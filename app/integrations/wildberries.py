"""Интеграция с Wildberries."""
import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

import httpx

from app.integrations.base import (
    AdapterError,
    AuthenticationError,
    OrderAdapter,
    PlatformAdapter,
    RateLimitError,
    SyncResult,
)
from app.models.ecommerce import Order, OrderStatus


class WildberriesAdapter(PlatformAdapter, OrderAdapter):
    """Адаптер для интеграции с Wildberries через JWT аутентификацию."""

    def __init__(self, credentials: dict[str, str], config: dict[str, Any] | None = None):
        super().__init__("wildberries", credentials, config)
        
        self.api_key = credentials.get("api_key", "")
        self.seller_token = credentials.get("seller_token", "")
        
        # API endpoints
        self.api_base_url = "https://suppliers-api.wildberries.ru"
        self.seller_base_url = "https://seller.wildberries.ru"
        
        # Rate limiting - Wildberries имеет строгие лимиты
        self.requests_per_minute = 60
        self.rate_limiter = None

    async def authenticate(self) -> bool:
        """Проверить JWT токен аутентификации."""
        if not self.api_key:
            raise AuthenticationError("Отсутствует API key", "wildberries")

        try:
            headers = self._get_auth_headers()
            
            async with httpx.AsyncClient() as client:
                # Проверяем токен через API склада
                response = await client.get(
                    f"{self.api_base_url}/api/v3/warehouses",
                    headers=headers
                )
                
                self._log_api_call("GET", "/api/v3/warehouses", response.status_code)
                
                if response.status_code == 200:
                    return True
                elif response.status_code == 401:
                    raise AuthenticationError("Неверный API key", "wildberries")
                elif response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded", "wildberries")
                else:
                    return False

        except AuthenticationError:
            raise
        except RateLimitError:
            raise
        except Exception as e:
            self.logger.error("Ошибка аутентификации Wildberries", error=str(e))
            raise AuthenticationError(f"Ошибка аутентификации: {str(e)}", "wildberries")

    async def sync_orders(self, since: datetime | None = None) -> SyncResult:
        """Синхронизация заказов из Wildberries."""
        try:
            headers = self._get_auth_headers()
            
            # Параметры запроса
            params = {}
            if since:
                params["dateFrom"] = since.strftime("%Y-%m-%d")

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Получаем заказы
                response = await client.get(
                    f"{self.api_base_url}/api/v3/orders",
                    headers=headers,
                    params=params
                )

                if response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded", "wildberries", retry_after=60)
                elif response.status_code != 200:
                    raise AdapterError(f"API error: {response.status_code}", "wildberries")

                data = response.json()
                orders = data.get("orders", [])

                self.logger.info(f"Получено {len(orders)} заказов из Wildberries")

                # Получаем статусы заказов
                for order in orders:
                    order_id = order.get("id")
                    if order_id:
                        status_info = await self._get_order_status_info(order_id, headers)
                        order["status_info"] = status_info

                return SyncResult(
                    success=True,
                    records_synced=len(orders),
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
        """Синхронизация товаров из каталога Wildberries."""
        try:
            headers = self._get_auth_headers()

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Получаем список товаров
                response = await client.get(
                    f"{self.api_base_url}/content/v1/cards/cursor/list",
                    headers=headers,
                    params={"limit": 1000}
                )

                if response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded", "wildberries")
                elif response.status_code != 200:
                    raise AdapterError(f"API error: {response.status_code}", "wildberries")

                data = response.json()
                cards = data.get("data", {}).get("cards", [])

                self.logger.info(f"Получено {len(cards)} товаров из каталога Wildberries")

                return SyncResult(
                    success=True,
                    records_synced=len(cards),
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
        """Синхронизация покупателей - Wildberries не предоставляет прямого доступа."""
        self.logger.info("Wildberries не предоставляет API для получения данных покупателей")
        return SyncResult(
            success=True,
            records_synced=0,
            sync_type="customers"
        )

    async def handle_webhook(self, event_type: str, payload: dict[str, Any]) -> str:
        """Обработка webhook от Wildberries."""
        message_id = self._generate_message_id()
        
        try:
            self.logger.info("Обработка Wildberries webhook", event_type=event_type, message_id=message_id)

            if event_type == "order_new":
                await self._handle_new_order(payload.get("data", {}))
            elif event_type == "order_status_changed":
                await self._handle_order_status_change(payload.get("data", {}))
            elif event_type == "order_cancelled":
                await self._handle_order_cancellation(payload.get("data", {}))
            else:
                self.logger.warning("Неизвестный тип события", event_type=event_type)

            return message_id

        except Exception as e:
            self.logger.error("Ошибка обработки webhook", error=str(e), message_id=message_id)
            raise

    async def get_order_status(self, order_id: str) -> str:
        """Получить статус заказа в Wildberries."""
        try:
            headers = self._get_auth_headers()
            status_info = await self._get_order_status_info(order_id, headers)
            
            # Преобразуем статус Wildberries в стандартный
            wb_status = status_info.get("supplierStatus", "")
            return self._map_wb_status_to_standard(wb_status)

        except Exception as e:
            self.logger.error("Ошибка получения статуса заказа", error=str(e), order_id=order_id)
            raise

    async def update_order_status(self, order_id: str, status: str) -> bool:
        """Обновить статус заказа - ограниченные возможности в Wildberries."""
        try:
            # Wildberries позволяет только отменять заказы и подтверждать сборку
            if status == OrderStatus.CANCELLED.value:
                return await self._cancel_order_wb(order_id)
            elif status == OrderStatus.PROCESSING.value:
                return await self._confirm_order_assembly(order_id)
            else:
                self.logger.warning(
                    "Wildberries не поддерживает обновление до этого статуса",
                    status=status,
                    order_id=order_id
                )
                return False

        except Exception as e:
            self.logger.error("Ошибка обновления статуса заказа", error=str(e), order_id=order_id)
            return False

    async def create_order(self, order: Order) -> str:
        """Создать заказ - не поддерживается Wildberries."""
        raise AdapterError("Создание заказов не поддерживается Wildberries", "wildberries")

    async def update_order(self, order_id: str, order: Order) -> bool:
        """Обновить заказ - ограниченные возможности."""
        # Можем только обновить статус
        return await self.update_order_status(order_id, order.status.value)

    async def cancel_order(self, order_id: str, reason: str) -> bool:
        """Отменить заказ в Wildberries."""
        return await self._cancel_order_wb(order_id, reason)

    def _get_auth_headers(self) -> dict[str, str]:
        """Получить заголовки аутентификации."""
        return {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }

    async def _get_order_status_info(self, order_id: str, headers: dict[str, str]) -> dict[str, Any]:
        """Получить детальную информацию о статусе заказа."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/api/v3/orders/{order_id}/status",
                    headers=headers
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    self.logger.warning("Не удалось получить статус заказа", order_id=order_id)
                    return {}

        except Exception as e:
            self.logger.error("Ошибка получения статуса заказа", error=str(e), order_id=order_id)
            return {}

    async def _cancel_order_wb(self, order_id: str, reason: str = "По запросу продавца") -> bool:
        """Отменить заказ в системе Wildberries."""
        try:
            headers = self._get_auth_headers()

            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.api_base_url}/api/v3/orders/{order_id}/cancel",
                    headers=headers,
                    json={"reason": reason}
                )

                return response.status_code == 204

        except Exception as e:
            self.logger.error("Ошибка отмены заказа", error=str(e), order_id=order_id)
            return False

    async def _confirm_order_assembly(self, order_id: str) -> bool:
        """Подтвердить сборку заказа."""
        try:
            headers = self._get_auth_headers()

            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.api_base_url}/api/v3/orders/{order_id}/confirm",
                    headers=headers
                )

                return response.status_code == 204

        except Exception as e:
            self.logger.error("Ошибка подтверждения сборки", error=str(e), order_id=order_id)
            return False

    async def _handle_new_order(self, data: dict[str, Any]):
        """Обработать новый заказ."""
        order_id = data.get("id")
        self.logger.info("Новый заказ Wildberries", order_id=order_id)
        
        # TODO: Создать заказ в локальной системе

    async def _handle_order_status_change(self, data: dict[str, Any]):
        """Обработать изменение статуса заказа."""
        order_id = data.get("id")
        new_status = data.get("status")
        self.logger.info("Изменен статус заказа Wildberries", order_id=order_id, status=new_status)
        
        # TODO: Обновить статус в локальной системе

    async def _handle_order_cancellation(self, data: dict[str, Any]):
        """Обработать отмену заказа."""
        order_id = data.get("id")
        reason = data.get("reason", "")
        self.logger.info("Отменен заказ Wildberries", order_id=order_id, reason=reason)
        
        # TODO: Отменить заказ в локальной системе

    def _map_wb_status_to_standard(self, wb_status: str) -> str:
        """Преобразовать статус Wildberries в стандартный."""
        mapping = {
            "new": OrderStatus.PENDING.value,
            "confirm": OrderStatus.CONFIRMED.value,
            "assembling": OrderStatus.PROCESSING.value,
            "sorted": OrderStatus.PROCESSING.value,
            "sold": OrderStatus.DELIVERED.value,
            "canceled": OrderStatus.CANCELLED.value,
            "canceled_by_client": OrderStatus.CANCELLED.value
        }
        return mapping.get(wb_status.lower(), OrderStatus.PENDING.value)