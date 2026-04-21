"""XP (Experience Points) Service.

Отвечает за:
- Начисление XP за различные действия
- Подсчёт общего XP и уровня
- Получение статистики за день
"""

from __future__ import annotations

import math
import inspect
from datetime import datetime, timezone, timedelta
from typing import Optional
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text

from app.models.core_tables import User
from app.models.extended_tables import XPEvent


class XPEventKind(str, Enum):
    """Типы XP событий."""
    SESSION_COMPLETE = "session_complete"       # Завершение сессии
    STREAK_BONUS = "streak_bonus"               # Бонус за streak
    VOCABULARY_LEARNED = "vocabulary_learned"   # Изучение нового слова
    PERFECT_PRONUNCIATION = "perfect_pronunciation"  # Идеальное произношение
    FIRST_SESSION = "first_session"             # Первая сессия
    COMEBACK = "comeback"                       # Возвращение после 7+ дней
    DAILY_GOAL = "daily_goal"                   # Выполнение дневной цели


# Базовые значения XP для каждого типа события
XP_VALUES = {
    XPEventKind.SESSION_COMPLETE: 10,
    XPEventKind.STREAK_BONUS: 5,              # Умножается на день streak
    XPEventKind.VOCABULARY_LEARNED: 2,         # За каждое слово
    XPEventKind.PERFECT_PRONUNCIATION: 15,
    XPEventKind.FIRST_SESSION: 50,
    XPEventKind.COMEBACK: 20,
    XPEventKind.DAILY_GOAL: 25,
}


def calculate_level(total_xp: int) -> int:
    """Вычислить уровень по общему XP.

    Формула: level = 1 + sqrt(xp / 50)
    - Level 1: 0 XP
    - Level 2: 50 XP
    - Level 3: 200 XP
    - Level 4: 450 XP
    - Level 5: 800 XP
    """
    if total_xp <= 0:
        return 1
    return int(1 + math.sqrt(total_xp / 50))


def xp_for_level(level: int) -> int:
    """Сколько XP нужно для достижения уровня."""
    if level <= 1:
        return 0
    return 50 * (level - 1) ** 2


def xp_progress_in_level(total_xp: int) -> float:
    """Прогресс внутри текущего уровня (0.0 - 1.0)."""
    current_level = calculate_level(total_xp)
    current_level_xp = xp_for_level(current_level)
    next_level_xp = xp_for_level(current_level + 1)

    if next_level_xp == current_level_xp:
        return 0.0

    progress = (total_xp - current_level_xp) / (next_level_xp - current_level_xp)
    return min(max(progress, 0.0), 1.0)


class XPService:
    """Сервис для управления XP."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _ensure_partition_for_timestamp(self, happened_at: datetime) -> None:
        """Create the required monthly xp_events partition before insert."""
        if not hasattr(self.db, "execute"):
            return
        month_start = happened_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)

        partition_name = f"xp_events_{month_start.strftime('%Y_%m')}"
        user_index_name = f"{partition_name}_user_idx"
        start_date = month_start.date().isoformat()
        end_date = next_month.date().isoformat()

        await self.db.execute(text(
            f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF xp_events
            FOR VALUES FROM ('{start_date}') TO ('{end_date}')
            """
        ))
        await self.db.execute(text(
            f"CREATE INDEX IF NOT EXISTS {user_index_name} ON {partition_name} (user_id, happened_at DESC)"
        ))

    async def award_xp(
        self,
        user_id: int,
        kind: XPEventKind | str,
        session_id: Optional[str] = None,
        multiplier: int = 1,
        custom_points: Optional[int] = None,
    ) -> XPEvent:
        """Начислить XP пользователю.

        Args:
            user_id: ID пользователя
            kind: Тип события
            session_id: ID сессии (опционально)
            multiplier: Множитель (для streak_bonus)
            custom_points: Кастомное количество очков (переопределяет базовое)

        Returns:
            Созданный XPEvent
        """
        # Нормализуем kind к строке
        if isinstance(kind, XPEventKind):
            kind_str = kind.value
            base_points = XP_VALUES.get(kind, 10)
        else:
            kind_str = kind
            # Пробуем найти в enum, иначе дефолт 10
            try:
                base_points = XP_VALUES.get(XPEventKind(kind), 10)
            except ValueError:
                base_points = 10

        # Вычисляем финальные очки
        points = custom_points if custom_points is not None else base_points * multiplier

        # Создаём событие
        # Use naive datetime for TIMESTAMP WITHOUT TIME ZONE column
        happened_at = datetime.utcnow()
        await self._ensure_partition_for_timestamp(happened_at)
        event = XPEvent(
            user_id=user_id,
            session_id=session_id,
            kind=kind_str,
            points=points,
            happened_at=happened_at,
        )

        add_result = self.db.add(event)
        if inspect.isawaitable(add_result):
            await add_result

        # Обновляем total_xp в users (денормализация для быстрых чтений)
        user = await self.db.get(User, user_id)
        if user:
            user.total_xp = (user.total_xp or 0) + points

        try:
            await self.db.commit()
            await self.db.refresh(event)
        except Exception:
            await self.db.rollback()
            raise

        return event

    async def get_total_xp(self, user_id: int) -> int:
        """Получить общий XP пользователя.

        Читает из денормализованного поля users.total_xp.
        """
        user = await self.db.get(User, user_id)
        if user:
            return user.total_xp or 0
        return 0

    async def get_level_info(self, user_id: int) -> dict:
        """Получить информацию об уровне пользователя.

        Returns:
            {
                "level": 5,
                "total_xp": 850,
                "current_level_xp": 800,
                "next_level_xp": 1250,
                "progress": 0.11
            }
        """
        total_xp = await self.get_total_xp(user_id)
        level = calculate_level(total_xp)

        return {
            "level": level,
            "total_xp": total_xp,
            "current_level_xp": xp_for_level(level),
            "next_level_xp": xp_for_level(level + 1),
            "progress": xp_progress_in_level(total_xp),
        }

    async def get_today_xp(self, user_id: int) -> int:
        """Получить XP, заработанный сегодня."""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        result = await self.db.execute(
            select(func.coalesce(func.sum(XPEvent.points), 0))
            .where(
                and_(
                    XPEvent.user_id == user_id,
                    XPEvent.happened_at >= today_start,
                )
            )
        )

        return result.scalar() or 0

    async def get_xp_history(
        self,
        user_id: int,
        days: int = 7,
    ) -> list[dict]:
        """Получить историю XP за последние N дней.

        Returns:
            [{"date": "2026-01-05", "xp": 45}, ...]
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(
                func.date(XPEvent.happened_at).label("date"),
                func.sum(XPEvent.points).label("xp"),
            )
            .where(
                and_(
                    XPEvent.user_id == user_id,
                    XPEvent.happened_at >= start_date,
                )
            )
            .group_by(func.date(XPEvent.happened_at))
            .order_by(func.date(XPEvent.happened_at))
        )

        return [
            {"date": str(row.date), "xp": row.xp}
            for row in result
        ]

    async def check_first_session(self, user_id: int) -> bool:
        """Проверить, была ли это первая сессия пользователя.

        Возвращает True, если XP за first_session ещё не начислялся.
        """
        result = await self.db.execute(
            select(XPEvent.id)
            .where(
                and_(
                    XPEvent.user_id == user_id,
                    XPEvent.kind == XPEventKind.FIRST_SESSION.value,
                )
            )
            .limit(1)
        )

        return result.scalar() is None

    async def recalculate_total_xp(self, user_id: int) -> int:
        """Пересчитать total_xp из xp_events (для исправления рассинхрона).

        Используется редко, только при обнаружении ошибок.
        """
        result = await self.db.execute(
            select(func.coalesce(func.sum(XPEvent.points), 0))
            .where(XPEvent.user_id == user_id)
        )

        total = result.scalar() or 0

        user = await self.db.get(User, user_id)
        if user:
            user.total_xp = total
            await self.db.commit()

        return total
