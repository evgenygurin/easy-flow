"""Unified messaging models for all messaging platforms."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Type of message content."""
    
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    LOCATION = "location"
    STICKER = "sticker"
    VOICE = "voice"
    CONTACT = "contact"
    POLL = "poll"
    COMMAND = "command"


class MessageDirection(str, Enum):
    """Direction of message flow."""
    
    INBOUND = "inbound"   # From user to bot
    OUTBOUND = "outbound"  # From bot to user


class DeliveryStatus(str, Enum):
    """Status of message delivery."""
    
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageAttachment(BaseModel):
    """Attachment in a message."""
    
    type: MessageType = Field(..., description="Type of attachment")
    url: str = Field(..., description="URL or file path to attachment")
    file_name: str | None = Field(None, description="Original file name")
    file_size: int | None = Field(None, description="File size in bytes")
    mime_type: str | None = Field(None, description="MIME type of the file")
    duration: int | None = Field(None, description="Duration for audio/video in seconds")
    width: int | None = Field(None, description="Width for images/videos")
    height: int | None = Field(None, description="Height for images/videos")


class InlineKeyboardButton(BaseModel):
    """Button in an inline keyboard."""
    
    text: str = Field(..., description="Button text")
    callback_data: str | None = Field(None, description="Callback data")
    url: str | None = Field(None, description="URL to open")
    switch_inline_query: str | None = Field(None, description="Switch to inline query")


class ReplyKeyboardButton(BaseModel):
    """Button in a reply keyboard."""
    
    text: str = Field(..., description="Button text")
    request_contact: bool = Field(False, description="Request user's contact")
    request_location: bool = Field(False, description="Request user's location")


class InlineKeyboard(BaseModel):
    """Inline keyboard markup."""
    
    buttons: list[list[InlineKeyboardButton]] = Field(
        ..., description="2D array of buttons"
    )


class ReplyKeyboard(BaseModel):
    """Reply keyboard markup."""
    
    buttons: list[list[ReplyKeyboardButton]] = Field(
        ..., description="2D array of buttons"
    )
    resize_keyboard: bool = Field(True, description="Resize keyboard to fit buttons")
    one_time_keyboard: bool = Field(False, description="Hide keyboard after use")
    selective: bool = Field(False, description="Show keyboard only to specific users")


class UnifiedMessage(BaseModel):
    """Unified message model for all messaging platforms."""
    
    # Core message fields
    message_id: str = Field(..., description="Unique message ID")
    platform: str = Field(..., description="Platform name (telegram, whatsapp, etc.)")
    platform_message_id: str = Field(..., description="Platform-specific message ID")
    
    # User information
    user_id: str = Field(..., description="Platform user ID")
    username: str | None = Field(None, description="Username if available")
    first_name: str | None = Field(None, description="User's first name")
    last_name: str | None = Field(None, description="User's last name")
    
    # Chat information
    chat_id: str = Field(..., description="Chat/conversation ID")
    chat_type: str = Field("private", description="Type of chat (private, group, channel)")
    
    # Message content
    message_type: MessageType = Field(MessageType.TEXT, description="Type of message")
    direction: MessageDirection = Field(..., description="Message direction")
    text: str | None = Field(None, description="Text content of message")
    attachments: list[MessageAttachment] = Field(
        default_factory=list, description="Message attachments"
    )
    
    # Keyboard markup
    inline_keyboard: InlineKeyboard | None = Field(
        None, description="Inline keyboard markup"
    )
    reply_keyboard: ReplyKeyboard | None = Field(
        None, description="Reply keyboard markup"
    )
    
    # Reply information
    reply_to_message_id: str | None = Field(
        None, description="ID of message this is replying to"
    )
    
    # Timestamps
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")
    platform_timestamp: datetime | None = Field(
        None, description="Platform's original timestamp"
    )
    
    # Metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Platform-specific metadata"
    )


class DeliveryResult(BaseModel):
    """Result of message delivery attempt."""
    
    message_id: str = Field(..., description="Unique message ID")
    platform: str = Field(..., description="Platform name")
    platform_message_id: str | None = Field(
        None, description="Platform-assigned message ID"
    )
    
    status: DeliveryStatus = Field(..., description="Delivery status")
    success: bool = Field(..., description="Whether delivery was successful")
    
    # Delivery details
    sent_at: datetime | None = Field(None, description="When message was sent")
    delivered_at: datetime | None = Field(None, description="When message was delivered")
    read_at: datetime | None = Field(None, description="When message was read")
    
    # Error information
    error_code: str | None = Field(None, description="Error code if delivery failed")
    error_message: str | None = Field(None, description="Error description")
    
    # Retry information
    retry_count: int = Field(0, description="Number of retry attempts")
    next_retry_at: datetime | None = Field(
        None, description="When to attempt next retry"
    )
    
    # Metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Platform-specific delivery metadata"
    )
    timestamp: datetime = Field(default_factory=datetime.now, description="Result timestamp")


class MessageQueue(BaseModel):
    """Queued message for processing."""
    
    queue_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Queue entry ID")
    message: UnifiedMessage = Field(..., description="Message to be processed")
    priority: int = Field(0, description="Message priority (higher = more priority)")
    
    # Processing state
    attempts: int = Field(0, description="Number of processing attempts")
    max_attempts: int = Field(3, description="Maximum retry attempts")
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.now, description="Queue creation time")
    scheduled_at: datetime = Field(default_factory=datetime.now, description="When to process")
    processed_at: datetime | None = Field(None, description="When message was processed")
    
    # Result
    result: DeliveryResult | None = Field(None, description="Processing result")
    
    # Tags for filtering/routing
    tags: list[str] = Field(default_factory=list, description="Message tags")


class ConversationContext(BaseModel):
    """Context for a conversation thread."""
    
    conversation_id: str = Field(..., description="Unique conversation ID")
    platform: str = Field(..., description="Platform name")
    user_id: str = Field(..., description="Platform user ID")
    chat_id: str = Field(..., description="Chat/conversation ID")
    
    # Conversation state
    state: str = Field("active", description="Conversation state")
    intent: str | None = Field(None, description="Detected user intent")
    language: str = Field("ru", description="Conversation language")
    
    # Context data
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Conversation variables"
    )
    
    # Message history (limited)
    recent_messages: list[str] = Field(
        default_factory=list, description="Recent message IDs for context"
    )
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.now, description="Conversation start")
    last_activity: datetime = Field(
        default_factory=datetime.now, description="Last message timestamp"
    )
    expires_at: datetime | None = Field(None, description="When conversation expires")
    
    # Flow control
    current_flow: str | None = Field(None, description="Current conversation flow")
    flow_step: str | None = Field(None, description="Current step in flow")
    
    # Escalation
    escalated: bool = Field(False, description="Whether escalated to human")
    escalated_at: datetime | None = Field(None, description="When escalated")
    operator_id: str | None = Field(None, description="Assigned operator ID")


class WebhookEvent(BaseModel):
    """Webhook event from messaging platform."""
    
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Event ID")
    platform: str = Field(..., description="Platform name")
    event_type: str = Field(..., description="Type of webhook event")
    
    # Timing
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    platform_timestamp: datetime | None = Field(
        None, description="Platform's event timestamp"
    )
    
    # Event data
    payload: dict[str, Any] = Field(..., description="Raw webhook payload")
    signature: str | None = Field(None, description="Webhook signature for verification")
    
    # Processing
    processed: bool = Field(False, description="Whether event was processed")
    processed_at: datetime | None = Field(None, description="When event was processed")
    
    # Extracted message (if applicable)
    message: UnifiedMessage | None = Field(
        None, description="Extracted unified message"
    )


class PlatformConfig(BaseModel):
    """Configuration for a messaging platform."""
    
    platform: str = Field(..., description="Platform name")
    enabled: bool = Field(True, description="Whether platform is enabled")
    
    # API configuration
    api_endpoint: str = Field(..., description="Platform API endpoint")
    webhook_url: str | None = Field(None, description="Webhook URL")
    
    # Authentication
    credentials: dict[str, str] = Field(..., description="Platform credentials")
    
    # Rate limiting
    rate_limit_per_second: int = Field(30, description="Messages per second limit")
    rate_limit_burst: int = Field(10, description="Burst limit")
    
    # Features
    supports_inline_keyboard: bool = Field(True, description="Supports inline keyboards")
    supports_reply_keyboard: bool = Field(True, description="Supports reply keyboards")
    supports_media: bool = Field(True, description="Supports media messages")
    supports_files: bool = Field(True, description="Supports file attachments")
    
    # Message limits
    max_text_length: int = Field(4096, description="Maximum text message length")
    max_file_size: int = Field(20 * 1024 * 1024, description="Maximum file size in bytes")
    
    # Retry configuration
    retry_attempts: int = Field(3, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(5, description="Base retry delay")
    
    # Webhook verification
    webhook_secret: str | None = Field(None, description="Webhook verification secret")
    verify_webhooks: bool = Field(True, description="Whether to verify webhook signatures")