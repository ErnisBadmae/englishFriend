# 🔒 ЗАМОРОЖЕН — Self-Use + Portfolio Plan — EnglishFriend как личный инструмент

> ## Статус: устарел, не использовать
>
> План был написан 2026-05-15 для сценария "автор продолжает поиск работы и использует EnglishFriend как portfolio". С 2026-05-18 автор стартует full-time как архитектор в Центре государственной экспертизы СПб. Это даёт значительно более сильный hiring signal, чем self-use продукта без пользователей. Поэтому план потерял актуальность.
>
> **EnglishFriend остаётся frozen** на новые фичи (см. memory `project_state.md`), используется только как:
> 1. Source codebase для extract'ов (eval framework → `scenario-gate`)
> 2. Reference implementation в README будущих OSS библиотек
> 3. Опционально — личный инструмент для тренировки английского 1-2ч/неделю
>
> **Актуальные документы**:
> - `SCENARIO_GATE_EXTRACT_PLAN.md` — главный план extract
> - `OSS_ROADMAP.md` — 18-месячный roadmap
> - `SCENARIO_GATE_TEAM_PITCH.md` — материал для команды Центра госэкспертизы
>
> Этот файл оставлен в репозитории как **исторический документ**. Не использовать как actionable план без явного подтверждения автора.

---

# (Заархивированный план ниже — для исторического контекста)

> **Назначение этого файла** (исходное): альтернативный план развития EnglishFriend для сценария "добить продукт для себя + использовать как portfolio для job search". Self-contained, можно шарить между сессиями (Claude, Codex, человек).
>
> **Отношение к другим планам** (исходное):
> - `OSS_EXTRACT_PLAN.md` — extract узкой OSS lib + posts (6 недель, narrow audience LangGraph community) — тоже заморожен
> - **Этот план** — добить полный продукт + ежедневное использование + portfolio packaging (8–14 недель, recruiters/interviewers)
> - Планы совместимы: можно делать последовательно или комбинировать (см. section 7)

---

## 0. Context

**Автор**: соло-разработчик ML/AI, русскоязычный, английский B1, ищет работу в западной компании. Состояние EnglishFriend: 0 пользователей, ~10K LOC, активная разработка ~12 недель.

**Время на план**: 15–20 часов в неделю.

**Срочность apply**: не срочно (runway появился).

**Целевые позиции**: пока не определены — Phase 0 в этом плане их определяет.

**Цель плана**: превратить EnglishFriend в (a) реально работающий персональный инструмент для подготовки к собесам, (b) impressive portfolio artifact для hiring conversations, (c) защищаемую архитектурную работу для technical interviews.

**Принцип**: **"добить для себя" ≠ "найти PMF"**. Не нужны 30 пользователей, distribution, монетизация, unit economics. Нужно — daily use + demo-readiness + defensible architecture.

---

## 1. Стратегия одной строкой

Cut overengineering → make it useful for me daily → package for recruiters → apply with it as live demo.

---

## 2. Принципиальная разница со старым extract-планом

| | OSS extract план | Self-use + Portfolio (этот) |
|---|---|---|
| Audience | LangGraph community (тысячи) | Recruiters + interviewers (десятки) |
| Артефакт | Маленькая focused lib + 4 поста | Полный working продукт + demo + write-ups |
| Time | 6 недель × 7ч | 8–14 недель × 15–20ч |
| Hiring signal | Concrete OSS contribution | Full-stack product thinking + depth |
| Лучше для | ML platform / infra / lib roles | Applied AI / startup / product engineer / AI engineer roles |
| Daily use автором | Нет | Да, ежедневная тренировка |

---

## 3. Phase 0 (Week 0): Определить целевые компании и позиции

Без этого весь продукт оптимизируется под воображаемого пользователя. **Этот Phase критичен**, не пропускать.

- Составить list 10–20 целевых компаний (Anthropic, OpenAI, Mistral, Cohere, Hugging Face, ElevenLabs, Speak, Yoodli, NotebookLM team, scale-up AI startups).
- Для каждой найти 1–2 open job descriptions (Applied AI Engineer, AI Engineer, ML Engineer, Member of Technical Staff).
- Из job descriptions выделить **общие требования**: LangChain/LangGraph, vector DB, voice/multimodal, evals, production deployment, RAG, fine-tuning.
- Это даёт **точный target** для следующих фаз: какие части продукта полировать, какие interview questions добавить.

**Deliverable**: `TARGET_ROLES.md` (private, не в git) с 10–20 строками "Company — Role — Key requirements".

---

## 4. Phase 1 (Week 1–2): Cut overengineering

На собесе **overengineered архитектура без пользователей = красный флаг**. Interviewer спросит "почему Kafka при 0 пользователей" — у тебя должен быть ответ "я её убрал когда понял что не нужна", а не "я её до сих пор поддерживаю".

### Что архивировать в `/archive/`

- `cdc/` — Debezium connectors, не используются в hot path
- `sync-vector/` — Kafka → Qdrant pipeline, не нужен под 0 пользователей
- `sync-graph/` — Kafka → Neo4j pipeline, не нужен
- `graph/` — Neo4j schema/queries, не используется в product-critical path
- `docker-compose.cdc.yml`, `docker-compose.vector.yml`, `docker-compose.graph.yml`
- `docker-compose.personaplex.yml` — если не используешь PersonaPlex сам
- `app/services/ai/personaplex_provider.py`, `personaplex_health.py` — если не используешь

### Что удалить (не архивировать, удалить)

- `/chat` legacy endpoint в `app/api/voice.py` (~300 LOC)
- `/chat/plex` endpoint если не пользуешься
- Упоминания FSRS spaced repetition в `CLAUDE.md`, `SYSTEM_OVERVIEW.md` (zombie feature)
- Упоминания emotion-tracking в docs (zombie feature)
- Упоминания Russian-specific errors W/V, TH, articles в `BUSINESS_STRATEGY.md` (старая стратегия)

### Что переписать

- Корневой `README.md` — 1 страница: что это, для кого, архитектурная диаграмма, как запустить локально
- `SYSTEM_OVERVIEW.md` — отражает реальную минимальную архитектуру, не aspirational
- `BUSINESS_STRATEGY.md` — синхронизировать с `MASTER_PROJECT_VIEW` (career English coach для ML/AI), убрать противоречия

### Deliverables Phase 1

- [ ] Repo size сократился на ~30%
- [ ] Корневой README выглядит professional для GitHub visitor
- [ ] Можешь объяснить каждое архитектурное решение в 1 предложении

---

## 5. Phase 2 (Week 3–6): Make it useful for YOU specifically

Теперь продукт оптимизируется под одного пользователя — тебя. Это значит:

### 5.1 Загрузи свой реальный контекст

- Твой CV в формате который продукт может прочитать (PDF или structured Markdown)
- 2–3 job descriptions из Phase 0 (как `vacancy_notes`)
- 2–3 твоих реальных проекта в виде `project_notes` (architecture, decisions, results)
- Это включает уже существующие фичи в проекте (`vacancy upload`, `project notes`, `project_story_pack`)

### 5.2 Расширить question bank под реальные ML позиции

В `app/data/interview_questions.py` сейчас 6 базовых вопросов. Расширь до ~30–50:

- **ML system design**: "Design a recommendation system for X", "How to serve 70B model in production", "Real-time vs batch inference tradeoffs"
- **Classical ML**: bias-variance, regularization, optimization, evaluation metrics
- **LLM-specific**: prompt engineering trade-offs, RAG vs fine-tuning, eval methodology, hallucination mitigation
- **Behavioral STAR** с акцентом на твои реальные проекты — берёшь у себя истории, формализуешь в STAR

Источники для вопросов: Hello Interview ML System Design, "Machine Learning System Design Interview" by Alex Xu, реальные posts по interview questions от Anthropic/OpenAI engineers на X/LinkedIn.

### 5.3 Daily-use loop

- Каждый день: 20-минутная сессия → review evidence → next-mission подхватывает слабое место
- Логи накапливаются: к концу Phase 2 у тебя ~40 реальных сессий своего использования
- Это и тренировка собесов, и непрерывный unit-test продукта одновременно

### 5.4 Зафикси то что бьёт по UX тебе самому

В `CURRENT_PRODUCT_STATE.md` уже перечислены Known Issues:
- Browser smoke не run — теперь у тебя есть время это сделать
- Browser Vosk weak на broken English — benchmark Parakeet, выбрать mainline
- First greeting audio, farewell audio — fix end-to-end
- Memory consolidation request-time only — добавить background job если нужно

### Deliverables Phase 2

- [ ] Минимум 40 реальных сессий своего daily use, записанных в evidence
- [ ] Question bank расширен до 30+
- [ ] Browser path работает clean (no console errors, audio quality acceptable)
- [ ] CV / vacancy / project notes загружены и используются в onboarding

---

## 6. Phase 3 (Week 7–9): Portfolio packaging

Когда продукт работает для тебя ежедневно — пакуешь его для recruiters/interviewers:

### 6.1 Demo video (приоритет №1)

- 3–5 минут Loom record
- Показать полный flow реальной сессии (без редактирования)
- Голос на английском — даже если не идеален, это +signal что ты сам пользуешься
- В описании: GitHub link, blog post link, LinkedIn link

### 6.2 Public GitHub polish

- Pinned на твоём профиле
- Clean commit history (если есть messy WIP — squash или archive в другую branch)
- README с архитектурной диаграммой (Mermaid или image)
- "Lessons learned" секция в README — самое ценное для interviewer'а

### 6.3 3 technical write-ups

Короче чем full blog posts из extract-плана — 800–1200 слов each:

- **Post A: "Architecting a personal voice interview coach"** — продуктовое решение и выбор stack, anti-roadmap, что выкинуто и почему
- **Post B: "Why I'm using LangGraph for multi-turn coaching"** — техническое, code snippets, comparison alternatives
- **Post C: "What 50 sessions with my own AI coach taught me about my English"** — personal narrative с реальными metrics из daily use

### 6.4 Distribution

- LinkedIn (приоритет — для recruiters): full posts с media
- dev.to (для tech audience)
- Habr (RU translation для русскоязычной audience, lower priority)
- X/Twitter threads с key insights

### Deliverables Phase 3

- [ ] Demo video published и embedded в README
- [ ] 3 write-ups published cross-platform
- [ ] GitHub profile updated, repo pinned
- [ ] LinkedIn headline + featured section updated

---

## 7. Phase 4 (Week 10–14): Apply with it as live demo

- LinkedIn headline: "Building EnglishFriend — voice AI coach for ML interview prep | Open to ML/AI Engineer roles"
- LinkedIn featured section: pinned demo video + repo link + 3 write-ups
- CV: bullet с метриками — "Built and use daily a voice AI interview coach (LangGraph + voice + vector memory). N sessions, X stars, Y reads on blog posts"
- Cover letters: reference конкретные технические решения релевантные позиции
- На technical interviews: предложи **live system design discussion на основе твоего продукта** — это сильнее любого abstract design question
- Apply целенаправленно — приоритет позициям из Phase 0 TARGET_ROLES.md

### Deliverables Phase 4

- [ ] 20–40 applications в targeted compaies
- [ ] 5+ phone screens
- [ ] 2+ on-site interview loops
- [ ] Этот product как demo material в всех технических интервью

---

## 8. Сочетание с OSS extract планом

Этот план **не отменяет** `OSS_EXTRACT_PLAN.md`. Возможные комбинации:

### Вариант A: Этот план only, без OSS extract

- Простой, конкретный, 8–14 недель
- Hiring signal через product thinking + demo
- Если найдёшь работу — OSS lib можно сделать позже с уже готовой audience

### Вариант B: Этот план + lite OSS extract внутри Phase 3

- Один из 3 write-ups (Post B) сопровождается маленьким repo extract `voice-langgraph` (упрощённый, без полного content series из OSS_EXTRACT_PLAN)
- Получаешь и product, и lib, но без 4 постов и launch hype
- Time: +2 недели к плану (всего 10–16 недель)

### Вариант C: OSS extract первым (6 недель), потом этот план (8 недель)

- Сначала extract + 4 поста как описано в `OSS_EXTRACT_PLAN.md`
- Потом возвращаешься к full product и Phase 1–4 из этого плана
- Total: 14 недель
- Лучшая комбинация если runway позволяет

**Рекомендация**: Вариант B если хочется не выбирать. Вариант A если хочешь самый прямой путь к найму.

---

## 9. Главные риски и mitigations

| Риск | Probability | Mitigation |
|---|---|---|
| "Куча времени" → вечный рефакторинг | High | Жёсткие дедлайны на Phase: "Phase 1 done by date X". Если не успеваешь — режь scope, не двигай дату. |
| Перфекционизм по polish | Medium | Правило: "good enough to demo and use myself" ≠ "production grade". Если фича работает 90% времени — не трогать. |
| Trap "ещё одну фичу" | Medium | Anti-roadmap из `MASTER_PROJECT_VIEW` — sticky. Любая новая фича проходит тест "приближает ли это к daily use или к hiring signal?". Если нет — нет. |
| Изоляция от рынка | Medium | 3–5 разговоров с друзьями на западе про их подготовку к собесам в течение Phase 1–2. Калибрует продукт под реальность. |
| Drift в "general English tutor" | Low (anti-roadmap уже locked) | Не возвращаться к vocabulary_drill, grammar_rescue, emotion-tracking. Фокус на 3 миссиях. |
| Английский B1 в write-ups | Medium | AI editing pass mandatory (см. section 6 в OSS_EXTRACT_PLAN.md). Native speaker review на Post A до публикации. |

---

## 10. Anti-roadmap

- ❌ Не возвращаться к Kafka / Debezium / Neo4j / sync-services (archived in Phase 1)
- ❌ Не добавлять новые learning modes сверх 3 существующих миссий
- ❌ Не строить TMA (Telegram Mini App) — web достаточно для self-use
- ❌ Не делать монетизацию / paid tier
- ❌ Не пытаться привлекать real users — это другой план
- ❌ Не делать YouTube channel
- ❌ Не делать собственный TTS / STT model — использовать готовые providers

---

## 11. Connection to other strategy docs

- `MASTER_PROJECT_VIEW_2026-04-22.md` — canonical product thesis (career English coach), остаётся в силе
- `CURRENT_PRODUCT_STATE.md` — operational truth, обновляется по Phase 1–4
- `OSS_EXTRACT_PLAN.md` — альтернативный/комплементарный план
- `сritics.md` (если есть) — бизнес-разбор который привёл к этим планам

---

## 12. Hand-off для следующих сессий

Если ты возвращаешься через дни/недели — проверь:

- [ ] Какая текущая Phase (0–4)?
- [ ] TARGET_ROLES.md создан в Phase 0?
- [ ] Что в blockers (запиши в bottom of file: `## Current blockers`)?
- [ ] Не пора ли pivot к OSS_EXTRACT_PLAN.md (если этот план буксует)?

Если ты Claude/Codex агент, читающий этот файл:
- Не предлагай добавлять scope в EnglishFriend — anti-roadmap (section 10) sticky
- Не предлагай "сделать ещё один продукт" — фокус на одном
- Если автор спрашивает "что дальше после Phase 4" — это решается по результатам apply, не предсказывается заранее
