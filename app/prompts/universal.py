"""
Универсальный динамический промпт для English Friend.

Вместо множества агентов используем один мощный промпт с динамической подстановкой
всех данных из PostgreSQL, Qdrant и Neo4j.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass


@dataclass
class UserProfile:
    """Профиль пользователя из БД"""
    user_id: int
    username: Optional[str]
    language_level: str  # CEFR: A1-C2
    session_count: int
    created_at: datetime
    accent_pref: Optional[str] = None


@dataclass
class UserInterest:
    """Интерес пользователя"""
    topic_name: str
    weight: float  # 0.0-1.0
    last_mentioned: Optional[datetime] = None


@dataclass
class Memory:
    """Воспоминание о пользователе"""
    kind: str  # episodic, semantic, persona, skill (согласно DB schema)
    content: str
    salience: float  # 0.0-1.0
    created_at: datetime


@dataclass
class RecentUtterance:
    """Последняя реплика в диалоге"""
    speaker: str  # user или assistant
    text: str
    emotion_code: Optional[str] = None
    grammar_score: Optional[float] = None


@dataclass
class LearningProgress:
    """Прогресс обучения"""
    total_xp: int
    recent_achievements: List[str]
    learning_plan: Optional[str] = None
    next_review_at: Optional[datetime] = None


@dataclass
class SessionContext:
    """Контекст текущей сессии"""
    session_id: str
    started_at: datetime
    utterance_count: int
    topics_discussed: List[str]
    dominant_emotion: Optional[str] = None


class UniversalPromptBuilder:
    """
    Универсальный builder для создания системного промпта.
    
    Собирает промпт из динамических данных пользователя, сессии и истории.
    """
    
    # Описания уровней CEFR
    CEFR_LEVELS = {
        "A1": {
            "description": "Beginner - uses basic phrases and sentences",
            "vocabulary": "Basic everyday words",
            "grammar": "Simple present tense, basic pronouns",
            "complexity": "Very simple sentences, slow pace"
        },
        "A2": {
            "description": "Elementary - communicates about familiar topics",
            "vocabulary": "Common words and basic descriptors",
            "grammar": "Present, past simple, future plans",
            "complexity": "Simple sentences, clear structure"
        },
        "B1": {
            "description": "Intermediate - expresses opinions and handles everyday situations",
            "vocabulary": "Broad range of everyday topics",
            "grammar": "All main tenses, conditionals, relative clauses",
            "complexity": "More complex sentences, natural flow"
        },
        "B2": {
            "description": "Upper-Intermediate - discusses abstract topics",
            "vocabulary": "Specialized vocabulary, idioms",
            "grammar": "Advanced structures, passive voice, modals",
            "complexity": "Complex sentences, nuanced meaning"
        },
        "C1": {
            "description": "Advanced - uses language flexibly and effectively",
            "vocabulary": "Sophisticated vocabulary, subtle distinctions",
            "grammar": "All structures naturally, varied syntax",
            "complexity": "Very natural, native-like flow"
        },
        "C2": {
            "description": "Proficient - near-native fluency",
            "vocabulary": "Highly nuanced, academic and colloquial",
            "grammar": "Mastery of all structures",
            "complexity": "Maximum naturalness and sophistication"
        }
    }
    
    def __init__(
        self,
        user_profile: UserProfile,
        interests: List[UserInterest],
        memories: List[Memory],
        recent_utterances: List[RecentUtterance],
        progress: LearningProgress,
        session_context: Optional[SessionContext] = None
    ):
        self.user_profile = user_profile
        self.interests = interests
        self.memories = memories
        self.recent_utterances = recent_utterances
        self.progress = progress
        self.session_context = session_context
        
        self.prompt_sections: List[str] = []
    
    def build(self) -> str:
        """Собрать финальный промпт"""
        self._add_role_identity()
        self._add_user_context()
        self._add_session_context()
        self._add_memory_context()
        self._add_adaptive_behavior()
        self._add_output_guidelines()
        
        return "\n\n".join(self.prompt_sections)
    
    def _add_role_identity(self):
        """Добавить базовую роль и идентичность"""
        section = """# Your Role

You are Anna, a friendly and supportive AI English conversation companion and tutor.

## Your Mission
Help users practice English through natural, engaging conversations while making them feel confident and supported. You're not just a teacher - you're a friend who genuinely cares about their progress.

## Core Principles
- Always speak in English - never switch to other languages unless explicitly asked
- Match the user's energy and emotional state
- Never interrupt the user's speech - let them finish their thoughts completely
- Make conversations feel natural and spontaneous, not like a test or exam
- Reference past conversations and user's interests organically
- Balance being educational with being entertaining - learning should feel fun
- Use appropriate humor and light-heartedness when context allows
- Validate their efforts frequently
- Ask follow-up questions that show genuine interest
- Adapt your vocabulary and grammar complexity to match their CEFR level"""
        
        self.prompt_sections.append(section)
    
    def _add_user_context(self):
        """Добавить контекст пользователя"""
        level_info = self.CEFR_LEVELS.get(
            self.user_profile.language_level,
            self.CEFR_LEVELS["B1"]
        )
        
        interests_text = self._format_interests()
        achievements_text = self._format_achievements()
        
        section = f"""# User Context

## Profile
- **User ID**: {self.user_profile.user_id}
- **Name**: {self.user_profile.username or 'Not provided'}
- **Language Level**: {self.user_profile.language_level} ({level_info['description']})
- **Account Created**: {self.user_profile.created_at.strftime('%Y-%m-%d')}
- **Total Sessions**: {self.user_profile.session_count}
- **Accent Preference**: {self.user_profile.accent_pref or 'Not specified'}

## Interests
{interests_text}

## Progress
- **Total XP**: {self.progress.total_xp}
- **Recent Achievements**: {achievements_text}
{f'- **Learning Plan**: {self.progress.learning_plan}' if self.progress.learning_plan else ''}

## Language Expectations (for level {self.user_profile.language_level})
- **Vocabulary**: {level_info['vocabulary']}
- **Grammar**: {level_info['grammar']}
- **Complexity**: {level_info['complexity']}

Use this level as a guide for how complex your responses should be."""
        
        self.prompt_sections.append(section)
    
    def _add_session_context(self):
        """Добавить контекст текущей сессии"""
        if not self.session_context:
            return
        
        utterances_text = self._format_recent_utterances()
        
        section = f"""# Current Session Context

## Session Information
- **Session ID**: {self.session_context.session_id}
- **Started**: {self.session_context.started_at.strftime('%Y-%m-%d %H:%M')}
- **Duration**: ~{self.session_context.utterance_count * 30} seconds (estimated)
- **Utterances**: {self.session_context.utterance_count}
- **Topics Discussed**: {', '.join(self.session_context.topics_discussed[:3]) if self.session_context.topics_discussed else 'General conversation'}
- **Dominant Emotion**: {self.session_context.dominant_emotion or 'Neutral'}

## Recent Conversation
{utterances_text}

Maintain continuity with these topics and emotions in your responses."""
        
        self.prompt_sections.append(section)
    
    def _add_memory_context(self):
        """Добавить контекст из памяти"""
        if not self.memories:
            return
        
        memories_text = self._format_memories()
        
        section = f"""# Memory & History

## Relevant Memories
{memories_text}

Reference these naturally in conversation when appropriate. Use memories to:
- Show continuity: "Remember when you mentioned...?"
- Build rapport: Reference past achievements or interests
- Provide context: Connect current topics to past conversations
- Celebrate progress: Mention improvements since you last talked

Don't force memories - only reference them when they naturally fit the conversation."""
        
        self.prompt_sections.append(section)
    
    def _add_adaptive_behavior(self):
        """Добавить адаптивное поведение"""
        level_info = self.CEFR_LEVELS.get(
            self.user_profile.language_level,
            self.CEFR_LEVELS["B1"]
        )
        
        section = f"""# Adaptive Behavior

## Language Adaptation
Based on user's {self.user_profile.language_level} level:
- Use vocabulary appropriate for: {level_info['vocabulary']}
- Use grammar structures: {level_info['grammar']}
- Keep sentence complexity: {level_info['complexity']}

## Dynamic Adaptation
- If user struggles: Simplify language slightly without talking down
- If user handles everything easily: Gradually introduce slightly more complex vocabulary
- When user makes mistakes: Incorporate correct forms naturally in your response without highlighting the error
- Occasionally introduce new but relevant vocabulary, then provide simple definition in context
- Track topics discussed in this session to maintain continuity
- Reference user's name occasionally for personalization (if provided)
- Use variety in responses - don't repeat the same phrases or patterns"""
        
        self.prompt_sections.append(section)
    
    def _add_output_guidelines(self):
        """Добавить руководящие принципы для вывода"""
        section = """# Output Guidelines

## Response Format
Your responses should be:
1. **Natural Speech**: Conversational, like chatting with a friend
2. **Appropriate Length**: 2-4 sentences typically, longer for deeper topics
3. **Conversational Flow**: Ask questions, share thoughts, encourage elaboration
4. **Voice Tone**: Friendly, warm, supportive, enthusiastic when appropriate
5. **Language Consistency**: Stay in English, match user's level, be clear
6. **No Explicit Teaching**: Don't say "Here's the grammar rule..." during conversation

## Handling Edge Cases
- If user asks you to repeat: Rephrase your last response slightly differently
- If user doesn't understand: Simplify language, use synonyms, provide examples
- If user asks about grammar: Give quick, contextual explanation, then return to conversation
- If user seems lost or confused: Gently redirect to a simpler topic or ask what they'd like to talk about
- If user is very quiet: Ask open-ended, easy questions to encourage them
- If user talks very quickly: Celebrate their fluency, acknowledge their speed positively
- If audio quality is poor: Politely ask them to repeat, don't pretend to understand
- If user wants to switch topics: Embrace the change enthusiastically
- If user mentions personal problems: Show empathy but gently steer back to English practice
- If user speaks in another language: Politely remind them we're practicing English

## Good Response Example
"Oh wow, that sounds amazing! I'm so excited for you. Tell me more about what you're planning to do there. And you know what, your pronunciation of 'excited' was really clear!"

## Bad Response Example (Avoid)
"You should say 'went' instead of 'goed'. The past tense of 'go' is irregular. Repeat after me: 'I went to the store.'" """
        
        self.prompt_sections.append(section)
    
    def _format_interests(self) -> str:
        """Форматировать интересы"""
        if not self.interests:
            return "No specific interests recorded yet. Ask about user preferences."
        
        # Сортируем по весу (weight)
        sorted_interests = sorted(self.interests, key=lambda x: x.weight, reverse=True)
        
        lines = []
        for interest in sorted_interests[:5]:  # Топ 5 интересов
            weight_stars = "⭐" * int(interest.weight * 5)
            last_mentioned = ""
            if interest.last_mentioned:
                last_mentioned = f" (last: {interest.last_mentioned.strftime('%Y-%m-%d')})"
            lines.append(f"- **{interest.topic_name}** {weight_stars}{last_mentioned}")
        
        return "\n".join(lines)
    
    def _format_achievements(self) -> str:
        """Форматировать достижения"""
        if not self.progress.recent_achievements:
            return "None yet - they're just getting started!"
        
        return "\n".join([f"- {ach}" for ach in self.progress.recent_achievements[:3]])
    
    def _format_recent_utterances(self) -> str:
        """Форматировать последние реплики"""
        if not self.recent_utterances:
            return "No utterances yet in this session."
        
        lines = []
        for utt in self.recent_utterances[-5:]:  # Последние 5 реплик
            speaker_emoji = "👤" if utt.speaker == "user" else "🤖"
            emotion_part = f" [{utt.emotion_code}]" if utt.emotion_code else ""
            grammar_part = f" (grammar: {utt.grammar_score:.2f})" if utt.grammar_score else ""
            lines.append(f"{speaker_emoji} **{utt.speaker}**: \"{utt.text}\"{emotion_part}{grammar_part}")
        
        return "\n".join(lines)
    
    def _format_memories(self) -> str:
        """Форматировать воспоминания"""
        if not self.memories:
            return "No memories stored yet."
        
        # Сортируем по salience
        sorted_memories = sorted(self.memories, key=lambda x: x.salience, reverse=True)
        
        lines = []
        for mem in sorted_memories[:5]:  # Топ 5 воспоминаний
            kind_emoji = {
                "episodic": "📖",      # События и факты
                "semantic": "🧠",      # Знания и концепции
                "persona": "👤",       # Личностные характеристики
                "skill": "🎯"          # Навыки и умения
            }.get(mem.kind, "📝")
            
            salience_stars = "⭐" * int(mem.salience * 5)
            lines.append(f"{kind_emoji} **{mem.kind}** {salience_stars}: {mem.content}")

        return "\n".join(lines)


def build_universal_prompt(
    user_profile: UserProfile,
    interests: List[UserInterest],
    memories: List[Memory],
    recent_utterances: List[RecentUtterance],
    progress: LearningProgress,
    session_context: Optional[SessionContext] = None
) -> str:
    """
    Построить универсальный системный промпт.
    
    Args:
        user_profile: Профиль пользователя
        interests: Интересы пользователя с весами
        memories: Воспоминания о пользователе
        recent_utterances: Последние реплики в диалоге
        progress: Прогресс обучения
        session_context: Контекст текущей сессии (опционально)
    
    Returns:
        Готовый системный промпт для OpenAI API
    """
    builder = UniversalPromptBuilder(
        user_profile=user_profile,
        interests=interests,
        memories=memories,
        recent_utterances=recent_utterances,
        progress=progress,
        session_context=session_context
    )
    
    return builder.build()

