"""
Скрипт для заполнения базы данных тестовыми данными.
Запускать после создания всех таблиц.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal, init_db
from app.data.test_data import (
    EMOTIONS_DATA, TOPICS_DATA, ACCENTS_DATA, USERS_DATA, SESSIONS_DATA,
    UTTERANCES_DATA, FEEDBACK_DATA, CORRECTIONS_DATA, INTERESTS_DATA,
    MEMORIES_DATA, LEARNING_PLANS_DATA, XP_EVENTS_DATA, EMOTIONAL_LOGS_DATA
)
from app.models.enums_and_dimensions import DimEmotion, DimTopic, DimAccent
from app.models.core_tables import User, Session, Utterance, Feedback, Correction
from app.models.extended_tables import UserInterest, Memory, LearningPlan, XPEvent, EmotionalStateLog
from app.models.enums_and_dimensions import CEFRLevel, MemoryKind, SessionStatus
from datetime import datetime
import uuid

async def create_test_data():
    """Создать тестовые данные в базе"""
    
    print("🚀 Начинаем заполнение базы данных тестовыми данными...")
    
    # Инициализируем БД
    await init_db()
    print("✅ База данных инициализирована")
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Создаем справочники
            print("📚 Создаем справочники...")
            
            # Эмоции
            for emotion_data in EMOTIONS_DATA:
                emotion = DimEmotion(**emotion_data)
                session.add(emotion)
            print(f"✅ Создано {len(EMOTIONS_DATA)} эмоций")
            
            # Темы (сначала основные, потом подтемы)
            main_topics = [t for t in TOPICS_DATA if t["parent_id"] is None]
            sub_topics = [t for t in TOPICS_DATA if t["parent_id"] is not None]
            
            # Создаем основные темы
            topic_id_map = {}
            for topic_data in main_topics:
                topic = DimTopic(
                    slug=topic_data["slug"],
                    display_name=topic_data["display_name"],
                    parent_id=None
                )
                session.add(topic)
                await session.flush()  # Получаем ID
                topic_id_map[topic_data["slug"]] = topic.id
            
            # Создаем подтемы
            for topic_data in sub_topics:
                parent_id = topic_id_map.get(topic_data["parent_id"])
                topic = DimTopic(
                    slug=topic_data["slug"],
                    display_name=topic_data["display_name"],
                    parent_id=parent_id
                )
                session.add(topic)
            print(f"✅ Создано {len(TOPICS_DATA)} тем")
            
            # Акценты
            for accent_data in ACCENTS_DATA:
                accent = DimAccent(**accent_data)
                session.add(accent)
            print(f"✅ Создано {len(ACCENTS_DATA)} акцентов")
            
            await session.commit()
            print("✅ Справочники сохранены")
            
            # 2. Создаем пользователей
            print("👥 Создаем пользователей...")
            user_id_map = {}
            for user_data in USERS_DATA:
                user = User(
                    telegram_id=user_data["telegram_id"],
                    username=user_data["username"],
                    language_level=user_data["language_level"],
                    accent_pref=user_data["accent_pref"]
                )
                session.add(user)
                await session.flush()
                user_id_map[user_data["telegram_id"]] = user.id
            print(f"✅ Создано {len(USERS_DATA)} пользователей")
            
            # 3. Создаем сессии
            print("🎯 Создаем сессии...")
            session_id_map = {}
            for i, session_data in enumerate(SESSIONS_DATA):
                session_obj = Session(
                    user_id=session_data["user_id"],
                    lang_code=session_data["lang_code"],
                    topics_detected=session_data["topics_detected"],
                    emotion_detected=session_data["emotion_detected"],
                    grammar_score=session_data["grammar_score"],
                    pronunciation_score=session_data["pronunciation_score"]
                )
                session.add(session_obj)
                await session.flush()
                session_id_map[f"session_{i+1}"] = session_obj.id
            print(f"✅ Создано {len(SESSIONS_DATA)} сессий")
            
            # 4. Создаем реплики
            print("💬 Создаем реплики...")
            for utterance_data in UTTERANCES_DATA:
                utterance = Utterance(
                    session_id=session_id_map[utterance_data["session_id"]],
                    speaker=utterance_data["speaker"],
                    t_start_ms=utterance_data["t_start_ms"],
                    t_end_ms=utterance_data["t_end_ms"],
                    text=utterance_data["text"],
                    emotion_code=utterance_data["emotion_code"],
                    emotion_score=utterance_data["emotion_score"],
                    grammar_score=utterance_data["grammar_score"],
                    pronunciation_score=utterance_data["pronunciation_score"]
                )
                session.add(utterance)
            print(f"✅ Создано {len(UTTERANCES_DATA)} реплик")
            
            # 5. Создаем обратную связь
            print("📝 Создаем обратную связь...")
            for feedback_data in FEEDBACK_DATA:
                feedback = Feedback(
                    session_id=session_id_map[feedback_data["session_id"]],
                    overall_grammar=feedback_data["overall_grammar"],
                    overall_pronunciation=feedback_data["overall_pronunciation"],
                    summary_md=feedback_data["summary_md"],
                    tips_md=feedback_data["tips_md"],
                    grammar_tips=feedback_data["grammar_tips"],
                    pronunciation_tips=feedback_data["pronunciation_tips"]
                )
                session.add(feedback)
            print(f"✅ Создано {len(FEEDBACK_DATA)} записей обратной связи")
            
            # 6. Создаем исправления
            print("✏️ Создаем исправления...")
            for correction_data in CORRECTIONS_DATA:
                correction = Correction(
                    session_id=session_id_map[correction_data["session_id"]],
                    user_text=correction_data["user_text"],
                    corrected_text=correction_data["corrected_text"],
                    rule_tag=correction_data["rule_tag"],
                    explanation_md=correction_data["explanation_md"]
                )
                session.add(correction)
            print(f"✅ Создано {len(CORRECTIONS_DATA)} исправлений")
            
            # 7. Создаем интересы
            print("🎯 Создаем интересы...")
            for interest_data in INTERESTS_DATA:
                # Находим topic_id по slug
                topic_result = await session.execute(
                    session.query(DimTopic).filter(DimTopic.slug == interest_data["topic_id"])
                )
                topic = topic_result.scalar_one_or_none()
                if topic:
                    interest = UserInterest(
                        user_id=interest_data["user_id"],
                        topic_id=topic.id,
                        weight=interest_data["weight"]
                    )
                    session.add(interest)
            print(f"✅ Создано {len(INTERESTS_DATA)} интересов")
            
            # 8. Создаем память
            print("🧠 Создаем память...")
            for memory_data in MEMORIES_DATA:
                memory = Memory(
                    user_id=memory_data["user_id"],
                    session_id=session_id_map.get(memory_data["session_id"]),
                    kind=memory_data["kind"],
                    content=memory_data["content"],
                    metadata=memory_data["metadata"]
                )
                session.add(memory)
            print(f"✅ Создано {len(MEMORIES_DATA)} записей памяти")
            
            # 9. Создаем планы обучения
            print("📚 Создаем планы обучения...")
            for plan_data in LEARNING_PLANS_DATA:
                plan = LearningPlan(
                    user_id=plan_data["user_id"],
                    target_level=plan_data["target_level"],
                    current_level=plan_data["current_level"],
                    topics=plan_data["topics"],
                    milestones=plan_data["milestones"]
                )
                session.add(plan)
            print(f"✅ Создано {len(LEARNING_PLANS_DATA)} планов обучения")
            
            # 10. Создаем события XP
            print("⭐ Создаем события XP...")
            for event_data in XP_EVENTS_DATA:
                event = XPEvent(
                    user_id=event_data["user_id"],
                    session_id=session_id_map.get(event_data["session_id"]),
                    event_type=event_data["event_type"],
                    xp_delta=event_data["xp_delta"],
                    metadata=event_data["metadata"]
                )
                session.add(event)
            print(f"✅ Создано {len(XP_EVENTS_DATA)} событий XP")
            
            # 11. Создаем лог эмоций
            print("😊 Создаем лог эмоций...")
            for log_data in EMOTIONAL_LOGS_DATA:
                log = EmotionalStateLog(
                    user_id=log_data["user_id"],
                    session_id=session_id_map.get(log_data["session_id"]),
                    emotion_code=log_data["emotion_code"],
                    intensity=log_data["intensity"],
                    context=log_data["context"]
                )
                session.add(log)
            print(f"✅ Создано {len(EMOTIONAL_LOGS_DATA)} записей эмоций")
            
            # Сохраняем все изменения
            await session.commit()
            print("🎉 Все тестовые данные успешно созданы!")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при создании тестовых данных: {e}")
            raise

async def main():
    """Главная функция"""
    try:
        await create_test_data()
        print("\n✅ Заполнение базы данных завершено успешно!")
        print("🔗 Теперь можно тестировать API endpoints:")
        print("   - http://localhost:8000/docs - Swagger UI")
        print("   - http://localhost:8000/api/v1/status - Статус API")
        print("   - http://localhost:8000/api/v1/dimensions/emotions/ - Эмоции")
        print("   - http://localhost:8000/api/v1/users/ - Пользователи")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
