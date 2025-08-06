"""Base repository interface with common CRUD operations."""
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar


EntityType = TypeVar("EntityType")
IDType = TypeVar("IDType")


class BaseRepository(ABC, Generic[EntityType, IDType]):
    """Abstract base repository interface."""

    @abstractmethod
    async def create(self, entity: EntityType) -> EntityType | None:
        """Create a new entity."""
        pass

    @abstractmethod
    async def get_by_id(self, entity_id: IDType) -> EntityType | None:
        """Retrieve an entity by its ID."""
        pass

    @abstractmethod
    async def update(self, entity: EntityType) -> EntityType | None:
        """Update an existing entity."""
        pass

    @abstractmethod
    async def delete(self, entity_id: IDType) -> bool:
        """Delete an entity by its ID."""
        pass

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[EntityType]:
        """List all entities with pagination."""
        pass

    @abstractmethod
    async def exists(self, entity_id: IDType) -> bool:
        """Check if an entity exists."""
        pass

    @abstractmethod
    async def count(self) -> int:
        """Count total number of entities."""
        pass