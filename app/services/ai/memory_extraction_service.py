"""Сервис извлечения памяти из разговоров.

Анализирует диалоги и извлекает:
- Факты о пользователе (имя, страна, профессия)
- Предпочтения (интересы, стиль обучения)
- Опыт (проекты, достижения)
- Цели (чего хочет достичь)
- Паттерны ошибок (повторяющиеся грамматические ошибки)

Использует LLM для структурированного извлечения.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from app.services.ai.llm_provider import (
    LLMEmptyContentError,
    RETRYABLE_EXCEPTIONS,
    get_llm_provider,
)
from app.models.enums_and_dimensions import MemoryKind

logger = logging.getLogger(__name__)


class MemoryExtractionSoftFailure(RuntimeError):
    """Transient, expected extraction failure that should not look fatal."""

    def __init__(self, *, reason: str, original_exception: Exception):
        self.reason = reason
        self.original_exception = original_exception
        super().__init__(f"{reason}: {original_exception}")


@dataclass
class ExtractedMemory:
    """Извлечённое воспоминание."""
    kind: MemoryKind
    content: str
    salience: float  # 0.0 - 1.0 (важность)
    meta: Optional[dict] = None


# Промпт для извлечения фактов из диалога
EXTRACTION_PROMPT = """You are a memory extraction system for an English learning app.

Analyze this conversation between a student and an AI English tutor.
Extract important facts that should be remembered for future sessions.

## Categories to extract:

1. **FACT** - Personal information about the student:
   - Name, country, city
   - Profession, workplace
   - Education, skills
   - Age, family (if mentioned)

2. **PREFERENCE** - Learning preferences:
   - Preferred topics
   - Learning style
   - Time preferences
   - What motivates them

3. **EXPERIENCE** - Past experiences:
   - Projects they worked on
   - Jobs they had
   - Achievements
   - Travel, hobbies

4. **GOAL** - Learning objectives:
   - Why they learn English
   - Target job/exam
   - Desired level
   - Deadline if any

5. **ERROR_PATTERN** - Recurring language mistakes:
   - Grammar errors they repeat
   - Pronunciation issues
   - Vocabulary gaps

## Conversation:
{conversation}

## Instructions:
Return a JSON array of extracted memories. Each memory should have:
- "kind": one of "fact", "preference", "experience", "goal", "error_pattern"
- "content": clear English statement of the information
- "salience": importance from 0.0 to 1.0 (name=0.9, hobby=0.5, typo=0.3)

Return ONLY valid JSON array. If nothing to extract, return empty array [].

## Example output:
[
  {{"kind": "fact", "content": "Student's name is Aaron", "salience": 0.9}},
  {{"kind": "goal", "content": "Wants to pass ML job interview", "salience": 0.95}},
  {{"kind": "error_pattern", "content": "Tends to omit articles before nouns", "salience": 0.7}}
]

## Your extraction:
"""


class MemoryExtractionService:
    """Сервис извлечения памяти из диалогов."""

    def __init__(self, llm_provider: Optional[str] = None):
        """
        Args:
            llm_provider: Тип LLM провайдера (groq, openai, vllm)
        """
        self._llm = get_llm_provider(llm_provider)
        logger.info(f"MemoryExtractionService initialized")

    def _classify_transient_failure(self, exc: Exception) -> Optional[str]:
        if isinstance(exc, (MemoryExtractionSoftFailure, *RETRYABLE_EXCEPTIONS, ConnectionError, TimeoutError, OSError)):
            return "provider_connection_error"

        message = f"{type(exc).__name__}: {exc}".lower()
        needles = (
            "connection error",
            "connect error",
            "connection aborted",
            "connection reset",
            "server disconnected",
            "timed out",
            "timeout",
            "temporarily unavailable",
            "remote protocol error",
        )
        if any(needle in message for needle in needles):
            return "provider_connection_error"
        return None

    async def extract_from_conversation(
        self,
        messages: list[dict],
        existing_memories: Optional[list[str]] = None,
    ) -> list[ExtractedMemory]:
        """Извлечь воспоминания из диалога.

        Args:
            messages: Список сообщений [{"role": "user/assistant", "content": "..."}]
            existing_memories: Уже известные факты (чтобы не дублировать)

        Returns:
            Список извлечённых воспоминаний
        """
        if not messages:
            return []

        # Форматируем диалог
        conversation_text = self._format_conversation(messages)

        # Добавляем контекст существующих воспоминаний
        if existing_memories:
            conversation_text += f"\n\n## Already known (do not duplicate):\n"
            for mem in existing_memories[:10]:  # Ограничиваем контекст
                conversation_text += f"- {mem}\n"

        prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)

        try:
            response = await self._llm.generate(
                user_message=prompt,
                system_prompt="You are a precise JSON extraction system. Return only valid JSON.",
                max_tokens=500,
            )

            # Парсим JSON
            memories = self._parse_response(response)
            logger.info(f"Extracted {len(memories)} memories from conversation")
            return memories

        except LLMEmptyContentError as e:
            logger.warning(f"Memory extraction returned no final content: {e}")
            return []
        except Exception as e:
            reason = self._classify_transient_failure(e)
            if reason:
                raise MemoryExtractionSoftFailure(reason=reason, original_exception=e) from e
            raise

    async def extract_error_patterns(
        self,
        student_utterances: list[str],
    ) -> list[ExtractedMemory]:
        """Извлечь паттерны ошибок из высказываний студента.

        Args:
            student_utterances: Список высказываний студента

        Returns:
            Список паттернов ошибок
        """
        if not student_utterances:
            return []

        text = "\n".join(f"- {u}" for u in student_utterances[-10:])  # Последние 10

        prompt = f"""Analyze these English utterances from a Russian-speaking student.
Identify recurring grammar/vocabulary/pronunciation patterns that indicate learning gaps.

## Student utterances:
{text}

## Return JSON array of error patterns:
[
  {{"kind": "error_pattern", "content": "Description of the error pattern", "salience": 0.0-1.0}}
]

Common Russian speaker errors to look for:
- Missing articles (a, an, the)
- Wrong prepositions
- Present Perfect vs Past Simple confusion
- Subject-verb agreement
- Double negatives
- Word order issues

Return only significant patterns, not one-time typos. Return empty [] if no patterns found.
"""

        try:
            response = await self._llm.generate(
                user_message=prompt,
                system_prompt="You are an ESL error analysis system. Return only valid JSON.",
                max_tokens=300,
            )

            memories = self._parse_response(response)
            # Фильтруем только error_patterns
            return [m for m in memories if m.kind == MemoryKind.ERROR_PATTERN]

        except LLMEmptyContentError as e:
            logger.warning(f"Error pattern extraction returned no final content: {e}")
            return []
        except Exception as e:
            reason = self._classify_transient_failure(e)
            if reason:
                raise MemoryExtractionSoftFailure(reason=reason, original_exception=e) from e
            raise

    def _format_conversation(self, messages: list[dict]) -> str:
        """Форматировать диалог для промпта."""
        lines = []
        for msg in messages[-20:]:  # Ограничиваем контекст
            role = "Student" if msg.get("role") == "user" else "Tutor"
            content = msg.get("content", "")[:500]  # Ограничиваем длину
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _parse_response(self, response: str) -> list[ExtractedMemory]:
        """Распарсить JSON ответ от LLM."""
        # Ищем JSON в ответе
        response = response.strip()

        # Удаляем markdown блоки если есть
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        response = response.strip()

        try:
            data = json.loads(response)
            if not isinstance(data, list):
                data = [data]

            memories = []
            for item in data:
                if not isinstance(item, dict):
                    continue

                kind_str = item.get("kind", "").lower()
                kind_map = {
                    "fact": MemoryKind.FACT,
                    "preference": MemoryKind.PREFERENCE,
                    "experience": MemoryKind.EXPERIENCE,
                    "goal": MemoryKind.GOAL,
                    "error_pattern": MemoryKind.ERROR_PATTERN,
                }

                if kind_str not in kind_map:
                    continue

                content = item.get("content", "").strip()
                if not content:
                    continue

                salience = float(item.get("salience", 0.5))
                salience = max(0.0, min(1.0, salience))  # Clamp to 0-1

                memories.append(ExtractedMemory(
                    kind=kind_map[kind_str],
                    content=content,
                    salience=salience,
                    meta=item.get("meta"),
                ))

            return memories

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response[:200]}")
            return []


# Singleton instance
_extraction_service: Optional[MemoryExtractionService] = None


def get_memory_extraction_service() -> MemoryExtractionService:
    """Получить singleton экземпляр MemoryExtractionService."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = MemoryExtractionService()
    return _extraction_service
