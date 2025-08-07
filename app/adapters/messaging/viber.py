"""Viber Business Messages adapter implementation."""
import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote

import structlog
import aiohttp

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
    InlineKeyboardButton as UnifiedInlineButton
)


logger = structlog.get_logger()


class ViberRateLimitConfig(MessagingRateLimitConfig):
    """Viber-specific rate limiting configuration."""
    
    messages_per_second: int = 10  # Conservative Viber rate limit
    burst_size: int = 3
    per_chat_limit: int = 1  # 1 message per second per chat


class ViberAdapter(MessagingAdapter):
    """Viber Business Messages API adapter for messaging."""

    def __init__(
        self,
        auth_token: str,
        bot_name: str,
        bot_avatar: str | None = None,
        webhook_url: str | None = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """Initialize Viber Business Messages adapter.

        Args:
        ----
            auth_token: Viber Bot authentication token
            bot_name: Bot display name
            bot_avatar: Bot avatar URL (optional)
            webhook_url: Webhook URL for receiving messages
            timeout: Request timeout
            max_retries: Maximum retry attempts
        """
        # Create platform config
        config = PlatformConfig(
            platform="viber",
            enabled=True,
            api_endpoint="https://chatapi.viber.com/pa",
            webhook_url=webhook_url,
            credentials={
                "auth_token": auth_token,
                "bot_name": bot_name,
                "bot_avatar": bot_avatar or ""
            },
            rate_limit_per_second=10,
            rate_limit_burst=3,
            supports_inline_keyboard=True,  # Viber keyboards
            supports_reply_keyboard=True,  # Viber keyboards
            supports_media=True,
            supports_files=True,
            max_text_length=7000,  # Viber text limit
            max_file_size=50 * 1024 * 1024,  # 50MB
            retry_attempts=max_retries,
            retry_delay_seconds=5,
            webhook_secret=None,  # Viber uses token-based auth
            verify_webhooks=True  # Always verify Viber webhooks
        )
        
        # Initialize parent class
        super().__init__(
            api_key=auth_token,
            base_url="https://chatapi.viber.com/pa",
            platform_name="viber",
            config=config,
            rate_limit_config=ViberRateLimitConfig(),
            timeout=timeout,
            max_retries=max_retries
        )
        
        self.auth_token = auth_token
        self.bot_name = bot_name
        self.bot_avatar = bot_avatar or ""
        
        # Delivery tracking
        self._message_delivery_status: dict[str, str] = {}
        
        logger.info(
            "Viber Business adapter initialized",
            bot_name=bot_name,
            has_avatar=bool(bot_avatar),
            webhook_url=webhook_url
        )

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for Viber API."""
        return {
            "X-Viber-Auth-Token": self.auth_token,
            "Content-Type": "application/json"
        }

    async def _send_platform_message(self, chat_id: str, message: UnifiedMessage) -> DeliveryResult:
        """Send message via Viber Business Messages API.
        
        Args:
        ----
            chat_id: Viber user ID
            message: Unified message to send
            
        Returns:
        -------
            DeliveryResult: Result of message sending
        """
        try:
            headers = await self._get_auth_headers()
            
            # Base message payload
            payload = {
                "receiver": chat_id,
                "type": "text",
                "sender": {
                    "name": self.bot_name,
                    "avatar": self.bot_avatar
                }
            }
            
            # Handle different message types
            if message.message_type == MessageType.TEXT:
                payload.update({
                    "type": "text",
                    "text": message.text or ""
                })
                
                # Add keyboard if present
                if message.inline_keyboard:
                    keyboard = self._create_viber_keyboard(message.inline_keyboard)
                    if keyboard:
                        payload["keyboard"] = keyboard
                
            elif message.message_type == MessageType.IMAGE and message.attachments:
                attachment = message.attachments[0]
                payload.update({
                    "type": "picture",
                    "media": attachment.url,
                    "text": message.text or ""
                })
                
            elif message.message_type == MessageType.VIDEO and message.attachments:
                attachment = message.attachments[0]
                payload.update({
                    "type": "video",
                    "media": attachment.url,
                    "size": attachment.file_size or 0
                })
                
            elif message.message_type == MessageType.DOCUMENT and message.attachments:
                attachment = message.attachments[0]
                payload.update({
                    "type": "file",
                    "media": attachment.url,
                    "size": attachment.file_size or 0,
                    "file_name": attachment.file_name or "document"
                })
                
            elif message.message_type == MessageType.LOCATION and message.metadata:
                # Viber location message
                lat = message.metadata.get("latitude")
                lon = message.metadata.get("longitude")
                if lat and lon:
                    payload.update({
                        "type": "location",
                        "location": {
                            "lat": float(lat),
                            "lon": float(lon)
                        }
                    })
                
            else:
                # Fallback to text
                payload.update({
                    "type": "text",
                    "text": message.text or f"Unsupported message type: {message.message_type}"
                })
            
            # Send message
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.base_url}/send_message",
                    headers=headers,
                    json=payload
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200 and response_data.get("status") == 0:
                        # Success
                        message_token = response_data.get("message_token")
                        
                        return DeliveryResult(
                            message_id=message.message_id,
                            platform=self.platform_name,
                            platform_message_id=str(message_token) if message_token else None,
                            status=DeliveryStatus.SENT,
                            success=True,
                            sent_at=datetime.now(),
                            timestamp=datetime.now(),
                            metadata={"viber_response": response_data}
                        )
                    else:
                        error_message = response_data.get("status_message", "Unknown Viber error")
                        error_code = response_data.get("status", response.status)
                        
                        logger.error(
                            "Viber API error",
                            chat_id=chat_id,
                            status=response.status,
                            error_code=error_code,
                            error_message=error_message
                        )
                        
                        return DeliveryResult(
                            message_id=message.message_id,
                            platform=self.platform_name,
                            status=DeliveryStatus.FAILED,
                            success=False,
                            error_code=str(error_code),
                            error_message=error_message,
                            timestamp=datetime.now()
                        )
            
        except aiohttp.ClientTimeout:
            return DeliveryResult(
                message_id=message.message_id,
                platform=self.platform_name,
                status=DeliveryStatus.FAILED,
                success=False,
                error_code="TIMEOUT",
                error_message=f"Request timed out after {self.timeout} seconds",
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(
                "Viber message send exception",
                chat_id=chat_id,
                error=str(e)
            )
            
            return DeliveryResult(
                message_id=message.message_id,
                platform=self.platform_name,
                status=DeliveryStatus.FAILED,
                success=False,
                error_code="EXCEPTION",
                error_message=str(e),
                timestamp=datetime.now()
            )

    def _create_viber_keyboard(self, keyboard: InlineKeyboard) -> dict[str, Any] | None:
        """Create Viber keyboard from unified inline keyboard format."""
        try:
            viber_buttons = []
            
            for row in keyboard.buttons[:7]:  # Viber supports max 7 rows
                for button in row[:6]:  # Viber supports max 6 buttons per row
                    viber_button = {
                        "Columns": 6 // len(row),  # Distribute evenly
                        "Rows": 1,
                        "Text": button.text[:30],  # Max 30 chars
                        "ActionType": "reply",
                        "ActionBody": button.callback_data or button.text,
                        "TextSize": "medium",
                        "TextHAlign": "center",
                        "TextVAlign": "middle"
                    }
                    
                    # Add URL action if present
                    if button.url:
                        viber_button.update({
                            "ActionType": "open-url",
                            "ActionBody": button.url
                        })
                    
                    viber_buttons.append(viber_button)
            
            return {
                "Type": "keyboard",
                "Buttons": viber_buttons,
                "DefaultHeight": False
            }
            
        except Exception as e:
            logger.error(
                "Failed to create Viber keyboard",
                error=str(e)
            )
            return None

    async def _extract_webhook_messages(self, payload: dict[str, Any]) -> list[UnifiedMessage]:
        """Extract unified messages from Viber webhook payload.
        
        Args:
        ----
            payload: Viber webhook payload
            
        Returns:
        -------
            list[UnifiedMessage]: Extracted unified messages
        """
        messages = []
        
        try:
            event = payload.get("event")
            
            if event == "message":
                # New message received
                message_data = payload.get("message", {})
                sender = payload.get("sender", {})
                unified_message = self._convert_viber_message(message_data, sender)
                if unified_message:
                    messages.append(unified_message)
            
            elif event == "delivered":
                # Message delivery confirmation
                message_token = payload.get("message_token")
                if message_token:
                    self._message_delivery_status[str(message_token)] = "delivered"
                    logger.info(
                        "Viber message delivered",
                        message_token=message_token
                    )
            
            elif event == "seen":
                # Message read confirmation
                message_token = payload.get("message_token")
                if message_token:
                    self._message_delivery_status[str(message_token)] = "seen"
                    logger.info(
                        "Viber message seen",
                        message_token=message_token
                    )
            
            elif event == "failed":
                # Message delivery failed
                message_token = payload.get("message_token")
                failure_reason = payload.get("desc", "Unknown failure")
                if message_token:
                    self._message_delivery_status[str(message_token)] = "failed"
                    logger.error(
                        "Viber message delivery failed",
                        message_token=message_token,
                        reason=failure_reason
                    )
            
        except Exception as e:
            logger.error(
                "Failed to extract messages from Viber webhook",
                error=str(e),
                event=payload.get("event"),
                payload_keys=list(payload.keys())
            )
        
        return messages

    def _convert_viber_message(self, msg: dict[str, Any], sender: dict[str, Any]) -> UnifiedMessage | None:
        """Convert Viber message to unified format."""
        try:
            # Determine message type and extract content
            message_type_str = msg.get("type", "text")
            text = None
            attachments = []
            
            if message_type_str == "text":
                message_type = MessageType.TEXT
                text = msg.get("text", "")
                
            elif message_type_str == "picture":
                message_type = MessageType.IMAGE
                text = msg.get("text")
                attachments.append(MessageAttachment(
                    type=MessageType.IMAGE,
                    url=msg.get("media", ""),
                    file_name=msg.get("file_name")
                ))
                
            elif message_type_str == "video":
                message_type = MessageType.VIDEO
                attachments.append(MessageAttachment(
                    type=MessageType.VIDEO,
                    url=msg.get("media", ""),
                    file_size=msg.get("size"),
                    duration=msg.get("duration")
                ))
                
            elif message_type_str == "file":
                message_type = MessageType.DOCUMENT
                attachments.append(MessageAttachment(
                    type=MessageType.DOCUMENT,
                    url=msg.get("media", ""),
                    file_name=msg.get("file_name"),
                    file_size=msg.get("size")
                ))
                
            elif message_type_str == "location":
                message_type = MessageType.LOCATION
                location = msg.get("location", {})
                text = f"Location: {location.get('lat', 0)}, {location.get('lon', 0)}"
                
            elif message_type_str == "contact":
                message_type = MessageType.CONTACT
                contact = msg.get("contact", {})
                text = f"Contact: {contact.get('name', 'Unknown')} - {contact.get('phone_number', 'No phone')}"
                
            elif message_type_str == "sticker":
                message_type = MessageType.STICKER
                text = f"Sticker ID: {msg.get('sticker_id', 'unknown')}"
                
            else:
                message_type = MessageType.TEXT
                text = f"Unsupported Viber message type: {message_type_str}"
            
            # Extract sender information
            user_id = sender.get("id", "unknown")
            name = sender.get("name", "")
            avatar = sender.get("avatar")
            
            # Parse name into first/last
            name_parts = name.split(" ", 1) if name else ["", ""]
            first_name = name_parts[0] if len(name_parts) > 0 else None
            last_name = name_parts[1] if len(name_parts) > 1 else None
            
            return UnifiedMessage(
                message_id=f"viber_{msg.get('message_id', int(time.time()))}_{user_id}",
                platform=self.platform_name,
                platform_message_id=str(msg.get("message_id", "")),
                user_id=user_id,
                username=None,  # Viber doesn't have usernames
                first_name=first_name,
                last_name=last_name,
                chat_id=user_id,  # In Viber, chat_id is same as user_id for individual chats
                chat_type="private",
                message_type=message_type,
                direction=MessageDirection.INBOUND,
                text=text,
                attachments=attachments,
                timestamp=datetime.now(),
                platform_timestamp=datetime.fromtimestamp(msg.get("timestamp", 0) / 1000),  # Viber uses milliseconds
                metadata={
                    "viber_message_id": msg.get("message_id"),
                    "sender": sender,
                    "message_type": message_type_str,
                    "avatar": avatar
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to convert Viber message",
                error=str(e),
                message_id=msg.get("message_id", "unknown")
            )
            return None

    async def _get_platform_conversation_context(
        self, chat_id: str, user_id: str
    ) -> ConversationContext | None:
        """Get Viber-specific conversation context."""
        return ConversationContext(
            conversation_id=f"viber_{chat_id}_{user_id}",
            platform=self.platform_name,
            user_id=user_id,
            chat_id=chat_id,
            state="active",
            language="ru",
            variables={},
            recent_messages=[]
        )

    async def _update_platform_conversation_context(self, context: ConversationContext) -> bool:
        """Update Viber-specific conversation context."""
        logger.info(
            "Viber conversation context updated",
            conversation_id=context.conversation_id,
            state=context.state
        )
        return True

    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify Viber webhook signature.
        
        For Viber, we verify the X-Viber-Auth-Token header matches our auth token.
        
        Args:
        ----
            payload: Raw webhook payload (not used for Viber)
            signature: X-Viber-Auth-Token header value
            secret: Expected auth token (should be same as self.auth_token)
            
        Returns:
        -------
            bool: Whether signature is valid
        """
        try:
            # Viber uses simple token comparison
            return hmac.compare_digest(signature, self.auth_token)
            
        except Exception as e:
            logger.error(
                "Viber webhook signature verification failed",
                error=str(e)
            )
            return False

    async def setup_webhook(self, webhook_url: str, event_types: list[str] | None = None) -> bool:
        """Set up Viber webhook.
        
        Args:
        ----
            webhook_url: URL to receive webhooks
            event_types: List of event types to subscribe to
            
        Returns:
        -------
            bool: Whether webhook setup was successful
        """
        try:
            headers = await self._get_auth_headers()
            
            payload = {
                "url": webhook_url,
                "event_types": event_types or [
                    "delivered", "seen", "failed", "subscribed", 
                    "unsubscribed", "conversation_started"
                ]
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.base_url}/set_webhook",
                    headers=headers,
                    json=payload
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200 and response_data.get("status") == 0:
                        logger.info(
                            "Viber webhook set up successfully",
                            webhook_url=webhook_url,
                            event_types=event_types
                        )
                        return True
                    else:
                        error_message = response_data.get("status_message", "Unknown error")
                        logger.error(
                            "Failed to set up Viber webhook",
                            webhook_url=webhook_url,
                            error=error_message
                        )
                        return False
            
        except Exception as e:
            logger.error(
                "Viber webhook setup exception",
                webhook_url=webhook_url,
                error=str(e)
            )
            return False

    async def get_account_info(self) -> dict[str, Any]:
        """Get Viber bot account information.
        
        Returns:
        -------
            dict[str, Any]: Account information
        """
        try:
            headers = await self._get_auth_headers()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.base_url}/get_account_info",
                    headers=headers,
                    json={}
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200 and response_data.get("status") == 0:
                        return {
                            "id": response_data.get("id"),
                            "name": response_data.get("name"),
                            "uri": response_data.get("uri"),
                            "icon": response_data.get("icon"),
                            "background": response_data.get("background"),
                            "category": response_data.get("category"),
                            "subcategory": response_data.get("subcategory"),
                            "location": response_data.get("location"),
                            "country": response_data.get("country"),
                            "webhook": response_data.get("webhook"),
                            "event_types": response_data.get("event_types", []),
                            "subscribers_count": response_data.get("subscribers_count", 0)
                        }
            
        except Exception as e:
            logger.error(
                "Failed to get Viber account info",
                error=str(e)
            )
        
        return {}

    async def get_user_details(self, user_id: str) -> dict[str, Any]:
        """Get Viber user details.
        
        Args:
        ----
            user_id: Viber user ID
            
        Returns:
        -------
            dict[str, Any]: User details
        """
        try:
            headers = await self._get_auth_headers()
            
            payload = {"id": user_id}
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.base_url}/get_user_details",
                    headers=headers,
                    json=payload
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200 and response_data.get("status") == 0:
                        user_data = response_data.get("user", {})
                        return {
                            "id": user_data.get("id"),
                            "name": user_data.get("name"),
                            "avatar": user_data.get("avatar"),
                            "country": user_data.get("country"),
                            "language": user_data.get("language"),
                            "api_version": user_data.get("api_version")
                        }
            
        except Exception as e:
            logger.error(
                "Failed to get Viber user details",
                user_id=user_id,
                error=str(e)
            )
        
        return {}

    async def send_broadcast_message(
        self, 
        user_ids: list[str], 
        message: UnifiedMessage
    ) -> list[DeliveryResult]:
        """Send broadcast message to multiple users.
        
        Args:
        ----
            user_ids: List of Viber user IDs
            message: Message to broadcast
            
        Returns:
        -------
            list[DeliveryResult]: Results for each user
        """
        results = []
        
        # Viber doesn't have native broadcast API, send individually
        for user_id in user_ids:
            result = await self.send_message(user_id, message)
            results.append(result)
            
            # Small delay between sends to respect rate limits
            await asyncio.sleep(0.1)
        
        return results

    def get_message_delivery_status(self, message_token: str) -> str | None:
        """Get delivery status for a message.
        
        Args:
        ----
            message_token: Viber message token
            
        Returns:
        -------
            str | None: Delivery status (sent, delivered, seen, failed) or None
        """
        return self._message_delivery_status.get(message_token)

    async def close(self):
        """Close Viber adapter connections."""
        try:
            await super().close()
            logger.info("Viber adapter closed")
        except Exception as e:
            logger.error("Error closing Viber adapter", error=str(e))