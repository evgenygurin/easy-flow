"""Voice assistant API routes - thin layer."""
from fastapi import APIRouter, Depends, Request
from typing import Any

from app.api.controllers.voice_controller import (
    VoiceController,
    VoiceWebhookRequest,
    VoiceWebhookResponse,
    VoicePlatformInfo,
    VoiceHealthResponse
)
from app.api.dependencies import get_voice_controller


# Create router for voice endpoints
router = APIRouter(prefix="/voice", tags=["voice"])


@router.post(
    "/webhook/{platform}",
    response_model=VoiceWebhookResponse,
    summary="Process voice webhook",
    description="Process incoming webhook from voice assistant platform"
)
async def process_voice_webhook(
    platform: str,
    request: Request,
    controller: VoiceController = Depends(get_voice_controller)
) -> VoiceWebhookResponse:
    """Process voice webhook - maximum 10 lines per CLAUDE.md."""
    # Get raw payload and signature
    payload = await request.json()
    signature = request.headers.get("X-Hub-Signature") or request.headers.get("Authorization")
    
    # Create webhook request
    webhook_request = VoiceWebhookRequest(
        platform=platform,
        payload=payload,
        signature=signature
    )
    
    return await controller.process_webhook(webhook_request)


@router.get(
    "/platforms",
    response_model=list[VoicePlatformInfo],
    summary="Get supported voice platforms",
    description="Get list of supported voice assistant platforms and their capabilities"
)
async def get_supported_platforms(
    controller: VoiceController = Depends(get_voice_controller)
) -> list[VoicePlatformInfo]:
    """Get supported voice platforms - thin delegation layer."""
    return await controller.get_supported_platforms()


@router.get(
    "/health",
    response_model=VoiceHealthResponse,
    summary="Get voice service health",
    description="Get health status of voice assistant service and all registered platforms"
)
async def get_voice_health(
    controller: VoiceController = Depends(get_voice_controller)
) -> VoiceHealthResponse:
    """Get voice service health - thin delegation layer."""
    return await controller.get_health_status()


# Yandex Alice specific endpoints (following Alice documentation)
@router.post(
    "/alice",
    response_model=dict[str, Any],
    summary="Yandex Alice webhook",
    description="Webhook endpoint specifically for Yandex Alice skill"
)
async def alice_webhook(
    request: Request,
    controller: VoiceController = Depends(get_voice_controller)
) -> dict[str, Any]:
    """Yandex Alice webhook - platform-specific endpoint."""
    payload = await request.json()
    signature = request.headers.get("X-Hub-Signature")
    
    webhook_request = VoiceWebhookRequest(
        platform="yandex_alice",
        payload=payload,
        signature=signature
    )
    
    result = await controller.process_webhook(webhook_request)
    
    # Return the platform response directly for Alice
    if result.success and result.response:
        return result.response
    else:
        # Return error response in Alice format
        return {
            "version": "1.0",
            "response": {
                "text": "Извините, произошла ошибка. Попробуйте позже.",
                "end_session": True
            }
        }