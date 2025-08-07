"""Messaging platform API routes."""
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, HTTPException
import structlog

from app.api.controllers.messaging_controller import (
    MessagingController,
    SendMessageRequest,
    SendMessageResponse,
    WebhookRequest,
    WebhookResponse,
    ConversationContextRequest,
    ConversationContextResponse,
    PlatformStatsResponse
)
from app.api.dependencies import get_messaging_controller
from app.models.messaging import ConversationContext


logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/messaging", tags=["messaging"])


@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    controller: MessagingController = Depends(get_messaging_controller)
) -> SendMessageResponse:
    """Send a message via messaging platform.
    
    Args:
    ----
        request: Message sending request
        controller: Messaging controller instance
        
    Returns:
    -------
        SendMessageResponse: Result of message sending
    """
    logger.info(
        "Sending message via API",
        platform=request.platform,
        chat_id=request.chat_id,
        message_type=request.message_type,
        priority=request.priority
    )
    
    return await controller.send_message(request)


@router.post("/webhook/{platform}", response_model=WebhookResponse)
async def process_webhook(
    platform: str,
    request: Request,
    controller: MessagingController = Depends(get_messaging_controller),
    x_telegram_bot_api_secret_token: str | None = Header(None),
    x_hub_signature_256: str | None = Header(None),
    x_signature: str | None = Header(None)
) -> WebhookResponse:
    """Process incoming webhook from messaging platform.
    
    Args:
    ----
        platform: Platform name (telegram, whatsapp, etc.)
        request: Raw HTTP request
        controller: Messaging controller instance
        x_telegram_bot_api_secret_token: Telegram webhook secret
        x_hub_signature_256: WhatsApp webhook signature
        x_signature: Generic webhook signature
        
    Returns:
    -------
        WebhookResponse: Result of webhook processing
    """
    try:
        # Get raw payload
        payload = await request.json()
        
        # Determine signature based on platform
        signature = None
        if platform == "telegram":
            signature = x_telegram_bot_api_secret_token
        elif platform == "whatsapp":
            signature = x_hub_signature_256
        else:
            signature = x_signature
        
        logger.info(
            "Processing webhook via API",
            platform=platform,
            event_type=payload.get("type", "unknown"),
            has_signature=signature is not None,
            payload_keys=list(payload.keys()) if payload else []
        )
        
        # Create webhook request
        webhook_request = WebhookRequest(
            platform=platform,
            payload=payload,
            signature=signature
        )
        
        return await controller.process_webhook(webhook_request)
        
    except Exception as e:
        logger.error(
            "Failed to process webhook via API",
            platform=platform,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process webhook: {str(e)}"
        )


@router.get("/context/{platform}/{chat_id}/{user_id}", response_model=ConversationContextResponse)
async def get_conversation_context(
    platform: str,
    chat_id: str,
    user_id: str,
    controller: MessagingController = Depends(get_messaging_controller)
) -> ConversationContextResponse:
    """Get conversation context for a chat.
    
    Args:
    ----
        platform: Platform name
        chat_id: Chat ID
        user_id: User ID
        controller: Messaging controller instance
        
    Returns:
    -------
        ConversationContextResponse: Conversation context
    """
    logger.info(
        "Getting conversation context via API",
        platform=platform,
        chat_id=chat_id,
        user_id=user_id
    )
    
    request = ConversationContextRequest(
        platform=platform,
        chat_id=chat_id,
        user_id=user_id
    )
    
    return await controller.get_conversation_context(request)


@router.put("/context/{platform}/{chat_id}/{user_id}", response_model=ConversationContextResponse)
async def update_conversation_context(
    platform: str,
    chat_id: str,
    user_id: str,
    context: ConversationContext,
    controller: MessagingController = Depends(get_messaging_controller)
) -> ConversationContextResponse:
    """Update conversation context for a chat.
    
    Args:
    ----
        platform: Platform name
        chat_id: Chat ID
        user_id: User ID
        context: New conversation context
        controller: Messaging controller instance
        
    Returns:
    -------
        ConversationContextResponse: Update result
    """
    logger.info(
        "Updating conversation context via API",
        platform=platform,
        chat_id=chat_id,
        user_id=user_id,
        conversation_id=context.conversation_id
    )
    
    request = ConversationContextRequest(
        platform=platform,
        chat_id=chat_id,
        user_id=user_id
    )
    
    return await controller.update_conversation_context(request, context)


@router.get("/stats/{platform}", response_model=PlatformStatsResponse)
async def get_platform_stats(
    platform: str,
    controller: MessagingController = Depends(get_messaging_controller)
) -> PlatformStatsResponse:
    """Get statistics for a messaging platform.
    
    Args:
    ----
        platform: Platform name
        controller: Messaging controller instance
        
    Returns:
    -------
        PlatformStatsResponse: Platform statistics
    """
    logger.info(
        "Getting platform stats via API",
        platform=platform
    )
    
    return await controller.get_platform_stats(platform)


@router.get("/platforms")
async def list_supported_platforms(
    controller: MessagingController = Depends(get_messaging_controller)
) -> dict[str, Any]:
    """List all supported messaging platforms.
    
    Args:
    ----
        controller: Messaging controller instance
        
    Returns:
    -------
        dict[str, Any]: List of supported platforms
    """
    logger.info("Listing supported platforms via API")
    
    return await controller.list_supported_platforms()


@router.get("/health")
async def messaging_health_check(
    controller: MessagingController = Depends(get_messaging_controller)
) -> dict[str, Any]:
    """Get health status of messaging platforms.
    
    Args:
    ----
        controller: Messaging controller instance
        
    Returns:
    -------
        dict[str, Any]: Health status of all messaging platforms
    """
    try:
        # For now, return basic health info
        # In production, this would check adapter health
        return {
            "messaging_service": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "platforms": []
        }
        
    except Exception as e:
        logger.error("Messaging health check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"Messaging service health check failed: {str(e)}"
        )


# Telegram-specific routes
@router.post("/telegram/setup-webhook")
async def setup_telegram_webhook(
    webhook_url: str,
    secret_token: str | None = None,
    controller: MessagingController = Depends(get_messaging_controller)
) -> dict[str, Any]:
    """Set up Telegram webhook.
    
    Args:
    ----
        webhook_url: URL to receive webhooks
        secret_token: Secret token for verification
        controller: Messaging controller instance
        
    Returns:
    -------
        dict[str, Any]: Setup result
    """
    try:
        logger.info(
            "Setting up Telegram webhook",
            webhook_url=webhook_url,
            has_secret=secret_token is not None
        )
        
        # TODO: Implement webhook setup via messaging service
        # For now, return success
        return {
            "success": True,
            "message": "Webhook setup initiated",
            "webhook_url": webhook_url
        }
        
    except Exception as e:
        logger.error("Telegram webhook setup failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to setup Telegram webhook: {str(e)}"
        )