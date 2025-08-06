"""Conversation repository interface."""
from abc import abstractmethod
from datetime import datetime
from typing import Any

from app.models.conversation import ConversationStatus, Platform
from app.models.database import Conversation
from app.repositories.interfaces.base_repository import BaseRepository


class ConversationRepository(BaseRepository[Conversation, str]):
    """Interface for conversation data access operations."""

    @abstractmethod
    async def create_conversation(
        self,
        user_id: str,
        session_id: str,
        platform: Platform,
        initial_context: dict[str, Any] | None = None
    ) -> Conversation | None:
        """Create a new conversation."""
        pass

    @abstractmethod
    async def get_by_session_id(self, session_id: str) -> Conversation | None:
        """Retrieve conversation by session ID."""
        pass

    @abstractmethod
    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 20,
        status: ConversationStatus | None = None
    ) -> list[Conversation]:
        """Get conversations for a specific user."""
        pass

    @abstractmethod
    async def update_status(
        self,
        conversation_id: str,
        status: ConversationStatus,
        ended_at: datetime | None = None
    ) -> Conversation | None:
        """Update conversation status."""
        pass

    @abstractmethod
    async def update_context(
        self,
        conversation_id: str,
        context: dict[str, Any]
    ) -> Conversation | None:
        """Update conversation context."""
        pass

    @abstractmethod
    async def get_active_conversations(
        self,
        since: datetime | None = None,
        limit: int = 100
    ) -> list[Conversation]:
        """Get active conversations, optionally since a specific time."""
        pass

    @abstractmethod
    async def end_conversation(self, conversation_id: str) -> bool:
        """End a conversation and set ended_at timestamp."""
        pass