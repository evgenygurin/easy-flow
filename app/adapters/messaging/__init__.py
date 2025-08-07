"""Messaging platform adapters package."""
from .base import MessagingAdapter, UnifiedMessage, DeliveryResult, MessageType
from .telegram import TelegramAdapter
from .whatsapp import WhatsAppAdapter
from .vk import VKAdapter
from .viber import ViberAdapter

__all__ = [
    "MessagingAdapter",
    "UnifiedMessage", 
    "DeliveryResult",
    "MessageType",
    "TelegramAdapter",
    "WhatsAppAdapter",
    "VKAdapter",
    "ViberAdapter",
]