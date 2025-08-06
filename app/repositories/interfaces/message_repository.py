"""Message repository interface."""
from abc import abstractmethod
from typing import Any

from app.models.conversation import MessageType
from app.models.database import Message
from app.repositories.interfaces.base_repository import BaseRepository


class MessageRepository(BaseRepository[Message, str]):
    """Interface for message data access operations."""

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50,
        message_type: MessageType | None = None
    ) -> list[Message]:
        """Get message history for a conversation."""
        pass

    @abstractmethod
    async def get_user_messages(
        self,
        user_id: str,
        limit: int = 100,
        message_type: MessageType | None = None
    ) -> list[Message]:
        """Get messages for a specific user across all conversations."""
        pass

    @abstractmethod
    async def update_message_metadata(
        self,
        message_id: str,
        metadata: dict[str, Any]
    ) -> Message | None:
        """Update message metadata."""
        pass

    @abstractmethod
    async def get_messages_by_intent(
        self,
        intent: str,
        limit: int = 100
    ) -> list[Message]:
        """Get messages by detected intent."""
        pass

    @abstractmethod
    async def get_messages_by_confidence_range(
        self,
        min_confidence: float,
        max_confidence: float,
        limit: int = 100
    ) -> list[Message]:
        """Get messages within confidence range."""
        pass