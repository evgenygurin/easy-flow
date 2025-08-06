"""BigCommerce e-commerce platform integration."""
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from app.models.ecommerce import Address, Customer, Order, OrderItem, OrderStatus, PaymentStatus, Product
from .base import APIResponse, PlatformAdapter

logger = structlog.get_logger()


class BigCommerceAdapter(PlatformAdapter):
    """BigCommerce e-commerce platform adapter with API v3 support."""
    
    def __init__(self, credentials: dict[str, Any], config: dict[str, Any] | None = None):
        super().__init__(credentials, config)
        
        # Required credentials
        self.store_hash = credentials["store_hash"]  # e.g., "abc123"
        self.access_token = credentials["access_token"]  # API access token
        
        # API endpoints
        self.api_url = f"https://api.bigcommerce.com/stores/{self.store_hash}/v3/"
        self.api_v2_url = f"https://api.bigcommerce.com/stores/{self.store_hash}/v2/"
        
        # API version
        self.api_version = config.get("api_version", "v3")
        
        # Default headers
        self.headers = {
            "X-Auth-Token": self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def authenticate(self) -> APIResponse:
        """Test authentication by fetching store information."""
        try:
            response = await self.make_request(
                "GET",
                f"{self.api_v2_url}store",
                headers=self.headers
            )
            
            if response.success and response.data:
                store_data = response.data
                logger.info(
                    "BigCommerce authentication successful",
                    store_name=store_data.get("name"),
                    store_url=store_data.get("domain")
                )
                return APIResponse(
                    success=True,
                    data={"store": store_data}
                )
            else:
                return APIResponse(
                    success=False,
                    error_message="Authentication failed: Invalid response"
                )
                
        except Exception as e:
            logger.error("BigCommerce authentication failed", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Authentication error: {str(e)}"
            )
    
    async def get_orders(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None
    ) -> APIResponse:
        """Fetch orders from BigCommerce using API v3."""
        try:
            params = {
                "limit": min(limit, 250),  # BigCommerce max limit is 250
                "page": (offset // limit) + 1,
            }
            
            if filters:
                if filters.get("status_id"):
                    params["status_id"] = filters["status_id"]
                if filters.get("min_date_created"):
                    params["min_date_created"] = filters["min_date_created"]
                if filters.get("max_date_created"):
                    params["max_date_created"] = filters["max_date_created"]
            
            response = await self.make_request(
                "GET",
                f"{self.api_v2_url}orders",  # v2 has more complete order data
                headers=self.headers,
                params=params
            )
            
            if response.success and response.data:
                orders_data = response.data
                transformed_orders = []
                
                for order_data in orders_data:
                    try:
                        # Fetch order products for complete data
                        products_response = await self.make_request(
                            "GET",
                            f"{self.api_v2_url}orders/{order_data['id']}/products",
                            headers=self.headers
                        )
                        
                        if products_response.success:
                            order_data["line_items"] = products_response.data
                        
                        transformed_order = self.transform_order(order_data)
                        if transformed_order:
                            transformed_orders.append(transformed_order)
                    except Exception as e:
                        logger.warning("Failed to transform BigCommerce order", order_id=order_data.get("id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_orders)} orders from BigCommerce")
                return APIResponse(
                    success=True,
                    data=transformed_orders,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch BigCommerce orders", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Error fetching orders: {str(e)}"
            )
    
    async def get_products(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None
    ) -> APIResponse:
        """Fetch products from BigCommerce using API v3."""
        try:
            params = {
                "limit": min(limit, 250),
                "page": (offset // limit) + 1,
                "include": "variants,images,custom_fields",  # Include related data
            }
            
            if filters:
                if filters.get("availability"):
                    params["availability"] = filters["availability"]
                if filters.get("categories"):
                    params["categories:in"] = filters["categories"]
                if filters.get("is_visible"):
                    params["is_visible"] = filters["is_visible"]
            
            response = await self.make_request(
                "GET",
                f"{self.api_url}catalog/products",
                headers=self.headers,
                params=params
            )
            
            if response.success and response.data:
                products_data = response.data.get("data", [])
                transformed_products = []
                
                for product_data in products_data:
                    try:
                        # Handle product variants
                        variants = product_data.get("variants", [])
                        
                        if variants:
                            for variant_data in variants:
                                combined_data = {**product_data, "variant": variant_data}
                                transformed_product = self.transform_product(combined_data)
                                if transformed_product:
                                    transformed_products.append(transformed_product)
                        else:
                            # Product without variants
                            transformed_product = self.transform_product(product_data)
                            if transformed_product:
                                transformed_products.append(transformed_product)
                                
                    except Exception as e:
                        logger.warning("Failed to transform BigCommerce product", product_id=product_data.get("id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_products)} products from BigCommerce")
                return APIResponse(
                    success=True,
                    data=transformed_products,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch BigCommerce products", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Error fetching products: {str(e)}"
            )
    
    async def get_customers(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None
    ) -> APIResponse:
        """Fetch customers from BigCommerce using API v3."""
        try:
            params = {
                "limit": min(limit, 250),
                "page": (offset // limit) + 1,
                "include": "addresses,form_fields",
            }
            
            if filters:
                if filters.get("email"):
                    params["email:in"] = filters["email"]
                if filters.get("customer_group_id"):
                    params["customer_group_id"] = filters["customer_group_id"]
            
            response = await self.make_request(
                "GET",
                f"{self.api_url}customers",
                headers=self.headers,
                params=params
            )
            
            if response.success and response.data:
                customers_data = response.data.get("data", [])
                transformed_customers = []
                
                for customer_data in customers_data:
                    try:
                        transformed_customer = self.transform_customer(customer_data)
                        if transformed_customer:
                            transformed_customers.append(transformed_customer)
                    except Exception as e:
                        logger.warning("Failed to transform BigCommerce customer", customer_id=customer_data.get("id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_customers)} customers from BigCommerce")
                return APIResponse(
                    success=True,
                    data=transformed_customers,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch BigCommerce customers", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Error fetching customers: {str(e)}"
            )
    
    async def update_order_status(self, order_id: str, status: str) -> APIResponse:
        """Update order status in BigCommerce."""
        try:
            # Map our status to BigCommerce status IDs
            status_mapping = {
                "pending": 1,        # Pending
                "processing": 7,     # Awaiting Processing
                "shipped": 9,        # Awaiting Shipment  
                "delivered": 10,     # Shipped
                "cancelled": 5,      # Cancelled
                "returned": 4        # Returned
            }
            
            bc_status_id = status_mapping.get(status, 1)
            
            update_data = {
                "status_id": bc_status_id
            }
            
            response = await self.make_request(
                "PUT",
                f"{self.api_v2_url}orders/{order_id}",
                headers=self.headers,
                json_data=update_data
            )
            
            if response.success:
                logger.info(f"Updated BigCommerce order {order_id} status to {bc_status_id}")
            
            return response
            
        except Exception as e:
            logger.error("Failed to update BigCommerce order status", order_id=order_id, error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Error updating order status: {str(e)}"
            )
    
    async def handle_webhook(self, payload: dict[str, Any]) -> APIResponse:
        """Handle BigCommerce webhook events."""
        try:
            event_type = payload.get("scope")  # BigCommerce uses 'scope' for event type
            
            if event_type in ["store/order/created", "store/order/updated"]:
                order_data = payload.get("data", {})
                order_id = order_data.get("id")
                
                if order_id:
                    # Fetch complete order data
                    order_response = await self.make_request(
                        "GET",
                        f"{self.api_v2_url}orders/{order_id}",
                        headers=self.headers
                    )
                    
                    if order_response.success:
                        transformed_order = self.transform_order(order_response.data)
                        if transformed_order:
                            logger.info(f"Processed BigCommerce {event_type} webhook", order_id=transformed_order.order_id)
                            return APIResponse(success=True, data={"order": transformed_order})
            
            elif event_type in ["store/product/created", "store/product/updated"]:
                product_data = payload.get("data", {})
                product_id = product_data.get("id")
                
                if product_id:
                    # Fetch complete product data
                    product_response = await self.make_request(
                        "GET",
                        f"{self.api_url}catalog/products/{product_id}",
                        headers=self.headers,
                        params={"include": "variants,images"}
                    )
                    
                    if product_response.success and product_response.data:
                        product_full_data = product_response.data.get("data", {})
                        transformed_product = self.transform_product(product_full_data)
                        if transformed_product:
                            logger.info(f"Processed BigCommerce {event_type} webhook", product_id=transformed_product.product_id)
                            return APIResponse(success=True, data={"product": transformed_product})
            
            elif event_type in ["store/customer/created", "store/customer/updated"]:
                customer_data = payload.get("data", {})
                customer_id = customer_data.get("id")
                
                if customer_id:
                    # Fetch complete customer data
                    customer_response = await self.make_request(
                        "GET",
                        f"{self.api_url}customers/{customer_id}",
                        headers=self.headers,
                        params={"include": "addresses"}
                    )
                    
                    if customer_response.success and customer_response.data:
                        customer_full_data = customer_response.data.get("data", {})
                        transformed_customer = self.transform_customer(customer_full_data)
                        if transformed_customer:
                            logger.info(f"Processed BigCommerce {event_type} webhook", customer_id=transformed_customer.customer_id)
                            return APIResponse(success=True, data={"customer": transformed_customer})
            
            else:
                logger.info(f"Unhandled BigCommerce webhook event: {event_type}")
                return APIResponse(success=True, data={"message": f"Event {event_type} acknowledged"})
                
        except Exception as e:
            logger.error("Failed to process BigCommerce webhook", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Webhook processing error: {str(e)}"
            )
    
    def transform_order(self, raw_order: dict[str, Any]) -> Order | None:
        """Transform BigCommerce order data to unified format."""
        try:
            # Map BigCommerce status IDs to our enum
            status_mapping = {
                0: OrderStatus.PENDING,      # Incomplete
                1: OrderStatus.PENDING,      # Pending
                2: OrderStatus.SHIPPED,      # Shipped
                3: OrderStatus.DELIVERED,    # Partially Shipped
                4: OrderStatus.RETURNED,     # Refunded
                5: OrderStatus.CANCELLED,    # Cancelled
                6: OrderStatus.CANCELLED,    # Declined
                7: OrderStatus.PROCESSING,   # Awaiting Processing
                8: OrderStatus.PROCESSING,   # Awaiting Payment
                9: OrderStatus.PROCESSING,   # Awaiting Pickup
                10: OrderStatus.SHIPPED,     # Awaiting Shipment
                11: OrderStatus.DELIVERED,   # Completed
                12: OrderStatus.PROCESSING,  # Awaiting Fulfillment
                13: OrderStatus.PROCESSING   # Manual Verification Required
            }
            
            # Transform line items
            order_items = []
            for item_data in raw_order.get("line_items", []):
                order_item = OrderItem(
                    item_id=str(item_data.get("id", "")),
                    order_id=str(raw_order.get("id", "")),
                    product_id=str(item_data.get("product_id", "")),
                    product_name=item_data.get("name", ""),
                    product_price=Decimal(str(item_data.get("price_inc_tax", item_data.get("base_price", "0")))),
                    quantity=item_data.get("quantity", 1),
                    subtotal=Decimal(str(item_data.get("total_inc_tax", item_data.get("base_total", "0")))),
                    total=Decimal(str(item_data.get("total_inc_tax", item_data.get("base_total", "0"))))
                )
                order_items.append(order_item)
            
            # Transform billing address as shipping address if shipping is not available
            shipping_address = None
            addr_data = raw_order.get("shipping_addresses")
            if addr_data and len(addr_data) > 0:
                addr = addr_data[0]  # Use first shipping address
            else:
                addr = raw_order.get("billing_address", {})
            
            if addr:
                shipping_address = Address(
                    customer_id=str(raw_order.get("customer_id", "")),
                    country=addr.get("country", ""),
                    region=addr.get("state", ""),
                    city=addr.get("city", ""),
                    street=f"{addr.get('street_1', '')} {addr.get('street_2', '')}".strip(),
                    house="",  # BigCommerce combines street and house
                    postal_code=addr.get("zip", "")
                )
            
            # Determine payment status from order status
            payment_status = PaymentStatus.PENDING
            order_status_id = raw_order.get("status_id", 1)
            if order_status_id in [10, 11, 2, 3]:  # Shipped, Completed, etc.
                payment_status = PaymentStatus.PAID
            elif order_status_id in [4]:  # Refunded
                payment_status = PaymentStatus.REFUNDED
            elif order_status_id in [5, 6]:  # Cancelled, Declined
                payment_status = PaymentStatus.FAILED
            
            return Order(
                order_id=str(raw_order.get("id", "")),
                customer_id=str(raw_order.get("customer_id", "")),
                status=status_mapping.get(order_status_id, OrderStatus.PENDING),
                payment_status=payment_status,
                items=order_items,
                subtotal=Decimal(str(raw_order.get("subtotal_inc_tax", raw_order.get("subtotal_ex_tax", "0")))),
                shipping_cost=Decimal(str(raw_order.get("shipping_cost_inc_tax", raw_order.get("base_shipping_cost", "0")))),
                tax_amount=Decimal(str(raw_order.get("total_tax", "0"))),
                total=Decimal(str(raw_order.get("total_inc_tax", raw_order.get("total_ex_tax", "0")))),
                shipping_address=shipping_address,
                created_at=datetime.fromisoformat(raw_order.get("date_created", "").replace("Z", "+00:00")) if raw_order.get("date_created") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_order.get("date_modified", "").replace("Z", "+00:00")) if raw_order.get("date_modified") else datetime.now(),
                notes=raw_order.get("customer_message", ""),
                source="bigcommerce"
            )
            
        except Exception as e:
            logger.error("Failed to transform BigCommerce order", error=str(e))
            return None
    
    def transform_product(self, raw_product: dict[str, Any]) -> Product | None:
        """Transform BigCommerce product data to unified format."""
        try:
            variant_data = raw_product.get("variant", {})
            
            # Use variant data if available, otherwise use product data
            price = variant_data.get("price") if variant_data else raw_product.get("price", "0")
            retail_price = variant_data.get("retail_price") if variant_data else raw_product.get("retail_price")
            inventory_level = variant_data.get("inventory_level") if variant_data else raw_product.get("inventory_level", 0)
            weight = variant_data.get("weight") if variant_data else raw_product.get("weight")
            sku = variant_data.get("sku") if variant_data else raw_product.get("sku", "")
            
            # Use variant ID as product ID if available for uniqueness
            product_id = variant_data.get("id") if variant_data else raw_product.get("id")
            
            # Get brand name
            brand = ""
            if raw_product.get("brand_id"):
                # In real implementation, would fetch brand data
                brand = f"Brand_{raw_product.get('brand_id')}"
            
            return Product(
                product_id=str(product_id),
                name=raw_product.get("name", ""),
                description=raw_product.get("description", ""),
                category=raw_product.get("type", ""),  # BigCommerce uses 'type' field
                brand=brand,
                price=Decimal(str(price)) if price else Decimal("0"),
                original_price=Decimal(str(retail_price)) if retail_price and retail_price != price else None,
                currency="USD",  # Should be configurable based on store settings
                weight=Decimal(str(weight)) if weight else None,
                in_stock=raw_product.get("availability", "") == "available" and inventory_level > 0,
                stock_quantity=inventory_level or 0,
                created_at=datetime.fromisoformat(raw_product.get("date_created", "").replace("Z", "+00:00")) if raw_product.get("date_created") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_product.get("date_modified", "").replace("Z", "+00:00")) if raw_product.get("date_modified") else datetime.now()
            )
            
        except Exception as e:
            logger.error("Failed to transform BigCommerce product", error=str(e))
            return None
    
    def transform_customer(self, raw_customer: dict[str, Any]) -> Customer | None:
        """Transform BigCommerce customer data to unified format."""
        try:
            return Customer(
                customer_id=str(raw_customer.get("id", "")),
                first_name=raw_customer.get("first_name", ""),
                last_name=raw_customer.get("last_name", ""),
                email=raw_customer.get("email"),
                phone=raw_customer.get("phone"),
                created_at=datetime.fromisoformat(raw_customer.get("date_created", "").replace("Z", "+00:00")) if raw_customer.get("date_created") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_customer.get("date_modified", "").replace("Z", "+00:00")) if raw_customer.get("date_modified") else datetime.now(),
                # BigCommerce doesn't provide order count and total spent in customer endpoint by default
                total_orders=0,  # Would need separate API call to get this
                total_spent=Decimal("0.00")  # Would need separate API call to get this
            )
            
        except Exception as e:
            logger.error("Failed to transform BigCommerce customer", error=str(e))
            return None