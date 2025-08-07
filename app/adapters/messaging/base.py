"""Base messaging adapter for all messaging platforms."""
import asyncio
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Any
from collections import defaultdict
import time

import structlog
from pydantic import BaseModel, Field

from app.adapters.base import PlatformAdapter, RateLimitConfig, APIResponse
from app.models.messaging import (
    UnifiedMessage,
    DeliveryResult,
    MessageType,
    MessageDirection,
    DeliveryStatus,
    WebhookEvent,
    ConversationContext,
    PlatformConfig,
    MessageQueue
)


logger = structlog.get_logger()


class MessagingRateLimitConfig(RateLimitConfig):
    """Enhanced rate limiting configuration for messaging platforms."""
    
    messages_per_second: int = Field(default=30, description="Max messages per second")
    burst_size: int = Field(default=10, description="Max burst messages")
    per_chat_limit: int = Field(default=1, description="Max messages per chat per second")


class MessageStats(BaseModel):
    """Statistics for message processing."""
    
    platform: str = Field(..., description="Platform name")
    total_sent: int = Field(0, description="Total messages sent")
    total_received: int = Field(0, description="Total messages received")
    total_failed: int = Field(0, description="Total failed messages")
    
    # Timing stats
    avg_delivery_time_ms: float = Field(0.0, description="Average delivery time in milliseconds")
    success_rate: float = Field(100.0, description="Success rate percentage")
    
    # Rate limiting stats
    rate_limit_hits: int = Field(0, description="Number of rate limit hits")
    
    timestamp: datetime = Field(default_factory=datetime.now, description="Stats timestamp")


class MessagingAdapter(PlatformAdapter):
    """Abstract base class for messaging platform adapters."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        platform_name: str,
        config: PlatformConfig,
        rate_limit_config: MessagingRateLimitConfig | None = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """Initialize the messaging adapter.

        Args:
        ----
            api_key: API key for authentication
            base_url: Base URL for the platform API
            platform_name: Name of the platform
            config: Platform-specific configuration
            rate_limit_config: Rate limiting configuration
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts

        """
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            platform_name=platform_name,
            rate_limit_config=rate_limit_config or MessagingRateLimitConfig(),
            timeout=timeout,
            max_retries=max_retries
        )
        
        self.config = config
        self.messaging_rate_config = rate_limit_config or MessagingRateLimitConfig()
        
        # Enhanced rate limiting for messaging
        self._per_chat_timers: dict[str, list[float]] = defaultdict(list)
        self._message_queue: list[MessageQueue] = []
        
        # Statistics
        self.stats = MessageStats(platform=platform_name)
        
        # Webhook processing
        self._webhook_handlers: dict[str, Any] = {}
        
        logger.info(
            "Messaging adapter initialized",
            platform=platform_name,
            rate_limit_per_second=self.messaging_rate_config.messages_per_second,
            webhook_verification=config.verify_webhooks
        )

    def _check_chat_rate_limit(self, chat_id: str) -> bool:
        """Check rate limit for specific chat."""
        current_time = time.time()
        
        # Clean old timestamps
        cutoff_time = current_time - 1.0  # 1 second window
        self._per_chat_timers[chat_id] = [
            t for t in self._per_chat_timers[chat_id] if t > cutoff_time
        ]
        
        # Check per-chat limit
        chat_messages = len(self._per_chat_timers[chat_id])
        if chat_messages >= self.messaging_rate_config.per_chat_limit:
            return False
            
        return True

    async def _wait_for_chat_rate_limit(self, chat_id: str):
        """Wait until we can send message to specific chat."""
        while not self._check_chat_rate_limit(chat_id):
            await asyncio.sleep(0.1)

    async def send_message(
        self,
        chat_id: str,
        message: UnifiedMessage,
        priority: int = 0
    ) -> DeliveryResult:
        """Send a message to the platform.
        
        Args:
        ----
            chat_id: Target chat/user ID
            message: Unified message to send
            priority: Message priority (higher = more urgent)
            
        Returns:
        -------
            DeliveryResult: Result of message delivery
        """
        start_time = time.time()
        
        try:
            logger.info(
                "Sending message",
                platform=self.platform_name,
                chat_id=chat_id,
                message_type=message.message_type,
                priority=priority
            )
            
            # Validate message
            self._validate_outgoing_message(message)
            
            # Check rate limits
            await self._wait_for_rate_limit()
            await self._wait_for_chat_rate_limit(chat_id)
            
            # Record request time for rate limiting
            current_time = time.time()
            self._request_times.append(current_time)
            self._per_chat_timers[chat_id].append(current_time)
            self._burst_count += 1
            
            # Send message via platform-specific implementation
            result = await self._send_platform_message(chat_id, message)
            
            # Update statistics
            delivery_time_ms = (time.time() - start_time) * 1000
            if result.success:
                self.stats.total_sent += 1
                # Update average delivery time
                self.stats.avg_delivery_time_ms = (
                    (self.stats.avg_delivery_time_ms * (self.stats.total_sent - 1) + delivery_time_ms) /
                    self.stats.total_sent
                )
            else:
                self.stats.total_failed += 1
                
            # Update success rate
            total_attempts = self.stats.total_sent + self.stats.total_failed
            self.stats.success_rate = (self.stats.total_sent / total_attempts) * 100 if total_attempts > 0 else 100.0
            
            logger.info(
                "Message sent successfully" if result.success else "Message send failed",
                platform=self.platform_name,
                chat_id=chat_id,
                message_id=result.message_id,
                platform_message_id=result.platform_message_id,
                delivery_time_ms=delivery_time_ms,
                success=result.success,
                error=result.error_message
            )
            
            return result
            
        except Exception as e:
            self.stats.total_failed += 1
            error_msg = f"Failed to send message: {str(e)}"
            
            logger.error(
                "Message send exception",
                platform=self.platform_name,
                chat_id=chat_id,
                error=error_msg,
                delivery_time_ms=(time.time() - start_time) * 1000
            )
            
            return DeliveryResult(
                message_id=message.message_id,
                platform=self.platform_name,
                status=DeliveryStatus.FAILED,
                success=False,
                error_message=error_msg,
                sent_at=None,
                timestamp=datetime.now()
            )

    async def receive_webhook(self, payload: dict[str, Any], signature: str | None = None) -> list[UnifiedMessage]:
        """Process incoming webhook from messaging platform.
        
        Args:
        ----
            payload: Webhook payload
            signature: Webhook signature for verification
            
        Returns:
        -------
            list[UnifiedMessage]: Extracted messages from webhook
        """
        try:
            logger.info(
                "Processing webhook",
                platform=self.platform_name,
                event_type=payload.get("type", "unknown"),
                has_signature=signature is not None
            )
            
            # Verify webhook signature if enabled
            if self.config.verify_webhooks and signature:
                if not self.verify_webhook_signature(
                    payload=str(payload).encode(),
                    signature=signature,
                    secret=self.config.webhook_secret or ""
                ):
                    raise ValueError("Invalid webhook signature")
            
            # Extract messages from webhook
            messages = await self._extract_webhook_messages(payload)
            
            # Update receive statistics
            self.stats.total_received += len(messages)
            
            logger.info(
                "Webhook processed",
                platform=self.platform_name,
                messages_extracted=len(messages)
            )
            
            return messages
            
        except Exception as e:
            logger.error(
                "Webhook processing failed",
                platform=self.platform_name,
                error=str(e)
            )
            raise

    def _validate_outgoing_message(self, message: UnifiedMessage) -> None:
        """Validate outgoing message against platform limits."""
        # Check text length
        if message.text and len(message.text) > self.config.max_text_length:
            raise ValueError(
                f"Message text too long: {len(message.text)} > {self.config.max_text_length}"
            )
        
        # Check file sizes
        for attachment in message.attachments:
            if attachment.file_size and attachment.file_size > self.config.max_file_size:
                raise ValueError(
                    f"Attachment too large: {attachment.file_size} > {self.config.max_file_size}"
                )
        
        # Check platform feature support
        if message.inline_keyboard and not self.config.supports_inline_keyboard:
            raise ValueError("Platform does not support inline keyboards")
            
        if message.reply_keyboard and not self.config.supports_reply_keyboard:
            raise ValueError("Platform does not support reply keyboards")
        
        # Check media support
        if message.attachments and not self.config.supports_media:
            raise ValueError("Platform does not support media attachments")

    async def get_conversation_context(self, chat_id: str, user_id: str) -> ConversationContext | None:
        """Get conversation context for chat.
        
        Args:
        ----
            chat_id: Chat/conversation ID
            user_id: User ID
            
        Returns:
        -------
            ConversationContext | None: Current conversation context
        """
        return await self._get_platform_conversation_context(chat_id, user_id)

    async def update_conversation_context(self, context: ConversationContext) -> bool:
        """Update conversation context.
        
        Args:
        ----
            context: Updated conversation context
            
        Returns:
        -------
            bool: Whether update was successful
        """
        return await self._update_platform_conversation_context(context)

    async def get_message_stats(self) -> MessageStats:
        """Get current message processing statistics."""
        self.stats.timestamp = datetime.now()
        return self.stats

    # Abstract methods that must be implemented by platform adapters

    @abstractmethod
    async def _send_platform_message(self, chat_id: str, message: UnifiedMessage) -> DeliveryResult:
        """Send message via platform-specific API."""

    @abstractmethod
    async def _extract_webhook_messages(self, payload: dict[str, Any]) -> list[UnifiedMessage]:
        """Extract unified messages from platform webhook payload."""

    @abstractmethod
    async def _get_platform_conversation_context(
        self, chat_id: str, user_id: str
    ) -> ConversationContext | None:
        """Get platform-specific conversation context."""

    @abstractmethod
    async def _update_platform_conversation_context(self, context: ConversationContext) -> bool:
        """Update platform-specific conversation context."""

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify webhook signature using platform-specific method."""

    # Implement base class abstract methods for messaging platforms
    
    async def test_connection(self) -> APIResponse:
        """Test connection to messaging platform."""
        try:
            # Default implementation - can be overridden by platform adapters
            result = await self._make_request("GET", "getMe")  # Common for many platforms
            return result
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0,
                platform=self.platform_name
            )

    async def sync_orders(self, limit: int = 100):
        """Not applicable for messaging platforms."""
        raise NotImplementedError("Order sync not applicable for messaging platforms")

    async def sync_products(self, limit: int = 100):
        """Not applicable for messaging platforms."""
        raise NotImplementedError("Product sync not applicable for messaging platforms")

    async def sync_customers(self, limit: int = 100):
        """Not applicable for messaging platforms."""
        raise NotImplementedError("Customer sync not applicable for messaging platforms")

    async def handle_webhook(self, payload: dict[str, Any], signature: str | None = None) -> bool:
        """Handle incoming webhook - delegates to receive_webhook."""
        try:
            messages = await self.receive_webhook(payload, signature)
            return len(messages) > 0
        except Exception:
            return False


# Re-export models for convenience
__all__ = [
    "MessagingAdapter",
    "MessagingRateLimitConfig", 
    "MessageStats",
    "UnifiedMessage",
    "DeliveryResult",
    "MessageType",
    "MessageDirection",
    "DeliveryStatus",
    "WebhookEvent",
    "ConversationContext",
    "PlatformConfig",
    "MessageQueue"
]