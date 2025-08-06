"""SQLAlchemy implementation of integration repository.

Note: This is a bridge implementation since PlatformInfo is not a SQLAlchemy model.
We'll need to create a proper Integration model or use existing IntegrationLog table.
For now, this provides the structure and we'll use in-memory storage as fallback.
"""
import uuid
from datetime import datetime
from typing import Any

import structlog

from app.models.integration import PlatformInfo
from app.repositories.interfaces.integration_repository import IntegrationRepository


logger = structlog.get_logger()


class SQLAlchemyIntegrationRepository(IntegrationRepository):
    """SQLAlchemy implementation of integration repository.
    
    Note: Currently uses in-memory storage as PlatformInfo is not a SQLAlchemy model.
    This should be refactored to use a proper Integration table in the future.
    """

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        # Temporary in-memory storage until proper Integration table is created
        self._integrations: dict[str, dict[str, list[PlatformInfo]]] = {}

    async def create(self, entity: PlatformInfo) -> PlatformInfo | None:
        """Create a new integration entity."""
        # Since PlatformInfo doesn't have a user_id field, we can't properly implement this
        # This would need a proper Integration SQLAlchemy model
        logger.warning("create() not fully implemented - needs proper Integration model")
        return entity

    async def get_by_id(self, integration_id: str) -> PlatformInfo | None:
        """Retrieve integration by ID."""
        try:
            for user_integrations in self._integrations.values():
                for integrations in user_integrations.values():
                    for integration in integrations:
                        if integration.platform_id == integration_id:
                            return integration
            return None
        except Exception as e:
            logger.error("Error retrieving integration by ID", error=str(e), integration_id=integration_id)
            return None

    async def update(self, entity: PlatformInfo) -> PlatformInfo | None:
        """Update an existing integration."""
        # Would need proper SQLAlchemy implementation with Integration table
        logger.warning("update() not fully implemented - needs proper Integration model")
        return entity

    async def delete(self, integration_id: str) -> bool:
        """Delete an integration by ID."""
        try:
            for user_id in self._integrations:
                for platform_name in list(self._integrations[user_id].keys()):
                    self._integrations[user_id][platform_name] = [
                        integration for integration in self._integrations[user_id][platform_name]
                        if integration.platform_id != integration_id
                    ]
                    if not self._integrations[user_id][platform_name]:
                        del self._integrations[user_id][platform_name]
            return True
        except Exception as e:
            logger.error("Error deleting integration", error=str(e), integration_id=integration_id)
            return False

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[PlatformInfo]:
        """List all integrations with pagination."""
        try:
            all_integrations = []
            for user_integrations in self._integrations.values():
                for integrations in user_integrations.values():
                    all_integrations.extend(integrations)
            
            return all_integrations[offset:offset + limit]
        except Exception as e:
            logger.error("Error listing integrations", error=str(e))
            return []

    async def exists(self, integration_id: str) -> bool:
        """Check if integration exists."""
        integration = await self.get_by_id(integration_id)
        return integration is not None

    async def count(self) -> int:
        """Count total number of integrations."""
        try:
            total = 0
            for user_integrations in self._integrations.values():
                for integrations in user_integrations.values():
                    total += len(integrations)
            return total
        except Exception as e:
            logger.error("Error counting integrations", error=str(e))
            return 0

    async def get_user_integrations(self, user_id: str) -> list[PlatformInfo]:
        """Get all integrations for a user."""
        try:
            logger.info("Retrieving integrations for user", user_id=user_id)
            user_integrations = []
            if user_id in self._integrations:
                for integrations in self._integrations[user_id].values():
                    user_integrations.extend(integrations)
            return user_integrations
        except Exception as e:
            logger.error("Error retrieving user integrations", error=str(e), user_id=user_id)
            return []

    async def get_by_platform_name(
        self,
        user_id: str,
        platform_name: str
    ) -> list[PlatformInfo]:
        """Get integrations by platform name for a user."""
        try:
            if user_id in self._integrations and platform_name in self._integrations[user_id]:
                return self._integrations[user_id][platform_name]
            return []
        except Exception as e:
            logger.error("Error retrieving integrations by platform", error=str(e), user_id=user_id, platform_name=platform_name)
            return []

    async def create_integration(
        self,
        user_id: str,
        platform_name: str,
        credentials: dict[str, str],
        configuration: dict[str, Any] | None = None
    ) -> PlatformInfo | None:
        """Create a new integration for a user."""
        try:
            logger.info("Creating integration", user_id=user_id, platform_name=platform_name)

            platform_id = str(uuid.uuid4())
            platform_info = PlatformInfo(
                platform_id=platform_id,
                platform_name=platform_name,
                status="connected",
                connected_at=datetime.now(),
                configuration=configuration or {}
            )

            # Initialize user integrations if needed
            if user_id not in self._integrations:
                self._integrations[user_id] = {}
            if platform_name not in self._integrations[user_id]:
                self._integrations[user_id][platform_name] = []

            self._integrations[user_id][platform_name].append(platform_info)

            logger.info(
                "Integration created successfully",
                user_id=user_id,
                platform_name=platform_name,
                platform_id=platform_id
            )

            return platform_info

        except Exception as e:
            logger.error("Error creating integration", error=str(e), user_id=user_id, platform_name=platform_name)
            return None

    async def update_configuration(
        self,
        integration_id: str,
        configuration: dict[str, Any]
    ) -> PlatformInfo | None:
        """Update integration configuration."""
        try:
            integration = await self.get_by_id(integration_id)
            if integration:
                integration.configuration = configuration
                # In a real implementation, this would update the database
                return integration
            return None
        except Exception as e:
            logger.error("Error updating integration configuration", error=str(e), integration_id=integration_id)
            return None

    async def update_last_sync(
        self,
        integration_id: str,
        sync_time: datetime
    ) -> PlatformInfo | None:
        """Update last sync time for an integration."""
        try:
            integration = await self.get_by_id(integration_id)
            if integration:
                integration.last_sync = sync_time
                # In a real implementation, this would update the database
                return integration
            return None
        except Exception as e:
            logger.error("Error updating last sync time", error=str(e), integration_id=integration_id)
            return None

    async def get_integrations_by_status(
        self,
        status: str,
        limit: int = 100
    ) -> list[PlatformInfo]:
        """Get integrations by status."""
        try:
            matching_integrations = []
            for user_integrations in self._integrations.values():
                for integrations in user_integrations.values():
                    for integration in integrations:
                        if integration.status == status:
                            matching_integrations.append(integration)
                            if len(matching_integrations) >= limit:
                                return matching_integrations
            
            return matching_integrations
        except Exception as e:
            logger.error("Error retrieving integrations by status", error=str(e), status=status)
            return []

    async def disconnect_integration(self, integration_id: str) -> bool:
        """Disconnect/delete an integration."""
        return await self.delete(integration_id)