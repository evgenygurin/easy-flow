"""Voice assistant controller - ONLY HTTP logic."""
import uuid
from typing import Any

import structlog
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.api.controllers.base import BaseController
from app.models.voice import VoicePlatform, VoicePlatformConfig
from app.services.voice_service import VoiceService


logger = structlog.get_logger()


# Request/Response models for HTTP API
class VoiceWebhookRequest(BaseModel):
    """Request for voice webhook processing."""
    
    platform: str = Field(..., description="Voice platform name")
    payload: dict[str, Any] = Field(..., description="Webhook payload")
    signature: str | None = Field(None, description="Webhook signature")


class VoiceWebhookResponse(BaseModel):
    """Response for voice webhook processing."""
    
    success: bool = Field(..., description="Processing success")
    event_id: str = Field(..., description="Event ID")
    platform: str = Field(..., description="Platform name")
    response: dict[str, Any] | None = Field(None, description="Platform response")
    error: str | None = Field(None, description="Error message")


class VoicePlatformInfo(BaseModel):
    """Voice platform information."""
    
    name: str = Field(..., description="Platform name")
    enabled: bool = Field(..., description="Whether platform is enabled")
    capabilities: dict[str, bool] = Field(..., description="Platform capabilities")
    languages: list[str] = Field(..., description="Supported languages")
    session_timeout_minutes: int = Field(..., description="Session timeout")
    is_connected: bool = Field(..., description="Connection status")


class VoiceHealthResponse(BaseModel):
    """Voice service health response."""
    
    voice_platforms: dict[str, Any] = Field(..., description="Platform health status")
    total_platforms: int = Field(..., description="Total platforms")
    healthy_platforms: int = Field(..., description="Healthy platforms")
    registered_intents: int = Field(..., description="Registered intents count")
    timestamp: str = Field(..., description="Health check timestamp")


class VoiceController(BaseController):
    """Voice assistant controller - ONLY HTTP logic."""
    
    def __init__(self, voice_service: VoiceService):
        """Initialize voice controller.
        
        Args:
        ----
            voice_service: Voice service for business logic
        """
        super().__init__()
        self.voice_service = voice_service
        
        logger.info("Voice controller initialized")
    
    async def process_webhook(self, request: VoiceWebhookRequest) -> VoiceWebhookResponse:
        """Process voice webhook - only HTTP validation and response formatting.
        
        Args:
        ----
            request: Webhook request
            
        Returns:
        -------
            VoiceWebhookResponse: Processing result
        """
        return await self.handle_request(
            self._process_webhook_impl,
            request
        )
    
    async def _process_webhook_impl(self, request: VoiceWebhookRequest) -> VoiceWebhookResponse:
        """Implementation of webhook processing.
        
        Args:
        ----
            request: Validated webhook request
            
        Returns:
        -------
            VoiceWebhookResponse: Processing result
        """
        # ✅ HTTP validation
        validated_request = self._validate_webhook_request(request)
        
        # ✅ Convert platform string to enum
        platform = self._parse_voice_platform(validated_request.platform)
        
        # ✅ Delegate to voice service (business logic)
        result = await self.voice_service.process_voice_webhook(
            platform=platform,
            request_data=validated_request.payload,
            signature=validated_request.signature
        )
        
        # ✅ Format HTTP response
        return VoiceWebhookResponse(
            success=result.success,
            event_id=result.event_id,
            platform=result.platform.value,
            response=result.response,
            error=result.error
        )
    
    async def get_supported_platforms(self) -> list[VoicePlatformInfo]:
        """Get supported voice platforms - only HTTP formatting.
        
        Returns:
        -------
            list[VoicePlatformInfo]: Platform information
        """
        return await self.handle_request(self._get_supported_platforms_impl)
    
    async def _get_supported_platforms_impl(self) -> list[VoicePlatformInfo]:
        """Implementation of getting supported platforms.
        
        Returns:
        -------
            list[VoicePlatformInfo]: Platform information
        """
        # ✅ Delegate to voice service
        platforms_data = await self.voice_service.get_supported_platforms()
        
        # ✅ Format HTTP response
        return [
            VoicePlatformInfo(
                name=platform["name"],
                enabled=platform["enabled"],
                capabilities=platform["capabilities"],
                languages=platform["languages"],
                session_timeout_minutes=platform["session_timeout_minutes"],
                is_connected=platform["is_connected"]
            )
            for platform in platforms_data
        ]
    
    async def get_health_status(self) -> VoiceHealthResponse:
        """Get voice service health status - only HTTP formatting.
        
        Returns:
        -------
            VoiceHealthResponse: Health status
        """
        return await self.handle_request(self._get_health_status_impl)
    
    async def _get_health_status_impl(self) -> VoiceHealthResponse:
        """Implementation of health status check.
        
        Returns:
        -------
            VoiceHealthResponse: Health status
        """
        # ✅ Delegate to voice service
        health_data = await self.voice_service.health_check()
        
        # ✅ Format HTTP response
        return VoiceHealthResponse(
            voice_platforms=health_data["voice_platforms"],
            total_platforms=health_data["total_platforms"],
            healthy_platforms=health_data["healthy_platforms"],
            registered_intents=health_data["registered_intents"],
            timestamp=health_data["timestamp"]
        )
    
    def _validate_webhook_request(self, request: VoiceWebhookRequest) -> VoiceWebhookRequest:
        """HTTP validation of webhook request.
        
        Args:
        ----
            request: Request to validate
            
        Returns:
        -------
            VoiceWebhookRequest: Validated request
            
        Raises:
        ------
            HTTPException: If validation fails
        """
        # Validate platform name
        if not request.platform or not request.platform.strip():
            raise HTTPException(
                status_code=400,
                detail="Platform name is required"
            )
        
        # Validate payload
        if not isinstance(request.payload, dict):
            raise HTTPException(
                status_code=400,
                detail="Payload must be a valid JSON object"
            )
        
        if not request.payload:
            raise HTTPException(
                status_code=400,
                detail="Payload cannot be empty"
            )
        
        # Validate platform is supported
        supported_platforms = [platform.value for platform in VoicePlatform]
        if request.platform not in supported_platforms:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform. Supported: {', '.join(supported_platforms)}"
            )
        
        return request
    
    def _parse_voice_platform(self, platform_str: str) -> VoicePlatform:
        """Parse voice platform from string.
        
        Args:
        ----
            platform_str: Platform string
            
        Returns:
        -------
            VoicePlatform: Parsed platform enum
            
        Raises:
        ------
            HTTPException: If platform is invalid
        """
        try:
            return VoicePlatform(platform_str)
        except ValueError:
            supported_platforms = [platform.value for platform in VoicePlatform]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid platform '{platform_str}'. Supported: {', '.join(supported_platforms)}"
            )