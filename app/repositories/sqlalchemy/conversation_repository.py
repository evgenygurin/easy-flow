"""SQLAlchemy implementation of conversation repository."""
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import ConversationStatus, Platform
from app.models.database import Conversation
from app.repositories.interfaces.conversation_repository import ConversationRepository


logger = structlog.get_logger()


class SQLAlchemyConversationRepository(ConversationRepository):
    """SQLAlchemy implementation of conversation repository."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def create(self, entity: Conversation) -> Conversation | None:
        """Create a new conversation entity."""
        try:
            async with self.session_factory() as session:
                session.add(entity)
                await session.commit()
                await session.refresh(entity)
                return entity
        except Exception as e:
            logger.error("Error creating conversation", error=str(e))
            return None

    async def get_by_id(self, conversation_id: str) -> Conversation | None:
        """Retrieve conversation by ID."""
        try:
            async with self.session_factory() as session:
                stmt = select(Conversation).where(Conversation.id == conversation_id)
                result = await session.execute(stmt)
                return result.scalars().first()
        except Exception as e:
            logger.error("Error retrieving conversation by ID", error=str(e), conversation_id=conversation_id)
            return None

    async def update(self, entity: Conversation) -> Conversation | None:
        """Update an existing conversation."""
        try:
            async with self.session_factory() as session:
                entity.updated_at = datetime.utcnow()
                await session.merge(entity)
                await session.commit()
                await session.refresh(entity)
                return entity
        except Exception as e:
            logger.error("Error updating conversation", error=str(e), conversation_id=entity.id)
            return None

    async def delete(self, conversation_id: str) -> bool:
        """Delete a conversation by ID."""
        try:
            async with self.session_factory() as session:
                stmt = select(Conversation).where(Conversation.id == conversation_id)
                result = await session.execute(stmt)
                conversation = result.scalars().first()
                if conversation:
                    await session.delete(conversation)
                    await session.commit()
                    return True
                return False
        except Exception as e:
            logger.error("Error deleting conversation", error=str(e), conversation_id=conversation_id)
            return False

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Conversation]:
        """List all conversations with pagination."""
        try:
            async with self.session_factory() as session:
                stmt = select(Conversation).limit(limit).offset(offset)
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error listing conversations", error=str(e))
            return []

    async def exists(self, conversation_id: str) -> bool:
        """Check if conversation exists."""
        try:
            async with self.session_factory() as session:
                stmt = select(Conversation.id).where(Conversation.id == conversation_id)
                result = await session.execute(stmt)
                return result.scalar() is not None
        except Exception as e:
            logger.error("Error checking conversation existence", error=str(e), conversation_id=conversation_id)
            return False

    async def count(self) -> int:
        """Count total number of conversations."""
        try:
            async with self.session_factory() as session:
                stmt = select(Conversation)
                result = await session.execute(stmt)
                return len(list(result.scalars().all()))
        except Exception as e:
            logger.error("Error counting conversations", error=str(e))
            return 0

    async def create_conversation(
        self,
        user_id: str,
        session_id: str,
        platform: Platform,
        initial_context: dict[str, Any] | None = None
    ) -> Conversation | None:
        """Create a new conversation."""
        try:
            async with self.session_factory() as session:
                conversation = Conversation(
                    user_id=user_id,
                    session_id=session_id,
                    platform=platform.value,
                    status=ConversationStatus.ACTIVE.value,
                    context=initial_context or {}
                )

                session.add(conversation)
                await session.commit()
                await session.refresh(conversation)

                logger.info("Created new conversation", conversation_id=conversation.id, user_id=user_id)
                return conversation

        except Exception as e:
            logger.error("Error creating conversation", error=str(e), user_id=user_id)
            return None

    async def get_by_session_id(self, session_id: str) -> Conversation | None:
        """Retrieve conversation by session ID."""
        try:
            async with self.session_factory() as session:
                stmt = select(Conversation).where(Conversation.session_id == session_id)
                result = await session.execute(stmt)
                return result.scalars().first()
        except Exception as e:
            logger.error("Error retrieving conversation by session ID", error=str(e), session_id=session_id)
            return None

    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 20,
        status: ConversationStatus | None = None
    ) -> list[Conversation]:
        """Get conversations for a specific user."""
        try:
            async with self.session_factory() as session:
                stmt = select(Conversation).where(Conversation.user_id == user_id)
                
                if status:
                    stmt = stmt.where(Conversation.status == status.value)
                
                stmt = stmt.order_by(Conversation.updated_at.desc()).limit(limit)
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error retrieving user conversations", error=str(e), user_id=user_id)
            return []

    async def update_status(
        self,
        conversation_id: str,
        status: ConversationStatus,
        ended_at: datetime | None = None
    ) -> Conversation | None:
        """Update conversation status."""
        try:
            async with self.session_factory() as session:
                stmt = select(Conversation).where(Conversation.id == conversation_id)
                result = await session.execute(stmt)
                conversation = result.scalars().first()

                if conversation:
                    conversation.status = status.value
                    conversation.updated_at = datetime.utcnow()
                    if ended_at:
                        conversation.ended_at = ended_at
                    
                    await session.commit()
                    await session.refresh(conversation)
                    return conversation

                return None
        except Exception as e:
            logger.error("Error updating conversation status", error=str(e), conversation_id=conversation_id)
            return None

    async def update_context(
        self,
        conversation_id: str,
        context: dict[str, Any]
    ) -> Conversation | None:
        """Update conversation context."""
        try:
            async with self.session_factory() as session:
                stmt = select(Conversation).where(Conversation.id == conversation_id)
                result = await session.execute(stmt)
                conversation = result.scalars().first()

                if conversation:
                    conversation.context = context
                    conversation.updated_at = datetime.utcnow()
                    
                    await session.commit()
                    await session.refresh(conversation)
                    return conversation

                return None
        except Exception as e:
            logger.error("Error updating conversation context", error=str(e), conversation_id=conversation_id)
            return None

    async def get_active_conversations(
        self,
        since: datetime | None = None,
        limit: int = 100
    ) -> list[Conversation]:
        """Get active conversations, optionally since a specific time."""
        try:
            async with self.session_factory() as session:
                stmt = select(Conversation).where(Conversation.status == ConversationStatus.ACTIVE.value)
                
                if since:
                    stmt = stmt.where(Conversation.updated_at >= since)
                
                stmt = stmt.order_by(Conversation.updated_at.desc()).limit(limit)
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error retrieving active conversations", error=str(e))
            return []

    async def end_conversation(self, conversation_id: str) -> bool:
        """End a conversation and set ended_at timestamp."""
        try:
            async with self.session_factory() as session:
                stmt = select(Conversation).where(Conversation.id == conversation_id)
                result = await session.execute(stmt)
                conversation = result.scalars().first()

                if conversation:
                    conversation.status = ConversationStatus.ENDED.value
                    conversation.ended_at = datetime.utcnow()
                    conversation.updated_at = datetime.utcnow()
                    
                    await session.commit()
                    return True

                return False
        except Exception as e:
            logger.error("Error ending conversation", error=str(e), conversation_id=conversation_id)
            return False