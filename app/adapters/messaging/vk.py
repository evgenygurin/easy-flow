"""VK Community Messages adapter implementation."""
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
    InlineKeyboardButton as UnifiedInlineButton,
    ReplyKeyboardButton as UnifiedReplyButton
)


logger = structlog.get_logger()


class VKRateLimitConfig(MessagingRateLimitConfig):
    """VK-specific rate limiting configuration."""
    
    messages_per_second: int = 20  # VK API limit is 20 calls/sec
    burst_size: int = 5
    per_chat_limit: int = 1  # 1 message per second per chat


class VKAdapter(MessagingAdapter):
    """VK Community Messages API adapter for messaging."""

    def __init__(
        self,
        access_token: str,
        group_id: str,
        confirmation_token: str | None = None,
        secret_key: str | None = None,
        api_version: str = "5.131",
        timeout: int = 30,
        max_retries: int = 3
    ):
        """Initialize VK Community Messages adapter.

        Args:
        ----
            access_token: VK Community access token with messages permission
            group_id: VK Community group ID
            confirmation_token: Token for webhook confirmation
            secret_key: Secret key for webhook verification
            api_version: VK API version
            timeout: Request timeout
            max_retries: Maximum retry attempts
        """
        # Create platform config
        config = PlatformConfig(
            platform="vk",
            enabled=True,
            api_endpoint="https://api.vk.com/method",
            webhook_url=None,  # Set externally
            credentials={
                "access_token": access_token,
                "group_id": group_id,
                "api_version": api_version
            },
            rate_limit_per_second=20,
            rate_limit_burst=5,
            supports_inline_keyboard=True,  # VK keyboards
            supports_reply_keyboard=True,  # VK keyboards
            supports_media=True,
            supports_files=True,
            max_text_length=4096,
            max_file_size=50 * 1024 * 1024,  # 50MB for documents
            retry_attempts=max_retries,
            retry_delay_seconds=5,
            webhook_secret=secret_key,
            verify_webhooks=secret_key is not None
        )
        
        # Initialize parent class
        super().__init__(
            api_key=access_token,
            base_url="https://api.vk.com/method",
            platform_name="vk",
            config=config,
            rate_limit_config=VKRateLimitConfig(),
            timeout=timeout,
            max_retries=max_retries
        )
        
        self.access_token = access_token
        self.group_id = group_id
        self.confirmation_token = confirmation_token
        self.secret_key = secret_key
        self.api_version = api_version
        
        logger.info(
            "VK Community Messages adapter initialized",
            group_id=group_id,
            api_version=api_version,
            verification_enabled=secret_key is not None
        )

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for VK API."""
        return {
            "Content-Type": "application/json"
        }

    async def _make_vk_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make authenticated request to VK API."""
        # Add auth parameters
        params.update({
            "access_token": self.access_token,
            "v": self.api_version
        })
        
        headers = await self._get_auth_headers()
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.post(
                f"{self.base_url}/{method}",
                headers=headers,
                data=params  # VK API expects form data, not JSON
            ) as response:
                response_data = await response.json()
                
                if "error" in response_data:
                    error = response_data["error"]
                    raise ValueError(f"VK API error {error['error_code']}: {error['error_msg']}")
                
                return response_data.get("response", {})

    async def _send_platform_message(self, chat_id: str, message: UnifiedMessage) -> DeliveryResult:
        """Send message via VK Messages API.
        
        Args:
        ----
            chat_id: VK user ID or peer ID
            message: Unified message to send
            
        Returns:
        -------
            DeliveryResult: Result of message sending
        """
        try:
            # Generate random_id for VK API
            random_id = int(time.time() * 1000)
            
            # Base parameters
            params = {
                "peer_id": int(chat_id),
                "random_id": random_id,
                "message": message.text or ""
            }
            
            # Handle keyboard attachments
            if message.inline_keyboard or message.reply_keyboard:
                keyboard = self._create_vk_keyboard(message.inline_keyboard or message.reply_keyboard)
                if keyboard:
                    params["keyboard"] = json.dumps(keyboard, ensure_ascii=False)
            
            # Handle media attachments
            attachment_strings = []
            for attachment in message.attachments:
                attachment_str = await self._upload_attachment(attachment)
                if attachment_str:
                    attachment_strings.append(attachment_str)
            
            if attachment_strings:
                params["attachment"] = ",".join(attachment_strings)
            
            # Send message
            response = await self._make_vk_request("messages.send", params)
            
            if response:
                vk_message_id = str(response)  # VK returns message ID directly
                
                return DeliveryResult(
                    message_id=message.message_id,
                    platform=self.platform_name,
                    platform_message_id=vk_message_id,
                    status=DeliveryStatus.SENT,
                    success=True,
                    sent_at=datetime.now(),
                    timestamp=datetime.now(),
                    metadata={"vk_random_id": random_id}
                )
            else:
                return DeliveryResult(
                    message_id=message.message_id,
                    platform=self.platform_name,
                    status=DeliveryStatus.FAILED,
                    success=False,
                    error_message="Empty response from VK API",
                    timestamp=datetime.now()
                )
            
        except ValueError as e:
            # VK API error
            logger.error(
                "VK API error",
                chat_id=chat_id,
                error=str(e)
            )
            
            return DeliveryResult(
                message_id=message.message_id,
                platform=self.platform_name,
                status=DeliveryStatus.FAILED,
                success=False,
                error_code="VK_API_ERROR",
                error_message=str(e),
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
                "VK message send exception",
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

    def _create_vk_keyboard(self, keyboard: InlineKeyboard | ReplyKeyboard) -> dict[str, Any] | None:
        """Create VK keyboard from unified keyboard format."""
        try:
            if isinstance(keyboard, InlineKeyboard):
                # VK inline keyboard
                buttons = []
                for row in keyboard.buttons[:10]:  # VK supports max 10 rows
                    button_row = []
                    for button in row[:5]:  # VK supports max 5 buttons per row
                        vk_button = {
                            "action": {
                                "type": "text",
                                "label": button.text[:40]  # VK button label max 40 chars
                            }
                        }
                        
                        # VK uses different colors for buttons
                        vk_button["color"] = "secondary"  # default color
                        
                        button_row.append(vk_button)
                    
                    if button_row:
                        buttons.append(button_row)
                
                return {
                    "buttons": buttons,
                    "inline": True
                }
                
            elif isinstance(keyboard, ReplyKeyboard):
                # VK reply keyboard
                buttons = []
                for row in keyboard.buttons[:10]:  # VK supports max 10 rows
                    button_row = []
                    for button in row[:5]:  # VK supports max 5 buttons per row
                        vk_button = {
                            "action": {
                                "type": "text",
                                "label": button.text[:40]
                            },
                            "color": "primary"
                        }
                        button_row.append(vk_button)
                    
                    if button_row:
                        buttons.append(button_row)
                
                return {
                    "buttons": buttons,
                    "one_time": keyboard.one_time_keyboard if hasattr(keyboard, 'one_time_keyboard') else False
                }
            
        except Exception as e:
            logger.error(
                "Failed to create VK keyboard",
                error=str(e)
            )
        
        return None

    async def _upload_attachment(self, attachment: MessageAttachment) -> str | None:
        """Upload attachment to VK and get attachment string."""
        try:
            if attachment.type == MessageType.IMAGE:
                # Upload photo
                upload_info = await self._make_vk_request("photos.getMessagesUploadServer", {
                    "peer_id": 0  # For community messages
                })
                
                # Upload file to VK servers
                upload_url = upload_info["upload_url"]
                
                # Download file first
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as response:
                        if response.status != 200:
                            return None
                        file_data = await response.read()
                
                # Upload to VK
                data = aiohttp.FormData()
                data.add_field("photo", file_data, filename="image.jpg")
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(upload_url, data=data) as response:
                        upload_response = await response.json()
                
                # Save photo
                save_response = await self._make_vk_request("photos.saveMessagesPhoto", {
                    "photo": upload_response["photo"],
                    "server": upload_response["server"],
                    "hash": upload_response["hash"]
                })
                
                if save_response:
                    photo = save_response[0]
                    return f"photo{photo['owner_id']}_{photo['id']}"
                
            elif attachment.type == MessageType.DOCUMENT:
                # Upload document
                upload_info = await self._make_vk_request("docs.getMessagesUploadServer", {
                    "type": "doc",
                    "peer_id": 0
                })
                
                upload_url = upload_info["upload_url"]
                
                # Download file
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as response:
                        if response.status != 200:
                            return None
                        file_data = await response.read()
                
                # Upload to VK
                data = aiohttp.FormData()
                data.add_field("file", file_data, filename=attachment.file_name or "document")
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(upload_url, data=data) as response:
                        upload_response = await response.json()
                
                # Save document
                save_response = await self._make_vk_request("docs.save", {
                    "file": upload_response["file"],
                    "title": attachment.file_name or "Document"
                })
                
                if save_response and save_response["doc"]:
                    doc = save_response["doc"]
                    return f"doc{doc['owner_id']}_{doc['id']}"
            
        except Exception as e:
            logger.error(
                "VK attachment upload failed",
                attachment_type=attachment.type,
                error=str(e)
            )
        
        return None

    async def _extract_webhook_messages(self, payload: dict[str, Any]) -> list[UnifiedMessage]:
        """Extract unified messages from VK webhook payload.
        
        Args:
        ----
            payload: VK Callback API payload
            
        Returns:
        -------
            list[UnifiedMessage]: Extracted unified messages
        """
        messages = []
        
        try:
            event_type = payload.get("type")
            
            if event_type == "message_new":
                # New incoming message
                message_data = payload.get("object", {}).get("message", {})
                unified_message = self._convert_vk_message(message_data)
                if unified_message:
                    messages.append(unified_message)
            
        except Exception as e:
            logger.error(
                "Failed to extract messages from VK webhook",
                error=str(e),
                payload_keys=list(payload.keys())
            )
        
        return messages

    def _convert_vk_message(self, msg: dict[str, Any]) -> UnifiedMessage | None:
        """Convert VK message to unified format."""
        try:
            # Determine message type and extract content
            message_type = MessageType.TEXT
            text = msg.get("text", "")
            attachments = []
            
            # Process VK attachments
            for attachment in msg.get("attachments", []):
                att_type = attachment.get("type")
                att_data = attachment.get(att_type, {})
                
                if att_type == "photo":
                    message_type = MessageType.IMAGE
                    # Get the largest photo size
                    sizes = att_data.get("sizes", [])
                    if sizes:
                        largest = max(sizes, key=lambda x: x.get("width", 0) * x.get("height", 0))
                        attachments.append(MessageAttachment(
                            type=MessageType.IMAGE,
                            url=largest["url"],
                            width=largest.get("width"),
                            height=largest.get("height")
                        ))
                
                elif att_type == "doc":
                    if att_data.get("type") in [1, 2, 3, 4, 5]:  # Document types
                        message_type = MessageType.DOCUMENT
                        attachments.append(MessageAttachment(
                            type=MessageType.DOCUMENT,
                            url=att_data["url"],
                            file_name=att_data.get("title"),
                            file_size=att_data.get("size")
                        ))
                
                elif att_type == "audio_message":
                    message_type = MessageType.VOICE
                    attachments.append(MessageAttachment(
                        type=MessageType.VOICE,
                        url=att_data["link_mp3"],
                        duration=att_data.get("duration"),
                        file_size=None
                    ))
            
            # Extract user information (limited in VK due to privacy)
            from_id = msg.get("from_id")
            peer_id = msg.get("peer_id")
            
            return UnifiedMessage(
                message_id=f"vk_{msg['id']}_{peer_id}",
                platform=self.platform_name,
                platform_message_id=str(msg["id"]),
                user_id=str(from_id),
                username=None,  # VK doesn't provide username in messages
                first_name=None,  # Would need separate API call to get user info
                last_name=None,
                chat_id=str(peer_id),
                chat_type="private" if peer_id > 0 else "group",
                message_type=message_type,
                direction=MessageDirection.INBOUND,
                text=text if text else None,
                attachments=attachments,
                timestamp=datetime.now(),
                platform_timestamp=datetime.fromtimestamp(msg.get("date", 0)),
                metadata={
                    "vk_message_id": msg["id"],
                    "from_id": from_id,
                    "peer_id": peer_id,
                    "conversation_message_id": msg.get("conversation_message_id"),
                    "random_id": msg.get("random_id")
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to convert VK message",
                error=str(e),
                message_id=msg.get("id", "unknown")
            )
            return None

    async def _get_platform_conversation_context(
        self, chat_id: str, user_id: str
    ) -> ConversationContext | None:
        """Get VK-specific conversation context."""
        return ConversationContext(
            conversation_id=f"vk_{chat_id}_{user_id}",
            platform=self.platform_name,
            user_id=user_id,
            chat_id=chat_id,
            state="active",
            language="ru",
            variables={},
            recent_messages=[]
        )

    async def _update_platform_conversation_context(self, context: ConversationContext) -> bool:
        """Update VK-specific conversation context."""
        logger.info(
            "VK conversation context updated",
            conversation_id=context.conversation_id,
            state=context.state
        )
        return True

    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify VK webhook signature.
        
        Args:
        ----
            payload: Raw webhook payload
            signature: Signature from request header
            secret: VK Callback API secret key
            
        Returns:
        -------
            bool: Whether signature is valid
        """
        if not secret:
            return True
        
        try:
            # VK uses simple hash comparison
            computed_hash = hashlib.sha256(secret.encode() + payload).hexdigest()
            return hmac.compare_digest(signature, computed_hash)
            
        except Exception as e:
            logger.error(
                "VK webhook signature verification failed",
                error=str(e)
            )
            return False

    async def handle_webhook_confirmation(self, payload: dict[str, Any]) -> str | None:
        """Handle VK webhook confirmation request.
        
        Args:
        ----
            payload: VK webhook confirmation payload
            
        Returns:
        -------
            str | None: Confirmation token if this is a confirmation request
        """
        if payload.get("type") == "confirmation":
            group_id = payload.get("group_id")
            if str(group_id) == str(self.group_id):
                logger.info(
                    "VK webhook confirmation requested",
                    group_id=group_id
                )
                return self.confirmation_token
        
        return None

    async def get_user_info(self, user_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Get VK user information.
        
        Args:
        ----
            user_ids: List of VK user IDs
            
        Returns:
        -------
            dict[str, dict[str, Any]]: User information by user ID
        """
        try:
            if not user_ids:
                return {}
            
            response = await self._make_vk_request("users.get", {
                "user_ids": ",".join(user_ids),
                "fields": "first_name,last_name,photo_50"
            })
            
            result = {}
            for user in response:
                result[str(user["id"])] = {
                    "first_name": user.get("first_name"),
                    "last_name": user.get("last_name"),
                    "photo_url": user.get("photo_50")
                }
            
            return result
            
        except Exception as e:
            logger.error(
                "Failed to get VK user info",
                user_ids=user_ids,
                error=str(e)
            )
            return {}

    async def mark_as_read(self, peer_id: str, start_message_id: str) -> bool:
        """Mark messages as read in VK conversation.
        
        Args:
        ----
            peer_id: VK peer ID
            start_message_id: Starting message ID to mark as read
            
        Returns:
        -------
            bool: Whether operation was successful
        """
        try:
            await self._make_vk_request("messages.markAsRead", {
                "peer_id": int(peer_id),
                "start_message_id": int(start_message_id)
            })
            return True
            
        except Exception as e:
            logger.error(
                "Failed to mark VK messages as read",
                peer_id=peer_id,
                start_message_id=start_message_id,
                error=str(e)
            )
            return False

    async def close(self):
        """Close VK adapter connections."""
        try:
            await super().close()
            logger.info("VK adapter closed")
        except Exception as e:
            logger.error("Error closing VK adapter", error=str(e))