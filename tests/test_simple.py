"""
Простой тест для проверки работы pytest.
"""
import pytest


def test_simple():
    """Простой тест."""
    assert True


@pytest.mark.asyncio
async def test_async_simple():
    """Простой асинхронный тест."""
    assert True
