"""SQLAlchemy implementation of message repository."""
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import MessageType
from app.models.database import Conversation, Message
from app.repositories.interfaces.message_repository import MessageRepository


logger = structlog.get_logger()


class SQLAlchemyMessageRepository(MessageRepository):
    """SQLAlchemy implementation of message repository."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def create(self, entity: Message) -> Message | None:
        """Create a new message entity."""
        try:
            async with self.session_factory() as session:
                session.add(entity)
                await session.commit()
                await session.refresh(entity)
                return entity
        except Exception as e:
            logger.error("Error creating message", error=str(e))
            return None

    async def get_by_id(self, message_id: str) -> Message | None:
        """Retrieve message by ID."""
        try:
            async with self.session_factory() as session:
                stmt = select(Message).where(Message.id == message_id)
                result = await session.execute(stmt)
                return result.scalars().first()
        except Exception as e:
            logger.error("Error retrieving message by ID", error=str(e), message_id=message_id)
            return None

    async def update(self, entity: Message) -> Message | None:
        """Update an existing message."""
        try:
            async with self.session_factory() as session:
                await session.merge(entity)
                await session.commit()
                await session.refresh(entity)
                return entity
        except Exception as e:
            logger.error("Error updating message", error=str(e), message_id=entity.id)
            return None

    async def delete(self, message_id: str) -> bool:
        """Delete a message by ID."""
        try:
            async with self.session_factory() as session:
                stmt = select(Message).where(Message.id == message_id)
                result = await session.execute(stmt)
                message = result.scalars().first()
                if message:
                    await session.delete(message)
                    await session.commit()
                    return True
                return False
        except Exception as e:
            logger.error("Error deleting message", error=str(e), message_id=message_id)
            return False

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Message]:
        """List all messages with pagination."""
        try:
            async with self.session_factory() as session:
                stmt = select(Message).limit(limit).offset(offset)
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error listing messages", error=str(e))
            return []

    async def exists(self, message_id: str) -> bool:
        """Check if message exists."""
        try:
            async with self.session_factory() as session:
                stmt = select(Message.id).where(Message.id == message_id)
                result = await session.execute(stmt)
                return result.scalar() is not None
        except Exception as e:
            logger.error("Error checking message existence", error=str(e), message_id=message_id)
            return False

    async def count(self) -> int:
        """Count total number of messages."""
        try:
            async with self.session_factory() as session:
                stmt = select(Message)
                result = await session.execute(stmt)
                return len(list(result.scalars().all()))
        except Exception as e:
            logger.error("Error counting messages", error=str(e))
            return 0

    async def add_message(
        self,
        conversation_id: str,
        content: str,
        message_type: MessageType,
        metadata: dict[str, Any] | None = None,
        intent: str | None = None,
        entities: dict[str, Any] | None = None,
        confidence: float | None = None,
        sentiment: str | None = None,
        language: str = "ru",
        ai_model_used: str | None = None,
        response_time_ms: int | None = None
    ) -> Message | None:
        """Add a new message to a conversation."""
        try:
            async with self.session_factory() as session:
                message = Message(
                    conversation_id=conversation_id,
                    content=content,
                    message_type=message_type.value,
                    metadata=metadata or {},
                    intent=intent,
                    entities=entities,
                    confidence=confidence,
                    sentiment=sentiment,
                    language=language,
                    ai_model_used=ai_model_used,
                    response_time_ms=response_time_ms
                )

                session.add(message)

                # Update conversation last activity
                stmt = select(Conversation).where(Conversation.id == conversation_id)
                result = await session.execute(stmt)
                conversation = result.scalars().first()

                if conversation:
                    conversation.updated_at = datetime.utcnow()

                await session.commit()
                await session.refresh(message)

                return message

        except Exception as e:
            logger.error("Error adding message", error=str(e), conversation_id=conversation_id)
            return None

    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50,
        message_type: MessageType | None = None
    ) -> list[Message]:
        """Get message history for a conversation."""
        try:
            async with self.session_factory() as session:
                stmt = select(Message).where(Message.conversation_id == conversation_id)
                
                if message_type:
                    stmt = stmt.where(Message.message_type == message_type.value)
                
                stmt = stmt.order_by(Message.created_at.desc()).limit(limit)
                result = await session.execute(stmt)
                messages = result.scalars().all()

                return list(reversed(messages))  # Return in chronological order

        except Exception as e:
            logger.error("Error retrieving conversation history", error=str(e), conversation_id=conversation_id)
            return []

    async def get_user_messages(
        self,
        user_id: str,
        limit: int = 100,
        message_type: MessageType | None = None
    ) -> list[Message]:
        """Get messages for a specific user across all conversations."""
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(Message)
                    .join(Conversation)
                    .where(Conversation.user_id == user_id)
                )
                
                if message_type:
                    stmt = stmt.where(Message.message_type == message_type.value)
                
                stmt = stmt.order_by(Message.created_at.desc()).limit(limit)
                result = await session.execute(stmt)
                return list(result.scalars().all())

        except Exception as e:
            logger.error("Error retrieving user messages", error=str(e), user_id=user_id)
            return []

    async def update_message_metadata(
        self,
        message_id: str,
        metadata: dict[str, Any]
    ) -> Message | None:
        """Update message metadata."""
        try:
            async with self.session_factory() as session:
                stmt = select(Message).where(Message.id == message_id)
                result = await session.execute(stmt)
                message = result.scalars().first()

                if message:
                    message.metadata = metadata
                    await session.commit()
                    await session.refresh(message)
                    return message

                return None
        except Exception as e:
            logger.error("Error updating message metadata", error=str(e), message_id=message_id)
            return None

    async def get_messages_by_intent(
        self,
        intent: str,
        limit: int = 100
    ) -> list[Message]:
        """Get messages by detected intent."""
        try:
            async with self.session_factory() as session:
                stmt = select(Message).where(Message.intent == intent).limit(limit)
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error retrieving messages by intent", error=str(e), intent=intent)
            return []

    async def get_messages_by_confidence_range(
        self,
        min_confidence: float,
        max_confidence: float,
        limit: int = 100
    ) -> list[Message]:
        """Get messages within confidence range."""
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(Message)
                    .where(Message.confidence.between(min_confidence, max_confidence))
                    .limit(limit)
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error retrieving messages by confidence range", error=str(e))
            return []