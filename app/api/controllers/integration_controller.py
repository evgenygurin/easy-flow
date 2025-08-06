"""Контроллер для интеграций с внешними платформами."""
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.api.controllers.base import BaseController
from app.models.integration import IntegrationRequest, PlatformInfo, WebhookPayload
from app.services.integration_service import IntegrationService


class SyncOperationRequest(BaseModel):
    """Запрос на операцию синхронизации."""

    operation: str = Field(
        default="orders",
        description="Тип операции синхронизации (orders, products, customers)"
    )


class IntegrationController(BaseController):
    """Контроллер для интеграций - только HTTP логика."""
    
    def __init__(self, integration_service: IntegrationService) -> None:
        """Инициализация контроллера интеграций.
        
        Args:
        ----
            integration_service: Сервис для работы с интеграциями
            
        """
        super().__init__()
        self.integration_service = integration_service
    
    async def get_supported_platforms(self) -> list[str]:
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
    
    async def get_connected_platforms(self, user_id: str) -> list[PlatformInfo]:
        """Получить список подключенных платформ для пользователя.
        
        Args:
        ----
            user_id: Идентификатор пользователя
            
        Returns:
        -------
            Список подключенных платформ
            
        """
        validated_user_id = self.validate_id(user_id, "user_id")
        
        return await self.handle_request(
            self.integration_service.get_user_integrations,
            validated_user_id
        )
    
    async def connect_platform(
        self,
        user_id: str,
        request: IntegrationRequest
    ) -> dict[str, str]:
        """Подключить новую платформу.
        
        Args:
        ----
            user_id: Идентификатор пользователя
            request: Данные для подключения платформы
            
        Returns:
        -------
            Результат подключения
            
        """
        validated_user_id = self.validate_id(user_id, "user_id")
        
        result = await self.handle_request(
            self.integration_service.connect_platform,
            validated_user_id,
            request.platform,
            request.credentials,
            request.configuration
        )
        
        return {"status": "connected", "platform_id": result.platform_id}
    
    async def disconnect_platform(
        self,
        platform_id: str,
        user_id: str
    ) -> dict[str, str]:
        """Отключить платформу.
        
        Args:
        ----
            platform_id: Идентификатор платформы
            user_id: Идентификатор пользователя
            
        Returns:
        -------
            Результат отключения
            
        """
        validated_platform_id = self.validate_id(platform_id, "platform_id")
        validated_user_id = self.validate_id(user_id, "user_id")
        
        await self.handle_request(
            self.integration_service.disconnect_platform,
            validated_user_id,
            validated_platform_id
        )
        
        return {"status": "disconnected"}
    
    async def handle_webhook(
        self,
        platform: str,
        payload: WebhookPayload
    ) -> dict[str, str]:
        """Обработка входящих webhook'ов от внешних платформ.
        
        Args:
        ----
            platform: Название платформы
            payload: Данные webhook'а
            
        Returns:
        -------
            Результат обработки webhook'а
            
        """
        if not platform or not platform.strip():
            raise HTTPException(
                status_code=400,
                detail="Название платформы не может быть пустым"
            )
        
        result = await self.handle_request(
            self.integration_service.process_webhook,
            platform.strip(),
            payload.dict()
        )
        
        return {"status": "processed", "message_id": result.message_id}
    
    async def sync_platform_data(
        self,
        platform_id: str,
        user_id: str,
        request: SyncOperationRequest
    ) -> dict[str, Any]:
        """Принудительная синхронизация данных с платформой.
        
        Args:
        ----
            platform_id: ID платформы для синхронизации
            user_id: ID пользователя
            request: Параметры синхронизации
            
        Returns:
        -------
            Результат синхронизации
            
        """
        validated_platform_id = self.validate_id(platform_id, "platform_id")
        validated_user_id = self.validate_id(user_id, "user_id")
        
        # Валидация операции
        if request.operation not in ["orders", "products", "customers"]:
            raise HTTPException(
                status_code=400,
                detail="Операция должна быть: orders, products, или customers"
            )
        
        result = await self.handle_request(
            self.integration_service.sync_platform_data,
            validated_user_id,
            validated_platform_id,
            request.operation
        )
        
        return {
            "status": "synced",
            "operation": request.operation,
            "platform": result.platform,
            "records_processed": result.records_processed,
            "records_success": result.records_success,
            "records_failed": result.records_failed,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
            "timestamp": result.timestamp.isoformat()
        }
    
    async def sync_all_platforms(
        self,
        user_id: str,
        request: SyncOperationRequest
    ) -> dict[str, Any]:
        """Синхронизация данных со всеми подключенными платформами.
        
        Args:
        ----
            user_id: Идентификатор пользователя
            request: Параметры синхронизации
            
        Returns:
        -------
            Результат массовой синхронизации
            
        """
        validated_user_id = self.validate_id(user_id, "user_id")
        
        # Валидация операции
        if request.operation not in ["orders", "products", "customers"]:
            raise HTTPException(
                status_code=400,
                detail="Операция должна быть: orders, products, или customers"
            )
        
        # Получение списка интеграций
        integrations = await self.handle_request(
            self.integration_service.get_user_integrations,
            validated_user_id
        )
        
        # Синхронизация каждой платформы
        results = []
        for integration in integrations:
            try:
                result = await self.integration_service.sync_platform_data(
                    validated_user_id, integration.platform_id, request.operation
                )
                
                # Check if sync was successful based on errors
                success = len(result.errors) == 0
                
                results.append({
                    "platform": integration.platform_name,
                    "platform_id": integration.platform_id,
                    "success": success,
                    "records_processed": result.records_processed,
                    "records_success": result.records_success,
                    "records_failed": result.records_failed,
                    "duration_seconds": result.duration_seconds,
                    "errors": result.errors,
                    "timestamp": result.timestamp.isoformat()
                })
            except Exception as e:
                # This shouldn't happen now since sync_platform_data doesn't raise exceptions
                # but keeping for backward compatibility
                results.append({
                    "platform": integration.platform_name,
                    "platform_id": integration.platform_id,
                    "success": False,
                    "records_processed": 0,
                    "records_success": 0,
                    "records_failed": 0,
                    "duration_seconds": 0.0,
                    "errors": [str(e)],
                    "timestamp": datetime.now().isoformat()
                })
        
        return {
            "status": "completed",
            "operation": request.operation,
            "platforms_synced": len(results),
            "results": results
        }
    
    async def get_webhook_url(self, platform: str) -> dict[str, str]:
        """Получить URL для настройки webhook'а на внешней платформе.
        
        Args:
        ----
            platform: Название платформы
            
        Returns:
        -------
            Данные для настройки webhook'а
            
        """
        if not platform or not platform.strip():
            raise HTTPException(
                status_code=400,
                detail="Название платформы не может быть пустым"
            )
        
        base_url = "https://your-domain.com"  # TODO: получать из конфигурации
        webhook_url = f"{base_url}/api/v1/integration/webhook/{platform.strip()}"
        
        return {
            "webhook_url": webhook_url,
            "platform": platform.strip(),
            "instructions": f"Настройте этот URL в админ-панели {platform.strip()}"
        }