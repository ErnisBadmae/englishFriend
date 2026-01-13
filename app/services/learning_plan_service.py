"""Сервис для управления планом обучения.

Отвечает за:
- Создание плана на основе цели пользователя
- Хранение прогресса и milestone'ов
- Запись результатов assessment
- Обновление roadmap
"""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm.attributes import flag_modified

from app.models.extended_tables import LearningPlan
from app.models.enums_and_dimensions import CEFRLevel


@dataclass
class GoalTemplate:
    """Шаблон цели обучения."""
    goal: str
    focus_areas: list[dict]
    milestones: list[dict]
    preferred_mode: str
    recommended_vocabulary: list[str]


# =============================================================================
# Шаблоны целей
# =============================================================================

GOAL_TEMPLATES = {
    "ml_interview": GoalTemplate(
        goal="ML/Data Science Interview Preparation",
        focus_areas=[
            {"area": "technical_vocabulary", "description": "ML terms and concepts"},
            {"area": "behavioral_questions", "description": "STAR method answers"},
            {"area": "explain_concepts", "description": "Simplifying complex ideas"},
            {"area": "project_walkthrough", "description": "Describing your work"},
        ],
        milestones=[
            {"name": "Complete assessment", "type": "assessment", "done": False},
            {"name": "Master 50 ML terms", "type": "vocabulary", "target": 50, "progress": 0},
            {"name": "Complete 5 mock interviews", "type": "mock_interview", "target": 5, "count": 0},
            {"name": "Practice STAR method", "type": "skill", "done": False},
        ],
        preferred_mode="mock_interview",
        recommended_vocabulary=[
            "implementation", "deployment", "inference", "training", "validation",
            "feature engineering", "cross-validation", "hyperparameter", "overfitting",
            "precision", "recall", "accuracy", "pipeline", "scalability", "optimization",
            "architecture", "framework", "algorithm", "dataset", "preprocessing",
        ],
    ),
    "software_interview": GoalTemplate(
        goal="Software Engineering Interview Preparation",
        focus_areas=[
            {"area": "technical_discussion", "description": "System design, algorithms"},
            {"area": "behavioral_questions", "description": "Team collaboration stories"},
            {"area": "code_explanation", "description": "Walking through your code"},
        ],
        milestones=[
            {"name": "Complete assessment", "type": "assessment", "done": False},
            {"name": "Master 40 tech terms", "type": "vocabulary", "target": 40, "progress": 0},
            {"name": "Complete 5 mock interviews", "type": "mock_interview", "target": 5, "count": 0},
        ],
        preferred_mode="mock_interview",
        recommended_vocabulary=[
            "scalability", "architecture", "microservices", "deployment", "debugging",
            "refactoring", "optimization", "dependency", "integration", "abstraction",
            "inheritance", "encapsulation", "polymorphism", "asynchronous", "concurrent",
        ],
    ),
    "general_fluency": GoalTemplate(
        goal="General English Fluency",
        focus_areas=[
            {"area": "conversation", "description": "Natural speaking flow"},
            {"area": "vocabulary", "description": "Expanding word range"},
            {"area": "grammar", "description": "Common mistake correction"},
        ],
        milestones=[
            {"name": "Complete assessment", "type": "assessment", "done": False},
            {"name": "Learn 100 new words", "type": "vocabulary", "target": 100, "progress": 0},
            {"name": "Practice 10 hours", "type": "practice", "target": 600, "minutes": 0},
        ],
        preferred_mode="free_conversation",
        recommended_vocabulary=[],
    ),
}


class LearningPlanService:
    """Сервис для управления планом обучения."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_plan(self, user_id: int) -> LearningPlan:
        """Получить или создать план обучения.

        Args:
            user_id: ID пользователя

        Returns:
            LearningPlan
        """
        result = await self.db.execute(
            select(LearningPlan).where(LearningPlan.user_id == user_id)
        )
        plan = result.scalar_one_or_none()

        if not plan:
            plan = LearningPlan(
                user_id=user_id,
                roadmap={
                    "goal": None,
                    "focus_areas": [],
                    "milestones": [],
                    "preferred_mode": "free_conversation",
                    "sessions_completed": 0,
                    "total_practice_minutes": 0,
                    "assessment_history": [],
                },
            )
            self.db.add(plan)
            await self.db.commit()
            await self.db.refresh(plan)

        return plan

    async def set_goal(
        self,
        user_id: int,
        goal_text: str,
        target_level: Optional[str] = None,
    ) -> LearningPlan:
        """Установить цель обучения.

        Анализирует текст цели и применяет подходящий шаблон.

        Args:
            user_id: ID пользователя
            goal_text: Текст цели (например, "ML interview preparation")
            target_level: Целевой CEFR уровень

        Returns:
            Обновленный LearningPlan
        """
        plan = await self.get_or_create_plan(user_id)

        # Определяем шаблон на основе текста цели
        template = self._match_goal_template(goal_text)

        # Обновляем roadmap
        roadmap = plan.roadmap or {}
        roadmap.update({
            "goal": goal_text,
            "goal_template": template.goal if template else "custom",
            "focus_areas": template.focus_areas if template else [],
            "milestones": template.milestones if template else [],
            "preferred_mode": template.preferred_mode if template else "free_conversation",
            "recommended_vocabulary": template.recommended_vocabulary if template else [],
            "created_at": datetime.utcnow().isoformat(),
        })

        # Обновляем план - важно: создаём новый dict чтобы SQLAlchemy увидел изменение
        plan.roadmap = dict(roadmap)  # Новый объект для отслеживания изменений
        flag_modified(plan, 'roadmap')  # Явно помечаем как изменённое

        if target_level:
            plan.level_target = CEFRLevel(target_level)
        plan.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(plan)

        return plan

    async def record_assessment(
        self,
        user_id: int,
        assessed_level: str,
        scores: Optional[dict] = None,
        notes: Optional[str] = None,
    ) -> LearningPlan:
        """Записать результат assessment.

        Args:
            user_id: ID пользователя
            assessed_level: Оценённый CEFR уровень
            scores: Детальные оценки (vocabulary, grammar, fluency, etc.)
            notes: Заметки от assessment

        Returns:
            Обновленный LearningPlan
        """
        plan = await self.get_or_create_plan(user_id)

        roadmap = plan.roadmap or {}

        # Добавляем в историю assessment
        assessment_history = roadmap.get("assessment_history", [])
        assessment_history.append({
            "date": datetime.utcnow().isoformat(),
            "level": assessed_level,
            "scores": scores or {},
            "notes": notes,
        })
        roadmap["assessment_history"] = assessment_history

        # Обновляем текущий уровень
        roadmap["current_level"] = assessed_level
        roadmap["last_assessment"] = datetime.utcnow().isoformat()

        # Отмечаем milestone
        self._update_milestone(roadmap, "assessment", done=True)

        plan.roadmap = roadmap
        plan.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(plan)

        return plan

    async def increment_session_count(
        self,
        user_id: int,
        mode: str,
        duration_minutes: int = 0,
    ) -> LearningPlan:
        """Увеличить счётчик сессий.

        Args:
            user_id: ID пользователя
            mode: Режим сессии
            duration_minutes: Длительность в минутах

        Returns:
            Обновленный LearningPlan
        """
        plan = await self.get_or_create_plan(user_id)

        roadmap = plan.roadmap or {}
        roadmap["sessions_completed"] = roadmap.get("sessions_completed", 0) + 1
        roadmap["total_practice_minutes"] = roadmap.get("total_practice_minutes", 0) + duration_minutes

        # Update milestones
        if mode == "mock_interview":
            self._update_milestone(roadmap, "mock_interview", increment=1)
        self._update_milestone(roadmap, "practice", minutes=roadmap.get("total_practice_minutes", 0))

        plan.roadmap = roadmap
        plan.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(plan)

        return plan

    async def add_vocabulary_progress(
        self,
        user_id: int,
        words_learned: int,
    ) -> LearningPlan:
        """Добавить прогресс по словарному запасу.

        Args:
            user_id: ID пользователя
            words_learned: Количество новых слов

        Returns:
            Обновленный LearningPlan
        """
        plan = await self.get_or_create_plan(user_id)

        roadmap = plan.roadmap or {}

        # Update milestone
        self._update_milestone(roadmap, "vocabulary", increment=words_learned)

        plan.roadmap = roadmap
        plan.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(plan)

        return plan

    def get_goal(self, plan: LearningPlan) -> Optional[str]:
        """Получить цель из плана."""
        if not plan.roadmap:
            return None
        return plan.roadmap.get("goal")

    def get_focus_areas(self, plan: LearningPlan) -> list[str]:
        """Получить области фокуса."""
        if not plan.roadmap:
            return []
        areas = plan.roadmap.get("focus_areas", [])
        return [a.get("area", "") for a in areas if isinstance(a, dict)]

    def get_preferred_mode(self, plan: LearningPlan) -> str:
        """Получить предпочтительный режим."""
        if not plan.roadmap:
            return "free_conversation"
        return plan.roadmap.get("preferred_mode", "free_conversation")

    def get_last_assessment_date(self, plan: LearningPlan) -> Optional[datetime]:
        """Получить дату последнего assessment."""
        if not plan.roadmap:
            return None
        last_assessment = plan.roadmap.get("last_assessment")
        if last_assessment:
            return datetime.fromisoformat(last_assessment)
        return None

    def get_session_count(self, plan: LearningPlan) -> int:
        """Получить количество завершённых сессий."""
        if not plan.roadmap:
            return 0
        return plan.roadmap.get("sessions_completed", 0)

    def get_recommended_vocabulary(self, plan: LearningPlan) -> list[str]:
        """Получить рекомендованный словарный запас."""
        if not plan.roadmap:
            return []
        return plan.roadmap.get("recommended_vocabulary", [])

    def _match_goal_template(self, goal_text: str) -> Optional[GoalTemplate]:
        """Найти подходящий шаблон для цели."""
        goal_lower = goal_text.lower()

        # ML/Data Science
        if any(kw in goal_lower for kw in ["ml", "machine learning", "data science", "data scientist"]):
            return GOAL_TEMPLATES["ml_interview"]

        # Software Engineering
        if any(kw in goal_lower for kw in ["software", "developer", "engineer", "programming"]):
            return GOAL_TEMPLATES["software_interview"]

        # Interview (general tech)
        if any(kw in goal_lower for kw in ["interview", "интервью", "собеседование"]):
            return GOAL_TEMPLATES["ml_interview"]  # Default to ML for now

        # General fluency
        return GOAL_TEMPLATES["general_fluency"]

    def _update_milestone(
        self,
        roadmap: dict,
        milestone_type: str,
        done: bool = False,
        increment: Optional[int] = None,
        **kwargs,
    ):
        """Update milestone in roadmap (handles both setting values and incrementing)."""
        milestones = roadmap.get("milestones", [])
        for milestone in milestones:
            if not (isinstance(milestone, dict) and milestone.get("type") == milestone_type):
                continue

            if done:
                milestone["done"] = True

            # Handle incrementing counters
            if increment is not None:
                field = "progress" if milestone_type == "vocabulary" else "count"
                milestone[field] = milestone.get(field, 0) + increment
                # Auto-complete if target reached
                target = milestone.get("target")
                if target and milestone[field] >= target:
                    milestone["done"] = True

            # Apply other updates
            milestone.update(kwargs)

        roadmap["milestones"] = milestones


async def detect_goal_from_message(message: str) -> Optional[str]:
    """Определить цель из сообщения пользователя.

    Использует fuzzy matching для обработки STT искажений.

    Args:
        message: Сообщение пользователя

    Returns:
        Определённая цель или None
    """
    message_lower = message.lower()

    print(f"[GoalDetect] Analyzing: '{message_lower[:80]}...'")

    # Паттерны для определения цели (расширенные для STT искажений)
    patterns = {
        "ML/Data Science Interview": [
            "ml interview", "machine learning", "data science", "data scientist",
            "ds interview", "ai interview", "neural network", "deep learning",
            # Fuzzy варианты для STT
            "ml", "and ml", "for ml", "in ml",
            "machine", "learning interview",
        ],
        "Software Engineering Interview": [
            "software interview", "developer interview", "engineer interview",
            "coding interview", "tech interview", "programmer",
            "software engineer", "backend", "frontend", "fullstack",
        ],
        "Job Interview": [
            "job interview", "собеседование", "интервью на работу",
            "найти работу", "find a job", "new job", "get a job",
            # Расширенные паттерны для любого interview
            "prepare for interview", "prepare to interview", "prepare interview",
            "want to interview", "going to interview", "have an interview",
            "interview preparation", "interview prep",
        ],
        "IELTS/TOEFL Preparation": [
            "ielts", "toefl", "экзамен", "exam preparation", "english exam",
        ],
        "Business English": [
            "business english", "деловой английский", "бизнес",
            "corporate", "meetings", "presentations",
        ],
        "General Fluency": [
            "fluency", "improve english", "улучшить английский",
            "practice speaking", "разговорный", "speak better",
            "improve my english", "learn english",
        ],
    }

    # Сначала ищем точные совпадения
    for goal, keywords in patterns.items():
        if any(kw in message_lower for kw in keywords):
            print(f"[GoalDetect] ✓ Matched goal: {goal}")
            return goal

    # Fallback: если есть слово "interview" - это Job Interview
    if "interview" in message_lower:
        print(f"[GoalDetect] ✓ Fallback match: Job Interview (contains 'interview')")
        return "Job Interview"

    print(f"[GoalDetect] ✗ No goal detected")
    return None
