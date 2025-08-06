"""BigCommerce e-commerce platform integration adapter."""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from app.adapters.base import PlatformAdapter, APIResponse, SyncResult, RateLimitConfig
from app.models.ecommerce import Customer, Order, Product

logger = structlog.get_logger()


class BigCommerceAdapter(PlatformAdapter):
    """BigCommerce e-commerce platform integration adapter with API v3."""
    
    def __init__(
        self,
        store_hash: str,
        access_token: str,
        client_id: Optional[str] = None
    ):
        """Initialize BigCommerce adapter.
        
        Args:
        ----
            store_hash: BigCommerce store hash
            access_token: BigCommerce access token
            client_id: BigCommerce client ID (for webhook verification)
        """
        base_url = f"https://api.bigcommerce.com/stores/{store_hash}"
        
        super().__init__(
            api_key=access_token,
            base_url=base_url,
            platform_name="bigcommerce",
            rate_limit_config=RateLimitConfig(
                requests_per_minute=150,  # BigCommerce has generous limits
                requests_per_hour=9000,
                burst_size=20
            )
        )
        
        self.store_hash = store_hash
        self.access_token = access_token
        self.client_id = client_id
        
        # BigCommerce order status mapping
        self.order_status_mapping = {
            0: "incomplete",  # Incomplete
            1: "pending",     # Pending
            2: "shipped",     # Shipped
            3: "partially_shipped",  # Partially Shipped
            4: "returned",    # Refunded
            5: "cancelled",   # Cancelled
            6: "declined",    # Declined
            7: "awaiting_payment",  # Awaiting Payment
            8: "awaiting_pickup",   # Awaiting Pickup
            9: "awaiting_shipment", # Awaiting Shipment
            10: "completed",  # Completed
            11: "awaiting_fulfillment",  # Awaiting Fulfillment
            12: "manual_verification_required",  # Manual Verification Required
            13: "disputed",   # Disputed
            14: "partially_refunded"  # Partially Refunded
        }
        
        # Map to our internal statuses
        self.internal_status_mapping = {
            "incomplete": "pending",
            "pending": "pending",
            "awaiting_payment": "pending",
            "manual_verification_required": "confirmed",
            "awaiting_fulfillment": "processing",
            "awaiting_shipment": "processing",
            "awaiting_pickup": "processing",
            "shipped": "shipped",
            "partially_shipped": "shipped",
            "completed": "delivered",
            "cancelled": "cancelled",
            "declined": "cancelled",
            "returned": "returned",
            "partially_refunded": "returned",
            "refunded": "returned",
            "disputed": "processing"
        }
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Auth-Token": self.access_token
        }
        
        if self.client_id:
            headers["X-Auth-Client"] = self.client_id
            
        return headers
    
    async def test_connection(self) -> APIResponse:
        """Test connection to BigCommerce API."""
        try:
            # Test with store info endpoint
            response = await self._make_request(
                method="GET",
                url="/v2/store"
            )
            
            if response.success:
                logger.info("BigCommerce connection test successful")
            
            return response
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0,
                platform=self.platform_name
            )
    
    async def sync_orders(self, limit: int = 100) -> SyncResult:
        """Sync orders from BigCommerce."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get orders from BigCommerce
            response = await self._make_request(
                method="GET",
                url="/v2/orders",
                params={
                    "limit": min(limit, 250),  # BigCommerce max per page
                    "page": 1,
                    "sort": "date_created:desc"
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
                    # Transform BigCommerce order to internal Order model
                    order = await self._transform_order(order_data)
                    
                    logger.info(
                        "Synchronized BigCommerce order",
                        bc_order_id=order_data.get("id"),
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
        """Sync products from BigCommerce catalog."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get products from BigCommerce
            response = await self._make_request(
                method="GET",
                url="/v3/catalog/products",
                params={
                    "limit": min(limit, 250),  # BigCommerce max per page
                    "page": 1,
                    "is_visible": True,
                    "include": "variants,images,custom_fields"
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
            
            products_response = response.data if isinstance(response.data, dict) else {}
            products_data = products_response.get("data", [])
            
            for product_data in products_data:
                processed += 1
                try:
                    # Transform BigCommerce product to internal Product model
                    product = await self._transform_product(product_data)
                    
                    logger.info(
                        "Synchronized BigCommerce product",
                        bc_product_id=product_data.get("id"),
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
        """Sync customers from BigCommerce."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get customers from BigCommerce
            response = await self._make_request(
                method="GET",
                url="/v3/customers",
                params={
                    "limit": min(limit, 250),  # BigCommerce max per page
                    "page": 1,
                    "include": "addresses,form_fields"
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
            
            customers_response = response.data if isinstance(response.data, dict) else {}
            customers_data = customers_response.get("data", [])
            
            for customer_data in customers_data:
                processed += 1
                try:
                    # Transform BigCommerce customer to internal Customer model
                    customer = await self._transform_customer(customer_data)
                    
                    logger.info(
                        "Synchronized BigCommerce customer",
                        bc_customer_id=customer_data.get("id"),
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
        """Handle BigCommerce webhook events."""
        try:
            scope = payload.get("scope")
            data = payload.get("data", {})
            
            logger.info("Processing BigCommerce webhook", scope=scope)
            
            if scope and "store/order/" in scope:
                # Order-related webhooks
                if scope == "store/order/created":
                    await self._handle_order_created(data)
                elif scope == "store/order/updated":
                    await self._handle_order_updated(data)
                elif scope == "store/order/statusUpdated":
                    await self._handle_order_status_updated(data)
            
            elif scope and "store/product/" in scope:
                # Product-related webhooks
                if scope == "store/product/created":
                    await self._handle_product_created(data)
                elif scope == "store/product/updated":
                    await self._handle_product_updated(data)
                elif scope == "store/product/inventory/updated":
                    await self._handle_product_inventory_updated(data)
            
            elif scope and "store/customer/" in scope:
                # Customer-related webhooks
                if scope == "store/customer/created":
                    await self._handle_customer_created(data)
                elif scope == "store/customer/updated":
                    await self._handle_customer_updated(data)
            
            return True
            
        except Exception as e:
            logger.error("BigCommerce webhook processing failed", error=str(e))
            return False
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify BigCommerce webhook signature."""
        # BigCommerce uses HMAC-SHA256 for webhook signature verification
        return self._verify_hmac_sha256(payload, signature, secret)
    
    async def get_product_variants(self, product_id: str) -> APIResponse:
        """Get product variants for a product."""
        try:
            response = await self._make_request(
                method="GET",
                url=f"/v3/catalog/products/{product_id}/variants"
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
        """Transform BigCommerce order to Order model."""
        from decimal import Decimal
        
        order_id = str(order_data.get("id", ""))
        
        # Map BigCommerce status to our internal status
        bc_status_id = order_data.get("status_id", 1)
        bc_status_name = self.order_status_mapping.get(bc_status_id, "pending")
        status = self.internal_status_mapping.get(bc_status_name, "pending")
        
        # Parse dates
        created_at = datetime.now()
        if order_data.get("date_created"):
            try:
                # BigCommerce uses RFC 2822 format
                created_at = datetime.strptime(
                    order_data["date_created"], 
                    "%a, %d %b %Y %H:%M:%S %z"
                )
            except:
                try:
                    # Fallback to ISO format
                    created_at = datetime.fromisoformat(order_data["date_created"].replace("Z", "+00:00"))
                except:
                    pass
        
        # Parse totals
        total_price = Decimal("0.00")
        if order_data.get("total_inc_tax"):
            try:
                total_price = Decimal(str(order_data["total_inc_tax"]))
            except:
                pass
        
        return Order(
            order_id=f"bc_{order_id}",
            customer_id=f"bc_{order_data.get('customer_id', 0)}",
            status=status,
            subtotal=total_price,
            total=total_price,
            created_at=created_at,
            source="bigcommerce",
            notes=order_data.get("customer_message", "")
        )
    
    async def _transform_product(self, product_data: Dict[str, Any]) -> Product:
        """Transform BigCommerce product to Product model."""
        from decimal import Decimal
        
        product_id = str(product_data.get("id", ""))
        
        # Parse price
        price = Decimal("0.00")
        if product_data.get("price"):
            try:
                price = Decimal(str(product_data["price"]))
            except:
                pass
        
        # Handle inventory tracking
        inventory_tracking = product_data.get("inventory_tracking", "none")
        in_stock = True
        stock_quantity = 0
        
        if inventory_tracking != "none":
            inventory_level = product_data.get("inventory_level", 0)
            stock_quantity = inventory_level
            in_stock = inventory_level > 0
        
        # Get categories - BigCommerce uses category IDs
        categories = product_data.get("categories", [])
        category = f"category_{categories[0]}" if categories else ""
        
        return Product(
            product_id=f"bc_{product_id}",
            name=product_data.get("name", ""),
            description=product_data.get("description", ""),
            category=category,
            brand=product_data.get("brand_id", ""),
            price=price,
            currency="USD",  # BigCommerce default, configurable per store
            in_stock=in_stock,
            stock_quantity=stock_quantity,
            weight=product_data.get("weight")
        )
    
    async def _transform_customer(self, customer_data: Dict[str, Any]) -> Customer:
        """Transform BigCommerce customer to Customer model."""
        customer_id = str(customer_data.get("id", ""))
        
        # Parse creation date
        created_at = datetime.now()
        if customer_data.get("date_created"):
            try:
                created_at = datetime.strptime(
                    customer_data["date_created"],
                    "%a, %d %b %Y %H:%M:%S %z"
                )
            except:
                try:
                    created_at = datetime.fromisoformat(customer_data["date_created"].replace("Z", "+00:00"))
                except:
                    pass
        
        return Customer(
            customer_id=f"bc_{customer_id}",
            first_name=customer_data.get("first_name", ""),
            last_name=customer_data.get("last_name", ""),
            email=customer_data.get("email"),
            phone=customer_data.get("phone"),
            created_at=created_at
        )
    
    async def _handle_order_created(self, order_data: Dict[str, Any]):
        """Handle order created webhook."""
        order_id = order_data.get("id")
        logger.info("BigCommerce order created", order_id=order_id)
        # TODO: Process new order
    
    async def _handle_order_updated(self, order_data: Dict[str, Any]):
        """Handle order updated webhook."""
        order_id = order_data.get("id")
        logger.info("BigCommerce order updated", order_id=order_id)
        # TODO: Update order
    
    async def _handle_order_status_updated(self, order_data: Dict[str, Any]):
        """Handle order status updated webhook."""
        order_id = order_data.get("id")
        status = order_data.get("status")
        logger.info("BigCommerce order status updated", order_id=order_id, status=status)
        # TODO: Update order status
    
    async def _handle_product_created(self, product_data: Dict[str, Any]):
        """Handle product created webhook."""
        product_id = product_data.get("id")
        logger.info("BigCommerce product created", product_id=product_id)
        # TODO: Process new product
    
    async def _handle_product_updated(self, product_data: Dict[str, Any]):
        """Handle product updated webhook."""
        product_id = product_data.get("id")
        logger.info("BigCommerce product updated", product_id=product_id)
        # TODO: Update product
    
    async def _handle_product_inventory_updated(self, product_data: Dict[str, Any]):
        """Handle product inventory updated webhook."""
        product_id = product_data.get("product_id")
        variant_id = product_data.get("variant_id")
        logger.info("BigCommerce product inventory updated", product_id=product_id, variant_id=variant_id)
        # TODO: Update product inventory
    
    async def _handle_customer_created(self, customer_data: Dict[str, Any]):
        """Handle customer created webhook."""
        customer_id = customer_data.get("id")
        logger.info("BigCommerce customer created", customer_id=customer_id)
        # TODO: Process new customer
    
    async def _handle_customer_updated(self, customer_data: Dict[str, Any]):
        """Handle customer updated webhook."""
        customer_id = customer_data.get("id")
        logger.info("BigCommerce customer updated", customer_id=customer_id)
        # TODO: Update customer