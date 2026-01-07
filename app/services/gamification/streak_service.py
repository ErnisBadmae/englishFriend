"""Streak Service.

Отвечает за:
- Отслеживание ежедневных серий (streaks)
- Check-in при активности
- Проверку риска потери streak
"""

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core_tables import User


class StreakService:
    """Сервис для управления streaks."""

    # Через сколько дней неактивности считать comeback
    COMEBACK_THRESHOLD_DAYS = 7

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_in(self, user_id: int) -> dict:
        """Зарегистрировать активность пользователя.

        Вызывать при завершении сессии или другой значимой активности.

        Логика:
        1. Если last_activity_date == сегодня → ничего не делаем
        2. Если last_activity_date == вчера → streak += 1
        3. Если last_activity_date < вчера → streak = 1 (сброс)
        4. Обновляем max_streak если current > max

        Args:
            user_id: ID пользователя

        Returns:
            {
                "streak": 7,
                "max_streak": 14,
                "is_new_record": False,
                "streak_extended": True,
                "is_comeback": False,
                "days_inactive": 0
            }
        """
        user = await self.db.get(User, user_id)
        if not user:
            return {
                "streak": 0,
                "max_streak": 0,
                "is_new_record": False,
                "streak_extended": False,
                "is_comeback": False,
                "days_inactive": 0,
            }

        today = date.today()
        last_activity = user.last_activity_date
        current_streak = user.current_streak or 0
        max_streak = user.max_streak or 0

        result = {
            "streak": current_streak,
            "max_streak": max_streak,
            "is_new_record": False,
            "streak_extended": False,
            "is_comeback": False,
            "days_inactive": 0,
        }

        # Если уже заходил сегодня — ничего не меняем
        if last_activity == today:
            return result

        # Вычисляем дни неактивности
        if last_activity:
            days_inactive = (today - last_activity).days
        else:
            days_inactive = 0  # Первая активность

        result["days_inactive"] = days_inactive

        # Определяем новый streak
        if last_activity is None:
            # Первая активность
            new_streak = 1
            result["streak_extended"] = True
        elif days_inactive == 1:
            # Продолжение streak (вчера была активность)
            new_streak = current_streak + 1
            result["streak_extended"] = True
        elif days_inactive >= self.COMEBACK_THRESHOLD_DAYS:
            # Comeback после долгого перерыва
            new_streak = 1
            result["is_comeback"] = True
        else:
            # Пропуск дня — сброс streak
            new_streak = 1

        # Обновляем max_streak если побили рекорд
        new_max = max(max_streak, new_streak)
        if new_streak > max_streak:
            result["is_new_record"] = True

        # Сохраняем изменения
        user.current_streak = new_streak
        user.max_streak = new_max
        user.last_activity_date = today

        await self.db.commit()

        result["streak"] = new_streak
        result["max_streak"] = new_max

        return result

    async def get_streak_info(self, user_id: int) -> dict:
        """Получить информацию о streak пользователя.

        Returns:
            {
                "current": 7,
                "max": 14,
                "at_risk": False,
                "last_activity": "2026-01-05"
            }
        """
        user = await self.db.get(User, user_id)
        if not user:
            return {
                "current": 0,
                "max": 0,
                "at_risk": True,
                "last_activity": None,
            }

        today = date.today()
        last_activity = user.last_activity_date

        # Streak at risk если сегодня ещё не было активности
        # и последняя активность была вчера или раньше
        at_risk = last_activity != today if last_activity else True

        return {
            "current": user.current_streak or 0,
            "max": user.max_streak or 0,
            "at_risk": at_risk,
            "last_activity": str(last_activity) if last_activity else None,
        }

    async def is_streak_at_risk(self, user_id: int) -> bool:
        """Проверить, под угрозой ли streak.

        Возвращает True если:
        - Сегодня ещё не было активности
        - У пользователя есть активный streak (> 1)
        """
        user = await self.db.get(User, user_id)
        if not user:
            return False

        today = date.today()
        last_activity = user.last_activity_date
        current_streak = user.current_streak or 0

        # Нет streak — нечего терять
        if current_streak <= 1:
            return False

        # Был активен сегодня — streak в безопасности
        if last_activity == today:
            return False

        # Есть streak и не был активен сегодня — под угрозой
        return True

    async def get_streak_bonus_multiplier(self, user_id: int) -> int:
        """Получить множитель бонуса за streak.

        Множитель = текущий streak день.
        Например, streak 7 = бонус 7x.
        """
        info = await self.get_streak_info(user_id)
        return max(1, info["current"])

    async def should_award_comeback_bonus(self, user_id: int) -> bool:
        """Проверить, нужно ли начислить бонус за comeback.

        Comeback = возвращение после 7+ дней неактивности.
        """
        user = await self.db.get(User, user_id)
        if not user or not user.last_activity_date:
            return False

        today = date.today()
        days_inactive = (today - user.last_activity_date).days

        return days_inactive >= self.COMEBACK_THRESHOLD_DAYS

    async def reset_streak(self, user_id: int) -> None:
        """Принудительно сбросить streak (для тестов).

        Не сбрасывает max_streak!
        """
        user = await self.db.get(User, user_id)
        if user:
            user.current_streak = 0
            user.last_activity_date = None
            await self.db.commit()
