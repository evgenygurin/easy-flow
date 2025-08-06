"""Magento e-commerce platform integration."""
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from app.models.ecommerce import Address, Customer, Order, OrderItem, OrderStatus, PaymentStatus, Product
from .base import APIResponse, PlatformAdapter

logger = structlog.get_logger()


class MagentoAdapter(PlatformAdapter):
    """Magento e-commerce platform adapter with REST/GraphQL hybrid support."""
    
    def __init__(self, credentials: dict[str, Any], config: dict[str, Any] | None = None):
        super().__init__(credentials, config)
        
        # Required credentials
        self.base_url = credentials["base_url"]  # e.g., "https://mystore.com"
        self.access_token = credentials["access_token"]  # Admin token or integration token
        
        # Optional: username/password for admin token generation
        self.username = credentials.get("username")
        self.password = credentials.get("password")
        
        # API endpoints
        self.rest_api_url = f"{self.base_url.rstrip('/')}/rest/V1/"
        self.graphql_api_url = f"{self.base_url.rstrip('/')}/graphql"
        
        # API version and store view
        self.store_view = config.get("store_view", "default")
        
        # Default headers
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def authenticate(self) -> APIResponse:
        """Test authentication by fetching store configuration."""
        try:
            # If no access token provided, try to get one with username/password
            if not self.access_token and self.username and self.password:
                auth_response = await self._get_admin_token()
                if not auth_response.success:
                    return auth_response
                
                self.access_token = auth_response.data
                self.headers["Authorization"] = f"Bearer {self.access_token}"
            
            # Test authentication with store config endpoint
            response = await self.make_request(
                "GET",
                f"{self.rest_api_url}store/storeConfigs",
                headers=self.headers
            )
            
            if response.success and response.data:
                store_config = response.data[0] if response.data else {}
                logger.info(
                    "Magento authentication successful",
                    store_name=store_config.get("base_url"),
                    locale=store_config.get("locale")
                )
                return APIResponse(
                    success=True,
                    data={"store_config": store_config}
                )
            else:
                return APIResponse(
                    success=False,
                    error_message="Authentication failed: Invalid response"
                )
                
        except Exception as e:
            logger.error("Magento authentication failed", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Authentication error: {str(e)}"
            )
    
    async def _get_admin_token(self) -> APIResponse:
        """Get admin token using username and password."""
        try:
            auth_data = {
                "username": self.username,
                "password": self.password
            }
            
            response = await self.make_request(
                "POST",
                f"{self.rest_api_url}integration/admin/token",
                json_data=auth_data
            )
            
            if response.success and response.data:
                return APIResponse(success=True, data=response.data.strip('"'))
            else:
                return APIResponse(
                    success=False,
                    error_message="Failed to obtain admin token"
                )
                
        except Exception as e:
            return APIResponse(
                success=False,
                error_message=f"Token generation error: {str(e)}"
            )
    
    async def get_orders(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None
    ) -> APIResponse:
        """Fetch orders from Magento using REST API."""
        try:
            params = {
                "searchCriteria[pageSize]": min(limit, 100),
                "searchCriteria[currentPage]": (offset // limit) + 1,
            }
            
            # Add filters
            filter_index = 0
            if filters:
                if filters.get("status"):
                    params[f"searchCriteria[filterGroups][{filter_index}][filters][0][field]"] = "status"
                    params[f"searchCriteria[filterGroups][{filter_index}][filters][0][value]"] = filters["status"]
                    params[f"searchCriteria[filterGroups][{filter_index}][filters][0][conditionType]"] = "eq"
                    filter_index += 1
                
                if filters.get("created_at_from"):
                    params[f"searchCriteria[filterGroups][{filter_index}][filters][0][field]"] = "created_at"
                    params[f"searchCriteria[filterGroups][{filter_index}][filters][0][value]"] = filters["created_at_from"]
                    params[f"searchCriteria[filterGroups][{filter_index}][filters][0][conditionType]"] = "gteq"
                    filter_index += 1
            
            response = await self.make_request(
                "GET",
                f"{self.rest_api_url}orders",
                headers=self.headers,
                params=params
            )
            
            if response.success and response.data:
                orders_data = response.data.get("items", [])
                transformed_orders = []
                
                for order_data in orders_data:
                    try:
                        transformed_order = self.transform_order(order_data)
                        if transformed_order:
                            transformed_orders.append(transformed_order)
                    except Exception as e:
                        logger.warning("Failed to transform Magento order", order_id=order_data.get("entity_id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_orders)} orders from Magento")
                return APIResponse(
                    success=True,
                    data=transformed_orders,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch Magento orders", error=str(e))
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
        """Fetch products from Magento using GraphQL API."""
        try:
            # GraphQL query for products
            query = """
            query getProducts($pageSize: Int!, $currentPage: Int!, $filter: ProductAttributeFilterInput) {
                products(pageSize: $pageSize, currentPage: $currentPage, filter: $filter) {
                    items {
                        id
                        name
                        sku
                        description {
                            html
                        }
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
                        categories {
                            id
                            name
                        }
                        weight
                        created_at
                        updated_at
                        stock_status
                        ... on ConfigurableProduct {
                            variants {
                                product {
                                    id
                                    sku
                                    name
                                    price_range {
                                        minimum_price {
                                            final_price {
                                                value
                                            }
                                        }
                                    }
                                    stock_status
                                }
                            }
                        }
                    }
                    page_info {
                        current_page
                        page_size
                        total_pages
                    }
                }
            }
            """
            
            variables = {
                "pageSize": min(limit, 100),
                "currentPage": (offset // limit) + 1,
                "filter": {}
            }
            
            if filters:
                if filters.get("category_id"):
                    variables["filter"]["category_id"] = {"eq": filters["category_id"]}
                if filters.get("name"):
                    variables["filter"]["name"] = {"match": filters["name"]}
            
            response = await self.make_request(
                "POST",
                self.graphql_api_url,
                headers=self.headers,
                json_data={"query": query, "variables": variables}
            )
            
            if response.success and response.data:
                products_data = response.data.get("data", {}).get("products", {}).get("items", [])
                transformed_products = []
                
                for product_data in products_data:
                    try:
                        # Handle configurable products with variants
                        variants = product_data.get("variants", [])
                        
                        if variants:
                            for variant_data in variants:
                                variant_product = variant_data.get("product", {})
                                combined_data = {**product_data, "variant": variant_product}
                                transformed_product = self.transform_product(combined_data)
                                if transformed_product:
                                    transformed_products.append(transformed_product)
                        else:
                            # Simple product
                            transformed_product = self.transform_product(product_data)
                            if transformed_product:
                                transformed_products.append(transformed_product)
                                
                    except Exception as e:
                        logger.warning("Failed to transform Magento product", product_id=product_data.get("id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_products)} products from Magento")
                return APIResponse(
                    success=True,
                    data=transformed_products,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch Magento products", error=str(e))
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
        """Fetch customers from Magento using REST API."""
        try:
            params = {
                "searchCriteria[pageSize]": min(limit, 100),
                "searchCriteria[currentPage]": (offset // limit) + 1,
            }
            
            # Add filters
            filter_index = 0
            if filters:
                if filters.get("email"):
                    params[f"searchCriteria[filterGroups][{filter_index}][filters][0][field]"] = "email"
                    params[f"searchCriteria[filterGroups][{filter_index}][filters][0][value]"] = filters["email"]
                    params[f"searchCriteria[filterGroups][{filter_index}][filters][0][conditionType]"] = "eq"
                    filter_index += 1
            
            response = await self.make_request(
                "GET",
                f"{self.rest_api_url}customers/search",
                headers=self.headers,
                params=params
            )
            
            if response.success and response.data:
                customers_data = response.data.get("items", [])
                transformed_customers = []
                
                for customer_data in customers_data:
                    try:
                        transformed_customer = self.transform_customer(customer_data)
                        if transformed_customer:
                            transformed_customers.append(transformed_customer)
                    except Exception as e:
                        logger.warning("Failed to transform Magento customer", customer_id=customer_data.get("id"), error=str(e))
                
                logger.info(f"Fetched {len(transformed_customers)} customers from Magento")
                return APIResponse(
                    success=True,
                    data=transformed_customers,
                    rate_limit_remaining=response.rate_limit_remaining
                )
            else:
                return response
                
        except Exception as e:
            logger.error("Failed to fetch Magento customers", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Error fetching customers: {str(e)}"
            )
    
    async def update_order_status(self, order_id: str, status: str) -> APIResponse:
        """Update order status in Magento."""
        try:
            # Map our status to Magento status
            status_mapping = {
                "pending": "pending",
                "processing": "processing",
                "shipped": "complete",  # Magento uses 'complete' for shipped
                "delivered": "complete",
                "cancelled": "canceled",
                "returned": "closed"
            }
            
            magento_status = status_mapping.get(status, status)
            
            # Create shipment for shipped status
            if magento_status == "complete":
                shipment_data = {
                    "items": [],
                    "notify": True,
                    "appendComment": False
                }
                
                response = await self.make_request(
                    "POST",
                    f"{self.rest_api_url}order/{order_id}/ship",
                    headers=self.headers,
                    json_data=shipment_data
                )
                
                if response.success:
                    logger.info(f"Created shipment for Magento order {order_id}")
                return response
            else:
                # For other status updates, would need to use status update API
                # Magento doesn't have direct status update API, usually done via order state changes
                logger.info(f"Status update for Magento order {order_id} to {magento_status} - requires custom implementation")
                return APIResponse(
                    success=True,
                    data={"message": f"Status update to {magento_status} acknowledged"}
                )
            
        except Exception as e:
            logger.error("Failed to update Magento order status", order_id=order_id, error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Error updating order status: {str(e)}"
            )
    
    async def handle_webhook(self, payload: dict[str, Any]) -> APIResponse:
        """Handle Magento webhook events."""
        try:
            event_type = payload.get("event_type", "unknown")
            
            if event_type in ["sales_order_save_after", "sales_order_place_after"]:
                order_data = payload.get("data", {})
                transformed_order = self.transform_order(order_data)
                
                if transformed_order:
                    logger.info(f"Processed Magento {event_type} webhook", order_id=transformed_order.order_id)
                    return APIResponse(success=True, data={"order": transformed_order})
            
            elif event_type in ["catalog_product_save_after"]:
                product_data = payload.get("data", {})
                transformed_product = self.transform_product(product_data)
                
                if transformed_product:
                    logger.info(f"Processed Magento {event_type} webhook", product_id=transformed_product.product_id)
                    return APIResponse(success=True, data={"product": transformed_product})
            
            elif event_type in ["customer_save_after"]:
                customer_data = payload.get("data", {})
                transformed_customer = self.transform_customer(customer_data)
                
                if transformed_customer:
                    logger.info(f"Processed Magento {event_type} webhook", customer_id=transformed_customer.customer_id)
                    return APIResponse(success=True, data={"customer": transformed_customer})
            
            else:
                logger.info(f"Unhandled Magento webhook event: {event_type}")
                return APIResponse(success=True, data={"message": f"Event {event_type} acknowledged"})
                
        except Exception as e:
            logger.error("Failed to process Magento webhook", error=str(e))
            return APIResponse(
                success=False,
                error_message=f"Webhook processing error: {str(e)}"
            )
    
    def transform_order(self, raw_order: dict[str, Any]) -> Order | None:
        """Transform Magento order data to unified format."""
        try:
            # Map Magento status to our enum
            status_mapping = {
                "pending": OrderStatus.PENDING,
                "pending_payment": OrderStatus.PENDING,
                "processing": OrderStatus.PROCESSING,
                "complete": OrderStatus.DELIVERED,
                "closed": OrderStatus.DELIVERED,
                "canceled": OrderStatus.CANCELLED,
                "holded": OrderStatus.PENDING
            }
            
            payment_status_mapping = {
                "pending": PaymentStatus.PENDING,
                "pending_payment": PaymentStatus.PENDING,
                "processing": PaymentStatus.PAID,
                "complete": PaymentStatus.PAID,
                "closed": PaymentStatus.PAID,
                "canceled": PaymentStatus.FAILED
            }
            
            # Transform line items
            order_items = []
            for item_data in raw_order.get("items", []):
                # Skip parent items for configurable products
                if item_data.get("parent_item_id"):
                    continue
                
                order_item = OrderItem(
                    item_id=str(item_data.get("item_id", "")),
                    order_id=str(raw_order.get("entity_id", "")),
                    product_id=str(item_data.get("product_id", "")),
                    product_name=item_data.get("name", ""),
                    product_price=Decimal(str(item_data.get("price", "0"))),
                    quantity=int(item_data.get("qty_ordered", 1)),
                    subtotal=Decimal(str(item_data.get("row_total", "0"))),
                    total=Decimal(str(item_data.get("row_total_incl_tax", item_data.get("row_total", "0"))))
                )
                order_items.append(order_item)
            
            # Transform shipping address
            shipping_address = None
            addr_data = raw_order.get("extension_attributes", {}).get("shipping_assignments", [])
            if addr_data and len(addr_data) > 0:
                addr = addr_data[0].get("shipping", {}).get("address", {})
            else:
                addr = raw_order.get("billing_address", {})
            
            if addr:
                street = addr.get("street", [])
                street_line = " ".join(street) if isinstance(street, list) else str(street)
                
                shipping_address = Address(
                    customer_id=str(raw_order.get("customer_id", "")),
                    country=addr.get("country_id", ""),
                    region=addr.get("region", ""),
                    city=addr.get("city", ""),
                    street=street_line,
                    house="",  # Magento combines street and house
                    postal_code=addr.get("postcode", "")
                )
            
            return Order(
                order_id=str(raw_order.get("entity_id", "")),
                customer_id=str(raw_order.get("customer_id", "")),
                status=status_mapping.get(raw_order.get("status", "pending"), OrderStatus.PENDING),
                payment_status=payment_status_mapping.get(raw_order.get("status", "pending"), PaymentStatus.PENDING),
                items=order_items,
                subtotal=Decimal(str(raw_order.get("subtotal", "0"))),
                shipping_cost=Decimal(str(raw_order.get("shipping_amount", "0"))),
                tax_amount=Decimal(str(raw_order.get("tax_amount", "0"))),
                total=Decimal(str(raw_order.get("grand_total", "0"))),
                shipping_address=shipping_address,
                created_at=datetime.fromisoformat(raw_order.get("created_at", "").replace(" ", "T")) if raw_order.get("created_at") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_order.get("updated_at", "").replace(" ", "T")) if raw_order.get("updated_at") else datetime.now(),
                source="magento"
            )
            
        except Exception as e:
            logger.error("Failed to transform Magento order", error=str(e))
            return None
    
    def transform_product(self, raw_product: dict[str, Any]) -> Product | None:
        """Transform Magento product data to unified format."""
        try:
            variant_data = raw_product.get("variant", {})
            
            # Use variant data if available, otherwise use product data
            if variant_data:
                price_info = variant_data.get("price_range", {}).get("minimum_price", {}).get("final_price", {})
                price = price_info.get("value", "0")
                currency = price_info.get("currency", "USD")
                product_id = variant_data.get("id")
                stock_status = variant_data.get("stock_status", "IN_STOCK")
                name = f"{raw_product.get('name', '')} - {variant_data.get('name', '')}"
            else:
                price_info = raw_product.get("price_range", {}).get("minimum_price", {}).get("final_price", {})
                regular_price_info = raw_product.get("price_range", {}).get("minimum_price", {}).get("regular_price", {})
                
                price = price_info.get("value", "0")
                regular_price = regular_price_info.get("value")
                currency = price_info.get("currency", "USD")
                product_id = raw_product.get("id")
                stock_status = raw_product.get("stock_status", "IN_STOCK")
                name = raw_product.get("name", "")
            
            # Get category names
            categories = raw_product.get("categories", [])
            category_names = [cat.get("name", "") for cat in categories]
            category = ", ".join(category_names) if category_names else ""
            
            # Description handling
            description = ""
            desc_data = raw_product.get("description", {})
            if isinstance(desc_data, dict):
                description = desc_data.get("html", "")
            else:
                description = str(desc_data)
            
            return Product(
                product_id=str(product_id),
                name=name,
                description=description,
                category=category,
                brand="",  # Magento brand would be in custom attributes
                price=Decimal(str(price)) if price else Decimal("0"),
                original_price=Decimal(str(regular_price)) if regular_price and regular_price != price else None,
                currency=currency,
                weight=Decimal(str(raw_product.get("weight", "0"))) if raw_product.get("weight") else None,
                in_stock=stock_status == "IN_STOCK",
                stock_quantity=0,  # Would need inventory API call for exact quantity
                created_at=datetime.fromisoformat(raw_product.get("created_at", "").replace(" ", "T")) if raw_product.get("created_at") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_product.get("updated_at", "").replace(" ", "T")) if raw_product.get("updated_at") else datetime.now()
            )
            
        except Exception as e:
            logger.error("Failed to transform Magento product", error=str(e))
            return None
    
    def transform_customer(self, raw_customer: dict[str, Any]) -> Customer | None:
        """Transform Magento customer data to unified format."""
        try:
            return Customer(
                customer_id=str(raw_customer.get("id", "")),
                first_name=raw_customer.get("firstname", ""),
                last_name=raw_customer.get("lastname", ""),
                email=raw_customer.get("email"),
                phone="",  # Phone is usually in addresses
                created_at=datetime.fromisoformat(raw_customer.get("created_at", "").replace(" ", "T")) if raw_customer.get("created_at") else datetime.now(),
                updated_at=datetime.fromisoformat(raw_customer.get("updated_at", "").replace(" ", "T")) if raw_customer.get("updated_at") else datetime.now(),
                birth_date=datetime.fromisoformat(raw_customer.get("dob", "").replace(" ", "T")) if raw_customer.get("dob") else None,
                gender=raw_customer.get("gender_text", raw_customer.get("gender")),
                # Magento doesn't provide order statistics in customer endpoint by default
                total_orders=0,  # Would need separate API call
                total_spent=Decimal("0.00")  # Would need separate API call
            )
            
        except Exception as e:
            logger.error("Failed to transform Magento customer", error=str(e))
            return None