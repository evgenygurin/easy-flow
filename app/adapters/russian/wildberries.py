"""Wildberries marketplace integration adapter."""
import contextlib
from datetime import datetime, timedelta
from typing import Any

import jwt
import structlog

from app.adapters.base import APIResponse, PlatformAdapter, RateLimitConfig, SyncResult
from app.models.ecommerce import Order, Product


logger = structlog.get_logger()


class WildberriesAdapter(PlatformAdapter):
    """Wildberries marketplace integration adapter with JWT authentication."""

    def __init__(self, api_key: str, jwt_secret: str | None = None):
        """Initialize Wildberries adapter.

        Args:
        ----
            api_key: Wildberries API key
            jwt_secret: JWT secret for token generation (if using JWT auth)

        """
        super().__init__(
            api_key=api_key,
            base_url="https://suppliers-api.wildberries.ru",
            platform_name="wildberries",
            rate_limit_config=RateLimitConfig(
                requests_per_minute=60,  # Conservative limit
                requests_per_hour=3600,
                burst_size=10
            )
        )

        self.jwt_secret = jwt_secret
        self.jwt_token: str | None = None
        self.jwt_expires_at: datetime | None = None

        # Wildberries order status mapping
        self.status_mapping = {
            0: "pending",        # На сборке
            1: "confirmed",      # В пути к клиенту
            2: "shipped",        # Доставлен в пункт выдачи
            3: "delivered",      # Получен покупателем
            4: "cancelled",      # Отменен до отгрузки в ПВЗ
            5: "cancelled",      # Отменен в пункте выдачи
            6: "returned",       # Возврат
            7: "returned"        # Частичный возврат
        }

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Use JWT token if available and valid
        if self.jwt_secret and (not self.jwt_token or self._is_jwt_expired()):
            await self._generate_jwt_token()

        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        else:
            # Fallback to API key
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _is_jwt_expired(self) -> bool:
        """Check if JWT token is expired."""
        if not self.jwt_expires_at:
            return True
        return datetime.now() >= self.jwt_expires_at

    async def _generate_jwt_token(self):
        """Generate JWT token for authentication."""
        if not self.jwt_secret:
            return

        try:
            payload = {
                "iss": "easy-flow",  # Issuer
                "aud": "wildberries",  # Audience
                "iat": datetime.now(),  # Issued at
                "exp": datetime.now() + timedelta(hours=1),  # Expires
                "sub": self.api_key  # Subject (API key)
            }

            self.jwt_token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
            self.jwt_expires_at = payload["exp"]

            logger.info("JWT token generated for Wildberries")

        except Exception as e:
            logger.error("Failed to generate JWT token", error=str(e))

    async def test_connection(self) -> APIResponse:
        """Test connection to Wildberries API."""
        try:
            # Test with supplier info endpoint
            response = await self._make_request(
                method="GET",
                url="/api/v3/supplier"
            )

            if response.success:
                logger.info("Wildberries connection test successful")

            return response

        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0,
                platform=self.platform_name
            )

    async def sync_orders(self, limit: int = 100) -> SyncResult:
        """Sync orders (sales) from Wildberries."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []

        try:
            # Get orders from last 30 days
            date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

            response = await self._make_request(
                method="GET",
                url="/api/v3/orders",
                params={
                    "limit": min(limit, 1000),  # Wildberries max limit
                    "next": 0,
                    "dateFrom": date_from
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
                    # Transform Wildberries order to internal Order model
                    order = await self._transform_order(order_data)

                    logger.info(
                        "Synchronized Wildberries order",
                        wb_order_id=order_data.get("id"),
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
        """Sync products from Wildberries catalog."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []

        try:
            # Get products from Wildberries
            response = await self._make_request(
                method="GET",
                url="/content/v1/cards/cursor/list",
                params={
                    "sort": {
                        "cursor": {
                            "limit": min(limit, 100)  # Wildberries max limit for products
                        }
                    }
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

            products_data = response.data.get("cards", [])

            for product_data in products_data:
                processed += 1
                try:
                    # Transform Wildberries product to internal Product model
                    product = await self._transform_product(product_data)

                    logger.info(
                        "Synchronized Wildberries product",
                        wb_product_id=product_data.get("nmID"),
                        product_id=product.product_id,
                        name=product.name
                    )
                    success += 1

                except Exception as e:
                    error_msg = f"Failed to process product {product_data.get('nmID')}: {str(e)}"
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
        """Sync customers from Wildberries (limited customer data available)."""
        start_time = datetime.now()

        # Wildberries doesn't provide direct customer data access
        # Customer information is typically embedded in orders
        logger.warning("Wildberries doesn't provide direct customer data access")

        return SyncResult(
            platform=self.platform_name,
            operation="customers",
            records_processed=0,
            records_success=0,
            records_failed=0,
            errors=["Wildberries doesn't provide direct customer data access"],
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )

    async def handle_webhook(self, payload: dict[str, Any], signature: str | None = None) -> bool:
        """Handle Wildberries webhook events."""
        try:
            event_type = payload.get("event_type")
            data = payload.get("data", {})

            logger.info("Processing Wildberries webhook", event_type=event_type)

            if event_type == "new_order":
                # New order received
                order_data = data.get("order", {})
                await self._handle_new_order(order_data)

            elif event_type == "order_status_changed":
                # Order status updated
                order_id = data.get("order_id")
                new_status = data.get("status")
                await self._handle_status_change(order_id, new_status)

            elif event_type == "return_request":
                # Return request
                return_data = data.get("return", {})
                await self._handle_return_request(return_data)

            return True

        except Exception as e:
            logger.error("Wildberries webhook processing failed", error=str(e))
            return False

    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify Wildberries webhook signature."""
        return self._verify_hmac_sha256(payload, signature, secret)

    async def _transform_order(self, order_data: dict[str, Any]) -> Order:
        """Transform Wildberries order to Order model."""
        from decimal import Decimal

        order_id = str(order_data.get("id", ""))
        status_code = order_data.get("status", 0)
        status = self.status_mapping.get(status_code, "pending")

        # Parse dates
        created_at = datetime.now()
        if order_data.get("date"):
            with contextlib.suppress(Exception):
                created_at = datetime.fromisoformat(order_data["date"])

        # Calculate totals
        total_price = Decimal("0.00")
        if order_data.get("totalPrice"):
            with contextlib.suppress(Exception):
                total_price = Decimal(str(order_data["totalPrice"]))

        return Order(
            order_id=f"wb_{order_id}",
            customer_id=f"wb_customer_{order_data.get('customerId', 'unknown')}",
            status=status,
            subtotal=total_price,
            total=total_price,
            created_at=created_at,
            source="wildberries",
            tracking_number=order_data.get("barcode")
        )

    async def _transform_product(self, product_data: dict[str, Any]) -> Product:
        """Transform Wildberries product to Product model."""
        from decimal import Decimal

        product_id = str(product_data.get("nmID", ""))

        # Get basic product info
        sizes = product_data.get("sizes", [])
        first_size = sizes[0] if sizes else {}

        # Parse price
        price = Decimal("0.00")
        if first_size.get("price"):
            with contextlib.suppress(Exception):
                price = Decimal(str(first_size["price"]))

        return Product(
            product_id=f"wb_{product_id}",
            name=product_data.get("title", ""),
            description=product_data.get("description", ""),
            category=product_data.get("object", ""),
            brand=product_data.get("brand", ""),
            price=price,
            currency="RUB",
            in_stock=len(sizes) > 0,
            stock_quantity=sum(size.get("stocks", 0) for size in sizes)
        )

    async def _handle_new_order(self, order_data: dict[str, Any]):
        """Handle new order webhook."""
        order_id = order_data.get("id")
        logger.info("New Wildberries order received", order_id=order_id)
        # TODO: Process new order

    async def _handle_status_change(self, order_id: str, new_status: int):
        """Handle order status change webhook."""
        status_name = self.status_mapping.get(new_status, "unknown")
        logger.info(
            "Wildberries order status changed",
            order_id=order_id,
            status_code=new_status,
            status_name=status_name
        )
        # TODO: Update order status

    async def _handle_return_request(self, return_data: dict[str, Any]):
        """Handle return request webhook."""
        order_id = return_data.get("order_id")
        logger.info("Wildberries return request", order_id=order_id)
        # TODO: Process return request
