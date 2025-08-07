# 🚀 Деплойментный гайд

## Обзор развертывания

Easy Flow поддерживает различные варианты развертывания от локального Docker до production Kubernetes кластера.

### Архитектура production

```
┌─────────────────────────────────────────────────────────────────┐
│                        Load Balancer                            │
│                     (Nginx/Cloudflare)                         │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────────────────────────────────────────────────┐
│                   API Gateway Layer                            │
│                  (FastAPI instances)                           │
├─────────────┬─────────────┬─────────────┬─────────────────────┤
│   App-1     │   App-2     │   App-3     │     App-N           │
│ (FastAPI)   │ (FastAPI)   │ (FastAPI)   │   (Auto-scaling)    │
└─────────────┴─────────────┴─────────────┴─────────────────────┘
                      │
┌─────────────────────────────────────────────────────────────────┐
│                    Service Layer                               │
├─────────────┬─────────────┬─────────────┬─────────────────────┤
│  PostgreSQL │    Redis    │   Celery    │    Monitoring       │
│ (Primary +  │  (Cache +   │  (Workers)  │ (Prometheus+        │
│  Replica)   │  Sessions)  │             │  Grafana)          │
└─────────────┴─────────────┴─────────────┴─────────────────────┘
```

## Docker Deployment

### Production Dockerfile

```dockerfile
FROM python:3.12-slim as builder

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Установка зависимостей
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

# Production stage
FROM python:3.12-slim as runtime

# Создание пользователя
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Копирование приложения
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . .

# Права доступа
RUN chown -R appuser:appuser /app
USER appuser

# Переменные окружения
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Команда запуска
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  app:
    build: .
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@db:5432/easyflow
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  db:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: easyflow
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  celery-worker:
    build: .
    restart: unless-stopped
    command: celery -A app.core.celery worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@db:5432/easyflow
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      - db
      - redis
    deploy:
      replicas: 2

  celery-beat:
    build: .
    restart: unless-stopped
    command: celery -A app.core.celery beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@db:5432/easyflow
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      - db
      - redis

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - app

volumes:
  postgres_data:
  redis_data:
```

### Nginx конфигурация

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream app_backend {
        server app:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    
    server {
        listen 80;
        server_name your-domain.com;
        
        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        # SSL configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
        
        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000" always;

        # Gzip compression
        gzip on;
        gzip_types text/plain application/json application/javascript text/css;

        # API endpoints
        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;
            
            proxy_pass http://app_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Webhooks (higher rate limit)
        location /api/v1/messaging/webhook/ {
            limit_req zone=api_limit burst=100 nodelay;
            
            proxy_pass http://app_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check
        location /health {
            proxy_pass http://app_backend;
            access_log off;
        }

        # Static files
        location /static/ {
            alias /app/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

## Kubernetes Deployment

### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: easyflow
```

### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: easyflow-config
  namespace: easyflow
data:
  DATABASE_URL: "postgresql+asyncpg://postgres:password@postgres:5432/easyflow"
  REDIS_URL: "redis://redis:6379/0"
  LOG_LEVEL: "INFO"
  WORKERS: "4"
```

### Secrets

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: easyflow-secrets
  namespace: easyflow
type: Opaque
data:
  OPENAI_API_KEY: <base64-encoded-key>
  TELEGRAM_BOT_TOKEN: <base64-encoded-token>
  DATABASE_PASSWORD: <base64-encoded-password>
  SECRET_KEY: <base64-encoded-secret>
```

### PostgreSQL Deployment

```yaml
# k8s/postgres.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: easyflow
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: easyflow
        - name: POSTGRES_USER
          value: postgres
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: easyflow-secrets
              key: DATABASE_PASSWORD
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: easyflow
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
```

### Redis Deployment

```yaml
# k8s/redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: easyflow
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        command: ["redis-server", "--appendonly", "yes"]
        volumeMounts:
        - name: redis-storage
          mountPath: /data
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: redis-storage
        persistentVolumeClaim:
          claimName: redis-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: easyflow
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

### Application Deployment

```yaml
# k8s/app.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: easyflow-app
  namespace: easyflow
spec:
  replicas: 3
  selector:
    matchLabels:
      app: easyflow-app
  template:
    metadata:
      labels:
        app: easyflow-app
    spec:
      containers:
      - name: app
        image: easyflow:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: easyflow-config
        - secretRef:
            name: easyflow-secrets
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: easyflow-app-service
  namespace: easyflow
spec:
  selector:
    app: easyflow-app
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

### Horizontal Pod Autoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: easyflow-app-hpa
  namespace: easyflow
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: easyflow-app
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: easyflow-ingress
  namespace: easyflow
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.easyflow.dev
    secretName: easyflow-tls
  rules:
  - host: api.easyflow.dev
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: easyflow-app-service
            port:
              number: 80
```

## CI/CD Pipeline

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]
  release:
    types: [published]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Install uv
      uses: astral-sh/setup-uv@v1
      with:
        version: "latest"
    
    - name: Set up Python
      run: uv python install 3.12
    
    - name: Install dependencies
      run: uv sync
    
    - name: Run linting
      run: |
        uv run ruff check app/ tests/
        uv run mypy app/
    
    - name: Run tests
      run: uv run pytest tests/ --cov=app --cov-report=xml
      env:
        DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test_easyflow
        REDIS_URL: redis://localhost:6379/1
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'release'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    
    - name: Login to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: |
          ghcr.io/${{ github.repository }}:latest
          ghcr.io/${{ github.repository }}:${{ github.event.release.tag_name }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'release'
    environment: production
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Deploy to Kubernetes
      uses: azure/k8s-deploy@v1
      with:
        manifests: |
          k8s/configmap.yaml
          k8s/secrets.yaml
          k8s/postgres.yaml
          k8s/redis.yaml
          k8s/app.yaml
          k8s/hpa.yaml
          k8s/ingress.yaml
        images: |
          ghcr.io/${{ github.repository }}:${{ github.event.release.tag_name }}
        kubeconfig: ${{ secrets.KUBE_CONFIG }}
```

## Мониторинг

### Prometheus конфигурация

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'easyflow-app'
    static_configs:
      - targets: ['app:8000']
    metrics_path: '/metrics'
    
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
    
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Easy Flow Monitoring",
    "panels": [
      {
        "title": "API Response Time",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Message Processing Rate",
        "targets": [
          {
            "expr": "rate(messages_processed_total[5m])",
            "legendFormat": "Messages/sec"
          }
        ]
      },
      {
        "title": "AI API Calls",
        "targets": [
          {
            "expr": "rate(ai_api_calls_total[5m])",
            "legendFormat": "{{provider}}"
          }
        ]
      }
    ]
  }
}
```

## Security

### Security Headers

```python
# app/middleware/security.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware

def setup_security_middleware(app: FastAPI):
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://your-domain.com"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Trusted hosts
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["your-domain.com", "api.your-domain.com"]
    )
    
    # Sessions
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        same_site="strict",
        https_only=True
    )
```

### SSL/TLS конфигурация

```bash
# Получение Let's Encrypt сертификата
certbot --nginx -d your-domain.com -d api.your-domain.com

# Автоматическое обновление
echo "0 2 * * * certbot renew --quiet && systemctl reload nginx" | crontab -
```

## Backup стратегия

### Автоматический backup PostgreSQL

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME="easyflow"

# Создание backup
pg_dump -h postgres -U postgres -d $DB_NAME > $BACKUP_DIR/easyflow_$DATE.sql

# Сжатие
gzip $BACKUP_DIR/easyflow_$DATE.sql

# Удаление старых backup'ов (старше 7 дней)
find $BACKUP_DIR -name "easyflow_*.sql.gz" -mtime +7 -delete

# Загрузка в S3
aws s3 cp $BACKUP_DIR/easyflow_$DATE.sql.gz s3://your-backup-bucket/database/
```

### Kubernetes CronJob для backup

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: easyflow
spec:
  schedule: "0 2 * * *"  # Каждый день в 2:00
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: postgres-backup
            image: postgres:15-alpine
            command:
            - /bin/bash
            - -c
            - |
              pg_dump -h postgres -U postgres easyflow | gzip > /backup/easyflow_$(date +%Y%m%d_%H%M%S).sql.gz
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: easyflow-secrets
                  key: DATABASE_PASSWORD
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
```

---

🤖 Создано с помощью [Claude Code](https://claude.ai/code)