"""Tests for messaging controller."""
import pytest
from unittest.mock import Mock, AsyncMock
from fastapi import HTTPException

from app.api.controllers.messaging_controller import (
    MessagingController,
    SendMessageRequest,
    SendMessageResponse,
    WebhookRequest,
    WebhookResponse
)
from app.models.messaging import MessageType, DeliveryResult, DeliveryStatus
from app.services.messaging_service import MessagingService


@pytest.fixture
def mock_messaging_service():
    """Mock messaging service."""
    return Mock(spec=MessagingService)


@pytest.fixture
def messaging_controller(mock_messaging_service):
    """Messaging controller with mocked service."""
    return MessagingController(messaging_service=mock_messaging_service)


class TestMessagingController:
    """Test cases for MessagingController."""

    async def test_send_message_success(self, messaging_controller, mock_messaging_service):
        """Test successful message sending."""
        # Arrange
        request = SendMessageRequest(
            platform="telegram",
            chat_id="123456",
            text="Hello, world!",
            message_type=MessageType.TEXT
        )
        
        mock_result = DeliveryResult(
            message_id="msg_123",
            platform_message_id="platform_msg_456",
            platform="telegram",
            status=DeliveryStatus.SENT,
            success=True,
            error_message=None
        )
        mock_messaging_service.send_message_from_request = AsyncMock(return_value=mock_result)
        
        # Act
        response = await messaging_controller.send_message(request)
        
        # Assert
        assert isinstance(response, SendMessageResponse)
        assert response.success is True
        assert response.message_id == "msg_123"
        assert response.platform_message_id == "platform_msg_456"
        assert response.delivery_status == DeliveryStatus.SENT.value
        assert response.error is None
        
        # Verify service was called correctly
        mock_messaging_service.send_message_from_request.assert_called_once_with(
            platform="telegram",
            chat_id="123456",
            text="Hello, world!",
            message_type=MessageType.TEXT,
            reply_to_message_id=None,
            inline_keyboard=None,
            reply_keyboard=None,
            priority=0
        )

    async def test_send_message_with_keyboards(self, messaging_controller, mock_messaging_service):
        """Test message sending with keyboards."""
        # Arrange
        inline_keyboard = {"inline_keyboard": [[{"text": "Button 1", "callback_data": "btn1"}]]}
        reply_keyboard = {"keyboard": [["Reply Button"]]}
        
        request = SendMessageRequest(
            platform="telegram",
            chat_id="123456",
            text="Choose an option:",
            inline_keyboard=inline_keyboard,
            reply_keyboard=reply_keyboard,
            priority=1
        )
        
        mock_result = DeliveryResult(
            message_id="msg_123",
            platform="telegram",
            status=DeliveryStatus.SENT,
            success=True
        )
        mock_messaging_service.send_message_from_request = AsyncMock(return_value=mock_result)
        
        # Act
        response = await messaging_controller.send_message(request)
        
        # Assert
        assert response.success is True
        mock_messaging_service.send_message_from_request.assert_called_once_with(
            platform="telegram",
            chat_id="123456",
            text="Choose an option:",
            message_type=MessageType.TEXT,
            reply_to_message_id=None,
            inline_keyboard=inline_keyboard,
            reply_keyboard=reply_keyboard,
            priority=1
        )

    async def test_send_message_validation_failure(self, messaging_controller, mock_messaging_service):
        """Test message sending with validation errors."""
        # Arrange
        request = SendMessageRequest(
            platform="",  # Empty platform should fail validation
            chat_id="123456",
            text="Hello, world!"
        )
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await messaging_controller.send_message(request)
        
        assert exc_info.value.status_code == 400
        assert "Platform name is required" in str(exc_info.value.detail)
        
        # Verify service was not called
        mock_messaging_service.send_message_from_request.assert_not_called()

    async def test_send_message_empty_chat_id(self, messaging_controller, mock_messaging_service):
        """Test message sending with empty chat ID."""
        # Arrange
        request = SendMessageRequest(
            platform="telegram",
            chat_id="",  # Empty chat ID should fail validation
            text="Hello, world!"
        )
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await messaging_controller.send_message(request)
        
        assert exc_info.value.status_code == 400
        assert "Chat ID is required" in str(exc_info.value.detail)

    async def test_send_message_empty_text_for_text_message(self, messaging_controller, mock_messaging_service):
        """Test text message sending with empty text."""
        # Arrange
        request = SendMessageRequest(
            platform="telegram",
            chat_id="123456",
            text="",  # Empty text for TEXT message should fail
            message_type=MessageType.TEXT
        )
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await messaging_controller.send_message(request)
        
        assert exc_info.value.status_code == 400
        assert "Text content is required" in str(exc_info.value.detail)

    async def test_send_message_service_failure(self, messaging_controller, mock_messaging_service):
        """Test message sending when service fails."""
        # Arrange
        request = SendMessageRequest(
            platform="telegram",
            chat_id="123456",
            text="Hello, world!"
        )
        
        mock_result = DeliveryResult(
            message_id="msg_123",
            platform="telegram",
            status=DeliveryStatus.FAILED,
            success=False,
            error_message="Network timeout"
        )
        mock_messaging_service.send_message_from_request = AsyncMock(return_value=mock_result)
        
        # Act
        response = await messaging_controller.send_message(request)
        
        # Assert
        assert response.success is False
        assert response.error == "Network timeout"
        assert response.delivery_status == DeliveryStatus.FAILED.value

    async def test_process_webhook_success(self, messaging_controller, mock_messaging_service):
        """Test successful webhook processing."""
        # Arrange
        webhook_request = WebhookRequest(
            platform="telegram",
            payload={"update_id": 123, "message": {"text": "Hello"}},
            signature="valid_signature"
        )
        
        from app.services.messaging_service import WebhookProcessingResult
        from app.models.messaging import UnifiedMessage, MessageDirection
        
        mock_messages = [
            UnifiedMessage(
                message_id="msg_123",
                platform="telegram",
                platform_message_id="456",
                user_id="user_789",
                chat_id="chat_123",
                text="Hello",
                message_type=MessageType.TEXT,
                direction=MessageDirection.INBOUND
            )
        ]
        
        mock_result = WebhookProcessingResult(
            event_id="event_123",
            platform="telegram",
            success=True,
            messages=mock_messages
        )
        mock_messaging_service.process_webhook = AsyncMock(return_value=mock_result)
        
        # Act
        response = await messaging_controller.process_webhook(webhook_request)
        
        # Assert
        assert isinstance(response, WebhookResponse)
        assert response.success is True
        assert response.messages_processed == 1
        assert response.event_id == "event_123"
        
        # Verify service was called correctly
        mock_messaging_service.process_webhook.assert_called_once_with(
            platform="telegram",
            payload={"update_id": 123, "message": {"text": "Hello"}},
            signature="valid_signature"
        )

    async def test_process_webhook_failure(self, messaging_controller, mock_messaging_service):
        """Test webhook processing failure."""
        # Arrange
        webhook_request = WebhookRequest(
            platform="telegram",
            payload={"invalid": "data"},
            signature="invalid_signature"
        )
        
        mock_messaging_service.process_webhook = AsyncMock(
            side_effect=ValueError("Invalid webhook signature")
        )
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await messaging_controller.process_webhook(webhook_request)
        
        assert exc_info.value.status_code == 500
        assert "Internal server error" in str(exc_info.value.detail).lower()

    def test_validate_send_message_request_valid(self, messaging_controller):
        """Test validation of valid send message request."""
        # Arrange
        request = SendMessageRequest(
            platform="telegram",
            chat_id="123456",
            text="Hello, world!",
            message_type=MessageType.TEXT
        )
        
        # Act
        result = messaging_controller._validate_send_message_request(request)
        
        # Assert
        assert result == request

    def test_validate_send_message_request_invalid_platform(self, messaging_controller):
        """Test validation with invalid platform."""
        # Arrange
        request = SendMessageRequest(
            platform="   ",  # Only whitespace
            chat_id="123456",
            text="Hello, world!"
        )
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            messaging_controller._validate_send_message_request(request)
        
        assert exc_info.value.status_code == 400
        assert "Platform name is required" in str(exc_info.value.detail)

    def test_validate_send_message_request_invalid_chat_id(self, messaging_controller):
        """Test validation with invalid chat ID."""
        # Arrange
        request = SendMessageRequest(
            platform="telegram",
            chat_id="   ",  # Only whitespace
            text="Hello, world!"
        )
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            messaging_controller._validate_send_message_request(request)
        
        assert exc_info.value.status_code == 400
        assert "Chat ID is required" in str(exc_info.value.detail)