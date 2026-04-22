"""
Сервис для управления словарём с FSRS spaced repetition.

Функции:
1. Добавление новых слов из диалогов
2. Получение карточек для повторения
3. Обработка результатов повторения
4. Извлечение новой лексики из ответов ментора
"""

from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass
from enum import IntEnum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.dialects.postgresql import insert

from fsrs import Scheduler, Card, Rating, State

from app.models.extended_tables import VocabularyCard, VocabularyReview


class ReviewRating(IntEnum):
    """Оценки повторения (совпадают с FSRS Rating)."""
    AGAIN = 1  # Забыл
    HARD = 2   # Трудно вспомнил
    GOOD = 3   # Нормально вспомнил
    EASY = 4   # Легко вспомнил


@dataclass
class VocabularyWord:
    """Слово для добавления в словарь."""
    word: str
    translation: Optional[str] = None
    example_sentence: Optional[str] = None
    phonetic: Optional[str] = None


class VocabularyService:
    """Сервис для работы со словарём и FSRS."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.scheduler = Scheduler()

    async def add_word(
        self,
        user_id: int,
        word: VocabularyWord,
        session_id: Optional[str] = None,
    ) -> VocabularyCard:
        """
        Добавить слово в словарь пользователя.

        Если слово уже есть, обновляет пример и перевод.

        Args:
            user_id: ID пользователя
            word: Слово для добавления
            session_id: ID сессии, откуда слово (опционально)

        Returns:
            Созданная или обновлённая карточка
        """
        # Проверяем, есть ли уже такое слово
        existing = await self.get_card_by_word(user_id, word.word)
        if existing:
            # Обновляем только пример и перевод, не трогаем FSRS
            if word.example_sentence:
                existing.example_sentence = word.example_sentence
            if word.translation:
                existing.translation = word.translation
            await self.db.commit()
            return existing

        # Создаём новую карточку
        card = VocabularyCard(
            user_id=user_id,
            word=word.word.lower().strip(),
            translation=word.translation,
            example_sentence=word.example_sentence,
            phonetic=word.phonetic,
            source_session_id=session_id,
            # FSRS начальные значения
            fsrs_state=0,  # New
            fsrs_step=0,
            fsrs_stability=0.0,
            fsrs_difficulty=0.0,
            due_at=datetime.now(timezone.utc),
        )

        self.db.add(card)
        await self.db.commit()
        await self.db.refresh(card)

        return card

    async def get_card_by_word(
        self,
        user_id: int,
        word: str,
    ) -> Optional[VocabularyCard]:
        """Получить карточку по слову."""
        result = await self.db.execute(
            select(VocabularyCard).where(
                and_(
                    VocabularyCard.user_id == user_id,
                    VocabularyCard.word == word.lower().strip(),
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_card(
        self,
        user_id: int,
        word: str,
        translation: str = "",
        example_sentence: str = "",
        notes: Optional[str] = None,
        source: str = "manual",
        session_id: Optional[str] = None,
    ) -> Optional[VocabularyCard]:
        """Создать новую карточку (alias для add_word с расширенными параметрами).

        Args:
            user_id: ID пользователя
            word: Слово
            translation: Перевод
            example_sentence: Пример использования
            notes: Заметки
            source: Источник (session, goal_template, manual)
            session_id: ID сессии

        Returns:
            Созданная карточка или None если уже существует
        """
        # Проверяем дубликат
        existing = await self.get_card_by_word(user_id, word)
        if existing:
            return None  # Не создаём дубликат

        vocab_word = VocabularyWord(
            word=word,
            translation=translation,
            example_sentence=example_sentence,
        )

        card = await self.add_word(user_id, vocab_word, session_id)

        # Добавляем notes в отдельное поле если есть
        if notes and card:
            # Notes можно хранить в example_sentence если пустой
            if not card.example_sentence:
                card.example_sentence = notes
            await self.db.commit()

        return card

    async def get_due_cards(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[VocabularyCard]:
        """
        Получить карточки, которые пора повторять.

        Args:
            user_id: ID пользователя
            limit: Максимум карточек

        Returns:
            Список карточек для повторения
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(VocabularyCard)
            .where(
                and_(
                    VocabularyCard.user_id == user_id,
                    VocabularyCard.due_at <= now,
                )
            )
            .order_by(VocabularyCard.due_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_new_cards(
        self,
        user_id: int,
        limit: int = 5,
    ) -> list[VocabularyCard]:
        """
        Получить новые карточки (ещё не изучались).

        Args:
            user_id: ID пользователя
            limit: Максимум карточек

        Returns:
            Список новых карточек
        """
        result = await self.db.execute(
            select(VocabularyCard)
            .where(
                and_(
                    VocabularyCard.user_id == user_id,
                    VocabularyCard.fsrs_state == 0,  # New
                )
            )
            .order_by(VocabularyCard.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def review_card(
        self,
        card: VocabularyCard,
        rating: ReviewRating,
        session_id: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> VocabularyCard:
        """
        Записать результат повторения карточки.

        Args:
            card: Карточка для повторения
            rating: Оценка (1-4)
            session_id: ID текущей сессии
            duration_ms: Время ответа в миллисекундах

        Returns:
            Обновлённая карточка
        """
        # Сохраняем предыдущее состояние для истории
        prev_state = card.fsrs_state
        prev_stability = card.fsrs_stability
        prev_difficulty = card.fsrs_difficulty

        # Создаём FSRS Card из текущего состояния
        fsrs_card = Card()
        fsrs_card.state = State(card.fsrs_state) if card.fsrs_state > 0 else State.New
        fsrs_card.step = card.fsrs_step
        fsrs_card.stability = card.fsrs_stability if card.fsrs_stability > 0 else 0.0
        fsrs_card.difficulty = card.fsrs_difficulty if card.fsrs_difficulty > 0 else 0.0
        if card.last_reviewed_at:
            fsrs_card.last_review = card.last_reviewed_at
        if card.due_at:
            fsrs_card.due = card.due_at

        # Получаем Rating для FSRS
        fsrs_rating = Rating(rating)

        # Выполняем review
        new_card, review_log = self.scheduler.review_card(fsrs_card, fsrs_rating)

        # Обновляем карточку в БД
        now = datetime.now(timezone.utc)
        card.fsrs_state = new_card.state.value
        card.fsrs_step = new_card.step
        card.fsrs_stability = new_card.stability
        card.fsrs_difficulty = new_card.difficulty
        card.due_at = new_card.due
        card.last_reviewed_at = now
        card.review_count += 1
        if rating >= ReviewRating.GOOD:
            card.correct_count += 1

        # Создаём запись истории
        review_record = VocabularyReview(
            card_id=card.id,
            user_id=card.user_id,
            rating=rating,
            prev_state=prev_state,
            prev_stability=prev_stability,
            prev_difficulty=prev_difficulty,
            reviewed_at=now,
            review_duration_ms=duration_ms,
            session_id=session_id,
        )
        self.db.add(review_record)

        await self.db.commit()
        await self.db.refresh(card)

        return card

    async def get_vocabulary_stats(
        self,
        user_id: int,
    ) -> dict:
        """
        Получить статистику словаря пользователя.

        Returns:
            Словарь со статистикой
        """
        from sqlalchemy import func

        # Подсчёт по состояниям
        result = await self.db.execute(
            select(
                VocabularyCard.fsrs_state,
                func.count(VocabularyCard.id).label('count')
            )
            .where(VocabularyCard.user_id == user_id)
            .group_by(VocabularyCard.fsrs_state)
        )
        state_counts = {row.fsrs_state: row.count for row in result}

        # Подсчёт due сегодня
        now = datetime.now(timezone.utc)
        due_result = await self.db.execute(
            select(func.count(VocabularyCard.id))
            .where(
                and_(
                    VocabularyCard.user_id == user_id,
                    VocabularyCard.due_at <= now,
                )
            )
        )
        due_count = due_result.scalar() or 0

        return {
            'total': sum(state_counts.values()),
            'new': state_counts.get(0, 0),
            'learning': state_counts.get(1, 0),
            'review': state_counts.get(2, 0),
            'relearning': state_counts.get(3, 0),
            'due_now': due_count,
        }


def extract_vocabulary_from_response(mentor_response: str) -> list[str]:
    """
    Извлечь потенциальные новые слова из ответа ментора.

    Ментор часто использует паттерны типа:
    - "The word 'resilience' means..."
    - "...that's called 'procrastination'"
    - "'Eloquent' is a great word for..."

    Args:
        mentor_response: Текст ответа ментора

    Returns:
        Список найденных слов/фраз
    """
    import re

    words = []

    # Паттерны для извлечения слов
    patterns = [
        # 'word' или "word" (в кавычках)
        r"['\"]([a-zA-Z]+)['\"]",
        # "The word X means..." или "X is called..."
        r"(?:word|term|phrase|expression)\s+['\"]?(\w+)['\"]?",
        # "...that's X" (определения)
        r"(?:that's|called|known as)\s+['\"]?(\w+)['\"]?",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, mentor_response, re.IGNORECASE)
        words.extend(matches)

    # Фильтруем короткие и стоп-слова
    stop_words = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been',
                  'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                  'would', 'could', 'should', 'may', 'might', 'must', 'can',
                  'i', 'you', 'he', 'she', 'it', 'we', 'they', 'this', 'that'}

    filtered = [
        w.lower() for w in words
        if len(w) >= 4 and w.lower() not in stop_words
    ]

    return list(set(filtered))
