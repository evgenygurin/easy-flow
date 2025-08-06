"""Unified Integration Manager для управления всеми интеграциями."""
import asyncio
from datetime import datetime
from typing import Any

import structlog

from app.integrations.base import IntegrationHealthCheck, PlatformAdapter, SyncResult
from app.integrations.bitrix import BitrixAdapter
from app.integrations.insales import InSalesAdapter
from app.integrations.ozon import OzonAdapter
from app.integrations.security import audit_logger, credential_manager, rate_limit_manager
from app.integrations.wildberries import WildberriesAdapter
from app.models.integration import IntegrationResult, PlatformInfo


logger = structlog.get_logger()


class IntegrationManager:
    """Unified менеджер для всех интеграций e-commerce платформ."""

    def __init__(self):
        self.adapters: dict[str, type[PlatformAdapter]] = {
            "wildberries": WildberriesAdapter,
            "ozon": OzonAdapter,
            "1c-bitrix": BitrixAdapter,
            "insales": InSalesAdapter,
            # Готово для добавления международных платформ
            # "shopify": ShopifyAdapter,
            # "woocommerce": WooCommerceAdapter,
            # "bigcommerce": BigCommerceAdapter,
        }
        
        self.active_integrations: dict[str, PlatformAdapter] = {}
        self.health_checks: dict[str, IntegrationHealthCheck] = {}
        
        # Статистика
        self.sync_stats = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "last_sync": None
        }

    async def connect_platform(
        self,
        user_id: str,
        platform: str,
        credentials: dict[str, str],
        configuration: dict[str, Any] | None = None
    ) -> IntegrationResult:
        """Подключить платформу с безопасным хранением учетных данных."""
        try:
            logger.info("Подключение платформы", user_id=user_id, platform=platform)
            
            # Валидация платформы
            if platform not in self.adapters:
                raise ValueError(f"Платформа {platform} не поддерживается")

            # Валидация учетных данных
            if not credential_manager.validate_credentials(platform, credentials):
                raise ValueError("Некорректные учетные данные")

            # Проверка rate limit
            can_connect, remaining = rate_limit_manager.can_make_request(platform, user_id)
            if not can_connect:
                raise ValueError("Превышен лимит подключений")

            # Создание адаптера
            adapter_class = self.adapters[platform]
            adapter = adapter_class(credentials, configuration)

            # Проверка подключения
            if not await adapter.authenticate():
                raise ValueError("Ошибка аутентификации")

            # Шифрование и сохранение учетных данных
            encrypted_credentials = credential_manager.encrypt_credentials(credentials)
            
            # Создание записи об интеграции
            platform_id = f"{platform}_{user_id}_{int(datetime.now().timestamp())}"
            
            platform_info = PlatformInfo(
                platform_id=platform_id,
                platform_name=platform,
                status="connected",
                connected_at=datetime.now(),
                configuration=configuration or {}
            )

            # Сохранение активной интеграции
            integration_key = f"{user_id}:{platform_id}"
            self.active_integrations[integration_key] = adapter
            self.health_checks[integration_key] = IntegrationHealthCheck(adapter)

            # Аудит лог
            audit_logger.log_integration_event(
                event_type="platform_connected",
                platform=platform,
                user_id=user_id,
                details={"platform_id": platform_id}
            )

            # Запись использования rate limit
            rate_limit_manager.record_request(platform, user_id)

            logger.info("Платформа успешно подключена", platform_id=platform_id)

            return IntegrationResult(
                platform_id=platform_id,
                success=True,
                message="Платформа успешно подключена"
            )

        except Exception as e:
            logger.error("Ошибка подключения платформы", error=str(e), platform=platform)
            
            audit_logger.log_error(
                error_type="connection_failed",
                platform=platform,
                error_message=str(e),
                user_id=user_id
            )
            
            raise

    async def disconnect_platform(self, user_id: str, platform_id: str) -> bool:
        """Отключить платформу."""
        try:
            integration_key = f"{user_id}:{platform_id}"
            
            if integration_key in self.active_integrations:
                adapter = self.active_integrations[integration_key]
                platform = adapter.platform_name
                
                # Удаление из активных интеграций
                del self.active_integrations[integration_key]
                if integration_key in self.health_checks:
                    del self.health_checks[integration_key]

                # Аудит лог
                audit_logger.log_integration_event(
                    event_type="platform_disconnected",
                    platform=platform,
                    user_id=user_id,
                    details={"platform_id": platform_id}
                )

                logger.info("Платформа отключена", platform_id=platform_id)
                return True

            return False

        except Exception as e:
            logger.error("Ошибка отключения платформы", error=str(e))
            return False

    async def sync_all_platforms(self, user_id: str, since: datetime | None = None) -> dict[str, SyncResult]:
        """Синхронизация всех подключенных платформ пользователя."""
        results = {}
        user_integrations = [
            (key, adapter) for key, adapter in self.active_integrations.items()
            if key.startswith(f"{user_id}:")
        ]

        logger.info(f"Синхронизация {len(user_integrations)} платформ для пользователя {user_id}")

        # Параллельная синхронизация всех платформ
        sync_tasks = []
        for integration_key, adapter in user_integrations:
            task = self._sync_platform_safe(integration_key, adapter, since)
            sync_tasks.append(task)

        if sync_tasks:
            sync_results = await asyncio.gather(*sync_tasks, return_exceptions=True)
            
            for (integration_key, adapter), result in zip(user_integrations, sync_results):
                platform = adapter.platform_name
                if isinstance(result, Exception):
                    results[platform] = SyncResult(
                        success=False,
                        sync_type="full",
                        errors=[str(result)]
                    )
                else:
                    results[platform] = result

        # Обновление статистики
        self._update_sync_stats(results)

        return results

    async def process_webhook(
        self,
        platform: str,
        event_type: str,
        payload: dict[str, Any],
        signature: str | None = None
    ) -> str:
        """Обработка webhook от любой платформы."""
        try:
            start_time = datetime.now()
            
            logger.info("Обработка webhook", platform=platform, event_type=event_type)

            # Поиск активного адаптера для платформы
            matching_adapters = [
                (key, adapter) for key, adapter in self.active_integrations.items()
                if adapter.platform_name == platform
            ]

            if not matching_adapters:
                raise ValueError(f"Нет активных интеграций для платформы {platform}")

            # Обрабатываем через первый найденный адаптер
            # В реальности здесь может быть более сложная логика маршрутизации
            _, adapter = matching_adapters[0]
            
            message_id = await adapter.handle_webhook(event_type, payload)
            
            # Логирование для аудита
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            audit_logger.log_webhook_received(
                platform=platform,
                event_type=event_type,
                payload_size=len(str(payload)),
                processing_time_ms=processing_time
            )

            return message_id

        except Exception as e:
            logger.error("Ошибка обработки webhook", error=str(e), platform=platform)
            
            audit_logger.log_error(
                error_type="webhook_processing_failed",
                platform=platform,
                error_message=str(e)
            )
            
            raise

    async def get_platform_status(self, user_id: str, platform_id: str) -> dict[str, Any]:
        """Получить статус конкретной платформы."""
        integration_key = f"{user_id}:{platform_id}"
        
        if integration_key not in self.active_integrations:
            return {"status": "not_found"}

        adapter = self.active_integrations[integration_key]
        health_check = self.health_checks[integration_key]

        try:
            health_status = await health_check.check_health()
            
            return {
                "status": "active",
                "platform": adapter.platform_name,
                "health": health_status,
                "last_check": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "status": "error",
                "platform": adapter.platform_name,
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }

    async def get_all_platform_statuses(self, user_id: str) -> dict[str, dict[str, Any]]:
        """Получить статус всех платформ пользователя."""
        user_integrations = [
            (key, adapter) for key, adapter in self.active_integrations.items()
            if key.startswith(f"{user_id}:")
        ]

        statuses = {}
        
        # Параллельная проверка статусов
        status_tasks = []
        for integration_key, adapter in user_integrations:
            platform_id = integration_key.split(":")[-1]
            task = self.get_platform_status(user_id, platform_id)
            status_tasks.append((adapter.platform_name, task))

        if status_tasks:
            for platform_name, task in status_tasks:
                try:
                    status = await task
                    statuses[platform_name] = status
                except Exception as e:
                    statuses[platform_name] = {
                        "status": "error",
                        "error": str(e)
                    }

        return statuses

    async def update_order_status_across_platforms(
        self,
        user_id: str,
        order_id: str,
        new_status: str
    ) -> dict[str, bool]:
        """Обновить статус заказа во всех подключенных платформах."""
        user_integrations = [
            (key, adapter) for key, adapter in self.active_integrations.items()
            if key.startswith(f"{user_id}:")
        ]

        results = {}

        for integration_key, adapter in user_integrations:
            try:
                if hasattr(adapter, 'update_order_status'):
                    success = await adapter.update_order_status(order_id, new_status)
                    results[adapter.platform_name] = success
                else:
                    results[adapter.platform_name] = False
                    logger.warning(
                        "Адаптер не поддерживает обновление статуса заказов",
                        platform=adapter.platform_name
                    )

            except Exception as e:
                logger.error(
                    "Ошибка обновления статуса заказа",
                    error=str(e),
                    platform=adapter.platform_name,
                    order_id=order_id
                )
                results[adapter.platform_name] = False

        return results

    async def get_supported_platforms(self) -> list[str]:
        """Получить список поддерживаемых платформ."""
        return list(self.adapters.keys())

    def get_sync_statistics(self) -> dict[str, Any]:
        """Получить статистику синхронизации."""
        return self.sync_stats.copy()

    async def _sync_platform_safe(
        self,
        integration_key: str,
        adapter: PlatformAdapter,
        since: datetime | None
    ) -> SyncResult:
        """Безопасная синхронизация платформы с обработкой ошибок."""
        try:
            # Синхронизация всех типов данных
            orders_result = await adapter.sync_orders(since)
            products_result = await adapter.sync_products(since)
            customers_result = await adapter.sync_customers(since)

            total_synced = (
                orders_result.records_synced +
                products_result.records_synced +
                customers_result.records_synced
            )

            all_errors = orders_result.errors + products_result.errors + customers_result.errors
            all_success = orders_result.success and products_result.success and customers_result.success

            return SyncResult(
                success=all_success,
                records_synced=total_synced,
                sync_type="full",
                errors=all_errors
            )

        except Exception as e:
            logger.error("Ошибка синхронизации платформы", error=str(e), platform=adapter.platform_name)
            return SyncResult(
                success=False,
                sync_type="full",
                errors=[str(e)]
            )

    def _update_sync_stats(self, results: dict[str, SyncResult]):
        """Обновить статистику синхронизации."""
        self.sync_stats["total_syncs"] += len(results)
        self.sync_stats["last_sync"] = datetime.now()

        for result in results.values():
            if result.success:
                self.sync_stats["successful_syncs"] += 1
            else:
                self.sync_stats["failed_syncs"] += 1


# Глобальный экземпляр менеджера интеграций
integration_manager = IntegrationManager()