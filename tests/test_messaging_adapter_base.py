"""Tests for messaging adapter base class."""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.adapters.messaging.base import MessagingAdapter, MessagingRateLimitConfig, MessageStats
from app.models.messaging import (
    UnifiedMessage,
    DeliveryResult,
    MessageType,
    MessageDirection,
    DeliveryStatus,
    PlatformConfig,
    ConversationContext
)


class TestMessagingAdapter(MessagingAdapter):
    """Concrete implementation of MessagingAdapter for testing."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._test_send_result = None
        self._test_webhook_messages = []
        self._test_context = None
        
    async def _send_platform_message(self, chat_id: str, message: UnifiedMessage) -> DeliveryResult:
        """Mock implementation."""
        if self._test_send_result:
            return self._test_send_result
        return DeliveryResult(
            message_id=message.message_id,
            platform_message_id=f"platform_{message.message_id}",
            platform=self.platform_name,
            status=DeliveryStatus.SENT,
            success=True,
            sent_at=datetime.now()
        )
    
    async def _extract_webhook_messages(self, payload: dict) -> list[UnifiedMessage]:
        """Mock implementation."""
        return self._test_webhook_messages
    
    async def _get_platform_conversation_context(self, chat_id: str, user_id: str) -> ConversationContext | None:
        """Mock implementation."""
        return self._test_context
    
    async def _update_platform_conversation_context(self, context: ConversationContext) -> bool:
        """Mock implementation."""
        return True
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Mock implementation."""
        return signature == "valid_signature"


@pytest.fixture
def platform_config():
    """Sample platform configuration."""
    return PlatformConfig(
        platform_name="test_platform",
        enabled=True,
        credentials={"token": "test_token"},
        webhook_secret="test_secret",
        webhook_url="https://example.com/webhook",
        verify_webhooks=True,
        max_text_length=4096,
        max_file_size=20971520,  # 20MB
        supports_inline_keyboard=True,
        supports_reply_keyboard=True,
        supports_media=True
    )


@pytest.fixture
def rate_limit_config():
    """Sample rate limit configuration."""
    return MessagingRateLimitConfig(
        messages_per_second=10,
        burst_size=5,
        per_chat_limit=2
    )


@pytest.fixture
def messaging_adapter(platform_config, rate_limit_config):
    """Test messaging adapter instance."""
    return TestMessagingAdapter(
        api_key="test_api_key",
        base_url="https://api.example.com",
        platform_name="test_platform",
        config=platform_config,
        rate_limit_config=rate_limit_config,
        timeout=10,
        max_retries=2
    )


@pytest.fixture
def sample_message():
    """Sample unified message."""
    return UnifiedMessage(
        message_id="msg_123",
        platform="test_platform",
        platform_message_id="",
        user_id="user_456",
        chat_id="chat_789",
        text="Hello, world!",
        message_type=MessageType.TEXT,
        direction=MessageDirection.OUTBOUND
    )


class TestMessagingAdapterBase:
    """Test cases for MessagingAdapter base class."""

    def test_initialization(self, messaging_adapter, platform_config, rate_limit_config):
        """Test adapter initialization."""
        assert messaging_adapter.platform_name == "test_platform"
        assert messaging_adapter.config == platform_config
        assert messaging_adapter.messaging_rate_config == rate_limit_config
        assert isinstance(messaging_adapter.stats, MessageStats)
        assert messaging_adapter.stats.platform == "test_platform"

    async def test_send_message_success(self, messaging_adapter, sample_message):
        """Test successful message sending."""
        # Act
        result = await messaging_adapter.send_message("chat_789", sample_message)
        
        # Assert
        assert result.success is True
        assert result.message_id == "msg_123"
        assert result.platform_message_id == f"platform_{sample_message.message_id}"
        assert result.platform == "test_platform"
        assert result.status == DeliveryStatus.SENT
        
        # Check stats updated
        assert messaging_adapter.stats.total_sent == 1
        assert messaging_adapter.stats.total_failed == 0

    async def test_send_message_failure(self, messaging_adapter, sample_message):
        """Test message sending failure."""
        # Arrange
        messaging_adapter._test_send_result = DeliveryResult(
            message_id="msg_123",
            platform="test_platform",
            status=DeliveryStatus.FAILED,
            success=False,
            error_message="Network error"
        )
        
        # Act
        result = await messaging_adapter.send_message("chat_789", sample_message)
        
        # Assert
        assert result.success is False
        assert result.error_message == "Network error"
        
        # Check stats updated
        assert messaging_adapter.stats.total_sent == 0
        assert messaging_adapter.stats.total_failed == 1

    async def test_send_message_exception_handling(self, messaging_adapter, sample_message):
        """Test message sending with exception."""
        # Arrange
        async def failing_send(*args, **kwargs):
            raise Exception("Unexpected error")
        
        messaging_adapter._send_platform_message = failing_send
        
        # Act
        result = await messaging_adapter.send_message("chat_789", sample_message)
        
        # Assert
        assert result.success is False
        assert "Failed to send message: Unexpected error" in result.error_message
        assert messaging_adapter.stats.total_failed == 1

    def test_check_chat_rate_limit(self, messaging_adapter):
        """Test per-chat rate limiting."""
        chat_id = "test_chat"
        
        # Should be able to send within limit
        assert messaging_adapter._check_chat_rate_limit(chat_id) is True
        
        # Add timestamps to simulate recent messages
        current_time = time.time()
        messaging_adapter._per_chat_timers[chat_id] = [
            current_time - 0.1,  # Recent message
            current_time - 0.2   # Another recent message
        ]
        
        # Should hit rate limit (per_chat_limit = 2)
        assert messaging_adapter._check_chat_rate_limit(chat_id) is False
        
        # Old timestamps should be cleaned up
        messaging_adapter._per_chat_timers[chat_id] = [
            current_time - 2.0,  # Old message (> 1 second)
            current_time - 0.1   # Recent message
        ]
        assert messaging_adapter._check_chat_rate_limit(chat_id) is True

    async def test_wait_for_chat_rate_limit(self, messaging_adapter):
        """Test waiting for chat rate limit."""
        chat_id = "test_chat"
        
        # Fill up rate limit
        current_time = time.time()
        messaging_adapter._per_chat_timers[chat_id] = [
            current_time - 0.1,
            current_time - 0.2
        ]
        
        # Mock the time to pass quickly
        with patch('time.time') as mock_time:
            mock_time.side_effect = [
                current_time,           # First check
                current_time + 0.1,     # Still rate limited
                current_time + 1.5      # Rate limit cleared
            ]
            
            start_time = time.time()
            await messaging_adapter._wait_for_chat_rate_limit(chat_id)
            # Should have waited briefly
            assert time.time() - start_time < 0.5

    async def test_receive_webhook_success(self, messaging_adapter):
        """Test successful webhook processing."""
        # Arrange
        payload = {"update_id": 123, "message": {"text": "Hello"}}
        signature = "valid_signature"
        
        test_message = UnifiedMessage(
            message_id="webhook_msg_123",
            platform="test_platform",
            platform_message_id="456",
            user_id="user_789",
            chat_id="chat_123",
            text="Hello",
            message_type=MessageType.TEXT,
            direction=MessageDirection.INBOUND
        )
        messaging_adapter._test_webhook_messages = [test_message]
        
        # Act
        messages = await messaging_adapter.receive_webhook(payload, signature)
        
        # Assert
        assert len(messages) == 1
        assert messages[0].text == "Hello"
        assert messages[0].direction == MessageDirection.INBOUND
        assert messaging_adapter.stats.total_received == 1

    async def test_receive_webhook_invalid_signature(self, messaging_adapter):
        """Test webhook processing with invalid signature."""
        # Arrange
        payload = {"update_id": 123, "message": {"text": "Hello"}}
        signature = "invalid_signature"
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid webhook signature"):
            await messaging_adapter.receive_webhook(payload, signature)

    async def test_receive_webhook_no_signature_verification(self, messaging_adapter):
        """Test webhook processing without signature verification."""
        # Arrange
        messaging_adapter.config.verify_webhooks = False
        payload = {"update_id": 123, "message": {"text": "Hello"}}
        
        test_message = UnifiedMessage(
            message_id="webhook_msg_123",
            platform="test_platform",
            platform_message_id="456",
            user_id="user_789",
            chat_id="chat_123",
            text="Hello",
            message_type=MessageType.TEXT,
            direction=MessageDirection.INBOUND
        )
        messaging_adapter._test_webhook_messages = [test_message]
        
        # Act
        messages = await messaging_adapter.receive_webhook(payload, None)
        
        # Assert
        assert len(messages) == 1
        assert messages[0].text == "Hello"

    async def test_receive_webhook_processing_failure(self, messaging_adapter):
        """Test webhook processing with extraction failure."""
        # Arrange
        payload = {"invalid": "data"}
        signature = "valid_signature"
        
        async def failing_extract(*args):
            raise ValueError("Failed to extract messages")
        
        messaging_adapter._extract_webhook_messages = failing_extract
        
        # Act & Assert
        with pytest.raises(ValueError, match="Failed to extract messages"):
            await messaging_adapter.receive_webhook(payload, signature)

    def test_validate_outgoing_message_success(self, messaging_adapter, sample_message):
        """Test successful message validation."""
        # Should not raise any exception
        messaging_adapter._validate_outgoing_message(sample_message)

    def test_validate_outgoing_message_text_too_long(self, messaging_adapter, sample_message):
        """Test message validation with text too long."""
        # Arrange
        sample_message.text = "x" * 5000  # Longer than max_text_length (4096)
        
        # Act & Assert
        with pytest.raises(ValueError, match="Message text too long"):
            messaging_adapter._validate_outgoing_message(sample_message)

    def test_validate_outgoing_message_file_too_large(self, messaging_adapter, sample_message):
        """Test message validation with file too large."""
        # Arrange
        from app.models.messaging import MessageAttachment
        large_attachment = MessageAttachment(
            file_id="file_123",
            file_name="large_file.pdf",
            file_size=30000000,  # 30MB, larger than max_file_size (20MB)
            content_type="application/pdf",
            file_url="https://example.com/file.pdf"
        )
        sample_message.attachments = [large_attachment]
        
        # Act & Assert
        with pytest.raises(ValueError, match="Attachment too large"):
            messaging_adapter._validate_outgoing_message(sample_message)

    def test_validate_outgoing_message_unsupported_inline_keyboard(self, messaging_adapter, sample_message):
        """Test message validation with unsupported inline keyboard."""
        # Arrange
        messaging_adapter.config.supports_inline_keyboard = False
        from app.models.messaging import InlineKeyboard, InlineKeyboardButton
        sample_message.inline_keyboard = InlineKeyboard(
            keyboard=[[InlineKeyboardButton(text="Button", callback_data="data")]]
        )
        
        # Act & Assert
        with pytest.raises(ValueError, match="does not support inline keyboards"):
            messaging_adapter._validate_outgoing_message(sample_message)

    async def test_get_conversation_context(self, messaging_adapter):
        """Test getting conversation context."""
        # Arrange
        test_context = ConversationContext(
            platform="test_platform",
            chat_id="chat_123",
            user_id="user_456",
            context_data={"last_intent": "greeting"},
            updated_at=datetime.now()
        )
        messaging_adapter._test_context = test_context
        
        # Act
        result = await messaging_adapter.get_conversation_context("chat_123", "user_456")
        
        # Assert
        assert result == test_context
        assert result.context_data["last_intent"] == "greeting"

    async def test_update_conversation_context(self, messaging_adapter):
        """Test updating conversation context."""
        # Arrange
        context = ConversationContext(
            platform="test_platform",
            chat_id="chat_123",
            user_id="user_456",
            context_data={"last_intent": "order_status"},
            updated_at=datetime.now()
        )
        
        # Act
        result = await messaging_adapter.update_conversation_context(context)
        
        # Assert
        assert result is True

    async def test_get_message_stats(self, messaging_adapter):
        """Test getting message statistics."""
        # Arrange
        messaging_adapter.stats.total_sent = 100
        messaging_adapter.stats.total_failed = 5
        messaging_adapter.stats.success_rate = 95.0
        
        # Act
        stats = await messaging_adapter.get_message_stats()
        
        # Assert
        assert stats.total_sent == 100
        assert stats.total_failed == 5
        assert stats.success_rate == 95.0
        assert stats.platform == "test_platform"

    async def test_test_connection_success(self, messaging_adapter):
        """Test successful connection test."""
        # Arrange
        with patch.object(messaging_adapter, '_make_request') as mock_request:
            from app.adapters.base import APIResponse
            mock_request.return_value = APIResponse(
                success=True,
                data={"ok": True},
                status_code=200,
                platform="test_platform"
            )
            
            # Act
            result = await messaging_adapter.test_connection()
            
            # Assert
            assert result.success is True
            assert result.status_code == 200

    async def test_handle_webhook_success(self, messaging_adapter):
        """Test webhook handling."""
        # Arrange
        payload = {"test": "data"}
        test_message = UnifiedMessage(
            message_id="msg_123",
            platform="test_platform",
            platform_message_id="456",
            user_id="user_789",
            chat_id="chat_123",
            text="Test",
            message_type=MessageType.TEXT,
            direction=MessageDirection.INBOUND
        )
        messaging_adapter._test_webhook_messages = [test_message]
        
        # Act
        result = await messaging_adapter.handle_webhook(payload, "valid_signature")
        
        # Assert
        assert result is True

    async def test_handle_webhook_failure(self, messaging_adapter):
        """Test webhook handling failure."""
        # Arrange
        async def failing_receive(*args):
            raise ValueError("Webhook processing failed")
        
        messaging_adapter.receive_webhook = failing_receive
        
        # Act
        result = await messaging_adapter.handle_webhook({}, "signature")
        
        # Assert
        assert result is False