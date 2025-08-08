"""Voice assistant service for business logic."""
import uuid
from datetime import datetime
from typing import Any

import structlog

from app.adapters.voice.base import VoiceAdapter
from app.adapters.voice.yandex_alice import YandexAliceAdapter
from app.models.voice import (
    VoiceMessage,
    VoiceResponse,
    VoiceSession,
    VoicePlatform,
    VoicePlatformConfig,
    VoiceProcessingResult,
    VoiceWebhookEvent,
    VoiceAnalytics,
    VoiceIntentMapping
)
from app.repositories.interfaces.integration_repository import IntegrationRepository


logger = structlog.get_logger()


class VoiceWebhookProcessingResult:
    """Result of voice webhook processing."""
    
    def __init__(
        self,
        event_id: str,
        platform: VoicePlatform,
        success: bool,
        response: dict[str, Any] | None = None,
        error: str | None = None
    ):
        self.event_id = event_id
        self.platform = platform
        self.success = success
        self.response = response
        self.error = error


class VoiceService:
    """Service for voice assistant business logic."""
    
    def __init__(self, integration_repository: IntegrationRepository):
        """Initialize voice service.
        
        Args:
        ----
            integration_repository: Repository for integration data
        """
        self.integration_repository = integration_repository
        self._adapters: dict[VoicePlatform, VoiceAdapter] = {}
        self._platform_configs: dict[VoicePlatform, VoicePlatformConfig] = {}
        self._intent_mappings: dict[str, VoiceIntentMapping] = {}
        
        logger.info("Voice service initialized")
    
    async def register_platform(
        self,
        platform: VoicePlatform,
        config: VoicePlatformConfig
    ) -> bool:
        """Register a voice platform.
        
        Args:
        ----
            platform: Voice platform
            config: Platform configuration
            
        Returns:
        -------
            bool: Whether registration was successful
        """
        try:
            # Store platform configuration
            self._platform_configs[platform] = config
            
            # Create and register adapter
            adapter = await self._create_adapter(platform, config)
            if adapter:
                self._adapters[platform] = adapter
                logger.info("Voice platform registered", platform=platform.value)
                return True
            
            return False
            
        except Exception as e:
            logger.error(
                "Failed to register voice platform",
                platform=platform.value,
                error=str(e)
            )
            return False
    
    async def _create_adapter(
        self,
        platform: VoicePlatform,
        config: VoicePlatformConfig
    ) -> VoiceAdapter | None:
        """Create platform-specific adapter.
        
        Args:
        ----
            platform: Voice platform
            config: Platform configuration
            
        Returns:
        -------
            VoiceAdapter | None: Created adapter or None if failed
        """
        try:
            if platform == VoicePlatform.YANDEX_ALICE:
                return YandexAliceAdapter(config)
            
            # Future implementations:
            # elif platform == VoicePlatform.AMAZON_ALEXA:
            #     return AlexaAdapter(config)
            # elif platform == VoicePlatform.GOOGLE_ASSISTANT:
            #     return GoogleAssistantAdapter(config)
            # elif platform == VoicePlatform.APPLE_SIRI:
            #     return SiriAdapter(config)
            
            else:
                logger.warning("Unsupported voice platform", platform=platform.value)
                return None
                
        except Exception as e:
            logger.error(
                "Failed to create voice adapter",
                platform=platform.value,
                error=str(e)
            )
            return None
    
    async def process_voice_webhook(
        self,
        platform: VoicePlatform,
        request_data: dict[str, Any],
        signature: str | None = None
    ) -> VoiceWebhookProcessingResult:
        """Process voice webhook from platform.
        
        Args:
        ----
            platform: Voice platform
            request_data: Webhook request data
            signature: Request signature for verification
            
        Returns:
        -------
            VoiceWebhookProcessingResult: Processing result
        """
        event_id = str(uuid.uuid4())
        
        try:
            logger.info(
                "Processing voice webhook",
                platform=platform.value,
                event_id=event_id,
                has_signature=signature is not None
            )
            
            # Get platform adapter
            adapter = self._adapters.get(platform)
            if not adapter:
                raise ValueError(f"Voice platform {platform.value} not registered")
            
            # Process request through adapter
            voice_response = await adapter.process_voice_request(request_data, signature)
            
            # Format response for platform
            formatted_response = await adapter.format_voice_response(voice_response)
            
            logger.info(
                "Voice webhook processed successfully",
                platform=platform.value,
                event_id=event_id,
                should_end_session=voice_response.should_end_session
            )
            
            return VoiceWebhookProcessingResult(
                event_id=event_id,
                platform=platform,
                success=True,
                response=formatted_response
            )
            
        except Exception as e:
            error_msg = f"Failed to process voice webhook: {str(e)}"
            logger.error(
                "Voice webhook processing failed",
                platform=platform.value,
                event_id=event_id,
                error=error_msg
            )
            
            return VoiceWebhookProcessingResult(
                event_id=event_id,
                platform=platform,
                success=False,
                error=error_msg
            )
    
    async def process_voice_message(
        self,
        platform: VoicePlatform,
        message: VoiceMessage,
        session: VoiceSession
    ) -> VoiceProcessingResult:
        """Process voice message through business logic.
        
        This method handles the core business logic for voice interactions,
        including intent recognition, entity extraction, and response generation.
        
        Args:
        ----
            platform: Voice platform
            message: Voice message to process
            session: Voice session context
            
        Returns:
        -------
            VoiceProcessingResult: Processing result with response
        """
        try:
            logger.info(
                "Processing voice message",
                platform=platform.value,
                session_id=session.session_id,
                intent=message.intent.name if message.intent else None,
                message_type=message.message_type.value
            )
            
            # Map voice intent to business action
            business_action = None
            if message.intent:
                mapping = self._intent_mappings.get(message.intent.name)
                if mapping and message.intent.confidence >= mapping.confidence_threshold:
                    business_action = mapping.business_action
            
            # Generate response based on business logic
            response = await self._generate_business_response(
                message, session, business_action
            )
            
            # Update session context if needed
            session_updated = await self._update_session_context(session, message, response)
            
            logger.info(
                "Voice message processed",
                platform=platform.value,
                session_id=session.session_id,
                business_action=business_action,
                session_updated=session_updated
            )
            
            return VoiceProcessingResult(
                success=True,
                response=response,
                intent_confidence=message.intent.confidence if message.intent else None,
                session_updated=session_updated,
                flow_changed=session.current_flow is not None
            )
            
        except Exception as e:
            logger.error(
                "Failed to process voice message",
                platform=platform.value,
                session_id=session.session_id,
                error=str(e)
            )
            
            return VoiceProcessingResult(
                success=False,
                error=f"Failed to process voice message: {str(e)}"
            )
    
    async def _generate_business_response(
        self,
        message: VoiceMessage,
        session: VoiceSession,
        business_action: str | None
    ) -> VoiceResponse:
        """Generate response based on business logic.
        
        This is where the main business logic for voice interactions
        would be implemented, including integration with:
        - Order management system
        - Product catalog
        - Customer service flows
        - Payment processing
        
        Args:
        ----
            message: Voice message
            session: Voice session
            business_action: Mapped business action
            
        Returns:
        -------
            VoiceResponse: Generated response
        """
        # This is a simplified implementation
        # In production, this would integrate with ConversationService,
        # OrderService, ProductService, etc.
        
        if business_action == "check_order_status":
            return await self._handle_order_status_inquiry(message, session)
        elif business_action == "search_products":
            return await self._handle_product_search(message, session)
        elif business_action == "add_to_cart":
            return await self._handle_add_to_cart(message, session)
        elif business_action == "initiate_payment":
            return await self._handle_payment_initiation(message, session)
        elif business_action == "get_help":
            return await self._handle_help_request(message, session)
        else:
            return await self._handle_unknown_request(message, session)
    
    async def _handle_order_status_inquiry(
        self,
        message: VoiceMessage,
        session: VoiceSession
    ) -> VoiceResponse:
        """Handle order status inquiry.
        
        Args:
        ----
            message: Voice message
            session: Voice session
            
        Returns:
        -------
            VoiceResponse: Order status response
        """
        # Extract order ID from entities or session context
        order_id = None
        for entity in message.entities:
            if entity.type.value == "order_id":
                order_id = entity.value
                break
        
        if not order_id and "order_id" in session.variables:
            order_id = session.variables["order_id"]
        
        if order_id:
            # In production: query order management system
            response_text = f"Заказ {order_id} находится в обработке. Ожидаемая дата доставки: завтра."
            
            return VoiceResponse(
                text=response_text,
                speech=response_text,
                should_end_session=True
            )
        else:
            return VoiceResponse(
                text="Для проверки статуса заказа назовите номер заказа.",
                speech="Для проверки статуса заказа назовите номер заказа.",
                should_end_session=False,
                expects_user_input=True,
                session_attributes={"awaiting_input": "order_id"}
            )
    
    async def _handle_product_search(
        self,
        message: VoiceMessage,
        session: VoiceSession
    ) -> VoiceResponse:
        """Handle product search request.
        
        Args:
        ----
            message: Voice message
            session: Voice session
            
        Returns:
        -------
            VoiceResponse: Product search response
        """
        # Extract product name from entities or text
        product_query = None
        for entity in message.entities:
            if entity.type.value == "product":
                product_query = entity.value
                break
        
        if not product_query and message.text:
            # Simple extraction from text (in production: use NLP service)
            product_query = message.text
        
        if product_query:
            # In production: query product catalog service
            response_text = f"Нашел несколько товаров по запросу '{product_query}'. Хотите добавить что-то в корзину?"
            
            return VoiceResponse(
                text=response_text,
                speech=response_text,
                should_end_session=False,
                session_attributes={"last_search": product_query}
            )
        else:
            return VoiceResponse(
                text="Что вы ищете? Назовите название товара.",
                speech="Что вы ищете? Назовите название товара.",
                should_end_session=False,
                expects_user_input=True
            )
    
    async def _handle_add_to_cart(
        self,
        message: VoiceMessage,
        session: VoiceSession
    ) -> VoiceResponse:
        """Handle add to cart request.
        
        Args:
        ----
            message: Voice message
            session: Voice session
            
        Returns:
        -------
            VoiceResponse: Add to cart response
        """
        # In production: integrate with cart service
        return VoiceResponse(
            text="Товар добавлен в корзину. Хотите оформить заказ или продолжить покупки?",
            speech="Товар добавлен в корзину. Хотите оформить заказ или продолжить покупки?",
            should_end_session=False
        )
    
    async def _handle_payment_initiation(
        self,
        message: VoiceMessage,
        session: VoiceSession
    ) -> VoiceResponse:
        """Handle payment initiation request.
        
        Args:
        ----
            message: Voice message
            session: Voice session
            
        Returns:
        -------
            VoiceResponse: Payment initiation response
        """
        # In production: integrate with payment service
        return VoiceResponse(
            text="Для оформления заказа перейдите в мобильное приложение или на сайт. Ссылка отправлена в уведомлениях.",
            speech="Для оформления заказа перейдите в мобильное приложение или на сайт. Ссылка отправлена в уведомлениях.",
            should_end_session=True
        )
    
    async def _handle_help_request(
        self,
        message: VoiceMessage,
        session: VoiceSession
    ) -> VoiceResponse:
        """Handle help request.
        
        Args:
        ----
            message: Voice message
            session: Voice session
            
        Returns:
        -------
            VoiceResponse: Help response
        """
        from app.models.voice import VoiceCard
        
        help_text = "Я могу помочь проверить статус заказа, найти товары, добавить их в корзину. Что вас интересует?"
        
        card = None
        if session.supports_display:
            card = VoiceCard(
                title="Возможности голосового помощника",
                text=help_text,
                buttons=[
                    {"title": "Проверить заказ", "payload": "check_order"},
                    {"title": "Найти товар", "payload": "search_product"}
                ]
            )
        
        return VoiceResponse(
            text=help_text,
            speech=help_text,
            card=card,
            should_end_session=False
        )
    
    async def _handle_unknown_request(
        self,
        message: VoiceMessage,
        session: VoiceSession
    ) -> VoiceResponse:
        """Handle unknown or unrecognized request.
        
        Args:
        ----
            message: Voice message
            session: Voice session
            
        Returns:
        -------
            VoiceResponse: Default response
        """
        return VoiceResponse(
            text="Не совсем понял ваш запрос. Попробуйте переформулировать или скажите 'помощь'.",
            speech="Не совсем понял ваш запрос. Попробуйте переформулировать или скажите 'помощь'.",
            should_end_session=False
        )
    
    async def _update_session_context(
        self,
        session: VoiceSession,
        message: VoiceMessage,
        response: VoiceResponse
    ) -> bool:
        """Update session context based on message and response.
        
        Args:
        ----
            session: Voice session to update
            message: Processed voice message
            response: Generated response
            
        Returns:
        -------
            bool: Whether session was updated
        """
        updated = False
        
        # Update session attributes from response
        if response.session_attributes:
            session.variables.update(response.session_attributes)
            updated = True
        
        # Track recent messages (keep last 5 for context)
        session.recent_messages.append(message.message_id)
        if len(session.recent_messages) > 5:
            session.recent_messages = session.recent_messages[-5:]
            updated = True
        
        # Update current intent
        if message.intent:
            session.current_intent = message.intent.name
            updated = True
        
        # Update last activity
        session.last_activity = datetime.now()
        
        return updated
    
    async def register_intent_mapping(self, mapping: VoiceIntentMapping):
        """Register intent mapping for business logic.
        
        Args:
        ----
            mapping: Intent mapping configuration
        """
        self._intent_mappings[mapping.voice_intent] = mapping
        
        logger.info(
            "Intent mapping registered",
            voice_intent=mapping.voice_intent,
            business_action=mapping.business_action
        )
    
    async def get_platform_analytics(
        self,
        platform: VoicePlatform
    ) -> VoiceAnalytics | None:
        """Get analytics for voice platform.
        
        Args:
        ----
            platform: Voice platform
            
        Returns:
        -------
            VoiceAnalytics | None: Platform analytics
        """
        adapter = self._adapters.get(platform)
        if adapter:
            return await adapter.get_analytics()
        return None
    
    async def get_supported_platforms(self) -> list[dict[str, Any]]:
        """Get list of supported voice platforms.
        
        Returns:
        -------
            list[dict[str, Any]]: Platform information
        """
        platforms = []
        
        for platform, config in self._platform_configs.items():
            platform_info = {
                "name": platform.value,
                "enabled": config.enabled,
                "capabilities": {
                    "supports_audio_output": config.supports_audio_output,
                    "supports_display": config.supports_display,
                    "supports_account_linking": config.supports_account_linking,
                    "supports_push_notifications": config.supports_push_notifications
                },
                "languages": config.supported_languages,
                "session_timeout_minutes": config.session_timeout_minutes,
                "is_connected": platform in self._adapters
            }
            platforms.append(platform_info)
        
        return platforms
    
    async def health_check(self) -> dict[str, Any]:
        """Get health status of voice service.
        
        Returns:
        -------
            dict[str, Any]: Health status
        """
        health_status = {}
        
        for platform, adapter in self._adapters.items():
            try:
                status = await adapter.get_health_status()
                health_status[platform.value] = status
            except Exception as e:
                health_status[platform.value] = {
                    "platform": platform.value,
                    "healthy": False,
                    "error": str(e),
                    "last_check": datetime.now().isoformat()
                }
        
        return {
            "voice_platforms": health_status,
            "total_platforms": len(self._adapters),
            "healthy_platforms": sum(
                1 for status in health_status.values() 
                if status.get("healthy", False)
            ),
            "registered_intents": len(self._intent_mappings),
            "timestamp": datetime.now().isoformat()
        }
    
    async def cleanup(self):
        """Clean up voice service resources."""
        try:
            # Close all adapters
            for platform, adapter in self._adapters.items():
                try:
                    await adapter.close()
                    logger.info("Closed voice adapter", platform=platform.value)
                except Exception as e:
                    logger.error(
                        "Error closing voice adapter",
                        platform=platform.value,
                        error=str(e)
                    )
            
            # Clear state
            self._adapters.clear()
            self._platform_configs.clear()
            self._intent_mappings.clear()
            
            logger.info("Voice service cleanup completed")
            
        except Exception as e:
            logger.error("Error during voice service cleanup", error=str(e))