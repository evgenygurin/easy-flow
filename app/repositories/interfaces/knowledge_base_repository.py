"""Knowledge base repository interface."""
from abc import abstractmethod
from datetime import datetime

from app.models.database import KnowledgeBaseItem
from app.repositories.interfaces.base_repository import BaseRepository


class KnowledgeBaseRepository(BaseRepository[KnowledgeBaseItem, str]):
    """Interface for knowledge base data access operations."""

    @abstractmethod
    async def search_by_keywords(
        self,
        keywords: list[str],
        category: str | None = None,
        limit: int = 5
    ) -> list[KnowledgeBaseItem]:
        """Search knowledge base by keywords."""
        pass

    @abstractmethod
    async def get_by_category(
        self,
        category: str,
        limit: int = 100
    ) -> list[KnowledgeBaseItem]:
        """Get knowledge base items by category."""
        pass

    @abstractmethod
    async def get_most_used(self, limit: int = 10) -> list[KnowledgeBaseItem]:
        """Get most frequently used knowledge base items."""
        pass

    @abstractmethod
    async def increment_usage(self, item_id: str) -> KnowledgeBaseItem | None:
        """Increment usage count for a knowledge base item."""
        pass

    @abstractmethod
    async def update_last_used(
        self,
        item_id: str,
        used_at: datetime
    ) -> KnowledgeBaseItem | None:
        """Update last used timestamp."""
        pass

    @abstractmethod
    async def get_active_items(self, limit: int = 100) -> list[KnowledgeBaseItem]:
        """Get active knowledge base items."""
        pass

    @abstractmethod
    async def deactivate_item(self, item_id: str) -> bool:
        """Deactivate a knowledge base item."""
        pass

    @abstractmethod
    async def search_by_content(
        self,
        search_term: str,
        limit: int = 10
    ) -> list[KnowledgeBaseItem]:
        """Search knowledge base by content."""
        pass