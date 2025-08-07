"""Сервис для интеграций с внешними платформами."""
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.adapters.base import PlatformAdapter, PlatformManager, SyncResult as BaseSyncResult
from app.adapters.russian.wildberries import WildberriesAdapter
from app.adapters.russian.ozon import OzonAdapter
from app.adapters.russian.bitrix import BitrixAdapter
from app.adapters.russian.insales import InSalesAdapter
from app.adapters.international.shopify import ShopifyAdapter
from app.adapters.international.woocommerce import WooCommerceAdapter
from app.models.integration import IntegrationResult, PlatformInfo
from app.repositories.interfaces.integration_repository import IntegrationRepository


logger = structlog.get_logger()


class WebhookResult(BaseModel):
    """Результат обработки webhook."""

    message_id: str = Field(..., description="ID сообщения")
    status: str = Field(default="processed", description="Статус обработки")


# Use SyncResult from adapters.base (imported as BaseSyncResult)
SyncResult = BaseSyncResult


class IntegrationService:
    """Сервис для управления интеграциями с внешними платформами."""

    def __init__(self, integration_repository: IntegrationRepository) -> None:
        self.integration_repository = integration_repository
        self._webhook_handlers: dict[str, Callable[[dict[str, Any]], Awaitable[str]]] = self._setup_webhook_handlers()
        self.platform_manager = PlatformManager()
        self._adapters_cache: dict[str, PlatformAdapter] = {}

    async def get_user_integrations(self, user_id: str) -> list[PlatformInfo]:
        """Получить список подключенных интеграций для пользователя."""
        try:
            logger.info("Получение интеграций пользователя", user_id=user_id)
            return await self.integration_repository.get_user_integrations(user_id)
        except Exception as e:
            logger.error("Ошибка получения интеграций", error=str(e), user_id=user_id)
            return []

    async def connect_platform(
        self,
        user_id: str,
        platform: str,
        credentials: dict[str, str],
        configuration: dict[str, Any] | None = None
    ) -> IntegrationResult:
        """Подключить новую платформу.

        Args:
        ----
            user_id: ID пользователя
            platform: Название платформы
            credentials: Учетные данные для подключения
            configuration: Дополнительные настройки

        Returns:
        -------
            IntegrationResult: Результат подключения

        """
        try:
            logger.info("Подключение платформы", user_id=user_id, platform=platform)

            # Валидация платформы
            if not self._is_platform_supported(platform):
                raise ValueError(f"Платформа {platform} не поддерживается")

            # Проверка учетных данных
            await self._validate_credentials(platform, credentials)

            # Создание записи об интеграции через repository
            platform_info = await self.integration_repository.create_integration(
                user_id=user_id,
                platform_name=platform,
                credentials=credentials,
                configuration=configuration
            )
            
            if not platform_info:
                raise ValueError("Failed to create integration")
            
            platform_id = platform_info.platform_id

            logger.info(
                "Платформа успешно подключена",
                user_id=user_id,
                platform=platform,
                platform_id=platform_id
            )

            return IntegrationResult(platform_id=platform_id)

        except Exception as e:
            logger.error(
                "Ошибка подключения платформы",
                error=str(e),
                user_id=user_id,
                platform=platform
            )
            raise

    async def disconnect_platform(self, user_id: str, platform_id: str) -> None:
        """Отключить платформу."""
        try:
            logger.info("Отключение платформы", user_id=user_id, platform_id=platform_id)

            success = await self.integration_repository.disconnect_integration(platform_id)
            if not success:
                raise ValueError(f"Failed to disconnect platform {platform_id}")

            logger.info("Платформа отключена", user_id=user_id, platform_id=platform_id)

        except Exception as e:
            logger.error(
                "Ошибка отключения платформы",
                error=str(e),
                user_id=user_id,
                platform_id=platform_id
            )
            raise

    async def process_webhook(self, platform: str, payload: dict[str, Any]) -> WebhookResult:
        """Обработка входящего webhook.

        Args:
        ----
            platform: Название платформы
            payload: Данные webhook

        Returns:
        -------
            WebhookResult: Результат обработки

        """
        try:
            logger.info("Обработка webhook", platform=platform, event_type=payload.get("event_type"))

            # Получаем обработчик для платформы
            handler = self._webhook_handlers.get(platform)
            if not handler:
                raise ValueError(f"Обработчик для платформы {platform} не найден")

            # Обрабатываем webhook
            message_id = await handler(payload)

            logger.info("Webhook успешно обработан", platform=platform, message_id=message_id)

            return WebhookResult(message_id=message_id)

        except Exception as e:
            logger.error("Ошибка обработки webhook", error=str(e), platform=platform)
            raise

    async def _get_platform_adapter(self, platform_id: str) -> PlatformAdapter:
        """Получить адаптер для платформы по ID интеграции."""
        # Check cache first
        if platform_id in self._adapters_cache:
            return self._adapters_cache[platform_id]

        # Get integration info from repository
        integration = await self.integration_repository.get_by_id(platform_id)
        if not integration:
            raise ValueError(f"Integration {platform_id} not found")

        # Create adapter based on platform name
        adapter = await self._create_platform_adapter(
            platform_name=integration.platform_name,
            credentials=integration.credentials,
            configuration=integration.configuration
        )

        # Cache the adapter
        self._adapters_cache[platform_id] = adapter
        return adapter

    async def _create_platform_adapter(
        self,
        platform_name: str,
        credentials: dict[str, str],
        configuration: dict[str, Any] | None = None
    ) -> PlatformAdapter:
        """Создать адаптер для платформы."""
        config = configuration or {}
        
        if platform_name == "wildberries":
            api_key = credentials.get("api_key")
            if not api_key:
                raise ValueError("API key required for Wildberries")
            return WildberriesAdapter(
                api_key=api_key,
                jwt_secret=config.get("jwt_secret")
            )
        
        elif platform_name == "ozon":
            client_id = credentials.get("client_id")
            api_key = credentials.get("api_key")
            if not client_id or not api_key:
                raise ValueError("Client ID and API key required for Ozon")
            return OzonAdapter(
                client_id=client_id,
                api_key=api_key
            )
        
        elif platform_name == "1c-bitrix":
            webhook_url = credentials.get("webhook_url")
            if not webhook_url:
                raise ValueError("Webhook URL required for 1C-Bitrix")
            return BitrixAdapter(webhook_url=webhook_url)
        
        elif platform_name == "insales":
            api_key = credentials.get("api_key")
            password = credentials.get("password")
            domain = credentials.get("domain")
            if not all([api_key, password, domain]):
                raise ValueError("API key, password, and domain required for InSales")
            return InSalesAdapter(
                api_key=api_key,
                password=password,
                domain=domain
            )
        
        elif platform_name == "shopify":
            shop_domain = credentials.get("shop_domain")
            access_token = credentials.get("access_token")
            if not shop_domain or not access_token:
                raise ValueError("Shop domain and access token required for Shopify")
            return ShopifyAdapter(
                shop_domain=shop_domain,
                access_token=access_token
            )
        
        elif platform_name == "woocommerce":
            base_url = credentials.get("base_url")
            consumer_key = credentials.get("consumer_key")
            consumer_secret = credentials.get("consumer_secret")
            if not all([base_url, consumer_key, consumer_secret]):
                raise ValueError("Base URL, consumer key, and consumer secret required for WooCommerce")
            return WooCommerceAdapter(
                base_url=base_url,
                consumer_key=consumer_key,
                consumer_secret=consumer_secret
            )
        
        else:
            raise ValueError(f"Unsupported platform: {platform_name}")

    async def sync_platform_data(self, user_id: str, platform_id: str, operation: str = "orders") -> SyncResult:
        """Синхронизация данных с платформой."""
        start_time = datetime.now()
        
        try:
            logger.info(
                "Начата синхронизация данных",
                user_id=user_id,
                platform_id=platform_id,
                operation=operation
            )

            # Validate operation
            if operation not in ["orders", "products", "customers"]:
                raise ValueError(f"Unsupported operation: {operation}")

            # Get platform adapter
            adapter = await self._get_platform_adapter(platform_id)
            
            # Perform sync based on operation type
            if operation == "orders":
                sync_result = await adapter.sync_orders(limit=1000)
            elif operation == "products":
                sync_result = await adapter.sync_products(limit=1000)
            elif operation == "customers":
                sync_result = await adapter.sync_customers(limit=1000)
            else:
                # This shouldn't happen due to validation above, but keeping for safety
                raise ValueError(f"Unsupported operation: {operation}")

            # Update last sync time in repository
            await self.integration_repository.update_last_sync(
                integration_id=platform_id,
                sync_time=sync_result.timestamp
            )

            logger.info(
                "Синхронизация завершена успешно",
                user_id=user_id,
                platform_id=platform_id,
                operation=operation,
                records_processed=sync_result.records_processed,
                records_success=sync_result.records_success,
                records_failed=sync_result.records_failed,
                duration_seconds=sync_result.duration_seconds
            )

            return sync_result

        except Exception as e:
            # Create error result
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            
            logger.error(
                "Ошибка синхронизации",
                error=error_msg,
                user_id=user_id,
                platform_id=platform_id,
                operation=operation,
                duration_seconds=duration
            )

            # Return failed sync result instead of raising exception
            return SyncResult(
                platform="unknown",  # Will be updated by adapter if available
                operation=operation,
                records_processed=0,
                records_success=0,
                records_failed=0,
                errors=[error_msg],
                duration_seconds=duration,
                timestamp=datetime.now()
            )

    def _is_platform_supported(self, platform: str) -> bool:
        """Проверка поддержки платформы."""
        supported_platforms = {
            "wildberries", "ozon", "1c-bitrix", "insales",
            "shopify", "woocommerce", "telegram", "whatsapp",
            "vk", "yandex-alice", "viber"
        }
        return platform in supported_platforms

    async def _validate_credentials(self, platform: str, credentials: dict[str, str]) -> None:
        """Валидация учетных данных для платформы."""
        validation_rules = {
            "wildberries": ["api_key"],
            "ozon": ["client_id", "api_key"],
            "1c-bitrix": ["webhook_url"],
            "telegram": ["bot_token"],
            "whatsapp": ["access_token"],
            "yandex-alice": ["skill_id", "oauth_token"]
        }

        required_fields = validation_rules.get(platform, [])
        missing_fields = [field for field in required_fields if field not in credentials]

        if missing_fields:
            raise ValueError(f"Отсутствуют обязательные поля: {', '.join(missing_fields)}")

        # TODO: Добавить реальную проверку учетных данных через API платформ

    def _setup_webhook_handlers(self) -> dict[str, Callable[[dict[str, Any]], Awaitable[str]]]:
        """Настройка обработчиков webhook для каждой платформы."""
        return {
            "wildberries": self._handle_wildberries_webhook,
            "ozon": self._handle_ozon_webhook,
            "telegram": self._handle_telegram_webhook,
            "whatsapp": self._handle_whatsapp_webhook,
            "yandex-alice": self._handle_alice_webhook,
            "1c-bitrix": self._handle_bitrix_webhook
        }

    async def _handle_wildberries_webhook(self, payload: dict[str, Any]) -> str:
        """Обработка webhook от Wildberries."""
        event_type = payload.get("event_type")

        if event_type == "new_order":
            # Обработка нового заказа
            order_data = payload.get("data", {})
            logger.info("Новый заказ Wildberries", order_id=order_data.get("id"))

        elif event_type == "order_status_changed":
            # Изменение статуса заказа
            order_data = payload.get("data", {})
            logger.info(
                "Изменен статус заказа Wildberries",
                order_id=order_data.get("id"),
                status=order_data.get("status")
            )

        # TODO: Add proper security audit logging
        logger.info("Webhook processed successfully", platform="wildberries", event_type=event_type)

        return str(uuid.uuid4())

    async def _handle_ozon_webhook(self, payload: dict[str, Any]) -> str:
        """Обработка webhook от Ozon."""
        event_type = payload.get("event_type")

        if event_type == "posting_created":
            # Новое отправление
            posting_data = payload.get("data", {})
            logger.info("Новое отправление Ozon", posting_number=posting_data.get("posting_number"))

        return str(uuid.uuid4())

    async def _handle_telegram_webhook(self, payload: dict[str, Any]) -> str:
        """Обработка webhook от Telegram."""
        message_data = payload.get("data", {})

        if "message" in message_data:
            message = message_data["message"]
            user_id = message.get("from", {}).get("id")
            text = message.get("text", "")

            logger.info("Новое сообщение Telegram", user_id=user_id, text=text[:50])

            # TODO: Обработать сообщение через conversation service

        return str(uuid.uuid4())

    async def _handle_whatsapp_webhook(self, payload: dict[str, Any]) -> str:
        """Обработка webhook от WhatsApp."""
        entry = payload.get("data", {}).get("entry", [])

        for entry_item in entry:
            changes = entry_item.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])

                for message in messages:
                    from_number = message.get("from")
                    text = message.get("text", {}).get("body", "")

                    logger.info("Новое сообщение WhatsApp", from_number=from_number, text=text[:50])

                    # TODO: Обработать сообщение через conversation service

        return str(uuid.uuid4())

    async def _handle_alice_webhook(self, payload: dict[str, Any]) -> str:
        """Обработка webhook от Yandex Alice."""
        request_data = payload.get("data", {}).get("request", {})
        command = request_data.get("command", "")
        user_id = payload.get("data", {}).get("session", {}).get("user_id")

        logger.info("Команда Alice", user_id=user_id, command=command)

        # TODO: Обработать команду через conversation service

        return str(uuid.uuid4())

    async def _handle_bitrix_webhook(self, payload: dict[str, Any]) -> str:
        """Обработка webhook от 1C-Bitrix."""
        event = payload.get("event")
        data = payload.get("data", {})

        if event == "ONCRMDEALUPDATE":
            # Обновление сделки
            deal_id = data.get("FIELDS", {}).get("ID")
            logger.info("Обновление сделки Bitrix", deal_id=deal_id)

        return str(uuid.uuid4())

    async def cleanup(self):
        """Clean up resources and close adapter connections."""
        try:
            # Close all cached adapters
            for adapter in self._adapters_cache.values():
                await adapter.close()
            
            # Clear the cache
            self._adapters_cache.clear()
            
            # Close platform manager adapters
            await self.platform_manager.close_all()
            
            logger.info("Integration service cleanup completed")
            
        except Exception as e:
            logger.error("Error during integration service cleanup", error=str(e))
