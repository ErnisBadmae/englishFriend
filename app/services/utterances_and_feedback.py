from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from app.models.core_tables import Utterance, Feedback, Correction
from app.schemas.extended_schemas import UtteranceCreate
from app.schemas.additional_schemas import FeedbackCreate, FeedbackUpdate, CorrectionCreate

class UtteranceService:
    """Сервис для работы с репликами"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_utterance(self, utterance_data: UtteranceCreate) -> Utterance:
        """Создать новую реплику"""
        db_utterance = Utterance(
            session_id=utterance_data.session_id,
            speaker=utterance_data.speaker,
            t_start_ms=utterance_data.t_start_ms,
            t_end_ms=utterance_data.t_end_ms,
            text=utterance_data.text,
            phonemes=utterance_data.phonemes,
            topics=utterance_data.topics,
            emotion_code=utterance_data.emotion_code,
            emotion_score=utterance_data.emotion_score,
            grammar_score=utterance_data.grammar_score,
            pronunciation_score=utterance_data.pronunciation_score
        )
        self.db.add(db_utterance)
        await self.db.commit()
        await self.db.refresh(db_utterance)
        return db_utterance

    async def get_utterance(self, utterance_id: str) -> Optional[Utterance]:
        """Получить реплику по ID"""
        result = await self.db.execute(
            select(Utterance).where(Utterance.id == utterance_id)
        )
        return result.scalar_one_or_none()

    async def get_session_utterances(self, session_id: str, skip: int = 0, limit: int = 100) -> List[Utterance]:
        """Получить реплики сессии"""
        result = await self.db.execute(
            select(Utterance)
            .where(Utterance.session_id == session_id)
            .order_by(Utterance.t_start_ms)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_utterances(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Utterance]:
        """Получить реплики пользователя через сессии"""
        result = await self.db.execute(
            select(Utterance)
            .join(Utterance.session)
            .where(Utterance.session.has(user_id=user_id))
            .order_by(Utterance.t_start_ms.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

class FeedbackService:
    """Сервис для работы с обратной связью"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_feedback(self, feedback_data: FeedbackCreate) -> Feedback:
        """Создать обратную связь по сессии"""
        db_feedback = Feedback(
            session_id=feedback_data.session_id,
            overall_grammar=feedback_data.overall_grammar,
            overall_pronunciation=feedback_data.overall_pronunciation,
            summary_md=feedback_data.summary_md,
            tips_md=feedback_data.tips_md,
            corrected_phrases=feedback_data.corrected_phrases,
            grammar_tips=feedback_data.grammar_tips,
            pronunciation_tips=feedback_data.pronunciation_tips,
            vocabulary_suggestions=feedback_data.vocabulary_suggestions
        )
        self.db.add(db_feedback)
        await self.db.commit()
        await self.db.refresh(db_feedback)
        return db_feedback

    async def get_feedback(self, session_id: str) -> Optional[Feedback]:
        """Получить обратную связь по сессии"""
        result = await self.db.execute(
            select(Feedback).where(Feedback.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def update_feedback(self, session_id: str, feedback_data: FeedbackUpdate) -> Optional[Feedback]:
        """Обновить обратную связь"""
        stmt = (
            update(Feedback)
            .where(Feedback.session_id == session_id)
            .values(
                overall_grammar=feedback_data.overall_grammar,
                overall_pronunciation=feedback_data.overall_pronunciation,
                summary_md=feedback_data.summary_md,
                tips_md=feedback_data.tips_md,
                corrected_phrases=feedback_data.corrected_phrases,
                grammar_tips=feedback_data.grammar_tips,
                pronunciation_tips=feedback_data.pronunciation_tips,
                vocabulary_suggestions=feedback_data.vocabulary_suggestions
            )
            .returning(Feedback)
        )
        result = await self.db.execute(stmt)
        updated_feedback = result.scalar_one_or_none()
        if updated_feedback:
            await self.db.commit()
            await self.db.refresh(updated_feedback)
        return updated_feedback

class CorrectionService:
    """Сервис для работы с исправлениями"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_correction(self, correction_data: CorrectionCreate) -> Correction:
        """Создать исправление"""
        db_correction = Correction(
            session_id=correction_data.session_id,
            utterance_id=correction_data.utterance_id,
            user_text=correction_data.user_text,
            corrected_text=correction_data.corrected_text,
            rule_tag=correction_data.rule_tag,
            explanation_md=correction_data.explanation_md
        )
        self.db.add(db_correction)
        await self.db.commit()
        await self.db.refresh(db_correction)
        return db_correction

    async def get_correction(self, correction_id: str) -> Optional[Correction]:
        """Получить исправление по ID"""
        result = await self.db.execute(
            select(Correction).where(Correction.id == correction_id)
        )
        return result.scalar_one_or_none()

    async def get_session_corrections(self, session_id: str, skip: int = 0, limit: int = 100) -> List[Correction]:
        """Получить исправления сессии"""
        result = await self.db.execute(
            select(Correction)
            .where(Correction.session_id == session_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_corrections(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Correction]:
        """Получить исправления пользователя через сессии"""
        result = await self.db.execute(
            select(Correction)
            .join(Correction.session)
            .where(Correction.session.has(user_id=user_id))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
