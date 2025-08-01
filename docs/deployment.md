# 🚀 Деплой

## Docker

### Одиночный контейнер
```bash
docker build -t ai-support .
docker run -p 8000:8000 ai-support
```

### Docker Compose
```bash
# Запуск всех сервисов
docker-compose up -d

# Остановка
docker-compose down

# Пересборка
docker-compose up --build
```

## Kubernetes

### Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-support
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-support
  template:
    metadata:
      labels:
        app: ai-support
    spec:
      containers:
      - name: ai-support
        image: ai-support:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: ai-support-secrets
              key: database-url
```

### Service
```yaml
apiVersion: v1
kind: Service
metadata:
  name: ai-support-service
spec:
  selector:
    app: ai-support
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Ingress
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ai-support-ingress
spec:
  rules:
  - host: api.yourcompany.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ai-support-service
            port:
              number: 80
```

## Переменные окружения

Для production развертывания убедитесь в настройке всех необходимых переменных:

```bash
# Обязательные
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SECRET_KEY=strong-secret-key

# API ключи
OPENAI_API_KEY=sk-...
YANDEX_GPT_API_KEY=...
TELEGRAM_BOT_TOKEN=...
```

## Мониторинг

### Health Checks
```bash
# Базовая проверка здоровья
curl http://localhost:8000/health/

# Проверка базы данных
curl http://localhost:8000/health/db

# Проверка Redis
curl http://localhost:8000/health/redis
```

### Логирование
- Все логи выводятся в stdout/stderr
- Используйте structured logging (JSON формат)
- Настройте централизованный сбор логов (ELK, Fluentd)

### Метрики
- Prometheus metrics доступны на `/metrics`
- Настройте alerting для критических метрик
- Мониторьте использование ресурсов и производительность

## Безопасность

- Используйте HTTPS в production
- Настройте firewall и security groups
- Регулярно обновляйте зависимости
- Следуйте принципу наименьших привилегий для доступов

## Backup и восстановление

### База данных
```bash
# Создание backup
pg_dump -h localhost -U username database_name > backup.sql

# Восстановление
psql -h localhost -U username database_name < backup.sql
```

### Redis (если используется для персистентных данных)
```bash
# Создание backup
redis-cli BGSAVE

# Восстановление - скопируйте dump.rdb в директорию данных Redis
```