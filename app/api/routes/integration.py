"""API endpoints для интеграций с внешними платформами."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_integration_service
from app.models.integration import (
    IntegrationRequest,
    PlatformInfo,
    WebhookPayload,
)
from app.services.integration_service import IntegrationService


router = APIRouter()


@router.get("/platforms", response_model=list[str])
async def get_supported_platforms() -> list[str]:
    """Получить список поддерживаемых платформ интеграции."""
    return [
        # Russian e-commerce platforms (Phase 1)
        "wildberries",
        "ozon",
        "1c-bitrix",
        "insales",

        # International e-commerce platforms (Phase 2)
        "shopify",
        "woocommerce",
        "bigcommerce",
        "magento",

        # Messaging platforms
        "telegram",
        "whatsapp",
        "vk",
        "viber",

        # Voice assistants
        "yandex-alice"
    ]


@router.get("/connected", response_model=list[PlatformInfo])
async def get_connected_platforms(
    user_id: str,
    integration_service: IntegrationService = Depends(get_integration_service)
) -> list[PlatformInfo]:
    """Получить список подключенных платформ для пользователя."""
    try:
        return await integration_service.get_user_integrations(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения интеграций: {str(e)}"
        )


@router.post("/connect")
async def connect_platform(
    user_id: str,
    request: IntegrationRequest,
    integration_service: IntegrationService = Depends(get_integration_service)
) -> dict[str, str]:
    """Подключить новую платформу."""
    try:
        result = await integration_service.connect_platform(
            user_id=user_id,
            platform=request.platform,
            credentials=request.credentials,
            configuration=request.configuration
        )
        return {"status": "connected", "platform_id": result.platform_id}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Ошибка подключения платформы: {str(e)}"
        )


@router.delete("/disconnect/{platform_id}")
async def disconnect_platform(
    platform_id: str,
    user_id: str,
    integration_service: IntegrationService = Depends(get_integration_service)
) -> dict[str, str]:
    """Отключить платформу."""
    try:
        await integration_service.disconnect_platform(user_id, platform_id)
        return {"status": "disconnected"}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Ошибка отключения платформы: {str(e)}"
        )


@router.post("/webhook/{platform}")
async def handle_webhook(
    platform: str,
    payload: WebhookPayload,
    integration_service: IntegrationService = Depends(get_integration_service)
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
    try:
        result = await integration_service.process_webhook(platform, payload.dict())
        return {"status": "processed", "message_id": result.message_id}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Ошибка обработки webhook: {str(e)}"
        )


@router.post("/sync/{platform_id}")
async def sync_platform_data(
    platform_id: str,
    user_id: str,
    operation: str = "orders",
    integration_service: IntegrationService = Depends(get_integration_service)
) -> dict[str, Any]:
    """Принудительная синхронизация данных с платформой.

    Args:
    ----
        platform_id: ID платформы для синхронизации
        user_id: ID пользователя
        operation: Тип операции синхронизации (orders, products, customers)

    """
    if operation not in ["orders", "products", "customers"]:
        raise HTTPException(
            status_code=400,
            detail="Операция должна быть: orders, products, или customers"
        )

    try:
        result = await integration_service.sync_platform_data(user_id, platform_id, operation)
        return {
            "status": "synced",
            "operation": operation,
            "records_processed": result.records_processed,
            "records_success": result.records_success,
            "records_failed": result.records_failed,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
            "timestamp": result.timestamp
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


@router.get("/health")
async def get_health_status(
    integration_service: IntegrationService = Depends(get_integration_service)
) -> dict[str, Any]:
    """Получить статус здоровья всех интеграций."""
    try:
        health_status = await integration_service.platform_manager.get_all_health_status()
        return health_status
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения статуса здоровья: {str(e)}"
        )


@router.get("/audit-logs")
async def get_audit_logs(
    user_id: str = None,
    platform: str = None,
    action: str = None,
    limit: int = 100,
    integration_service: IntegrationService = Depends(get_integration_service)
) -> dict[str, Any]:
    """Получить журнал аудита интеграций."""
    try:
        limit = min(limit, 1000)

        audit_logs = integration_service.security_manager.get_audit_logs(
            platform=platform,
            user_id=user_id,
            action=action,
            limit=limit
        )

        return {
            "logs": [log.dict() for log in audit_logs],
            "total": len(audit_logs),
            "filters": {
                "user_id": user_id,
                "platform": platform,
                "action": action,
                "limit": limit
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения журнала аудита: {str(e)}"
        )


@router.post("/sync-all")
async def sync_all_platforms(
    user_id: str,
    operation: str = "orders",
    integration_service: IntegrationService = Depends(get_integration_service)
) -> dict[str, Any]:
    """Синхронизация данных со всеми подключенными платформами."""
    if operation not in ["orders", "products", "customers"]:
        raise HTTPException(
            status_code=400,
            detail="Операция должна быть: orders, products, или customers"
        )

    try:
        # Get user integrations
        integrations = await integration_service.get_user_integrations(user_id)
        results = []

        # Sync each platform
        for integration in integrations:
            try:
                result = await integration_service.sync_platform_data(
                    user_id, integration.platform_id, operation
                )
                results.append({
                    "platform": integration.platform_name,
                    "platform_id": integration.platform_id,
                    "success": True,
                    "records_processed": result.records_processed,
                    "records_success": result.records_success,
                    "records_failed": result.records_failed,
                    "errors": result.errors
                })
            except Exception as e:
                results.append({
                    "platform": integration.platform_name,
                    "platform_id": integration.platform_id,
                    "success": False,
                    "error": str(e)
                })

        return {
            "status": "completed",
            "operation": operation,
            "platforms_synced": len(results),
            "results": results
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка массовой синхронизации: {str(e)}"
        )


@router.get("/webhook-url/{platform}")
async def get_webhook_url(platform: str) -> dict[str, str]:
    """Получить URL для настройки webhook'а на внешней платформе."""
    base_url = "https://your-domain.com"  # TODO: получать из конфигурации
    webhook_url = f"{base_url}/api/v1/integration/webhook/{platform}"

    return {
        "webhook_url": webhook_url,
        "platform": platform,
        "instructions": f"Настройте этот URL в админ-панели {platform}"
    }
