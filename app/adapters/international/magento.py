"""Magento e-commerce platform integration adapter."""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from app.adapters.base import PlatformAdapter, APIResponse, SyncResult, RateLimitConfig
from app.models.ecommerce import Customer, Order, Product

logger = structlog.get_logger()


class MagentoAdapter(PlatformAdapter):
    """Magento e-commerce platform integration adapter with REST/GraphQL hybrid."""
    
    def __init__(
        self,
        base_url: str,
        admin_token: str,
        use_graphql: bool = True,
        api_version: str = "V1"
    ):
        """Initialize Magento adapter.
        
        Args:
        ----
            base_url: Magento store base URL (e.g., 'https://myshop.com')
            admin_token: Magento admin access token
            use_graphql: Whether to use GraphQL API for complex queries
            api_version: Magento REST API version
        """
        super().__init__(
            api_key=admin_token,
            base_url=base_url.rstrip('/'),
            platform_name="magento",
            rate_limit_config=RateLimitConfig(
                requests_per_minute=60,  # Conservative for Magento
                requests_per_hour=3600,
                burst_size=10
            )
        )
        
        self.admin_token = admin_token
        self.use_graphql = use_graphql
        self.api_version = api_version
        
        # Magento order status mapping
        self.order_status_mapping = {
            "pending": "pending",
            "pending_payment": "pending",
            "payment_review": "confirmed",
            "processing": "processing",
            "shipped": "shipped",
            "complete": "delivered",
            "canceled": "cancelled",
            "closed": "delivered",
            "fraud": "cancelled",
            "holded": "processing"
        }
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.admin_token}"
        }
    
    async def _make_graphql_request(self, query: str, variables: Optional[Dict[str, Any]] = None) -> APIResponse:
        """Make a GraphQL request to Magento."""
        return await self._make_request(
            method="POST",
            url="/graphql",
            data={
                "query": query,
                "variables": variables or {}
            }
        )
    
    async def test_connection(self) -> APIResponse:
        """Test connection to Magento API."""
        try:
            # Test with store config endpoint
            response = await self._make_request(
                method="GET",
                url=f"/rest/{self.api_version}/store/storeConfigs"
            )
            
            if response.success:
                logger.info("Magento connection test successful")
            
            return response
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0,
                platform=self.platform_name
            )
    
    async def sync_orders(self, limit: int = 100) -> SyncResult:
        """Sync orders from Magento."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get orders from Magento using REST API
            response = await self._make_request(
                method="GET",
                url=f"/rest/{self.api_version}/orders",
                params={
                    "searchCriteria[pageSize]": min(limit, 100),  # Magento max per page
                    "searchCriteria[currentPage]": 1,
                    "searchCriteria[sortOrders][0][field]": "created_at",
                    "searchCriteria[sortOrders][0][direction]": "DESC"
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
            
            orders_response = response.data if isinstance(response.data, dict) else {}
            orders_data = orders_response.get("items", [])
            
            for order_data in orders_data:
                processed += 1
                try:
                    # Transform Magento order to internal Order model
                    order = await self._transform_order(order_data)
                    
                    logger.info(
                        "Synchronized Magento order",
                        magento_order_id=order_data.get("entity_id"),
                        order_id=order.order_id,
                        status=order.status
                    )
                    success += 1
                    
                except Exception as e:
                    error_msg = f"Failed to process order {order_data.get('entity_id')}: {str(e)}"
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
        """Sync products from Magento catalog."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            if self.use_graphql:
                # Use GraphQL for products with complex attributes
                query = """
                query getProducts($pageSize: Int!, $currentPage: Int!) {
                    products(pageSize: $pageSize, currentPage: $currentPage) {
                        items {
                            id
                            name
                            sku
                            price_range {
                                minimum_price {
                                    regular_price {
                                        value
                                        currency
                                    }
                                    final_price {
                                        value
                                        currency
                                    }
                                }
                            }
                            description {
                                html
                            }
                            short_description {
                                html
                            }
                            categories {
                                id
                                name
                            }
                            image {
                                url
                                label
                            }
                            stock_status
                            weight
                            ... on ConfigurableProduct {
                                configurable_options {
                                    attribute_id
                                    label
                                    values {
                                        value_index
                                        label
                                    }
                                }
                                variants {
                                    product {
                                        id
                                        name
                                        sku
                                        price_range {
                                            minimum_price {
                                                regular_price {
                                                    value
                                                }
                                            }
                                        }
                                    }
                                    attributes {
                                        code
                                        value_index
                                    }
                                }
                            }
                        }
                        page_info {
                            page_size
                            current_page
                            total_pages
                        }
                        total_count
                    }
                }
                """
                
                response = await self._make_graphql_request(
                    query, 
                    {"pageSize": min(limit, 100), "currentPage": 1}
                )
                
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
                
                products_data = response.data.get("data", {}).get("products", {}).get("items", [])
                
            else:
                # Use REST API
                response = await self._make_request(
                    method="GET",
                    url=f"/rest/{self.api_version}/products",
                    params={
                        "searchCriteria[pageSize]": min(limit, 100),
                        "searchCriteria[currentPage]": 1
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
                products_data = products_response.get("items", [])
            
            for product_data in products_data:
                processed += 1
                try:
                    # Transform Magento product to internal Product model
                    product = await self._transform_product(product_data, is_graphql=self.use_graphql)
                    
                    logger.info(
                        "Synchronized Magento product",
                        magento_product_id=product_data.get("id"),
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
        """Sync customers from Magento."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get customers from Magento
            response = await self._make_request(
                method="GET",
                url=f"/rest/{self.api_version}/customers/search",
                params={
                    "searchCriteria[pageSize]": min(limit, 100),
                    "searchCriteria[currentPage]": 1,
                    "searchCriteria[sortOrders][0][field]": "created_at",
                    "searchCriteria[sortOrders][0][direction]": "DESC"
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
            customers_data = customers_response.get("items", [])
            
            for customer_data in customers_data:
                processed += 1
                try:
                    # Transform Magento customer to internal Customer model
                    customer = await self._transform_customer(customer_data)
                    
                    logger.info(
                        "Synchronized Magento customer",
                        magento_customer_id=customer_data.get("id"),
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
        """Handle Magento webhook events."""
        try:
            # Magento webhook structure varies by event type
            # Events are configured via admin panel or API
            
            event_type = payload.get("event_type") or payload.get("type")
            data = payload.get("data", payload)  # Data might be at root level
            
            logger.info("Processing Magento webhook", event_type=event_type)
            
            if event_type:
                if "order" in event_type:
                    await self._handle_order_webhook(data, event_type)
                elif "product" in event_type:
                    await self._handle_product_webhook(data, event_type)
                elif "customer" in event_type:
                    await self._handle_customer_webhook(data, event_type)
                else:
                    logger.warning("Unknown Magento webhook event", event_type=event_type)
            else:
                # Try to determine from data structure
                if "entity_id" in data and "grand_total" in data:
                    await self._handle_order_webhook(data, "order_update")
                elif "entity_id" in data and "sku" in data:
                    await self._handle_product_webhook(data, "product_update")
                elif "id" in data and "email" in data:
                    await self._handle_customer_webhook(data, "customer_update")
            
            return True
            
        except Exception as e:
            logger.error("Magento webhook processing failed", error=str(e))
            return False
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify Magento webhook signature."""
        # Magento webhook signature verification varies by configuration
        # Implement based on your specific setup
        return self._verify_hmac_sha256(payload, signature, secret)
    
    async def _transform_order(self, order_data: Dict[str, Any]) -> Order:
        """Transform Magento order to Order model."""
        from decimal import Decimal
        
        order_id = str(order_data.get("entity_id", ""))
        status = self.order_status_mapping.get(order_data.get("status", ""), "pending")
        
        # Parse dates
        created_at = datetime.now()
        if order_data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(order_data["created_at"].replace("Z", "+00:00"))
            except:
                pass
        
        # Parse totals
        total_price = Decimal("0.00")
        if order_data.get("grand_total"):
            try:
                total_price = Decimal(str(order_data["grand_total"]))
            except:
                pass
        
        return Order(
            order_id=f"magento_{order_id}",
            customer_id=f"magento_{order_data.get('customer_id', 'guest')}",
            status=status,
            subtotal=total_price,
            total=total_price,
            created_at=created_at,
            source="magento",
            notes=""
        )
    
    async def _transform_product(self, product_data: Dict[str, Any], is_graphql: bool = False) -> Product:
        """Transform Magento product to Product model."""
        from decimal import Decimal
        
        if is_graphql:
            # GraphQL format
            product_id = str(product_data.get("id", ""))
            name = product_data.get("name", "")
            description = product_data.get("description", {}).get("html", "")
            
            # Get price from price_range
            price = Decimal("0.00")
            price_range = product_data.get("price_range", {})
            min_price = price_range.get("minimum_price", {})
            regular_price = min_price.get("regular_price", {})
            
            if regular_price.get("value"):
                try:
                    price = Decimal(str(regular_price["value"]))
                except:
                    pass
            
            # Get category
            categories = product_data.get("categories", [])
            category = categories[0].get("name", "") if categories else ""
            
            # Stock status
            stock_status = product_data.get("stock_status", "")
            in_stock = stock_status == "IN_STOCK"
            
        else:
            # REST API format
            product_id = str(product_data.get("id", ""))
            name = product_data.get("name", "")
            
            # Get description from custom attributes
            description = ""
            custom_attributes = product_data.get("custom_attributes", [])
            for attr in custom_attributes:
                if attr.get("attribute_code") == "description":
                    description = attr.get("value", "")
                    break
            
            # Parse price
            price = Decimal("0.00")
            if product_data.get("price"):
                try:
                    price = Decimal(str(product_data["price"]))
                except:
                    pass
            
            # Get category from custom attributes
            category = ""
            for attr in custom_attributes:
                if attr.get("attribute_code") == "category_ids":
                    category_ids = attr.get("value", [])
                    if category_ids:
                        category = f"category_{category_ids[0]}"
                    break
            
            # Stock status from extension attributes
            in_stock = True  # Default, would need inventory API for accurate data
        
        return Product(
            product_id=f"magento_{product_id}",
            name=name,
            description=description,
            category=category,
            price=price,
            currency="USD",  # Magento default, configurable per store
            in_stock=in_stock,
            weight=product_data.get("weight")
        )
    
    async def _transform_customer(self, customer_data: Dict[str, Any]) -> Customer:
        """Transform Magento customer to Customer model."""
        customer_id = str(customer_data.get("id", ""))
        
        # Parse creation date
        created_at = datetime.now()
        if customer_data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(customer_data["created_at"].replace("Z", "+00:00"))
            except:
                pass
        
        return Customer(
            customer_id=f"magento_{customer_id}",
            first_name=customer_data.get("firstname", ""),
            last_name=customer_data.get("lastname", ""),
            email=customer_data.get("email"),
            created_at=created_at
        )
    
    async def _handle_order_webhook(self, order_data: Dict[str, Any], event_type: str):
        """Handle order webhook event."""
        order_id = order_data.get("entity_id")
        logger.info("Magento order webhook", order_id=order_id, event_type=event_type)
        # TODO: Update internal order data
    
    async def _handle_product_webhook(self, product_data: Dict[str, Any], event_type: str):
        """Handle product webhook event."""
        product_id = product_data.get("entity_id") or product_data.get("id")
        logger.info("Magento product webhook", product_id=product_id, event_type=event_type)
        # TODO: Update internal product data
    
    async def _handle_customer_webhook(self, customer_data: Dict[str, Any], event_type: str):
        """Handle customer webhook event."""
        customer_id = customer_data.get("id")
        logger.info("Magento customer webhook", customer_id=customer_id, event_type=event_type)
        # TODO: Update internal customer data