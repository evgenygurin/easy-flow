"""Сервис для сбора и отображения метрик производительности."""
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any

import structlog
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app.services.cache_service import cache_service


logger = structlog.get_logger()


# Prometheus метрики
ai_requests_total = Counter('ai_requests_total', 'Общее количество запросов к AI', ['intent', 'response_type'])
ai_response_time_seconds = Histogram('ai_response_time_seconds', 'Время ответа AI в секундах', ['response_type'])
ai_confidence_score = Histogram('ai_confidence_score', 'Оценка уверенности AI', ['intent', 'response_type'])
cache_hits_total = Counter('cache_hits_total', 'Количество попаданий в кэш', ['cache_type'])
cache_misses_total = Counter('cache_misses_total', 'Количество промахов кэша', ['cache_type'])
active_conversations = Gauge('active_conversations', 'Количество активных диалогов')
nlp_processing_time_seconds = Histogram('nlp_processing_time_seconds', 'Время обработки NLP в секундах')
embeddings_search_time_seconds = Histogram('embeddings_search_time_seconds', 'Время поиска по embeddings в секундах')


class MetricsService:
    """Сервис для сбора метрик производительности."""

    def __init__(self) -> None:
        self._session_metrics: dict[str, dict[str, Any]] = {}
        self._daily_metrics: dict[str, dict[str, Any]] = defaultdict(lambda: {
            'requests': 0,
            'successful_responses': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_response_time': 0.0,
            'escalations': 0,
            'average_confidence': 0.0,
            'confidence_samples': []
        })

    @asynccontextmanager
    async def measure_ai_response_time(self, response_type: str):
        """Контекстный менеджер для измерения времени AI ответа."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            ai_response_time_seconds.labels(response_type=response_type).observe(duration)

            # Обновляем дневные метрики
            today = datetime.now().strftime('%Y-%m-%d')
            self._daily_metrics[today]['total_response_time'] += duration

    @asynccontextmanager
    async def measure_nlp_processing_time(self):
        """Контекстный менеджер для измерения времени NLP обработки."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            nlp_processing_time_seconds.observe(duration)

    @asynccontextmanager
    async def measure_embeddings_search_time(self):
        """Контекстный менеджер для измерения времени поиска по embeddings."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            embeddings_search_time_seconds.observe(duration)

    async def record_ai_request(
        self,
        intent: str | None,
        response_type: str,
        confidence: float,
        cache_hit: bool,
        session_id: str | None = None
    ) -> None:
        """Записать метрики AI запроса."""
        # Prometheus метрики
        ai_requests_total.labels(
            intent=intent or 'unknown',
            response_type=response_type
        ).inc()

        ai_confidence_score.labels(
            intent=intent or 'unknown',
            response_type=response_type
        ).observe(confidence)

        if cache_hit:
            cache_hits_total.labels(cache_type='ai_response').inc()
        else:
            cache_misses_total.labels(cache_type='ai_response').inc()

        # Дневные метрики
        today = datetime.now().strftime('%Y-%m-%d')
        daily_stats = self._daily_metrics[today]
        daily_stats['requests'] += 1
        daily_stats['successful_responses'] += 1
        daily_stats['confidence_samples'].append(confidence)

        if cache_hit:
            daily_stats['cache_hits'] += 1
        else:
            daily_stats['cache_misses'] += 1

        # Пересчитываем средную уверенность
        if daily_stats['confidence_samples']:
            daily_stats['average_confidence'] = sum(daily_stats['confidence_samples']) / len(daily_stats['confidence_samples'])

        # Сессионные метрики
        if session_id:
            if session_id not in self._session_metrics:
                self._session_metrics[session_id] = {
                    'start_time': datetime.now(),
                    'requests': 0,
                    'cache_hits': 0,
                    'total_confidence': 0.0,
                    'response_types': defaultdict(int)
                }

            session_stats = self._session_metrics[session_id]
            session_stats['requests'] += 1
            session_stats['total_confidence'] += confidence
            session_stats['response_types'][response_type] += 1

            if cache_hit:
                session_stats['cache_hits'] += 1

    async def record_escalation(self, reason: str, session_id: str | None = None) -> None:
        """Записать метрику эскалации."""
        today = datetime.now().strftime('%Y-%m-%d')
        self._daily_metrics[today]['escalations'] += 1

        if session_id and session_id in self._session_metrics:
            self._session_metrics[session_id]['escalated'] = True
            self._session_metrics[session_id]['escalation_reason'] = reason

    async def update_active_conversations(self, count: int) -> None:
        """Обновить счетчик активных диалогов."""
        active_conversations.set(count)

    async def get_session_metrics(self, session_id: str) -> dict[str, Any]:
        """Получить метрики сессии."""
        if session_id not in self._session_metrics:
            return {}

        session_stats = self._session_metrics[session_id]
        duration = (datetime.now() - session_stats['start_time']).total_seconds()

        return {
            'session_id': session_id,
            'duration_seconds': duration,
            'total_requests': session_stats['requests'],
            'cache_hit_rate': session_stats['cache_hits'] / max(session_stats['requests'], 1),
            'average_confidence': session_stats['total_confidence'] / max(session_stats['requests'], 1),
            'response_types': dict(session_stats['response_types']),
            'escalated': session_stats.get('escalated', False),
            'escalation_reason': session_stats.get('escalation_reason')
        }

    async def get_daily_metrics(self, days: int = 7) -> list[dict[str, Any]]:
        """Получить дневные метрики за последние N дней."""
        metrics = []

        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            daily_stats = self._daily_metrics[date]

            cache_hit_rate = 0.0
            if daily_stats['requests'] > 0:
                cache_hit_rate = daily_stats['cache_hits'] / daily_stats['requests']

            average_response_time = 0.0
            if daily_stats['successful_responses'] > 0:
                average_response_time = daily_stats['total_response_time'] / daily_stats['successful_responses']

            metrics.append({
                'date': date,
                'total_requests': daily_stats['requests'],
                'successful_responses': daily_stats['successful_responses'],
                'cache_hit_rate': cache_hit_rate,
                'average_response_time_seconds': average_response_time,
                'escalations': daily_stats['escalations'],
                'average_confidence': daily_stats['average_confidence']
            })

        return metrics

    async def get_performance_summary(self) -> dict[str, Any]:
        """Получить сводку производительности."""
        today = datetime.now().strftime('%Y-%m-%d')
        today_stats = self._daily_metrics[today]

        # Кэш статистика
        cache_stats = await cache_service.get_cache_stats()

        return {
            'today': {
                'total_requests': today_stats['requests'],
                'successful_responses': today_stats['successful_responses'],
                'escalations': today_stats['escalations'],
                'cache_hit_rate': today_stats['cache_hits'] / max(today_stats['requests'], 1),
                'average_confidence': today_stats['average_confidence'],
                'average_response_time': today_stats['total_response_time'] / max(today_stats['successful_responses'], 1)
            },
            'active_sessions': len(self._session_metrics),
            'cache_stats': cache_stats,
            'system_health': {
                'ai_service': True,  # TODO: добавить проверки здоровья
                'cache_service': cache_stats.get('available', False),
                'database_service': True  # TODO: добавить проверку БД
            }
        }

    async def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Очистка старых сессионных метрик."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        removed_count = 0

        sessions_to_remove = []
        for session_id, session_data in self._session_metrics.items():
            if session_data['start_time'] < cutoff_time:
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            del self._session_metrics[session_id]
            removed_count += 1

        if removed_count > 0:
            logger.info("Очищены старые сессионные метрики", removed_count=removed_count)

        return removed_count

    async def get_prometheus_metrics(self) -> str:
        """Получить метрики в формате Prometheus."""
        return generate_latest()

    def get_content_type(self) -> str:
        """Получить content-type для метрик Prometheus."""
        return CONTENT_TYPE_LATEST


# Глобальный экземпляр сервиса метрик
metrics_service = MetricsService()
