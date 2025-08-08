"""Base voice assistant adapter."""
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import structlog

from app.models.voice import (
    VoiceMessage,
    VoiceResponse,
    VoiceSession,
    VoiceProcessingResult,
    VoicePlatformConfig,
    VoiceAnalytics
)


logger = structlog.get_logger()


class VoiceAdapter(ABC):
    """Base class for voice assistant platform adapters."""
    
    def __init__(
        self,
        config: VoicePlatformConfig,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """Initialize voice adapter.
        
        Args:
        ----
            config: Platform configuration
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.config = config
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Analytics tracking
        self._analytics = VoiceAnalytics(platform=config.platform)
        self._session_count = 0
        self._request_count = 0
        
        logger.info(
            "Voice adapter initialized",
            platform=config.platform.value,
            timeout=timeout,
            max_retries=max_retries
        )
    
    @abstractmethod
    async def process_voice_request(
        self,
        request_data: dict[str, Any],
        signature: str | None = None
    ) -> VoiceResponse:
        """Process incoming voice request.
        
        Args:
        ----
            request_data: Raw request data from platform
            signature: Request signature for verification
            
        Returns:
        -------
            VoiceResponse: Response to send back to platform
        """
        pass
    
    @abstractmethod
    async def extract_voice_message(
        self,
        request_data: dict[str, Any]
    ) -> VoiceMessage:
        """Extract unified voice message from platform request.
        
        Args:
        ----
            request_data: Raw request data
            
        Returns:
        -------
            VoiceMessage: Unified voice message
        """
        pass
    
    @abstractmethod
    async def format_voice_response(
        self,
        response: VoiceResponse
    ) -> dict[str, Any]:
        """Format voice response for platform.
        
        Args:
        ----
            response: Unified voice response
            
        Returns:
        -------
            dict[str, Any]: Platform-specific response format
        """
        pass
    
    @abstractmethod
    async def verify_request_signature(
        self,
        request_data: dict[str, Any],
        signature: str
    ) -> bool:
        """Verify request signature from platform.
        
        Args:
        ----
            request_data: Request data
            signature: Request signature
            
        Returns:
        -------
            bool: Whether signature is valid
        """
        pass
    
    async def get_session(
        self,
        session_id: str,
        user_id: str
    ) -> VoiceSession | None:
        """Get voice session by ID.
        
        Args:
        ----
            session_id: Session ID
            user_id: User ID
            
        Returns:
        -------
            VoiceSession | None: Session or None if not found
        """
        # Default implementation - override in platform adapters
        # for persistent session storage
        logger.debug(
            "Getting voice session",
            platform=self.config.platform.value,
            session_id=session_id,
            user_id=user_id
        )
        return None
    
    async def save_session(self, session: VoiceSession) -> bool:
        """Save voice session.
        
        Args:
        ----
            session: Session to save
            
        Returns:
        -------
            bool: Whether save was successful
        """
        # Default implementation - override in platform adapters
        # for persistent session storage
        logger.debug(
            "Saving voice session",
            platform=self.config.platform.value,
            session_id=session.session_id,
            user_id=session.user_id
        )
        return True
    
    async def create_session(
        self,
        session_id: str,
        user_id: str,
        supports_display: bool = False,
        supports_account_linking: bool = False
    ) -> VoiceSession:
        """Create new voice session.
        
        Args:
        ----
            session_id: Session ID
            user_id: User ID
            supports_display: Whether device has display
            supports_account_linking: Whether supports account linking
            
        Returns:
        -------
            VoiceSession: New session
        """
        session = VoiceSession(
            session_id=session_id,
            platform=self.config.platform,
            user_id=user_id,
            language=self.config.default_language,
            supports_display=supports_display,
            supports_account_linking=supports_account_linking
        )
        
        await self.save_session(session)
        self._session_count += 1
        
        logger.info(
            "Created voice session",
            platform=self.config.platform.value,
            session_id=session_id,
            user_id=user_id,
            supports_display=supports_display
        )
        
        return session
    
    async def end_session(self, session_id: str) -> bool:
        """End voice session.
        
        Args:
        ----
            session_id: Session ID to end
            
        Returns:
        -------
            bool: Whether session was ended successfully
        """
        # Default implementation - override for persistent storage
        logger.info(
            "Ending voice session",
            platform=self.config.platform.value,
            session_id=session_id
        )
        return True
    
    def _validate_request_data(self, request_data: dict[str, Any]) -> bool:
        """Validate request data format.
        
        Args:
        ----
            request_data: Request data to validate
            
        Returns:
        -------
            bool: Whether request data is valid
        """
        # Basic validation - override in platform adapters for specific checks
        if not isinstance(request_data, dict):
            return False
            
        # Check for required common fields
        if "request" not in request_data:
            return False
            
        return True
    
    def _update_analytics(
        self,
        success: bool,
        intent_confidence: float | None = None,
        response_time_ms: int | None = None
    ):
        """Update analytics metrics.
        
        Args:
        ----
            success: Whether request was successful
            intent_confidence: Intent recognition confidence
            response_time_ms: Response time in milliseconds
        """
        self._request_count += 1
        
        if success:
            self._analytics.successful_requests += 1
        else:
            self._analytics.failed_requests += 1
        
        self._analytics.total_requests = self._request_count
        
        if intent_confidence is not None:
            # Update running average confidence
            current_total = (
                self._analytics.average_confidence * 
                (self._request_count - 1)
            )
            self._analytics.average_confidence = (
                (current_total + intent_confidence) / self._request_count
            )
        
        if response_time_ms is not None:
            # Update running average response time
            current_total = (
                self._analytics.average_response_time_ms * 
                (self._request_count - 1)
            )
            self._analytics.average_response_time_ms = int(
                (current_total + response_time_ms) / self._request_count
            )
    
    async def get_analytics(self) -> VoiceAnalytics:
        """Get analytics for this adapter.
        
        Returns:
        -------
            VoiceAnalytics: Current analytics data
        """
        # Update calculated metrics
        if self._analytics.total_requests > 0:
            self._analytics.intent_recognition_rate = (
                self._analytics.successful_requests / self._analytics.total_requests
            )
        
        self._analytics.total_sessions = self._session_count
        self._analytics.date = datetime.now()
        
        return self._analytics
    
    async def get_health_status(self) -> dict[str, Any]:
        """Get health status of the voice adapter.
        
        Returns:
        -------
            dict[str, Any]: Health status information
        """
        return {
            "platform": self.config.platform.value,
            "healthy": True,
            "total_requests": self._request_count,
            "total_sessions": self._session_count,
            "success_rate": (
                self._analytics.successful_requests / max(self._request_count, 1)
            ),
            "last_check": datetime.now().isoformat(),
            "capabilities": {
                "supports_audio_output": self.config.supports_audio_output,
                "supports_display": self.config.supports_display,
                "supports_account_linking": self.config.supports_account_linking
            }
        }
    
    async def close(self):
        """Clean up adapter resources."""
        logger.info(
            "Closing voice adapter",
            platform=self.config.platform.value,
            total_requests=self._request_count,
            total_sessions=self._session_count
        )