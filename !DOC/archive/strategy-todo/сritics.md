Критический разбор EnglishFriend как продукта                                                                                  
                                                        
 Context

 Соло-разработчик (ты) строит AI-помощника для подготовки к собеседованиям, сейчас фокус — ML-позиции на западном рынке.
 Запрос: свежий критический взгляд "инвестор + топ-менеджер + архитектор + опытный разработчик". Я провёл аудит через три
 параллельных Explore-агента (продукт, архитектура, состояние) + сам прочитал MASTER_PROJECT_VIEW_2026-04-22.md,
 CURRENT_PRODUCT_STATE.md, BUSINESS_STRATEGY.md, GO_TO_MARKET.md, UNIT_ECONOMICS.md и пробежал git-историю.

 Уточнённые входные (ответы на мои вопросы):
 - Real users сейчас: 0 (только синтетические тесты)
 - Цель ближайших 90 дней: найти PMF (real users + retention)
 - Отношение к упрощению инфры: нужны аргументы для каждого решения

 Это меняет разбор: всё, что не приближает первого реального пользователя в ближайшие 30 дней — это балласт. Любое
 архитектурное решение должен проходить тест: "помогает ли это привести и удержать первого пользователя?"

 Ниже — мой честный разбор, не комплимент. Я постарался разделить, что у тебя сильно, что слабо, и где главные риски.

 ---
 Executive summary (одной строкой по роли)

 - Инвестор: ниша узкая, моат недоказанный, distribution неясен — это пока не бизнес, а технологически зрелый прототип в
 поисках PMF.
 - Топ-менеджер: продуктовая дисциплина выше среднего, исполнение сильное, но критическая нехватка — нет реальных пользователей
  и unit-economics построена на иллюзии "self-hosted = $0".
 - Архитектор: ~50% кодовой базы — преждевременная масштабная инфраструктура для нулевой нагрузки. Соло-dev не сможет это
 поддерживать год.
 - Разработчик: техническое качество приличное (eval-gates, тесты, миграции, observability), но три воркфлоу одновременно
 (/chat, /chat/v2, /chat/plex) и зависимость от LAN-сервера 192.168.0.18 — точка отказа.

 ---
 1. Инвестор / бизнес-аналитик

 Что хорошо

 - Чёткий wedge в MASTER_PROJECT_VIEW: "career English coach для Russian-speaking ML/AI". Не "AI tutor for everyone". Это
 редко.
 - Анти-roadmap явно описан: "no general tutor platform, no notebook workspace, no user-facing multi-agent shell". Это сильный
 продуктовый сигнал — автор сопротивляется scope creep.
 - Моat-формулировка career state → evidence → adaptive missions — внятная.

 Что не сходится

 (a) Документы рассинхронизированы — две разные стратегии живут параллельно

 - !DOC/strategy/BUSINESS_STRATEGY.md (Feb 2026): "Russian-speakers learning English, freemium Telegram, $12.99/мес, moat =
 Russian-specific errors (W/V, TH, articles)". Это language-learning product, конкуренты — TalkPal, Speak, ELSA.
 - !DOC/MASTER_PROJECT_VIEW_2026-04-22.md (Apr 2026): "career English coach для ML/AI, moat = evidence-driven adaptive
 missions". Это career-prep product, конкуренты — Pramp, Interviewing.io, Hello Interview, ChatGPT Voice + Custom GPT.
 - Эти продукты выглядят похоже, но имеют разный TAM, разные каналы, разный pricing, разные unit economics. Сейчас в коде живёт
  второй, а в business-документации частично — первый.

 (b) TAM реалистично маленький

 - Russian-speaking ML/AI engineers, готовящиеся к собесам на западные компании = ~10–30K активных таргет-пользователей.
 - При 1% conversion в платящих → 100–300 платящих → $1.3–4K MRR при $12.99/мес.
 - Это не венчурный бизнес. Это lifestyle-business / side-revenue, в лучшем случае.
 - Чтобы стать venture-scale, либо нужен другой TAM (не только русскоязычные / не только ML), либо B2B-трек (но компаний
 нанимающих "career coaches" мало), либо принципиально другой ARPU.

 (c) Конкурентная позиция слабее чем кажется

 Главный вопрос инвестора: "почему пользователь не откроет ChatGPT Voice?"

 - ChatGPT Voice ($20/мес) сейчас умеет: говорить, помнить через ChatGPT Memory, сыграть mock interview, дать критику, иметь
 Custom GPT "ML Interview Coach".
 - Преимущества EnglishFriend, которые автор заявляет:
   - Structured evidence loop → не виден за первые 5 минут, проявляется через недели использования.
   - 200мс latency (vs 800мс у API-стэков) → на мобильном через 4G пользователь не различит.
   - L1-specific error detection → не реализовано в текущем коде, только заявлено в BUSINESS_STRATEGY.
 - Брeнд-доверие у OpenAI намного выше; пользователь, у которого один шанс попробовать, выберет известное.

 (d) Distribution problem не решён

 - GO_TO_MARKET.md упоминает Telegram + Habr + IT-каналы.
 - В git-истории за 60 дней — 0 коммитов про маркетинг/landing/SEO/контент. Все ресурсы идут в продукт.
 - Соло-разработчик не может одновременно: писать код, поддерживать инфру, делать marketing, делать research. Distribution
 провисает.

 Инвесторский вердикт

 Если бы ты пришёл ко мне просить seed: "нет" в текущем виде. Слишком ранняя стадия, нет signals спроса, инфра-overhead
 высокий. Я бы советовал прийти после: 50 real users, 10 платящих, 30-дневный retention >20%.

 ---
 2. Топ-менеджер / продакт-аналитик

 Что сильно

 - Eval-gate как релизный контроль (scripts/run_product_synthetic_eval.py --scenario-set mainline) — это редкая дисциплина для
 соло-проекта.
 - Routing policy и scope_status ловят расфокус на этапе onboarding — отсекают "anxiety only / grammar only / vague" из
 career-loop. Это правильный продуктовый выбор.
 - Только 3 миссии активны (foundation_speaking_drill, stakeholder_explanation_drill, technical_project_walkthrough) — не 10
 режимов. Дисциплина.
 - Anti-roadmap в стратегии (vocabulary_drill, grammar_rescue — secondary). Это значит, что ты УЖЕ один раз пережил pivot и
 научился говорить "нет".

 Главные продуктовые разрывы (что заявлено ≠ что работает)

 ┌────────────────────────────────────────┬────────────────────────────────────────────────────────────────────────────────┐
 │                Заявлено                │                                   Реальность                                   │
 ├────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
 │ "Адаптивный coach с emotion-tracking"  │ Emotion-extraction нет в коде. Это zombie-feature.                             │
 │ (SYSTEM_OVERVIEW)                      │                                                                                │
 ├────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
 │ "Гибридная память Postgres + Vector +  │ Hot path только Postgres; Qdrant best-effort async; Neo4j вообще не в          │
 │ Graph"                                 │ onboarding/learning loop.                                                      │
 ├────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
 │ "FSRS spaced repetition vocabulary"    │ Не виден в product-critical path.                                              │
 │ (CLAUDE.md)                            │                                                                                │
 ├────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
 │ "PersonaPlex full-duplex 200ms voice"  │ Главный аргумент UNIT_ECONOMICS. В eval-сценариях не используется. Mainline    │
 │                                        │ воркфлоу — /chat/v2 через Vosk+Groq+edge-tts.                                  │
 ├────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
 │ "Russian-speaker L1 errors (W/V, TH,   │ Не реализовано в pronunciation analysis. Pace/pause evidence явно "missing" в  │
 │ articles)"                             │ Known Issues.                                                                  │
 ├────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
 │ "Vacancy upload + interview pack +     │ Упомянуто в What Works Now, но не покрыто mainline eval — нет gate-проверки    │
 │ paid intent"                           │ что эти фичи работают end-to-end.                                              │
 └────────────────────────────────────────┴────────────────────────────────────────────────────────────────────────────────┘

 Demo readiness — 6/10

 - 30-минутный demo возможен, но fragile: если 192.168.0.18:8000/v1 не отвечает, mainline воркфлоу падает с пустым ответом на
 первом ходе (Known Issues, line 97).
 - Frontend есть (VoiceChatV2.tsx, 37KB), но browser-level smoke не запускался (Known Issues, line 91) — UI может ломаться
 непредсказуемо.
 - Evidence-loop UI видим только после нескольких completed missions (Known Issues, line 100) — cold-start пользователь не
 видит core value.

 Что меряется vs что важно

 - Меряется: routing accuracy, mission handoff, snapshot freshness, eval pass rate.
 - НЕ меряется: STT accuracy на broken English (Vosk vs Parakeet benchmark "pending"), retention, time-to-aha, ни одной
 user-metric потому что нет users.
 - Это значит, что текущие eval-результаты подтверждают что "система не сломана", но не подтверждают что продукт ценен.

 Продуктовый вердикт

 Дисциплина и execution выше среднего. Но текущий phase = "product completeness theater" — допиливание eval gates на
 синтетических сценариях вместо встречи с реальными пользователями. Каждая неделя без real-user feedback увеличивает риск что
 весь evidence-loop окажется не нужен пользователю в той форме, в которой ты его построил.

 ---
 3. Архитектор / tech lead

 Stack inventory (что реально работает vs зомби)

 Активное ядро (~50% LOC, оправдано):
 - app/agent/nodes_v2/ (~3200 LOC): LangGraph onboarding/learning — core product
 - app/services/ (~6400 LOC): business logic, pedagogy, learning plans, evidence
 - app/api/voice.py (1902 LOC, single file — велик): WebSocket эндпоинты
 - PostgreSQL canonical layer: правильная архитектура

 Зомби-инфраструктура (~30% LOC, не оправдана для текущей стадии):
 - sync-vector/ (316 LOC) + sync-graph/ (266 LOC) — Kafka-based CDC pipelines под 0 пользователей
 - cdc/ + docker-compose.cdc.yml — Debezium connectors которые редко регистрируются
 - Neo4j integration: 4 упоминания на весь codebase, все в recovery.py
 - RLS + partitions + materialized views: технически красиво, но мертвый код для нулевой нагрузки
 - Три voice endpoints одновременно (/chat, /chat/v2, /chat/plex) — два из них legacy/experimental, поддерживаются параллельно

 5 главных мест overengineering

 1. CDC через Kafka+Debezium вместо прямых вызовов. Для 0 пользователей это +200% сложности эксплуатации, +0 ценности. Когда
 придут 1000 одновременных пользователей — тогда CDC оправдается.
 2. Neo4j. Графовые отношения (User-Topic-Emotion) не используются в routing/session decisions. Чисто артефакт прошлой
 архитектуры.
 3. PostgreSQL partitioning (sessions_2025_10, utterances_p0..p7, xp_events_2025_10). Оправданно для миллионов записей. Для
 тестового user-id — это maintenance-tax при каждой миграции.
 4. PersonaPlex как заявленный mainline. UNIT_ECONOMICS обещает 92-98% gross margin благодаря self-hosted. Реальность: один RTX
  5060 Ti 16GB на 192.168.0.18 — это домашний сервер, не production. 5 одновременных пользователей убьют GPU, downtime
 неизбежен. И "self-hosted = $0" не учитывает твоё время на поддержание.
 5. Три voice endpoints. /chat legacy, /chat/v2 mainline, /chat/plex экспериментальный — поддерживать все три значит
 тестировать все три. Если один honest mainline endpoint, остальные надо удалить или /archive.

 3 оправданных усложнения

 1. LangGraph + педагогические ноды — это core product, без альтернативы.
 2. PostgreSQL-canonical с Qdrant как async best-effort — это правильный паттерн, недавно явно зафиксированный (line 53
 CURRENT_PRODUCT_STATE).
 3. Synthetic eval-gate + categorized checks — это золотой стандарт CI для AI-продукта. Не выкидывай.

 Зависимость от 192.168.0.18 — точка отказа

 - vLLM endpoint, PersonaPlex GPU, Qdrant, Neo4j — всё на одном LAN-сервере.
 - Если сервер уходит в ребут / провайдер сменил IP / GPU драйвер обновился — продукт мёртв.
 - Для demo инвестору / клиенту / community — это must-be-cloud или принимать downtime как норму.
 - В Known Issues это явно записано (line 97), но в UNIT_ECONOMICS self-hosted всё ещё преподносится как moat.

 Архитекторский вердикт

 Если бы я начинал сегодня (and you were 1 engineer):

 Выкинул бы целиком:
 - sync-vector/, sync-graph/, cdc/, docker-compose.cdc.yml, Neo4j, Kafka, Debezium
 - /chat (legacy) и /chat/plex (PersonaPlex) endpoint-ы; оставил бы один /chat/v2
 - Partitions / RLS до момента, когда >1000 users
 - materialized views, partition management scripts

 Оставил бы:
 - PostgreSQL + SQLAlchemy
 - Qdrant (прямые вызовы из app/services/, не через Kafka)
 - LangGraph + nodes_v2
 - Synthetic eval framework
 - Frontend (VoiceChatV2)
 - Один LLM provider (Groq / OpenAI) как mainline, vLLM как dev/cost-optimization на втором месте

 Это бы сократило кодовую базу на ~30–40%, ускорило onboarding и оставило место для продуктовых экспериментов.

 ---
 4. Опытный разработчик

 Что качественно

 - Типизация (Pydantic schemas), async-first, миграции упорядочены, логирование с request-id, Prometheus metrics, тесты (~498
 test-функций, 47 test-файлов).
 - Git-история чистая, осмысленные коммиты с conventional commit стилем.
 - Truth-state rules в .claude/rules/ — редкость, что соло-dev держит canonical rules для агентов.
 - Documentation continuity rule (one canonical CURRENT_PRODUCT_STATE.md) — правильная гигиена.

 Что бьёт по сопровождаемости

 - app/api/voice.py = 1902 строки в одном файле. Это рефакторинг-кандидат №1: разделить на бутcrap, реалтайм, WebSocket
 handlers.
 - app/agent/nodes_v2/onboarding.py = 1974 строки, learning.py = 1223 строки. Это violation of single-responsibility — внутри
 уже много под-функций которые просятся в отдельные модули.
 - 5 docker-compose файлов (docker-compose.yml, .cdc.yml, .vector.yml, .graph.yml, .partitions.yml, .personaplex.yml).
 Локальный setup непредсказуем — какой стек где запускать.
 - Тесты есть, но pytest tests -q имеет "unrelated legacy failures outside the current wedge" (line 95 Known Issues). Это
 означает, что тестовый CI не зелёный полностью — со временем красные тесты привыкают игнорировать, и реальная регрессия
 проскочит.

 Зависимости и риски эксплуатации

 - Python + Docker + Postgres + Vosk WASM + Groq SDK + edge-tts + (опционально) Kafka, Debezium, Neo4j, Qdrant, PersonaPlex
 websockets.
 - Frontend: React + Vite + Tailwind, отдельный TS стек.
 - Если ты заболеешь на 2 недели, продукт стоит. Нет резерва.

 ---
 5. Главные риски (топ-5 по уязвимости)

 1. Нет реальных пользователей. Synthetic eval не доказывает PMF. Без 10–20 пользователей в feedback loop в течение месяца —
 все архитектурные и продуктовые решения остаются гипотезами.
 2. Single point of failure — 192.168.0.18. Любой demo может умереть в неподходящий момент.
 3. Расхождение стратегий (BUSINESS_STRATEGY vs MASTER_PROJECT_VIEW). Это создаст путаницу при общении с инвесторами /
 партнёрами / маркетинге — ты сам не до конца определился, что продаёшь.
 4. Distribution не решён. Готовый продукт без потока юзеров — это никто. Соло-разработчик без сети должен тратить минимум 30%
 времени на community/marketing/content, иначе продукт не найдут.
 5. Конкуренция с ChatGPT Voice + Custom GPT. Ответ на вопрос "почему не ChatGPT" должен быть очевиден в первые 90 секунд
 использования. Сейчас — нет.

 ---
 6. PMF-first action plan (90 дней, 0 → 10–30 active users)

 Принцип фильтрации работы

 Каждая задача проходит один тест: "приведёт ли это к первому/удержит ли это первого пользователя в ближайшие 30 дней?"

 - Да → делаем сейчас.
 - Нет → замораживаем, без обсуждения "ну может потом пригодится".

 При 0 пользователях у тебя нет данных, чтобы оптимизировать что-либо кроме вопроса "почему люди не приходят / не
 возвращаются". Всё остальное — спекуляция.

 Неделя 1–2: устранить блокеры для первого реального пользователя

 1. Cloud-fallback для LLM (приоритет №1). Сейчас весь mainline воркфлоу падает если 192.168.0.18:8000/v1 недоступен. Это
 блокирует любой outreach: ты пишешь "попробуй мой продукт" → пользователь заходит → пустой ответ на первом ходе → больше не
 возвращается. Решение: сделать Groq (llama-3.3-70b-versatile) primary для prod, vLLM остаётся для local dev. Это ~3–6 часов
 работы (provider switch + .env config + smoke-test).
 2. Browser smoke-test всего пути (Known Issues, line 91). Прямо сейчас никто не проверял что real user в Chrome / Safari /
 Edge на iOS пройдёт onboarding → first mission → session_end → snapshot. Высокий риск что сломается на этапе аудио. Это 1 день
  полной ручной проверки + фиксы.
 3. Унифицировать стратегию-документ. Перепиши BUSINESS_STRATEGY.md под текущую версию из MASTER_PROJECT_VIEW.md (career
 English для ML/AI). Удали или /archive старую версию про "Russian-speaker errors W/V, TH". Без этого ты сам не сможешь чётко
 рассказать продукт первым пользователям.

 Неделя 2–4: первые 10 живых пользователей

 4. Outreach в 5 каналов. Telegram-чаты: ODS.ai, Data Karpov, ML Recruiting, Школа Karpov, Yandex DS chat, релокация-чаты "RU
 IT to EU/US". Запостить честно: "Делаю AI-помощника для подготовки к собесам на ML-позиции на западе на английском. Ищу 10
 человек попробовать бесплатно за честную обратную связь". Не ходи в крупные каналы (>50K) — там тебя забанят за рекламу. Ходи
 в нишевые чаты ~500–5000 человек где тебя знают или комьюнити дружелюбное.
 5. 30-секундный value-proof loom-видео. До outreach запиши: "вот это ChatGPT даёт когда ты говоришь 'mock me ML interview'",
 "вот это даёт EnglishFriend". Если разница не очевидна за 30 секунд — продукт ещё не готов идти к пользователям.
 6. Простая метрика "пришёл и вернулся". Не нужен Mixpanel. PostHog free / простой лог user_id, session_count, last_session_at
 в Postgres достаточно. Цель D7: 30%+ из 10 пришедших возвращаются хотя бы один раз.

 Неделя 4–8: цикл feedback → фиксы

 7. Личный созвон с каждым из первых 10 пользователей (15 минут). Узнай: где застряли, что было непонятно, что бы они сказали
 другу, заплатили бы $5/$10/$20. Это даст качественные данные которые ни один eval не даст.
 8. Если D7 retention < 30% → проблема скорее всего НЕ в evidence-loop (он становится виден только после 3–4 сессий). Проблема
 в первом ходе: микрофон не работает / агент не понимает / диалог скучный / value не очевидно. Чини первые 90 секунд опыта.
 9. Если D7 retention 30–50% → продукт работает для каких-то пользователей. Сегментируй: кто возвращается, что у них общего.
 Это твой ICP.

 Неделя 8–12: первая монетизация (если retention здоровый)

 10. Включить paid-intent capture (он уже есть в коде). Не платный продукт ещё, а кнопка "Я бы заплатил $X/мес за это, оставьте
  контакт когда запустите". Если из 30 active users 5+ нажимают → есть spit на pricing.
 11. Только тогда возвращайся к технической полировке: PersonaPlex, classifier promotion to gate, Parakeet STT benchmark,
 partitions/RLS. Ни одно из этих решений нельзя делать осмысленно без real-user данных.

 Что НЕ делать в эти 90 дней

 - Не трогать Kafka / Debezium / sync-vector / sync-graph / Neo4j (см. секцию 7).
 - Не пилить новые learning modes (vocabulary, grammar, etc.) — у тебя 3 миссии и этого достаточно для 10–30 пользователей.
 - Не делать собственный landing-page-design на 2 недели. Notion-страница / простой Tilda за 2 часа достаточно.
 - Не делать Telegram Mini App пока не докажешь что web-версия работает (TMA = ещё один stack для отладки).

 ---
 7. Развёрнутая аргументация по каждому инфра-компоненту

 Ты сказал "нужны аргументы" — поэтому каждый компонент с конкретными критериями: что он стоит сегодня, что приносит, и точный
 триггер "когда оправдано вернуть".

 7.1 Kafka + Debezium + cdc/ + docker-compose.cdc.yml

 - Что он делает: захватывает изменения в Postgres (CDC) и шлёт в Kafka, откуда sync-vector пишет в Qdrant, sync-graph — в
 Neo4j.
 - Что стоит сегодня:
   - Сложность поднять локально (5 контейнеров вместо 1)
   - Поломки Debezium connector при schema changes — отдельная категория багов
   - Время на регистрацию connector-ов после каждой миграции
   - Onboarding нового контрибьютора замедляется на дни
 - Какую ценность приносит сегодня: ноль. У тебя 0 пользователей, 0 записей в день, никакой нагрузки нет. Ты можешь делать
 write в Postgres → следом write в Qdrant прямым async вызовом из app/services/.
 - Когда CDC оправдан: когда у тебя >1000 активных пользователей и >10K events/sec в Postgres, и ты не можешь себе позволить
 блокировать write-path синхронной записью в Qdrant/Neo4j. Это уровень series-A продукта, не PMF-search.
 - Вердикт: переноси cdc/, sync-vector/, sync-graph/, docker-compose.cdc.yml в /archive/infra-future/. Заменяй прямыми вызовами
  в app/services/ai/memory_pipeline.py (он уже делает background sync — там осталось 1 шаг до полного отказа от Kafka).

 7.2 Neo4j (graph database)

 - Что он делает: хранит связи User-Topic-Emotion-Session для будущей графовой аналитики.
 - Что стоит сегодня: контейнер на 1.5GB RAM в docker-compose, отдельный язык (Cypher), отдельные миграции.
 - Какую ценность приносит сегодня: 0. Grep по коду показывает 4 упоминания, все в recovery.py и async sync. Ни одно
 routing/learning/onboarding решение не использует graph.
 - Когда оправдан: когда у тебя есть продуктовый use case "найти пользователей с похожими интересами" / "рекомендовать миссию
 на основе графа социальных связей". У тебя такого нет и не планируется в anti-roadmap.
 - Вердикт: целиком убрать. Это самый чистый "пилили потому что круто", без продуктовой потребности.

 7.3 PersonaPlex (self-hosted full-duplex voice)

 - Что он делает: NVIDIA Moshi 7B на твоём LAN-сервере 192.168.0.18:8998, обещает 200мс latency.
 - Что стоит сегодня:
   - Зависимость от домашнего GPU (он один, RTX 5060 Ti 16GB)
   - 5+ одновременных пользователей убьют GPU
   - Нет fallback — если сервер ребутается, mainline /chat/plex мёртв
   - Поддержка отдельного docker-compose, отдельного протокола, отдельного fallback-механизма в app/api/voice.py
   - В CURRENT_PRODUCT_STATE PersonaPlex даже не в mainline eval — реальный mainline это /chat/v2 (Vosk+Groq+edge-tts)
 - Какую ценность приносит сегодня: концептуальную — "у нас self-hosted voice с маржой 92-98%". Реальную для пользователя —
 ноль, потому что 200мс vs 800мс на мобильном через 4G не различимы (RTT сети сама съедает разницу).
 - Когда оправдан: когда у тебя >$5K MRR, есть нанятый DevOps, и cost API-провайдеров (Groq + Deepgram + ElevenLabs) >$500/мес.
  Тогда self-host окупает себя.
 - Вердикт: заморозить. Удалить /chat/plex endpoint, оставить только /chat/v2. PersonaPlex код не удалять (труд жалко), но
 переместить в /experimental/ и убрать из mainline path. Перепиши UNIT_ECONOMICS.md без претензии на "self-hosted = $0" — это
 пока неправда.

 7.4 Postgres partitioning (sessions / utterances / xp_events) + RLS

 - Что делает: партиции по месяцу/хэшу для масштабирования; Row-Level Security для изоляции данных пользователей.
 - Что стоит сегодня: каждая миграция теперь должна знать про партиции. scripts/manage_partitions.sh нужно запускать. RLS
 требует SET application.user_id иначе query возвращает пусто (твой собственный Common Issues пункт 3).
 - Какую ценность приносит сегодня: 0. Ты единственный test user, partition-overhead больше пользы.
 - Когда оправдано: партиции — когда таблица >10M записей (для sessions это >100K активных пользователей по 100 сессий каждый).
  RLS — когда есть multi-tenancy между разными компаниями (B2B). Сейчас ни того, ни другого.
 - Вердикт: НЕ откатывать миграции (это рискованно), но заморозить пилёжку partition-management. Не трогай
 004_partition_management.sql, не запускай cron docker-compose.partitions.yml. Если partitions начнут чудить на dev — просто
 truncate таблиц и делай заново без партиций для local dev.

 7.5 Voice endpoints (/chat, /chat/v2, /chat/plex)

 - Что делает: три разные реализации voice-WebSocket в app/api/voice.py (1902 строки!).
 - Что стоит сегодня: тестировать надо все три, поддерживать все три, баги множатся.
 - Какую ценность приносит сегодня: mainline один — /chat/v2. Остальные — legacy/experimental.
 - Вердикт:
   - /chat (legacy) — удалить целиком, переименовать /chat/v2 → /chat. Frontend перенаправить.
   - /chat/plex — переместить в /experimental/, в README отметить "не для продакшена".
   - Это сократит voice.py минимум на 30–40%.

 7.6 Что точно оставить (контр-аргумент против тотального cutting)

 ┌─────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────┐
 │                  Компонент                  │                            Почему оставить                            │
 ├─────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
 │ PostgreSQL + миграции 000–002, 005, 006     │ Core canonical layer, async-async-friendly, правильный выбор          │
 ├─────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
 │ Qdrant + app/services/ai/memory_pipeline.py │ Прямые вызовы, без Kafka. Vector search для memory работает           │
 ├─────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
 │ LangGraph + nodes_v2/                       │ Это твой core product brain. Не трогать                               │
 ├─────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
 │ Synthetic eval framework                    │ Золотой стандарт CI. Расширять, не сокращать                          │
 ├─────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
 │ vLLM как dev/cost-fallback                  │ Для local dev оставить; для prod — Groq primary                       │
 ├─────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
 │ Frontend VoiceChatV2 + Home + Progress      │ Уже работает, не переписывать пока retention не докажет необходимости │
 ├─────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
 │ .claude/rules/ + truth-state docs           │ Дисциплина которую трудно вернуть после потери                        │
 └─────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────┘

 7.7 Сводка "что выкинуть / заморозить / держать"

 ┌──────────────┬────────────────────────────────────────────────────────────────────┬────────────────────────────────────┐
 │  Категория   │                                Что                                 │              Действие              │
 ├──────────────┼────────────────────────────────────────────────────────────────────┼────────────────────────────────────┤
 │              │ cdc/, sync-vector/, sync-graph/, docker-compose.cdc.yml,           │                                    │
 │ Выкинуть     │ docker-compose.vector.yml, docker-compose.graph.yml, Neo4j         │ git mv в /archive/infra-future/    │
 │              │ integration, graph/ папка                                          │                                    │
 ├──────────────┼────────────────────────────────────────────────────────────────────┼────────────────────────────────────┤
 │              │ PersonaPlex (/chat/plex, personaplex_*.py,                         │ оставить код, не трогать, не       │
 │ Заморозить   │ docker-compose.personaplex.yml), partition management cron,        │ упоминать в product-критичных      │
 │              │ materialized views, RLS активная разработка                        │ доках                              │
 ├──────────────┼────────────────────────────────────────────────────────────────────┼────────────────────────────────────┤
 │ Удалить      │ /chat legacy endpoint, упоминания FSRS/emotion-tracking из         │ прямой git rm + редактирование .md │
 │              │ SYSTEM_OVERVIEW.md и CLAUDE.md (zombie features)                   │                                    │
 ├──────────────┼────────────────────────────────────────────────────────────────────┼────────────────────────────────────┤
 │ Держать и    │ PostgreSQL canonical, Qdrant прямые вызовы, LangGraph, synthetic   │ core продукта                      │
 │ развивать    │ eval, frontend VoiceChatV2, truth-state docs                       │                                    │
 └──────────────┴────────────────────────────────────────────────────────────────────┴────────────────────────────────────┘

 7.8 Сколько LOC это сократит

 Грубо: ~600 LOC в sync-services + ~200 LOC PersonaPlex provider/health + ~300 LOC /chat legacy в voice.py + 50 LOC graph
 integrations + 5 docker-compose файлов. Итого: ~1100–1500 LOC + значительное сокращение когнитивной нагрузки.

 Это эквивалентно "у тебя появилось 2-3 недели разработческого времени в месяц обратно".

 ---
 8. Что у тебя по-настоящему сильно (не недооценивай)

 - Продуктовая дисциплина: anti-roadmap, scope gate, sticky primary_context, three missions only — это уровень senior PM.
 - Eval-as-release-gate: 95% продуктовых стартапов не имеют синтетических end-to-end eval. У тебя есть.
 - Truth-state docs (!DOC/operations/CURRENT_PRODUCT_STATE.md + .claude/rules/): редко вижу у соло-dev.
 - Honest known-issues: ты сам пишешь что Vosk слаб, что browser smoke не run, что classifier в shadow. Это сигнал зрелости.
 - PostgreSQL-canonical architecture с async слоями — правильное архитектурное решение.

 Это база. Если бы у тебя ещё было 10 активных пользователей и retention-data — это был бы серьёзный seed-кейс.

 ---
 Критические файлы

 Этот разбор основан на:
 - /Users/macbook/Desktop/englishFriend/!DOC/operations/CURRENT_PRODUCT_STATE.md (line 31–110)
 - /Users/macbook/Desktop/englishFriend/!DOC/MASTER_PROJECT_VIEW_2026-04-22.md
 - /Users/macbook/Desktop/englishFriend/!DOC/strategy/BUSINESS_STRATEGY.md
 - /Users/macbook/Desktop/englishFriend/!DOC/strategy/GO_TO_MARKET.md
 - /Users/macbook/Desktop/englishFriend/!DOC/strategy/UNIT_ECONOMICS.md
 - app/api/voice.py, app/agent/nodes_v2/, app/services/, sync-vector/, sync-graph/
 - git log за 90 дней (61 коммит)

 ---
 Verification (как ты сможешь проверить мои тезисы сам)

 1. "Расхождение стратегий": открой одновременно BUSINESS_STRATEGY.md line 1–80 и MASTER_PROJECT_VIEW.md "Product Thesis". Это
 разные продукты.
 2. "PersonaPlex не в mainline": grep -r "personaplex" tests/ scripts/run_product_synthetic_eval.py — не найдёшь.
 3. "Single point of failure": останови 192.168.0.18:8000, запусти scripts/run_product_synthetic_eval.py --scenario-set
 mainline — упадёт с пустым content на первом ходе.
 4. "Зомби-инфра": grep -rn "sync_vector\|sync_graph\|debezium\|kafka" app/ — увидишь, как мало это используется из core app.
 5. "Distribution не решён": git log --oneline --since="60 days ago" -- "*landing*" "*marketing*" "*content*" — пусто.