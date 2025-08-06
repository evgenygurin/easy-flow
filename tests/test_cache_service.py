"""Тесты для сервиса кэширования."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.cache_service import CacheService


@pytest.fixture
def mock_redis():
    """Мок Redis клиента."""
    mock = AsyncMock()
    mock.get = AsyncMock()
    mock.setex = AsyncMock()
    mock.keys = AsyncMock()
    mock.delete = AsyncMock()
    mock.info = AsyncMock()
    mock.ping = AsyncMock()
    return mock


@pytest.fixture
def cache_service_with_mock_redis(mock_redis):
    """Кэш сервис с моковым Redis."""
    with patch('app.services.cache_service.redis.from_url', return_value=mock_redis):
        service = CacheService()
        return service


class TestCacheService:
    """Тесты для сервиса кэширования."""

    @pytest.mark.asyncio
    async def test_get_ai_response_cache_hit(self, cache_service_with_mock_redis, mock_redis):
        """Тест получения кэшированного AI ответа."""
        cache_data = {
            "response": "Кэшированный ответ",
            "confidence": 0.9
        }
        mock_redis.get.return_value = json.dumps(cache_data, ensure_ascii=False)

        result = await cache_service_with_mock_redis.get_ai_response_cache(
            "тестовое сообщение", "test_intent", {"entity": "value"}
        )

        assert result == cache_data
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_ai_response_cache_miss(self, cache_service_with_mock_redis, mock_redis):
        """Тест промаха кэша AI ответа."""
        mock_redis.get.return_value = None

        result = await cache_service_with_mock_redis.get_ai_response_cache(
            "тестовое сообщение", "test_intent", {"entity": "value"}
        )

        assert result is None
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_ai_response_cache(self, cache_service_with_mock_redis, mock_redis):
        """Тест сохранения AI ответа в кэш."""
        response_data = {
            "response": "Тестовый ответ",
            "confidence": 0.8
        }
        mock_redis.setex.return_value = True

        result = await cache_service_with_mock_redis.set_ai_response_cache(
            "тестовое сообщение",
            "test_intent",
            {"entity": "value"},
            response_data,
            ttl_seconds=3600
        )

        assert result is True
        mock_redis.setex.assert_called_once()

        # Проверяем аргументы вызова
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600  # TTL

        # Проверяем что данные сериализованы в JSON
        cached_json = call_args[0][2]
        parsed_data = json.loads(cached_json)
        assert parsed_data == response_data

    @pytest.mark.asyncio
    async def test_get_session_context_hit(self, cache_service_with_mock_redis, mock_redis):
        """Тест получения контекста сессии из кэша."""
        session_data = {
            "user_id": "user1",
            "last_activity": "2024-01-01T10:00:00"
        }
        mock_redis.get.return_value = json.dumps(session_data, default=str)

        result = await cache_service_with_mock_redis.get_session_context("session123")

        assert result == session_data
        mock_redis.get.assert_called_with("session:session123")

    @pytest.mark.asyncio
    async def test_set_session_context(self, cache_service_with_mock_redis, mock_redis):
        """Тест сохранения контекста сессии."""
        session_data = {
            "user_id": "user1",
            "platform": "web"
        }
        mock_redis.setex.return_value = True

        result = await cache_service_with_mock_redis.set_session_context(
            "session123", session_data, ttl_seconds=1800
        )

        assert result is True
        mock_redis.setex.assert_called_with(
            "session:session123",
            1800,
            json.dumps(session_data, ensure_ascii=False, default=str)
        )

    @pytest.mark.asyncio
    async def test_invalidate_user_cache(self, cache_service_with_mock_redis, mock_redis):
        """Тест очистки кэша пользователя."""
        mock_redis.keys.return_value = ["session:user1_session1", "session:user1_session2"]
        mock_redis.delete.return_value = 2

        result = await cache_service_with_mock_redis.invalidate_user_cache("user1")

        assert result == 2
        mock_redis.keys.assert_called_with("session:*user1*")
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_stats_available(self, cache_service_with_mock_redis, mock_redis):
        """Тест получения статистики кэша при доступном Redis."""
        mock_redis.info.return_value = {
            "connected_clients": 5,
            "used_memory_human": "1.2M",
            "keyspace_hits": 100,
            "keyspace_misses": 10,
            "expired_keys": 5
        }

        stats = await cache_service_with_mock_redis.get_cache_stats()

        assert stats["available"] is True
        assert stats["connected_clients"] == 5
        assert stats["used_memory"] == "1.2M"
        assert stats["keyspace_hits"] == 100

    @pytest.mark.asyncio
    async def test_health_check_success(self, cache_service_with_mock_redis, mock_redis):
        """Тест успешной проверки здоровья Redis."""
        mock_redis.ping.return_value = True

        result = await cache_service_with_mock_redis.health_check()

        assert result is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, cache_service_with_mock_redis, mock_redis):
        """Тест неудачной проверки здоровья Redis."""
        mock_redis.ping.side_effect = Exception("Connection failed")

        result = await cache_service_with_mock_redis.health_check()

        assert result is False

    def test_generate_ai_cache_key_consistency(self, cache_service_with_mock_redis):
        """Тест консистентности генерации ключей кэша."""
        # Одинаковые данные должны давать одинаковый ключ
        key1 = cache_service_with_mock_redis._generate_ai_cache_key(
            "тестовое сообщение", "intent1", {"key": "value"}
        )
        key2 = cache_service_with_mock_redis._generate_ai_cache_key(
            "тестовое сообщение", "intent1", {"key": "value"}
        )

        assert key1 == key2
        assert key1.startswith("ai_response:")

    def test_generate_ai_cache_key_different_inputs(self, cache_service_with_mock_redis):
        """Тест различных ключей для разных входных данных."""
        key1 = cache_service_with_mock_redis._generate_ai_cache_key(
            "сообщение 1", "intent1", {"key": "value1"}
        )
        key2 = cache_service_with_mock_redis._generate_ai_cache_key(
            "сообщение 2", "intent1", {"key": "value1"}
        )
        key3 = cache_service_with_mock_redis._generate_ai_cache_key(
            "сообщение 1", "intent2", {"key": "value1"}
        )

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    @pytest.mark.asyncio
    async def test_cache_service_unavailable(self):
        """Тест поведения при недоступном Redis."""
        with patch('app.services.cache_service.redis.from_url', side_effect=Exception("Connection failed")):
            service = CacheService()

            # Все операции должны возвращать None/False при недоступном Redis
            result = await service.get_ai_response_cache("message", "intent", {})
            assert result is None

            result = await service.set_ai_response_cache("message", "intent", {}, {})
            assert result is False

            result = await service.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_error_handling_in_operations(self, cache_service_with_mock_redis, mock_redis):
        """Тест обработки ошибок в операциях кэширования."""
        mock_redis.get.side_effect = Exception("Redis error")
        mock_redis.setex.side_effect = Exception("Redis error")

        # Операции не должны падать при ошибках Redis
        result = await cache_service_with_mock_redis.get_ai_response_cache("message", "intent", {})
        assert result is None

        result = await cache_service_with_mock_redis.set_ai_response_cache("message", "intent", {}, {})
        assert result is False

    @pytest.mark.asyncio
    async def test_knowledge_base_cache_operations(self, cache_service_with_mock_redis, mock_redis):
        """Тест операций с кэшем базы знаний."""
        kb_results = [{"id": "1", "content": "test content"}]
        mock_redis.setex.return_value = True
        mock_redis.get.return_value = json.dumps(kb_results)

        # Тест сохранения
        result = await cache_service_with_mock_redis.set_knowledge_base_cache("hash123", kb_results)
        assert result is True

        # Тест получения
        result = await cache_service_with_mock_redis.get_knowledge_base_cache("hash123")
        assert result == kb_results

    @pytest.mark.asyncio
    async def test_close_connection(self, cache_service_with_mock_redis, mock_redis):
        """Тест закрытия соединения с Redis."""
        await cache_service_with_mock_redis.close()
        mock_redis.close.assert_called_once()
