"""Integration repository interface."""
from abc import abstractmethod
from datetime import datetime
from typing import Any

from app.models.integration import PlatformInfo
from app.repositories.interfaces.base_repository import BaseRepository


class IntegrationRepository(BaseRepository[PlatformInfo, str]):
    """Interface for integration data access operations."""

    @abstractmethod
    async def get_user_integrations(self, user_id: str) -> list[PlatformInfo]:
        """Get all integrations for a user."""
        pass

    @abstractmethod
    async def get_by_platform_name(
        self,
        user_id: str,
        platform_name: str
    ) -> list[PlatformInfo]:
        """Get integrations by platform name for a user."""
        pass

    @abstractmethod
    async def create_integration(
        self,
        user_id: str,
        platform_name: str,
        credentials: dict[str, str],
        configuration: dict[str, Any] | None = None
    ) -> PlatformInfo | None:
        """Create a new integration for a user."""
        pass

    @abstractmethod
    async def update_configuration(
        self,
        integration_id: str,
        configuration: dict[str, Any]
    ) -> PlatformInfo | None:
        """Update integration configuration."""
        pass

    @abstractmethod
    async def update_last_sync(
        self,
        integration_id: str,
        sync_time: datetime
    ) -> PlatformInfo | None:
        """Update last sync time for an integration."""
        pass

    @abstractmethod
    async def get_integrations_by_status(
        self,
        status: str,
        limit: int = 100
    ) -> list[PlatformInfo]:
        """Get integrations by status."""
        pass

    @abstractmethod
    async def disconnect_integration(self, integration_id: str) -> bool:
        """Disconnect/delete an integration."""
        pass