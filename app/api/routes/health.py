"""Health check endpoints для мониторинга состояния сервиса."""
import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.repository_service import repository_service


router = APIRouter()


class HealthResponse(BaseModel):
    """Модель ответа health check."""

    status: str
    timestamp: float
    version: str
    checks: dict[str, Any]


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Основной health check endpoint.
    Проверяет состояние всех критичных компонентов системы.
    """
    checks = {}

    # Проверка базы данных
    try:
        start_time = time.time()
        if repository_service.available:
            is_healthy = await repository_service.health_check()
            response_time_ms = int((time.time() - start_time) * 1000)
            if is_healthy:
                checks["database"] = {"status": "healthy", "response_time_ms": response_time_ms}
            else:
                checks["database"] = {"status": "unhealthy", "error": "Database connection failed"}
        else:
            checks["database"] = {"status": "unhealthy", "error": "Database not configured"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    # Проверка Redis (заглушка)
    try:
        # TODO: Добавить реальную проверку Redis
        checks["redis"] = {"status": "healthy", "response_time_ms": 2}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}

    # Проверка AI сервисов (заглушка)
    try:
        # TODO: Добавить проверку доступности OpenAI/YandexGPT
        checks["ai_services"] = {"status": "healthy", "response_time_ms": 100}
    except Exception as e:
        checks["ai_services"] = {"status": "unhealthy", "error": str(e)}

    # Определяем общий статус
    overall_status = "healthy"
    for check in checks.values():
        if check["status"] != "healthy":
            overall_status = "unhealthy"
            break

    return HealthResponse(
        status=overall_status,
        timestamp=time.time(),
        version="0.1.0",
        checks=checks
    )


@router.get("/liveness")
async def liveness_probe() -> dict[str, str]:
    """Liveness probe для Kubernetes."""
    return {"status": "alive"}


@router.get("/readiness")
async def readiness_probe() -> dict[str, str]:
    """Readiness probe для Kubernetes."""
    # Проверяем готовность сервисов
    try:
        if repository_service.available and await repository_service.health_check():
            return {"status": "ready"}
        else:
            return {"status": "not_ready"}
    except Exception:
        return {"status": "not_ready"}
