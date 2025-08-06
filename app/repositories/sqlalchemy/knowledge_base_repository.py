"""SQLAlchemy implementation of knowledge base repository."""
from datetime import datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import KnowledgeBaseItem
from app.repositories.interfaces.knowledge_base_repository import KnowledgeBaseRepository


logger = structlog.get_logger()


class SQLAlchemyKnowledgeBaseRepository(KnowledgeBaseRepository):
    """SQLAlchemy implementation of knowledge base repository."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def create(self, entity: KnowledgeBaseItem) -> KnowledgeBaseItem | None:
        """Create a new knowledge base item entity."""
        try:
            async with self.session_factory() as session:
                session.add(entity)
                await session.commit()
                await session.refresh(entity)
                return entity
        except Exception as e:
            logger.error("Error creating knowledge base item", error=str(e))
            return None

    async def get_by_id(self, item_id: str) -> KnowledgeBaseItem | None:
        """Retrieve knowledge base item by ID."""
        try:
            async with self.session_factory() as session:
                stmt = select(KnowledgeBaseItem).where(KnowledgeBaseItem.id == item_id)
                result = await session.execute(stmt)
                return result.scalars().first()
        except Exception as e:
            logger.error("Error retrieving knowledge base item by ID", error=str(e), item_id=item_id)
            return None

    async def update(self, entity: KnowledgeBaseItem) -> KnowledgeBaseItem | None:
        """Update an existing knowledge base item."""
        try:
            async with self.session_factory() as session:
                entity.updated_at = datetime.utcnow()
                await session.merge(entity)
                await session.commit()
                await session.refresh(entity)
                return entity
        except Exception as e:
            logger.error("Error updating knowledge base item", error=str(e), item_id=entity.id)
            return None

    async def delete(self, item_id: str) -> bool:
        """Delete a knowledge base item by ID."""
        try:
            async with self.session_factory() as session:
                stmt = select(KnowledgeBaseItem).where(KnowledgeBaseItem.id == item_id)
                result = await session.execute(stmt)
                item = result.scalars().first()
                if item:
                    await session.delete(item)
                    await session.commit()
                    return True
                return False
        except Exception as e:
            logger.error("Error deleting knowledge base item", error=str(e), item_id=item_id)
            return False

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[KnowledgeBaseItem]:
        """List all knowledge base items with pagination."""
        try:
            async with self.session_factory() as session:
                stmt = select(KnowledgeBaseItem).limit(limit).offset(offset)
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error listing knowledge base items", error=str(e))
            return []

    async def exists(self, item_id: str) -> bool:
        """Check if knowledge base item exists."""
        try:
            async with self.session_factory() as session:
                stmt = select(KnowledgeBaseItem.id).where(KnowledgeBaseItem.id == item_id)
                result = await session.execute(stmt)
                return result.scalar() is not None
        except Exception as e:
            logger.error("Error checking knowledge base item existence", error=str(e), item_id=item_id)
            return False

    async def count(self) -> int:
        """Count total number of knowledge base items."""
        try:
            async with self.session_factory() as session:
                stmt = select(func.count(KnowledgeBaseItem.id))
                result = await session.execute(stmt)
                return result.scalar() or 0
        except Exception as e:
            logger.error("Error counting knowledge base items", error=str(e))
            return 0

    async def search_by_keywords(
        self,
        keywords: list[str],
        category: str | None = None,
        limit: int = 5
    ) -> list[KnowledgeBaseItem]:
        """Search knowledge base by keywords."""
        try:
            async with self.session_factory() as session:
                # Simple keyword search using array_to_string
                conditions = []
                for keyword in keywords:
                    conditions.append(
                        func.array_to_string(KnowledgeBaseItem.keywords, ' ').ilike(f'%{keyword}%')
                    )

                stmt = select(KnowledgeBaseItem).where(
                    KnowledgeBaseItem.is_active,
                    *conditions
                )

                if category:
                    stmt = stmt.where(KnowledgeBaseItem.category == category)

                stmt = stmt.order_by(
                    KnowledgeBaseItem.priority.desc(),
                    KnowledgeBaseItem.usage_count.desc()
                ).limit(limit)

                result = await session.execute(stmt)
                items = result.scalars().all()

                # Update usage counts
                for item in items:
                    item.usage_count += 1
                    item.last_used_at = datetime.utcnow()

                if items:
                    await session.commit()

                return list(items)

        except Exception as e:
            logger.error("Error searching knowledge base by keywords", error=str(e))
            return []

    async def get_by_category(
        self,
        category: str,
        limit: int = 100
    ) -> list[KnowledgeBaseItem]:
        """Get knowledge base items by category."""
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(KnowledgeBaseItem)
                    .where(
                        KnowledgeBaseItem.category == category,
                        KnowledgeBaseItem.is_active
                    )
                    .order_by(KnowledgeBaseItem.priority.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error retrieving knowledge base items by category", error=str(e), category=category)
            return []

    async def get_most_used(self, limit: int = 10) -> list[KnowledgeBaseItem]:
        """Get most frequently used knowledge base items."""
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(KnowledgeBaseItem)
                    .where(KnowledgeBaseItem.is_active)
                    .order_by(KnowledgeBaseItem.usage_count.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error retrieving most used knowledge base items", error=str(e))
            return []

    async def increment_usage(self, item_id: str) -> KnowledgeBaseItem | None:
        """Increment usage count for a knowledge base item."""
        try:
            async with self.session_factory() as session:
                stmt = select(KnowledgeBaseItem).where(KnowledgeBaseItem.id == item_id)
                result = await session.execute(stmt)
                item = result.scalars().first()

                if item:
                    item.usage_count += 1
                    item.last_used_at = datetime.utcnow()
                    await session.commit()
                    await session.refresh(item)
                    return item

                return None
        except Exception as e:
            logger.error("Error incrementing knowledge base item usage", error=str(e), item_id=item_id)
            return None

    async def update_last_used(
        self,
        item_id: str,
        used_at: datetime
    ) -> KnowledgeBaseItem | None:
        """Update last used timestamp."""
        try:
            async with self.session_factory() as session:
                stmt = select(KnowledgeBaseItem).where(KnowledgeBaseItem.id == item_id)
                result = await session.execute(stmt)
                item = result.scalars().first()

                if item:
                    item.last_used_at = used_at
                    await session.commit()
                    await session.refresh(item)
                    return item

                return None
        except Exception as e:
            logger.error("Error updating last used timestamp", error=str(e), item_id=item_id)
            return None

    async def get_active_items(self, limit: int = 100) -> list[KnowledgeBaseItem]:
        """Get active knowledge base items."""
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(KnowledgeBaseItem)
                    .where(KnowledgeBaseItem.is_active == True)
                    .order_by(KnowledgeBaseItem.priority.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error retrieving active knowledge base items", error=str(e))
            return []

    async def deactivate_item(self, item_id: str) -> bool:
        """Deactivate a knowledge base item."""
        try:
            async with self.session_factory() as session:
                stmt = select(KnowledgeBaseItem).where(KnowledgeBaseItem.id == item_id)
                result = await session.execute(stmt)
                item = result.scalars().first()

                if item:
                    item.is_active = False
                    item.updated_at = datetime.utcnow()
                    await session.commit()
                    return True

                return False
        except Exception as e:
            logger.error("Error deactivating knowledge base item", error=str(e), item_id=item_id)
            return False

    async def search_by_content(
        self,
        search_term: str,
        limit: int = 10
    ) -> list[KnowledgeBaseItem]:
        """Search knowledge base by content."""
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(KnowledgeBaseItem)
                    .where(
                        KnowledgeBaseItem.is_active,
                        KnowledgeBaseItem.content.ilike(f'%{search_term}%')
                    )
                    .order_by(KnowledgeBaseItem.priority.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error searching knowledge base by content", error=str(e), search_term=search_term)
            return []