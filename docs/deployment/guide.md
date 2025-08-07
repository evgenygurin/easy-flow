# Деплой

Docker
```bash
docker-compose up -d
# или
docker build -t easy-flow .
docker run -p 8000:8000 easy-flow
```

Переменные окружения
- См. `README.md` и `app/core/config.py` — ключи AI, e‑commerce, мессенджеры, платежи

Производственный запуск
- Uvicorn/Gunicorn, reverse proxy (NGINX), Redis, Postgres
- Логи/метрики: агрегировать (ELK/Prometheus)
- Секреты: через менеджер секретов/CI‑CD variables

Kubernetes (эскиз)
- Deployment (3 реплики), Service, Ingress; readiness/liveness probes
- ConfigMap/Secret для конфигурации

Обновления
- Blue/Green или Rolling Update
- Миграции БД через Alembic (если включены репозитории + БД)
