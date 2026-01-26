"""Prompt Template Service with A/B testing support.

Provides:
- Template loading from database
- Jinja2 rendering with state context
- A/B experiment selection
- Usage logging for analytics
"""

import logging
import time
from datetime import datetime
from typing import Optional, Any
from jinja2 import Environment, BaseLoader, TemplateSyntaxError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_models import (
    PromptTemplate,
    ABExperiment,
    SessionPromptLog,
    DimLearningGoal,
)
from app.core.database import get_async_session

logger = logging.getLogger(__name__)


class PromptService:
    """Service for managing prompt templates and A/B testing."""

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self._jinja_env = Environment(loader=BaseLoader())
        # Add custom filters
        self._jinja_env.filters['join'] = lambda x, sep=', ': sep.join(x) if x else ''

    async def get_template(
        self,
        node_type: str,
        user_id: int,
        variant: Optional[str] = None,
    ) -> Optional[PromptTemplate]:
        """Get prompt template with A/B experiment selection.

        Args:
            node_type: Type of node (onboarding, learning_session, session_end)
            user_id: User ID for deterministic A/B assignment
            variant: Force specific variant (bypasses A/B selection)

        Returns:
            PromptTemplate or None if not found
        """
        async with self._get_db() as db:
            # Check for active experiment if no variant forced
            if variant is None:
                experiment = await self._get_active_experiment(db, node_type)
                if experiment:
                    variant = self._select_variant(user_id, experiment.traffic_percent)
                    template_id = (
                        experiment.variant_template_id if variant == "variant"
                        else experiment.control_template_id
                    )
                    if template_id:
                        result = await db.execute(
                            select(PromptTemplate).where(PromptTemplate.id == template_id)
                        )
                        template = result.scalar_one_or_none()
                        if template:
                            return template

            # No experiment or forced variant - get by variant name
            variant = variant or "control"
            result = await db.execute(
                select(PromptTemplate)
                .where(PromptTemplate.node_type == node_type)
                .where(PromptTemplate.variant == variant)
                .where(PromptTemplate.is_active == True)
                .order_by(PromptTemplate.weight.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def render_template(
        self,
        template: PromptTemplate,
        state: dict[str, Any],
    ) -> str:
        """Render template with state context using Jinja2.

        Args:
            template: PromptTemplate with Jinja2 syntax
            state: AgentState dict with context variables

        Returns:
            Rendered prompt string
        """
        try:
            jinja_template = self._jinja_env.from_string(template.template)
            return jinja_template.render(**state)
        except TemplateSyntaxError as e:
            logger.error(f"Template syntax error in {template.name}: {e}")
            # Fallback: return raw template
            return template.template
        except Exception as e:
            logger.error(f"Error rendering template {template.name}: {e}")
            return template.template

    async def get_and_render(
        self,
        node_type: str,
        user_id: int,
        state: dict[str, Any],
        variant: Optional[str] = None,
    ) -> tuple[str, Optional[PromptTemplate]]:
        """Get template and render in one call.

        Args:
            node_type: Type of node
            user_id: User ID for A/B selection
            state: AgentState dict
            variant: Force specific variant

        Returns:
            Tuple of (rendered_prompt, template)
        """
        template = await self.get_template(node_type, user_id, variant)
        if not template:
            logger.warning(f"No template found for node_type={node_type}, variant={variant}")
            return "", None

        rendered = await self.render_template(template, state)
        return rendered, template

    async def log_usage(
        self,
        session_id: str,
        user_id: int,
        node_type: str,
        template: Optional[PromptTemplate],
        variant: str,
        turn_number: Optional[int] = None,
        llm_response: Optional[str] = None,
        parsed_action: Optional[dict] = None,
        parse_success: bool = True,
        latency_ms: Optional[int] = None,
        experiment_id: Optional[str] = None,
    ) -> None:
        """Log prompt usage for A/B analytics.

        Args:
            session_id: Session UUID
            user_id: User ID
            node_type: Node type
            template: PromptTemplate used (or None if fallback)
            variant: Variant name
            turn_number: Turn number in session
            llm_response: Raw LLM response
            parsed_action: Parsed action dict
            parse_success: Whether parsing succeeded
            latency_ms: LLM response time in ms
            experiment_id: A/B experiment ID if applicable
        """
        try:
            async with self._get_db() as db:
                log_entry = SessionPromptLog(
                    session_id=session_id,
                    user_id=user_id,
                    node_type=node_type,
                    prompt_template_id=template.id if template else None,
                    experiment_id=experiment_id,
                    variant=variant,
                    turn_number=turn_number,
                    llm_response=llm_response[:2000] if llm_response else None,
                    parsed_action=parsed_action,
                    parse_success=parse_success,
                    latency_ms=latency_ms,
                )
                db.add(log_entry)
                await db.commit()
        except Exception as e:
            logger.warning(f"Failed to log prompt usage: {e}")

    async def get_learning_goal(self, slug: str) -> Optional[DimLearningGoal]:
        """Get learning goal by slug.

        Args:
            slug: Goal slug (e.g., 'ml_interview', 'general_fluency')

        Returns:
            DimLearningGoal or None
        """
        async with self._get_db() as db:
            result = await db.execute(
                select(DimLearningGoal)
                .where(DimLearningGoal.slug == slug)
                .where(DimLearningGoal.is_active == True)
            )
            return result.scalar_one_or_none()

    async def get_all_learning_goals(self) -> list[DimLearningGoal]:
        """Get all active learning goals ordered by priority.

        Returns:
            List of DimLearningGoal
        """
        async with self._get_db() as db:
            result = await db.execute(
                select(DimLearningGoal)
                .where(DimLearningGoal.is_active == True)
                .order_by(DimLearningGoal.priority)
            )
            return list(result.scalars().all())

    async def match_goal_from_keywords(self, text: str) -> Optional[DimLearningGoal]:
        """Match learning goal from user text using extraction keywords.

        Args:
            text: User message text

        Returns:
            Best matching DimLearningGoal or None
        """
        text_lower = text.lower()
        goals = await self.get_all_learning_goals()

        best_match = None
        best_score = 0

        for goal in goals:
            score = sum(
                1 for keyword in (goal.extraction_keywords or [])
                if keyword.lower() in text_lower
            )
            if score > best_score:
                best_score = score
                best_match = goal

        return best_match if best_score > 0 else None

    async def _get_active_experiment(
        self,
        db: AsyncSession,
        node_type: str,
    ) -> Optional[ABExperiment]:
        """Get active A/B experiment for node type."""
        result = await db.execute(
            select(ABExperiment)
            .where(ABExperiment.node_type == node_type)
            .where(ABExperiment.status == "running")
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _select_variant(self, user_id: int, traffic_percent: int) -> str:
        """Deterministically select variant based on user_id.

        Args:
            user_id: User ID for consistent assignment
            traffic_percent: Percent of traffic to variant (0-100)

        Returns:
            "variant" or "control"
        """
        # Use modulo for deterministic assignment
        return "variant" if (user_id % 100) < traffic_percent else "control"

    def _get_db(self):
        """Get database session (use provided or create new)."""
        if self.db:
            # Use context manager pattern for provided db
            class DBContext:
                def __init__(self, db):
                    self.db = db

                async def __aenter__(self):
                    return self.db

                async def __aexit__(self, *args):
                    pass  # Don't close provided db

            return DBContext(self.db)
        else:
            return get_async_session()()


# Singleton instance for convenience
_prompt_service: Optional[PromptService] = None


def get_prompt_service(db: Optional[AsyncSession] = None) -> PromptService:
    """Get prompt service instance.

    Args:
        db: Optional database session (creates new if not provided)

    Returns:
        PromptService instance
    """
    global _prompt_service
    if db:
        return PromptService(db)
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service
