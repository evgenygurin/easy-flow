"""WhatsApp Business Cloud API adapter implementation."""
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
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
    ReplyKeyboard
)


logger = structlog.get_logger()


class WhatsAppRateLimitConfig(MessagingRateLimitConfig):
    """WhatsApp-specific rate limiting configuration."""
    
    messages_per_second: int = 20  # WhatsApp Business API limit
    burst_size: int = 5
    per_chat_limit: int = 1  # 1 message per second per chat


class WhatsAppAdapter(MessagingAdapter):
    """WhatsApp Business Cloud API adapter for messaging."""

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        business_account_id: str,
        webhook_verify_token: str | None = None,
        app_secret: str | None = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """Initialize WhatsApp Business adapter.

        Args:
        ----
            access_token: WhatsApp Business API access token
            phone_number_id: Phone number ID from WhatsApp Business
            business_account_id: Business account ID
            webhook_verify_token: Token for webhook verification
            app_secret: App secret for signature verification
            timeout: Request timeout
            max_retries: Maximum retry attempts
        """
        # Create platform config
        config = PlatformConfig(
            platform="whatsapp",
            enabled=True,
            api_endpoint=f"https://graph.facebook.com/v18.0/{phone_number_id}",
            webhook_url=None,  # Set externally
            credentials={
                "access_token": access_token,
                "phone_number_id": phone_number_id,
                "business_account_id": business_account_id
            },
            rate_limit_per_second=20,
            rate_limit_burst=5,
            supports_inline_keyboard=True,  # Interactive buttons
            supports_reply_keyboard=False,  # Not supported
            supports_media=True,
            supports_files=True,
            max_text_length=4096,
            max_file_size=16 * 1024 * 1024,  # 16MB
            retry_attempts=max_retries,
            retry_delay_seconds=5,
            webhook_secret=app_secret,
            verify_webhooks=app_secret is not None
        )
        
        # Initialize parent class
        super().__init__(
            api_key=access_token,
            base_url=f"https://graph.facebook.com/v18.0/{phone_number_id}",
            platform_name="whatsapp",
            config=config,
            rate_limit_config=WhatsAppRateLimitConfig(),
            timeout=timeout,
            max_retries=max_retries
        )
        
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.business_account_id = business_account_id
        self.webhook_verify_token = webhook_verify_token
        self.app_secret = app_secret
        
        # 24-hour session window tracking
        self._session_windows: dict[str, datetime] = {}
        
        logger.info(
            "WhatsApp Business adapter initialized",
            phone_number_id=phone_number_id,
            business_account_id=business_account_id,
            verification_enabled=app_secret is not None
        )

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for WhatsApp Business API."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _is_within_session_window(self, chat_id: str) -> bool:
        """Check if we're within 24-hour session window for chat."""
        last_message_time = self._session_windows.get(chat_id)
        if not last_message_time:
            return False
            
        # WhatsApp 24-hour session window
        return datetime.now() - last_message_time < timedelta(hours=24)

    def _update_session_window(self, chat_id: str):
        """Update session window for chat."""
        self._session_windows[chat_id] = datetime.now()

    async def _send_platform_message(self, chat_id: str, message: UnifiedMessage) -> DeliveryResult:
        """Send message via WhatsApp Business Cloud API.
        
        Args:
        ----
            chat_id: WhatsApp phone number (with country code)
            message: Unified message to send
            
        Returns:
        -------
            DeliveryResult: Result of message sending
        """
        try:
            headers = await self._get_auth_headers()
            
            # Check if we need to use a template message (outside 24h window)
            if not self._is_within_session_window(chat_id):
                logger.info(
                    "Outside 24-hour window, may need template message",
                    chat_id=chat_id,
                    message_type=message.message_type
                )
            
            # Build message payload
            payload = {
                "messaging_product": "whatsapp",
                "to": chat_id,
                "recipient_type": "individual"
            }
            
            # Handle different message types
            if message.message_type == MessageType.TEXT:
                payload.update({
                    "type": "text",
                    "text": {"body": message.text or ""}
                })
                
                # Add interactive buttons if present
                if message.inline_keyboard:
                    interactive_payload = self._create_interactive_buttons(message.inline_keyboard)
                    payload.update(interactive_payload)
                
            elif message.message_type == MessageType.IMAGE and message.attachments:
                attachment = message.attachments[0]
                payload.update({
                    "type": "image",
                    "image": {
                        "link": attachment.url,
                        "caption": message.text or ""
                    }
                })
                
            elif message.message_type == MessageType.DOCUMENT and message.attachments:
                attachment = message.attachments[0]
                payload.update({
                    "type": "document",
                    "document": {
                        "link": attachment.url,
                        "filename": attachment.file_name or "document",
                        "caption": message.text or ""
                    }
                })
                
            elif message.message_type == MessageType.AUDIO and message.attachments:
                attachment = message.attachments[0]
                payload.update({
                    "type": "audio",
                    "audio": {
                        "link": attachment.url
                    }
                })
                
            elif message.message_type == MessageType.VIDEO and message.attachments:
                attachment = message.attachments[0]
                payload.update({
                    "type": "video",
                    "video": {
                        "link": attachment.url,
                        "caption": message.text or ""
                    }
                })
                
            else:
                # Fallback to text message
                payload.update({
                    "type": "text",
                    "text": {"body": message.text or f"Unsupported message type: {message.message_type}"}
                })
            
            # Send message
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=payload
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200 and response_data.get("messages"):
                        # Update session window
                        self._update_session_window(chat_id)
                        
                        whatsapp_message_id = response_data["messages"][0]["id"]
                        
                        return DeliveryResult(
                            message_id=message.message_id,
                            platform=self.platform_name,
                            platform_message_id=whatsapp_message_id,
                            status=DeliveryStatus.SENT,
                            success=True,
                            sent_at=datetime.now(),
                            timestamp=datetime.now(),
                            metadata={"whatsapp_response": response_data}
                        )
                    else:
                        error_message = response_data.get("error", {}).get("message", "Unknown error")
                        error_code = response_data.get("error", {}).get("code", response.status)
                        
                        logger.error(
                            "WhatsApp API error",
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
                "WhatsApp message send exception",
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

    def _create_interactive_buttons(self, keyboard: InlineKeyboard) -> dict[str, Any]:
        """Create WhatsApp interactive buttons from inline keyboard."""
        # WhatsApp supports up to 3 quick reply buttons or 10 list items
        buttons = []
        
        for row in keyboard.buttons[:3]:  # Max 3 buttons
            for button in row:
                if len(buttons) >= 3:
                    break
                    
                buttons.append({
                    "type": "reply",
                    "reply": {
                        "id": button.callback_data or f"btn_{len(buttons)}",
                        "title": button.text[:20]  # Max 20 chars for button title
                    }
                })
        
        return {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Choose an option:"},
                "action": {"buttons": buttons}
            }
        }

    async def _extract_webhook_messages(self, payload: dict[str, Any]) -> list[UnifiedMessage]:
        """Extract unified messages from WhatsApp webhook payload.
        
        Args:
        ----
            payload: WhatsApp webhook payload
            
        Returns:
        -------
            list[UnifiedMessage]: Extracted unified messages
        """
        messages = []
        
        try:
            # WhatsApp webhook structure
            if "entry" not in payload:
                return messages
            
            for entry in payload["entry"]:
                if "changes" not in entry:
                    continue
                    
                for change in entry["changes"]:
                    if change.get("field") != "messages":
                        continue
                        
                    value = change.get("value", {})
                    
                    # Process incoming messages
                    if "messages" in value:
                        for msg in value["messages"]:
                            unified_message = self._convert_whatsapp_message(msg, value)
                            if unified_message:
                                messages.append(unified_message)
                                # Update session window for incoming message
                                self._update_session_window(unified_message.chat_id)
                    
                    # Process status updates (delivery receipts)
                    if "statuses" in value:
                        for status in value["statuses"]:
                            self._process_status_update(status)
            
        except Exception as e:
            logger.error(
                "Failed to extract messages from WhatsApp webhook",
                error=str(e),
                payload_keys=list(payload.keys())
            )
        
        return messages

    def _convert_whatsapp_message(self, msg: dict[str, Any], value: dict[str, Any]) -> UnifiedMessage | None:
        """Convert WhatsApp message to unified format."""
        try:
            # Get contact info
            contacts = {contact["wa_id"]: contact for contact in value.get("contacts", [])}
            contact = contacts.get(msg["from"], {})
            
            # Determine message type and extract content
            message_type = MessageType.TEXT
            text = None
            attachments = []
            
            if "text" in msg:
                message_type = MessageType.TEXT
                text = msg["text"]["body"]
                
            elif "image" in msg:
                message_type = MessageType.IMAGE
                image_data = msg["image"]
                text = image_data.get("caption")
                attachments.append(MessageAttachment(
                    type=MessageType.IMAGE,
                    url=image_data.get("link", ""),
                    file_name=image_data.get("filename"),
                    mime_type=image_data.get("mime_type"),
                    file_size=None  # Not provided in webhook
                ))
                
            elif "document" in msg:
                message_type = MessageType.DOCUMENT
                doc_data = msg["document"]
                text = doc_data.get("caption")
                attachments.append(MessageAttachment(
                    type=MessageType.DOCUMENT,
                    url=doc_data.get("link", ""),
                    file_name=doc_data.get("filename"),
                    mime_type=doc_data.get("mime_type"),
                    file_size=None  # Not provided in webhook
                ))
                
            elif "audio" in msg:
                message_type = MessageType.AUDIO
                audio_data = msg["audio"]
                attachments.append(MessageAttachment(
                    type=MessageType.AUDIO,
                    url=audio_data.get("link", ""),
                    mime_type=audio_data.get("mime_type"),
                    file_size=None  # Not provided in webhook
                ))
                
            elif "video" in msg:
                message_type = MessageType.VIDEO
                video_data = msg["video"]
                text = video_data.get("caption")
                attachments.append(MessageAttachment(
                    type=MessageType.VIDEO,
                    url=video_data.get("link", ""),
                    file_name=video_data.get("filename"),
                    mime_type=video_data.get("mime_type"),
                    file_size=None  # Not provided in webhook
                ))
                
            elif "interactive" in msg:
                # Handle interactive message responses (button clicks)
                interactive = msg["interactive"]
                if interactive["type"] == "button_reply":
                    message_type = MessageType.COMMAND
                    text = interactive["button_reply"]["id"]
                elif interactive["type"] == "list_reply":
                    message_type = MessageType.COMMAND
                    text = interactive["list_reply"]["id"]
            
            # Create unified message
            return UnifiedMessage(
                message_id=f"wa_{msg['id']}",
                platform=self.platform_name,
                platform_message_id=msg["id"],
                user_id=msg["from"],
                username=None,  # WhatsApp doesn't have usernames
                first_name=contact.get("profile", {}).get("name"),
                last_name=None,
                chat_id=msg["from"],  # In WhatsApp, chat_id is same as user phone number for individual chats
                chat_type="private",
                message_type=message_type,
                direction=MessageDirection.INBOUND,
                text=text,
                attachments=attachments,
                timestamp=datetime.now(),
                platform_timestamp=datetime.fromtimestamp(int(msg["timestamp"])),
                metadata={
                    "whatsapp_message_id": msg["id"],
                    "from": msg["from"],
                    "contact_profile": contact.get("profile", {}),
                    "message_type": msg["type"]
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to convert WhatsApp message",
                error=str(e),
                message_id=msg.get("id", "unknown")
            )
            return None

    def _process_status_update(self, status: dict[str, Any]):
        """Process WhatsApp message status update."""
        try:
            message_id = status["id"]
            status_type = status["status"]  # sent, delivered, read, failed
            
            logger.info(
                "WhatsApp message status update",
                message_id=message_id,
                status=status_type,
                recipient=status.get("recipient_id"),
                timestamp=status.get("timestamp")
            )
            
            # Here you could update message delivery status in your database
            # For now, just log the update
            
        except Exception as e:
            logger.error(
                "Failed to process WhatsApp status update",
                error=str(e),
                status=status
            )

    async def _get_platform_conversation_context(
        self, chat_id: str, user_id: str
    ) -> ConversationContext | None:
        """Get WhatsApp-specific conversation context."""
        return ConversationContext(
            conversation_id=f"wa_{chat_id}_{user_id}",
            platform=self.platform_name,
            user_id=user_id,
            chat_id=chat_id,
            state="active",
            language="ru",
            variables={
                "session_window_active": self._is_within_session_window(chat_id)
            },
            recent_messages=[]
        )

    async def _update_platform_conversation_context(self, context: ConversationContext) -> bool:
        """Update WhatsApp-specific conversation context."""
        logger.info(
            "WhatsApp conversation context updated",
            conversation_id=context.conversation_id,
            state=context.state
        )
        return True

    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify WhatsApp webhook signature using Meta's method.
        
        Args:
        ----
            payload: Raw webhook payload
            signature: Signature from X-Hub-Signature-256 header
            secret: App secret from Meta
            
        Returns:
        -------
            bool: Whether signature is valid
        """
        if not secret:
            return True
        
        try:
            # Meta uses sha256 HMAC with X-Hub-Signature-256 header
            if not signature.startswith("sha256="):
                return False
                
            expected_signature = signature[7:]  # Remove 'sha256=' prefix
            computed_signature = hmac.new(
                secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, computed_signature)
            
        except Exception as e:
            logger.error(
                "WhatsApp webhook signature verification failed",
                error=str(e)
            )
            return False

    async def send_template_message(
        self,
        chat_id: str,
        template_name: str,
        language_code: str = "ru",
        parameters: list[str] | None = None
    ) -> DeliveryResult:
        """Send WhatsApp template message (for use outside 24-hour window).
        
        Args:
        ----
            chat_id: WhatsApp phone number
            template_name: Name of approved template
            language_code: Template language code
            parameters: Template parameters
            
        Returns:
        -------
            DeliveryResult: Result of message sending
        """
        try:
            headers = await self._get_auth_headers()
            
            # Build template payload
            payload = {
                "messaging_product": "whatsapp",
                "to": chat_id,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": language_code}
                }
            }
            
            # Add parameters if provided
            if parameters:
                payload["template"]["components"] = [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": param} for param in parameters]
                }]
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=payload
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200 and response_data.get("messages"):
                        whatsapp_message_id = response_data["messages"][0]["id"]
                        
                        # Update session window after template message
                        self._update_session_window(chat_id)
                        
                        return DeliveryResult(
                            message_id=f"template_{int(time.time())}",
                            platform=self.platform_name,
                            platform_message_id=whatsapp_message_id,
                            status=DeliveryStatus.SENT,
                            success=True,
                            sent_at=datetime.now(),
                            timestamp=datetime.now(),
                            metadata={
                                "template_name": template_name,
                                "whatsapp_response": response_data
                            }
                        )
                    else:
                        error_message = response_data.get("error", {}).get("message", "Template send failed")
                        
                        return DeliveryResult(
                            message_id=f"template_{int(time.time())}",
                            platform=self.platform_name,
                            status=DeliveryStatus.FAILED,
                            success=False,
                            error_message=error_message,
                            timestamp=datetime.now()
                        )
            
        except Exception as e:
            logger.error(
                "WhatsApp template message send failed",
                template_name=template_name,
                chat_id=chat_id,
                error=str(e)
            )
            
            return DeliveryResult(
                message_id=f"template_{int(time.time())}",
                platform=self.platform_name,
                status=DeliveryStatus.FAILED,
                success=False,
                error_message=str(e),
                timestamp=datetime.now()
            )

    async def upload_media(self, file_url: str, file_type: str) -> str | None:
        """Upload media to WhatsApp and get media ID.
        
        Args:
        ----
            file_url: URL of file to upload
            file_type: MIME type of file
            
        Returns:
        -------
            str | None: WhatsApp media ID or None if failed
        """
        try:
            headers = await self._get_auth_headers()
            
            # First, download the file
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status != 200:
                        return None
                    
                    file_data = await response.read()
            
            # Upload to WhatsApp
            data = aiohttp.FormData()
            data.add_field("messaging_product", "whatsapp")
            data.add_field("file", file_data, content_type=file_type)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://graph.facebook.com/v18.0/{self.phone_number_id}/media",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    data=data
                ) as response:
                    response_data = await response.json()
                    
                    if response.status == 200 and "id" in response_data:
                        return response_data["id"]
            
        except Exception as e:
            logger.error(
                "WhatsApp media upload failed",
                file_url=file_url,
                error=str(e)
            )
        
        return None

    async def verify_webhook_request(self, query_params: dict[str, str]) -> str | None:
        """Verify WhatsApp webhook verification request.
        
        Args:
        ----
            query_params: Query parameters from webhook verification request
            
        Returns:
        -------
            str | None: Challenge string if verification successful
        """
        hub_mode = query_params.get("hub.mode")
        hub_verify_token = query_params.get("hub.verify_token")
        hub_challenge = query_params.get("hub.challenge")
        
        if (hub_mode == "subscribe" and 
            hub_verify_token == self.webhook_verify_token):
            logger.info("WhatsApp webhook verification successful")
            return hub_challenge
        
        logger.warning(
            "WhatsApp webhook verification failed",
            mode=hub_mode,
            provided_token=hub_verify_token,
            expected_token=self.webhook_verify_token
        )
        return None

    async def close(self):
        """Close WhatsApp adapter connections."""
        try:
            await super().close()
            logger.info("WhatsApp adapter closed")
        except Exception as e:
            logger.error("Error closing WhatsApp adapter", error=str(e))