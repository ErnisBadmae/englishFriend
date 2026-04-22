"""Unit тесты для XPService.

Тестирует:
- Начисление XP
- Расчёт уровня
- Статистика за день
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, date

from app.services.gamification.xp_service import (
    XPService,
    XPEventKind,
    XP_VALUES,
    calculate_level,
    xp_for_level,
    xp_progress_in_level,
)


# ============== Level Calculation Tests ==============

class TestLevelCalculation:
    """Тесты формулы расчёта уровня."""

    def test_level_1_at_zero_xp(self):
        """Уровень 1 при 0 XP."""
        assert calculate_level(0) == 1

    def test_level_1_at_49_xp(self):
        """Уровень 1 при 49 XP."""
        assert calculate_level(49) == 1

    def test_level_2_at_50_xp(self):
        """Уровень 2 при 50 XP."""
        assert calculate_level(50) == 2

    def test_level_3_at_200_xp(self):
        """Уровень 3 при 200 XP."""
        assert calculate_level(200) == 3

    def test_level_5_at_800_xp(self):
        """Уровень 5 при 800 XP."""
        assert calculate_level(800) == 5

    def test_level_10_at_4050_xp(self):
        """Уровень 10 при 4050 XP."""
        assert calculate_level(4050) == 10

    def test_negative_xp_returns_level_1(self):
        """Отрицательный XP возвращает уровень 1."""
        assert calculate_level(-100) == 1


class TestXPForLevel:
    """Тесты функции xp_for_level."""

    def test_xp_for_level_1(self):
        """XP для уровня 1 = 0."""
        assert xp_for_level(1) == 0

    def test_xp_for_level_2(self):
        """XP для уровня 2 = 50."""
        assert xp_for_level(2) == 50

    def test_xp_for_level_3(self):
        """XP для уровня 3 = 200."""
        assert xp_for_level(3) == 200

    def test_xp_for_level_5(self):
        """XP для уровня 5 = 800."""
        assert xp_for_level(5) == 800


class TestXPProgress:
    """Тесты прогресса внутри уровня."""

    def test_progress_at_level_start(self):
        """Прогресс 0% в начале уровня."""
        # Level 2 starts at 50 XP
        progress = xp_progress_in_level(50)
        assert progress == pytest.approx(0.0, abs=0.01)

    def test_progress_at_50_percent(self):
        """Прогресс 50% в середине уровня."""
        # Level 2: 50-200, midpoint ~125
        progress = xp_progress_in_level(125)
        assert progress == pytest.approx(0.5, abs=0.1)

    def test_progress_near_level_end(self):
        """Прогресс близок к 100% в конце уровня."""
        # Level 2 ends at 200
        progress = xp_progress_in_level(199)
        assert progress > 0.9


# ============== XP Values Tests ==============

class TestXPValues:
    """Тесты значений XP для разных типов событий."""

    def test_session_complete_value(self):
        """XP за завершение сессии."""
        assert XP_VALUES[XPEventKind.SESSION_COMPLETE] == 10

    def test_streak_bonus_value(self):
        """XP за streak бонус."""
        assert XP_VALUES[XPEventKind.STREAK_BONUS] == 5

    def test_vocabulary_learned_value(self):
        """XP за изучение слова."""
        assert XP_VALUES[XPEventKind.VOCABULARY_LEARNED] == 2

    def test_first_session_value(self):
        """XP за первую сессию."""
        assert XP_VALUES[XPEventKind.FIRST_SESSION] == 50

    def test_comeback_value(self):
        """XP за comeback."""
        assert XP_VALUES[XPEventKind.COMEBACK] == 20


# ============== XPService Tests (Mocked) ==============

class TestXPServiceAwardXP:
    """Тесты начисления XP с мокированием БД."""

    @pytest.fixture
    def mock_db(self):
        """Мок async session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def mock_user(self):
        """Мок пользователя."""
        user = MagicMock()
        user.total_xp = 100
        return user

    @pytest.mark.asyncio
    async def test_award_xp_creates_event(self, mock_db, mock_user):
        """award_xp создаёт XPEvent."""
        mock_db.get.return_value = mock_user

        service = XPService(mock_db)
        event = await service.award_xp(
            user_id=1,
            kind=XPEventKind.SESSION_COMPLETE,
            session_id="test-session-123",
        )

        # Проверяем что add был вызван
        mock_db.add.assert_called_once()
        assert mock_db.execute.await_count >= 2

        # Проверяем что commit был вызван
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_award_xp_updates_user_total(self, mock_db, mock_user):
        """award_xp обновляет total_xp пользователя."""
        mock_db.get.return_value = mock_user
        initial_xp = mock_user.total_xp

        service = XPService(mock_db)
        await service.award_xp(
            user_id=1,
            kind=XPEventKind.SESSION_COMPLETE,
        )

        # XP должен увеличиться на 10 (SESSION_COMPLETE)
        assert mock_user.total_xp == initial_xp + 10

    @pytest.mark.asyncio
    async def test_award_xp_with_multiplier(self, mock_db, mock_user):
        """award_xp применяет multiplier."""
        mock_db.get.return_value = mock_user
        initial_xp = mock_user.total_xp

        service = XPService(mock_db)
        await service.award_xp(
            user_id=1,
            kind=XPEventKind.STREAK_BONUS,
            multiplier=7,  # 7-day streak
        )

        # XP должен увеличиться на 5 * 7 = 35
        assert mock_user.total_xp == initial_xp + 35

    @pytest.mark.asyncio
    async def test_award_xp_with_custom_points(self, mock_db, mock_user):
        """award_xp с custom_points."""
        mock_db.get.return_value = mock_user
        initial_xp = mock_user.total_xp

        service = XPService(mock_db)
        await service.award_xp(
            user_id=1,
            kind=XPEventKind.SESSION_COMPLETE,
            custom_points=100,
        )

        # Custom points переопределяют базовое значение
        assert mock_user.total_xp == initial_xp + 100

    @pytest.mark.asyncio
    async def test_award_xp_with_string_kind(self, mock_db, mock_user):
        """award_xp работает со строковым kind."""
        mock_db.get.return_value = mock_user

        service = XPService(mock_db)
        await service.award_xp(
            user_id=1,
            kind="session_complete",  # String instead of enum
        )

        mock_db.add.assert_called_once()


class TestXPServiceGetTotalXP:
    """Тесты получения общего XP."""

    @pytest.fixture
    def mock_db(self):
        """Мок async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_total_xp_returns_user_xp(self, mock_db):
        """get_total_xp возвращает XP пользователя."""
        mock_user = MagicMock()
        mock_user.total_xp = 1250
        mock_db.get.return_value = mock_user

        service = XPService(mock_db)
        total = await service.get_total_xp(user_id=1)

        assert total == 1250

    @pytest.mark.asyncio
    async def test_get_total_xp_returns_zero_for_missing_user(self, mock_db):
        """get_total_xp возвращает 0 для несуществующего пользователя."""
        mock_db.get.return_value = None

        service = XPService(mock_db)
        total = await service.get_total_xp(user_id=999)

        assert total == 0


class TestXPServiceLevelInfo:
    """Тесты получения информации об уровне."""

    @pytest.fixture
    def mock_db(self):
        """Мок async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_level_info(self, mock_db):
        """get_level_info возвращает корректную структуру."""
        mock_user = MagicMock()
        mock_user.total_xp = 850
        mock_db.get.return_value = mock_user

        service = XPService(mock_db)
        info = await service.get_level_info(user_id=1)

        assert info["total_xp"] == 850
        assert info["level"] == 5  # sqrt(850/50) ≈ 4.12 → 5
        assert "current_level_xp" in info
        assert "next_level_xp" in info
        assert "progress" in info
        assert 0 <= info["progress"] <= 1


class TestXPServiceFirstSession:
    """Тесты проверки первой сессии."""

    @pytest.fixture
    def mock_db(self):
        """Мок async session."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None  # No previous first_session event
        db.execute.return_value = mock_result
        return db

    @pytest.mark.asyncio
    async def test_check_first_session_returns_true_for_new_user(self, mock_db):
        """check_first_session возвращает True для нового пользователя."""
        service = XPService(mock_db)
        is_first = await service.check_first_session(user_id=1)

        assert is_first is True

    @pytest.mark.asyncio
    async def test_check_first_session_returns_false_after_award(self, mock_db):
        """check_first_session возвращает False после награды."""
        # Simulate existing first_session event
        mock_result = MagicMock()
        mock_result.scalar.return_value = "some-event-id"
        mock_db.execute.return_value = mock_result

        service = XPService(mock_db)
        is_first = await service.check_first_session(user_id=1)

        assert is_first is False
