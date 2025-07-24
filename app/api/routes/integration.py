"""
API endpoints для интеграций с внешними платформами.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.services.integration_service import IntegrationService

router = APIRouter()


class PlatformInfo(BaseModel):
    """Информация о подключенной платформе."""
    platform_id: str
    platform_name: str
    status: str
    connected_at: datetime
    last_sync: Optional[datetime] = None
    configuration: Dict[str, Any]


class WebhookPayload(BaseModel):
    """Входящий webhook от внешней платформы."""
    platform: str = Field(..., description="Название платформы")
    event_type: str = Field(..., description="Тип события")
    data: Dict[str, Any] = Field(..., description="Данные события")
    timestamp: Optional[datetime] = Field(None, description="Время события")
    signature: Optional[str] = Field(None, description="Подпись для проверки")


class IntegrationRequest(BaseModel):
    """Запрос на подключение интеграции."""
    platform: str = Field(..., description="Название платформы")
    credentials: Dict[str, str] = Field(..., description="Данные для подключения")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Дополнительные настройки")


@router.get("/platforms", response_model=List[str])
async def get_supported_platforms() -> List[str]:
    """Получить список поддерживаемых платформ интеграции."""
    return [
        "wildberries",
        "ozon", 
        "1c-bitrix",
        "insales",
        "shopify",
        "woocommerce",
        "telegram",
        "whatsapp",
        "vk",
        "yandex-alice"
    ]


@router.get("/connected", response_model=List[PlatformInfo])
async def get_connected_platforms(
    user_id: str,
    integration_service: IntegrationService = Depends()
) -> List[PlatformInfo]:
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
) -> Dict[str, str]:
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
) -> Dict[str, str]:
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
) -> Dict[str, str]:
    """
    Обработка входящих webhook'ов от внешних платформ.
    
    Поддерживаемые платформы:
    - wildberries: новые заказы, изменения статусов
    - ozon: обновления товаров, заказы
    - telegram: входящие сообщения
    - whatsapp: сообщения клиентов
    - alice: команды голосового ассистента
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
) -> Dict[str, Any]:
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
async def get_webhook_url(platform: str) -> Dict[str, str]:
    """Получить URL для настройки webhook'а на внешней платформе."""
    base_url = "https://your-domain.com"  # TODO: получать из конфигурации
    webhook_url = f"{base_url}/api/v1/integration/webhook/{platform}"
    
    return {
        "webhook_url": webhook_url,
        "platform": platform,
        "instructions": f"Настройте этот URL в админ-панели {platform}"
    }