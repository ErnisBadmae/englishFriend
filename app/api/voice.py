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
"""

import json
import re
import uuid
import base64
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.database import UserService
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

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


@router.websocket("/chat")
async def voice_chat(
    websocket: WebSocket,
    user_id: int = Query(..., description="ID пользователя"),
    mode: Optional[str] = Query(None, description="Режим обучения"),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint для голосового чата с педагогической архитектурой.

    Режимы обучения:
    - assessment: Оценка уровня
    - mock_interview: Симуляция собеседования
    - vocabulary_drill: Повторение слов через FSRS
    - free_conversation: Свободный разговор с коррекцией

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

    try:
        # === INITIALIZATION BLOCK ===

        # Проверяем пользователя
        user = None
        try:
            user_service = UserService(db)
            user = await user_service.get_user(user_id)
        except Exception as e:
            print(f"Warning: Could not fetch user from DB: {e}")

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

            print(f"[Pedagogy] Loaded context: goal={session_context.goal}, "
                  f"due_vocab={session_context.due_vocabulary_count}, "
                  f"sessions={session_context.total_sessions}")
        except Exception as e:
            print(f"Warning: Could not load learning context: {e}")

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
        print(f"[Pedagogy] Selected mode: {current_mode.value}, focus: {focus_area}")

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
                print(f"[RAG] Loaded memory context ({len(memory_section)} chars)")
        except Exception as e:
            print(f"Warning: Could not load memory context: {e}")

        system_prompt = build_mode_prompt(
            mode=current_mode,
            username=session_context.username,
            level=session_context.language_level,
            goal=session_context.goal or "improve English",
            interests="technology, career development",
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
                            learning_plan = await learning_plan_service.set_goal(
                                user_id, goal_text
                            )
                            session_context.goal = goal_text

                            # Перевыбираем режим под новую цель
                            current_mode = select_learning_mode(session_context)
                            focus_area = get_focus_area_for_mode(current_mode, session_context)

                            # Перестраиваем промпт
                            system_prompt = build_mode_prompt(
                                mode=current_mode,
                                username=session_context.username,
                                level=session_context.language_level,
                                goal=goal_text,
                                focus_area=focus_area,
                                vocabulary_list=vocabulary_list,
                            )

                            await websocket.send_json({
                                "type": "goal_set",
                                "goal": goal_text,
                                "mode": current_mode.value,
                                "message": f"Great! I'll help you with {goal_text}. Let's start!",
                            })
                            print(f"[Pedagogy] Goal set: {goal_text}, new mode: {current_mode.value}")
                        except Exception as e:
                            print(f"Error setting goal: {e}")
                    continue

                # === ОБРАБОТКА СМЕНЫ РЕЖИМА ===
                if message.get("type") == "change_mode":
                    new_mode_str = message.get("mode", "").strip()
                    try:
                        new_mode = LearningMode(new_mode_str)
                        current_mode = new_mode
                        focus_area = get_focus_area_for_mode(current_mode, session_context)

                        system_prompt = build_mode_prompt(
                            mode=current_mode,
                            username=session_context.username,
                            level=session_context.language_level,
                            goal=session_context.goal or "improve English",
                            focus_area=focus_area,
                            vocabulary_list=vocabulary_list,
                        )

                        greeting = get_session_greeting(current_mode, session_context.username)
                        await websocket.send_json({
                            "type": "mode_changed",
                            "mode": current_mode.value,
                            "greeting": greeting,
                        })
                        print(f"[Pedagogy] Mode changed to: {current_mode.value}")
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

                    # Первое сообщение: проверяем, не указывает ли цель
                    if turn_count == 1 and not session_context.goal:
                        detected_goal = await detect_goal_from_message(user_text)
                        if detected_goal:
                            try:
                                await learning_plan_service.set_goal(user_id, detected_goal)
                                session_context.goal = detected_goal

                                # Перевыбираем режим
                                current_mode = select_learning_mode(session_context)
                                focus_area = get_focus_area_for_mode(current_mode, session_context)

                                system_prompt = build_mode_prompt(
                                    mode=current_mode,
                                    username=session_context.username,
                                    level=session_context.language_level,
                                    goal=detected_goal,
                                    focus_area=focus_area,
                                    vocabulary_list=vocabulary_list,
                                )
                                print(f"[Pedagogy] Detected goal: {detected_goal}")
                            except Exception as e:
                                print(f"Error setting detected goal: {e}")

                    # Проверяем запрос на смену режима в тексте
                    requested_mode = parse_user_mode_request(user_text)
                    if requested_mode and requested_mode != current_mode:
                        current_mode = requested_mode
                        focus_area = get_focus_area_for_mode(current_mode, session_context)
                        system_prompt = build_mode_prompt(
                            mode=current_mode,
                            username=session_context.username,
                            level=session_context.language_level,
                            goal=session_context.goal or "improve English",
                            focus_area=focus_area,
                            vocabulary_list=vocabulary_list,
                        )
                        print(f"[Pedagogy] Mode switched by user request: {current_mode.value}")

                    # Отправляем подтверждение получения текста
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "user",
                        "text": user_text,
                    })

                    # Генерируем ответ через LLM
                    try:
                        response_text = await llm.generate(
                            user_message=user_text,
                            system_prompt=system_prompt,
                            conversation_history=conversation_history,
                            max_tokens=250,  # Больше для объяснений и feedback
                        )
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"LLM error: {str(e)}",
                        })
                        continue

                    # Добавляем в историю
                    conversation_history.append({"role": "user", "content": user_text})
                    conversation_history.append({"role": "assistant", "content": response_text})

                    # Логирование
                    print(f"[Turn {turn_count}] Mode: {current_mode.value}")
                    print(f"[Turn {turn_count}] User: {user_text[:50]}...")
                    print(f"[Turn {turn_count}] Assistant: {response_text[:50]}...")

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
                        print(f"Warning: Could not extract vocabulary: {e}")

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
                                print(f"[RAG] Extracted {len(extracted)} memories from conversation")
                        except Exception as e:
                            print(f"Warning: Could not extract memories: {e}")

                    # Синтезируем и отправляем аудио
                    try:
                        audio_bytes = await tts.synthesize(response_text)
                        await websocket.send_json({
                            "type": "audio",
                            "data": base64.b64encode(audio_bytes).decode(),
                            "format": "mp3",
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"TTS error: {str(e)}",
                        })

                elif message.get("type") == "end":
                    # Финальное извлечение памяти из всей сессии
                    if conversation_history:
                        try:
                            extracted = await memory_pipeline.process_conversation(
                                user_id=user_id,
                                messages=conversation_history,
                                session_id=session_id,
                            )
                            if extracted:
                                print(f"[RAG] Final extraction: {len(extracted)} memories")
                        except Exception as e:
                            print(f"Warning: Could not extract final memories: {e}")

                    # Обновляем счётчик сессий
                    try:
                        await learning_plan_service.increment_session_count(
                            user_id,
                            mode=current_mode.value,
                            duration_minutes=turn_count * 2,  # Примерная оценка
                        )
                    except Exception as e:
                        print(f"Warning: Could not update session count: {e}")

                    # === Gamification: XP и Streak ===
                    try:
                        xp_service = XPService(db)
                        streak_service = StreakService(db)

                        # Check-in для streak
                        streak_result = await streak_service.check_in(user_id)
                        print(f"[Gamification] Streak: {streak_result['streak']} (max: {streak_result['max_streak']})")

                        # XP за завершение сессии
                        await xp_service.award_xp(
                            user_id,
                            XPEventKind.SESSION_COMPLETE,
                            session_id=session_id,
                        )

                        # Бонус за streak (если streak > 1)
                        if streak_result["streak"] > 1:
                            await xp_service.award_xp(
                                user_id,
                                XPEventKind.STREAK_BONUS,
                                session_id=session_id,
                                multiplier=streak_result["streak"],
                            )
                            print(f"[Gamification] Streak bonus: +{streak_result['streak'] * 5} XP")

                        # Бонус за первую сессию
                        if await xp_service.check_first_session(user_id):
                            await xp_service.award_xp(
                                user_id,
                                XPEventKind.FIRST_SESSION,
                                session_id=session_id,
                            )
                            print("[Gamification] First session bonus: +50 XP")

                        # Бонус за comeback (после 7+ дней)
                        if streak_result.get("is_comeback"):
                            await xp_service.award_xp(
                                user_id,
                                XPEventKind.COMEBACK,
                                session_id=session_id,
                            )
                            print("[Gamification] Comeback bonus: +20 XP")

                    except Exception as e:
                        print(f"Warning: Gamification error: {e}")

                    break

            except WebSocketDisconnect:
                print(f"Client disconnected: session {session_id}")
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
                        xp_service = XPService(db)
                        streak_service = StreakService(db)
                        streak_result = await streak_service.check_in(user_id)
                        await xp_service.award_xp(user_id, XPEventKind.SESSION_COMPLETE, session_id=session_id)
                        if streak_result["streak"] > 1:
                            await xp_service.award_xp(user_id, XPEventKind.STREAK_BONUS, session_id=session_id, multiplier=streak_result["streak"])
                    except Exception:
                        pass

                break

    except Exception as e:
        # Top-level error во время инициализации или message loop
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Server error. Please refresh the page.",
            })
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass  # Connection already closed

    finally:
        # Cleanup
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
