"""Ozon marketplace integration adapter."""
import contextlib
from datetime import datetime, timedelta
from typing import Any

import structlog

from app.adapters.base import APIResponse, PlatformAdapter, RateLimitConfig, SyncResult
from app.models.ecommerce import Customer, Order, Product


logger = structlog.get_logger()


class OzonAdapter(PlatformAdapter):
    """Ozon marketplace integration adapter with dual API support."""

    def __init__(self, client_id: str, api_key: str, chat_api_token: str | None = None):
        """Initialize Ozon adapter.

        Args:
        ----
            client_id: Ozon client ID
            api_key: Ozon API key
            chat_api_token: Ozon Chat API token for customer support

        """
        super().__init__(
            api_key=api_key,
            base_url="https://api-seller.ozon.ru",
            platform_name="ozon",
            rate_limit_config=RateLimitConfig(
                requests_per_minute=30,  # Ozon has stricter limits
                requests_per_hour=1800,
                burst_size=5
            )
        )

        self.client_id = client_id
        self.chat_api_token = chat_api_token
        self.chat_api_url = "https://chat-api.ozon.ru"

        # Ozon posting status mapping
        self.posting_status_mapping = {
            "awaiting_registration": "pending",
            "awaiting_approve": "confirmed",
            "awaiting_packaging": "processing",
            "awaiting_deliver": "shipped",
            "delivering": "shipped",
            "delivered": "delivered",
            "cancelled": "cancelled",
            "not_accepted": "cancelled"
        }

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Client-Id": self.client_id,
            "Api-Key": self.api_key
        }

    async def _get_chat_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for Chat API."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.chat_api_token}"
        }

    async def test_connection(self) -> APIResponse:
        """Test connection to Ozon API."""
        try:
            # Test seller info endpoint
            response = await self._make_request(
                method="POST",
                url="/v1/seller/info"
            )

            if response.success:
                logger.info("Ozon connection test successful")

            return response

        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0,
                platform=self.platform_name
            )

    async def sync_orders(self, limit: int = 100) -> SyncResult:
        """Sync postings (orders) from Ozon."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []

        try:
            # Get postings from last 30 days
            since_date = (datetime.now() - timedelta(days=30)).isoformat()

            response = await self._make_request(
                method="POST",
                url="/v3/posting/fbs/list",
                data={
                    "dir": "DESC",
                    "filter": {
                        "since": since_date,
                        "status": ""  # All statuses
                    },
                    "limit": min(limit, 1000),  # Ozon max limit
                    "offset": 0,
                    "with": {
                        "analytics_data": True,
                        "financial_data": True
                    }
                }
            )

            if not response.success:
                errors.append(f"Failed to fetch postings: {response.error}")
                return SyncResult(
                    platform=self.platform_name,
                    operation="orders",
                    records_processed=processed,
                    records_success=success,
                    records_failed=processed - success,
                    errors=errors,
                    duration_seconds=(datetime.now() - start_time).total_seconds()
                )

            postings = response.data.get("result", [])

            for posting in postings:
                processed += 1
                try:
                    # Transform Ozon posting to internal Order model
                    order = await self._transform_posting_to_order(posting)

                    logger.info(
                        "Synchronized Ozon posting",
                        posting_number=posting.get("posting_number"),
                        order_id=order.order_id,
                        status=order.status
                    )
                    success += 1

                except Exception as e:
                    error_msg = f"Failed to process posting {posting.get('posting_number')}: {str(e)}"
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
        """Sync products from Ozon catalog."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []

        try:
            # Get products from Ozon
            response = await self._make_request(
                method="POST",
                url="/v2/product/list",
                data={
                    "filter": {
                        "offer_id": "",
                        "product_id": "",
                        "visibility": "ALL"
                    },
                    "last_id": "",
                    "limit": min(limit, 1000)
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

            products_data = response.data.get("result", {}).get("items", [])

            for product_data in products_data:
                processed += 1
                try:
                    # Transform Ozon product to internal Product model
                    product = await self._transform_product(product_data)

                    logger.info(
                        "Synchronized Ozon product",
                        product_id=product_data.get("product_id"),
                        offer_id=product_data.get("offer_id"),
                        name=product.name
                    )
                    success += 1

                except Exception as e:
                    error_msg = f"Failed to process product {product_data.get('product_id')}: {str(e)}"
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
        """Sync customers from Ozon Chat API."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []

        if not self.chat_api_token:
            errors.append("Chat API token not configured")
            return SyncResult(
                platform=self.platform_name,
                operation="customers",
                records_processed=processed,
                records_success=success,
                records_failed=processed - success,
                errors=errors,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )

        try:
            # Get customers from Chat API
            response = await self._make_request(
                method="GET",
                url=f"{self.chat_api_url}/v1/customers",
                headers=await self._get_chat_auth_headers(),
                params={
                    "limit": min(limit, 100)
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
                    # Transform Ozon customer to internal Customer model
                    customer = await self._transform_customer(customer_data)

                    logger.info(
                        "Synchronized Ozon customer",
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

    async def handle_webhook(self, payload: dict[str, Any], signature: str | None = None) -> bool:
        """Handle Ozon webhook events."""
        try:
            event_type = payload.get("event_type")
            data = payload.get("data", {})

            logger.info("Processing Ozon webhook", event_type=event_type)

            if event_type == "posting_created":
                # New posting created
                posting_data = data.get("posting", {})
                await self._handle_posting_created(posting_data)

            elif event_type == "posting_status_changed":
                # Posting status changed
                posting_number = data.get("posting_number")
                new_status = data.get("status")
                await self._handle_posting_status_change(posting_number, new_status)

            elif event_type == "chat_message":
                # Customer chat message (if Chat API is enabled)
                message_data = data.get("message", {})
                await self._handle_chat_message(message_data)

            return True

        except Exception as e:
            logger.error("Ozon webhook processing failed", error=str(e))
            return False

    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify Ozon webhook signature."""
        return self._verify_hmac_sha256(payload, signature, secret)

    async def create_support_ticket(self, customer_id: str, subject: str, description: str) -> APIResponse:
        """Create a support ticket via Chat API."""
        if not self.chat_api_token:
            return APIResponse(
                success=False,
                error="Chat API token not configured",
                status_code=0,
                platform=self.platform_name
            )

        try:
            response = await self._make_request(
                method="POST",
                url=f"{self.chat_api_url}/v1/tickets",
                headers=await self._get_chat_auth_headers(),
                data={
                    "customer_id": customer_id,
                    "subject": subject,
                    "description": description,
                    "priority": "medium"
                }
            )

            return response

        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0,
                platform=self.platform_name
            )

    async def _transform_posting_to_order(self, posting: dict[str, Any]) -> Order:
        """Transform Ozon posting to Order model."""
        from decimal import Decimal

        posting_number = posting.get("posting_number", "")
        status = self.posting_status_mapping.get(posting.get("status", ""), "pending")

        # Parse dates
        created_at = datetime.now()
        if posting.get("in_process_at"):
            with contextlib.suppress(Exception):
                created_at = datetime.fromisoformat(posting["in_process_at"].replace("Z", "+00:00"))

        # Calculate totals from products
        products = posting.get("products", [])
        total_price = Decimal("0.00")

        for product in products:
            try:
                quantity = int(product.get("quantity", 0))
                price = Decimal(str(product.get("price", "0")))
                total_price += quantity * price
            except:
                pass

        # Extract customer info
        customer = posting.get("customer", {})
        customer_id = str(customer.get("customer_id", "unknown"))

        return Order(
            order_id=f"ozon_{posting_number}",
            customer_id=f"ozon_{customer_id}",
            status=status,
            subtotal=total_price,
            total=total_price,
            created_at=created_at,
            source="ozon",
            tracking_number=posting.get("tracking_number")
        )

    async def _transform_product(self, product_data: dict[str, Any]) -> Product:
        """Transform Ozon product to Product model."""
        from decimal import Decimal

        product_id = str(product_data.get("product_id", ""))
        offer_id = product_data.get("offer_id", "")

        # Parse price (need to get from stocks or pricing API)
        price = Decimal("0.00")

        return Product(
            product_id=f"ozon_{product_id}",
            name=offer_id,  # Ozon uses offer_id as product name/SKU
            description="",  # Need separate API call for full details
            category="",
            price=price,
            currency="RUB",
            in_stock=product_data.get("visibility", "") == "VISIBLE"
        )

    async def _transform_customer(self, customer_data: dict[str, Any]) -> Customer:
        """Transform Ozon customer to Customer model."""
        customer_id = str(customer_data.get("id", ""))

        return Customer(
            customer_id=f"ozon_{customer_id}",
            first_name=customer_data.get("first_name", ""),
            last_name=customer_data.get("last_name", ""),
            email=customer_data.get("email"),
            phone=customer_data.get("phone"),
            created_at=datetime.now()
        )

    async def _handle_posting_created(self, posting_data: dict[str, Any]):
        """Handle posting created webhook."""
        posting_number = posting_data.get("posting_number")
        logger.info("New Ozon posting created", posting_number=posting_number)
        # TODO: Process new posting

    async def _handle_posting_status_change(self, posting_number: str, new_status: str):
        """Handle posting status change webhook."""
        status_name = self.posting_status_mapping.get(new_status, "unknown")
        logger.info(
            "Ozon posting status changed",
            posting_number=posting_number,
            status=new_status,
            status_name=status_name
        )
        # TODO: Update posting status

    async def _handle_chat_message(self, message_data: dict[str, Any]):
        """Handle customer chat message webhook."""
        customer_id = message_data.get("customer_id")
        message = message_data.get("text")
        logger.info("Ozon chat message received", customer_id=customer_id, message=message[:100])
        # TODO: Process chat message
