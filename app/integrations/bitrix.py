"""Интеграция с 1C-Bitrix."""
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


class BitrixAdapter(PlatformAdapter, OrderAdapter, ProductAdapter, CustomerAdapter):
    """Адаптер для интеграции с 1C-Bitrix через REST API и OAuth 2.0."""

    def __init__(self, credentials: dict[str, str], config: dict[str, Any] | None = None):
        super().__init__("1c-bitrix", credentials, config)
        
        self.webhook_url = credentials.get("webhook_url", "")
        self.client_id = credentials.get("client_id", "")
        self.client_secret = credentials.get("client_secret", "")
        self.access_token = credentials.get("access_token", "")
        self.refresh_token = credentials.get("refresh_token", "")
        
        # Базовый URL API (извлекается из webhook URL)
        if self.webhook_url:
            parts = self.webhook_url.split("/rest/")
            self.base_url = parts[0] + "/rest" if parts else ""
        else:
            self.base_url = ""

    async def authenticate(self) -> bool:
        """Проверить OAuth 2.0 токены и обновить при необходимости."""
        if not self.access_token:
            raise AuthenticationError("Отсутствует access_token", "1c-bitrix")

        try:
            async with httpx.AsyncClient() as client:
                # Проверяем токен через simple API call
                response = await client.get(
                    f"{self.base_url}/user.current",
                    params={"auth": self.access_token}
                )
                
                if response.status_code == 200:
                    self._log_api_call("GET", "/user.current", 200)
                    return True
                elif response.status_code == 401:
                    # Пытаемся обновить токен
                    return await self._refresh_access_token()
                else:
                    self._log_api_call("GET", "/user.current", response.status_code)
                    return False

        except Exception as e:
            self.logger.error("Ошибка аутентификации Bitrix", error=str(e))
            raise AuthenticationError(f"Ошибка аутентификации: {str(e)}", "1c-bitrix")

    async def _refresh_access_token(self) -> bool:
        """Обновить access token используя refresh token."""
        if not self.refresh_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/oauth/token/",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": self.refresh_token
                    }
                )

                if response.status_code == 200:
                    token_data = response.json()
                    self.access_token = token_data.get("access_token", "")
                    self.refresh_token = token_data.get("refresh_token", "")
                    
                    self.logger.info("Access token обновлен")
                    return True

                return False

        except Exception as e:
            self.logger.error("Ошибка обновления токена", error=str(e))
            return False

    async def sync_orders(self, since: datetime | None = None) -> SyncResult:
        """Синхронизация заказов (сделок) из Bitrix."""
        try:
            params = {
                "auth": self.access_token,
                "order": {"DATE_CREATE": "DESC"},
                "filter": {}
            }

            if since:
                params["filter"][">DATE_CREATE"] = since.strftime("%Y-%m-%d %H:%M:%S")

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/crm.deal.list",
                    params=params
                )

                if response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded", "1c-bitrix")
                elif response.status_code != 200:
                    raise AdapterError(f"API error: {response.status_code}", "1c-bitrix")

                data = response.json()
                deals = data.get("result", [])

                self.logger.info(f"Получено {len(deals)} сделок из Bitrix")

                # TODO: Преобразовать сделки Bitrix в модель Order и сохранить в БД

                return SyncResult(
                    success=True,
                    records_synced=len(deals),
                    sync_type="orders"
                )

        except Exception as e:
            self.logger.error("Ошибка синхронизации заказов", error=str(e))
            return SyncResult(
                success=False,
                sync_type="orders",
                errors=[str(e)]
            )

    async def sync_products(self, since: datetime | None = None) -> SyncResult:
        """Синхронизация товаров из каталога Bitrix."""
        try:
            params = {
                "auth": self.access_token,
                "order": {"DATE_CREATE": "DESC"}
            }

            if since:
                params["filter"] = {">DATE_CREATE": since.strftime("%Y-%m-%d %H:%M:%S")}

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/catalog.product.list",
                    params=params
                )

                if response.status_code != 200:
                    raise AdapterError(f"API error: {response.status_code}", "1c-bitrix")

                data = response.json()
                products = data.get("result", [])

                self.logger.info(f"Получено {len(products)} товаров из каталога Bitrix")

                return SyncResult(
                    success=True,
                    records_synced=len(products),
                    sync_type="products"
                )

        except Exception as e:
            self.logger.error("Ошибка синхронизации товаров", error=str(e))
            return SyncResult(
                success=False,
                sync_type="products",
                errors=[str(e)]
            )

    async def sync_customers(self, since: datetime | None = None) -> SyncResult:
        """Синхронизация контактов из Bitrix CRM."""
        try:
            params = {
                "auth": self.access_token,
                "order": {"DATE_CREATE": "DESC"}
            }

            if since:
                params["filter"] = {">DATE_CREATE": since.strftime("%Y-%m-%d %H:%M:%S")}

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/crm.contact.list",
                    params=params
                )

                if response.status_code != 200:
                    raise AdapterError(f"API error: {response.status_code}", "1c-bitrix")

                data = response.json()
                contacts = data.get("result", [])

                self.logger.info(f"Получено {len(contacts)} контактов из Bitrix CRM")

                return SyncResult(
                    success=True,
                    records_synced=len(contacts),
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
        """Обработка webhook от Bitrix."""
        message_id = self._generate_message_id()
        
        try:
            # Проверка подписи webhook
            if not self._verify_webhook_signature(payload):
                raise AdapterError("Invalid webhook signature", "1c-bitrix", "INVALID_SIGNATURE")

            self.logger.info("Обработка Bitrix webhook", event_type=event_type, message_id=message_id)

            if event_type == "ONCRMDEALUPDATE":
                await self._handle_deal_update(payload.get("data", {}))
            elif event_type == "ONCRMDEALDELETE":
                await self._handle_deal_delete(payload.get("data", {}))
            elif event_type == "ONCRMCONTACTUPDATE":
                await self._handle_contact_update(payload.get("data", {}))
            else:
                self.logger.warning("Неизвестный тип события", event_type=event_type)

            return message_id

        except Exception as e:
            self.logger.error("Ошибка обработки webhook", error=str(e), message_id=message_id)
            raise

    async def get_order_status(self, order_id: str) -> str:
        """Получить статус сделки в Bitrix."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/crm.deal.get",
                    params={
                        "auth": self.access_token,
                        "id": order_id
                    }
                )

                if response.status_code != 200:
                    raise AdapterError(f"API error: {response.status_code}", "1c-bitrix")

                data = response.json()
                deal = data.get("result", {})
                stage_id = deal.get("STAGE_ID", "")

                # Преобразование stage_id в стандартный статус
                return self._map_bitrix_stage_to_status(stage_id)

        except Exception as e:
            self.logger.error("Ошибка получения статуса заказа", error=str(e), order_id=order_id)
            raise

    async def update_order_status(self, order_id: str, status: str) -> bool:
        """Обновить статус сделки в Bitrix."""
        try:
            stage_id = self._map_status_to_bitrix_stage(status)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/crm.deal.update",
                    data={
                        "auth": self.access_token,
                        "id": order_id,
                        "fields": {"STAGE_ID": stage_id}
                    }
                )

                return response.status_code == 200

        except Exception as e:
            self.logger.error("Ошибка обновления статуса заказа", error=str(e), order_id=order_id)
            return False

    # Реализация методов адаптеров
    async def create_order(self, order: Order) -> str:
        """Создать сделку в Bitrix."""
        # Реализация создания сделки
        pass

    async def update_order(self, order_id: str, order: Order) -> bool:
        """Обновить сделку в Bitrix."""
        # Реализация обновления сделки
        pass

    async def cancel_order(self, order_id: str, reason: str) -> bool:
        """Отменить сделку в Bitrix."""
        return await self.update_order_status(order_id, "cancelled")

    async def get_product(self, product_id: str) -> Product | None:
        """Получить товар из каталога Bitrix."""
        # Реализация получения товара
        pass

    async def update_product(self, product_id: str, product: Product) -> bool:
        """Обновить товар в каталоге Bitrix."""
        # Реализация обновления товара
        pass

    async def update_stock(self, product_id: str, quantity: int) -> bool:
        """Обновить остатки товара в Bitrix."""
        # Реализация обновления остатков
        pass

    async def get_customer(self, customer_id: str) -> Customer | None:
        """Получить контакт из Bitrix CRM."""
        # Реализация получения контакта
        pass

    async def create_customer(self, customer: Customer) -> str:
        """Создать контакт в Bitrix CRM."""
        # Реализация создания контакта
        pass

    async def update_customer(self, customer_id: str, customer: Customer) -> bool:
        """Обновить контакт в Bitrix CRM."""
        # Реализация обновления контакта
        pass

    def _verify_webhook_signature(self, payload: dict[str, Any]) -> bool:
        """Проверить подпись webhook."""
        # Простая заглушка - в реальности нужно проверять подпись
        return True

    async def _handle_deal_update(self, data: dict[str, Any]):
        """Обработать обновление сделки."""
        deal_id = data.get("FIELDS", {}).get("ID")
        self.logger.info("Обновление сделки", deal_id=deal_id)

    async def _handle_deal_delete(self, data: dict[str, Any]):
        """Обработать удаление сделки."""
        deal_id = data.get("FIELDS", {}).get("ID")
        self.logger.info("Удаление сделки", deal_id=deal_id)

    async def _handle_contact_update(self, data: dict[str, Any]):
        """Обработать обновление контакта."""
        contact_id = data.get("FIELDS", {}).get("ID")
        self.logger.info("Обновление контакта", contact_id=contact_id)

    def _map_bitrix_stage_to_status(self, stage_id: str) -> str:
        """Преобразовать stage_id Bitrix в стандартный статус."""
        mapping = {
            "NEW": OrderStatus.PENDING.value,
            "PREPARATION": OrderStatus.PROCESSING.value,
            "PREPAYMENT_INVOICE": OrderStatus.CONFIRMED.value,
            "WON": OrderStatus.DELIVERED.value,
            "LOSE": OrderStatus.CANCELLED.value
        }
        return mapping.get(stage_id, OrderStatus.PENDING.value)

    def _map_status_to_bitrix_stage(self, status: str) -> str:
        """Преобразовать стандартный статус в stage_id Bitrix."""
        mapping = {
            OrderStatus.PENDING.value: "NEW",
            OrderStatus.PROCESSING.value: "PREPARATION", 
            OrderStatus.CONFIRMED.value: "PREPAYMENT_INVOICE",
            OrderStatus.DELIVERED.value: "WON",
            OrderStatus.CANCELLED.value: "LOSE"
        }
        return mapping.get(status, "NEW")