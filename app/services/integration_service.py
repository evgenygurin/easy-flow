"""Сервис для интеграций с внешними платформами e-commerce."""
from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.integrations.manager import integration_manager
from app.models.integration import IntegrationResult, PlatformInfo


logger = structlog.get_logger()


class WebhookResult(BaseModel):
    """Результат обработки webhook."""

    message_id: str = Field(..., description="ID сообщения")
    status: str = Field(default="processed", description="Статус обработки")


class SyncResult(BaseModel):
    """Результат синхронизации."""

    records_updated: int = Field(..., description="Количество обновленных записей")
    sync_time: datetime = Field(..., description="Время синхронизации")


class IntegrationService:
    """Модернизированный сервис для управления e-commerce интеграциями."""

    def __init__(self) -> None:
        # Используем новый unified integration manager
        self.manager = integration_manager

    async def get_user_integrations(self, user_id: str) -> list[PlatformInfo]:
        """Получить список подключенных интеграций для пользователя."""
        try:
            logger.info("Получение интеграций пользователя", user_id=user_id)
            # Получаем статусы всех платформ пользователя
            statuses = await self.manager.get_all_platform_statuses(user_id)
            
            # Преобразуем в список PlatformInfo
            platform_infos = []
            for platform_name, status_info in statuses.items():
                if status_info.get("status") == "active":
                    platform_info = PlatformInfo(
                        platform_id=f"{platform_name}_{user_id}",
                        platform_name=platform_name,
                        status="connected",
                        connected_at=datetime.now(),
                        configuration={}
                    )
                    platform_infos.append(platform_info)
            
            return platform_infos
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
        """Подключить новую платформу через unified integration manager.

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
            
            # Используем новый integration manager
            return await self.manager.connect_platform(user_id, platform, credentials, configuration)

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
            
            # Используем новый integration manager
            success = await self.manager.disconnect_platform(user_id, platform_id)
            
            if not success:
                raise ValueError(f"Не удалось отключить платформу {platform_id}")
            
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
        """Обработка входящего webhook через unified integration manager.

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

            # Используем новый integration manager
            event_type = payload.get("event_type", "unknown")
            signature = payload.get("signature")
            
            message_id = await self.manager.process_webhook(platform, event_type, payload, signature)

            logger.info("Webhook успешно обработан", platform=platform, message_id=message_id)

            return WebhookResult(message_id=message_id)

        except Exception as e:
            logger.error("Ошибка обработки webhook", error=str(e), platform=platform)
            raise

    async def sync_platform_data(self, user_id: str, platform_id: str) -> SyncResult:
        """Синхронизация данных с платформой через unified integration manager."""
        try:
            logger.info("Синхронизация данных", user_id=user_id, platform_id=platform_id)

            # Используем новый integration manager для синхронизации всех платформ
            sync_results = await self.manager.sync_all_platforms(user_id)
            
            # Подсчитываем общее количество обновленных записей
            total_records = sum(result.records_synced for result in sync_results.values())
            
            sync_time = datetime.now()

            logger.info(
                "Синхронизация завершена",
                user_id=user_id,
                platform_id=platform_id,
                records_updated=total_records
            )

            return SyncResult(records_updated=total_records, sync_time=sync_time)

        except Exception as e:
            logger.error(
                "Ошибка синхронизации",
                error=str(e),
                user_id=user_id,
                platform_id=platform_id
            )
            raise

    async def get_supported_platforms(self) -> list[str]:
        """Получить список поддерживаемых платформ."""
        return await self.manager.get_supported_platforms()

    async def get_platform_status(self, user_id: str, platform_id: str) -> dict[str, Any]:
        """Получить статус конкретной платформы."""
        return await self.manager.get_platform_status(user_id, platform_id)

    async def get_sync_statistics(self) -> dict[str, Any]:
        """Получить статистику синхронизации."""
        return self.manager.get_sync_statistics()

# Старые методы удалены - теперь используется unified integration manager
