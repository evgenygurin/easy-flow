"""Модели данных для e-commerce интеграции."""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    """Статусы заказов."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class PaymentStatus(str, Enum):
    """Статусы платежей."""

    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethod(str, Enum):
    """Способы оплаты."""

    CARD = "card"
    CASH = "cash"
    ONLINE_BANKING = "online_banking"
    YOOMONEY = "yoomoney"
    QR_CODE = "qr_code"


class ShippingMethod(str, Enum):
    """Способы доставки."""

    COURIER = "courier"
    PICKUP = "pickup"
    POST = "post"
    EXPRESS = "express"


class Customer(BaseModel):
    """Модель клиента."""

    customer_id: str = Field(..., description="ID клиента")
    first_name: str = Field(..., description="Имя")
    last_name: str = Field(..., description="Фамилия")
    email: str | None = Field(None, description="Email")
    phone: str | None = Field(None, description="Телефон")
    created_at: datetime = Field(default_factory=datetime.now, description="Дата создания")
    updated_at: datetime = Field(default_factory=datetime.now, description="Дата обновления")

    # Дополнительные поля
    birth_date: datetime | None = Field(None, description="Дата рождения")
    gender: str | None = Field(None, description="Пол")
    loyalty_level: str = Field(default="bronze", description="Уровень лояльности")
    total_orders: int = Field(default=0, description="Общее количество заказов")
    total_spent: Decimal = Field(default=Decimal("0.00"), description="Общая сумма потрачена")


class Address(BaseModel):
    """Модель адреса."""

    address_id: str | None = Field(None, description="ID адреса")
    customer_id: str = Field(..., description="ID клиента")

    # Адресные поля
    country: str = Field(default="Россия", description="Страна")
    region: str | None = Field(None, description="Регион/область")
    city: str = Field(..., description="Город")
    street: str = Field(..., description="Улица")
    house: str = Field(..., description="Номер дома")
    apartment: str | None = Field(None, description="Квартира")
    postal_code: str | None = Field(None, description="Почтовый индекс")

    # Метаданные
    is_default: bool = Field(default=False, description="Адрес по умолчанию")
    address_type: str = Field(default="home", description="Тип адреса (home, work, other)")
    created_at: datetime = Field(default_factory=datetime.now, description="Дата создания")


class Product(BaseModel):
    """Модель товара."""

    product_id: str = Field(..., description="ID товара")
    name: str = Field(..., description="Название товара")
    description: str | None = Field(None, description="Описание")
    category: str = Field(..., description="Категория")
    brand: str | None = Field(None, description="Бренд")

    # Цены
    price: Decimal = Field(..., description="Цена")
    original_price: Decimal | None = Field(None, description="Первоначальная цена")
    currency: str = Field(default="RUB", description="Валюта")

    # Характеристики
    weight: Decimal | None = Field(None, description="Вес в граммах")
    dimensions: dict[str, Any] | None = Field(None, description="Размеры")
    color: str | None = Field(None, description="Цвет")
    size: str | None = Field(None, description="Размер")

    # Наличие
    in_stock: bool = Field(default=True, description="В наличии")
    stock_quantity: int = Field(default=0, description="Количество на складе")

    # Метаданные
    created_at: datetime = Field(default_factory=datetime.now, description="Дата создания")
    updated_at: datetime = Field(default_factory=datetime.now, description="Дата обновления")


class OrderItem(BaseModel):
    """Позиция заказа."""

    item_id: str | None = Field(None, description="ID позиции")
    order_id: str = Field(..., description="ID заказа")
    product_id: str = Field(..., description="ID товара")

    # Детали товара на момент заказа
    product_name: str = Field(..., description="Название товара")
    product_price: Decimal = Field(..., description="Цена товара")
    quantity: int = Field(..., ge=1, description="Количество")

    # Расчетные поля
    subtotal: Decimal = Field(..., description="Подытог")
    discount_amount: Decimal = Field(default=Decimal("0.00"), description="Размер скидки")
    total: Decimal = Field(..., description="Итого с учетом скидки")


class Order(BaseModel):
    """Модель заказа."""

    order_id: str = Field(..., description="ID заказа")
    customer_id: str = Field(..., description="ID клиента")

    # Статусы
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Статус заказа")
    payment_status: PaymentStatus = Field(default=PaymentStatus.PENDING, description="Статус оплаты")

    # Товары
    items: list[OrderItem] = Field(default_factory=list, description="Позиции заказа")

    # Суммы
    subtotal: Decimal = Field(..., description="Подытог")
    shipping_cost: Decimal = Field(default=Decimal("0.00"), description="Стоимость доставки")
    tax_amount: Decimal = Field(default=Decimal("0.00"), description="Налог")
    discount_amount: Decimal = Field(default=Decimal("0.00"), description="Скидка")
    total: Decimal = Field(..., description="Общая сумма")

    # Доставка
    shipping_method: ShippingMethod | None = Field(None, description="Способ доставки")
    shipping_address: Address | None = Field(None, description="Адрес доставки")
    estimated_delivery: datetime | None = Field(None, description="Ожидаемая дата доставки")
    tracking_number: str | None = Field(None, description="Трек-номер")

    # Оплата
    payment_method: PaymentMethod | None = Field(None, description="Способ оплаты")

    # Даты
    created_at: datetime = Field(default_factory=datetime.now, description="Дата создания")
    updated_at: datetime = Field(default_factory=datetime.now, description="Дата обновления")
    shipped_at: datetime | None = Field(None, description="Дата отправки")
    delivered_at: datetime | None = Field(None, description="Дата доставки")

    # Дополнительная информация
    notes: str | None = Field(None, description="Примечания")
    source: str = Field(default="web", description="Источник заказа")


class Payment(BaseModel):
    """Модель платежа."""

    payment_id: str = Field(..., description="ID платежа")
    order_id: str = Field(..., description="ID заказа")
    customer_id: str = Field(..., description="ID клиента")

    # Сумма и статус
    amount: Decimal = Field(..., description="Сумма платежа")
    currency: str = Field(default="RUB", description="Валюта")
    status: PaymentStatus = Field(default=PaymentStatus.PENDING, description="Статус платежа")

    # Способ оплаты
    method: PaymentMethod = Field(..., description="Способ оплаты")

    # Детали платежа
    transaction_id: str | None = Field(None, description="ID транзакции")
    gateway_response: dict[str, Any] | None = Field(None, description="Ответ платежного шлюза")

    # Даты
    created_at: datetime = Field(default_factory=datetime.now, description="Дата создания")
    processed_at: datetime | None = Field(None, description="Дата обработки")

    # Дополнительная информация
    description: str | None = Field(None, description="Описание платежа")
    metadata: dict[str, Any] | None = Field(None, description="Дополнительные данные")


class Cart(BaseModel):
    """Модель корзины покупок."""

    cart_id: str = Field(..., description="ID корзины")
    customer_id: str | None = Field(None, description="ID клиента")
    session_id: str | None = Field(None, description="ID сессии")

    # Товары
    items: list[OrderItem] = Field(default_factory=list, description="Товары в корзине")

    # Суммы
    subtotal: Decimal = Field(default=Decimal("0.00"), description="Подытог")
    discount_amount: Decimal = Field(default=Decimal("0.00"), description="Размер скидки")
    total: Decimal = Field(default=Decimal("0.00"), description="Итого")

    # Метаданные
    created_at: datetime = Field(default_factory=datetime.now, description="Дата создания")
    updated_at: datetime = Field(default_factory=datetime.now, description="Дата обновления")
    expires_at: datetime | None = Field(None, description="Дата истечения")


class Refund(BaseModel):
    """Модель возврата."""

    refund_id: str = Field(..., description="ID возврата")
    order_id: str = Field(..., description="ID заказа")
    payment_id: str = Field(..., description="ID платежа")
    customer_id: str = Field(..., description="ID клиента")

    # Сумма возврата
    amount: Decimal = Field(..., description="Сумма возврата")
    currency: str = Field(default="RUB", description="Валюта")

    # Причина и статус
    reason: str = Field(..., description="Причина возврата")
    status: str = Field(default="pending", description="Статус возврата")

    # Товары для возврата
    items: list[OrderItem] | None = Field(None, description="Товары для возврата")

    # Даты
    created_at: datetime = Field(default_factory=datetime.now, description="Дата создания")
    processed_at: datetime | None = Field(None, description="Дата обработки")

    # Дополнительная информация
    notes: str | None = Field(None, description="Примечания")
    admin_notes: str | None = Field(None, description="Административные примечания")
