"""Интеграция с Ozon."""
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


class OzonAdapter(PlatformAdapter, OrderAdapter, ProductAdapter, CustomerAdapter):
    """Адаптер для интеграции с Ozon через API и Chat API."""

    def __init__(self, credentials: dict[str, str], config: dict[str, Any] | None = None):
        super().__init__("ozon", credentials, config)
        
        self.client_id = credentials.get("client_id", "")
        self.api_key = credentials.get("api_key", "")
        self.chat_token = credentials.get("chat_token", "")
        
        # API endpoints
        self.api_base_url = "https://api-seller.ozon.ru"
        self.chat_api_url = "https://api-chat.ozon.ru"
        
        # Rate limiting
        self.requests_per_minute = 1000  # Ozon имеет высокие лимиты

    async def authenticate(self) -> bool:
        """Проверить API ключи Ozon."""
        if not self.client_id or not self.api_key:
            raise AuthenticationError("Отсутствует client_id или api_key", "ozon")

        try:
            headers = self._get_auth_headers()
            
            async with httpx.AsyncClient() as client:
                # Проверяем подключение через API продавца
                response = await client.post(
                    f"{self.api_base_url}/v1/seller/info",
                    headers=headers
                )
                
                self._log_api_call("POST", "/v1/seller/info", response.status_code)
                
                if response.status_code == 200:
                    return True
                elif response.status_code == 401:
                    raise AuthenticationError("Неверные учетные данные", "ozon")
                elif response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded", "ozon")
                else:
                    return False

        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            self.logger.error("Ошибка аутентификации Ozon", error=str(e))
            raise AuthenticationError(f"Ошибка аутентификации: {str(e)}", "ozon")

    async def sync_orders(self, since: datetime | None = None) -> SyncResult:
        """Синхронизация заказов (отправлений) из Ozon."""
        try:
            headers = self._get_auth_headers()
            
            # Параметры для получения отправлений
            request_data = {
                "dir": "ASC",
                "filter": {
                    "since": since.isoformat() if since else None,
                    "status": ""  # Все статусы
                },
                "limit": 1000,
                "offset": 0,
                "with": {
                    "analytics_data": True,
                    "financial_data": True
                }
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base_url}/v3/posting/fbs/list",
                    headers=headers,
                    json=request_data
                )

                if response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded", "ozon", retry_after=60)
                elif response.status_code != 200:
                    raise AdapterError(f"API error: {response.status_code}", "ozon")

                data = response.json()
                postings = data.get("result", {}).get("postings", [])

                self.logger.info(f"Получено {len(postings)} отправлений из Ozon")

                # Получаем дополнительную информацию по каждому отправлению
                for posting in postings:
                    posting_number = posting.get("posting_number")
                    if posting_number:
                        # Получаем трекинг информацию
                        tracking_info = await self._get_posting_tracking(posting_number, headers)
                        posting["tracking_info"] = tracking_info

                return SyncResult(
                    success=True,
                    records_synced=len(postings),
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
        """Синхронизация товаров из каталога Ozon."""
        try:
            headers = self._get_auth_headers()

            request_data = {
                "filter": {
                    "visibility": "ALL"
                },
                "last_id": "",
                "limit": 1000
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base_url}/v2/product/list",
                    headers=headers,
                    json=request_data
                )

                if response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded", "ozon")
                elif response.status_code != 200:
                    raise AdapterError(f"API error: {response.status_code}", "ozon")

                data = response.json()
                products = data.get("result", {}).get("items", [])

                self.logger.info(f"Получено {len(products)} товаров из каталога Ozon")

                return SyncResult(
                    success=True,
                    records_synced=len(products),
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
        """Синхронизация покупателей - Ozon не предоставляет прямого доступа."""
        self.logger.info("Ozon не предоставляет API для получения данных покупателей")
        return SyncResult(
            success=True,
            records_synced=0,
            sync_type="customers"
        )

    async def handle_webhook(self, event_type: str, payload: dict[str, Any]) -> str:
        """Обработка webhook от Ozon."""
        message_id = self._generate_message_id()
        
        try:
            self.logger.info("Обработка Ozon webhook", event_type=event_type, message_id=message_id)

            if event_type == "posting_created":
                await self._handle_posting_created(payload.get("data", {}))
            elif event_type == "posting_status_changed":
                await self._handle_posting_status_changed(payload.get("data", {}))
            elif event_type == "chat_new_message":
                await self._handle_chat_message(payload.get("data", {}))
            else:
                self.logger.warning("Неизвестный тип события", event_type=event_type)

            return message_id

        except Exception as e:
            self.logger.error("Ошибка обработки webhook", error=str(e), message_id=message_id)
            raise

    async def get_order_status(self, order_id: str) -> str:
        """Получить статус отправления в Ozon."""
        try:
            headers = self._get_auth_headers()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/v3/posting/fbs/get",
                    headers=headers,
                    json={"posting_number": order_id}
                )

                if response.status_code != 200:
                    raise AdapterError(f"API error: {response.status_code}", "ozon")

                data = response.json()
                posting = data.get("result", {})
                ozon_status = posting.get("status", "")

                # Преобразуем статус Ozon в стандартный
                return self._map_ozon_status_to_standard(ozon_status)

        except Exception as e:
            self.logger.error("Ошибка получения статуса заказа", error=str(e), order_id=order_id)
            raise

    async def update_order_status(self, order_id: str, status: str) -> bool:
        """Обновить статус отправления - ограниченные возможности в Ozon."""
        try:
            # Ozon позволяет только подтверждать отправку и отменять
            if status == OrderStatus.SHIPPED.value:
                return await self._ship_posting(order_id)
            elif status == OrderStatus.CANCELLED.value:
                return await self._cancel_posting(order_id)
            else:
                self.logger.warning(
                    "Ozon не поддерживает обновление до этого статуса",
                    status=status,
                    order_id=order_id
                )
                return False

        except Exception as e:
            self.logger.error("Ошибка обновления статуса заказа", error=str(e), order_id=order_id)
            return False

    async def create_chat_ticket(self, customer_request: dict[str, Any]) -> str:
        """Создать тикет в чате поддержки Ozon."""
        try:
            if not self.chat_token:
                raise AdapterError("Отсутствует chat_token для Ozon", "ozon")

            headers = self._get_chat_auth_headers()

            ticket_data = {
                "chat_id": customer_request.get("chat_id"),
                "message": customer_request.get("message", ""),
                "type": "support_ticket"
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.chat_api_url}/v1/chat/ticket",
                    headers=headers,
                    json=ticket_data
                )

                if response.status_code == 201:
                    data = response.json()
                    return data.get("ticket_id", "")
                else:
                    raise AdapterError(f"Chat API error: {response.status_code}", "ozon")

        except Exception as e:
            self.logger.error("Ошибка создания тикета", error=str(e))
            raise

    # Реализация методов адаптеров
    async def create_order(self, order: Order) -> str:
        """Создать заказ - не поддерживается Ozon."""
        raise AdapterError("Создание заказов не поддерживается Ozon", "ozon")

    async def update_order(self, order_id: str, order: Order) -> bool:
        """Обновить заказ - ограниченные возможности."""
        return await self.update_order_status(order_id, order.status.value)

    async def cancel_order(self, order_id: str, reason: str) -> bool:
        """Отменить отправление в Ozon."""
        return await self._cancel_posting(order_id, reason)

    async def get_product(self, product_id: str) -> Product | None:
        """Получить товар из каталога Ozon."""
        # Реализация получения товара
        pass

    async def update_product(self, product_id: str, product: Product) -> bool:
        """Обновить товар в каталоге Ozon."""
        # Реализация обновления товара
        pass

    async def update_stock(self, product_id: str, quantity: int) -> bool:
        """Обновить остатки товара в Ozon."""
        try:
            headers = self._get_auth_headers()

            request_data = {
                "stocks": [{
                    "offer_id": product_id,
                    "stock": quantity,
                    "warehouse_id": 0  # Основной склад
                }]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/v1/product/import/stocks",
                    headers=headers,
                    json=request_data
                )

                return response.status_code == 200

        except Exception as e:
            self.logger.error("Ошибка обновления остатков", error=str(e), product_id=product_id)
            return False

    async def get_customer(self, customer_id: str) -> Customer | None:
        """Получить покупателя - не поддерживается Ozon."""
        return None

    async def create_customer(self, customer: Customer) -> str:
        """Создать покупателя - не поддерживается Ozon."""
        raise AdapterError("Создание покупателей не поддерживается Ozon", "ozon")

    async def update_customer(self, customer_id: str, customer: Customer) -> bool:
        """Обновить покупателя - не поддерживается Ozon."""
        return False

    def _get_auth_headers(self) -> dict[str, str]:
        """Получить заголовки аутентификации для основного API."""
        return {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def _get_chat_auth_headers(self) -> dict[str, str]:
        """Получить заголовки аутентификации для Chat API."""
        return {
            "Authorization": f"Bearer {self.chat_token}",
            "Content-Type": "application/json"
        }

    async def _get_posting_tracking(self, posting_number: str, headers: dict[str, str]) -> dict[str, Any]:
        """Получить информацию о трекинге отправления."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/v2/posting/tracking",
                    headers=headers,
                    json={"posting_number": posting_number}
                )

                if response.status_code == 200:
                    return response.json().get("result", {})
                else:
                    return {}

        except Exception as e:
            self.logger.error("Ошибка получения трекинга", error=str(e), posting_number=posting_number)
            return {}

    async def _ship_posting(self, posting_number: str) -> bool:
        """Отправить отправление."""
        try:
            headers = self._get_auth_headers()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/v2/posting/fbs/ship",
                    headers=headers,
                    json={"posting_number": posting_number}
                )

                return response.status_code == 200

        except Exception as e:
            self.logger.error("Ошибка отправки", error=str(e), posting_number=posting_number)
            return False

    async def _cancel_posting(self, posting_number: str, reason: str = "По запросу продавца") -> bool:
        """Отменить отправление."""
        try:
            headers = self._get_auth_headers()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/v2/posting/fbs/cancel",
                    headers=headers,
                    json={
                        "posting_number": posting_number,
                        "cancel_reason_id": 400,  # Стандартная причина
                        "cancel_reason_message": reason
                    }
                )

                return response.status_code == 200

        except Exception as e:
            self.logger.error("Ошибка отмены", error=str(e), posting_number=posting_number)
            return False

    async def _handle_posting_created(self, data: dict[str, Any]):
        """Обработать создание нового отправления."""
        posting_number = data.get("posting_number")
        self.logger.info("Новое отправление Ozon", posting_number=posting_number)

    async def _handle_posting_status_changed(self, data: dict[str, Any]):
        """Обработать изменение статуса отправления."""
        posting_number = data.get("posting_number")
        new_status = data.get("status")
        self.logger.info("Изменен статус отправления Ozon", posting_number=posting_number, status=new_status)

    async def _handle_chat_message(self, data: dict[str, Any]):
        """Обработать новое сообщение в чате."""
        chat_id = data.get("chat_id")
        message = data.get("message", "")
        self.logger.info("Новое сообщение в чате Ozon", chat_id=chat_id, message=message[:50])

    def _map_ozon_status_to_standard(self, ozon_status: str) -> str:
        """Преобразовать статус Ozon в стандартный."""
        mapping = {
            "awaiting_registration": OrderStatus.PENDING.value,
            "awaiting_approve": OrderStatus.CONFIRMED.value,
            "awaiting_packaging": OrderStatus.PROCESSING.value,
            "awaiting_deliver": OrderStatus.SHIPPED.value,
            "delivered": OrderStatus.DELIVERED.value,
            "cancelled": OrderStatus.CANCELLED.value
        }
        return mapping.get(ozon_status.lower(), OrderStatus.PENDING.value)