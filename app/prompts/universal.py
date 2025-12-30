"""
Универсальный промпт для English Friend.
Динамически подставляет контекст пользователя, сессии, прогресс и память.
"""

import enum
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass


class PromptMode(str, enum.Enum):
    """Режимы промпта для оптимизации токенов"""
    FULL = "full"        # ~2,300 токенов - начало сессии
    COMPACT = "compact"  # ~1,500 токенов - продолжение диалога


@dataclass
class UserProfile:
    """Профиль пользователя"""
    id: int
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    language_level: Optional[str] = None
    last_session_date: Optional[datetime] = None
    
    def __str__(self):
        level = f" ({self.language_level})" if self.language_level else ""
        return f"{self.username or 'User'}#{self.id}{level}"


@dataclass
class UserInterest:
    """Интерес пользователя"""
    topic: str
    salience: float = 0.0
    
    def __str__(self):
        return f"{self.topic} (важность: {self.salience:.2f})"


@dataclass
class Memory:
    """Воспоминание о пользователе"""
    kind: str  # episodic, semantic, persona, skill
    content: str
    salience: float = 0.0
    
    def __str__(self):
        return f"[{self.kind}] {self.content}"


@dataclass
class RecentUtterance:
    """Недавняя реплика"""
    text: str
    speaker: str
    timestamp: datetime


@dataclass
class LearningProgress:
    """Прогресс обучения"""
    total_xp: int = 0
    current_level: Optional[str] = None
    achievements: List[str] = None
    
    def __init__(self, total_xp=0, current_level=None, achievements=None):
        self.total_xp = total_xp
        self.current_level = current_level
        self.achievements = achievements or []


@dataclass
class SessionContext:
    """Контекст текущей сессии"""
    session_id: str
    utterance_count: int = 0
    duration_seconds: int = 0
    started_at: Optional[datetime] = None


class UniversalPromptBuilder:
    """Строитель универсального промпта"""
    
    def __init__(
        self,
        user_profile: Optional[UserProfile] = None,
        interests: Optional[List[UserInterest]] = None,
        memories: Optional[List[Memory]] = None,
        recent_utterances: Optional[List[RecentUtterance]] = None,
        progress: Optional[LearningProgress] = None,
        session_context: Optional[SessionContext] = None,
        mode: PromptMode = PromptMode.FULL
    ):
        self.user_profile = user_profile
        self.interests = interests or []
        self.memories = memories or []
        self.recent_utterances = recent_utterances or []
        self.progress = progress or LearningProgress()
        self.session_context = session_context
        self.mode = mode
        self.prompt_sections = []
    
    def build(self) -> str:
        """Собрать финальный промпт"""
        if self.mode == PromptMode.FULL:
            return self._build_full()
        else:
            return self._build_compact()
    
    def _build_full(self) -> str:
        """Построить полный промпт (~2,300 токенов)"""
        self._add_role_identity()
        self._add_user_context()
        self._add_interests()
        self._add_memories()
        self._add_recent_dialogue()
        self._add_progress()
        self._add_behavior_guidelines()
        return "\n\n".join(self.prompt_sections)
    
    def _build_compact(self) -> str:
        """Построить компактный промпт (~1,500 токенов)"""
        self._add_role_identity_compact()
        self._add_user_context_compact()
        self._add_session_context_compact()
        self._add_behavior_compact()
        return "\n\n".join(self.prompt_sections)
    
    def _add_role_identity(self):
        """Роль и идентичность"""
        text = """You are a friendly AI English tutor named "English Friend".
Your goal is to help users practice English naturally through conversation.
Be encouraging, patient, and supportive."""
        self.prompt_sections.append(text)
    
    def _add_role_identity_compact(self):
        """Роль (компактная версия)"""
        self.prompt_sections.append("You are English Friend, a friendly AI English tutor.")
    
    def _add_user_context(self):
        """Контекст пользователя"""
        if not self.user_profile:
            return
        
        lines = [f"User: {self.user_profile}"]
        if self.user_profile.language_level:
            lines.append(f"Level: {self.user_profile.language_level}")
        if self.user_profile.last_session_date:
            days_ago = (datetime.now() - self.user_profile.last_session_date).days
            lines.append(f"Last session: {days_ago} days ago")
        
        self.prompt_sections.append("User Context:\n" + "\n".join(lines))
    
    def _add_user_context_compact(self):
        """Контекст пользователя (компактный)"""
        if self.user_profile:
            level = f" ({self.user_profile.language_level})" if self.user_profile.language_level else ""
            self.prompt_sections.append(f"User: {self.user_profile.username or 'User'}{level}")
    
    def _add_session_context_compact(self):
        """Контекст сессии (компактный)"""
        if self.session_context:
            self.prompt_sections.append(
                f"Session: {self.session_context.utterance_count} exchanges"
            )
    
    def _add_interests(self):
        """Интересы пользователя"""
        if not self.interests:
            return
        
        lines = ["User Interests:"]
        for interest in self.interests:
            lines.append(f"- {interest}")
        
        self.prompt_sections.append("\n".join(lines))
    
    def _add_memories(self):
        """Память о пользователе"""
        if not self.memories:
            return
        
        # Группируем по типу
        by_kind = {}
        for mem in self.memories:
            if mem.kind not in by_kind:
                by_kind[mem.kind] = []
            by_kind[mem.kind].append(mem)
        
        lines = ["Memories about the user:"]
        for kind, mems in by_kind.items():
            lines.append(f"\n{kind.capitalize()}:")
            for m in mems[:3]:  # Берём топ-3 по salience
                lines.append(f"- {m}")
        
        self.prompt_sections.append("\n".join(lines))
    
    def _add_recent_dialogue(self):
        """Недавний диалог"""
        if not self.recent_utterances:
            return
        
        lines = ["Recent dialogue:"]
        for utt in self.recent_utterances[-6:]:  # Последние 6 реплик
            lines.append(f"{utt.speaker}: {utt.text}")
        
        self.prompt_sections.append("\n".join(lines))
    
    def _add_progress(self):
        """Прогресс обучения"""
        lines = [f"Learning Progress: {self.progress.total_xp} XP"]
        if self.progress.current_level:
            lines.append(f"Level: {self.progress.current_level}")
        if self.progress.achievements:
            lines.append(f"Achievements: {', '.join(self.progress.achievements[:3])}")
        
        self.prompt_sections.append("\n".join(lines))
    
    def _add_behavior_guidelines(self):
        """Руководящие принципы поведения"""
        text = """Guidelines:
- Respond naturally and conversationally
- Correct grammar mistakes gently
- Encourage the user to practice
- Ask follow-up questions to keep the conversation going"""
        self.prompt_sections.append(text)
    
    def _add_behavior_compact(self):
        """Руководящие принципы (компактные)"""
        self.prompt_sections.append("Be conversational, encouraging, and gently correct mistakes.")


def determine_prompt_mode(
    session_context: Optional[SessionContext],
    user_profile: UserProfile
) -> PromptMode:
    """
    Определить режим промпта на основе контекста.
    
    Args:
        session_context: Контекст сессии
        user_profile: Профиль пользователя
        
    Returns:
        PromptMode: FULL или COMPACT
    """
    # Если сессия новая или нет реплик - полный промпт
    if not session_context or session_context.utterance_count == 0:
        return PromptMode.FULL
    
    # Если прошло больше недели - полный промпт
    if user_profile.last_session_date:
        days_since = (datetime.now() - user_profile.last_session_date).days
        if days_since > 7:
            return PromptMode.FULL
    
    # Иначе - компактный
    return PromptMode.COMPACT


def build_universal_prompt(
    user_profile: Optional[UserProfile] = None,
    interests: Optional[List[UserInterest]] = None,
    memories: Optional[List[Memory]] = None,
    recent_utterances: Optional[List[RecentUtterance]] = None,
    progress: Optional[LearningProgress] = None,
    session_context: Optional[SessionContext] = None,
    mode: Optional[PromptMode] = None
) -> str:
    """
    Собрать универсальный промпт.
    
    Args:
        user_profile: Профиль пользователя
        interests: Интересы пользователя
        memories: Память о пользователе
        recent_utterances: Недавние реплики
        progress: Прогресс обучения
        session_context: Контекст сессии
        mode: Режим промпта (если None - определяется автоматически)
    
    Returns:
        str: Готовый промпт для LLM
    """
    # Определить режим, если не указан
    if mode is None:
        mode = determine_prompt_mode(session_context, user_profile or UserProfile(id=0))
    
    builder = UniversalPromptBuilder(
        user_profile=user_profile,
        interests=interests,
        memories=memories,
        recent_utterances=recent_utterances,
        progress=progress,
        session_context=session_context,
        mode=mode
    )
    
    return builder.build()

