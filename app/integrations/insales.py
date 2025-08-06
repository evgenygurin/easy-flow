"""Интеграция с InSales."""
import hashlib
import hmac
from datetime import datetime
from typing import Any

import httpx

from app.integrations.base import (
    AdapterError,
    AuthenticationError,
    CustomerAdapter,
    OrderAdapter,
    PlatformAdapter,
    ProductAdapter,
    RateLimitError,
    SyncResult,
)
from app.models.ecommerce import Customer, Order, OrderStatus, Product


class InSalesAdapter(PlatformAdapter, OrderAdapter, ProductAdapter, CustomerAdapter):
    """Адаптер для интеграции с InSales через REST API и webhook."""

    def __init__(self, credentials: dict[str, str], config: dict[str, Any] | None = None):
        super().__init__("insales", credentials, config)
        
        self.domain = credentials.get("domain", "")
        self.api_key = credentials.get("api_key", "")
        self.password = credentials.get("password", "")
        self.webhook_secret = credentials.get("webhook_secret", "")
        
        # API endpoint
        if self.domain:
            self.api_base_url = f"https://{self.domain}/admin"
        else:
            self.api_base_url = ""

    async def authenticate(self) -> bool:
        """Проверить аутентификацию через Basic Auth."""
        if not self.api_key or not self.password or not self.domain:
            raise AuthenticationError("Отсутствуют учетные данные", "insales")

        try:
            async with httpx.AsyncClient() as client:
                # Проверяем подключение через получение информации о магазине
                response = await client.get(
                    f"{self.api_base_url}/account.json",
                    auth=(self.api_key, self.password)
                )
                
                self._log_api_call("GET", "/account.json", response.status_code)
                
                if response.status_code == 200:
                    return True
                elif response.status_code == 401:
                    raise AuthenticationError("Неверные учетные данные", "insales")
                elif response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded", "insales")
                else:
                    return False

        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            self.logger.error("Ошибка аутентификации InSales", error=str(e))
            raise AuthenticationError(f"Ошибка аутентификации: {str(e)}", "insales")

    async def sync_orders(self, since: datetime | None = None) -> SyncResult:
        """Синхронизация заказов из InSales."""
        try:
            params = {
                "per_page": 250,
                "page": 1
            }

            if since:
                params["updated_since"] = since.isoformat()

            all_orders = []
            
            async with httpx.AsyncClient() as client:
                while True:
                    response = await client.get(
                        f"{self.api_base_url}/orders.json",
                        auth=(self.api_key, self.password),
                        params=params
                    )

                    if response.status_code == 429:
                        raise RateLimitError("Rate limit exceeded", "insales", retry_after=60)
                    elif response.status_code != 200:
                        raise AdapterError(f"API error: {response.status_code}", "insales")

                    data = response.json()
                    orders = data.get("orders", [])
                    
                    if not orders:
                        break
                        
                    all_orders.extend(orders)
                    params["page"] += 1

                    # InSales рекомендует делать паузы между запросами
                    await self._rate_limit_pause()

                self.logger.info(f"Получено {len(all_orders)} заказов из InSales")

                return SyncResult(
                    success=True,
                    records_synced=len(all_orders),
                    sync_type="orders"
                )

        except (RateLimitError, AdapterError):
            raise
        except Exception as e:
            self.logger.error("Ошибка синхронизации заказов", error=str(e))
            return SyncResult(
                success=False,
                sync_type="orders",
                errors=[str(e)]
            )

    async def sync_products(self, since: datetime | None = None) -> SyncResult:
        """Синхронизация товаров из InSales."""
        try:
            params = {
                "per_page": 250,
                "page": 1
            }

            if since:
                params["updated_since"] = since.isoformat()

            all_products = []

            async with httpx.AsyncClient() as client:
                while True:
                    response = await client.get(
                        f"{self.api_base_url}/products.json",
                        auth=(self.api_key, self.password),
                        params=params
                    )

                    if response.status_code == 429:
                        raise RateLimitError("Rate limit exceeded", "insales")
                    elif response.status_code != 200:
                        raise AdapterError(f"API error: {response.status_code}", "insales")

                    data = response.json()
                    products = data.get("products", [])
                    
                    if not products:
                        break
                        
                    all_products.extend(products)
                    params["page"] += 1

                    await self._rate_limit_pause()

                self.logger.info(f"Получено {len(all_products)} товаров из InSales")

                return SyncResult(
                    success=True,
                    records_synced=len(all_products),
                    sync_type="products"
                )

        except (RateLimitError, AdapterError):
            raise
        except Exception as e:
            self.logger.error("Ошибка синхронизации товаров", error=str(e))
            return SyncResult(
                success=False,
                sync_type="products",
                errors=[str(e)]
            )

    async def sync_customers(self, since: datetime | None = None) -> SyncResult:
        """Синхронизация клиентов из InSales."""
        try:
            params = {
                "per_page": 250,
                "page": 1
            }

            if since:
                params["updated_since"] = since.isoformat()

            all_clients = []

            async with httpx.AsyncClient() as client:
                while True:
                    response = await client.get(
                        f"{self.api_base_url}/clients.json",
                        auth=(self.api_key, self.password),
                        params=params
                    )

                    if response.status_code != 200:
                        break

                    data = response.json()
                    clients = data.get("clients", [])
                    
                    if not clients:
                        break
                        
                    all_clients.extend(clients)
                    params["page"] += 1

                    await self._rate_limit_pause()

                self.logger.info(f"Получено {len(all_clients)} клиентов из InSales")

                return SyncResult(
                    success=True,
                    records_synced=len(all_clients),
                    sync_type="customers"
                )

        except Exception as e:
            self.logger.error("Ошибка синхронизации клиентов", error=str(e))
            return SyncResult(
                success=False,
                sync_type="customers",
                errors=[str(e)]
            )

    async def handle_webhook(self, event_type: str, payload: dict[str, Any]) -> str:
        """Обработка webhook от InSales с проверкой подписи."""
        message_id = self._generate_message_id()
        
        try:
            # Проверяем подпись webhook
            if not self._verify_webhook_signature(payload):
                raise AdapterError("Invalid webhook signature", "insales", "INVALID_SIGNATURE")

            self.logger.info("Обработка InSales webhook", event_type=event_type, message_id=message_id)

            if event_type == "order_create":
                await self._handle_order_create(payload.get("data", {}))
            elif event_type == "order_update":
                await self._handle_order_update(payload.get("data", {}))
            elif event_type == "order_paid":
                await self._handle_order_paid(payload.get("data", {}))
            elif event_type == "product_update":
                await self._handle_product_update(payload.get("data", {}))
            else:
                self.logger.warning("Неизвестный тип события", event_type=event_type)

            return message_id

        except Exception as e:
            self.logger.error("Ошибка обработки webhook", error=str(e), message_id=message_id)
            raise

    async def get_order_status(self, order_id: str) -> str:
        """Получить статус заказа в InSales."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/orders/{order_id}.json",
                    auth=(self.api_key, self.password)
                )

                if response.status_code != 200:
                    raise AdapterError(f"API error: {response.status_code}", "insales")

                data = response.json()
                order = data.get("order", {})
                insales_status = order.get("fulfillment_status", "")

                return self._map_insales_status_to_standard(insales_status)

        except Exception as e:
            self.logger.error("Ошибка получения статуса заказа", error=str(e), order_id=order_id)
            raise

    async def update_order_status(self, order_id: str, status: str) -> bool:
        """Обновить статус заказа в InSales."""
        try:
            insales_status = self._map_status_to_insales(status)

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.api_base_url}/orders/{order_id}.json",
                    auth=(self.api_key, self.password),
                    json={
                        "order": {
                            "fulfillment_status": insales_status
                        }
                    }
                )

                return response.status_code == 200

        except Exception as e:
            self.logger.error("Ошибка обновления статуса заказа", error=str(e), order_id=order_id)
            return False

    # Реализация методов адаптеров
    async def create_order(self, order: Order) -> str:
        """Создать заказ в InSales."""
        try:
            order_data = {
                "order": {
                    "client_id": order.customer_id,
                    "order_lines": [
                        {
                            "variant_id": item.product_id,
                            "quantity": item.quantity,
                            "sale_price": float(item.product_price)
                        }
                        for item in order.items
                    ],
                    "delivery_title": order.shipping_method.value if order.shipping_method else "Доставка",
                    "delivery_price": float(order.shipping_cost)
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/orders.json",
                    auth=(self.api_key, self.password),
                    json=order_data
                )

                if response.status_code == 201:
                    data = response.json()
                    return str(data.get("order", {}).get("id", ""))
                else:
                    raise AdapterError(f"Ошибка создания заказа: {response.status_code}", "insales")

        except Exception as e:
            self.logger.error("Ошибка создания заказа", error=str(e))
            raise

    async def update_order(self, order_id: str, order: Order) -> bool:
        """Обновить заказ в InSales."""
        # Реализация обновления заказа
        return await self.update_order_status(order_id, order.status.value)

    async def cancel_order(self, order_id: str, reason: str) -> bool:
        """Отменить заказ в InSales."""
        return await self.update_order_status(order_id, OrderStatus.CANCELLED.value)

    async def get_product(self, product_id: str) -> Product | None:
        """Получить товар из InSales."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/products/{product_id}.json",
                    auth=(self.api_key, self.password)
                )

                if response.status_code == 200:
                    data = response.json()
                    product_data = data.get("product", {})
                    # TODO: Преобразовать данные InSales в модель Product
                    return None  # Заглушка

                return None

        except Exception as e:
            self.logger.error("Ошибка получения товара", error=str(e), product_id=product_id)
            return None

    async def update_product(self, product_id: str, product: Product) -> bool:
        """Обновить товар в InSales."""
        # Реализация обновления товара
        pass

    async def update_stock(self, product_id: str, quantity: int) -> bool:
        """Обновить остатки товара в InSales."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.api_base_url}/variants/{product_id}.json",
                    auth=(self.api_key, self.password),
                    json={
                        "variant": {
                            "quantity": quantity
                        }
                    }
                )

                return response.status_code == 200

        except Exception as e:
            self.logger.error("Ошибка обновления остатков", error=str(e), product_id=product_id)
            return False

    async def get_customer(self, customer_id: str) -> Customer | None:
        """Получить клиента из InSales."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/clients/{customer_id}.json",
                    auth=(self.api_key, self.password)
                )

                if response.status_code == 200:
                    data = response.json()
                    client_data = data.get("client", {})
                    # TODO: Преобразовать данные InSales в модель Customer
                    return None  # Заглушка

                return None

        except Exception as e:
            self.logger.error("Ошибка получения клиента", error=str(e), customer_id=customer_id)
            return None

    async def create_customer(self, customer: Customer) -> str:
        """Создать клиента в InSales."""
        try:
            client_data = {
                "client": {
                    "name": f"{customer.first_name} {customer.last_name}",
                    "email": customer.email,
                    "phone": customer.phone
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/clients.json",
                    auth=(self.api_key, self.password),
                    json=client_data
                )

                if response.status_code == 201:
                    data = response.json()
                    return str(data.get("client", {}).get("id", ""))
                else:
                    raise AdapterError(f"Ошибка создания клиента: {response.status_code}", "insales")

        except Exception as e:
            self.logger.error("Ошибка создания клиента", error=str(e))
            raise

    async def update_customer(self, customer_id: str, customer: Customer) -> bool:
        """Обновить клиента в InSales."""
        # Реализация обновления клиента
        pass

    def _verify_webhook_signature(self, payload: dict[str, Any]) -> bool:
        """Проверить подпись webhook InSales."""
        if not self.webhook_secret:
            return True  # Если секрет не установлен, пропускаем проверку

        signature = payload.get("signature", "")
        if not signature:
            return False

        # InSales использует HMAC-SHA256 для подписи
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            json.dumps(payload.get("data", {})).encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    async def _rate_limit_pause(self):
        """Пауза между запросами для соблюдения rate limit."""
        import asyncio
        await asyncio.sleep(0.5)  # 500ms пауза между запросами

    async def _handle_order_create(self, data: dict[str, Any]):
        """Обработать создание нового заказа."""
        order_id = data.get("id")
        self.logger.info("Новый заказ InSales", order_id=order_id)

    async def _handle_order_update(self, data: dict[str, Any]):
        """Обработать обновление заказа."""
        order_id = data.get("id")
        status = data.get("fulfillment_status", "")
        self.logger.info("Обновление заказа InSales", order_id=order_id, status=status)

    async def _handle_order_paid(self, data: dict[str, Any]):
        """Обработать оплату заказа."""
        order_id = data.get("id")
        self.logger.info("Оплата заказа InSales", order_id=order_id)

    async def _handle_product_update(self, data: dict[str, Any]):
        """Обработать обновление товара."""
        product_id = data.get("id")
        self.logger.info("Обновление товара InSales", product_id=product_id)

    def _map_insales_status_to_standard(self, insales_status: str) -> str:
        """Преобразовать статус InSales в стандартный."""
        mapping = {
            "pending": OrderStatus.PENDING.value,
            "paid": OrderStatus.CONFIRMED.value,
            "processing": OrderStatus.PROCESSING.value,
            "shipped": OrderStatus.SHIPPED.value,
            "delivered": OrderStatus.DELIVERED.value,
            "cancelled": OrderStatus.CANCELLED.value,
            "refunded": OrderStatus.RETURNED.value
        }
        return mapping.get(insales_status.lower(), OrderStatus.PENDING.value)

    def _map_status_to_insales(self, status: str) -> str:
        """Преобразовать стандартный статус в статус InSales."""
        mapping = {
            OrderStatus.PENDING.value: "pending",
            OrderStatus.CONFIRMED.value: "paid",
            OrderStatus.PROCESSING.value: "processing",
            OrderStatus.SHIPPED.value: "shipped",
            OrderStatus.DELIVERED.value: "delivered",
            OrderStatus.CANCELLED.value: "cancelled",
            OrderStatus.RETURNED.value: "refunded"
        }
        return mapping.get(status, "pending")