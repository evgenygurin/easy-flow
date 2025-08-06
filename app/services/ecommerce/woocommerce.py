"""WooCommerce e-commerce platform integration."""
import base64
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from app.models.ecommerce import Address, Customer, Order, OrderItem, OrderStatus, PaymentStatus, Product
from .base import APIResponse, PlatformAdapter

logger = structlog.get_logger()


class WooCommerceAdapter(PlatformAdapter):
    """WooCommerce e-commerce platform adapter with REST API support."""
    
    def __init__(self, credentials: dict[str, Any], config: dict[str, Any] | None = None):
        super().__init__(credentials, config)
        
        # Required credentials
        self.base_url = credentials["base_url"]  # e.g., "https://mystore.com"
        self.consumer_key = credentials["consumer_key"]
        self.consumer_secret = credentials["consumer_secret"]
        
        # API endpoints
        self.api_url = f"{self.base_url.rstrip('/')}/wp-json/wc/v3/"
        
        # Authentication - WooCommerce uses Basic Auth with consumer key/secret
        auth_string = f"{self.consumer_key}:{self.consumer_secret}"
        auth_bytes = auth_string.encode("ascii")
        auth_base64 = base64.b64encode(auth_bytes).decode("ascii")
        
        self.headers = {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/json"
        }
        
        # API version
        self.api_version = config.get("api_version", "v3")
    
    async def authenticate(self) -> APIResponse:
        """Test authentication by fetching system status."""
        try:
            response = await self.make_request(
                "GET",
                f"{self.api_url}system_status",
                headers=self.headers
            )
            
            if response.success and response.data:
                system_data = response.data
                logger.info(
                    "WooCommerce authentication successful",
                    site_url=system_data.get("settings", {}).get("site_url"),
                    wc_version=system_data.get("settings", {}).get("wc_version")
                )
                return APIResponse(
                    success=True,
                    data={"system_status": system_data}
                )
            else:
                return APIResponse(
                    success=False,
                    error_message="Authentication failed: Invalid response"
                )
                
        except Exception as e:
            logger.error("WooCommerce authentication failed", error=str(e))
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
        """Fetch orders from WooCommerce using REST API."""
        try:
            params = {
                "per_page": min(limit, 100),  # WooCommerce max limit is 100
                "page": (offset // limit) + 1,
                "status": filters.get("status", "any") if filters else "any",
            }
            
            if filters:
                if filters.get("after"):
                    params["after"] = filters["after"]
                if filters.get("before"):
                    params["before"] = filters["before"]
            
            response = await self.make_request(
                "GET",
                f"{self.api_url}orders",
                headers=self.headers,
                params=params
            )
            
            if response.success and response.data:
                orders_data = response.data
                transformed_orders = []
                
                for order_data in orders_data:
                    try:
                        transformed_order = self.transform_order(order_data)
                        if transformed_order:
                            transformed_orders.append(transformed_order)
                    except Exception as e:
                        logger.warning("Failed to transform WooCommerce order", order_id=order_data.get("id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_orders)} orders from WooCommerce")
                return APIResponse(
                    success=True,
                    data=transformed_orders,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch WooCommerce orders", error=str(e))
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
        """Fetch products from WooCommerce using REST API."""
        try:
            params = {
                "per_page": min(limit, 100),
                "page": (offset // limit) + 1,
                "status": filters.get("status", "publish") if filters else "publish",
            }
            
            if filters:
                if filters.get("category"):
                    params["category"] = filters["category"]
                if filters.get("search"):
                    params["search"] = filters["search"]
            
            response = await self.make_request(
                "GET",
                f"{self.api_url}products",
                headers=self.headers,
                params=params
            )
            
            if response.success and response.data:
                products_data = response.data
                transformed_products = []
                
                for product_data in products_data:
                    try:
                        # Handle product variations
                        if product_data.get("type") == "variable":
                            # Fetch variations for variable products
                            variations_response = await self.make_request(
                                "GET",
                                f"{self.api_url}products/{product_data['id']}/variations",
                                headers=self.headers,
                                params={"per_page": 100}
                            )
                            
                            if variations_response.success and variations_response.data:
                                for variation_data in variations_response.data:
                                    combined_data = {**product_data, "variation": variation_data}
                                    transformed_product = self.transform_product(combined_data)
                                    if transformed_product:
                                        transformed_products.append(transformed_product)
                            else:
                                # Fallback to main product if variations fetch fails
                                transformed_product = self.transform_product(product_data)
                                if transformed_product:
                                    transformed_products.append(transformed_product)
                        else:
                            # Simple product
                            transformed_product = self.transform_product(product_data)
                            if transformed_product:
                                transformed_products.append(transformed_product)
                                
                    except Exception as e:
                        logger.warning("Failed to transform WooCommerce product", product_id=product_data.get("id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_products)} products from WooCommerce")
                return APIResponse(
                    success=True,
                    data=transformed_products,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch WooCommerce products", error=str(e))
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
        """Fetch customers from WooCommerce using REST API."""
        try:
            params = {
                "per_page": min(limit, 100),
                "page": (offset // limit) + 1,
            }
            
            if filters:
                if filters.get("email"):
                    params["email"] = filters["email"]
                if filters.get("search"):
                    params["search"] = filters["search"]
            
            response = await self.make_request(
                "GET",
                f"{self.api_url}customers",
                headers=self.headers,
                params=params
            )
            
            if response.success and response.data:
                customers_data = response.data
                transformed_customers = []
                
                for customer_data in customers_data:
                    try:
                        transformed_customer = self.transform_customer(customer_data)
                        if transformed_customer:
                            transformed_customers.append(transformed_customer)
                    except Exception as e:
                        logger.warning("Failed to transform WooCommerce customer", customer_id=customer_data.get("id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_customers)} customers from WooCommerce")
                return APIResponse(
                    success=True,
                    data=transformed_customers,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch WooCommerce customers", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Error fetching customers: {str(e)}"
            )
    
    async def update_order_status(self, order_id: str, status: str) -> APIResponse:
        """Update order status in WooCommerce."""
        try:
            # Map our status to WooCommerce status
            status_mapping = {
                "pending": "pending",
                "processing": "processing",
                "shipped": "processing",  # WooCommerce doesn't have shipped, use processing
                "delivered": "completed",
                "cancelled": "cancelled",
                "returned": "refunded"
            }
            
            wc_status = status_mapping.get(status, status)
            
            update_data = {
                "status": wc_status
            }
            
            response = await self.make_request(
                "PUT",
                f"{self.api_url}orders/{order_id}",
                headers=self.headers,
                json_data=update_data
            )
            
            if response.success:
                logger.info(f"Updated WooCommerce order {order_id} status to {wc_status}")
            
            return response
            
        except Exception as e:
            logger.error("Failed to update WooCommerce order status", order_id=order_id, error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Error updating order status: {str(e)}"
            )
    
    async def handle_webhook(self, payload: dict[str, Any]) -> APIResponse:
        """Handle WooCommerce webhook events."""
        try:
            event_type = payload.get("event_type", "unknown")
            
            if event_type in ["order.created", "order.updated"]:
                order_data = payload.get("data", {})
                transformed_order = self.transform_order(order_data)
                
                if transformed_order:
                    logger.info(f"Processed WooCommerce {event_type} webhook", order_id=transformed_order.order_id)
                    return APIResponse(success=True, data={"order": transformed_order})
            
            elif event_type == "order.completed":
                order_data = payload.get("data", {})
                order_id = order_data.get("id")
                logger.info(f"WooCommerce order {order_id} completed")
                return APIResponse(success=True, data={"order_id": order_id, "status": "completed"})
            
            elif event_type in ["product.created", "product.updated"]:
                product_data = payload.get("data", {})
                transformed_product = self.transform_product(product_data)
                
                if transformed_product:
                    logger.info(f"Processed WooCommerce {event_type} webhook", product_id=transformed_product.product_id)
                    return APIResponse(success=True, data={"product": transformed_product})
            
            elif event_type in ["customer.created", "customer.updated"]:
                customer_data = payload.get("data", {})
                transformed_customer = self.transform_customer(customer_data)
                
                if transformed_customer:
                    logger.info(f"Processed WooCommerce {event_type} webhook", customer_id=transformed_customer.customer_id)
                    return APIResponse(success=True, data={"customer": transformed_customer})
            
            else:
                logger.info(f"Unhandled WooCommerce webhook event: {event_type}")
                return APIResponse(success=True, data={"message": f"Event {event_type} acknowledged"})
                
        except Exception as e:
            logger.error("Failed to process WooCommerce webhook", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Webhook processing error: {str(e)}"
            )
    
    def transform_order(self, raw_order: dict[str, Any]) -> Order | None:
        """Transform WooCommerce order data to unified format."""
        try:
            # Map WooCommerce status to our enum
            status_mapping = {
                "pending": OrderStatus.PENDING,
                "processing": OrderStatus.PROCESSING,
                "on-hold": OrderStatus.PENDING,
                "completed": OrderStatus.DELIVERED,
                "cancelled": OrderStatus.CANCELLED,
                "refunded": OrderStatus.RETURNED,
                "failed": OrderStatus.CANCELLED
            }
            
            payment_status_mapping = {
                "pending": PaymentStatus.PENDING,
                "processing": PaymentStatus.PENDING,
                "on-hold": PaymentStatus.PENDING,
                "completed": PaymentStatus.PAID,
                "cancelled": PaymentStatus.FAILED,
                "refunded": PaymentStatus.REFUNDED,
                "failed": PaymentStatus.FAILED
            }
            
            # Transform line items
            order_items = []
            for item_data in raw_order.get("line_items", []):
                order_item = OrderItem(
                    item_id=str(item_data.get("id", "")),
                    order_id=str(raw_order.get("id", "")),
                    product_id=str(item_data.get("product_id", "")),
                    product_name=item_data.get("name", ""),
                    product_price=Decimal(str(item_data.get("price", "0"))),
                    quantity=item_data.get("quantity", 1),
                    subtotal=Decimal(str(item_data.get("subtotal", "0"))),
                    total=Decimal(str(item_data.get("total", "0")))
                )
                order_items.append(order_item)
            
            # Transform shipping address
            shipping_address = None
            if raw_order.get("shipping"):
                addr_data = raw_order["shipping"]
                shipping_address = Address(
                    customer_id=str(raw_order.get("customer_id", "")),
                    country=addr_data.get("country", ""),
                    region=addr_data.get("state", ""),
                    city=addr_data.get("city", ""),
                    street=f"{addr_data.get('address_1', '')} {addr_data.get('address_2', '')}".strip(),
                    house="",  # WooCommerce combines street and house
                    postal_code=addr_data.get("postcode", "")
                )
            
            return Order(
                order_id=str(raw_order.get("id", "")),
                customer_id=str(raw_order.get("customer_id", "")),
                status=status_mapping.get(raw_order.get("status", "pending"), OrderStatus.PENDING),
                payment_status=payment_status_mapping.get(raw_order.get("status", "pending"), PaymentStatus.PENDING),
                items=order_items,
                subtotal=Decimal(str(raw_order.get("subtotal", "0"))),
                shipping_cost=Decimal(str(raw_order.get("shipping_total", "0"))),
                tax_amount=Decimal(str(raw_order.get("total_tax", "0"))),
                total=Decimal(str(raw_order.get("total", "0"))),
                shipping_address=shipping_address,
                created_at=datetime.fromisoformat(raw_order.get("date_created", "").replace("Z", "+00:00")) if raw_order.get("date_created") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_order.get("date_modified", "").replace("Z", "+00:00")) if raw_order.get("date_modified") else datetime.now(),
                notes=raw_order.get("customer_note"),
                source="woocommerce"
            )
            
        except Exception as e:
            logger.error("Failed to transform WooCommerce order", error=str(e))
            return None
    
    def transform_product(self, raw_product: dict[str, Any]) -> Product | None:
        """Transform WooCommerce product data to unified format."""
        try:
            variation_data = raw_product.get("variation", {})
            
            # Use variation data if available, otherwise use product data
            price = variation_data.get("price") if variation_data else raw_product.get("price", "0")
            regular_price = variation_data.get("regular_price") if variation_data else raw_product.get("regular_price", "0")
            stock_quantity = variation_data.get("stock_quantity") if variation_data else raw_product.get("stock_quantity", 0)
            in_stock = variation_data.get("in_stock", True) if variation_data else raw_product.get("in_stock", True)
            weight = variation_data.get("weight") if variation_data else raw_product.get("weight")
            sku = variation_data.get("sku") if variation_data else raw_product.get("sku", "")
            
            # Use variation ID as product ID if available for uniqueness
            product_id = variation_data.get("id") if variation_data else raw_product.get("id")
            
            # Get category names
            category_names = [cat.get("name", "") for cat in raw_product.get("categories", [])]
            category = ", ".join(category_names) if category_names else ""
            
            return Product(
                product_id=str(product_id),
                name=raw_product.get("name", ""),
                description=raw_product.get("description", ""),
                category=category,
                brand="",  # WooCommerce doesn't have a standard brand field
                price=Decimal(str(price)) if price else Decimal("0"),
                original_price=Decimal(str(regular_price)) if regular_price and regular_price != price else None,
                currency="USD",  # Should be configurable based on WooCommerce settings
                weight=Decimal(str(weight)) if weight else None,
                in_stock=in_stock and (stock_quantity is None or stock_quantity > 0),
                stock_quantity=stock_quantity or 0,
                created_at=datetime.fromisoformat(raw_product.get("date_created", "").replace("Z", "+00:00")) if raw_product.get("date_created") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_product.get("date_modified", "").replace("Z", "+00:00")) if raw_product.get("date_modified") else datetime.now()
            )
            
        except Exception as e:
            logger.error("Failed to transform WooCommerce product", error=str(e))
            return None
    
    def transform_customer(self, raw_customer: dict[str, Any]) -> Customer | None:
        """Transform WooCommerce customer data to unified format."""
        try:
            return Customer(
                customer_id=str(raw_customer.get("id", "")),
                first_name=raw_customer.get("first_name", ""),
                last_name=raw_customer.get("last_name", ""),
                email=raw_customer.get("email"),
                phone=raw_customer.get("billing", {}).get("phone") if raw_customer.get("billing") else None,
                created_at=datetime.fromisoformat(raw_customer.get("date_created", "").replace("Z", "+00:00")) if raw_customer.get("date_created") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_customer.get("date_modified", "").replace("Z", "+00:00")) if raw_customer.get("date_modified") else datetime.now(),
                total_orders=raw_customer.get("orders_count", 0),
                total_spent=Decimal(str(raw_customer.get("total_spent", "0")))
            )
            
        except Exception as e:
            logger.error("Failed to transform WooCommerce customer", error=str(e))
            return None