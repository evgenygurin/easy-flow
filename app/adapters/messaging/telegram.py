"""Telegram messaging adapter implementation."""
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote

import structlog
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.error import TelegramError, RetryAfter, TimedOut

from app.adapters.messaging.base import (
    MessagingAdapter,
    MessagingRateLimitConfig
)
from app.models.messaging import (
    UnifiedMessage,
    DeliveryResult,
    MessageType,
    MessageDirection,
    DeliveryStatus,
    ConversationContext,
    PlatformConfig,
    MessageAttachment,
    InlineKeyboard,
    ReplyKeyboard,
    InlineKeyboardButton as UnifiedInlineButton,
    ReplyKeyboardButton as UnifiedReplyButton
)


logger = structlog.get_logger()


class TelegramRateLimitConfig(MessagingRateLimitConfig):
    """Telegram-specific rate limiting configuration."""
    
    messages_per_second: int = 30  # Telegram limit
    burst_size: int = 5
    per_chat_limit: int = 1  # 1 message per second per chat


class TelegramAdapter(MessagingAdapter):
    """Telegram Bot API adapter for messaging."""

    def __init__(
        self,
        bot_token: str,
        webhook_secret: str | None = None,
        webhook_url: str | None = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """Initialize Telegram adapter.

        Args:
        ----
            bot_token: Telegram Bot API token
            webhook_secret: Secret for webhook verification
            webhook_url: URL for webhook setup
            timeout: Request timeout
            max_retries: Maximum retry attempts
        """
        # Create platform config
        config = PlatformConfig(
            platform="telegram",
            enabled=True,
            api_endpoint=f"https://api.telegram.org/bot{bot_token}",
            webhook_url=webhook_url,
            credentials={"bot_token": bot_token},
            rate_limit_per_second=30,
            rate_limit_burst=5,
            supports_inline_keyboard=True,
            supports_reply_keyboard=True,
            supports_media=True,
            supports_files=True,
            max_text_length=4096,
            max_file_size=20 * 1024 * 1024,  # 20MB
            retry_attempts=max_retries,
            retry_delay_seconds=5,
            webhook_secret=webhook_secret,
            verify_webhooks=webhook_secret is not None
        )
        
        # Initialize parent class
        super().__init__(
            api_key=bot_token,
            base_url=f"https://api.telegram.org/bot{bot_token}",
            platform_name="telegram",
            config=config,
            rate_limit_config=TelegramRateLimitConfig(),
            timeout=timeout,
            max_retries=max_retries
        )
        
        # Initialize Telegram Bot
        self.bot = Bot(token=bot_token)
        self.bot_token = bot_token
        self.webhook_secret = webhook_secret
        
        logger.info(
            "Telegram adapter initialized",
            bot_token_prefix=bot_token[:10] + "...",
            webhook_enabled=webhook_url is not None,
            verification_enabled=webhook_secret is not None
        )

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for Telegram API."""
        return {
            "Content-Type": "application/json"
        }

    async def _send_platform_message(self, chat_id: str, message: UnifiedMessage) -> DeliveryResult:
        """Send message via Telegram Bot API.
        
        Args:
        ----
            chat_id: Telegram chat ID
            message: Unified message to send
            
        Returns:
        -------
            DeliveryResult: Result of message sending
        """
        try:
            # Convert inline keyboard if present
            reply_markup = None
            if message.inline_keyboard:
                reply_markup = self._convert_inline_keyboard(message.inline_keyboard)
            elif message.reply_keyboard:
                reply_markup = self._convert_reply_keyboard(message.reply_keyboard)
            
            # Handle different message types
            if message.message_type == MessageType.TEXT:
                telegram_message = await self.bot.send_message(
                    chat_id=int(chat_id),
                    text=message.text or "",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=int(message.reply_to_message_id) if message.reply_to_message_id else None
                )
                
            elif message.message_type == MessageType.IMAGE and message.attachments:
                attachment = message.attachments[0]
                telegram_message = await self.bot.send_photo(
                    chat_id=int(chat_id),
                    photo=attachment.url,
                    caption=message.text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=int(message.reply_to_message_id) if message.reply_to_message_id else None
                )
                
            elif message.message_type == MessageType.DOCUMENT and message.attachments:
                attachment = message.attachments[0]
                telegram_message = await self.bot.send_document(
                    chat_id=int(chat_id),
                    document=attachment.url,
                    caption=message.text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=int(message.reply_to_message_id) if message.reply_to_message_id else None
                )
                
            else:
                # Fallback to text message
                telegram_message = await self.bot.send_message(
                    chat_id=int(chat_id),
                    text=message.text or f"Unsupported message type: {message.message_type}",
                    reply_markup=reply_markup,
                    reply_to_message_id=int(message.reply_to_message_id) if message.reply_to_message_id else None
                )
            
            return DeliveryResult(
                message_id=message.message_id,
                platform=self.platform_name,
                platform_message_id=str(telegram_message.message_id),
                status=DeliveryStatus.SENT,
                success=True,
                sent_at=datetime.now(),
                timestamp=datetime.now()
            )
            
        except RetryAfter as e:
            # Rate limit exceeded
            logger.warning(
                "Telegram rate limit hit",
                chat_id=chat_id,
                retry_after=e.retry_after
            )
            
            return DeliveryResult(
                message_id=message.message_id,
                platform=self.platform_name,
                status=DeliveryStatus.FAILED,
                success=False,
                error_code="RATE_LIMIT",
                error_message=f"Rate limit exceeded, retry after {e.retry_after} seconds",
                retry_count=1,
                timestamp=datetime.now()
            )
            
        except TimedOut as e:
            # Request timeout
            logger.warning(
                "Telegram request timeout",
                chat_id=chat_id,
                timeout=self.timeout
            )
            
            return DeliveryResult(
                message_id=message.message_id,
                platform=self.platform_name,
                status=DeliveryStatus.FAILED,
                success=False,
                error_code="TIMEOUT",
                error_message=f"Request timed out after {self.timeout} seconds",
                timestamp=datetime.now()
            )
            
        except TelegramError as e:
            # Telegram API error
            logger.error(
                "Telegram API error",
                chat_id=chat_id,
                error_code=e.message,
                error=str(e)
            )
            
            return DeliveryResult(
                message_id=message.message_id,
                platform=self.platform_name,
                status=DeliveryStatus.FAILED,
                success=False,
                error_code="TELEGRAM_ERROR",
                error_message=str(e),
                timestamp=datetime.now()
            )

    def _convert_inline_keyboard(self, keyboard: InlineKeyboard) -> InlineKeyboardMarkup:
        """Convert unified inline keyboard to Telegram format."""
        telegram_keyboard = []
        
        for row in keyboard.buttons:
            telegram_row = []
            for button in row:
                telegram_button = InlineKeyboardButton(
                    text=button.text,
                    callback_data=button.callback_data,
                    url=button.url,
                    switch_inline_query=button.switch_inline_query
                )
                telegram_row.append(telegram_button)
            telegram_keyboard.append(telegram_row)
        
        return InlineKeyboardMarkup(telegram_keyboard)

    def _convert_reply_keyboard(self, keyboard: ReplyKeyboard) -> ReplyKeyboardMarkup:
        """Convert unified reply keyboard to Telegram format."""
        telegram_keyboard = []
        
        for row in keyboard.buttons:
            telegram_row = []
            for button in row:
                telegram_button = KeyboardButton(
                    text=button.text,
                    request_contact=button.request_contact,
                    request_location=button.request_location
                )
                telegram_row.append(telegram_button)
            telegram_keyboard.append(telegram_row)
        
        return ReplyKeyboardMarkup(
            keyboard=telegram_keyboard,
            resize_keyboard=keyboard.resize_keyboard,
            one_time_keyboard=keyboard.one_time_keyboard,
            selective=keyboard.selective
        )

    async def _extract_webhook_messages(self, payload: dict[str, Any]) -> list[UnifiedMessage]:
        """Extract unified messages from Telegram webhook payload.
        
        Args:
        ----
            payload: Telegram webhook payload
            
        Returns:
        -------
            list[UnifiedMessage]: Extracted unified messages
        """
        messages = []
        
        try:
            # Create Update object from payload
            update = Update.de_json(payload, self.bot)
            
            if not update:
                return messages
            
            # Extract message from update
            telegram_message = None
            if update.message:
                telegram_message = update.message
            elif update.edited_message:
                telegram_message = update.edited_message
            elif update.callback_query and update.callback_query.message:
                # Handle callback queries as special messages
                callback_message = self._create_callback_message(update.callback_query)
                if callback_message:
                    messages.append(callback_message)
                telegram_message = update.callback_query.message
            
            if telegram_message:
                unified_message = self._convert_telegram_message(telegram_message)
                if unified_message:
                    messages.append(unified_message)
            
        except Exception as e:
            logger.error(
                "Failed to extract messages from Telegram webhook",
                error=str(e),
                payload_keys=list(payload.keys())
            )
        
        return messages

    def _convert_telegram_message(self, telegram_message) -> UnifiedMessage | None:
        """Convert Telegram message to unified format."""
        try:
            # Determine message type
            message_type = MessageType.TEXT
            attachments = []
            
            if telegram_message.photo:
                message_type = MessageType.IMAGE
                photo = telegram_message.photo[-1]  # Get highest resolution
                attachments.append(MessageAttachment(
                    type=MessageType.IMAGE,
                    url=f"https://api.telegram.org/file/bot{self.bot_token}/{photo.file_path}",
                    file_size=photo.file_size,
                    width=photo.width,
                    height=photo.height
                ))
                
            elif telegram_message.document:
                message_type = MessageType.DOCUMENT
                doc = telegram_message.document
                attachments.append(MessageAttachment(
                    type=MessageType.DOCUMENT,
                    url=f"https://api.telegram.org/file/bot{self.bot_token}/{doc.file_path}",
                    file_name=doc.file_name,
                    file_size=doc.file_size,
                    mime_type=doc.mime_type
                ))
                
            elif telegram_message.voice:
                message_type = MessageType.VOICE
                voice = telegram_message.voice
                attachments.append(MessageAttachment(
                    type=MessageType.VOICE,
                    url=f"https://api.telegram.org/file/bot{self.bot_token}/{voice.file_path}",
                    file_size=voice.file_size,
                    duration=voice.duration,
                    mime_type=voice.mime_type
                ))
            
            # Extract user information
            user = telegram_message.from_user
            username = user.username if user else None
            first_name = user.first_name if user else None
            last_name = user.last_name if user else None
            user_id = str(user.id) if user else "unknown"
            
            # Create unified message
            return UnifiedMessage(
                message_id=f"tg_{telegram_message.message_id}_{telegram_message.chat.id}",
                platform=self.platform_name,
                platform_message_id=str(telegram_message.message_id),
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                chat_id=str(telegram_message.chat.id),
                chat_type=telegram_message.chat.type,
                message_type=message_type,
                direction=MessageDirection.INBOUND,
                text=telegram_message.text or telegram_message.caption,
                attachments=attachments,
                reply_to_message_id=str(telegram_message.reply_to_message.message_id) 
                    if telegram_message.reply_to_message else None,
                timestamp=datetime.now(),
                platform_timestamp=telegram_message.date,
                metadata={
                    "message_id": telegram_message.message_id,
                    "chat_id": telegram_message.chat.id,
                    "chat_type": telegram_message.chat.type,
                    "from_user_id": user.id if user else None
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to convert Telegram message",
                error=str(e),
                message_id=getattr(telegram_message, 'message_id', 'unknown')
            )
            return None

    def _create_callback_message(self, callback_query) -> UnifiedMessage | None:
        """Create unified message from callback query."""
        try:
            user = callback_query.from_user
            
            return UnifiedMessage(
                message_id=f"tg_callback_{callback_query.id}",
                platform=self.platform_name,
                platform_message_id=callback_query.id,
                user_id=str(user.id),
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                chat_id=str(callback_query.message.chat.id) if callback_query.message else str(user.id),
                chat_type="callback",
                message_type=MessageType.COMMAND,
                direction=MessageDirection.INBOUND,
                text=callback_query.data,
                timestamp=datetime.now(),
                metadata={
                    "callback_query_id": callback_query.id,
                    "callback_data": callback_query.data,
                    "original_message_id": callback_query.message.message_id if callback_query.message else None
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to create callback message",
                error=str(e),
                callback_id=getattr(callback_query, 'id', 'unknown')
            )
            return None

    async def _get_platform_conversation_context(
        self, chat_id: str, user_id: str
    ) -> ConversationContext | None:
        """Get Telegram-specific conversation context."""
        # For now, return a basic context
        # In production, this would fetch from a conversation store
        return ConversationContext(
            conversation_id=f"tg_{chat_id}_{user_id}",
            platform=self.platform_name,
            user_id=user_id,
            chat_id=chat_id,
            state="active",
            language="ru",
            variables={},
            recent_messages=[],
            metadata={}
        )

    async def _update_platform_conversation_context(self, context: ConversationContext) -> bool:
        """Update Telegram-specific conversation context."""
        # For now, always return True
        # In production, this would update the conversation store
        logger.info(
            "Conversation context updated",
            conversation_id=context.conversation_id,
            platform=context.platform,
            state=context.state
        )
        return True

    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify Telegram webhook signature.
        
        Args:
        ----
            payload: Raw webhook payload
            signature: Signature from X-Telegram-Bot-Api-Secret-Token header
            secret: Webhook secret token
            
        Returns:
        -------
            bool: Whether signature is valid
        """
        if not secret:
            # No secret configured, skip verification
            return True
        
        try:
            # For Telegram, the signature is in the X-Telegram-Bot-Api-Secret-Token header
            # and should match the configured secret
            return hmac.compare_digest(signature, secret)
            
        except Exception as e:
            logger.error(
                "Telegram webhook signature verification failed",
                error=str(e)
            )
            return False

    async def setup_webhook(self, webhook_url: str, secret_token: str | None = None) -> bool:
        """Set up Telegram webhook.
        
        Args:
        ----
            webhook_url: URL to receive webhooks
            secret_token: Secret token for webhook verification
            
        Returns:
        -------
            bool: Whether webhook setup was successful
        """
        try:
            await self.bot.set_webhook(
                url=webhook_url,
                secret_token=secret_token,
                allowed_updates=[
                    "message",
                    "edited_message", 
                    "callback_query",
                    "inline_query"
                ],
                drop_pending_updates=True
            )
            
            logger.info(
                "Telegram webhook set up successfully",
                webhook_url=webhook_url,
                has_secret=secret_token is not None
            )
            
            return True
            
        except TelegramError as e:
            logger.error(
                "Failed to set up Telegram webhook",
                webhook_url=webhook_url,
                error=str(e)
            )
            return False

    async def delete_webhook(self) -> bool:
        """Delete Telegram webhook.
        
        Returns:
        -------
            bool: Whether webhook deletion was successful
        """
        try:
            await self.bot.delete_webhook(drop_pending_updates=True)
            logger.info("Telegram webhook deleted successfully")
            return True
            
        except TelegramError as e:
            logger.error(
                "Failed to delete Telegram webhook",
                error=str(e)
            )
            return False

    async def get_bot_info(self) -> dict[str, Any]:
        """Get information about the Telegram bot.
        
        Returns:
        -------
            dict[str, Any]: Bot information
        """
        try:
            bot_info = await self.bot.get_me()
            return {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
                "can_join_groups": bot_info.can_join_groups,
                "can_read_all_group_messages": bot_info.can_read_all_group_messages,
                "supports_inline_queries": bot_info.supports_inline_queries
            }
            
        except TelegramError as e:
            logger.error(
                "Failed to get Telegram bot info",
                error=str(e)
            )
            return {}

    async def close(self):
        """Close Telegram adapter connections."""
        try:
            await super().close()
            # Close bot session if needed
            logger.info("Telegram adapter closed")
        except Exception as e:
            logger.error("Error closing Telegram adapter", error=str(e))