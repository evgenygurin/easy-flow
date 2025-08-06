"""Сервис для работы с векторными представлениями (embeddings)."""
import hashlib
from typing import Any

import numpy as np
import structlog
from sentence_transformers import SentenceTransformer

from app.services.cache_service import cache_service


logger = structlog.get_logger()


class EmbeddingsService:
    """Сервис для создания и поиска по векторным представлениям."""

    def __init__(self) -> None:
        try:
            # Используем многоязычную модель для русского языка
            self.model = SentenceTransformer('intfloat/multilingual-e5-large')
            self._available = True
            logger.info("Модель embeddings загружена", model="intfloat/multilingual-e5-large")
        except Exception as e:
            self.model = None
            self._available = False
            logger.error("Ошибка загрузки модели embeddings", error=str(e))

    async def encode_text(self, text: str) -> np.ndarray | None:
        """Создать embedding для текста."""
        if not self._available:
            return None

        try:
            # Проверяем кэш
            text_hash = hashlib.md5(text.encode()).hexdigest()
            cache_key = f"embedding:{text_hash}"
            
            cached_embedding = await cache_service._redis.get(cache_key) if cache_service._available else None
            if cached_embedding:
                return np.frombuffer(bytes.fromhex(cached_embedding), dtype=np.float32)

            # Префикс для улучшения качества embeddings
            prefixed_text = f"query: {text}"
            
            # Создаем embedding
            embedding = self.model.encode(prefixed_text, normalize_embeddings=True)
            
            # Кэшируем на 24 часа
            if cache_service._available:
                await cache_service._redis.setex(
                    cache_key, 
                    86400, 
                    embedding.tobytes().hex()
                )
            
            return embedding
            
        except Exception as e:
            logger.error("Ошибка создания embedding", error=str(e), text_preview=text[:100])
            return None

    async def encode_knowledge_base(self, knowledge_items: list[dict[str, Any]]) -> dict[str, np.ndarray]:
        """Создать embeddings для элементов базы знаний."""
        if not self._available:
            return {}

        embeddings_dict = {}
        
        try:
            for item in knowledge_items:
                # Комбинируем заголовок, контент и ключевые слова для лучшего поиска
                combined_text = f"{item.get('title', '')} {item.get('content', '')} {' '.join(item.get('keywords', []))}"
                
                embedding = await self.encode_text(combined_text)
                if embedding is not None:
                    embeddings_dict[item['id']] = embedding
                    
            logger.info("Создано embeddings для базы знаний", count=len(embeddings_dict))
            return embeddings_dict
            
        except Exception as e:
            logger.error("Ошибка создания embeddings для базы знаний", error=str(e))
            return {}

    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Вычислить косинусное сходство между embeddings."""
        try:
            # Косинусное сходство для нормализованных векторов
            similarity = np.dot(embedding1, embedding2)
            return float(similarity)
        except Exception as e:
            logger.error("Ошибка вычисления сходства", error=str(e))
            return 0.0

    async def search_similar_knowledge(
        self,
        query_text: str,
        knowledge_embeddings: dict[str, np.ndarray],
        knowledge_items: dict[str, dict[str, Any]],
        threshold: float = 0.6,
        top_k: int = 3
    ) -> list[dict[str, Any]]:
        """Поиск похожих элементов в базе знаний."""
        if not self._available or not knowledge_embeddings:
            return []

        try:
            # Создаем embedding для запроса
            query_embedding = await self.encode_text(query_text)
            if query_embedding is None:
                return []

            # Вычисляем сходство со всеми элементами
            similarities = []
            for item_id, item_embedding in knowledge_embeddings.items():
                similarity = self.calculate_similarity(query_embedding, item_embedding)
                if similarity >= threshold:
                    similarities.append({
                        'id': item_id,
                        'similarity': similarity,
                        'item': knowledge_items.get(item_id, {})
                    })

            # Сортируем по убыванию сходства
            similarities.sort(key=lambda x: x['similarity'], reverse=True)

            # Возвращаем топ-k результатов
            results = []
            for sim in similarities[:top_k]:
                result = sim['item'].copy()
                result['similarity_score'] = sim['similarity']
                results.append(result)

            logger.info(
                "Поиск по embeddings завершен", 
                query_preview=query_text[:50], 
                found_results=len(results),
                top_similarity=similarities[0]['similarity'] if similarities else 0
            )

            return results

        except Exception as e:
            logger.error("Ошибка поиска по embeddings", error=str(e), query=query_text[:100])
            return []

    async def create_knowledge_base_index(
        self, 
        knowledge_base: list[dict[str, Any]]
    ) -> tuple[dict[str, np.ndarray], dict[str, dict[str, Any]]]:
        """Создать индекс базы знаний с embeddings."""
        try:
            # Создаем embeddings
            embeddings_dict = await self.encode_knowledge_base(knowledge_base)
            
            # Создаем словарь элементов по ID
            items_dict = {item['id']: item for item in knowledge_base}
            
            logger.info("Индекс базы знаний создан", items_count=len(items_dict), embeddings_count=len(embeddings_dict))
            
            return embeddings_dict, items_dict
            
        except Exception as e:
            logger.error("Ошибка создания индекса базы знаний", error=str(e))
            return {}, {}

    def get_embedding_stats(self) -> dict[str, Any]:
        """Получить статистику модели embeddings."""
        if not self._available:
            return {"available": False}

        try:
            return {
                "available": True,
                "model_name": "intfloat/multilingual-e5-large",
                "embedding_dimension": self.model.get_sentence_embedding_dimension(),
                "max_seq_length": getattr(self.model, 'max_seq_length', 512)
            }
        except Exception as e:
            logger.error("Ошибка получения статистики embeddings", error=str(e))
            return {"available": False, "error": str(e)}


# Глобальный экземпляр сервиса embeddings
embeddings_service = EmbeddingsService()