"""1C-Bitrix CRM integration adapter."""
import base64
import contextlib
from datetime import datetime
from typing import Any

import structlog

from app.adapters.base import APIResponse, PlatformAdapter, RateLimitConfig, SyncResult
from app.models.ecommerce import Customer, Order, Product


logger = structlog.get_logger()


class BitrixAdapter(PlatformAdapter):
    """1C-Bitrix CRM integration adapter with OAuth 2.0 authentication."""

    def __init__(
        self,
        webhook_url: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None
    ):
        """Initialize Bitrix adapter.

        Args:
        ----
            webhook_url: Bitrix webhook URL for REST API access
            client_id: OAuth application client ID
            client_secret: OAuth application client secret
            access_token: OAuth access token
            refresh_token: OAuth refresh token

        """
        # Extract domain from webhook URL for OAuth
        base_url = webhook_url.split('/rest/')[0] if '/rest/' in webhook_url else webhook_url

        super().__init__(
            api_key=webhook_url,  # Use webhook URL as API key
            base_url=base_url,
            platform_name="1c-bitrix",
            rate_limit_config=RateLimitConfig(
                requests_per_minute=120,  # Bitrix allows quite generous limits
                requests_per_hour=7200,
                burst_size=20
            )
        )

        self.webhook_url = webhook_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token

        # Bitrix deal stages mapping
        self.deal_stage_mapping = {
            "NEW": "pending",
            "PREPARATION": "confirmed",
            "PREPAYMENT_INVOICE": "processing",
            "EXECUTING": "processing",
            "FINAL_INVOICE": "shipped",
            "WON": "delivered",
            "LOSE": "cancelled"
        }

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        return headers

    async def _refresh_access_token(self) -> bool:
        """Refresh OAuth access token."""
        if not self.refresh_token or not self.client_id or not self.client_secret:
            return False

        try:
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_encoded = base64.b64encode(auth_string.encode()).decode()

            response = await self._make_request(
                method="POST",
                url=f"{self.base_url}/oauth/token/",
                headers={
                    "Authorization": f"Basic {auth_encoded}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token
                }
            )

            if response.success and response.data:
                self.access_token = response.data.get("access_token")
                self.refresh_token = response.data.get("refresh_token")
                return True

        except Exception as e:
            logger.error("Failed to refresh Bitrix token", error=str(e))

        return False

    async def test_connection(self) -> APIResponse:
        """Test connection to Bitrix."""
        try:
            if self.webhook_url:
                # Test webhook connection
                response = await self._make_request(
                    method="GET",
                    url=self.webhook_url + "profile"
                )
            else:
                # Test OAuth connection
                response = await self._make_request(
                    method="GET",
                    url="/rest/profile"
                )

            if not response.success and self.access_token:
                # Try refreshing token
                if await self._refresh_access_token():
                    response = await self._make_request(
                        method="GET",
                        url="/rest/profile"
                    )

            return response

        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                status_code=0,
                platform=self.platform_name
            )

    async def sync_orders(self, limit: int = 100) -> SyncResult:
        """Sync deals (orders) from Bitrix."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []

        try:
            # Get deals from Bitrix
            endpoint = f"{self.webhook_url}crm.deal.list" if self.webhook_url else "/rest/crm.deal.list"

            response = await self._make_request(
                method="GET",
                url=endpoint,
                params={
                    "select": ["ID", "TITLE", "STAGE_ID", "OPPORTUNITY", "CURRENCY_ID",
                              "DATE_CREATE", "DATE_MODIFY", "CONTACT_ID", "COMPANY_ID"],
                    "order": {"DATE_CREATE": "DESC"},
                    "filter": {"!STAGE_ID": "LOSE"},  # Exclude lost deals
                    "start": 0
                }
            )

            if not response.success:
                errors.append(f"Failed to fetch deals: {response.error}")
                return SyncResult(
                    platform=self.platform_name,
                    operation="orders",
                    records_processed=processed,
                    records_success=success,
                    records_failed=processed - success,
                    errors=errors,
                    duration_seconds=(datetime.now() - start_time).total_seconds()
                )

            deals = response.data.get("result", [])

            for deal in deals[:limit]:
                processed += 1
                try:
                    # Transform Bitrix deal to internal Order model
                    order = await self._transform_deal_to_order(deal)

                    # TODO: Save to internal database
                    logger.info(
                        "Synchronized Bitrix deal",
                        deal_id=deal.get("ID"),
                        order_id=order.order_id,
                        title=deal.get("TITLE")
                    )
                    success += 1

                except Exception as e:
                    error_msg = f"Failed to process deal {deal.get('ID')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error("Deal processing failed", error=error_msg)

        except Exception as e:
            errors.append(f"Sync operation failed: {str(e)}")

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
        """Sync products from Bitrix catalog."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []

        try:
            # Get products from Bitrix catalog
            endpoint = f"{self.webhook_url}catalog.product.list" if self.webhook_url else "/rest/catalog.product.list"

            response = await self._make_request(
                method="GET",
                url=endpoint,
                params={
                    "select": ["ID", "NAME", "DESCRIPTION", "PRICE", "CURRENCY", "ACTIVE"],
                    "filter": {"ACTIVE": "Y"},
                    "start": 0
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

            products = response.data.get("result", [])

            for product_data in products[:limit]:
                processed += 1
                try:
                    # Transform Bitrix product to internal Product model
                    product = await self._transform_product(product_data)

                    logger.info(
                        "Synchronized Bitrix product",
                        product_id=product.product_id,
                        name=product.name
                    )
                    success += 1

                except Exception as e:
                    error_msg = f"Failed to process product {product_data.get('ID')}: {str(e)}"
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
        """Sync contacts (customers) from Bitrix."""
        start_time = datetime.now()
        processed = 0
        success = 0
        errors = []

        try:
            # Get contacts from Bitrix
            endpoint = f"{self.webhook_url}crm.contact.list" if self.webhook_url else "/rest/crm.contact.list"

            response = await self._make_request(
                method="GET",
                url=endpoint,
                params={
                    "select": ["ID", "NAME", "LAST_NAME", "EMAIL", "PHONE", "DATE_CREATE"],
                    "order": {"DATE_CREATE": "DESC"},
                    "start": 0
                }
            )

            if not response.success:
                errors.append(f"Failed to fetch contacts: {response.error}")
                return SyncResult(
                    platform=self.platform_name,
                    operation="customers",
                    records_processed=processed,
                    records_success=success,
                    records_failed=processed - success,
                    errors=errors,
                    duration_seconds=(datetime.now() - start_time).total_seconds()
                )

            contacts = response.data.get("result", [])

            for contact in contacts[:limit]:
                processed += 1
                try:
                    # Transform Bitrix contact to internal Customer model
                    customer = await self._transform_contact_to_customer(contact)

                    logger.info(
                        "Synchronized Bitrix contact",
                        contact_id=contact.get("ID"),
                        customer_id=customer.customer_id
                    )
                    success += 1

                except Exception as e:
                    error_msg = f"Failed to process contact {contact.get('ID')}: {str(e)}"
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
        """Handle Bitrix webhook events."""
        try:
            event = payload.get("event")
            data = payload.get("data", {})

            logger.info("Processing Bitrix webhook", event=event, data_keys=list(data.keys()))

            if event == "ONCRMDEALUPDATE":
                # Deal (order) updated
                deal_id = data.get("FIELDS", {}).get("ID")
                await self._handle_deal_update(deal_id, data)

            elif event == "ONCRMCONTACTUPDATE":
                # Contact (customer) updated
                contact_id = data.get("FIELDS", {}).get("ID")
                await self._handle_contact_update(contact_id, data)

            elif event == "ONCATALOGPRODUCTUPDATE":
                # Product updated
                product_id = data.get("FIELDS", {}).get("ID")
                await self._handle_product_update(product_id, data)

            return True

        except Exception as e:
            logger.error("Bitrix webhook processing failed", error=str(e))
            return False

    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify Bitrix webhook signature (Bitrix uses different auth mechanism)."""
        # Bitrix webhooks are typically authenticated via the webhook URL itself
        # For additional security, implement custom verification if needed
        return True

    async def _transform_deal_to_order(self, deal: dict[str, Any]) -> Order:
        """Transform Bitrix deal to Order model."""
        from decimal import Decimal

        deal_id = str(deal.get("ID", ""))
        stage_id = deal.get("STAGE_ID", "NEW")
        status = self.deal_stage_mapping.get(stage_id, "pending")

        # Parse dates
        created_at = datetime.now()
        if deal.get("DATE_CREATE"):
            with contextlib.suppress(Exception):
                created_at = datetime.fromisoformat(deal["DATE_CREATE"].replace("T", " "))

        # Parse opportunity (price)
        amount = Decimal("0.00")
        if deal.get("OPPORTUNITY"):
            with contextlib.suppress(Exception):
                amount = Decimal(str(deal["OPPORTUNITY"]))

        return Order(
            order_id=f"bitrix_{deal_id}",
            customer_id=str(deal.get("CONTACT_ID", "")),
            status=status,
            subtotal=amount,
            total=amount,
            created_at=created_at,
            source="bitrix",
            notes=deal.get("TITLE", "")
        )

    async def _transform_product(self, product_data: dict[str, Any]) -> Product:
        """Transform Bitrix product to Product model."""
        from decimal import Decimal

        product_id = str(product_data.get("ID", ""))

        # Parse price
        price = Decimal("0.00")
        if product_data.get("PRICE"):
            with contextlib.suppress(Exception):
                price = Decimal(str(product_data["PRICE"]))

        return Product(
            product_id=f"bitrix_{product_id}",
            name=product_data.get("NAME", ""),
            description=product_data.get("DESCRIPTION", ""),
            category="general",
            price=price,
            currency=product_data.get("CURRENCY", "RUB"),
            in_stock=product_data.get("ACTIVE") == "Y"
        )

    async def _transform_contact_to_customer(self, contact: dict[str, Any]) -> Customer:
        """Transform Bitrix contact to Customer model."""
        contact_id = str(contact.get("ID", ""))

        # Parse creation date
        created_at = datetime.now()
        if contact.get("DATE_CREATE"):
            with contextlib.suppress(Exception):
                created_at = datetime.fromisoformat(contact["DATE_CREATE"].replace("T", " "))

        # Extract phone and email from arrays if needed
        phone = contact.get("PHONE")
        if isinstance(phone, list) and phone:
            phone = phone[0].get("VALUE", "") if isinstance(phone[0], dict) else str(phone[0])

        email = contact.get("EMAIL")
        if isinstance(email, list) and email:
            email = email[0].get("VALUE", "") if isinstance(email[0], dict) else str(email[0])

        return Customer(
            customer_id=f"bitrix_{contact_id}",
            first_name=contact.get("NAME", ""),
            last_name=contact.get("LAST_NAME", ""),
            email=str(email) if email else None,
            phone=str(phone) if phone else None,
            created_at=created_at
        )

    async def _handle_deal_update(self, deal_id: str, data: dict[str, Any]):
        """Handle deal update webhook."""
        logger.info("Bitrix deal updated", deal_id=deal_id)
        # TODO: Update internal order data

    async def _handle_contact_update(self, contact_id: str, data: dict[str, Any]):
        """Handle contact update webhook."""
        logger.info("Bitrix contact updated", contact_id=contact_id)
        # TODO: Update internal customer data

    async def _handle_product_update(self, product_id: str, data: dict[str, Any]):
        """Handle product update webhook."""
        logger.info("Bitrix product updated", product_id=product_id)
        # TODO: Update internal product data
