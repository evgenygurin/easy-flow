"""User repository interface."""
from abc import abstractmethod
from typing import Any

from app.models.conversation import Platform
from app.models.database import User
from app.repositories.interfaces.base_repository import BaseRepository


class UserRepository(BaseRepository[User, str]):
    """Interface for user data access operations."""

    @abstractmethod
    async def get_by_external_id(self, external_id: str, platform: Platform) -> User | None:
        """Retrieve user by external ID and platform."""
        pass

    @abstractmethod
    async def get_or_create_user(
        self,
        external_id: str,
        platform: Platform,
        metadata: dict[str, Any] | None = None
    ) -> User | None:
        """Get existing user or create new one."""
        pass

    @abstractmethod
    async def update_metadata(self, user_id: str, metadata: dict[str, Any]) -> User | None:
        """Update user metadata."""
        pass

    @abstractmethod
    async def update_preferences(self, user_id: str, preferences: dict[str, Any]) -> User | None:
        """Update user preferences."""
        pass

    @abstractmethod
    async def get_active_users(self, limit: int = 100) -> list[User]:
        """Get list of active users."""
        pass

    @abstractmethod
    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account."""
        pass