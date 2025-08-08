"""Voice assistant models for all voice platforms."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VoicePlatform(str, Enum):
    """Voice assistant platforms."""
    
    YANDEX_ALICE = "yandex_alice"
    AMAZON_ALEXA = "amazon_alexa" 
    GOOGLE_ASSISTANT = "google_assistant"
    APPLE_SIRI = "apple_siri"


class VoiceMessageType(str, Enum):
    """Type of voice message content."""
    
    TEXT = "text"
    AUDIO = "audio"
    DIRECTIVE = "directive"  # Platform-specific actions
    CARD = "card"  # Rich content display
    INTENT = "intent"  # Structured intent data


class VoiceDirection(str, Enum):
    """Direction of voice interaction."""
    
    REQUEST = "request"  # From user to assistant
    RESPONSE = "response"  # From assistant to user


class VoiceSessionState(str, Enum):
    """State of voice session."""
    
    ACTIVE = "active"
    ENDED = "ended"
    PAUSED = "paused"
    ERROR = "error"


class EntityType(str, Enum):
    """Types of extracted entities."""
    
    PRODUCT = "product"
    ORDER_ID = "order_id"
    DATE = "date"
    PRICE = "price"
    LOCATION = "location"
    PERSON = "person"
    PHONE = "phone"
    EMAIL = "email"
    CUSTOM = "custom"


class VoiceIntent(BaseModel):
    """Recognized intent from voice input."""
    
    name: str = Field(..., description="Intent name")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    entities: dict[str, Any] = Field(
        default_factory=dict, description="Extracted entities"
    )


class VoiceEntity(BaseModel):
    """Extracted entity from voice input."""
    
    type: EntityType = Field(..., description="Entity type")
    value: Any = Field(..., description="Entity value")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    start_pos: int | None = Field(None, description="Start position in text")
    end_pos: int | None = Field(None, description="End position in text")


class VoiceCard(BaseModel):
    """Rich content card for voice response."""
    
    title: str = Field(..., description="Card title")
    text: str | None = Field(None, description="Card text")
    image_url: str | None = Field(None, description="Card image URL")
    buttons: list[dict[str, str]] = Field(
        default_factory=list, description="Action buttons"
    )


class VoiceDirective(BaseModel):
    """Platform-specific directive."""
    
    type: str = Field(..., description="Directive type")
    payload: dict[str, Any] = Field(..., description="Directive payload")


class VoiceMessage(BaseModel):
    """Unified voice message model."""
    
    # Core message fields
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    platform: VoicePlatform = Field(..., description="Voice platform")
    platform_message_id: str = Field(..., description="Platform-specific message ID")
    
    # Session information
    session_id: str = Field(..., description="Voice session ID")
    user_id: str = Field(..., description="User ID")
    
    # Message content
    message_type: VoiceMessageType = Field(..., description="Message type")
    direction: VoiceDirection = Field(..., description="Message direction")
    
    # Text content (transcribed speech or text response)
    text: str | None = Field(None, description="Text content")
    
    # Speech synthesis
    speech_text: str | None = Field(None, description="Text for speech synthesis")
    speech_url: str | None = Field(None, description="Pre-generated speech audio URL")
    
    # Intent recognition (for requests)
    intent: VoiceIntent | None = Field(None, description="Recognized intent")
    entities: list[VoiceEntity] = Field(
        default_factory=list, description="Extracted entities"
    )
    
    # Rich content (for responses)
    card: VoiceCard | None = Field(None, description="Rich content card")
    directives: list[VoiceDirective] = Field(
        default_factory=list, description="Platform directives"
    )
    
    # Session management
    should_end_session: bool = Field(False, description="Whether to end session")
    expects_user_input: bool = Field(True, description="Whether expecting user response")
    
    # Timestamps
    timestamp: datetime = Field(default_factory=datetime.now)
    platform_timestamp: datetime | None = Field(None, description="Platform timestamp")
    
    # Metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Platform-specific metadata"
    )


class VoiceSession(BaseModel):
    """Voice session context."""
    
    session_id: str = Field(..., description="Session ID")
    platform: VoicePlatform = Field(..., description="Voice platform")
    user_id: str = Field(..., description="User ID")
    
    # Session state
    state: VoiceSessionState = Field(VoiceSessionState.ACTIVE)
    current_intent: str | None = Field(None, description="Current active intent")
    language: str = Field("ru", description="Session language")
    
    # Context variables
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Session variables"
    )
    
    # Flow control
    current_flow: str | None = Field(None, description="Current conversation flow")
    flow_step: str | None = Field(None, description="Current flow step")
    
    # Message history (limited for context)
    recent_messages: list[str] = Field(
        default_factory=list, description="Recent message IDs"
    )
    
    # Timestamps
    started_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    ends_at: datetime | None = Field(None, description="Session expiration")
    
    # Capabilities
    supports_audio: bool = Field(True, description="Supports audio output")
    supports_display: bool = Field(False, description="Has display for cards/images")
    supports_account_linking: bool = Field(False, description="Supports account linking")


class VoiceResponse(BaseModel):
    """Response to voice platform."""
    
    # Response content
    text: str | None = Field(None, description="Response text")
    speech: str | None = Field(None, description="Speech synthesis text")
    
    # Rich content
    card: VoiceCard | None = Field(None, description="Rich card")
    directives: list[VoiceDirective] = Field(
        default_factory=list, description="Platform directives"
    )
    
    # Session control
    should_end_session: bool = Field(False, description="End session")
    expects_user_input: bool = Field(True, description="Expect user response")
    
    # Session data to store
    session_attributes: dict[str, Any] = Field(
        default_factory=dict, description="Session attributes to persist"
    )


class VoiceWebhookEvent(BaseModel):
    """Webhook event from voice platform."""
    
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    platform: VoicePlatform = Field(..., description="Voice platform")
    event_type: str = Field(..., description="Event type")
    
    # Timing
    timestamp: datetime = Field(default_factory=datetime.now)
    platform_timestamp: datetime | None = Field(None, description="Platform timestamp")
    
    # Event data
    payload: dict[str, Any] = Field(..., description="Raw webhook payload")
    signature: str | None = Field(None, description="Webhook signature")
    
    # Processing state
    processed: bool = Field(False, description="Whether processed")
    processed_at: datetime | None = Field(None, description="Processing timestamp")
    
    # Extracted message
    message: VoiceMessage | None = Field(None, description="Extracted voice message")


class VoiceProcessingResult(BaseModel):
    """Result of voice message processing."""
    
    success: bool = Field(..., description="Processing success")
    response: VoiceResponse | None = Field(None, description="Voice response")
    error: str | None = Field(None, description="Error message")
    
    # Processing metadata
    intent_confidence: float | None = Field(None, description="Intent recognition confidence")
    processing_time_ms: int | None = Field(None, description="Processing time in ms")
    
    # Session updates
    session_updated: bool = Field(False, description="Whether session was updated")
    flow_changed: bool = Field(False, description="Whether conversation flow changed")


class VoicePlatformConfig(BaseModel):
    """Configuration for voice platform."""
    
    platform: VoicePlatform = Field(..., description="Platform name")
    enabled: bool = Field(True, description="Whether platform is enabled")
    
    # Webhook configuration
    webhook_url: str | None = Field(None, description="Webhook URL")
    webhook_secret: str | None = Field(None, description="Webhook verification secret")
    verify_webhooks: bool = Field(True, description="Verify webhook signatures")
    
    # Authentication
    credentials: dict[str, str] = Field(..., description="Platform credentials")
    
    # Platform capabilities
    supports_audio_output: bool = Field(True, description="Supports audio output")
    supports_display: bool = Field(False, description="Has display capabilities")
    supports_account_linking: bool = Field(False, description="Supports account linking")
    supports_push_notifications: bool = Field(False, description="Supports push notifications")
    
    # Session management
    session_timeout_minutes: int = Field(15, description="Session timeout in minutes")
    max_session_attributes: int = Field(10, description="Max session attributes")
    
    # Speech settings
    default_language: str = Field("ru", description="Default language")
    supported_languages: list[str] = Field(
        default_factory=lambda: ["ru"], description="Supported languages"
    )
    
    # Response limits
    max_response_text_length: int = Field(8000, description="Max response text length")
    max_card_title_length: int = Field(200, description="Max card title length")
    max_card_text_length: int = Field(1000, description="Max card text length")
    
    # Rate limiting
    requests_per_minute: int = Field(60, description="Max requests per minute")
    max_concurrent_sessions: int = Field(100, description="Max concurrent sessions")


class VoiceIntentMapping(BaseModel):
    """Mapping between voice intents and business actions."""
    
    voice_intent: str = Field(..., description="Voice platform intent name")
    business_action: str = Field(..., description="Internal business action")
    required_entities: list[str] = Field(
        default_factory=list, description="Required entities for this intent"
    )
    confidence_threshold: float = Field(0.7, description="Minimum confidence for intent")
    
    # Response templates
    success_response: str | None = Field(None, description="Success response template")
    error_response: str | None = Field(None, description="Error response template")
    clarification_response: str | None = Field(None, description="Clarification request template")


class VoiceAnalytics(BaseModel):
    """Voice interaction analytics."""
    
    platform: VoicePlatform = Field(..., description="Voice platform")
    date: datetime = Field(default_factory=datetime.now)
    
    # Usage metrics
    total_requests: int = Field(0, description="Total requests")
    successful_requests: int = Field(0, description="Successful requests")
    failed_requests: int = Field(0, description="Failed requests")
    
    # Intent metrics
    intent_recognition_rate: float = Field(0.0, description="Intent recognition success rate")
    average_confidence: float = Field(0.0, description="Average intent confidence")
    
    # Session metrics
    total_sessions: int = Field(0, description="Total sessions")
    average_session_length_minutes: float = Field(0.0, description="Average session length")
    session_completion_rate: float = Field(0.0, description="Session completion rate")
    
    # Performance metrics
    average_response_time_ms: int = Field(0, description="Average response time")
    timeout_rate: float = Field(0.0, description="Request timeout rate")
    
    # Popular intents
    top_intents: list[dict[str, Any]] = Field(
        default_factory=list, description="Most popular intents with counts"
    )