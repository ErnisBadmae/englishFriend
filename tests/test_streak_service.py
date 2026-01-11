"""Unit тесты для StreakService.

Тестирует:
- Check-in логику (продление/сброс streak)
- Получение информации о streak
- Проверку риска потери streak
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import date, timedelta

from app.services.gamification.streak_service import StreakService


# ============== Check-in Tests ==============

class TestStreakCheckIn:
    """Тесты check-in логики."""

    @pytest.fixture
    def mock_db(self):
        """Мок async session."""
        return AsyncMock()

    @pytest.fixture
    def mock_user_new(self):
        """Новый пользователь без активности."""
        user = MagicMock()
        user.current_streak = 0
        user.max_streak = 0
        user.last_activity_date = None
        return user

    @pytest.fixture
    def mock_user_active_yesterday(self):
        """Пользователь с активностью вчера."""
        user = MagicMock()
        user.current_streak = 5
        user.max_streak = 10
        user.last_activity_date = date.today() - timedelta(days=1)
        return user

    @pytest.fixture
    def mock_user_active_today(self):
        """Пользователь с активностью сегодня."""
        user = MagicMock()
        user.current_streak = 5
        user.max_streak = 10
        user.last_activity_date = date.today()
        return user

    @pytest.fixture
    def mock_user_inactive_week(self):
        """Пользователь без активности неделю."""
        user = MagicMock()
        user.current_streak = 5
        user.max_streak = 10
        user.last_activity_date = date.today() - timedelta(days=8)
        return user

    @pytest.mark.asyncio
    async def test_first_check_in_starts_streak(self, mock_db, mock_user_new):
        """Первый check-in начинает streak с 1."""
        mock_db.get.return_value = mock_user_new

        service = StreakService(mock_db)
        result = await service.check_in(user_id=1)

        assert result["streak"] == 1
        assert result["streak_extended"] is True
        assert mock_user_new.current_streak == 1

    @pytest.mark.asyncio
    async def test_consecutive_day_extends_streak(self, mock_db, mock_user_active_yesterday):
        """Активность вчера → продление streak."""
        mock_db.get.return_value = mock_user_active_yesterday

        service = StreakService(mock_db)
        result = await service.check_in(user_id=1)

        assert result["streak"] == 6  # Was 5, now 6
        assert result["streak_extended"] is True
        assert mock_user_active_yesterday.current_streak == 6

    @pytest.mark.asyncio
    async def test_same_day_no_change(self, mock_db, mock_user_active_today):
        """Повторный check-in сегодня не меняет streak."""
        mock_db.get.return_value = mock_user_active_today

        service = StreakService(mock_db)
        result = await service.check_in(user_id=1)

        assert result["streak"] == 5  # Unchanged
        assert result["streak_extended"] is False
        # current_streak should not change
        assert mock_user_active_today.current_streak == 5

    @pytest.mark.asyncio
    async def test_missed_day_resets_streak(self, mock_db):
        """Пропуск дня сбрасывает streak."""
        user = MagicMock()
        user.current_streak = 5
        user.max_streak = 10
        user.last_activity_date = date.today() - timedelta(days=2)  # Missed yesterday
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        result = await service.check_in(user_id=1)

        assert result["streak"] == 1  # Reset
        assert user.current_streak == 1

    @pytest.mark.asyncio
    async def test_comeback_after_week(self, mock_db, mock_user_inactive_week):
        """Возвращение после 7+ дней = comeback."""
        mock_db.get.return_value = mock_user_inactive_week

        service = StreakService(mock_db)
        result = await service.check_in(user_id=1)

        assert result["streak"] == 1  # Reset
        assert result["is_comeback"] is True
        assert result["days_inactive"] >= 7

    @pytest.mark.asyncio
    async def test_new_record_flag(self, mock_db):
        """Флаг is_new_record при побитии рекорда."""
        user = MagicMock()
        user.current_streak = 9  # Will become 10
        user.max_streak = 9      # Current record
        user.last_activity_date = date.today() - timedelta(days=1)
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        result = await service.check_in(user_id=1)

        assert result["streak"] == 10
        assert result["is_new_record"] is True
        assert user.max_streak == 10

    @pytest.mark.asyncio
    async def test_max_streak_not_decreased(self, mock_db):
        """max_streak не уменьшается при сбросе streak."""
        user = MagicMock()
        user.current_streak = 5
        user.max_streak = 20
        user.last_activity_date = date.today() - timedelta(days=2)  # Missed day
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        result = await service.check_in(user_id=1)

        assert result["streak"] == 1  # Reset
        assert result["max_streak"] == 20  # Unchanged
        assert user.max_streak == 20

    @pytest.mark.asyncio
    async def test_missing_user_returns_zeros(self, mock_db):
        """Несуществующий пользователь возвращает нули."""
        mock_db.get.return_value = None

        service = StreakService(mock_db)
        result = await service.check_in(user_id=999)

        assert result["streak"] == 0
        assert result["max_streak"] == 0


# ============== Get Streak Info Tests ==============

class TestGetStreakInfo:
    """Тесты получения информации о streak."""

    @pytest.fixture
    def mock_db(self):
        """Мок async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_streak_info_active_today(self, mock_db):
        """Streak info для активного сегодня пользователя."""
        user = MagicMock()
        user.current_streak = 7
        user.max_streak = 14
        user.last_activity_date = date.today()
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        info = await service.get_streak_info(user_id=1)

        assert info["current"] == 7
        assert info["max"] == 14
        assert info["at_risk"] is False  # Active today

    @pytest.mark.asyncio
    async def test_get_streak_info_not_active_today(self, mock_db):
        """Streak info для не активного сегодня пользователя."""
        user = MagicMock()
        user.current_streak = 7
        user.max_streak = 14
        user.last_activity_date = date.today() - timedelta(days=1)
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        info = await service.get_streak_info(user_id=1)

        assert info["current"] == 7
        assert info["at_risk"] is True  # Not active today

    @pytest.mark.asyncio
    async def test_get_streak_info_missing_user(self, mock_db):
        """Streak info для несуществующего пользователя."""
        mock_db.get.return_value = None

        service = StreakService(mock_db)
        info = await service.get_streak_info(user_id=999)

        assert info["current"] == 0
        assert info["max"] == 0
        assert info["at_risk"] is True


# ============== Is Streak At Risk Tests ==============

class TestIsStreakAtRisk:
    """Тесты проверки риска потери streak."""

    @pytest.fixture
    def mock_db(self):
        """Мок async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_no_risk_if_active_today(self, mock_db):
        """Нет риска если был активен сегодня."""
        user = MagicMock()
        user.current_streak = 7
        user.last_activity_date = date.today()
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        at_risk = await service.is_streak_at_risk(user_id=1)

        assert at_risk is False

    @pytest.mark.asyncio
    async def test_at_risk_if_not_active_today(self, mock_db):
        """Риск если не был активен сегодня и есть streak."""
        user = MagicMock()
        user.current_streak = 7
        user.last_activity_date = date.today() - timedelta(days=1)
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        at_risk = await service.is_streak_at_risk(user_id=1)

        assert at_risk is True

    @pytest.mark.asyncio
    async def test_no_risk_if_streak_is_1(self, mock_db):
        """Нет риска если streak = 1 (нечего терять)."""
        user = MagicMock()
        user.current_streak = 1
        user.last_activity_date = date.today() - timedelta(days=1)
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        at_risk = await service.is_streak_at_risk(user_id=1)

        assert at_risk is False

    @pytest.mark.asyncio
    async def test_no_risk_if_no_streak(self, mock_db):
        """Нет риска если streak = 0."""
        user = MagicMock()
        user.current_streak = 0
        user.last_activity_date = None
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        at_risk = await service.is_streak_at_risk(user_id=1)

        assert at_risk is False


# ============== Streak Bonus Multiplier Tests ==============

class TestStreakBonusMultiplier:
    """Тесты множителя бонуса за streak."""

    @pytest.fixture
    def mock_db(self):
        """Мок async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_multiplier_equals_streak(self, mock_db):
        """Множитель равен текущему streak."""
        user = MagicMock()
        user.current_streak = 7
        user.max_streak = 14
        user.last_activity_date = date.today()
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        multiplier = await service.get_streak_bonus_multiplier(user_id=1)

        assert multiplier == 7

    @pytest.mark.asyncio
    async def test_multiplier_minimum_1(self, mock_db):
        """Множитель минимум 1."""
        user = MagicMock()
        user.current_streak = 0
        user.max_streak = 0
        user.last_activity_date = None
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        multiplier = await service.get_streak_bonus_multiplier(user_id=1)

        assert multiplier == 1


# ============== Comeback Bonus Tests ==============

class TestComebackBonus:
    """Тесты бонуса за comeback."""

    @pytest.fixture
    def mock_db(self):
        """Мок async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_should_award_comeback_after_7_days(self, mock_db):
        """Бонус за comeback после 7+ дней."""
        user = MagicMock()
        user.last_activity_date = date.today() - timedelta(days=8)
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        should_award = await service.should_award_comeback_bonus(user_id=1)

        assert should_award is True

    @pytest.mark.asyncio
    async def test_no_comeback_if_less_than_7_days(self, mock_db):
        """Нет бонуса если меньше 7 дней."""
        user = MagicMock()
        user.last_activity_date = date.today() - timedelta(days=5)
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        should_award = await service.should_award_comeback_bonus(user_id=1)

        assert should_award is False

    @pytest.mark.asyncio
    async def test_no_comeback_for_new_user(self, mock_db):
        """Нет бонуса для нового пользователя."""
        user = MagicMock()
        user.last_activity_date = None
        mock_db.get.return_value = user

        service = StreakService(mock_db)
        should_award = await service.should_award_comeback_bonus(user_id=1)

        assert should_award is False
