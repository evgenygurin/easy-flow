"""Messaging service for handling messaging platform business logic."""
import uuid
from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.adapters.messaging.base import MessagingAdapter
from app.adapters.messaging.telegram import TelegramAdapter
from app.adapters.messaging.whatsapp import WhatsAppAdapter
from app.adapters.messaging.vk import VKAdapter
from app.adapters.messaging.viber import ViberAdapter
from app.models.messaging import (
    UnifiedMessage,
    DeliveryResult,
    WebhookEvent,
    ConversationContext,
    PlatformConfig
)
from app.adapters.messaging.base import MessageStats
from app.repositories.interfaces.integration_repository import IntegrationRepository


logger = structlog.get_logger()


class WebhookProcessingResult(BaseModel):
    """Result of webhook processing."""
    
    event_id: str = Field(..., description="Webhook event ID")
    platform: str = Field(..., description="Platform name")
    success: bool = Field(..., description="Processing success")
    messages: list[UnifiedMessage] = Field(..., description="Extracted messages")
    error: str | None = Field(None, description="Error message if failed")


class MessagingService:
    """Service for messaging platform business logic."""

    def __init__(self, integration_repository: IntegrationRepository):
        """Initialize messaging service.
        
        Args:
        ----
            integration_repository: Repository for integration data
        """
        self.integration_repository = integration_repository
        self._adapters: dict[str, MessagingAdapter] = {}
        self._platform_configs: dict[str, PlatformConfig] = {}
        
        logger.info("Messaging service initialized")

    async def register_platform(self, platform: str, config: PlatformConfig) -> bool:
        """Register a messaging platform.
        
        Args:
        ----
            platform: Platform name
            config: Platform configuration
            
        Returns:
        -------
            bool: Whether registration was successful
        """
        try:
            # Store platform configuration
            self._platform_configs[platform] = config
            
            # Create and register adapter
            adapter = await self._create_adapter(platform, config)
            if adapter:
                self._adapters[platform] = adapter
                logger.info("Messaging platform registered", platform=platform)
                return True
            
            return False
            
        except Exception as e:
            logger.error(
                "Failed to register messaging platform",
                platform=platform,
                error=str(e)
            )
            return False

    async def _create_adapter(self, platform: str, config: PlatformConfig) -> MessagingAdapter | None:
        """Create platform-specific adapter.
        
        Args:
        ----
            platform: Platform name
            config: Platform configuration
            
        Returns:
        -------
            MessagingAdapter | None: Created adapter or None if failed
        """
        try:
            if platform == "telegram":
                bot_token = config.credentials.get("bot_token")
                if not bot_token:
                    raise ValueError("Bot token required for Telegram")
                
                return TelegramAdapter(
                    bot_token=bot_token,
                    webhook_secret=config.webhook_secret,
                    webhook_url=config.webhook_url,
                    timeout=30,
                    max_retries=config.retry_attempts
                )
            
            elif platform == "whatsapp":
                access_token = config.credentials.get("access_token")
                phone_number_id = config.credentials.get("phone_number_id")
                if not access_token or not phone_number_id:
                    raise ValueError("Access token and phone number ID required for WhatsApp")
                
                return WhatsAppAdapter(
                    access_token=access_token,
                    phone_number_id=phone_number_id,
                    webhook_secret=config.webhook_secret,
                    webhook_url=config.webhook_url,
                    timeout=30,
                    max_retries=config.retry_attempts
                )
            
            elif platform == "vk":
                access_token = config.credentials.get("access_token")
                group_id = config.credentials.get("group_id")
                if not access_token or not group_id:
                    raise ValueError("Access token and group ID required for VK")
                
                return VKAdapter(
                    access_token=access_token,
                    group_id=group_id,
                    webhook_secret=config.webhook_secret,
                    webhook_url=config.webhook_url,
                    timeout=30,
                    max_retries=config.retry_attempts
                )
            
            elif platform == "viber":
                auth_token = config.credentials.get("auth_token")
                if not auth_token:
                    raise ValueError("Auth token required for Viber")
                
                return ViberAdapter(
                    auth_token=auth_token,
                    webhook_secret=config.webhook_secret,
                    webhook_url=config.webhook_url,
                    timeout=30,
                    max_retries=config.retry_attempts
                )
            
            else:
                logger.warning("Unsupported messaging platform", platform=platform)
                return None
                
        except Exception as e:
            logger.error(
                "Failed to create messaging adapter",
                platform=platform,
                error=str(e)
            )
            return None

    async def send_message(
        self,
        platform: str,
        chat_id: str,
        message: UnifiedMessage,
        priority: int = 0
    ) -> DeliveryResult:
        """Send message via messaging platform.
        
        Args:
        ----
            platform: Platform name
            chat_id: Target chat ID
            message: Message to send
            priority: Message priority
            
        Returns:
        -------
            DeliveryResult: Result of message sending
        """
        try:
            logger.info(
                "Sending message via messaging service",
                platform=platform,
                chat_id=chat_id,
                message_type=message.message_type,
                priority=priority
            )
            
            # Get platform adapter
            adapter = self._adapters.get(platform)
            if not adapter:
                raise ValueError(f"Platform {platform} not registered or not available")
            
            # Validate message platform matches
            if message.platform != platform:
                message.platform = platform
            
            # Send message via adapter
            result = await adapter.send_message(chat_id, message, priority)
            
            logger.info(
                "Message sent via messaging service",
                platform=platform,
                chat_id=chat_id,
                message_id=result.message_id,
                success=result.success,
                platform_message_id=result.platform_message_id
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to send message: {str(e)}"
            logger.error(
                "Message sending failed in service",
                platform=platform,
                chat_id=chat_id,
                error=error_msg
            )
            
            # Return failure result
            return DeliveryResult(
                message_id=message.message_id,
                platform=platform,
                status="failed",
                success=False,
                error_message=error_msg,
                timestamp=datetime.now()
            )

    async def send_message_from_request(
        self,
        platform: str,
        chat_id: str,
        text: str | None = None,
        message_type = None,
        reply_to_message_id: str | None = None,
        inline_keyboard: dict | None = None,
        reply_keyboard: dict | None = None,
        priority: int = 0
    ) -> DeliveryResult:
        """Send message from controller request - handles business logic.
        
        Args:
        ----
            platform: Platform name
            chat_id: Target chat ID
            text: Message text
            message_type: Type of message
            reply_to_message_id: Message ID to reply to
            inline_keyboard: Inline keyboard data
            reply_keyboard: Reply keyboard data
            priority: Message priority
            
        Returns:
        -------
            DeliveryResult: Result of message sending
        """
        try:
            # Import here to avoid circular imports
            from app.models.messaging import MessageType, MessageDirection
            
            # Business logic: Create unified message
            message = UnifiedMessage(
                message_id=str(uuid.uuid4()),
                platform=platform,
                platform_message_id="",  # Will be set by platform adapter
                user_id="system",  # System-sent message
                chat_id=chat_id,
                message_type=message_type or MessageType.TEXT,
                direction=MessageDirection.OUTBOUND,
                text=text,
                reply_to_message_id=reply_to_message_id,
                metadata={
                    "inline_keyboard": inline_keyboard,
                    "reply_keyboard": reply_keyboard
                }
            )
            
            # Business validation
            if not platform or not platform.strip():
                raise ValueError("Platform name is required")
                
            if not chat_id or not chat_id.strip():
                raise ValueError("Chat ID is required")
                
            if message_type == MessageType.TEXT and (not text or not text.strip()):
                raise ValueError("Text content is required for text messages")
            
            # Delegate to existing send_message method
            return await self.send_message(platform, chat_id, message, priority)
            
        except Exception as e:
            error_msg = f"Failed to send message from request: {str(e)}"
            logger.error(
                "Message sending from request failed",
                platform=platform,
                chat_id=chat_id,
                error=error_msg
            )
            
            return DeliveryResult(
                message_id=str(uuid.uuid4()),
                platform=platform,
                status="failed",
                success=False,
                error_message=error_msg,
                timestamp=datetime.now()
            )

    async def process_webhook(
        self,
        platform: str,
        payload: dict[str, Any],
        signature: str | None = None
    ) -> WebhookProcessingResult:
        """Process incoming webhook from messaging platform.
        
        Args:
        ----
            platform: Platform name
            payload: Webhook payload
            signature: Webhook signature for verification
            
        Returns:
        -------
            WebhookProcessingResult: Result of webhook processing
        """
        event_id = str(uuid.uuid4())
        
        try:
            logger.info(
                "Processing webhook via messaging service",
                platform=platform,
                event_id=event_id,
                event_type=payload.get("type", "unknown"),
                has_signature=signature is not None
            )
            
            # Get platform adapter
            adapter = self._adapters.get(platform)
            if not adapter:
                raise ValueError(f"Platform {platform} not registered or not available")
            
            # Process webhook via adapter
            messages = await adapter.receive_webhook(payload, signature)
            
            # TODO: Process extracted messages through conversation flow
            # For now, we just log them
            for message in messages:
                logger.info(
                    "Message extracted from webhook",
                    platform=platform,
                    message_id=message.message_id,
                    user_id=message.user_id,
                    chat_id=message.chat_id,
                    message_type=message.message_type,
                    text_preview=message.text[:50] if message.text else None
                )
            
            logger.info(
                "Webhook processed via messaging service",
                platform=platform,
                event_id=event_id,
                messages_extracted=len(messages)
            )
            
            return WebhookProcessingResult(
                event_id=event_id,
                platform=platform,
                success=True,
                messages=messages
            )
            
        except Exception as e:
            error_msg = f"Failed to process webhook: {str(e)}"
            logger.error(
                "Webhook processing failed in service",
                platform=platform,
                event_id=event_id,
                error=error_msg
            )
            
            return WebhookProcessingResult(
                event_id=event_id,
                platform=platform,
                success=False,
                messages=[],
                error=error_msg
            )

    async def get_conversation_context(
        self,
        platform: str,
        chat_id: str,
        user_id: str
    ) -> ConversationContext | None:
        """Get conversation context for a chat.
        
        Args:
        ----
            platform: Platform name
            chat_id: Chat ID
            user_id: User ID
            
        Returns:
        -------
            ConversationContext | None: Conversation context
        """
        try:
            adapter = self._adapters.get(platform)
            if not adapter:
                raise ValueError(f"Platform {platform} not registered or not available")
            
            context = await adapter.get_conversation_context(chat_id, user_id)
            
            logger.info(
                "Retrieved conversation context",
                platform=platform,
                chat_id=chat_id,
                user_id=user_id,
                has_context=context is not None
            )
            
            return context
            
        except Exception as e:
            logger.error(
                "Failed to get conversation context",
                platform=platform,
                chat_id=chat_id,
                user_id=user_id,
                error=str(e)
            )
            return None

    async def update_conversation_context(
        self,
        platform: str,
        context: ConversationContext
    ) -> bool:
        """Update conversation context.
        
        Args:
        ----
            platform: Platform name
            context: Updated conversation context
            
        Returns:
        -------
            bool: Whether update was successful
        """
        try:
            adapter = self._adapters.get(platform)
            if not adapter:
                raise ValueError(f"Platform {platform} not registered or not available")
            
            success = await adapter.update_conversation_context(context)
            
            logger.info(
                "Updated conversation context",
                platform=platform,
                conversation_id=context.conversation_id,
                success=success
            )
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to update conversation context",
                platform=platform,
                conversation_id=getattr(context, 'conversation_id', 'unknown'),
                error=str(e)
            )
            return False

    async def get_platform_stats(self, platform: str) -> MessageStats | None:
        """Get statistics for a messaging platform.
        
        Args:
        ----
            platform: Platform name
            
        Returns:
        -------
            MessageStats | None: Platform statistics
        """
        try:
            adapter = self._adapters.get(platform)
            if not adapter:
                raise ValueError(f"Platform {platform} not registered or not available")
            
            stats = await adapter.get_message_stats()
            
            logger.info(
                "Retrieved platform stats",
                platform=platform,
                total_sent=stats.total_sent,
                total_received=stats.total_received,
                success_rate=stats.success_rate
            )
            
            return stats
            
        except Exception as e:
            logger.error(
                "Failed to get platform stats",
                platform=platform,
                error=str(e)
            )
            return None

    async def get_supported_platforms(self) -> list[dict[str, Any]]:
        """Get list of supported messaging platforms.
        
        Returns:
        -------
            list[dict[str, Any]]: List of supported platforms with capabilities
        """
        platforms = []
        
        for platform, config in self._platform_configs.items():
            platform_info = {
                "name": platform,
                "enabled": config.enabled,
                "capabilities": {
                    "supports_inline_keyboard": config.supports_inline_keyboard,
                    "supports_reply_keyboard": config.supports_reply_keyboard,
                    "supports_media": config.supports_media,
                    "supports_files": config.supports_files
                },
                "limits": {
                    "max_text_length": config.max_text_length,
                    "max_file_size": config.max_file_size,
                    "rate_limit_per_second": config.rate_limit_per_second
                },
                "is_connected": platform in self._adapters
            }
            platforms.append(platform_info)
        
        return platforms

    async def setup_webhook(self, platform: str, webhook_url: str, secret_token: str | None = None) -> bool:
        """Set up webhook for a messaging platform.
        
        Args:
        ----
            platform: Platform name
            webhook_url: Webhook URL
            secret_token: Secret token for verification
            
        Returns:
        -------
            bool: Whether webhook setup was successful
        """
        try:
            adapter = self._adapters.get(platform)
            if not adapter:
                raise ValueError(f"Platform {platform} not registered or not available")
            
            # Check if adapter supports webhook setup
            if hasattr(adapter, 'setup_webhook'):
                success = await adapter.setup_webhook(webhook_url, secret_token)
                
                logger.info(
                    "Webhook setup attempted",
                    platform=platform,
                    webhook_url=webhook_url,
                    success=success
                )
                
                return success
            else:
                logger.warning(
                    "Platform does not support webhook setup",
                    platform=platform
                )
                return False
                
        except Exception as e:
            logger.error(
                "Failed to setup webhook",
                platform=platform,
                webhook_url=webhook_url,
                error=str(e)
            )
            return False

    async def health_check(self) -> dict[str, Any]:
        """Get health status of all registered messaging platforms.
        
        Returns:
        -------
            dict[str, Any]: Health status of all platforms
        """
        health_status = {}
        
        for platform, adapter in self._adapters.items():
            try:
                status = await adapter.get_health_status()
                health_status[platform] = status
            except Exception as e:
                health_status[platform] = {
                    "platform": platform,
                    "healthy": False,
                    "error": str(e),
                    "last_check": datetime.now().isoformat()
                }
        
        return {
            "messaging_platforms": health_status,
            "total_platforms": len(self._adapters),
            "healthy_platforms": sum(1 for status in health_status.values() if status.get("healthy", False)),
            "timestamp": datetime.now().isoformat()
        }

    async def cleanup(self):
        """Clean up messaging service resources."""
        try:
            # Close all adapters
            for platform, adapter in self._adapters.items():
                try:
                    await adapter.close()
                    logger.info("Closed messaging adapter", platform=platform)
                except Exception as e:
                    logger.error(
                        "Error closing messaging adapter",
                        platform=platform,
                        error=str(e)
                    )
            
            # Clear adapters
            self._adapters.clear()
            self._platform_configs.clear()
            
            logger.info("Messaging service cleanup completed")
            
        except Exception as e:
            logger.error("Error during messaging service cleanup", error=str(e))