"""WooCommerce (WordPress) e-commerce platform integration adapter."""
import base64
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from app.adapters.base import PlatformAdapter, APIResponse, SyncResult, RateLimitConfig
from app.models.ecommerce import Customer, Order, Product

logger = structlog.get_logger()


class WooCommerceAdapter(PlatformAdapter):
    """WooCommerce e-commerce platform integration adapter with WordPress REST API."""
    
    def __init__(
        self,
        site_url: str,
        consumer_key: str,
        consumer_secret: str,
        api_version: str = "v3"
    ):
        """Initialize WooCommerce adapter.
        
        Args:
        ----
            site_url: WordPress site URL (e.g., 'https://myshop.com')
            consumer_key: WooCommerce API consumer key
            consumer_secret: WooCommerce API consumer secret
            api_version: WooCommerce API version
        """
        base_url = site_url.rstrip('/')
        
        super().__init__(
            api_key=consumer_key,
            base_url=base_url,
            platform_name="woocommerce",
            rate_limit_config=RateLimitConfig(
                requests_per_minute=120,  # WooCommerce is generally permissive
                requests_per_hour=7200,
                burst_size=20
            )
        )
        
        self.site_url = site_url
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.api_version = api_version
        
        # WooCommerce order status mapping
        self.order_status_mapping = {
            "pending": "pending",
            "processing": "confirmed",
            "on-hold": "processing",
            "completed": "delivered",
            "cancelled": "cancelled",
            "refunded": "returned",
            "failed": "cancelled"
        }
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers with Basic Auth."""
        # WooCommerce uses HTTP Basic Authentication with consumer key/secret
        auth_string = f"{self.consumer_key}:{self.consumer_secret}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()
        
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Basic {auth_encoded}"
        }
    
    async def test_connection(self) -> APIResponse:
        """Test connection to WooCommerce API."""
        try:
            # Test with system status endpoint
            response = await self._make_request(
                method="GET",
                url=f"/wp-json/wc/{self.api_version}/system_status"
            )
            
            if response.success:
                logger.info("WooCommerce connection test successful")
            
            return response
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0,
                platform=self.platform_name
            )
    
    async def sync_orders(self, limit: int = 100) -> SyncResult:
        """Sync orders from WooCommerce."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get orders from WooCommerce
            response = await self._make_request(
                method="GET",
                url=f"/wp-json/wc/{self.api_version}/orders",
                params={
                    "per_page": min(limit, 100),  # WooCommerce max per page
                    "page": 1,
                    "order": "desc",
                    "orderby": "date"
                }
            )
            
            if not response.success:
                errors.append(f"Failed to fetch orders: {response.error}")
                return SyncResult(
                    platform=self.platform_name,
                    operation="orders",
                    records_processed=processed,
                    records_success=success,
                    records_failed=processed - success,
                    errors=errors,
                    duration_seconds=(datetime.now() - start_time).total_seconds()
                )
            
            orders_data = response.data if isinstance(response.data, list) else []
            
            for order_data in orders_data:
                processed += 1
                try:
                    # Transform WooCommerce order to internal Order model
                    order = await self._transform_order(order_data)
                    
                    logger.info(
                        "Synchronized WooCommerce order",
                        wc_order_id=order_data.get("id"),
                        order_id=order.order_id,
                        status=order.status
                    )
                    success += 1
                    
                except Exception as e:
                    error_msg = f"Failed to process order {order_data.get('id')}: {str(e)}"
                    errors.append(error_msg)
        
        except Exception as e:
            errors.append(f"Order sync failed: {str(e)}")
        
        return SyncResult(
            platform=self.platform_name,
            operation="orders",
            records_processed=processed,
            records_success=success,
            records_failed=processed - success,
            errors=errors,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )
    
    async def sync_products(self, limit: int = 100) -> SyncResult:
        """Sync products from WooCommerce catalog."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get products from WooCommerce
            response = await self._make_request(
                method="GET",
                url=f"/wp-json/wc/{self.api_version}/products",
                params={
                    "per_page": min(limit, 100),  # WooCommerce max per page
                    "page": 1,
                    "status": "publish"
                }
            )
            
            if not response.success:
                errors.append(f"Failed to fetch products: {response.error}")
                return SyncResult(
                    platform=self.platform_name,
                    operation="products",
                    records_processed=processed,
                    records_success=success,
                    records_failed=processed - success,
                    errors=errors,
                    duration_seconds=(datetime.now() - start_time).total_seconds()
                )
            
            products_data = response.data if isinstance(response.data, list) else []
            
            for product_data in products_data:
                processed += 1
                try:
                    # Transform WooCommerce product to internal Product model
                    product = await self._transform_product(product_data)
                    
                    logger.info(
                        "Synchronized WooCommerce product",
                        wc_product_id=product_data.get("id"),
                        product_id=product.product_id,
                        name=product.name
                    )
                    success += 1
                    
                except Exception as e:
                    error_msg = f"Failed to process product {product_data.get('id')}: {str(e)}"
                    errors.append(error_msg)
        
        except Exception as e:
            errors.append(f"Product sync failed: {str(e)}")
        
        return SyncResult(
            platform=self.platform_name,
            operation="products",
            records_processed=processed,
            records_success=success,
            records_failed=processed - success,
            errors=errors,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )
    
    async def sync_customers(self, limit: int = 100) -> SyncResult:
        """Sync customers from WooCommerce."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get customers from WooCommerce
            response = await self._make_request(
                method="GET",
                url=f"/wp-json/wc/{self.api_version}/customers",
                params={
                    "per_page": min(limit, 100),  # WooCommerce max per page
                    "page": 1,
                    "order": "desc",
                    "orderby": "registered_date"
                }
            )
            
            if not response.success:
                errors.append(f"Failed to fetch customers: {response.error}")
                return SyncResult(
                    platform=self.platform_name,
                    operation="customers",
                    records_processed=processed,
                    records_success=success,
                    records_failed=processed - success,
                    errors=errors,
                    duration_seconds=(datetime.now() - start_time).total_seconds()
                )
            
            customers_data = response.data if isinstance(response.data, list) else []
            
            for customer_data in customers_data:
                processed += 1
                try:
                    # Transform WooCommerce customer to internal Customer model
                    customer = await self._transform_customer(customer_data)
                    
                    logger.info(
                        "Synchronized WooCommerce customer",
                        wc_customer_id=customer_data.get("id"),
                        customer_id=customer.customer_id
                    )
                    success += 1
                    
                except Exception as e:
                    error_msg = f"Failed to process customer {customer_data.get('id')}: {str(e)}"
                    errors.append(error_msg)
        
        except Exception as e:
            errors.append(f"Customer sync failed: {str(e)}")
        
        return SyncResult(
            platform=self.platform_name,
            operation="customers",
            records_processed=processed,
            records_success=success,
            records_failed=processed - success,
            errors=errors,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )
    
    async def handle_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None) -> bool:
        """Handle WooCommerce webhook events."""
        try:
            # WooCommerce webhook structure varies by event type
            # Events are typically based on the webhook topic configured
            
            # Determine event type from payload structure or custom header
            if "id" in payload and "status" in payload and "total" in payload:
                # Likely an order webhook
                await self._handle_order_webhook(payload)
            elif "id" in payload and "name" in payload and "price" in payload:
                # Likely a product webhook  
                await self._handle_product_webhook(payload)
            elif "id" in payload and "email" in payload and "first_name" in payload:
                # Likely a customer webhook
                await self._handle_customer_webhook(payload)
            else:
                logger.warning("Unknown WooCommerce webhook event", payload_keys=list(payload.keys()))
                return False
            
            logger.info("Processed WooCommerce webhook")
            return True
            
        except Exception as e:
            logger.error("WooCommerce webhook processing failed", error=str(e))
            return False
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify WooCommerce webhook signature."""
        # WooCommerce uses HMAC-SHA256 for webhook signature verification
        return self._verify_hmac_sha256(payload, signature, secret)
    
    async def get_product_variations(self, product_id: str) -> APIResponse:
        """Get product variations for a variable product."""
        try:
            response = await self._make_request(
                method="GET",
                url=f"/wp-json/wc/{self.api_version}/products/{product_id}/variations"
            )
            return response
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0,
                platform=self.platform_name
            )
    
    async def _transform_order(self, order_data: Dict[str, Any]) -> Order:
        """Transform WooCommerce order to Order model."""
        from decimal import Decimal
        
        order_id = str(order_data.get("id", ""))
        status = self.order_status_mapping.get(order_data.get("status", ""), "pending")
        
        # Parse dates
        created_at = datetime.now()
        if order_data.get("date_created"):
            try:
                created_at = datetime.fromisoformat(order_data["date_created"].replace("Z", "+00:00"))
            except:
                pass
        
        # Parse totals
        total_price = Decimal("0.00")
        if order_data.get("total"):
            try:
                total_price = Decimal(str(order_data["total"]))
            except:
                pass
        
        # Get customer info
        billing = order_data.get("billing", {})
        customer_id = str(order_data.get("customer_id", "guest"))
        
        return Order(
            order_id=f"wc_{order_id}",
            customer_id=f"wc_{customer_id}",
            status=status,
            subtotal=total_price,
            total=total_price,
            created_at=created_at,
            source="woocommerce",
            notes=order_data.get("customer_note", "")
        )
    
    async def _transform_product(self, product_data: Dict[str, Any]) -> Product:
        """Transform WooCommerce product to Product model."""
        from decimal import Decimal
        
        product_id = str(product_data.get("id", ""))
        
        # Parse price
        price = Decimal("0.00")
        if product_data.get("regular_price"):
            try:
                price = Decimal(str(product_data["regular_price"]))
            except:
                pass
        
        # Handle stock status and quantity
        in_stock = product_data.get("stock_status", "") == "instock"
        stock_quantity = 0
        
        if product_data.get("stock_quantity") is not None:
            try:
                stock_quantity = int(product_data["stock_quantity"])
            except:
                pass
        
        # Get categories
        categories = product_data.get("categories", [])
        category = categories[0].get("name", "") if categories else ""
        
        return Product(
            product_id=f"wc_{product_id}",
            name=product_data.get("name", ""),
            description=product_data.get("description", ""),
            category=category,
            price=price,
            currency="USD",  # WooCommerce default, configurable per shop
            in_stock=in_stock,
            stock_quantity=stock_quantity,
            weight=product_data.get("weight")
        )
    
    async def _transform_customer(self, customer_data: Dict[str, Any]) -> Customer:
        """Transform WooCommerce customer to Customer model."""
        from decimal import Decimal
        
        customer_id = str(customer_data.get("id", ""))
        
        # Parse creation date
        created_at = datetime.now()
        if customer_data.get("date_created"):
            try:
                created_at = datetime.fromisoformat(customer_data["date_created"].replace("Z", "+00:00"))
            except:
                pass
        
        # Parse total spent
        total_spent = Decimal("0.00")
        if customer_data.get("total_spent"):
            try:
                total_spent = Decimal(str(customer_data["total_spent"]))
            except:
                pass
        
        return Customer(
            customer_id=f"wc_{customer_id}",
            first_name=customer_data.get("first_name", ""),
            last_name=customer_data.get("last_name", ""),
            email=customer_data.get("email"),
            phone=customer_data.get("billing", {}).get("phone"),
            created_at=created_at,
            total_orders=customer_data.get("orders_count", 0),
            total_spent=total_spent
        )
    
    async def _handle_order_webhook(self, order_data: Dict[str, Any]):
        """Handle order webhook event."""
        order_id = order_data.get("id")
        status = order_data.get("status")
        logger.info("WooCommerce order webhook", order_id=order_id, status=status)
        # TODO: Update internal order data
    
    async def _handle_product_webhook(self, product_data: Dict[str, Any]):
        """Handle product webhook event."""
        product_id = product_data.get("id")
        logger.info("WooCommerce product webhook", product_id=product_id)
        # TODO: Update internal product data
    
    async def _handle_customer_webhook(self, customer_data: Dict[str, Any]):
        """Handle customer webhook event."""
        customer_id = customer_data.get("id")
        logger.info("WooCommerce customer webhook", customer_id=customer_id)
        # TODO: Update internal customer data