"""WebSocket API для голосовых диалогов.

Педагогическая архитектура с режимами обучения:
- ASSESSMENT: Оценка уровня
- MOCK_INTERVIEW: Симуляция собеседования
- VOCABULARY_DRILL: Повторение слов через FSRS
- FREE_CONVERSATION: Свободный разговор с коррекцией

Архитектура Vosk + Groq + edge-tts:
- Фронтенд (Telegram Mini App) использует Vosk для STT локально
- Отправляет текст на бэкенд через WebSocket
- Бэкенд генерирует ответ через Groq (Llama-70B)
- Синтезирует речь через edge-tts
- Отправляет аудио обратно

Два эндпоинта:
- /chat: Legacy endpoint с хардкод логикой
- /chat/v2: Новый endpoint на LangGraph state machine
"""

import json
import re
import uuid
import base64
import time
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import (
    voice_sessions_active,
    voice_sessions_total,
    voice_turn_total_seconds,
    voice_llm_latency_seconds,
    voice_tts_latency_seconds,
    voice_messages_total,
    voice_errors_total,
    agent_version_sessions,
    agent_version_errors,
    agent_version_onboarding_complete,
    personaplex_connections_active,
    personaplex_sessions_total,
    personaplex_latency_seconds,
    personaplex_session_duration_seconds,
    personaplex_turns_total,
    personaplex_pedagogical_events,
    personaplex_errors_total,
    personaplex_fallback_total,
)

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.services.database import UserService
from app.schemas.user import UserCreate
from app.services.ai.llm_provider import get_llm_provider
from app.services.ai.tts_service import get_tts_service
from app.services.ai.mentor_prompt import build_mentor_prompt, build_simple_prompt, UserContext
from app.services.ai.learning_mentor_prompt import build_simple_learning_prompt

# Педагогические модули
from app.services.ai.mode_prompts import (
    LearningMode,
    build_mode_prompt,
    get_session_greeting,
)
from app.services.ai.mode_selector import (
    SessionContext,
    select_learning_mode,
    get_focus_area_for_mode,
    parse_user_mode_request,
)
from app.services.learning_plan_service import (
    LearningPlanService,
    detect_goal_from_message,
)
from app.services.ai.vocabulary_service import (
    VocabularyService,
    VocabularyWord,
)
from app.services.gamification import XPService, StreakService
from app.services.gamification.xp_service import XPEventKind

# RAG и память
from app.services.ai.memory_pipeline import create_memory_pipeline, MemoryPipeline

# Post-session обработка и логирование
from app.services.ai.post_session_service import PostSessionService, create_initial_vocabulary_cards
from app.services.data_flow_logger import data_logger

# Voice helpers для упрощения WebSocket логики
from app.api.voice_helpers import (
    handle_goal_setting,
    award_session_gamification,
    rebuild_system_prompt,
    persist_goal_state_if_needed,
    persist_interview_run_if_needed,
    persist_session_evidence_if_needed,
)

# PersonaPlex speech-to-speech
from app.core.config import settings
from app.services.ai.personaplex_provider import PersonaPlexProvider, PersonaPlexConnectionError
from app.services.ai.personaplex_health import check_personaplex_health
from app.services.ai.base import VoiceSession

# LangGraph agent (v1 - original 11-node architecture)
from app.agent import AgentState, AgentPhase, LearningModeEnum
from app.agent.graph import run_agent_turn, initialize_session

# LangGraph agent v2 (simplified 4-node LLM-driven architecture)
from app.agent.graph_v2 import (
    initialize_session_v2,
    run_agent_turn_v2,
    USE_AGENT_V2,
)

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


@router.websocket("/chat")
async def voice_chat(
    websocket: WebSocket,
    user_id: int = Query(..., description="ID пользователя"),
    mode: Optional[str] = Query(None, description="Режим обучения"),
    interview_track: Optional[str] = Query(None, description="ID трека интервью"),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint для голосового чата.

    DEPRECATED: Этот эндпоинт теперь использует LangGraph agent (v2).
    Для обратной совместимости оставлен тот же URL.

    Используйте /chat/v2 для явного вызова LangGraph версии.
    """
    # Redirect to v2 (LangGraph) implementation
    logger.info(f"[Voice] /chat redirecting to v2 (LangGraph) for user {user_id}")
    await voice_chat_v2(websocket, user_id=user_id, mode=mode, interview_track=interview_track, db=db)


@router.websocket("/chat-legacy")
async def voice_chat_legacy(
    websocket: WebSocket,
    user_id: int = Query(..., description="ID пользователя"),
    mode: Optional[str] = Query(None, description="Режим обучения"),
    db: AsyncSession = Depends(get_db),
):
    """
    Legacy WebSocket endpoint с хардкод логикой (без LangGraph).

    Сохранён для отладки и сравнения с v2.
    Для продакшена используйте /chat или /chat/v2.

    Протокол:
    - Client -> Server: {"type": "text", "text": "распознанный текст от Vosk"}
    - Client -> Server: {"type": "set_goal", "goal": "ML interview preparation"}
    - Client -> Server: {"type": "change_mode", "mode": "mock_interview"}
    - Server -> Client: {"type": "connected", "session_id": "...", "mode": "...", "greeting": "..."}
    - Server -> Client: {"type": "transcript", "role": "assistant", "text": "..."}
    - Server -> Client: {"type": "audio", "data": "<base64 MP3>", "format": "mp3"}
    - Server -> Client: {"type": "mode_changed", "mode": "...", "message": "..."}
    - Server -> Client: {"type": "error", "message": "..."}
    """
    await websocket.accept()

    # Metrics: increment active sessions
    voice_sessions_active.inc()
    session_start_time = time.time()
    final_mode = "unknown"  # Will be set after mode selection
    session_status = "disconnected"  # Default, changed on proper end

    try:
        # === INITIALIZATION BLOCK ===

        # Проверяем пользователя (автосоздание если не существует)
        user = None
        try:
            user_service = UserService(db)
            user = await user_service.get_user(user_id)

            # Auto-create user if doesn't exist (fixes FK violation)
            if not user:
                logger.info(f"[Voice] User {user_id} not found, auto-creating...")
                user = await user_service.create_user(UserCreate(
                    telegram_id=user_id,
                    username=f"User_{user_id}",
                    language_level="B1"
                ))
                logger.info(f"[Voice] Auto-created user {user_id}")
        except Exception as e:
            logger.warning(f"Could not fetch/create user from DB: {e}")
            voice_errors_total.labels(stage="db").inc()

        # Инициализируем сервисы
        llm = get_llm_provider()
        tts = get_tts_service()
        learning_plan_service = LearningPlanService(db)
        vocabulary_service = VocabularyService(db)
        memory_pipeline = create_memory_pipeline(db)

        # История диалога для контекста
        conversation_history: list[dict] = []
        turn_count = 0
        session_id = str(uuid.uuid4())

        # === ЗАГРУЖАЕМ КОНТЕКСТ ОБУЧЕНИЯ ===
        learning_plan = None
        due_vocabulary: list = []
        session_context = SessionContext(
            user_id=user_id,
            username=user.username if user else f"Student",
            language_level=user.language_level if user else "B1",
        )

        try:
            # Загружаем план обучения
            learning_plan = await learning_plan_service.get_or_create_plan(user_id)
            session_context.goal = learning_plan_service.get_goal(learning_plan)
            session_context.focus_areas = learning_plan_service.get_focus_areas(learning_plan)
            session_context.preferred_mode = learning_plan_service.get_preferred_mode(learning_plan)
            session_context.last_assessment_date = learning_plan_service.get_last_assessment_date(learning_plan)
            session_context.total_sessions = learning_plan_service.get_session_count(learning_plan)

            # Загружаем слова для повторения
            due_vocabulary = await vocabulary_service.get_due_cards(user_id, limit=10)
            session_context.due_vocabulary_count = len(due_vocabulary)
            session_context.due_vocabulary_words = [card.word for card in due_vocabulary]

            logger.info(f"[Pedagogy] Loaded context: goal={session_context.goal}, "
                  f"due_vocab={session_context.due_vocabulary_count}, "
                  f"sessions={session_context.total_sessions}")
        except Exception as e:
            logger.warning(f"Could not load learning context: {e}")
            voice_errors_total.labels(stage="db").inc()

        # === ОПРЕДЕЛЯЕМ РЕЖИМ СЕССИИ ===
        if mode:
            # Клиент явно указал режим
            try:
                current_mode = LearningMode(mode)
                session_context.requested_mode = current_mode
            except ValueError:
                current_mode = select_learning_mode(session_context)
        else:
            # Автоматический выбор режима
            current_mode = select_learning_mode(session_context)

        focus_area = get_focus_area_for_mode(current_mode, session_context)
        logger.info(f"[Pedagogy] Selected mode: {current_mode.value}, focus: {focus_area}")
        final_mode = current_mode.value  # Track for metrics

        # === СТРОИМ ПРОМПТ ДЛЯ РЕЖИМА ===
        vocabulary_list = ""
        if due_vocabulary:
            vocabulary_list = "\n".join([
                f"- {card.word}: {card.example_sentence or 'practice using this word'}"
                for card in due_vocabulary[:5]
            ])

        # Получаем контекст памяти для персонализации
        memory_section = ""
        try:
            memory_section = await memory_pipeline.format_memory_for_prompt(user_id)
            if memory_section:
                logger.info(f"[RAG] Loaded memory context ({len(memory_section)} chars)")
        except Exception as e:
            logger.warning(f"Could not load memory context: {e}")

        system_prompt = rebuild_system_prompt(
            current_mode=current_mode,
            session_context=session_context,
            focus_area=focus_area,
            vocabulary_list=vocabulary_list,
            memory_section=memory_section,
        )

        # Приветствие для режима
        greeting = get_session_greeting(current_mode, session_context.username)

        # === MESSAGE LOOP ===
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "mode": current_mode.value,
            "greeting": greeting,
            "due_vocabulary_count": session_context.due_vocabulary_count,
            "goal": session_context.goal,
        })

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                # === ОБРАБОТКА УСТАНОВКИ ЦЕЛИ ===
                if message.get("type") == "set_goal":
                    goal_text = message.get("goal", "").strip()
                    if goal_text:
                        try:
                            new_mode, new_prompt = await handle_goal_setting(
                                goal_text=goal_text,
                                user_id=user_id,
                                db=db,
                                learning_plan_service=learning_plan_service,
                                session_context=session_context,
                                websocket=websocket,
                            )
                            if new_mode:
                                current_mode = new_mode
                                final_mode = current_mode.value
                                focus_area = get_focus_area_for_mode(current_mode, session_context)
                            if new_prompt:
                                system_prompt = new_prompt
                        except Exception as e:
                            logger.error(f"Error setting goal: {e}")
                    continue

                # === ОБРАБОТКА СМЕНЫ РЕЖИМА ===
                if message.get("type") == "change_mode":
                    new_mode_str = message.get("mode", "").strip()
                    try:
                        new_mode = LearningMode(new_mode_str)
                        current_mode = new_mode
                        focus_area = get_focus_area_for_mode(current_mode, session_context)

                        system_prompt = rebuild_system_prompt(
                            current_mode=current_mode,
                            session_context=session_context,
                            focus_area=focus_area,
                            vocabulary_list=vocabulary_list,
                            memory_section=memory_section,
                        )

                        greeting = get_session_greeting(current_mode, session_context.username)
                        await websocket.send_json({
                            "type": "mode_changed",
                            "mode": current_mode.value,
                            "greeting": greeting,
                        })
                        final_mode = current_mode.value
                        logger.info(f"[Pedagogy] Mode changed to: {current_mode.value}")
                    except ValueError:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown mode: {new_mode_str}",
                        })
                    continue

                # === ОБРАБОТКА ТЕКСТА ===
                if message.get("type") == "text":
                    user_text = message.get("text", "").strip()
                    if not user_text:
                        continue

                    turn_count += 1
                    turn_start = time.time()  # Metrics: start turn timer
                    voice_messages_total.labels(direction="inbound", type="text").inc()

                    # Первое сообщение: проверяем, не указывает ли цель
                    if turn_count == 1 and not session_context.goal:
                        detected_goal = await detect_goal_from_message(user_text)
                        if detected_goal:
                            try:
                                learning_plan = await learning_plan_service.set_goal(user_id, detected_goal)
                                session_context.goal = detected_goal

                                # Логируем определение цели
                                data_logger.log_goal_detected(
                                    user_id=user_id,
                                    message=user_text[:50],
                                    detected_goal=detected_goal,
                                )
                                data_logger.log_postgres_write(
                                    table="learning_plan",
                                    operation="UPDATE",
                                    data={"goal": detected_goal},
                                    user_id=user_id,
                                )

                                # Создаём начальные карточки из рекомендованного словаря
                                recommended_vocab = learning_plan_service.get_recommended_vocabulary(learning_plan)
                                if recommended_vocab:
                                    cards_created = await create_initial_vocabulary_cards(
                                        db, user_id, detected_goal, recommended_vocab
                                    )
                                    logger.info(f"[Pedagogy] Created {cards_created} initial vocab cards for detected goal")

                                # Перевыбираем режим
                                current_mode = select_learning_mode(session_context)
                                focus_area = get_focus_area_for_mode(current_mode, session_context)

                                system_prompt = rebuild_system_prompt(
                                    current_mode=current_mode,
                                    session_context=session_context,
                                    focus_area=focus_area,
                                    vocabulary_list=vocabulary_list,
                                    memory_section=memory_section,
                                )
                                final_mode = current_mode.value
                                logger.info(f"[Pedagogy] Detected goal: {detected_goal}")
                            except Exception as e:
                                logger.error(f"Error setting detected goal: {e}")

                    # Проверяем запрос на смену режима в тексте
                    requested_mode = parse_user_mode_request(user_text)
                    if requested_mode and requested_mode != current_mode:
                        current_mode = requested_mode
                        focus_area = get_focus_area_for_mode(current_mode, session_context)
                        system_prompt = rebuild_system_prompt(
                            current_mode=current_mode,
                            session_context=session_context,
                            focus_area=focus_area,
                            vocabulary_list=vocabulary_list,
                            memory_section=memory_section,
                        )
                        final_mode = current_mode.value
                        logger.info(f"[Pedagogy] Mode switched by user request: {current_mode.value}")

                    # Отправляем подтверждение получения текста
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "user",
                        "text": user_text,
                    })

                    # Генерируем ответ через LLM
                    try:
                        llm_start = time.time()
                        response_text = await llm.generate(
                            user_message=user_text,
                            system_prompt=system_prompt,
                            conversation_history=conversation_history,
                            max_tokens=250,  # Больше для объяснений и feedback
                        )
                        voice_llm_latency_seconds.labels(mode=current_mode.value).observe(
                            time.time() - llm_start
                        )
                    except Exception as e:
                        voice_errors_total.labels(stage="llm").inc()
                        voice_messages_total.labels(direction="outbound", type="error").inc()
                        await websocket.send_json({
                            "type": "error",
                            "message": f"LLM error: {str(e)}",
                        })
                        continue

                    # Добавляем в историю
                    conversation_history.append({"role": "user", "content": user_text})
                    conversation_history.append({"role": "assistant", "content": response_text})

                    # Логирование (INFO level only, DEBUG removed for noise reduction)
                    logger.info(f"[Turn {turn_count}] Mode: {current_mode.value}")

                    # Ограничиваем историю
                    if len(conversation_history) > 20:
                        conversation_history = conversation_history[-20:]

                    # Отправляем текст ответа
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "assistant",
                        "text": response_text,
                        "mode": current_mode.value,
                        "turn": turn_count,
                    })

                    # Извлекаем и сохраняем vocabulary (асинхронно, не блокируем)
                    try:
                        # Простое извлечение: слова в CAPS (ментор акцентирует внимание)
                        emphasized_words = re.findall(r'\b([A-Z]{2,})\b', response_text)
                        for word in emphasized_words[:3]:  # Максимум 3 слова за ответ
                            await vocabulary_service.add_word(
                                user_id=user_id,
                                word=VocabularyWord(
                                    word=word.lower(),
                                    example_sentence=response_text[:200],
                                ),
                                session_id=session_id,
                            )
                    except Exception as e:
                        logger.warning(f"Could not extract vocabulary: {e}")

                    # === RAG: ИЗВЛЕКАЕМ И СОХРАНЯЕМ ВОСПОМИНАНИЯ ===
                    # Каждые 5 ходов обрабатываем диалог для извлечения памяти
                    if turn_count % 5 == 0 and len(conversation_history) >= 4:
                        try:
                            extracted = await memory_pipeline.process_conversation(
                                user_id=user_id,
                                messages=conversation_history[-10:],  # Последние 10 сообщений
                                session_id=session_id,
                            )
                            if extracted:
                                logger.info(f"[RAG] Extracted {len(extracted)} memories from conversation")
                        except Exception as e:
                            logger.warning(f"Could not extract memories: {e}")

                    # Синтезируем и отправляем аудио
                    try:
                        tts_start = time.time()
                        audio_bytes = await tts.synthesize(response_text)
                        voice_tts_latency_seconds.observe(time.time() - tts_start)

                        await websocket.send_json({
                            "type": "audio",
                            "data": base64.b64encode(audio_bytes).decode(),
                            "format": "mp3",
                        })
                        voice_messages_total.labels(direction="outbound", type="audio").inc()

                        # Record total turn time
                        voice_turn_total_seconds.labels(mode=current_mode.value).observe(
                            time.time() - turn_start
                        )
                    except Exception as e:
                        voice_errors_total.labels(stage="tts").inc()
                        voice_messages_total.labels(direction="outbound", type="error").inc()
                        await websocket.send_json({
                            "type": "error",
                            "message": f"TTS error: {str(e)}",
                        })

                elif message.get("type") == "end":
                    session_status = "completed"  # Metrics: proper session end
                    final_mode = current_mode.value

                    # === POST-SESSION: Анализ и генерация карточек ===
                    post_session_result = {}
                    if conversation_history and len(conversation_history) >= 2:
                        try:
                            post_session = PostSessionService(db)
                            post_session_result = await post_session.process_session_end(
                                user_id=user_id,
                                session_id=session_id,
                                conversation_history=conversation_history,
                                current_mode=current_mode.value,
                                session_context={
                                    "goal": session_context.goal,
                                    "assessed_level": session_context.language_level,
                                },
                            )
                            data_logger.log_postgres_write(
                                table="post_session",
                                operation="PROCESS",
                                data=post_session_result,
                                user_id=user_id,
                            )
                        except Exception as e:
                            logger.warning(f"Post-session processing failed: {e}")

                    # Финальное извлечение памяти из всей сессии
                    if conversation_history:
                        try:
                            extracted = await memory_pipeline.process_conversation(
                                user_id=user_id,
                                messages=conversation_history,
                                session_id=session_id,
                            )
                            if extracted:
                                logger.info(f"[RAG] Final extraction: {len(extracted)} memories")
                                data_logger.log_qdrant_write(
                                    collection="memories",
                                    data={"count": len(extracted)},
                                    user_id=user_id,
                                )
                        except Exception as e:
                            logger.warning(f"Could not extract final memories: {e}")

                    # Обновляем счётчик сессий
                    try:
                        await learning_plan_service.increment_session_count(
                            user_id,
                            mode=current_mode.value,
                            duration_minutes=turn_count * 2,  # Примерная оценка
                        )
                        data_logger.log_postgres_write(
                            table="learning_plan",
                            operation="UPDATE",
                            data={"sessions_completed": "+1", "mode": current_mode.value},
                            user_id=user_id,
                        )
                    except Exception as e:
                        logger.warning(f"Could not update session count: {e}")

                    # === Gamification: XP и Streak ===
                    await award_session_gamification(db, user_id, session_id)

                    break

            except WebSocketDisconnect:
                logger.info(f"Client disconnected: session {session_id}")
                session_status = "disconnected"
                final_mode = current_mode.value

                # Обновляем счётчик сессий при отключении
                try:
                    await learning_plan_service.increment_session_count(
                        user_id,
                        mode=current_mode.value,
                        duration_minutes=turn_count * 2,
                    )
                except Exception:
                    pass

                # Gamification при disconnect (если были реплики)
                if turn_count > 0:
                    try:
                        await award_session_gamification(db, user_id, session_id)
                    except Exception:
                        pass

                break

    except Exception as e:
        # Top-level error во время инициализации или message loop
        logger.error(f"WebSocket error: {e}", exc_info=True)
        session_status = "error"
        voice_errors_total.labels(stage="websocket").inc()
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Server error. Please refresh the page.",
            })
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass  # Connection already closed

    finally:
        # Metrics: decrement active sessions and record total
        voice_sessions_active.dec()
        voice_sessions_total.labels(mode=final_mode, status=session_status).inc()

        # Cleanup
        try:
            await websocket.close()
        except Exception:
            pass


# =============================================================================
# LangGraph-based endpoint (v2)
# =============================================================================

@router.websocket("/chat/v2")
async def voice_chat_v2(
    websocket: WebSocket,
    user_id: int = Query(..., description="ID пользователя"),
    mode: Optional[str] = Query(None, description="Режим обучения"),
    interview_track: Optional[str] = Query(None, description="ID трека интервью"),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint для голосового чата на LangGraph state machine.

    Улучшения по сравнению с /chat:
    - Цель определяется через диалог с подтверждением
    - Интересы выясняются активно
    - Все педагогические решения логируются
    - Структурированный онбординг для новых пользователей

    Протокол (совместим с /chat):
    - Client -> Server: {"type": "text", "text": "..."}
    - Client -> Server: {"type": "end"}
    - Server -> Client: {"type": "connected", "session_id": "...", "phase": "..."}
    - Server -> Client: {"type": "transcript", "role": "assistant", "text": "..."}
    - Server -> Client: {"type": "audio", "data": "<base64 MP3>", "format": "mp3"}
    - Server -> Client: {"type": "phase_changed", "phase": "...", "mode": "..."}
    - Server -> Client: {"type": "error", "message": "..."}
    """
    await websocket.accept()

    # Metrics: increment active sessions
    voice_sessions_active.inc()
    session_start_time = time.time()
    final_mode = "unknown"
    session_status = "disconnected"

    try:
        # === INITIALIZATION ===
        session_id = str(uuid.uuid4())

        # Load user data
        user = None
        is_new_user = True
        username = "Student"
        language_level = "B1"

        try:
            user_service = UserService(db)
            user = await user_service.get_user(user_id)

            # Auto-create user if doesn't exist (fixes FK violation)
            if not user:
                logger.info(f"[Voice] User {user_id} not found, auto-creating...")
                user = await user_service.create_user(UserCreate(
                    telegram_id=user_id,
                    username=f"User_{user_id}",
                    language_level="B1"
                ))
                logger.info(f"[Voice] Auto-created user {user_id}")

            if user:
                username = user.username or "Student"
                language_level = user.language_level or "B1"
        except Exception as e:
            logger.warning(f"Could not fetch/create user from DB: {e}")
            voice_errors_total.labels(stage="db").inc()

        # Load learning context
        learning_plan_service = LearningPlanService(db)
        vocabulary_service = VocabularyService(db)
        memory_pipeline = create_memory_pipeline(db)

        confirmed_goal = None
        confirmed_interests = None
        roadmap = None
        due_vocabulary_count = 0
        due_vocabulary_words = []
        memory_section = ""

        try:
            learning_plan = await learning_plan_service.get_or_create_plan(user_id)
            confirmed_goal = learning_plan_service.get_goal(learning_plan)
            roadmap = learning_plan.roadmap
            language_level = learning_plan_service.get_current_level(learning_plan) or language_level

            # Determine if new user
            total_sessions = learning_plan_service.get_session_count(learning_plan)
            is_new_user = total_sessions == 0 and not confirmed_goal

            # Load vocabulary due
            due_vocabulary = await vocabulary_service.get_due_cards(user_id, limit=10)
            due_vocabulary_count = len(due_vocabulary)
            due_vocabulary_words = [card.word for card in due_vocabulary]

            # Load memory context
            memory_section = await memory_pipeline.format_memory_for_prompt(user_id)

            logger.info(f"[AgentV2] User {user_id}: is_new={is_new_user}, "
                       f"goal={confirmed_goal}, due_vocab={due_vocabulary_count}")

        except Exception as e:
            logger.warning(f"Could not load learning context: {e}")
            voice_errors_total.labels(stage="db").inc()

        # Determine agent version based on feature flag
        use_v2 = USE_AGENT_V2
        agent_version = "v2" if use_v2 else "v1"
        logger.info(f"[Voice] Using agent {agent_version} for user {user_id}")

        # Track version usage
        agent_version_sessions.labels(version=agent_version).inc()

        # Initialize agent state (v1 or v2)
        if use_v2:
            agent_state = await initialize_session_v2(
                user_id=user_id,
                session_id=session_id,
                username=username,
                is_new_user=is_new_user,
                language_level=language_level,
                confirmed_goal=confirmed_goal,
                confirmed_interests=confirmed_interests,
                roadmap=roadmap,
                due_vocabulary_count=due_vocabulary_count,
                due_vocabulary_words=due_vocabulary_words,
                memory_section=memory_section,
                explicit_mode=mode,
                interview_track_id=interview_track,
            )
        else:
            agent_state = await initialize_session(
                user_id=user_id,
                session_id=session_id,
                username=username,
                is_new_user=is_new_user,
                language_level=language_level,
                confirmed_goal=confirmed_goal,
                confirmed_interests=confirmed_interests,
                roadmap=roadmap,
                due_vocabulary_count=due_vocabulary_count,
                due_vocabulary_words=due_vocabulary_words,
                memory_section=memory_section,
            )

        # Initialize TTS service
        tts = get_tts_service()

        # Run initial agent turn (greeting/first question)
        if use_v2:
            agent_state = await run_agent_turn_v2(agent_state, user_message=None)
        else:
            agent_state = await run_agent_turn(agent_state, user_message=None)

        # Get initial response
        initial_response = agent_state.get("pending_response", "")
        current_phase = agent_state.get("current_phase", AgentPhase.START)
        current_mode = agent_state.get("current_mode", LearningModeEnum.FREE_CONVERSATION)

        final_mode = current_mode.value

        # Send connected message
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "phase": current_phase.value,
            "mode": current_mode.value,
            "is_new_user": is_new_user,
            "goal": confirmed_goal,
            "due_vocabulary_count": due_vocabulary_count,
        })

        # Send initial greeting/question
        if initial_response:
            await websocket.send_json({
                "type": "transcript",
                "role": "assistant",
                "text": initial_response,
                "phase": current_phase.value,
            })

            # Synthesize audio
            try:
                tts_start = time.time()
                audio_bytes = await tts.synthesize(initial_response)
                voice_tts_latency_seconds.observe(time.time() - tts_start)

                await websocket.send_json({
                    "type": "audio",
                    "data": base64.b64encode(audio_bytes).decode(),
                    "format": "mp3",
                })
                voice_messages_total.labels(direction="outbound", type="audio").inc()
            except Exception as e:
                logger.warning(f"TTS error for greeting: {e}")
                voice_errors_total.labels(stage="tts").inc()

        # === MESSAGE LOOP ===
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "text":
                    user_text = message.get("text", "").strip()
                    if not user_text:
                        continue

                    turn_start = time.time()
                    voice_messages_total.labels(direction="inbound", type="text").inc()

                    # Send user transcript
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "user",
                        "text": user_text,
                    })

                    # Run agent turn (v1 or v2)
                    old_phase = agent_state.get("current_phase", AgentPhase.START)
                    if use_v2:
                        agent_state = await run_agent_turn_v2(agent_state, user_message=user_text)
                    else:
                        agent_state = await run_agent_turn(agent_state, user_message=user_text)

                    # Get response
                    response_text = agent_state.get("pending_response", "")
                    current_phase = agent_state.get("current_phase", AgentPhase.START)
                    current_mode = agent_state.get("current_mode", LearningModeEnum.FREE_CONVERSATION)
                    turn_count = agent_state.get("turn_count", 0)

                    final_mode = current_mode.value

                    # Check for phase change
                    if old_phase != current_phase:
                        await websocket.send_json({
                            "type": "phase_changed",
                            "phase": current_phase.value,
                            "mode": current_mode.value,
                        })

                        # Track onboarding completion (transition to learning)
                        if current_phase == AgentPhase.LEARNING_SESSION:
                            agent_version_onboarding_complete.labels(
                                version=agent_version
                            ).inc()

                    if response_text:
                        # Send transcript
                        await websocket.send_json({
                            "type": "transcript",
                            "role": "assistant",
                            "text": response_text,
                            "phase": current_phase.value,
                            "mode": current_mode.value,
                            "turn": turn_count,
                        })

                        # Synthesize audio
                        try:
                            tts_start = time.time()
                            audio_bytes = await tts.synthesize(response_text)
                            voice_tts_latency_seconds.observe(time.time() - tts_start)

                            await websocket.send_json({
                                "type": "audio",
                                "data": base64.b64encode(audio_bytes).decode(),
                                "format": "mp3",
                            })
                            voice_messages_total.labels(direction="outbound", type="audio").inc()

                            voice_turn_total_seconds.labels(mode=current_mode.value).observe(
                                time.time() - turn_start
                            )
                        except Exception as e:
                            logger.warning(f"TTS error: {e}")
                            voice_errors_total.labels(stage="tts").inc()

                    # Check for session end
                    if agent_state.get("should_end_session"):
                        session_status = "completed"
                        break

                elif message.get("type") == "end":
                    session_status = "completed"

                    # Process session end (v1 or v2)
                    agent_state["should_end_session"] = True
                    if use_v2:
                        agent_state = await run_agent_turn_v2(agent_state, user_message=None)
                    else:
                        agent_state = await run_agent_turn(agent_state, user_message=None)

                    # Send farewell if generated
                    farewell = agent_state.get("pending_response", "")
                    if farewell:
                        await websocket.send_json({
                            "type": "transcript",
                            "role": "assistant",
                            "text": farewell,
                            "phase": "session_end",
                        })

                        try:
                            audio_bytes = await tts.synthesize(farewell)
                            await websocket.send_json({
                                "type": "audio",
                                "data": base64.b64encode(audio_bytes).decode(),
                                "format": "mp3",
                            })
                        except Exception as e:
                            logger.warning(f"TTS error for farewell: {e}")

                    # Persist session data
                    try:
                        await persist_goal_state_if_needed(
                            user_id=user_id,
                            existing_goal=confirmed_goal,
                            agent_state=agent_state,
                            learning_plan_service=learning_plan_service,
                        )

                        # Update session count
                        await learning_plan_service.increment_session_count(
                            user_id,
                            mode=current_mode.value,
                            duration_minutes=agent_state.get("turn_count", 0) * 2,
                        )

                        # Record assessment if done
                        if agent_state.get("assessed_level"):
                            await learning_plan_service.record_assessment(
                                user_id,
                                assessed_level=agent_state["assessed_level"],
                                scores=agent_state.get("assessment_scores"),
                                provisional=bool(agent_state.get("baseline_provisional")),
                                confidence_override=agent_state.get("baseline_confidence"),
                            )

                        # Process memories
                        conversation_history = agent_state.get("conversation_history", [])
                        if conversation_history:
                            await memory_pipeline.process_conversation(
                                user_id=user_id,
                                messages=conversation_history,
                                session_id=session_id,
                            )

                        # Gamification
                        await award_session_gamification(db, user_id, session_id)

                        # Persist interview run if this was a mock_interview session
                        interview_run = await persist_interview_run_if_needed(
                            db=db,
                            user_id=user_id,
                            session_id=session_id,
                            current_mode=current_mode.value,
                            interview_track_id=agent_state.get("interview_track_id"),
                            conversation_history=agent_state.get("conversation_history", []),
                            corrections_made=len(agent_state.get("corrections_made", [])),
                            vocabulary_reviewed=agent_state.get("vocabulary_reviewed", []),
                        )
                        await persist_session_evidence_if_needed(
                            db=db,
                            user_id=user_id,
                            session_id=session_id,
                            current_mode=current_mode.value,
                            conversation_history=agent_state.get("conversation_history", []),
                            corrections_made=agent_state.get("corrections_made", []),
                            vocabulary_reviewed=agent_state.get("vocabulary_reviewed", []),
                            duration_minutes=agent_state.get("turn_count", 0) * 2,
                            assessed_level=agent_state.get("assessed_level"),
                            assessment_scores=agent_state.get("assessment_scores", {}),
                            interview_run=interview_run,
                        )

                    except Exception as e:
                        logger.warning(f"Error persisting session data: {e}")

                    break

            except WebSocketDisconnect:
                logger.info(f"Client disconnected: session {session_id}")
                session_status = "disconnected"

                # Try to persist on disconnect
                try:
                    await persist_goal_state_if_needed(
                        user_id=user_id,
                        existing_goal=confirmed_goal,
                        agent_state=agent_state,
                        learning_plan_service=learning_plan_service,
                    )
                    if agent_state.get("assessed_level"):
                        await learning_plan_service.record_assessment(
                            user_id,
                            assessed_level=agent_state["assessed_level"],
                            scores=agent_state.get("assessment_scores"),
                            provisional=bool(agent_state.get("baseline_provisional")),
                            confidence_override=agent_state.get("baseline_confidence"),
                        )
                    await learning_plan_service.increment_session_count(
                        user_id,
                        mode=current_mode.value,
                        duration_minutes=agent_state.get("turn_count", 0) * 2,
                    )
                    if agent_state.get("turn_count", 0) > 0:
                        await award_session_gamification(db, user_id, session_id)
                    interview_run = await persist_interview_run_if_needed(
                        db=db,
                        user_id=user_id,
                        session_id=session_id,
                        current_mode=current_mode.value,
                        interview_track_id=agent_state.get("interview_track_id"),
                        conversation_history=agent_state.get("conversation_history", []),
                        corrections_made=len(agent_state.get("corrections_made", [])),
                        vocabulary_reviewed=agent_state.get("vocabulary_reviewed", []),
                    )
                    await persist_session_evidence_if_needed(
                        db=db,
                        user_id=user_id,
                        session_id=session_id,
                        current_mode=current_mode.value,
                        conversation_history=agent_state.get("conversation_history", []),
                        corrections_made=agent_state.get("corrections_made", []),
                        vocabulary_reviewed=agent_state.get("vocabulary_reviewed", []),
                        duration_minutes=agent_state.get("turn_count", 0) * 2,
                        assessed_level=agent_state.get("assessed_level"),
                        assessment_scores=agent_state.get("assessment_scores", {}),
                        interview_run=interview_run,
                    )
                except Exception:
                    pass

                break

    except Exception as e:
        logger.error(f"WebSocket error (v2): {e}", exc_info=True)
        session_status = "error"
        voice_errors_total.labels(stage="websocket").inc()
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Server error. Please refresh the page.",
            })
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass

    finally:
        voice_sessions_active.dec()
        voice_sessions_total.labels(mode=final_mode, status=session_status).inc()

        try:
            await websocket.close()
        except Exception:
            pass


# =============================================================================
# PersonaPlex-based endpoint (full-duplex speech-to-speech)
# =============================================================================


def _build_personaplex_system_prompt(agent_state: dict) -> str:
    """Build a rich pedagogical system prompt for PersonaPlex from agent state.

    PersonaPlex uses this prompt to condition its speech generation, so it
    includes the full learning context: goal, mode, vocabulary, memories, etc.
    """
    username = agent_state.get("username", "Student")
    level = agent_state.get("language_level", "B1")
    goal = agent_state.get("confirmed_goal") or agent_state.get("detected_goal") or "improve English"
    mode = agent_state.get("current_mode", LearningModeEnum.FREE_CONVERSATION)
    if isinstance(mode, LearningModeEnum):
        mode = mode.value
    interests = agent_state.get("detected_interests") or []
    memories = agent_state.get("memory_section") or ""
    vocab_words = agent_state.get("due_vocabulary_words") or []

    mode_instructions = {
        "mock_interview": (
            "Act as a professional interviewer. Ask behavioral and technical "
            "questions. Give STAR method feedback. Be encouraging but honest."
        ),
        "vocabulary_drill": (
            "Focus on vocabulary practice. Use the target words naturally in "
            "conversation. Ask the student to use them in sentences."
        ),
        "free_conversation": (
            "Have a natural conversation. Gently correct errors using Socratic "
            "recasting. Keep the dialogue engaging and educational."
        ),
        "grammar_focus": (
            "Focus on grammar exercises. Provide examples and ask the student "
            "to construct sentences. Correct errors explicitly."
        ),
        "assessment": (
            "Assess the student's English level through natural conversation. "
            "Ask progressively harder questions to gauge CEFR level."
        ),
    }

    sections = [
        f"You are Sarah, a warm and professional English mentor.",
        f"",
        f"STUDENT PROFILE:",
        f"- Name: {username}",
        f"- Level: {level} (CEFR)",
        f"- Goal: {goal}",
    ]

    if interests:
        sections.append(f"- Interests: {', '.join(interests[:5])}")

    sections.extend([
        f"",
        f"CURRENT SESSION MODE: {mode.replace('_', ' ').title()}",
        mode_instructions.get(mode, mode_instructions["free_conversation"]),
    ])

    if vocab_words:
        sections.append("")
        sections.append("VOCABULARY TO REINFORCE:")
        for word in vocab_words[:5]:
            sections.append(f"- \"{word}\" (weave into conversation naturally)")

    if memories:
        sections.append("")
        sections.append("MEMORY CONTEXT (from previous sessions):")
        sections.append(memories)

    sections.extend([
        "",
        "IMPORTANT RULES:",
        "- Speak naturally and at a pace appropriate for the student's level.",
        "- Use Socratic recasting: repeat the student's error in correct form.",
        "- Keep responses concise (2-3 sentences) for voice conversation.",
        "- Be encouraging and maintain a positive learning atmosphere.",
    ])

    return "\n".join(sections)


@router.websocket("/chat/plex")
async def voice_chat_plex(
    websocket: WebSocket,
    user_id: int = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """PersonaPlex-based full-duplex voice chat with pedagogical pipeline.

    Flow:
    1. Health-check PersonaPlex → fallback to /chat/v2 if unavailable
    2. Initialize LangGraph agent state (same as /chat/v2)
    3. Build pedagogical system prompt for PersonaPlex
    4. Connect to PersonaPlex (WebSocket)
    5. Bidirectional streaming:
       - Client audio → PersonaPlex
       - PersonaPlex audio/transcript → Client
       - Transcripts → LangGraph for pedagogical analysis

    Protocol:
    - Client -> Server: {"type": "audio", "data": "<base64 opus>"}
    - Client -> Server: {"type": "text", "text": "..."}  (text fallback)
    - Client -> Server: {"type": "end"}
    - Server -> Client: {"type": "connected", "session_id": "...", "provider": "personaplex"}
    - Server -> Client: {"type": "transcript", "role": "user"|"assistant", "text": "..."}
    - Server -> Client: {"type": "audio", "data": "<base64 opus>", "format": "opus"}
    - Server -> Client: {"type": "phase_changed", "phase": "...", "mode": "..."}
    - Server -> Client: {"type": "error", "message": "..."}
    """
    # --- Health check: fallback to v2 if PersonaPlex is unavailable ---
    if not settings.personaplex_enabled or not await check_personaplex_health():
        logger.info(f"[PersonaPlex] Unavailable for user {user_id}, falling back to v2")
        personaplex_fallback_total.labels(reason="health_check_failed").inc()
        data_logger.log_personaplex_fallback(user_id, reason="health_check_failed")
        return await voice_chat_v2(websocket, user_id=user_id, db=db)

    await websocket.accept()

    personaplex_connections_active.inc()
    session_start_time = time.time()
    final_mode = "unknown"
    session_status = "disconnected"
    plex: PersonaPlexProvider | None = None
    plex_turn_count = 0

    try:
        # === INITIALIZATION (same as /chat/v2) ===
        session_id = str(uuid.uuid4())

        user = None
        is_new_user = True
        username = "Student"
        language_level = "B1"

        try:
            user_service = UserService(db)
            user = await user_service.get_user(user_id)
            if not user:
                logger.info(f"[PersonaPlex] User {user_id} not found, auto-creating...")
                user = await user_service.create_user(UserCreate(
                    telegram_id=user_id,
                    username=f"User_{user_id}",
                    language_level="B1",
                ))
            if user:
                username = user.username or "Student"
                language_level = user.language_level or "B1"
        except Exception as e:
            logger.warning(f"Could not fetch/create user from DB: {e}")
            voice_errors_total.labels(stage="db").inc()

        # Load learning context
        learning_plan_service = LearningPlanService(db)
        vocabulary_service = VocabularyService(db)
        memory_pipeline = create_memory_pipeline(db)

        confirmed_goal = None
        confirmed_interests = None
        roadmap = None
        due_vocabulary_count = 0
        due_vocabulary_words: list[str] = []
        memory_section = ""

        try:
            learning_plan = await learning_plan_service.get_or_create_plan(user_id)
            confirmed_goal = learning_plan_service.get_goal(learning_plan)
            roadmap = learning_plan.roadmap
            language_level = learning_plan_service.get_current_level(learning_plan) or language_level
            total_sessions = learning_plan_service.get_session_count(learning_plan)
            is_new_user = total_sessions == 0 and not confirmed_goal

            due_vocabulary = await vocabulary_service.get_due_cards(user_id, limit=10)
            due_vocabulary_count = len(due_vocabulary)
            due_vocabulary_words = [card.word for card in due_vocabulary]

            memory_section = await memory_pipeline.format_memory_for_prompt(user_id)
        except Exception as e:
            logger.warning(f"Could not load learning context: {e}")
            voice_errors_total.labels(stage="db").inc()

        # Initialize LangGraph agent state
        use_v2 = USE_AGENT_V2
        if use_v2:
            agent_state = await initialize_session_v2(
                user_id=user_id,
                session_id=session_id,
                username=username,
                is_new_user=is_new_user,
                language_level=language_level,
                confirmed_goal=confirmed_goal,
                confirmed_interests=confirmed_interests,
                roadmap=roadmap,
                due_vocabulary_count=due_vocabulary_count,
                due_vocabulary_words=due_vocabulary_words,
                memory_section=memory_section,
            )
        else:
            agent_state = await initialize_session(
                user_id=user_id,
                session_id=session_id,
                username=username,
                is_new_user=is_new_user,
                language_level=language_level,
                confirmed_goal=confirmed_goal,
                confirmed_interests=confirmed_interests,
                roadmap=roadmap,
                due_vocabulary_count=due_vocabulary_count,
                due_vocabulary_words=due_vocabulary_words,
                memory_section=memory_section,
            )

        current_phase = agent_state.get("current_phase", AgentPhase.START)
        current_mode = agent_state.get("current_mode", LearningModeEnum.FREE_CONVERSATION)
        final_mode = current_mode.value if isinstance(current_mode, LearningModeEnum) else str(current_mode)

        # Build pedagogical prompt for PersonaPlex
        system_prompt = _build_personaplex_system_prompt(agent_state)

        # === CONNECT TO PERSONAPLEX ===
        plex = PersonaPlexProvider(voice=settings.personaplex_default_voice)
        try:
            connect_start = time.time()
            await plex.connect(VoiceSession(
                session_id=session_id,
                user_id=user_id,
                system_prompt=system_prompt,
            ))
            personaplex_latency_seconds.labels(operation="connect").observe(
                time.time() - connect_start
            )
        except PersonaPlexConnectionError:
            logger.warning(f"[PersonaPlex] Connection failed for user {user_id}, falling back to v2")
            personaplex_fallback_total.labels(reason="connection_error").inc()
            personaplex_errors_total.labels(error_type="connection_failed").inc()
            data_logger.log_personaplex_fallback(user_id, reason="connection_error")
            personaplex_connections_active.dec()
            # Fall back: re-use the already-accepted websocket by continuing as v2
            # We need to send an error and close, then the client will reconnect
            await websocket.send_json({
                "type": "error",
                "message": "PersonaPlex unavailable, please reconnect to /chat/v2",
            })
            await websocket.close(code=1013, reason="PersonaPlex unavailable")
            return

        data_logger.log_personaplex_connect(
            user_id=user_id,
            session_id=session_id,
            voice=settings.personaplex_default_voice,
            mode=final_mode,
        )

        # Send connected message to client
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "phase": current_phase.value if isinstance(current_phase, AgentPhase) else str(current_phase),
            "mode": final_mode,
            "provider": "personaplex",
            "is_new_user": is_new_user,
            "goal": confirmed_goal,
            "due_vocabulary_count": due_vocabulary_count,
        })

        # Track conversation transcripts for pedagogical analysis
        conversation_history: list[dict] = []

        # === BIDIRECTIONAL STREAMING ===
        import asyncio

        async def forward_plex_to_client():
            """Forward PersonaPlex events (audio + transcripts) to the client."""
            nonlocal plex_turn_count
            async for event in plex.receive():
                if event["type"] == "audio":
                    await websocket.send_json({
                        "type": "audio",
                        "data": base64.b64encode(event["data"]).decode(),
                        "format": "opus",
                    })
                    voice_messages_total.labels(direction="outbound", type="audio").inc()

                elif event["type"] == "transcript":
                    role = event.get("role", "assistant")
                    text = event.get("text", "")
                    is_final = event.get("is_final", True)

                    if is_final and text:
                        plex_turn_count += 1
                        conversation_history.append({"role": role, "content": text})

                        mode_str = final_mode
                        phase_str = (
                            current_phase.value
                            if isinstance(current_phase, AgentPhase)
                            else str(current_phase)
                        )
                        personaplex_turns_total.labels(mode=mode_str, phase=phase_str).inc()
                        data_logger.log_personaplex_turn(
                            session_id=session_id,
                            role=role,
                            text_preview=text,
                            latency_ms=0,  # PersonaPlex handles latency internally
                        )

                    await websocket.send_json({
                        "type": "transcript",
                        "role": role,
                        "text": text,
                        "is_final": is_final,
                        "phase": (
                            current_phase.value
                            if isinstance(current_phase, AgentPhase)
                            else str(current_phase)
                        ),
                        "mode": final_mode,
                        "turn": plex_turn_count,
                    })

                elif event["type"] == "error":
                    await websocket.send_json({
                        "type": "error",
                        "message": event.get("message", "PersonaPlex error"),
                    })
                    personaplex_errors_total.labels(error_type="audio_processing").inc()

        async def forward_client_to_plex():
            """Forward client messages (audio/text/end) to PersonaPlex."""
            nonlocal current_phase, current_mode, final_mode

            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                msg_type = message.get("type", "")

                if msg_type == "audio":
                    # Client sends base64-encoded opus audio
                    audio_bytes = base64.b64decode(message["data"])
                    await plex.send_audio(audio_bytes)
                    voice_messages_total.labels(direction="inbound", type="audio").inc()

                elif msg_type == "text":
                    # Text fallback: client sends recognized text
                    user_text = message.get("text", "").strip()
                    if not user_text:
                        continue
                    voice_messages_total.labels(direction="inbound", type="text").inc()
                    conversation_history.append({"role": "user", "content": user_text})

                    # Run pedagogical analysis via LangGraph
                    old_phase = agent_state.get("current_phase", AgentPhase.START)
                    if use_v2:
                        updated = await run_agent_turn_v2(agent_state, user_message=user_text)
                    else:
                        updated = await run_agent_turn(agent_state, user_message=user_text)
                    agent_state.update(updated)

                    new_phase = agent_state.get("current_phase", AgentPhase.START)
                    new_mode = agent_state.get("current_mode", LearningModeEnum.FREE_CONVERSATION)

                    # Check for phase/mode change → update PersonaPlex prompt
                    if old_phase != new_phase or current_mode != new_mode:
                        current_phase = new_phase
                        current_mode = new_mode
                        final_mode = (
                            current_mode.value
                            if isinstance(current_mode, LearningModeEnum)
                            else str(current_mode)
                        )
                        new_prompt = _build_personaplex_system_prompt(agent_state)
                        await plex.update_persona(new_prompt)
                        personaplex_pedagogical_events.labels(event_type="mode_changed").inc()

                        await websocket.send_json({
                            "type": "phase_changed",
                            "phase": (
                                current_phase.value
                                if isinstance(current_phase, AgentPhase)
                                else str(current_phase)
                            ),
                            "mode": final_mode,
                        })

                    # Periodic memory extraction (every 5 turns)
                    if plex_turn_count > 0 and plex_turn_count % 5 == 0:
                        try:
                            extracted = await memory_pipeline.process_conversation(
                                user_id=user_id,
                                messages=conversation_history[-10:],
                                session_id=session_id,
                            )
                            if extracted:
                                personaplex_pedagogical_events.labels(
                                    event_type="memory_extracted"
                                ).inc()
                                logger.info(
                                    f"[PersonaPlex] Extracted {len(extracted)} memories"
                                )
                        except Exception as e:
                            logger.warning(f"Memory extraction failed: {e}")

                elif msg_type == "end":
                    raise WebSocketDisconnect(code=1000, reason="Client ended session")

        # Run both directions concurrently
        plex_task = asyncio.create_task(forward_plex_to_client())
        try:
            await forward_client_to_plex()
        except WebSocketDisconnect:
            session_status = "completed" if plex_turn_count > 0 else "disconnected"
        finally:
            plex_task.cancel()
            try:
                await plex_task
            except asyncio.CancelledError:
                pass

        # === POST-SESSION PERSISTENCE ===
        try:
            await persist_goal_state_if_needed(
                user_id=user_id,
                existing_goal=confirmed_goal,
                agent_state=agent_state,
                learning_plan_service=learning_plan_service,
            )

            await learning_plan_service.increment_session_count(
                user_id,
                mode=final_mode,
                duration_minutes=int((time.time() - session_start_time) / 60),
            )

            if agent_state.get("assessed_level"):
                await learning_plan_service.record_assessment(
                    user_id,
                    assessed_level=agent_state["assessed_level"],
                    scores=agent_state.get("assessment_scores"),
                    provisional=bool(agent_state.get("baseline_provisional")),
                    confidence_override=agent_state.get("baseline_confidence"),
                )

            if conversation_history:
                await memory_pipeline.process_conversation(
                    user_id=user_id,
                    messages=conversation_history,
                    session_id=session_id,
                )

            await award_session_gamification(db, user_id, session_id)
            interview_run = await persist_interview_run_if_needed(
                db=db,
                user_id=user_id,
                session_id=session_id,
                current_mode=final_mode,
                interview_track_id=agent_state.get("interview_track_id"),
                conversation_history=conversation_history,
                corrections_made=len(agent_state.get("corrections_made", [])),
                vocabulary_reviewed=agent_state.get("vocabulary_reviewed", []),
            )
            await persist_session_evidence_if_needed(
                db=db,
                user_id=user_id,
                session_id=session_id,
                current_mode=final_mode,
                conversation_history=conversation_history,
                corrections_made=agent_state.get("corrections_made", []),
                vocabulary_reviewed=agent_state.get("vocabulary_reviewed", []),
                duration_minutes=int((time.time() - session_start_time) / 60),
                assessed_level=agent_state.get("assessed_level"),
                assessment_scores=agent_state.get("assessment_scores", {}),
                interview_run=interview_run,
            )
        except Exception as e:
            logger.warning(f"[PersonaPlex] Post-session persistence error: {e}")

    except PersonaPlexConnectionError as e:
        logger.error(f"[PersonaPlex] Connection error: {e}")
        session_status = "error"
        personaplex_errors_total.labels(error_type="connection_failed").inc()
        try:
            await websocket.send_json({
                "type": "error",
                "message": "PersonaPlex connection lost",
            })
            await websocket.close(code=1011, reason="PersonaPlex error")
        except Exception:
            pass

    except Exception as e:
        logger.error(f"[PersonaPlex] Unexpected error: {e}", exc_info=True)
        session_status = "error"
        personaplex_errors_total.labels(error_type="unexpected").inc()
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Server error. Please refresh the page.",
            })
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass

    finally:
        # Disconnect PersonaPlex
        if plex:
            await plex.disconnect()

        # Metrics
        personaplex_connections_active.dec()
        session_duration = time.time() - session_start_time
        personaplex_session_duration_seconds.observe(session_duration)
        personaplex_sessions_total.labels(status=session_status).inc()

        data_logger.log_personaplex_disconnect(
            session_id=session_id,
            turns=plex_turn_count,
            duration_seconds=session_duration,
        )

        try:
            await websocket.close()
        except Exception:
            pass


# Legacy endpoint для обратной совместимости с OpenAI Realtime
@router.websocket("/stream")
async def voice_stream_legacy(
    websocket: WebSocket,
    user_id: int = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """
    Legacy WebSocket endpoint для потокового аудио.

    Использует старые провайдеры (OpenAI Realtime, Hume EVI).
    Для нового Vosk + Groq используйте /chat.
    """
    from app.services.ai import get_ai_provider, VoiceSession

    await websocket.accept()

    user_service = UserService(db)
    user = await user_service.get_user(user_id)
    if not user:
        await websocket.send_json({"type": "error", "message": "User not found"})
        await websocket.close()
        return

    session = VoiceSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        system_prompt=build_simple_prompt(),
    )

    provider = get_ai_provider()

    try:
        await provider.connect(session)
        await websocket.send_json({
            "type": "connected",
            "session_id": session.session_id,
            "message": "Ready to talk!",
        })

        import asyncio

        async def forward_ai_events():
            async for event in provider.receive():
                if event["type"] == "audio":
                    await websocket.send_json({
                        "type": "audio",
                        "data": base64.b64encode(event["data"]).decode(),
                    })
                elif event["type"] == "transcript":
                    session.transcript.append({
                        "role": event["role"],
                        "text": event["text"],
                    })
                    await websocket.send_json(event)
                elif event["type"] == "error":
                    await websocket.send_json(event)
                    break

        ai_task = asyncio.create_task(forward_ai_events())

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "audio":
                    audio_bytes = base64.b64decode(message["data"])
                    await provider.send_audio(audio_bytes)

                elif message.get("type") == "end":
                    break

        except WebSocketDisconnect:
            pass
        finally:
            ai_task.cancel()

    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})

    finally:
        await provider.disconnect()
        await websocket.close()
