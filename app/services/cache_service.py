"""Сервис кэширования для AI ответов и сессий."""
import json
import hashlib
from datetime import timedelta
from typing import Any, Optional

import redis.asyncio as redis
import structlog
from pydantic import BaseModel

from app.core.config import settings


logger = structlog.get_logger()


class CacheService:
    """Сервис для кэширования AI ответов и данных сессий."""

    def __init__(self) -> None:
        try:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            self._available = True
            logger.info("Redis кэш инициализирован", url=settings.REDIS_URL)
        except Exception as e:
            self._redis = None
            self._available = False
            logger.warning("Redis недоступен, кэширование отключено", error=str(e))

    async def get_ai_response_cache(
        self,
        message: str,
        intent: str | None,
        entities: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Получить кэшированный ответ AI."""
        if not self._available:
            return None

        try:
            cache_key = self._generate_ai_cache_key(message, intent, entities)
            cached_data = await self._redis.get(cache_key)
            
            if cached_data:
                logger.debug("Найден кэшированный AI ответ", cache_key=cache_key)
                return json.loads(cached_data)
                
        except Exception as e:
            logger.error("Ошибка получения кэша AI ответа", error=str(e))
        
        return None

    async def set_ai_response_cache(
        self,
        message: str,
        intent: str | None,
        entities: dict[str, Any] | None,
        response_data: dict[str, Any],
        ttl_seconds: int = 3600  # 1 час по умолчанию
    ) -> bool:
        """Сохранить ответ AI в кэш."""
        if not self._available:
            return False

        try:
            cache_key = self._generate_ai_cache_key(message, intent, entities)
            await self._redis.setex(
                cache_key,
                ttl_seconds,
                json.dumps(response_data, ensure_ascii=False, default=str)
            )
            logger.debug("AI ответ сохранен в кэш", cache_key=cache_key, ttl=ttl_seconds)
            return True
            
        except Exception as e:
            logger.error("Ошибка сохранения кэша AI ответа", error=str(e))
            return False

    async def get_session_context(self, session_id: str) -> dict[str, Any] | None:
        """Получить контекст сессии из кэша."""
        if not self._available:
            return None

        try:
            cache_key = f"session:{session_id}"
            cached_data = await self._redis.get(cache_key)
            
            if cached_data:
                logger.debug("Найден кэшированный контекст сессии", session_id=session_id)
                return json.loads(cached_data)
                
        except Exception as e:
            logger.error("Ошибка получения контекста сессии", error=str(e), session_id=session_id)
        
        return None

    async def set_session_context(
        self,
        session_id: str,
        context_data: dict[str, Any],
        ttl_seconds: int = 1800  # 30 минут по умолчанию
    ) -> bool:
        """Сохранить контекст сессии в кэш."""
        if not self._available:
            return False

        try:
            cache_key = f"session:{session_id}"
            await self._redis.setex(
                cache_key,
                ttl_seconds,
                json.dumps(context_data, ensure_ascii=False, default=str)
            )
            logger.debug("Контекст сессии сохранен в кэш", session_id=session_id, ttl=ttl_seconds)
            return True
            
        except Exception as e:
            logger.error("Ошибка сохранения контекста сессии", error=str(e), session_id=session_id)
            return False

    async def get_knowledge_base_cache(self, query_hash: str) -> list[dict[str, Any]] | None:
        """Получить результаты поиска по базе знаний из кэша."""
        if not self._available:
            return None

        try:
            cache_key = f"kb:{query_hash}"
            cached_data = await self._redis.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
                
        except Exception as e:
            logger.error("Ошибка получения кэша базы знаний", error=str(e))
        
        return None

    async def set_knowledge_base_cache(
        self,
        query_hash: str,
        results: list[dict[str, Any]],
        ttl_seconds: int = 7200  # 2 часа
    ) -> bool:
        """Сохранить результаты поиска по базе знаний в кэш."""
        if not self._available:
            return False

        try:
            cache_key = f"kb:{query_hash}"
            await self._redis.setex(
                cache_key,
                ttl_seconds,
                json.dumps(results, ensure_ascii=False, default=str)
            )
            return True
            
        except Exception as e:
            logger.error("Ошибка сохранения кэша базы знаний", error=str(e))
            return False

    async def invalidate_user_cache(self, user_id: str) -> int:
        """Очистить весь кэш пользователя."""
        if not self._available:
            return 0

        try:
            pattern = f"session:*{user_id}*"
            keys = await self._redis.keys(pattern)
            
            if keys:
                deleted = await self._redis.delete(*keys)
                logger.info("Кэш пользователя очищен", user_id=user_id, deleted_keys=deleted)
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error("Ошибка очистки кэша пользователя", error=str(e), user_id=user_id)
            return 0

    async def get_cache_stats(self) -> dict[str, Any]:
        """Получить статистику кэша."""
        if not self._available:
            return {"available": False}

        try:
            info = await self._redis.info()
            return {
                "available": True,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "expired_keys": info.get("expired_keys", 0)
            }
            
        except Exception as e:
            logger.error("Ошибка получения статистики кэша", error=str(e))
            return {"available": False, "error": str(e)}

    async def health_check(self) -> bool:
        """Проверка доступности Redis."""
        if not self._available:
            return False

        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    def _generate_ai_cache_key(
        self,
        message: str,
        intent: str | None,
        entities: dict[str, Any] | None
    ) -> str:
        """Генерация ключа кэша для AI ответа."""
        # Создаем хэш на основе сообщения, намерения и сущностей
        content = {
            "message": message.lower().strip(),
            "intent": intent,
            "entities": entities or {}
        }
        content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
        content_hash = hashlib.md5(content_str.encode()).hexdigest()
        
        return f"ai_response:{content_hash}"

    async def close(self) -> None:
        """Закрытие соединения с Redis."""
        if self._redis and self._available:
            await self._redis.close()
            logger.info("Redis соединение закрыто")


# Глобальный экземпляр сервиса кэширования
cache_service = CacheService()