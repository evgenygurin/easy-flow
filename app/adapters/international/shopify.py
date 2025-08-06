"""Shopify e-commerce platform integration adapter."""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from app.adapters.base import PlatformAdapter, APIResponse, SyncResult, RateLimitConfig
from app.models.ecommerce import Customer, Order, Product

logger = structlog.get_logger()


class ShopifyAdapter(PlatformAdapter):
    """Shopify e-commerce platform integration adapter with GraphQL/REST hybrid."""
    
    def __init__(
        self,
        shop_domain: str,
        access_token: str,
        api_version: str = "2023-10",
        use_graphql: bool = True
    ):
        """Initialize Shopify adapter.
        
        Args:
        ----
            shop_domain: Shopify shop domain (e.g., 'myshop.myshopify.com')
            access_token: Shopify access token
            api_version: Shopify API version
            use_graphql: Whether to use GraphQL API for complex queries
        """
        base_url = f"https://{shop_domain}"
        
        super().__init__(
            api_key=access_token,
            base_url=base_url,
            platform_name="shopify",
            rate_limit_config=RateLimitConfig(
                requests_per_minute=40,  # Shopify Plus has higher limits
                requests_per_hour=2400,
                burst_size=10
            )
        )
        
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.api_version = api_version
        self.use_graphql = use_graphql
        
        # Shopify order status mapping
        self.order_status_mapping = {
            "pending": "pending",
            "authorized": "confirmed", 
            "partially_paid": "processing",
            "paid": "processing",
            "partially_fulfilled": "shipped",
            "fulfilled": "delivered",
            "cancelled": "cancelled",
            "refunded": "returned"
        }
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Shopify-Access-Token": self.access_token
        }
    
    async def _make_graphql_request(self, query: str, variables: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Make a GraphQL request to Shopify."""
        return await self._make_request(
            method="POST",
            url=f"/admin/api/{self.api_version}/graphql.json",
            data={
                "query": query,
                "variables": variables or {}
            }
        )
    
    async def test_connection(self) -> APIResponse:
        """Test connection to Shopify API."""
        try:
            # Test with shop info endpoint
            response = await self._make_request(
                method="GET",
                url=f"/admin/api/{self.api_version}/shop.json"
            )
            
            if response.success:
                logger.info("Shopify connection test successful")
            
            return response
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0,
                platform=self.platform_name
            )
    
    async def sync_orders(self, limit: int = 100) -> SyncResult:
        """Sync orders from Shopify."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            if self.use_graphql:
                # Use GraphQL for more efficient data fetching
                query = """
                query getOrders($first: Int!) {
                    orders(first: $first) {
                        edges {
                            node {
                                id
                                name
                                email
                                createdAt
                                updatedAt
                                totalPriceSet {
                                    shopMoney {
                                        amount
                                        currencyCode
                                    }
                                }
                                displayFulfillmentStatus
                                displayFinancialStatus
                                customer {
                                    id
                                    firstName
                                    lastName
                                    email
                                    phone
                                }
                                lineItems(first: 10) {
                                    edges {
                                        node {
                                            id
                                            name
                                            quantity
                                            variant {
                                                id
                                                title
                                                price
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                """
                
                response = await self._make_graphql_request(query, {"first": min(limit, 250)})
                
                if not response.success:
                    errors.append(f"GraphQL query failed: {response.error}")
                    return SyncResult(
                        platform=self.platform_name,
                        operation="orders",
                        records_processed=processed,
                        records_success=success,
                        records_failed=processed - success,
                        errors=errors,
                        duration_seconds=(datetime.now() - start_time).total_seconds()
                    )
                
                orders_data = response.data.get("data", {}).get("orders", {}).get("edges", [])
                orders_data = [edge["node"] for edge in orders_data]
                
            else:
                # Use REST API
                response = await self._make_request(
                    method="GET",
                    url=f"/admin/api/{self.api_version}/orders.json",
                    params={
                        "limit": min(limit, 250),
                        "status": "any"
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
                
                orders_data = response.data.get("orders", [])
            
            for order_data in orders_data:
                processed += 1
                try:
                    # Transform Shopify order to internal Order model
                    order = await self._transform_order(order_data, is_graphql=self.use_graphql)
                    
                    logger.info(
                        "Synchronized Shopify order",
                        shopify_order_id=order_data.get("id"),
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
        """Sync products from Shopify catalog."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            if self.use_graphql:
                # Use GraphQL for products with variants
                query = """
                query getProducts($first: Int!) {
                    products(first: $first) {
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
                                variants(first: 10) {
                                    edges {
                                        node {
                                            id
                                            title
                                            price
                                            inventoryQuantity
                                            weight
                                            weightUnit
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
                        }
                    }
                }
                """
                
                response = await self._make_graphql_request(query, {"first": min(limit, 250)})
                
                if not response.success:
                    errors.append(f"GraphQL query failed: {response.error}")
                    return SyncResult(
                        platform=self.platform_name,
                        operation="products",
                        records_processed=processed,
                        records_success=success,
                        records_failed=processed - success,
                        errors=errors,
                        duration_seconds=(datetime.now() - start_time).total_seconds()
                    )
                
                products_data = response.data.get("data", {}).get("products", {}).get("edges", [])
                products_data = [edge["node"] for edge in products_data]
                
            else:
                # Use REST API
                response = await self._make_request(
                    method="GET",
                    url=f"/admin/api/{self.api_version}/products.json",
                    params={
                        "limit": min(limit, 250),
                        "fields": "id,title,body_html,handle,product_type,vendor,created_at,updated_at,variants"
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
                
                products_data = response.data.get("products", [])
            
            for product_data in products_data:
                processed += 1
                try:
                    # Transform Shopify product to internal Product model
                    product = await self._transform_product(product_data, is_graphql=self.use_graphql)
                    
                    logger.info(
                        "Synchronized Shopify product",
                        shopify_product_id=product_data.get("id"),
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
        """Sync customers from Shopify."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get customers from Shopify
            response = await self._make_request(
                method="GET",
                url=f"/admin/api/{self.api_version}/customers.json",
                params={
                    "limit": min(limit, 250),
                    "fields": "id,first_name,last_name,email,phone,created_at,updated_at,orders_count,total_spent"
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
            
            customers_data = response.data.get("customers", [])
            
            for customer_data in customers_data:
                processed += 1
                try:
                    # Transform Shopify customer to internal Customer model
                    customer = await self._transform_customer(customer_data)
                    
                    logger.info(
                        "Synchronized Shopify customer",
                        shopify_customer_id=customer_data.get("id"),
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
        """Handle Shopify webhook events."""
        try:
            # Shopify webhook headers contain the topic
            # In practice, this would be passed via headers in the webhook call
            topic = payload.get("topic") or "unknown"
            
            logger.info("Processing Shopify webhook", topic=topic)
            
            if "orders/" in topic:
                # Order-related webhooks
                if topic == "orders/create":
                    await self._handle_order_created(payload)
                elif topic == "orders/updated":
                    await self._handle_order_updated(payload)
                elif topic == "orders/cancelled":
                    await self._handle_order_cancelled(payload)
            
            elif "products/" in topic:
                # Product-related webhooks
                if topic == "products/create":
                    await self._handle_product_created(payload)
                elif topic == "products/update":
                    await self._handle_product_updated(payload)
            
            elif "customers/" in topic:
                # Customer-related webhooks
                if topic == "customers/create":
                    await self._handle_customer_created(payload)
                elif topic == "customers/update":
                    await self._handle_customer_updated(payload)
            
            return True
            
        except Exception as e:
            logger.error("Shopify webhook processing failed", error=str(e))
            return False
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify Shopify webhook signature."""
        return self._verify_hmac_sha256(payload, signature, secret)
    
    async def _transform_order(self, order_data: Dict[str, Any], is_graphql: bool = False) -> Order:
        """Transform Shopify order to Order model."""
        from decimal import Decimal
        
        if is_graphql:
            # GraphQL format
            order_id = order_data.get("id", "").replace("gid://shopify/Order/", "")
            financial_status = order_data.get("displayFinancialStatus", "")
            fulfillment_status = order_data.get("displayFulfillmentStatus", "")
            
            # Parse total price from GraphQL format
            total_price = Decimal("0.00")
            price_set = order_data.get("totalPriceSet", {}).get("shopMoney", {})
            if price_set.get("amount"):
                try:
                    total_price = Decimal(str(price_set["amount"]))
                except:
                    pass
            
            # Parse creation date
            created_at = datetime.now()
            if order_data.get("createdAt"):
                try:
                    created_at = datetime.fromisoformat(order_data["createdAt"].replace("Z", "+00:00"))
                except:
                    pass
            
            customer_data = order_data.get("customer", {})
            customer_id = customer_data.get("id", "").replace("gid://shopify/Customer/", "") if customer_data else "unknown"
        
        else:
            # REST API format
            order_id = str(order_data.get("id", ""))
            financial_status = order_data.get("financial_status", "")
            fulfillment_status = order_data.get("fulfillment_status", "")
            
            # Parse total price
            total_price = Decimal("0.00")
            if order_data.get("total_price"):
                try:
                    total_price = Decimal(str(order_data["total_price"]))
                except:
                    pass
            
            # Parse creation date
            created_at = datetime.now()
            if order_data.get("created_at"):
                try:
                    created_at = datetime.fromisoformat(order_data["created_at"].replace("Z", "+00:00"))
                except:
                    pass
            
            customer_id = str(order_data.get("customer", {}).get("id", "unknown"))
        
        # Map status
        status = "pending"
        if fulfillment_status:
            status = self.order_status_mapping.get(fulfillment_status, "pending")
        elif financial_status:
            status = self.order_status_mapping.get(financial_status, "pending")
        
        return Order(
            order_id=f"shopify_{order_id}",
            customer_id=f"shopify_{customer_id}",
            status=status,
            subtotal=total_price,
            total=total_price,
            created_at=created_at,
            source="shopify",
            notes=order_data.get("note", "")
        )
    
    async def _transform_product(self, product_data: Dict[str, Any], is_graphql: bool = False) -> Product:
        """Transform Shopify product to Product model."""
        from decimal import Decimal
        
        if is_graphql:
            # GraphQL format
            product_id = product_data.get("id", "").replace("gid://shopify/Product/", "")
            title = product_data.get("title", "")
            description = product_data.get("description", "")
            product_type = product_data.get("productType", "")
            vendor = product_data.get("vendor", "")
            
            # Get price from first variant
            variants = product_data.get("variants", {}).get("edges", [])
            price = Decimal("0.00")
            stock_quantity = 0
            
            if variants:
                first_variant = variants[0]["node"]
                if first_variant.get("price"):
                    try:
                        price = Decimal(str(first_variant["price"]))
                    except:
                        pass
                
                if first_variant.get("inventoryQuantity"):
                    try:
                        stock_quantity = int(first_variant["inventoryQuantity"])
                    except:
                        pass
        
        else:
            # REST API format
            product_id = str(product_data.get("id", ""))
            title = product_data.get("title", "")
            description = product_data.get("body_html", "")
            product_type = product_data.get("product_type", "")
            vendor = product_data.get("vendor", "")
            
            # Get price from first variant
            variants = product_data.get("variants", [])
            price = Decimal("0.00")
            stock_quantity = 0
            
            if variants:
                first_variant = variants[0]
                if first_variant.get("price"):
                    try:
                        price = Decimal(str(first_variant["price"]))
                    except:
                        pass
                
                if first_variant.get("inventory_quantity"):
                    try:
                        stock_quantity = int(first_variant["inventory_quantity"])
                    except:
                        pass
        
        return Product(
            product_id=f"shopify_{product_id}",
            name=title,
            description=description,
            category=product_type,
            brand=vendor,
            price=price,
            currency="USD",  # Shopify default, could be shop-specific
            in_stock=stock_quantity > 0,
            stock_quantity=stock_quantity
        )
    
    async def _transform_customer(self, customer_data: Dict[str, Any]) -> Customer:
        """Transform Shopify customer to Customer model."""
        from decimal import Decimal
        
        customer_id = str(customer_data.get("id", ""))
        
        # Parse creation date
        created_at = datetime.now()
        if customer_data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(customer_data["created_at"].replace("Z", "+00:00"))
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
            customer_id=f"shopify_{customer_id}",
            first_name=customer_data.get("first_name", ""),
            last_name=customer_data.get("last_name", ""),
            email=customer_data.get("email"),
            phone=customer_data.get("phone"),
            created_at=created_at,
            total_orders=customer_data.get("orders_count", 0),
            total_spent=total_spent
        )
    
    async def _handle_order_created(self, order_data: Dict[str, Any]):
        """Handle order created webhook."""
        order_id = order_data.get("id")
        logger.info("Shopify order created", order_id=order_id)
        # TODO: Process new order
    
    async def _handle_order_updated(self, order_data: Dict[str, Any]):
        """Handle order updated webhook."""
        order_id = order_data.get("id")
        logger.info("Shopify order updated", order_id=order_id)
        # TODO: Update order
    
    async def _handle_order_cancelled(self, order_data: Dict[str, Any]):
        """Handle order cancelled webhook."""
        order_id = order_data.get("id")
        logger.info("Shopify order cancelled", order_id=order_id)
        # TODO: Update order status
    
    async def _handle_product_created(self, product_data: Dict[str, Any]):
        """Handle product created webhook."""
        product_id = product_data.get("id")
        logger.info("Shopify product created", product_id=product_id)
        # TODO: Process new product
    
    async def _handle_product_updated(self, product_data: Dict[str, Any]):
        """Handle product updated webhook."""
        product_id = product_data.get("id")
        logger.info("Shopify product updated", product_id=product_id)
        # TODO: Update product
    
    async def _handle_customer_created(self, customer_data: Dict[str, Any]):
        """Handle customer created webhook."""
        customer_id = customer_data.get("id")
        logger.info("Shopify customer created", customer_id=customer_id)
        # TODO: Process new customer
    
    async def _handle_customer_updated(self, customer_data: Dict[str, Any]):
        """Handle customer updated webhook."""
        customer_id = customer_data.get("id")
        logger.info("Shopify customer updated", customer_id=customer_id)
        # TODO: Update customer