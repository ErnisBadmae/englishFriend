---
last_updated: 2026-05-06
status: Активный founder-learning sprint
---

# Roadmap

Это канонический план текущего цикла.

Связанные документы:
- [../MASTER_PROJECT_VIEW_2026-04-22.md](../MASTER_PROJECT_VIEW_2026-04-22.md)
- [../architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md](../architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md)
- [../operations/CURRENT_PRODUCT_STATE.md](../operations/CURRENT_PRODUCT_STATE.md)

## Тезис спринта

Этот цикл не про расширение продукта и не про полировку инфраструктуры ради самой инфраструктуры.

Вопрос цикла один:

`Сможет ли узкий ML/SWE interview-prep loop удержать хотя бы одного реального пользователя до session 2 и дать сигнал, что ему нужна session 3?`

## Зафиксированные решения

- Wedge: только `ML/SWE interview prep`
- Порядок: `discovery first`, потом build
- Базовая модальность: `text-first`
- Voice: `opt-in`, а не главный gate продукта
- Длина спринта: `2.5-3 недели`
- Порог успеха: хотя бы один пользователь доходит до `Tier 2` после `session 2`

## Уровни сигнала

- `Tier 1`: пользователь словами говорит, что хочет `session 3`
- `Tier 2`: пользователь соглашается или реально бронирует `session 3`
- `Tier 3`: пользователь готов платить или платит

Правило успеха цикла:
- одного `Tier 1` недостаточно
- цикл считается успешным только если хотя бы один пользователь достигает `Tier 2`
- если единственный `Tier 2` пришел только от warm-contact, результат считается provisional и должен быть перепроверен на cold user

## Фаза 0: Discovery до build

Цель: проверить, что боль реальна, до того как тратить спринт на реализацию.

Объем:
- провести 5 discovery calls с ML/SWE пользователями, готовящимися к интервью на английском
- минимум 1 discovery call должен быть `cold`
- спросить, как они готовятся сейчас, что болит сильнее всего, что уже пробовали и бросили, где корневая боль: speaking или answer structure, и за что они готовы платить
- завершить коротким readout `go / narrow / pivot / kill`

Правило решения:
- если speaking pressure реален, продолжаем текущий курс `text-first + voice-opt-in`
- если главный pain — structure / STAR / behavioral framing, wedge остается тем же, но приоритет смещается в качество typed answers и feedback
- если willingness to pay и return intent слабы почти у всех, спринт не продолжается по инерции

## Фаза 1: Узкие blockers

Цель: убрать дефекты, из-за которых продуктовое обучение становится шумным или ложным.

Объем:
- применить миграцию выравнивания `memory_kind` и проверить, что memory persistence снова работает
- закрыть `next_mission_choice -> session 2` continuity для interview path
- свести ownership runtime к одному mainline path:
  - `/api/v1/voice/chat/v2` остается публичным endpoint
  - `voice_runtime/controller.py` владеет turn loop и completion ordering
  - `voice_session/service.py` владеет bootstrap и persistence
  - `voice.py` остается тонкой endpoint-оберткой

Критерии:
- memory writes больше не падают из-за enum mismatch
- `session 2` уважает прошлый mission choice
- `session_complete` уходит один раз на mainline path

## Фаза 2: Text-first baseline

Цель: проверить ценность продукта, не делая STT/TTS узким горлышком.

Объем:
- typed/composer flow становится default interview path
- typed sessions получают текстовый ответ сразу
- на typed mainline нет автоматического TTS
- voice остается opt-in
- отдельный `Parakeet vs Vosk` benchmark в этом спринте не запускается

Критерии:
- interview onboarding -> mission -> evidence -> next mission проходит на typed mainline
- проверка ценности не зависит от качества browser Vosk или backend STT

## Фаза 3: Operator replay

Цель: сделать любой pilot session разбираемым по `session_id`.

Объем:
- добавить script-level replay artifact для одной сессии
- включить transcript, corrections, feedback, matching roadmap evidence и snapshot excerpt
- использовать `session_id` как общий ключ для логов и trace-контекста

Критерии:
- любую успешную или провальную pilot session можно собрать в один replay bundle
- debrief notes всегда ссылаются на конкретный `session_id`

## Фаза 4: Pilot validation

Цель: проверить, зарабатывает ли узкий цикл реальный follow-up session.

Объем:
- провести 3-5 pilot sessions после discovery и blocker-fix этапа
- минимум 1 pilot user должен быть `cold`
- собирать структурированный debrief:
  - что сломалось
  - felt relevance следующей mission
  - было ли достаточно text-first
  - добавил ли voice ценность
  - готовность к `session 2`
  - готовность к `session 3`
  - реакция на фиксированные pricing anchors

Критерии:
- минимум 3 реальных пользователя проходят `session 1`
- минимум 1 пользователь возвращается в течение 7 дней, проходит `session 2` до evidence persistence и достигает `Tier 2`

## Явные не-цели

В этом цикле не тратим время на:
- `workplace_communication` как mainline track
- отдельный `project_story_pack`, если только pilots не докажут, что это недостающий interview artifact
- `Parakeet vs Vosk` как отдельный benchmark-проект
- `Codex/Ollama` workflow
- широкие graph/vector/platform инициативы
- user-facing multi-agent или notebook surfaces
