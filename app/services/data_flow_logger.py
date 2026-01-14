"""Data Flow Logger - централизованное логирование записи данных.

Логирует все записи в хранилища:
- PostgreSQL: sessions, utterances, memories, learning_plan, vocabulary_cards, xp_events
- Qdrant: vectors
- Neo4j: nodes/relationships

Использование:
    from app.services.data_flow_logger import data_logger

    data_logger.log_postgres_write("xp_events", {"user_id": 1, "points": 10})
    data_logger.log_qdrant_write("memories", {"text": "user likes ML"})
"""

import logging
from datetime import datetime
from typing import Any, Optional
from functools import wraps

from app.services.logger_helpers import format_user_info, format_data_preview

# Создаём специальный логгер для data flow
logger = logging.getLogger("data_flow")
logger.setLevel(logging.INFO)

# Форматтер с выделением
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "\033[36m[DATA-FLOW]\033[0m %(asctime)s | %(message)s",
    datefmt="%H:%M:%S"
))
logger.addHandler(handler)


class DataFlowLogger:
    """Централизованный логгер для отслеживания data flow."""

    def __init__(self):
        self.stats = {
            "postgres_writes": 0,
            "postgres_reads": 0,
            "qdrant_writes": 0,
            "qdrant_reads": 0,
            "neo4j_writes": 0,
            "neo4j_reads": 0,
        }

    def log_postgres_write(
        self,
        table: str,
        data: dict,
        operation: str = "INSERT",
        user_id: Optional[int] = None,
    ):
        """Логировать запись в PostgreSQL."""
        self.stats["postgres_writes"] += 1

        # Форматируем данные для читаемости
        data_preview = format_data_preview(data)

        user_info = format_user_info(user_id)
        logger.info(
            f"📝 POSTGRES {operation}{user_info} → {table}: {data_preview}"
        )

    def log_postgres_read(
        self,
        table: str,
        query_info: str,
        result_count: int = 0,
        user_id: Optional[int] = None,
    ):
        """Логировать чтение из PostgreSQL."""
        self.stats["postgres_reads"] += 1

        user_info = format_user_info(user_id)
        logger.info(
            f"📖 POSTGRES READ{user_info} ← {table}: {query_info} ({result_count} rows)"
        )

    def log_qdrant_write(
        self,
        collection: str,
        data: dict,
        vector_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """Логировать запись в Qdrant."""
        self.stats["qdrant_writes"] += 1

        data_preview = format_data_preview(data)
        user_info = format_user_info(user_id)
        vector_info = f" id={vector_id}" if vector_id else ""

        logger.info(
            f"🧠 QDRANT WRITE{user_info}{vector_info} → {collection}: {data_preview}"
        )

    def log_qdrant_search(
        self,
        collection: str,
        query_preview: str,
        result_count: int = 0,
        user_id: Optional[int] = None,
    ):
        """Логировать поиск в Qdrant."""
        self.stats["qdrant_reads"] += 1

        user_info = format_user_info(user_id)
        logger.info(
            f"🔍 QDRANT SEARCH{user_info} ← {collection}: '{query_preview[:50]}...' ({result_count} results)"
        )

    def log_neo4j_write(
        self,
        operation: str,
        node_type: str,
        data: dict,
        user_id: Optional[int] = None,
    ):
        """Логировать запись в Neo4j."""
        self.stats["neo4j_writes"] += 1

        data_preview = format_data_preview(data)
        user_info = format_user_info(user_id)

        logger.info(
            f"🕸️  NEO4J {operation}{user_info} → {node_type}: {data_preview}"
        )

    def log_learning_plan_update(
        self,
        user_id: int,
        field: str,
        old_value: Any,
        new_value: Any,
    ):
        """Логировать обновление плана обучения."""
        logger.info(
            f"📚 LEARNING_PLAN [user={user_id}] {field}: {old_value} → {new_value}"
        )

    def log_goal_detected(
        self,
        user_id: int,
        message: str,
        detected_goal: str,
    ):
        """Логировать определение цели."""
        logger.info(
            f"🎯 GOAL DETECTED [user={user_id}] from '{message[:50]}...' → {detected_goal}"
        )

    def log_vocabulary_card_created(
        self,
        user_id: int,
        word: str,
        source: str = "session",
    ):
        """Логировать создание карточки."""
        logger.info(
            f"🃏 VOCAB CARD [user={user_id}] created: '{word}' (source: {source})"
        )

    def log_fsrs_review(
        self,
        user_id: int,
        word: str,
        rating: str,
        next_review: str,
    ):
        """Логировать FSRS повторение."""
        logger.info(
            f"🔄 FSRS REVIEW [user={user_id}] '{word}' rated={rating} → next: {next_review}"
        )

    def log_session_summary(
        self,
        user_id: int,
        session_id: str,
        duration_minutes: int,
        new_words: int,
        xp_earned: int,
    ):
        """Логировать итоги сессии."""
        logger.info(
            f"📊 SESSION END [user={user_id}] session={session_id[:8]}... "
            f"duration={duration_minutes}min, new_words={new_words}, xp={xp_earned}"
        )

    def get_stats(self) -> dict:
        """Получить статистику операций."""
        return self.stats.copy()


# Глобальный экземпляр
data_logger = DataFlowLogger()


def log_db_operation(table: str, operation: str = "INSERT"):
    """Декоратор для логирования операций с БД.

    Использование:
        @log_db_operation("xp_events", "INSERT")
        async def award_xp(self, user_id: int, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # Пытаемся извлечь user_id из аргументов
            user_id = kwargs.get("user_id") or (args[1] if len(args) > 1 else None)

            data_logger.log_postgres_write(
                table=table,
                operation=operation,
                data={"result": str(result)[:100] if result else "None"},
                user_id=user_id,
            )

            return result
        return wrapper
    return decorator
