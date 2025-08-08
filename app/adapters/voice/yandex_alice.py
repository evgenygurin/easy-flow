"""Yandex Alice voice assistant adapter."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any

import structlog

from app.adapters.voice.base import VoiceAdapter
from app.models.voice import (
    VoiceMessage,
    VoiceResponse,
    VoiceSession,
    VoicePlatform,
    VoiceMessageType,
    VoiceDirection,
    VoiceIntent,
    VoiceEntity,
    EntityType,
    VoiceCard,
    VoiceDirective,
    VoicePlatformConfig,
    VoiceSessionState
)


logger = structlog.get_logger()


class YandexAliceAdapter(VoiceAdapter):
    """Yandex Alice voice assistant adapter."""
    
    def __init__(self, config: VoicePlatformConfig, **kwargs):
        """Initialize Yandex Alice adapter.
        
        Args:
        ----
            config: Alice platform configuration
            **kwargs: Additional adapter arguments
        """
        super().__init__(config, **kwargs)
        
        # Alice-specific configuration validation
        required_creds = ["oauth_token"]
        missing_creds = [
            cred for cred in required_creds 
            if cred not in config.credentials
        ]
        
        if missing_creds:
            raise ValueError(f"Missing Alice credentials: {missing_creds}")
        
        self.oauth_token = config.credentials["oauth_token"]
        
        logger.info("Yandex Alice adapter initialized")
    
    async def process_voice_request(
        self,
        request_data: dict[str, Any],
        signature: str | None = None
    ) -> VoiceResponse:
        """Process Alice voice request.
        
        Args:
        ----
            request_data: Alice request payload
            signature: Request signature (if webhook verification enabled)
            
        Returns:
        -------
            VoiceResponse: Response for Alice
        """
        start_time = datetime.now()
        
        try:
            logger.info(
                "Processing Alice voice request",
                request_type=request_data.get("request", {}).get("type"),
                session_id=request_data.get("session", {}).get("session_id")
            )
            
            # Verify signature if required
            if self.config.verify_webhooks and signature:
                is_valid = await self.verify_request_signature(request_data, signature)
                if not is_valid:
                    raise ValueError("Invalid request signature")
            
            # Validate request format
            if not self._validate_alice_request(request_data):
                raise ValueError("Invalid Alice request format")
            
            # Extract voice message
            voice_message = await self.extract_voice_message(request_data)
            
            # Get or create session
            session = await self._get_or_create_session(request_data)
            
            # Process the message through business logic
            # This would integrate with ConversationService in full implementation
            response = await self._generate_response(voice_message, session)
            
            # Update session if needed
            await self._update_session_from_response(session, response)
            
            # Update analytics
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self._update_analytics(
                success=True,
                intent_confidence=voice_message.intent.confidence if voice_message.intent else None,
                response_time_ms=processing_time
            )
            
            logger.info(
                "Alice request processed successfully",
                session_id=session.session_id,
                processing_time_ms=processing_time
            )
            
            return response
            
        except Exception as e:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self._update_analytics(success=False, response_time_ms=processing_time)
            
            logger.error(
                "Failed to process Alice request",
                error=str(e),
                processing_time_ms=processing_time
            )
            
            # Return error response
            return VoiceResponse(
                text="Извините, произошла ошибка. Попробуйте ещё раз.",
                speech="Извините, произошла ошибка. Попробуйте ещё раз.",
                should_end_session=False
            )
    
    async def extract_voice_message(self, request_data: dict[str, Any]) -> VoiceMessage:
        """Extract voice message from Alice request.
        
        Args:
        ----
            request_data: Alice request data
            
        Returns:
        -------
            VoiceMessage: Unified voice message
        """
        request = request_data.get("request", {})
        session = request_data.get("session", {})
        
        # Extract intent and entities
        intent = None
        entities = []
        
        if "nlu" in request:
            nlu = request["nlu"]
            
            # Extract intent
            if "intents" in nlu and nlu["intents"]:
                # Get the highest confidence intent
                intent_data = max(
                    nlu["intents"].items(),
                    key=lambda x: x[1].get("slots", {}).get("confidence", 0.0)
                )
                
                intent = VoiceIntent(
                    name=intent_data[0],
                    confidence=intent_data[1].get("slots", {}).get("confidence", 0.0),
                    entities=intent_data[1].get("slots", {})
                )
            
            # Extract entities
            if "entities" in nlu:
                for entity_data in nlu["entities"]:
                    entity_type = self._map_alice_entity_type(entity_data.get("type"))
                    entities.append(VoiceEntity(
                        type=entity_type,
                        value=entity_data.get("value"),
                        confidence=entity_data.get("confidence", 1.0),
                        start_pos=entity_data.get("tokens", {}).get("start"),
                        end_pos=entity_data.get("tokens", {}).get("end")
                    ))
        
        # Create voice message
        voice_message = VoiceMessage(
            platform=VoicePlatform.YANDEX_ALICE,
            platform_message_id=request.get("request_id", ""),
            session_id=session.get("session_id", ""),
            user_id=session.get("user_id", ""),
            message_type=VoiceMessageType.TEXT if request.get("original_utterance") else VoiceMessageType.INTENT,
            direction=VoiceDirection.REQUEST,
            text=request.get("original_utterance"),
            intent=intent,
            entities=entities,
            metadata={
                "alice_request_type": request.get("type"),
                "alice_command": request.get("command"),
                "alice_session_new": session.get("new", False),
                "alice_application_id": session.get("application_id"),
                "alice_user": session.get("user", {}),
                "alice_interface": request_data.get("version", ""),
                "alice_timezone": request_data.get("meta", {}).get("timezone"),
                "alice_client_id": request_data.get("meta", {}).get("client_id")
            }
        )
        
        return voice_message
    
    async def format_voice_response(self, response: VoiceResponse) -> dict[str, Any]:
        """Format response for Alice.
        
        Args:
        ----
            response: Unified voice response
            
        Returns:
        -------
            dict[str, Any]: Alice-formatted response
        """
        alice_response = {
            "version": "1.0",
            "response": {
                "end_session": response.should_end_session
            }
        }
        
        # Add text response
        if response.text:
            alice_response["response"]["text"] = response.text[:self.config.max_response_text_length]
        
        # Add speech synthesis
        if response.speech:
            alice_response["response"]["tts"] = response.speech
        
        # Add card if present
        if response.card:
            card_data = {
                "type": "BigImage",
                "title": response.card.title[:self.config.max_card_title_length],
                "description": response.card.text[:self.config.max_card_text_length] if response.card.text else ""
            }
            
            if response.card.image_url:
                card_data["image_id"] = response.card.image_url
            
            # Add buttons
            if response.card.buttons:
                buttons = []
                for button in response.card.buttons[:5]:  # Alice supports up to 5 buttons
                    button_data = {
                        "title": button.get("title", "")[:64],  # Alice button title limit
                    }
                    
                    if button.get("url"):
                        button_data["url"] = button["url"]
                    elif button.get("payload"):
                        button_data["payload"] = button["payload"]
                    
                    buttons.append(button_data)
                
                card_data["buttons"] = buttons
            
            alice_response["response"]["card"] = card_data
        
        # Add Alice-specific directives
        if response.directives:
            for directive in response.directives:
                if directive.type == "alice_directive":
                    # Merge Alice-specific directive data into response
                    alice_response["response"].update(directive.payload)
        
        # Add session attributes
        if response.session_attributes:
            alice_response["session_state"] = {
                "user": response.session_attributes
            }
        
        # Add suggests (quick replies)
        if not response.should_end_session:
            suggests = self._get_context_suggests(response)
            if suggests:
                alice_response["response"]["buttons"] = suggests
        
        return alice_response
    
    async def verify_request_signature(
        self,
        request_data: dict[str, Any],
        signature: str
    ) -> bool:
        """Verify Alice request signature.
        
        Args:
        ----
            request_data: Request data
            signature: Request signature
            
        Returns:
        -------
            bool: Whether signature is valid
        """
        if not self.config.webhook_secret:
            logger.warning("Webhook secret not configured for Alice")
            return True
        
        try:
            # Alice uses HMAC-SHA256 for signature verification
            secret = self.config.webhook_secret.encode('utf-8')
            body = json.dumps(request_data, separators=(',', ':')).encode('utf-8')
            
            expected_signature = hmac.new(
                secret,
                body,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature.lower(), expected_signature.lower())
            
        except Exception as e:
            logger.error("Error verifying Alice signature", error=str(e))
            return False
    
    def _validate_alice_request(self, request_data: dict[str, Any]) -> bool:
        """Validate Alice request format.
        
        Args:
        ----
            request_data: Request data to validate
            
        Returns:
        -------
            bool: Whether request is valid
        """
        # Check required top-level fields
        required_fields = ["version", "session", "request"]
        if not all(field in request_data for field in required_fields):
            return False
        
        # Check session fields
        session = request_data.get("session", {})
        session_required = ["session_id", "user_id"]
        if not all(field in session for field in session_required):
            return False
        
        # Check request fields
        request = request_data.get("request", {})
        request_required = ["type"]
        if not all(field in request for field in request_required):
            return False
        
        return True
    
    async def _get_or_create_session(self, request_data: dict[str, Any]) -> VoiceSession:
        """Get existing session or create new one.
        
        Args:
        ----
            request_data: Alice request data
            
        Returns:
        -------
            VoiceSession: Voice session
        """
        session_data = request_data.get("session", {})
        session_id = session_data.get("session_id")
        user_id = session_data.get("user_id")
        is_new_session = session_data.get("new", False)
        
        if is_new_session or not session_id:
            # Create new session
            supports_display = self._has_display_capability(request_data)
            session = await self.create_session(
                session_id=session_id,
                user_id=user_id,
                supports_display=supports_display,
                supports_account_linking=False  # Alice doesn't support account linking yet
            )
        else:
            # Try to get existing session
            session = await self.get_session(session_id, user_id)
            if not session:
                # Session expired or not found, create new one
                session = await self.create_session(
                    session_id=session_id,
                    user_id=user_id,
                    supports_display=self._has_display_capability(request_data)
                )
        
        # Update last activity
        session.last_activity = datetime.now()
        await self.save_session(session)
        
        return session
    
    def _has_display_capability(self, request_data: dict[str, Any]) -> bool:
        """Check if Alice device has display capability.
        
        Args:
        ----
            request_data: Alice request data
            
        Returns:
        -------
            bool: Whether device has display
        """
        interfaces = request_data.get("meta", {}).get("interfaces", {})
        return "screen" in interfaces
    
    def _map_alice_entity_type(self, alice_type: str) -> EntityType:
        """Map Alice entity type to unified entity type.
        
        Args:
        ----
            alice_type: Alice entity type
            
        Returns:
        -------
            EntityType: Unified entity type
        """
        mapping = {
            "YANDEX.DATETIME": EntityType.DATE,
            "YANDEX.NUMBER": EntityType.CUSTOM,
            "YANDEX.GEO": EntityType.LOCATION,
            "YANDEX.FIO": EntityType.PERSON,
            "YANDEX.PHONE": EntityType.PHONE,
            "YANDEX.EMAIL": EntityType.EMAIL,
        }
        
        return mapping.get(alice_type, EntityType.CUSTOM)
    
    async def _generate_response(
        self,
        message: VoiceMessage,
        session: VoiceSession
    ) -> VoiceResponse:
        """Generate response for Alice request.
        
        This is a simplified implementation. In production, this would
        integrate with ConversationService and business logic.
        
        Args:
        ----
            message: Voice message
            session: Voice session
            
        Returns:
        -------
            VoiceResponse: Generated response
        """
        # Simple intent-based responses (placeholder implementation)
        if message.intent:
            intent_name = message.intent.name
            
            if intent_name == "order_status":
                return VoiceResponse(
                    text="Для проверки статуса заказа назовите номер заказа.",
                    speech="Для проверки статуса заказа назовите номер заказа.",
                    should_end_session=False,
                    session_attributes={"awaiting": "order_id"}
                )
            
            elif intent_name == "product_search":
                return VoiceResponse(
                    text="Что вы ищете? Назовите название товара.",
                    speech="Что вы ищете? Назовите название товара.",
                    should_end_session=False,
                    session_attributes={"awaiting": "product_name"}
                )
            
            elif intent_name == "help":
                card = VoiceCard(
                    title="Помощь",
                    text="Я могу помочь с заказами, поиском товаров и ответить на вопросы о доставке.",
                    buttons=[
                        {"title": "Статус заказа", "payload": "order_status"},
                        {"title": "Поиск товаров", "payload": "product_search"}
                    ]
                )
                
                return VoiceResponse(
                    text="Я могу помочь с заказами, поиском товаров и вопросами о доставке. Что вас интересует?",
                    speech="Я могу помочь с заказами, поиском товаров и вопросами о доставке. Что вас интересует?",
                    card=card,
                    should_end_session=False
                )
        
        # Handle text input based on session context
        if message.text and session.variables.get("awaiting"):
            awaiting = session.variables["awaiting"]
            
            if awaiting == "order_id":
                # Extract order ID and process
                order_id = self._extract_order_id(message.text)
                if order_id:
                    return VoiceResponse(
                        text=f"Заказ {order_id} обрабатывается. Ожидаемая дата доставки: завтра.",
                        speech=f"Заказ {order_id} обрабатывается. Ожидаемая дата доставки: завтра.",
                        should_end_session=True,
                        session_attributes={}
                    )
                else:
                    return VoiceResponse(
                        text="Не удалось распознать номер заказа. Попробуйте ещё раз.",
                        speech="Не удалось распознать номер заказа. Попробуйте ещё раз.",
                        should_end_session=False
                    )
        
        # Default response for unhandled cases
        return VoiceResponse(
            text="Здравствуйте! Я помощник интернет-магазина. Могу помочь с заказами и поиском товаров. Что вас интересует?",
            speech="Здравствуйте! Я помощник интернет-магазина. Могу помочь с заказами и поиском товаров. Что вас интересует?",
            should_end_session=False
        )
    
    def _extract_order_id(self, text: str) -> str | None:
        """Extract order ID from text.
        
        Args:
        ----
            text: Text to extract from
            
        Returns:
        -------
            str | None: Extracted order ID or None
        """
        import re
        
        # Simple regex for order ID pattern (digits)
        match = re.search(r'\b\d{6,10}\b', text)
        return match.group() if match else None
    
    def _get_context_suggests(self, response: VoiceResponse) -> list[dict[str, str]]:
        """Get context-appropriate suggestions for Alice.
        
        Args:
        ----
            response: Voice response
            
        Returns:
        -------
            list[dict[str, str]]: Suggestion buttons
        """
        # Default suggestions based on context
        suggests = [
            {"title": "Помощь", "payload": "help"},
            {"title": "Мои заказы", "payload": "my_orders"},
        ]
        
        return suggests[:3]  # Alice supports up to 3 suggests
    
    async def _update_session_from_response(
        self,
        session: VoiceSession,
        response: VoiceResponse
    ):
        """Update session based on response.
        
        Args:
        ----
            session: Voice session to update
            response: Voice response
        """
        # Update session attributes
        if response.session_attributes:
            session.variables.update(response.session_attributes)
        
        # End session if requested
        if response.should_end_session:
            session.state = VoiceSessionState.ENDED
            await self.end_session(session.session_id)
        else:
            session.last_activity = datetime.now()
            # Set expiration time
            session.ends_at = datetime.now() + timedelta(
                minutes=self.config.session_timeout_minutes
            )
            await self.save_session(session)