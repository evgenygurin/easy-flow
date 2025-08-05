"""Модуль состояний для conversation flow."""
from .base import ConversationState, StateResult
from .hangup import HangupState
from .hello import HelloState
from .order import OrderState
from .payment import PaymentState
from .shipping import ShippingState


__all__ = [
    "ConversationState",
    "StateResult",
    "HelloState",
    "OrderState",
    "PaymentState",
    "ShippingState",
    "HangupState"
]
