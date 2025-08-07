"""Tests for messaging service."""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from app.services.messaging_service import MessagingService, WebhookProcessingResult
from app.models.messaging import (
    UnifiedMessage, 
    DeliveryResult, 
    MessageType, 
    MessageDirection, 
    DeliveryStatus,
    PlatformConfig
)
from app.adapters.messaging.base import MessagingAdapter
from app.repositories.interfaces.integration_repository import IntegrationRepository


@pytest.fixture
def mock_integration_repository():
    """Mock integration repository."""
    return Mock(spec=IntegrationRepository)


@pytest.fixture
def messaging_service(mock_integration_repository):
    """Messaging service with mocked dependencies."""
    return MessagingService(integration_repository=mock_integration_repository)


@pytest.fixture
def mock_telegram_adapter():
    """Mock Telegram adapter."""
    adapter = Mock(spec=MessagingAdapter)
    adapter.send_message = AsyncMock()
    adapter.receive_webhook = AsyncMock()
    adapter.get_message_stats = AsyncMock()
    return adapter


@pytest.fixture
def sample_unified_message():
    """Sample unified message for testing."""
    return UnifiedMessage(
        message_id="msg_123",
        platform="telegram",
        platform_message_id="",
        user_id="user_456",
        chat_id="chat_789",
        text="Hello, world!",
        message_type=MessageType.TEXT,
        direction=MessageDirection.OUTBOUND
    )


class TestMessagingService:
    """Test cases for MessagingService."""

    async def test_register_platform_success(self, messaging_service):
        """Test successful platform registration."""
        # Arrange
        config = PlatformConfig(
            platform_name="telegram",
            enabled=True,
            credentials={"bot_token": "test_token"},
            webhook_secret="secret123",
            webhook_url="https://example.com/webhook",
            retry_attempts=3
        )
        
        # Act
        result = await messaging_service.register_platform("telegram", config)
        
        # Assert
        assert result is True
        assert "telegram" in messaging_service._platform_configs
        assert "telegram" in messaging_service._adapters

    async def test_register_platform_missing_credentials(self, messaging_service):
        """Test platform registration with missing credentials."""
        # Arrange
        config = PlatformConfig(
            platform_name="telegram",
            enabled=True,
            credentials={},  # Missing bot_token
            webhook_secret="secret123",
            webhook_url="https://example.com/webhook"
        )
        
        # Act
        result = await messaging_service.register_platform("telegram", config)
        
        # Assert
        assert result is False
        assert "telegram" not in messaging_service._adapters

    async def test_send_message_success(self, messaging_service, mock_telegram_adapter, sample_unified_message):
        """Test successful message sending."""
        # Arrange
        messaging_service._adapters["telegram"] = mock_telegram_adapter
        
        expected_result = DeliveryResult(
            message_id="msg_123",
            platform_message_id="tg_456",
            platform="telegram",
            status=DeliveryStatus.SENT,
            success=True,
            sent_at=datetime.now()
        )
        mock_telegram_adapter.send_message.return_value = expected_result
        
        # Act
        result = await messaging_service.send_message(
            platform="telegram",
            chat_id="chat_789",
            message=sample_unified_message,
            priority=0
        )
        
        # Assert
        assert result.success is True
        assert result.message_id == "msg_123"
        assert result.platform_message_id == "tg_456"
        
        # Verify adapter was called correctly
        mock_telegram_adapter.send_message.assert_called_once_with("chat_789", sample_unified_message, 0)

    async def test_send_message_platform_not_registered(self, messaging_service, sample_unified_message):
        """Test sending message to unregistered platform."""
        # Act
        result = await messaging_service.send_message(
            platform="unknown_platform",
            chat_id="chat_789",
            message=sample_unified_message
        )
        
        # Assert
        assert result.success is False
        assert "not registered" in result.error_message

    async def test_send_message_platform_mismatch(self, messaging_service, mock_telegram_adapter):
        """Test message sending with platform mismatch correction."""
        # Arrange
        messaging_service._adapters["telegram"] = mock_telegram_adapter
        
        message = UnifiedMessage(
            message_id="msg_123",
            platform="whatsapp",  # Different platform
            platform_message_id="",
            user_id="user_456",
            chat_id="chat_789",
            text="Hello, world!",
            message_type=MessageType.TEXT,
            direction=MessageDirection.OUTBOUND
        )
        
        expected_result = DeliveryResult(
            message_id="msg_123",
            platform="telegram",
            status=DeliveryStatus.SENT,
            success=True
        )
        mock_telegram_adapter.send_message.return_value = expected_result
        
        # Act
        result = await messaging_service.send_message(
            platform="telegram",
            chat_id="chat_789",
            message=message
        )
        
        # Assert
        assert result.success is True
        assert message.platform == "telegram"  # Should be corrected

    async def test_send_message_from_request_success(self, messaging_service, mock_telegram_adapter):
        """Test successful message sending from request."""
        # Arrange
        messaging_service._adapters["telegram"] = mock_telegram_adapter
        
        expected_result = DeliveryResult(
            message_id="msg_123",
            platform="telegram",
            status=DeliveryStatus.SENT,
            success=True
        )
        mock_telegram_adapter.send_message.return_value = expected_result
        
        # Act
        result = await messaging_service.send_message_from_request(
            platform="telegram",
            chat_id="chat_789",
            text="Hello, world!",
            message_type=MessageType.TEXT,
            priority=1
        )
        
        # Assert
        assert result.success is True
        assert result.message_id == "msg_123"
        
        # Verify adapter was called
        mock_telegram_adapter.send_message.assert_called_once()
        call_args = mock_telegram_adapter.send_message.call_args
        assert call_args[0][0] == "chat_789"  # chat_id
        assert call_args[0][2] == 1  # priority
        
        # Verify message was created correctly
        message_arg = call_args[0][1]  # UnifiedMessage
        assert message_arg.platform == "telegram"
        assert message_arg.text == "Hello, world!"
        assert message_arg.message_type == MessageType.TEXT
        assert message_arg.user_id == "system"

    async def test_send_message_from_request_validation_errors(self, messaging_service):
        """Test message sending from request with validation errors."""
        # Test empty platform
        result = await messaging_service.send_message_from_request(
            platform="",
            chat_id="chat_789",
            text="Hello"
        )
        assert result.success is False
        assert "Platform name is required" in result.error_message
        
        # Test empty chat_id
        result = await messaging_service.send_message_from_request(
            platform="telegram",
            chat_id="",
            text="Hello"
        )
        assert result.success is False
        assert "Chat ID is required" in result.error_message
        
        # Test empty text for text message
        result = await messaging_service.send_message_from_request(
            platform="telegram",
            chat_id="chat_789",
            text="",
            message_type=MessageType.TEXT
        )
        assert result.success is False
        assert "Text content is required" in result.error_message

    async def test_process_webhook_success(self, messaging_service, mock_telegram_adapter):
        """Test successful webhook processing."""
        # Arrange
        messaging_service._adapters["telegram"] = mock_telegram_adapter
        
        payload = {
            "update_id": 123,
            "message": {
                "message_id": 456,
                "from": {"id": 789, "username": "testuser"},
                "chat": {"id": 123456},
                "text": "Hello from webhook"
            }
        }
        
        mock_messages = [
            UnifiedMessage(
                message_id="msg_webhook_123",
                platform="telegram",
                platform_message_id="456",
                user_id="789",
                chat_id="123456",
                text="Hello from webhook",
                message_type=MessageType.TEXT,
                direction=MessageDirection.INBOUND
            )
        ]
        mock_telegram_adapter.receive_webhook.return_value = mock_messages
        
        # Act
        result = await messaging_service.process_webhook(
            platform="telegram",
            payload=payload,
            signature="valid_signature"
        )
        
        # Assert
        assert isinstance(result, WebhookProcessingResult)
        assert result.success is True
        assert result.platform == "telegram"
        assert len(result.messages) == 1
        assert result.messages[0].text == "Hello from webhook"
        
        # Verify adapter was called correctly
        mock_telegram_adapter.receive_webhook.assert_called_once_with(payload, "valid_signature")

    async def test_process_webhook_platform_not_registered(self, messaging_service):
        """Test webhook processing for unregistered platform."""
        # Act
        result = await messaging_service.process_webhook(
            platform="unknown_platform",
            payload={"test": "data"}
        )
        
        # Assert
        assert result.success is False
        assert "not registered" in result.error

    async def test_process_webhook_adapter_failure(self, messaging_service, mock_telegram_adapter):
        """Test webhook processing when adapter fails."""
        # Arrange
        messaging_service._adapters["telegram"] = mock_telegram_adapter
        mock_telegram_adapter.receive_webhook.side_effect = ValueError("Invalid webhook data")
        
        # Act
        result = await messaging_service.process_webhook(
            platform="telegram",
            payload={"invalid": "data"}
        )
        
        # Assert
        assert result.success is False
        assert "Invalid webhook data" in result.error

    def test_get_supported_platforms(self, messaging_service, mock_telegram_adapter):
        """Test getting list of supported platforms."""
        # Arrange
        messaging_service._adapters["telegram"] = mock_telegram_adapter
        messaging_service._adapters["whatsapp"] = Mock()
        
        # Act
        platforms = messaging_service.get_supported_platforms()
        
        # Assert
        assert "telegram" in platforms
        assert "whatsapp" in platforms
        assert len(platforms) == 2

    async def test_get_platform_stats(self, messaging_service, mock_telegram_adapter):
        """Test getting platform statistics."""
        # Arrange
        messaging_service._adapters["telegram"] = mock_telegram_adapter
        
        from app.adapters.messaging.base import MessageStats
        mock_stats = MessageStats(
            platform="telegram",
            total_sent=100,
            total_received=50,
            total_failed=5,
            success_rate=95.0
        )
        mock_telegram_adapter.get_message_stats.return_value = mock_stats
        
        # Act
        stats = await messaging_service.get_platform_stats("telegram")
        
        # Assert
        assert stats is not None
        assert stats.platform == "telegram"
        assert stats.total_sent == 100
        assert stats.success_rate == 95.0

    async def test_get_platform_stats_platform_not_found(self, messaging_service):
        """Test getting stats for non-existent platform."""
        # Act
        stats = await messaging_service.get_platform_stats("unknown_platform")
        
        # Assert
        assert stats is None

    def test_create_messaging_adapter_telegram(self, messaging_service):
        """Test creating Telegram adapter."""
        # Arrange
        config = PlatformConfig(
            platform_name="telegram",
            enabled=True,
            credentials={"bot_token": "test_token"},
            webhook_secret="secret123",
            webhook_url="https://example.com/webhook",
            retry_attempts=3
        )
        
        # Act
        adapter = messaging_service._create_messaging_adapter("telegram", config)
        
        # Assert
        assert adapter is not None
        assert adapter.platform_name == "telegram"

    def test_create_messaging_adapter_whatsapp(self, messaging_service):
        """Test creating WhatsApp adapter."""
        # Arrange
        config = PlatformConfig(
            platform_name="whatsapp",
            enabled=True,
            credentials={
                "access_token": "test_token",
                "phone_number_id": "1234567890"
            },
            webhook_secret="secret123",
            webhook_url="https://example.com/webhook"
        )
        
        # Act
        adapter = messaging_service._create_messaging_adapter("whatsapp", config)
        
        # Assert
        assert adapter is not None
        assert adapter.platform_name == "whatsapp"

    def test_create_messaging_adapter_unsupported_platform(self, messaging_service):
        """Test creating adapter for unsupported platform."""
        # Arrange
        config = PlatformConfig(
            platform_name="unknown_platform",
            enabled=True,
            credentials={"token": "test"}
        )
        
        # Act
        adapter = messaging_service._create_messaging_adapter("unknown_platform", config)
        
        # Assert
        assert adapter is None