"""API endpoints для интеграций с внешними платформами."""
from typing import Any

from fastapi import APIRouter, Depends

from app.api.controllers.integration_controller import (
    IntegrationController,
    SyncOperationRequest
)
from app.api.dependencies import get_integration_controller
from app.models.integration import (
    IntegrationRequest,
    PlatformInfo,
    WebhookPayload,
)


router = APIRouter()


@router.get("/platforms", response_model=list[str])
async def get_supported_platforms(
    controller: IntegrationController = Depends(get_integration_controller)
) -> list[str]:
    """Получить список поддерживаемых платформ интеграции."""
    return await controller.get_supported_platforms()


@router.get("/connected", response_model=list[PlatformInfo])
async def get_connected_platforms(
    user_id: str,
    controller: IntegrationController = Depends(get_integration_controller)
) -> list[PlatformInfo]:
    """Получить список подключенных платформ для пользователя."""
    return await controller.get_connected_platforms(user_id)


@router.post("/connect")
async def connect_platform(
    user_id: str,
    request: IntegrationRequest,
    controller: IntegrationController = Depends(get_integration_controller)
) -> dict[str, str]:
    """Подключить новую платформу."""
    return await controller.connect_platform(user_id, request)


@router.delete("/disconnect/{platform_id}")
async def disconnect_platform(
    platform_id: str,
    user_id: str,
    controller: IntegrationController = Depends(get_integration_controller)
) -> dict[str, str]:
    """Отключить платформу."""
    return await controller.disconnect_platform(platform_id, user_id)


@router.post("/webhook/{platform}")
async def handle_webhook(
    platform: str,
    payload: WebhookPayload,
    controller: IntegrationController = Depends(get_integration_controller)
) -> dict[str, str]:
    """Обработка входящих webhook'ов от внешних платформ.

    Поддерживаемые платформы:

    Russian e-commerce:
    - wildberries: новые заказы, изменения статусов
    - ozon: обновления товаров, заказы, чат-сообщения
    - 1c-bitrix: обновления сделок, контактов, товаров
    - insales: заказы, товары, клиенты

    International e-commerce:
    - shopify: заказы, товары, клиенты
    - woocommerce: WordPress интеграция
    - bigcommerce: полный спектр событий
    - magento: заказы и каталог

    Messaging:
    - telegram: входящие сообщения
    - whatsapp: сообщения клиентов
    - yandex-alice: команды голосового ассистента
    """
    return await controller.handle_webhook(platform, payload)


@router.post("/sync/{platform_id}")
async def sync_platform_data(
    platform_id: str,
    user_id: str,
    operation: str = "orders",
    controller: IntegrationController = Depends(get_integration_controller)
) -> dict[str, Any]:
    """Принудительная синхронизация данных с платформой.

    Args:
    ----
        platform_id: ID платформы для синхронизации
        user_id: ID пользователя
        operation: Тип операции синхронизации (orders, products, customers)

    """
    request = SyncOperationRequest(operation=operation)
    return await controller.sync_platform_data(platform_id, user_id, request)


@router.get("/health")
async def get_health_status() -> dict[str, str]:
    """Получить статус здоровья всех интеграций."""
    # TODO: Implement health check through controller after service refactoring
    return {"status": "healthy"}


@router.get("/audit-logs")
async def get_audit_logs(
    user_id: str = None,
    platform: str = None,
    action: str = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Получить журнал аудита интеграций."""
    # TODO: Implement audit logs through controller after service refactoring
    limit = min(limit, 1000)
    return {
        "logs": [],
        "total": 0,
        "filters": {
            "user_id": user_id,
            "platform": platform,
            "action": action,
            "limit": limit
        }
    }


@router.post("/sync-all")
async def sync_all_platforms(
    user_id: str,
    operation: str = "orders",
    controller: IntegrationController = Depends(get_integration_controller)
) -> dict[str, Any]:
    """Синхронизация данных со всеми подключенными платформами."""
    request = SyncOperationRequest(operation=operation)
    return await controller.sync_all_platforms(user_id, request)


@router.get("/webhook-url/{platform}")
async def get_webhook_url(
    platform: str,
    controller: IntegrationController = Depends(get_integration_controller)
) -> dict[str, str]:
    """Получить URL для настройки webhook'а на внешней платформе."""
    return await controller.get_webhook_url(platform)
