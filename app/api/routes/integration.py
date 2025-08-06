"""API endpoints для интеграций с внешними платформами."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

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
        # Russian e-commerce platforms
        "wildberries",
        "ozon",
        "1c-bitrix",
        "insales",
        # International e-commerce platforms
        "shopify",
        "woocommerce",
        "bigcommerce",
        "magento",
        # Messaging platforms
        "telegram",
        "whatsapp",
        "vk",
        "yandex-alice",
        "viber"
    ]


@router.get("/connected", response_model=list[PlatformInfo])
async def get_connected_platforms(
    user_id: str,
    integration_service: IntegrationService = Depends()
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
    integration_service: IntegrationService = Depends()
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
    integration_service: IntegrationService = Depends()
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
    integration_service: IntegrationService = Depends()
) -> dict[str, str]:
    """Обработка входящих webhook'ов от внешних платформ.

    Поддерживаемые платформы:
    Russian e-commerce:
    - wildberries: новые заказы, изменения статусов
    - ozon: обновления товаров, заказы
    - 1c-bitrix: обновления сделок, контактов
    - insales: события заказов и товаров
    
    International e-commerce:
    - shopify: заказы, продукты, клиенты
    - woocommerce: заказы, продукты, клиенты
    - bigcommerce: заказы, продукты, клиенты
    - magento: заказы, продукты, клиенты
    
    Messaging platforms:
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
    integration_service: IntegrationService = Depends()
) -> dict[str, Any]:
    """Принудительная синхронизация данных с платформой."""
    try:
        result = await integration_service.sync_platform_data(user_id, platform_id)
        return {
            "status": "synced",
            "records_updated": result.records_updated,
            "last_sync": result.sync_time
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации: {str(e)}"
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
