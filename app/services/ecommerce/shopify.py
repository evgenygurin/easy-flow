"""Shopify e-commerce platform integration."""
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

import structlog

from app.models.ecommerce import Address, Customer, Order, OrderItem, OrderStatus, PaymentStatus, Product
from .base import APIResponse, PlatformAdapter

logger = structlog.get_logger()


class ShopifyAdapter(PlatformAdapter):
    """Shopify e-commerce platform adapter with GraphQL/REST API support."""
    
    def __init__(self, credentials: dict[str, Any], config: dict[str, Any] | None = None):
        super().__init__(credentials, config)
        
        # Required credentials
        self.shop_domain = credentials["shop_domain"]  # e.g., "myshop.myshopify.com"
        self.access_token = credentials["access_token"]  # Admin API access token
        
        # API endpoints
        self.base_url = f"https://{self.shop_domain}"
        self.rest_api_url = f"{self.base_url}/admin/api/2023-10/"
        self.graphql_api_url = f"{self.base_url}/admin/api/2023-10/graphql.json"
        
        # API version
        self.api_version = config.get("api_version", "2023-10")
        
        # Default headers
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }
    
    async def authenticate(self) -> APIResponse:
        """Test authentication by fetching shop information."""
        try:
            response = await self.make_request(
                "GET",
                f"{self.rest_api_url}shop.json",
                headers=self.headers
            )
            
            if response.success and response.data:
                shop_data = response.data.get("shop", {})
                logger.info(
                    "Shopify authentication successful",
                    shop_name=shop_data.get("name"),
                    shop_domain=shop_data.get("domain")
                )
                return APIResponse(
                    success=True,
                    data={"shop": shop_data}
                )
            else:
                return APIResponse(
                    success=False,
                    error_message="Authentication failed: Invalid response"
                )
                
        except Exception as e:
            logger.error("Shopify authentication failed", error=str(e))
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
        """Fetch orders from Shopify using REST API."""
        try:
            params = {
                "limit": min(limit, 250),  # Shopify max limit is 250
                "status": filters.get("status", "any") if filters else "any",
            }
            
            # Add pagination using since_id instead of offset for better performance
            if offset > 0 and filters and filters.get("since_id"):
                params["since_id"] = filters["since_id"]
            
            response = await self.make_request(
                "GET",
                f"{self.rest_api_url}orders.json",
                headers=self.headers,
                params=params
            )
            
            if response.success and response.data:
                orders_data = response.data.get("orders", [])
                transformed_orders = []
                
                for order_data in orders_data:
                    try:
                        transformed_order = self.transform_order(order_data)
                        if transformed_order:
                            transformed_orders.append(transformed_order)
                    except Exception as e:
                        logger.warning("Failed to transform Shopify order", order_id=order_data.get("id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_orders)} orders from Shopify")
                return APIResponse(
                    success=True,
                    data=transformed_orders,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch Shopify orders", error=str(e))
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
        """Fetch products from Shopify using GraphQL API."""
        try:
            # GraphQL query for products
            query = """
            query getProducts($first: Int!, $after: String) {
                products(first: $first, after: $after) {
                    edges {
                        node {
                            id
                            title
                            description
                            handle
                            productType
                            vendor
                            createdAt
                            updatedAt
                            status
                            variants(first: 10) {
                                edges {
                                    node {
                                        id
                                        title
                                        price
                                        compareAtPrice
                                        inventoryQuantity
                                        weight
                                        weightUnit
                                        sku
                                        barcode
                                    }
                                }
                            }
                            images(first: 5) {
                                edges {
                                    node {
                                        id
                                        url
                                        altText
                                    }
                                }
                            }
                        }
                        cursor
                    }
                    pageInfo {
                        hasNextPage
                        hasPreviousPage
                    }
                }
            }
            """
            
            variables = {
                "first": min(limit, 250),
                "after": filters.get("after") if filters else None
            }
            
            response = await self.make_request(
                "POST",
                self.graphql_api_url,
                headers=self.headers,
                json_data={"query": query, "variables": variables}
            )
            
            if response.success and response.data:
                products_data = response.data.get("data", {}).get("products", {}).get("edges", [])
                transformed_products = []
                
                for product_edge in products_data:
                    try:
                        product_node = product_edge["node"]
                        # For each variant, create a separate product
                        variants = product_node.get("variants", {}).get("edges", [])
                        
                        if variants:
                            for variant_edge in variants:
                                variant_node = variant_edge["node"]
                                combined_data = {**product_node, "variant": variant_node}
                                transformed_product = self.transform_product(combined_data)
                                if transformed_product:
                                    transformed_products.append(transformed_product)
                        else:
                            # Product without variants
                            transformed_product = self.transform_product(product_node)
                            if transformed_product:
                                transformed_products.append(transformed_product)
                                
                    except Exception as e:
                        logger.warning("Failed to transform Shopify product", product_id=product_edge.get("node", {}).get("id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_products)} products from Shopify")
                return APIResponse(
                    success=True,
                    data=transformed_products,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch Shopify products", error=str(e))
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
        """Fetch customers from Shopify using REST API."""
        try:
            params = {
                "limit": min(limit, 250),
            }
            
            if offset > 0 and filters and filters.get("since_id"):
                params["since_id"] = filters["since_id"]
            
            response = await self.make_request(
                "GET",
                f"{self.rest_api_url}customers.json",
                headers=self.headers,
                params=params
            )
            
            if response.success and response.data:
                customers_data = response.data.get("customers", [])
                transformed_customers = []
                
                for customer_data in customers_data:
                    try:
                        transformed_customer = self.transform_customer(customer_data)
                        if transformed_customer:
                            transformed_customers.append(transformed_customer)
                    except Exception as e:
                        logger.warning("Failed to transform Shopify customer", customer_id=customer_data.get("id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_customers)} customers from Shopify")
                return APIResponse(
                    success=True,
                    data=transformed_customers,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch Shopify customers", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Error fetching customers: {str(e)}"
            )
    
    async def update_order_status(self, order_id: str, status: str) -> APIResponse:
        """Update order fulfillment status in Shopify."""
        try:
            # Shopify uses fulfillment API for order status updates
            fulfillment_data = {
                "fulfillment": {
                    "location_id": self.config.get("location_id"),
                    "tracking_number": None,
                    "notify_customer": True
                }
            }
            
            response = await self.make_request(
                "POST",
                f"{self.rest_api_url}orders/{order_id}/fulfillments.json",
                headers=self.headers,
                json_data=fulfillment_data
            )
            
            if response.success:
                logger.info(f"Updated Shopify order {order_id} status to {status}")
            
            return response
            
        except Exception as e:
            logger.error("Failed to update Shopify order status", order_id=order_id, error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Error updating order status: {str(e)}"
            )
    
    async def handle_webhook(self, payload: dict[str, Any]) -> APIResponse:
        """Handle Shopify webhook events."""
        try:
            # Shopify webhooks include the event type in the headers (X-Shopify-Topic)
            event_type = payload.get("event_type", "unknown")
            
            if event_type in ["orders/create", "orders/updated"]:
                order_data = payload.get("data", {})
                transformed_order = self.transform_order(order_data)
                
                if transformed_order:
                    logger.info(f"Processed Shopify {event_type} webhook", order_id=transformed_order.order_id)
                    return APIResponse(success=True, data={"order": transformed_order})
            
            elif event_type == "orders/paid":
                order_data = payload.get("data", {})
                order_id = order_data.get("id")
                logger.info(f"Shopify order {order_id} payment confirmed")
                return APIResponse(success=True, data={"order_id": order_id, "status": "paid"})
            
            elif event_type in ["products/create", "products/update"]:
                product_data = payload.get("data", {})
                transformed_product = self.transform_product(product_data)
                
                if transformed_product:
                    logger.info(f"Processed Shopify {event_type} webhook", product_id=transformed_product.product_id)
                    return APIResponse(success=True, data={"product": transformed_product})
            
            else:
                logger.info(f"Unhandled Shopify webhook event: {event_type}")
                return APIResponse(success=True, data={"message": f"Event {event_type} acknowledged"})
                
        except Exception as e:
            logger.error("Failed to process Shopify webhook", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Webhook processing error: {str(e)}"
            )
    
    def transform_order(self, raw_order: dict[str, Any]) -> Order | None:
        """Transform Shopify order data to unified format."""
        try:
            # Map Shopify status to our enum
            status_mapping = {
                "open": OrderStatus.PROCESSING,
                "closed": OrderStatus.DELIVERED,
                "cancelled": OrderStatus.CANCELLED
            }
            
            payment_status_mapping = {
                "pending": PaymentStatus.PENDING,
                "paid": PaymentStatus.PAID,
                "refunded": PaymentStatus.REFUNDED,
                "partially_refunded": PaymentStatus.PARTIALLY_REFUNDED,
                "voided": PaymentStatus.FAILED
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
                    subtotal=Decimal(str(item_data.get("price", "0"))) * item_data.get("quantity", 1),
                    total=Decimal(str(item_data.get("price", "0"))) * item_data.get("quantity", 1)
                )
                order_items.append(order_item)
            
            # Transform shipping address
            shipping_address = None
            if raw_order.get("shipping_address"):
                addr_data = raw_order["shipping_address"]
                shipping_address = Address(
                    customer_id=str(raw_order.get("customer", {}).get("id", "")),
                    country=addr_data.get("country", ""),
                    region=addr_data.get("province", ""),
                    city=addr_data.get("city", ""),
                    street=f"{addr_data.get('address1', '')} {addr_data.get('address2', '')}".strip(),
                    house="",  # Shopify combines street and house
                    postal_code=addr_data.get("zip", "")
                )
            
            return Order(
                order_id=str(raw_order.get("id", "")),
                customer_id=str(raw_order.get("customer", {}).get("id", "")) if raw_order.get("customer") else "",
                status=status_mapping.get(raw_order.get("fulfillment_status", "open"), OrderStatus.PROCESSING),
                payment_status=payment_status_mapping.get(raw_order.get("financial_status", "pending"), PaymentStatus.PENDING),
                items=order_items,
                subtotal=Decimal(str(raw_order.get("subtotal_price", "0"))),
                shipping_cost=Decimal(str(raw_order.get("total_shipping_price_set", {}).get("shop_money", {}).get("amount", "0"))),
                tax_amount=Decimal(str(raw_order.get("total_tax", "0"))),
                total=Decimal(str(raw_order.get("total_price", "0"))),
                shipping_address=shipping_address,
                tracking_number=raw_order.get("tracking_number"),
                created_at=datetime.fromisoformat(raw_order.get("created_at", "").replace("Z", "+00:00")) if raw_order.get("created_at") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_order.get("updated_at", "").replace("Z", "+00:00")) if raw_order.get("updated_at") else datetime.now(),
                notes=raw_order.get("note"),
                source="shopify"
            )
            
        except Exception as e:
            logger.error("Failed to transform Shopify order", error=str(e))
            return None
    
    def transform_product(self, raw_product: dict[str, Any]) -> Product | None:
        """Transform Shopify product data to unified format."""
        try:
            variant_data = raw_product.get("variant", {})
            
            # Use variant data if available, otherwise use product data
            price = variant_data.get("price") or raw_product.get("variants", {}).get("edges", [{}])[0].get("node", {}).get("price", "0")
            compare_at_price = variant_data.get("compareAtPrice") or variant_data.get("compare_at_price")
            inventory_quantity = variant_data.get("inventoryQuantity", variant_data.get("inventory_quantity", 0))
            weight = variant_data.get("weight", 0)
            sku = variant_data.get("sku", "")
            
            # Extract numeric ID from GraphQL ID
            product_id = raw_product.get("id", "").split("/")[-1] if "gid://shopify" in raw_product.get("id", "") else raw_product.get("id", "")
            variant_id = variant_data.get("id", "").split("/")[-1] if "gid://shopify" in variant_data.get("id", "") else variant_data.get("id", "")
            
            # Use variant ID as product ID if available for uniqueness
            final_product_id = variant_id if variant_id else product_id
            
            return Product(
                product_id=str(final_product_id),
                name=raw_product.get("title", ""),
                description=raw_product.get("description", ""),
                category=raw_product.get("productType", raw_product.get("product_type", "")),
                brand=raw_product.get("vendor", ""),
                price=Decimal(str(price)),
                original_price=Decimal(str(compare_at_price)) if compare_at_price else None,
                currency="USD",  # Shopify defaults, should be configurable
                weight=Decimal(str(weight)) if weight else None,
                in_stock=inventory_quantity > 0,
                stock_quantity=inventory_quantity or 0,
                created_at=datetime.fromisoformat(raw_product.get("createdAt", raw_product.get("created_at", "")).replace("Z", "+00:00")) if raw_product.get("createdAt") or raw_product.get("created_at") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_product.get("updatedAt", raw_product.get("updated_at", "")).replace("Z", "+00:00")) if raw_product.get("updatedAt") or raw_product.get("updated_at") else datetime.now()
            )
            
        except Exception as e:
            logger.error("Failed to transform Shopify product", error=str(e))
            return None
    
    def transform_customer(self, raw_customer: dict[str, Any]) -> Customer | None:
        """Transform Shopify customer data to unified format."""
        try:
            return Customer(
                customer_id=str(raw_customer.get("id", "")),
                first_name=raw_customer.get("first_name", ""),
                last_name=raw_customer.get("last_name", ""),
                email=raw_customer.get("email"),
                phone=raw_customer.get("phone"),
                created_at=datetime.fromisoformat(raw_customer.get("created_at", "").replace("Z", "+00:00")) if raw_customer.get("created_at") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_customer.get("updated_at", "").replace("Z", "+00:00")) if raw_customer.get("updated_at") else datetime.now(),
                total_orders=raw_customer.get("orders_count", 0),
                total_spent=Decimal(str(raw_customer.get("total_spent", "0")))
            )
            
        except Exception as e:
            logger.error("Failed to transform Shopify customer", error=str(e))
            return None