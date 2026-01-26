"""Post-Session Service - обработка после завершения сессии.

Отвечает за:
1. Анализ транскрипта сессии через LLM
2. Извлечение новых слов/фраз для изучения
3. Создание флеш-карточек (vocabulary_cards)
4. Определение и сохранение уровня (assessment)
5. Обновление learning_plan

Вызывается при завершении сессии (type: "end" или disconnect).
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai.llm_provider import get_llm_provider
from app.services.ai.vocabulary_service import VocabularyService
from app.services.learning_plan_service import LearningPlanService
from app.services.data_flow_logger import data_logger

logger = logging.getLogger(__name__)


# Промпт для анализа сессии
SESSION_ANALYSIS_PROMPT = """Analyze this English learning conversation and extract:

1. **New vocabulary**: Words or phrases the student struggled with or didn't know
2. **Grammar errors**: Common mistakes the student made
3. **Assessed level**: Estimate CEFR level (A1, A2, B1, B2, C1, C2) based on the conversation
4. **Goal detected**: What is the student's learning goal (if mentioned)?

Conversation:
{conversation}

Respond in this exact JSON format:
```json
{
  "vocabulary": [
    {"word": "implementation", "context": "I did the implementation", "correction": "I completed the implementation", "translation_ru": "реализация"},
    {"word": "inference", "context": "student asked about this", "correction": null, "translation_ru": "вывод/инференс"}
  ],
  "grammar_errors": [
    {"error": "I have work", "correction": "I have worked / I've been working", "rule": "Present Perfect tense"}
  ],
  "assessed_level": "B1",
  "level_confidence": "medium",
  "level_notes": "Good vocabulary but struggles with tenses",
  "detected_goal": "ML interview preparation",
  "recommendations": ["Practice past tenses", "Learn more technical vocabulary"]
}
```

Only include vocabulary words that:
- The student didn't know or used incorrectly
- Are relevant to their learning goal
- Are B1+ level (skip basic words like "go", "make")

Be concise. Maximum 5 vocabulary items, 3 grammar errors.
"""


class PostSessionService:
    """Сервис для обработки после сессии."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_provider()
        self.vocabulary_service = VocabularyService(db)
        self.learning_plan_service = LearningPlanService(db)

    async def process_session_end(
        self,
        user_id: int,
        session_id: str,
        conversation_history: list[dict],
        current_mode: str,
        session_context: dict,
    ) -> dict:
        """Обработать завершение сессии.

        Args:
            user_id: ID пользователя
            session_id: ID сессии
            conversation_history: История диалога
            current_mode: Режим сессии
            session_context: Контекст (goal, level, etc.)

        Returns:
            Результат обработки:
            {
                "cards_created": 3,
                "level_assessed": "B1",
                "goal_updated": True,
                "xp_bonus": 10,
            }
        """
        result = {
            "cards_created": 0,
            "level_assessed": None,
            "goal_updated": False,
            "xp_bonus": 0,
            "recommendations": [],
        }

        if not conversation_history or len(conversation_history) < 2:
            data_logger.log_session_summary(
                user_id=user_id,
                session_id=session_id,
                duration_minutes=0,
                new_words=0,
                xp_earned=0,
            )
            return result

        # Анализируем сессию через LLM
        try:
            analysis = await self._analyze_session(conversation_history)
            data_logger.log_postgres_write(
                table="session_analysis",
                operation="ANALYZE",
                data={"vocabulary_count": len(analysis.get("vocabulary", []))},
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(f"Session analysis failed: {e}")
            return result

        # 1. Создаём флеш-карточки из новых слов
        vocabulary_items = analysis.get("vocabulary", [])
        for item in vocabulary_items:
            try:
                card = await self.vocabulary_service.create_card(
                    user_id=user_id,
                    word=item["word"],
                    translation=item.get("translation_ru", ""),
                    example_sentence=item.get("context", ""),
                    notes=item.get("correction"),
                    source="session",
                )
                if card:
                    result["cards_created"] += 1
                    data_logger.log_vocabulary_card_created(
                        user_id=user_id,
                        word=item["word"],
                        source="session_analysis",
                    )
            except Exception as e:
                logger.warning(f"Failed to create card for '{item.get('word')}': {e}")

        # 2. Обновляем уровень если это assessment или первая сессия
        assessed_level = analysis.get("assessed_level")
        if assessed_level and (current_mode == "assessment" or not session_context.get("assessed_level")):
            try:
                await self.learning_plan_service.record_assessment(
                    user_id=user_id,
                    assessed_level=assessed_level,
                    scores={
                        "confidence": analysis.get("level_confidence", "low"),
                        "notes": analysis.get("level_notes", ""),
                    },
                )
                result["level_assessed"] = assessed_level
                data_logger.log_learning_plan_update(
                    user_id=user_id,
                    field="assessed_level",
                    old_value=session_context.get("assessed_level"),
                    new_value=assessed_level,
                )
            except Exception as e:
                logger.warning(f"Failed to record assessment: {e}")

        # 3. Обновляем цель если определена и не была установлена
        detected_goal = analysis.get("detected_goal")
        if detected_goal and not session_context.get("goal"):
            try:
                await self.learning_plan_service.set_goal(user_id, detected_goal)
                result["goal_updated"] = True
                data_logger.log_goal_detected(
                    user_id=user_id,
                    message="(from session analysis)",
                    detected_goal=detected_goal,
                )
            except Exception as e:
                logger.warning(f"Failed to set goal: {e}")

        # 4. Сохраняем рекомендации
        result["recommendations"] = analysis.get("recommendations", [])

        # 5. Начисляем бонус XP за изученные слова
        if result["cards_created"] > 0:
            result["xp_bonus"] = result["cards_created"] * 2  # 2 XP за слово

        # Логируем итоги сессии
        data_logger.log_session_summary(
            user_id=user_id,
            session_id=session_id,
            duration_minutes=len(conversation_history) * 2,  # ~2 мин на реплику
            new_words=result["cards_created"],
            xp_earned=result["xp_bonus"],
        )

        logger.info(f"Post-session completed: cards={result['cards_created']}, level={result['level_assessed']}")
        return result

    async def _analyze_session(self, conversation_history: list[dict]) -> dict:
        """Анализировать сессию через LLM.

        Args:
            conversation_history: История диалога

        Returns:
            Результат анализа (vocabulary, grammar_errors, level, etc.)
        """
        # Формируем текст разговора
        conversation_text = "\n".join([
            f"{'Student' if msg['role'] == 'user' else 'Mentor'}: {msg['content']}"
            for msg in conversation_history
        ])

        prompt = SESSION_ANALYSIS_PROMPT.format(conversation=conversation_text)

        # Запрашиваем анализ
        response = await self.llm.generate(
            user_message="Please analyze this conversation.",
            system_prompt=prompt,
            max_tokens=800,
        )

        # Парсим JSON из ответа
        return self._parse_analysis_response(response)

    def _parse_analysis_response(self, response: str) -> dict:
        """Парсить JSON из ответа LLM.

        Args:
            response: Текстовый ответ от LLM

        Returns:
            Распарсенный dict
        """
        # Ищем JSON блок в ответе
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Пробуем парсить весь ответ как JSON
        try:
            # Убираем возможные markdown обёртки
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]

            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM response as JSON: {response[:100]}...")
            return {
                "vocabulary": [],
                "grammar_errors": [],
                "assessed_level": None,
                "detected_goal": None,
                "recommendations": [],
            }


async def create_initial_vocabulary_cards(
    db: AsyncSession,
    user_id: int,
    goal: str,
    vocabulary_words: list[str],
) -> int:
    """Создать начальные карточки на основе цели.

    Вызывается после установки цели (set_goal).

    Args:
        db: Сессия БД
        user_id: ID пользователя
        goal: Цель обучения
        vocabulary_words: Рекомендованные слова из шаблона

    Returns:
        Количество созданных карточек
    """
    vocabulary_service = VocabularyService(db)
    created = 0

    for word in vocabulary_words[:10]:  # Максимум 10 начальных карточек
        try:
            card = await vocabulary_service.create_card(
                user_id=user_id,
                word=word,
                translation="",  # Будет заполнено при изучении
                example_sentence="",
                notes=f"Initial vocabulary for: {goal}",
                source="goal_template",
            )
            if card:
                created += 1
                data_logger.log_vocabulary_card_created(
                    user_id=user_id,
                    word=word,
                    source="goal_template",
                )
        except Exception as e:
            logger.warning(f"Failed to create initial card for '{word}': {e}")

    logger.info(f"Created {created} initial vocabulary cards for user {user_id}")
    return created
