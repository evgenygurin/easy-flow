"""InSales e-commerce platform integration adapter."""
import base64
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from app.adapters.base import PlatformAdapter, APIResponse, SyncResult, RateLimitConfig
from app.models.ecommerce import Customer, Order, Product

logger = structlog.get_logger()


class InSalesAdapter(PlatformAdapter):
    """InSales e-commerce platform integration adapter with webhook support."""
    
    def __init__(
        self,
        shop_domain: str,
        api_key: str,
        api_password: str,
        webhook_secret: Optional[str] = None
    ):
        """Initialize InSales adapter.
        
        Args:
        ----
            shop_domain: InSales shop domain (e.g., 'myshop.myinsales.ru')
            api_key: InSales API key
            api_password: InSales API password
            webhook_secret: Secret for webhook signature verification
        """
        base_url = f"https://{shop_domain}"
        
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            platform_name="insales",
            rate_limit_config=RateLimitConfig(
                requests_per_minute=120,  # InSales is generally permissive
                requests_per_hour=7200,
                burst_size=20
            )
        )
        
        self.shop_domain = shop_domain
        self.api_password = api_password
        self.webhook_secret = webhook_secret
        
        # InSales order status mapping
        self.order_status_mapping = {
            "new": "pending",
            "accepted": "confirmed",
            "paid": "processing",
            "delivered": "delivered",
            "canceled": "cancelled",
            "refunded": "returned"
        }
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers with Basic Auth."""
        # InSales uses HTTP Basic Authentication
        auth_string = f"{self.api_key}:{self.api_password}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()
        
        return {
            "Content-Type": "application/json",
            "Accept": "application/json", 
            "Authorization": f"Basic {auth_encoded}"
        }
    
    async def test_connection(self) -> APIResponse:
        """Test connection to InSales API."""
        try:
            # Test with account info endpoint
            response = await self._make_request(
                method="GET",
                url="/admin/account.json"
            )
            
            if response.success:
                logger.info("InSales connection test successful")
            
            return response
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0,
                platform=self.platform_name
            )
    
    async def sync_orders(self, limit: int = 100) -> SyncResult:
        """Sync orders from InSales."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get orders from InSales
            response = await self._make_request(
                method="GET",
                url="/admin/orders.json",
                params={
                    "per_page": min(limit, 250),  # InSales max per page
                    "page": 1,
                    "updated_since": (datetime.now() - datetime.timedelta(days=30)).isoformat()
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
                    # Transform InSales order to internal Order model
                    order = await self._transform_order(order_data)
                    
                    logger.info(
                        "Synchronized InSales order",
                        insales_order_id=order_data.get("id"),
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
        """Sync products from InSales catalog."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get products from InSales
            response = await self._make_request(
                method="GET", 
                url="/admin/products.json",
                params={
                    "per_page": min(limit, 250),  # InSales max per page
                    "page": 1
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
                    # Transform InSales product to internal Product model
                    product = await self._transform_product(product_data)
                    
                    logger.info(
                        "Synchronized InSales product",
                        insales_product_id=product_data.get("id"),
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
        """Sync customers from InSales."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []
        
        try:
            # Get clients from InSales
            response = await self._make_request(
                method="GET",
                url="/admin/clients.json",
                params={
                    "per_page": min(limit, 250),  # InSales max per page
                    "page": 1
                }
            )
            
            if not response.success:
                errors.append(f"Failed to fetch clients: {response.error}")
                return SyncResult(
                    platform=self.platform_name,
                    operation="customers",
                    records_processed=processed,
                    records_success=success,
                    records_failed=processed - success,
                    errors=errors,
                    duration_seconds=(datetime.now() - start_time).total_seconds()
                )
            
            clients_data = response.data if isinstance(response.data, list) else []
            
            for client_data in clients_data:
                processed += 1
                try:
                    # Transform InSales client to internal Customer model
                    customer = await self._transform_customer(client_data)
                    
                    logger.info(
                        "Synchronized InSales client",
                        insales_client_id=client_data.get("id"),
                        customer_id=customer.customer_id
                    )
                    success += 1
                    
                except Exception as e:
                    error_msg = f"Failed to process client {client_data.get('id')}: {str(e)}"
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
        """Handle InSales webhook events."""
        try:
            # InSales webhook payload structure varies by event type
            event_type = payload.get("event_type")  # Custom field we might add
            
            # Determine event type from payload structure
            if "order" in payload:
                event_type = "order_updated"
                await self._handle_order_webhook(payload["order"])
            elif "product" in payload:
                event_type = "product_updated"
                await self._handle_product_webhook(payload["product"])
            elif "client" in payload:
                event_type = "client_updated"
                await self._handle_client_webhook(payload["client"])
            else:
                logger.warning("Unknown InSales webhook event", payload_keys=list(payload.keys()))
                return False
            
            logger.info("Processed InSales webhook", event_type=event_type)
            return True
            
        except Exception as e:
            logger.error("InSales webhook processing failed", error=str(e))
            return False
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify InSales webhook signature."""
        if not self.webhook_secret:
            # If no secret is configured, skip verification
            return True
        
        return self._verify_hmac_sha256(payload, signature, secret)
    
    async def _transform_order(self, order_data: Dict[str, Any]) -> Order:
        """Transform InSales order to Order model."""
        from decimal import Decimal
        
        order_id = str(order_data.get("id", ""))
        
        # Map InSales fulfillment status to our status
        fulfillment_status = order_data.get("fulfillment_status", "new")
        status = self.order_status_mapping.get(fulfillment_status, "pending")
        
        # Parse dates
        created_at = datetime.now()
        if order_data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(order_data["created_at"].replace("Z", "+00:00"))
            except:
                pass
        
        # Parse totals
        total_price = Decimal("0.00")
        if order_data.get("total_price"):
            try:
                total_price = Decimal(str(order_data["total_price"]))
            except:
                pass
        
        return Order(
            order_id=f"insales_{order_id}",
            customer_id=f"insales_{order_data.get('client_id', 'unknown')}",
            status=status,
            subtotal=total_price,
            total=total_price,
            created_at=created_at,
            source="insales",
            notes=order_data.get("comment", "")
        )
    
    async def _transform_product(self, product_data: Dict[str, Any]) -> Product:
        """Transform InSales product to Product model."""
        from decimal import Decimal
        
        product_id = str(product_data.get("id", ""))
        
        # Parse price
        price = Decimal("0.00")
        if product_data.get("price"):
            try:
                price = Decimal(str(product_data["price"]))
            except:
                pass
        
        return Product(
            product_id=f"insales_{product_id}",
            name=product_data.get("title", ""),
            description=product_data.get("description", ""),
            category="",  # InSales may have categories in separate field
            price=price,
            currency="RUB",  # InSales primarily Russian market
            in_stock=product_data.get("state", "enabled") == "enabled",
            stock_quantity=product_data.get("quantity", 0)
        )
    
    async def _transform_customer(self, client_data: Dict[str, Any]) -> Customer:
        """Transform InSales client to Customer model."""
        client_id = str(client_data.get("id", ""))
        
        # Parse creation date
        created_at = datetime.now()
        if client_data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(client_data["created_at"].replace("Z", "+00:00"))
            except:
                pass
        
        return Customer(
            customer_id=f"insales_{client_id}",
            first_name=client_data.get("name", "").split()[0] if client_data.get("name") else "",
            last_name=" ".join(client_data.get("name", "").split()[1:]) if client_data.get("name") else "",
            email=client_data.get("email"),
            phone=client_data.get("phone"),
            created_at=created_at
        )
    
    async def _handle_order_webhook(self, order_data: Dict[str, Any]):
        """Handle order webhook event."""
        order_id = order_data.get("id")
        status = order_data.get("fulfillment_status")
        logger.info("InSales order webhook", order_id=order_id, status=status)
        # TODO: Update internal order data
    
    async def _handle_product_webhook(self, product_data: Dict[str, Any]):
        """Handle product webhook event."""
        product_id = product_data.get("id")
        logger.info("InSales product webhook", product_id=product_id)
        # TODO: Update internal product data
    
    async def _handle_client_webhook(self, client_data: Dict[str, Any]):
        """Handle client webhook event."""
        client_id = client_data.get("id")
        logger.info("InSales client webhook", client_id=client_id)
        # TODO: Update internal customer data