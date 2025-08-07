"""Messaging controller for handling messaging platform operations."""
import uuid
from typing import Any

import structlog
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.api.controllers.base import BaseController
from app.models.messaging import (
    UnifiedMessage,
    DeliveryResult,
    MessageDirection,
    MessageType,
    WebhookEvent,
    ConversationContext,
    MessageStats
)
from app.services.messaging_service import MessagingService


logger = structlog.get_logger()


class SendMessageRequest(BaseModel):
    """Request model for sending messages."""
    
    platform: str = Field(..., description="Messaging platform name")
    chat_id: str = Field(..., description="Target chat ID")
    text: str | None = Field(None, description="Message text")
    message_type: MessageType = Field(MessageType.TEXT, description="Type of message")
    reply_to_message_id: str | None = Field(None, description="Message ID to reply to")
    inline_keyboard: dict[str, Any] | None = Field(None, description="Inline keyboard data")
    reply_keyboard: dict[str, Any] | None = Field(None, description="Reply keyboard data")
    priority: int = Field(0, description="Message priority")


class SendMessageResponse(BaseModel):
    """Response model for sending messages."""
    
    success: bool = Field(..., description="Whether message was sent successfully")
    message_id: str = Field(..., description="Unique message ID")
    platform_message_id: str | None = Field(None, description="Platform-assigned message ID")
    delivery_status: str = Field(..., description="Delivery status")
    error: str | None = Field(None, description="Error message if failed")


class WebhookRequest(BaseModel):
    """Request model for webhook processing."""
    
    platform: str = Field(..., description="Messaging platform name")
    payload: dict[str, Any] = Field(..., description="Webhook payload")
    signature: str | None = Field(None, description="Webhook signature")


class WebhookResponse(BaseModel):
    """Response model for webhook processing."""
    
    success: bool = Field(..., description="Whether webhook was processed successfully")
    messages_processed: int = Field(..., description="Number of messages extracted")
    event_id: str = Field(..., description="Webhook event ID")


class ConversationContextRequest(BaseModel):
    """Request model for conversation context operations."""
    
    platform: str = Field(..., description="Messaging platform name")
    chat_id: str = Field(..., description="Chat ID")
    user_id: str = Field(..., description="User ID")


class ConversationContextResponse(BaseModel):
    """Response model for conversation context."""
    
    success: bool = Field(..., description="Whether operation was successful")
    context: ConversationContext | None = Field(None, description="Conversation context")


class PlatformStatsResponse(BaseModel):
    """Response model for platform statistics."""
    
    success: bool = Field(..., description="Whether stats retrieval was successful")
    stats: MessageStats | None = Field(None, description="Platform statistics")


class MessagingController(BaseController):
    """Controller for messaging platform operations.
    
    This controller handles HTTP requests for messaging operations,
    delegating business logic to the MessagingService.
    """

    def __init__(self, messaging_service: MessagingService):
        """Initialize the messaging controller.
        
        Args:
        ----
            messaging_service: Service for messaging business logic
        """
        super().__init__()
        self.messaging_service = messaging_service
        logger.info("Messaging controller initialized")

    async def send_message(self, request: SendMessageRequest) -> SendMessageResponse:
        """Send a message via messaging platform.
        
        Args:
        ----
            request: Message sending request
            
        Returns:
        -------
            SendMessageResponse: Result of message sending
        """
        return await self.handle_request(
            self._send_message_impl,
            request
        )

    async def _send_message_impl(self, request: SendMessageRequest) -> SendMessageResponse:
        """Implementation of message sending."""
        # Validate request
        validated_request = self._validate_send_message_request(request)
        
        # Create unified message
        message = UnifiedMessage(
            message_id=str(uuid.uuid4()),
            platform=validated_request.platform,
            platform_message_id="",  # Will be set by platform adapter
            user_id="system",  # System-sent message
            chat_id=validated_request.chat_id,
            message_type=validated_request.message_type,
            direction=MessageDirection.OUTBOUND,
            text=validated_request.text,
            reply_to_message_id=validated_request.reply_to_message_id,
            metadata={
                "inline_keyboard": validated_request.inline_keyboard,
                "reply_keyboard": validated_request.reply_keyboard
            }
        )
        
        # Send message via service
        result = await self.messaging_service.send_message(
            platform=validated_request.platform,
            chat_id=validated_request.chat_id,
            message=message,
            priority=validated_request.priority
        )
        
        return SendMessageResponse(
            success=result.success,
            message_id=result.message_id,
            platform_message_id=result.platform_message_id,
            delivery_status=result.status.value,
            error=result.error_message
        )

    def _validate_send_message_request(self, request: SendMessageRequest) -> SendMessageRequest:
        """Validate send message request.
        
        Args:
        ----
            request: Request to validate
            
        Returns:
        -------
            SendMessageRequest: Validated request
            
        Raises:
        ------
            HTTPException: If validation fails
        """
        # Validate platform
        if not request.platform or not request.platform.strip():
            raise HTTPException(
                status_code=400,
                detail="Platform name is required"
            )
        
        # Validate chat_id
        if not request.chat_id or not request.chat_id.strip():
            raise HTTPException(
                status_code=400,
                detail="Chat ID is required"
            )
        
        # Validate message content
        if request.message_type == MessageType.TEXT:
            if not request.text or not request.text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Text content is required for text messages"
                )
            if len(request.text) > 4096:
                raise HTTPException(
                    status_code=400,
                    detail="Text message too long (max 4096 characters)"
                )
        
        # Validate priority
        if request.priority < 0 or request.priority > 10:
            raise HTTPException(
                status_code=400,
                detail="Priority must be between 0 and 10"
            )
        
        return request

    async def process_webhook(self, request: WebhookRequest) -> WebhookResponse:
        """Process incoming webhook from messaging platform.
        
        Args:
        ----
            request: Webhook processing request
            
        Returns:
        -------
            WebhookResponse: Result of webhook processing
        """
        return await self.handle_request(
            self._process_webhook_impl,
            request
        )

    async def _process_webhook_impl(self, request: WebhookRequest) -> WebhookResponse:
        """Implementation of webhook processing."""
        # Validate request
        validated_request = self._validate_webhook_request(request)
        
        # Process webhook via service
        result = await self.messaging_service.process_webhook(
            platform=validated_request.platform,
            payload=validated_request.payload,
            signature=validated_request.signature
        )
        
        return WebhookResponse(
            success=True,
            messages_processed=len(result.messages),
            event_id=result.event_id
        )

    def _validate_webhook_request(self, request: WebhookRequest) -> WebhookRequest:
        """Validate webhook request.
        
        Args:
        ----
            request: Request to validate
            
        Returns:
        -------
            WebhookRequest: Validated request
            
        Raises:
        ------
            HTTPException: If validation fails
        """
        # Validate platform
        if not request.platform or not request.platform.strip():
            raise HTTPException(
                status_code=400,
                detail="Platform name is required"
            )
        
        # Validate payload
        if not request.payload:
            raise HTTPException(
                status_code=400,
                detail="Webhook payload is required"
            )
        
        return request

    async def get_conversation_context(
        self, request: ConversationContextRequest
    ) -> ConversationContextResponse:
        """Get conversation context for a chat.
        
        Args:
        ----
            request: Context request
            
        Returns:
        -------
            ConversationContextResponse: Conversation context
        """
        return await self.handle_request(
            self._get_conversation_context_impl,
            request
        )

    async def _get_conversation_context_impl(
        self, request: ConversationContextRequest
    ) -> ConversationContextResponse:
        """Implementation of getting conversation context."""
        # Validate request
        validated_request = self._validate_context_request(request)
        
        # Get context via service
        context = await self.messaging_service.get_conversation_context(
            platform=validated_request.platform,
            chat_id=validated_request.chat_id,
            user_id=validated_request.user_id
        )
        
        return ConversationContextResponse(
            success=True,
            context=context
        )

    async def update_conversation_context(
        self, request: ConversationContextRequest, context: ConversationContext
    ) -> ConversationContextResponse:
        """Update conversation context for a chat.
        
        Args:
        ----
            request: Context request
            context: New conversation context
            
        Returns:
        -------
            ConversationContextResponse: Update result
        """
        return await self.handle_request(
            self._update_conversation_context_impl,
            request,
            context
        )

    async def _update_conversation_context_impl(
        self, request: ConversationContextRequest, context: ConversationContext
    ) -> ConversationContextResponse:
        """Implementation of updating conversation context."""
        # Validate request
        validated_request = self._validate_context_request(request)
        
        # Update context via service
        success = await self.messaging_service.update_conversation_context(
            platform=validated_request.platform,
            context=context
        )
        
        return ConversationContextResponse(
            success=success,
            context=context if success else None
        )

    def _validate_context_request(self, request: ConversationContextRequest) -> ConversationContextRequest:
        """Validate conversation context request.
        
        Args:
        ----
            request: Request to validate
            
        Returns:
        -------
            ConversationContextRequest: Validated request
            
        Raises:
        ------
            HTTPException: If validation fails
        """
        # Validate platform
        if not request.platform or not request.platform.strip():
            raise HTTPException(
                status_code=400,
                detail="Platform name is required"
            )
        
        # Validate chat_id
        if not request.chat_id or not request.chat_id.strip():
            raise HTTPException(
                status_code=400,
                detail="Chat ID is required"
            )
        
        # Validate user_id
        if not request.user_id or not request.user_id.strip():
            raise HTTPException(
                status_code=400,
                detail="User ID is required"
            )
        
        return request

    async def get_platform_stats(self, platform: str) -> PlatformStatsResponse:
        """Get statistics for a messaging platform.
        
        Args:
        ----
            platform: Platform name
            
        Returns:
        -------
            PlatformStatsResponse: Platform statistics
        """
        return await self.handle_request(
            self._get_platform_stats_impl,
            platform
        )

    async def _get_platform_stats_impl(self, platform: str) -> PlatformStatsResponse:
        """Implementation of getting platform statistics."""
        # Validate platform name
        if not platform or not platform.strip():
            raise HTTPException(
                status_code=400,
                detail="Platform name is required"
            )
        
        # Get stats via service
        stats = await self.messaging_service.get_platform_stats(platform)
        
        return PlatformStatsResponse(
            success=True,
            stats=stats
        )

    async def list_supported_platforms(self) -> dict[str, Any]:
        """List all supported messaging platforms.
        
        Returns:
        -------
            dict[str, Any]: List of supported platforms with their capabilities
        """
        return await self.handle_request(
            self._list_supported_platforms_impl
        )

    async def _list_supported_platforms_impl(self) -> dict[str, Any]:
        """Implementation of listing supported platforms."""
        platforms = await self.messaging_service.get_supported_platforms()
        
        return {
            "success": True,
            "platforms": platforms,
            "total": len(platforms)
        }