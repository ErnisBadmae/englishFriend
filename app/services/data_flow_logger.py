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
            "personaplex_connections": 0,
            "personaplex_turns": 0,
        }

    @staticmethod
    def _safe_text(value: Any, limit: int = 120) -> str:
        text = str(value)
        if len(text) > limit:
            text = f"{text[:limit]}..."
        return text.encode("ascii", errors="backslashreplace").decode("ascii")

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
            f"POSTGRES WRITE {self._safe_text(operation)}{self._safe_text(user_info)} "
            f"-> {self._safe_text(table)}: {self._safe_text(data_preview)}"
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
            f"POSTGRES READ{self._safe_text(user_info)} <- {self._safe_text(table)}: "
            f"{self._safe_text(query_info)} ({result_count} rows)"
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
            f"QDRANT WRITE{self._safe_text(user_info)}{self._safe_text(vector_info)} "
            f"-> {self._safe_text(collection)}: {self._safe_text(data_preview)}"
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
            f"QDRANT SEARCH{self._safe_text(user_info)} <- {self._safe_text(collection)}: "
            f"'{self._safe_text(query_preview, 50)}' ({result_count} results)"
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
            f"NEO4J {self._safe_text(operation)}{self._safe_text(user_info)} "
            f"-> {self._safe_text(node_type)}: {self._safe_text(data_preview)}"
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
            f"LEARNING_PLAN [user={user_id}] {self._safe_text(field)}: "
            f"{self._safe_text(old_value)} -> {self._safe_text(new_value)}"
        )

    def log_goal_detected(
        self,
        user_id: int,
        message: str,
        detected_goal: str,
    ):
        """Логировать определение цели."""
        logger.info(
            f"GOAL DETECTED [user={user_id}] from '{self._safe_text(message, 50)}' "
            f"-> {self._safe_text(detected_goal)}"
        )

    def log_vocabulary_card_created(
        self,
        user_id: int,
        word: str,
        source: str = "session",
    ):
        """Логировать создание карточки."""
        logger.info(
            f"VOCAB CARD [user={user_id}] created: '{self._safe_text(word)}' "
            f"(source: {self._safe_text(source)})"
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
            f"FSRS REVIEW [user={user_id}] '{self._safe_text(word)}' "
            f"rated={self._safe_text(rating)} -> next: {self._safe_text(next_review)}"
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
            f"SESSION END [user={user_id}] session={self._safe_text(session_id[:8])}... "
            f"duration={duration_minutes}min, new_words={new_words}, xp={xp_earned}"
        )

    # === PersonaPlex Events ===

    def log_personaplex_connect(
        self,
        user_id: int,
        session_id: str,
        voice: str,
        mode: str,
    ):
        """Log PersonaPlex session start."""
        self.stats["personaplex_connections"] += 1
        logger.info(
            f"PERSONAPLEX CONNECT [user={user_id}] "
            f"session={self._safe_text(session_id[:8])}... voice={self._safe_text(voice)} "
            f"mode={self._safe_text(mode)}"
        )

    def log_personaplex_turn(
        self,
        session_id: str,
        role: str,
        text_preview: str,
        latency_ms: int,
    ):
        """Log each PersonaPlex conversation turn."""
        self.stats["personaplex_turns"] += 1
        preview = text_preview[:50] + "..." if len(text_preview) > 50 else text_preview
        logger.info(
            f"PERSONAPLEX TURN session={self._safe_text(session_id[:8])}... "
            f"role={self._safe_text(role)} latency={latency_ms}ms "
            f"text={self._safe_text(preview)}"
        )

    def log_personaplex_disconnect(
        self,
        session_id: str,
        turns: int,
        duration_seconds: float,
    ):
        """Log PersonaPlex session end."""
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        logger.info(
            f"PERSONAPLEX DISCONNECT session={self._safe_text(session_id[:8])}... "
            f"turns={turns} duration={minutes}m{seconds}s"
        )

    def log_personaplex_fallback(
        self,
        user_id: int,
        reason: str,
    ):
        """Log fallback from PersonaPlex to legacy stack."""
        logger.warning(
            f"PERSONAPLEX FALLBACK [user={user_id}] reason={self._safe_text(reason)}"
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
