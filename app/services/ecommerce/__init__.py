"""E-commerce platform integrations."""

from .base import (
    APIResponse,
    PlatformAdapter,
    PlatformCredentials,
    PlatformManager,
    SyncResult,
)
from .shopify import ShopifyAdapter
from .woocommerce import WooCommerceAdapter
from .bigcommerce import BigCommerceAdapter
from .magento import MagentoAdapter

__all__ = [
    "APIResponse",
    "PlatformAdapter", 
    "PlatformCredentials",
    "PlatformManager",
    "SyncResult",
    "ShopifyAdapter",
    "WooCommerceAdapter", 
    "BigCommerceAdapter",
    "MagentoAdapter",
]