# 🔒 ЗАМОРОЖЕН — Voice-LangGraph OSS Extract & Content Plan

> ## Статус: устарел, не использовать
>
> Этот план был написан 2026-05-15 в предположении, что автор продолжает поиск работы. С 2026-05-18 автор стартует full-time как архитектор AI агента в Центре государственной экспертизы СПб, где нужен **document audit** (анализ документов), а не **voice coach**. Поэтому voice-направление перестало быть приоритетным.
>
> **Актуальные документы**:
> - `SCENARIO_GATE_EXTRACT_PLAN.md` — новый главный план extract (eval framework вместо voice runtime)
> - `OSS_ROADMAP.md` — общий 18-месячный roadmap всех extract'ов
> - `SCENARIO_GATE_TEAM_PITCH.md` — pitch команде Центра госэкспертизы
>
> Этот файл оставлен в репозитории как **исторический документ** (показывает эволюцию мышления), не как actionable план. Если кто-то (включая будущие сессии Claude/Codex) предлагает вернуться к voice-langgraph extract — это нужно явно подтверждать с автором, см. anti-roadmap в `OSS_ROADMAP.md` section 5.

---

# (Заархивированный план ниже — для исторического контекста)

> **Назначение этого файла** (исходное): standalone план для соло-разработчика автора EnglishFriend на 6 недель работы параллельно с поиском работы. Документ предназначен для шаринга между сессиями (Claude, Codex, человек), поэтому self-contained — не требует контекста предыдущих обсуждений.
>
> **Куда положить** (исходное): `!DOC/strategy/OSS_EXTRACT_PLAN.md` или `!DOC/strategy/voice-langgraph-extract-plan.md`.

---

## 0. Context (зачем это нужно)

**Автор**: соло-разработчик, ML/AI background, русскоязычный, английский B1, ищет работу в западной компании. Бюджет времени: ~5–7 часов в неделю × 6 недель = ~30–40 часов всего. Параллельно с активным job search.

**Исходный проект**: EnglishFriend (`/Users/macbook/Desktop/englishFriend`) — vertical voice coach для подготовки к ML-собеседованиям на западе. 0 пользователей, активная разработка ~12 недель, ~10K LOC.

**Проблема**: продукт сам по себе не приведёт к работе или доходу в нужный срок (см. предыдущий бизнес-разбор). Но в коде накоплены **переиспользуемые паттерны для voice + LangGraph + vertical AI agents**, которые в open-source community пока редко документированы.

**Цель плана**: вытащить из EnglishFriend узкую focused library + написать 4 технических blog-поста, чтобы:
1. Получить hiring signal (visible OSS + technical writing для рекрутеров FAANG/scale-up).
2. Построить минимальную audience для будущих проектов.
3. Валидировать спрос на vertical-voice-coaching паттерны от community (это даст сигнал, продолжать ли EnglishFriend через 6–12 месяцев).

**Принцип**: focused lib (одна вещь хорошо) × consistent content × 6 weeks. Не framework. Не платформа. Не multiple libs.

---

## 1. Стратегия одной строкой

`voice-langgraph` library + 4 blog posts + cross-posted launches → hiring signal + 200–500 GitHub stars + 5K–15K post reads.

---

## 2. Что extract'им из EnglishFriend

### 2.1 Что брать (ранжировано по ценности)

| Источник в EnglishFriend | Что это | Куда в lib |
|---|---|---|
| `app/services/voice_session/service.py` | Voice session lifecycle: bootstrap, mission metadata, persistence | `voice_langgraph/session.py` |
| `app/services/voice_runtime/` (controller, transport, STT, TTS, turn_detector) | Modular runtime с swap-провайдерами | `voice_langgraph/runtime/` |
| `app/api/voice.py` (только `/chat/v2` ядро, 200–300 LOC из 1902) | WebSocket handler + LangGraph integration | `voice_langgraph/transports/fastapi_websocket.py` |
| `app/agent/recovery.py` | Mission-safe recovery вместо generic fallback | `voice_langgraph/recovery.py` |
| `app/services/routing/goal_routing.py` (упрощённая версия) | Scope gate + sticky context pattern | `voice_langgraph/scope_gate.py` (как opt-in helper) |
| `scripts/run_product_synthetic_eval.py` (упрощённая) | Scenario-based eval runner | отдельный пример в `examples/eval/`, не core lib |

### 2.2 Что НЕ брать (явно)

- `sync-vector/`, `sync-graph/`, `cdc/` — Kafka/Debezium pipelines не нужны для core voice+LangGraph use case.
- `app/services/ai/personaplex_provider.py` — слишком specific (NVIDIA Moshi self-hosted).
- Vosk-specific код — оставить только interface, имплементацию пусть пользователь подключает свою.
- Любая Russian-language логика, hardcoded scenarios EnglishFriend, FSRS, emotion-tracking упоминания.
- PostgreSQL persistence, Qdrant integration, RLS, partitioning — это не воркфлоу-зависимое.
- Frontend (VoiceChatV2) — целиком исключить, это другая категория продукта.

### 2.3 Архитектура целевой library

```
voice_langgraph/
├── __init__.py
├── session.py          # VoiceSession lifecycle + state restoration
├── runtime/
│   ├── controller.py   # Coordinates STT → LangGraph → TTS
│   ├── stt.py          # STTProvider interface + base implementations
│   ├── tts.py          # TTSProvider interface + base implementations
│   ├── transport.py    # TransportAdapter interface
│   └── turn_detector.py
├── transports/
│   └── fastapi_websocket.py  # Optional FastAPI integration
├── recovery.py         # Drill-pinned recovery utilities
├── scope_gate.py       # Optional scope-gating helper for vertical agents
└── types.py            # TypedDict / Pydantic schemas

examples/
├── interview_coach/    # Полный working example: 1 mission, ~3 nodes
│   ├── app.py          # Entry point
│   ├── nodes.py        # LangGraph nodes
│   ├── prompts.py
│   └── README.md
├── minimal/            # Quickstart < 50 строк
└── eval/               # Scenario eval демо

tests/
├── test_session.py
├── test_runtime.py
├── test_recovery.py
└── conftest.py

docs/
├── README.md           # Главная страница (см. section 3.4)
├── ARCHITECTURE.md     # Диаграмма + объяснение почему так
├── PROVIDERS.md        # Как подключать свои STT/TTS
└── COMPARISON.md       # vs LangChain text-only, vs raw WebSocket

pyproject.toml
LICENSE                 # MIT
.github/workflows/
├── ci.yml              # pytest + mypy + ruff
└── publish.yml         # PyPI publish on tag
```

### 2.4 Размер и зависимости

- **Целевой LOC**: 800–1500 (core lib, без examples).
- **Hard dependencies**: `langgraph >= 0.2`, `pydantic >= 2`, `typing-extensions`.
- **Optional dependencies** (через extras_require):
  - `fastapi` для WebSocket transport
  - `websockets` для standalone server
  - Никаких STT/TTS provider-specific deps в core (пусть пользователь ставит сам)

### 2.5 Public API surface (минимальный, фиксируется в `__init__.py`)

```python
from voice_langgraph import (
    VoiceSession,           # main class
    VoiceSessionController, # runtime coordinator
    STTProvider,            # interface
    TTSProvider,            # interface
    TransportAdapter,       # interface
    TurnDetector,           # interface
    MissionSafeRecovery,    # opt-in helper
    ScopeGate,              # opt-in helper
)
```

Ничего больше публично не экспортируется. Это критично — small surface area = ниже maintenance burden.

---

## 3. Phase 1: Library extraction (Weeks 1–3)

### 3.1 Engineering checklist

- [ ] Создать пустой repo `voice-langgraph` на GitHub
- [ ] `pyproject.toml` с MIT license, requires Python ≥ 3.11
- [ ] Extract code файл-за-файлом из EnglishFriend (по таблице 2.1)
- [ ] **Очистка**: убрать все упоминания EnglishFriend, Russian text, PersonaPlex, Vosk-specific, Postgres-specific
- [ ] Type hints везде, mypy strict
- [ ] Pytest tests с coverage > 70%
- [ ] CI: GitHub Actions (pytest + mypy + ruff на push/PR)
- [ ] Один полный working example: simplified interview coach (1 mission, 3 nodes, ~200 LOC)
- [ ] Один minimal quickstart example (< 50 строк) для README
- [ ] LICENSE (MIT), CODE_OF_CONDUCT.md, CONTRIBUTING.md (короткий)
- [ ] CHANGELOG.md (Keep a Changelog format)
- [ ] Semver: первый релиз `0.1.0`
- [ ] PyPI publish workflow

### 3.2 Quickstart example (для README — это то, что увидит человек первым)

Цель: показать в < 50 строк что lib делает. Текст ниже — placeholder, финальный код пишется при extract.

```python
from voice_langgraph import VoiceSession, VoiceSessionController
from voice_langgraph.runtime import STTProvider, TTSProvider
from langgraph.graph import StateGraph

# 1. Define your LangGraph state machine
graph = StateGraph(MyState)
graph.add_node("greet", greet_node)
graph.add_node("listen", listen_node)
graph.set_entry_point("greet")
compiled = graph.compile()

# 2. Plug in your STT/TTS providers
stt = MyWhisperSTT()
tts = MyOpenAITTS()

# 3. Wrap in a voice session
controller = VoiceSessionController(graph=compiled, stt=stt, tts=tts)

# 4. Start a session (FastAPI WebSocket example)
@app.websocket("/voice")
async def voice_endpoint(ws: WebSocket):
    session = await VoiceSession.start(ws, controller=controller)
    await session.run()
```

### 3.3 README структура (это самый важный файл — большинство людей дальше не пойдёт)

```markdown
# voice-langgraph

> Voice runtime for LangGraph state machines. Bring your own STT/TTS.

[Бейджи: PyPI version, Python versions, CI status, license]

## Why

[3–5 предложений: какую боль решает. Конкретно: state restoration в voice, mid-turn streaming, transcript handling]

## Install

`pip install voice-langgraph`

## Quickstart

[< 50 строк example из section 3.2]

## When to use

✅ Building voice agents on top of LangGraph
✅ Need to swap STT/TTS providers
✅ Need mid-conversation state restoration

## When NOT to use

❌ Pure text agents (use LangGraph directly)
❌ Need built-in conversation memory (this is runtime only)
❌ Want a complete voice product out of the box

## Examples

- [Minimal](examples/minimal/) — 50-line quickstart
- [Interview coach](examples/interview_coach/) — full working vertical agent
- [Custom STT provider](examples/custom_stt/) — implementing the interface

## Architecture

[Diagram + 1 short paragraph; полная версия в ARCHITECTURE.md]

## Comparison

| | voice-langgraph | LangGraph (text) | Raw WebSocket |
|---|---|---|---|
| ... | ... | ... | ... |

## Contributing

Issues and PRs welcome. See CONTRIBUTING.md.

## License

MIT
```

### 3.4 Что точно НЕ делать в lib

- Не встраивать конкретные STT/TTS providers (Whisper, ElevenLabs etc) — interface only.
- Не делать "framework features" типа plugin system, middleware chains, hooks.
- Не пилить documentation site (Sphinx/MkDocs) — README + 3 markdown файла достаточно для v0.1.
- Не делать TypeScript port, Rust port, ничего дополнительного.

---

## 4. Phase 2: Blog posts (Weeks 2–6, parallel)

### 4.1 Общие правила для всех постов

- **Длина**: 1200–2000 слов каждый.
- **Структура**: hook → problem → solution → code → results → takeaway.
- **Code snippets**: каждый пост содержит 2–4 code блока из реальной lib (не псевдокод).
- **Один концепт на пост**. Не пытаться сказать всё.
- **Английский B1 strategy** (см. section 6).

### 4.2 Post 1: "Why Voice + LangGraph is Harder Than You Think"

- **Цель поста**: показать боль, представить lib как решение.
- **Outline**:
  - Hook: "I built a voice agent on LangGraph. Here are 5 things that broke that aren't in any tutorial."
  - Problem 1: state restoration when WebSocket reconnects mid-conversation
  - Problem 2: streaming TTS while LangGraph node is still running
  - Problem 3: mission/context metadata across session lifecycle
  - Problem 4: graceful degradation when STT returns garbage
  - Problem 5: testing voice flows without recording audio
  - Solution: how `voice-langgraph` addresses each
  - CTA: link to repo + minimal example
- **Code**: 3 snippets из lib showing each pattern.
- **Distribution**: dev.to (primary), HackerNews (Show HN на день launch), LinkedIn, X/Twitter, r/LangChain.

### 4.3 Post 2: "Scope Gates: Stopping Vertical AI Agents from Drifting"

- **Цель**: представить scope-gating паттерн, привлечь vertical AI builders.
- **Outline**:
  - Hook: "If you're building an AI agent for a specific domain (medical, legal, sales coaching), you've hit this: users ask off-topic questions and the agent goes off the rails."
  - Concept: scope gate as separate layer before routing
  - 3 status patterns: `in_scope` / `needs_narrowing` / `out_of_scope`
  - Sticky context (once routed, don't re-route on next message)
  - Code: scope gate implementation
  - When NOT to use this (general assistants)
  - CTA: link to `voice_langgraph.scope_gate` opt-in helper
- **Distribution**: dev.to, Hashnode, Habr (RU translation), LinkedIn, X.

### 4.4 Post 3: "Scenario-Based Eval as Release Gate (Beyond Promptfoo)"

- **Цель**: представить eval паттерн, привлечь AI evaluation community.
- **Outline**:
  - Hook: "Promptfoo is great for single-turn prompt testing. But how do you test a 10-turn voice conversation that should reach a specific outcome?"
  - Concept: scenario eval — declarative multi-turn scenarios + categorized assertions
  - Mainline (blocking) vs expanded (advisory) tiers
  - "No fallback leak" scan as gate
  - Code: scenario YAML + runner
  - Tradeoffs vs Promptfoo, Braintrust, Langfuse
  - CTA: link to `examples/eval/` directory in repo
- **Distribution**: dev.to, HackerNews, X (especially target AI evals folks like Hamel Husain, Eugene Yan).

### 4.5 Post 4: "Why I'm Building Vertical: Notes from a Voice Interview Coach"

- **Цель**: personal-narrative пост, builds your name. Не про library, про продуктовое мышление.
- **Outline**:
  - Hook: "Everyone is building AI tutors. I think 'AI tutor for everyone' is dead, and 'voice coach for ML interviews' is the right shape. Here's why."
  - Problem: ChatGPT Voice already does general conversation. What's left?
  - Vertical wedge: career-state + evidence loop + adaptive missions
  - Anti-roadmap: what I'm explicitly NOT building
  - 3 things I learned that surprised me (route stickiness, scope gating, embedded baseline)
  - Honest section: 0 users, what I learned anyway
  - CTA: link to repo + previous 3 posts
- **Distribution**: dev.to, Medium (для broader audience), Habr, LinkedIn, X, IndieHackers.

### 4.6 Posting cadence

- Не публиковать все 4 за неделю. Публиковать **по одному в неделю** в Weeks 3, 4, 5, 6 (после того как library уже на GitHub).
- Cross-post с задержкой 2–3 дня между платформами (избегать "duplicate spam" восприятия).
- Каждый пост должен ссылаться на следующий (внутри серии) и на repo.

---

## 5. Distribution plan

### 5.1 Channel priorities (по hiring signal × audience size)

| Channel | Audience | Difficulty | Hiring signal value |
|---|---|---|---|
| dev.to | Wide developer | Easy (just publish) | Medium |
| HackerNews "Show HN" | Tech leaders, founders | Hard (one shot, must hit Mon–Wed 9am ET) | **Very high** |
| GitHub Trending | Wide developer | Hard (need stars momentum) | **Very high** |
| X/Twitter | AI builders | Medium (need engagement) | Medium-high |
| LinkedIn | Recruiters! | Easy | **High for hiring** |
| Habr | Russian-speaking devs | Easy | Low for Western hiring |
| r/LangChain, r/LocalLLaMA | LLM builders | Easy | Medium |
| Hashnode | Wide developer | Easy | Low |
| IndieHackers | Solo builders | Easy | Low for hiring |

### 5.2 Launch plan

- **Day of repo public**: post on X with screenshot + one-liner. Tag `@LangChainAI`.
- **Same day**: pin repo as featured on GitHub profile, update LinkedIn headline ("Building voice-langgraph | Open-source voice runtime for LangGraph").
- **Day 3**: Post #1 on dev.to.
- **Day 5**: Cross-post #1 to HackerNews "Show HN: voice-langgraph — Voice runtime for LangGraph". Best slot: Tue/Wed 9–10am ET.
- **Days 7–28**: One post per week, rotate distribution.

### 5.3 Engagement rules

- Reply to **every** comment in first 48 hours of each post.
- If someone opens GitHub issue, reply within 24h, even just "thanks, looking into it".
- Don't argue with critics. Acknowledge, ask question, learn.
- DO NOT use emoji в постах для англоязычной technical audience (signals "marketing").

---

## 6. English B1 strategy

Английский B1 — workable, но требует процесса:

### 6.1 Workflow per post

1. Write draft в Russian первый (быстрее, ясная структура).
2. Translate to English manually (не Google Translate — он даёт неестественный синтаксис).
3. Run through Claude/ChatGPT с промптом: "Edit this technical blog post for clarity, idiomatic English, and engineering blog tone. Don't add new content. Keep my voice. Flag any factual errors."
4. Re-read aloud — если spotykaeшsya, переписать предложение.
5. Show to native speaker if possible (or another AI agent for second-pass editing).

### 6.2 Language safety rules

- **Short sentences**: target 12–18 слов, avoid 25+.
- **Active voice**: "I built X" not "X was built by me".
- **No idioms**: "the rubber meets the road" → "in practice it works like".
- **Concrete > abstract**: показывать примеры, не философствовать.
- **One claim per paragraph**: ниже шанс сказать неловко.

### 6.3 Templates для самых рисковых разделов

- **Hook**: "I [did X]. Here's [Y] that surprised me." / "If you [build Z], you've hit this problem: [...]."
- **Problem statement**: "The standard approach is [A]. But for [B], it breaks because [C]."
- **Code intro**: "Here's how this looks in practice:"
- **Conclusion**: "If you're [doing X], try [Y]. Code is at [link]. Feedback welcome."

### 6.4 Чего избегать

- Не писать в casual American slang ("super cool", "tons of", "killer feature") — звучит фальшиво для non-native, и русские читатели на Habr найдут.
- Не использовать "very", "really", "actually" — слова-паразиты которые B1 любит вставлять.
- Не пытаться шутить на английском — почти всегда не работает на B1.

---

## 7. Weekly schedule (6 weeks)

| Week | Hours | Focus | Output |
|---|---|---|---|
| 1 | 7h | Library skeleton: repo setup, pyproject, CI workflow, extract `runtime/` | Empty repo + `voice_langgraph/runtime/` working with stub providers |
| 2 | 7h | Extract `session.py`, `recovery.py`, `scope_gate.py`. Tests for runtime | Library 60% complete + 70% test coverage on runtime |
| 3 | 7h | Build `examples/interview_coach/` + `examples/minimal/`. Write README. **Post #1 draft.** | Repo public with examples. Post #1 published mid-week. |
| 4 | 6h | Polish docs (ARCHITECTURE.md, PROVIDERS.md, COMPARISON.md). **Post #2 draft + publish.** | All docs in place. Post #2 published. |
| 5 | 6h | Bug fixes from community feedback. **Post #3 draft + publish.** | Library v0.1.1 if needed. Post #3 published. |
| 6 | 7h | **Post #4 (personal narrative) + publish.** Wrap-up post on LinkedIn. Update CV/portfolio. | Post #4 published. CV updated with library + posts links. |

**Total**: ~40 hours over 6 weeks (~6.7h/week average).

---

## 8. Success metrics (что считаем "получилось")

### 8.1 Realistic targets (90th percentile of solo OSS launches)

- **GitHub stars after 6 weeks**: 50–200 (anything > 100 is a strong signal)
- **PyPI downloads** in first month: 200–1000
- **Total post reads (sum of 4)**: 5000–15000
- **Quality replies / DMs from devs**: 5–20 (this matters more than vanity)
- **Recruiter inbound on LinkedIn**: 3–10 over 6 weeks

### 8.2 What would be exceptional

- HackerNews front page (top 30) for at least 1 post → 50K+ reads
- 500+ stars → "trending" on GitHub
- Maintainer of LangChain or LangGraph notices and shares
- Cited by another OSS project / blog post

### 8.3 What would be failure

- < 20 stars after 6 weeks AND < 1000 post reads AND no recruiter inbound → audience-fit problem
- В этом случае: pivot к другому extract (например, `convoeval` standalone) или сосредоточиться 100% на найме без OSS.

### 8.4 Anti-metrics (не ловиться на них)

- Twitter likes — noise.
- Discord/Slack joins — vanity.
- Stars from your own network — discount these mentally.

---

## 9. Risks and mitigations

| Risk | Probability | Mitigation |
|---|---|---|
| Time conflict with job search | High | Library work — only outside peak interview prep weeks. Если interview loop активный — ставить library на pause, content нет. |
| English quality undermines credibility | Medium | Section 6 workflow (AI editing pass mandatory). Preview-показать 1 native speaker для post #1 перед публикацией. |
| Maintenance burden грозит | Medium | README explicitly: "Maintained by 1 person, response within 1 week". Не обещать enterprise support. Closing PRs которые увеличивают surface area. |
| Кто-то выпустит подобную lib параллельно | Low-Medium | Не критично — рынок не winner-take-all для OSS dev tools. Differentiate через quality of docs + content. |
| HN/Reddit отреагируют негативно | Medium | Подготовиться: review критику Show HN постов про другие LangGraph tools, понять common complaints. Не отвечать defensive. |
| Library extract займёт > 3 недель | Medium | Если на week 3 lib не готов к публикации — не задерживать. Опубликовать как `0.0.1-alpha`, доделать по feedback. Worse outcome — perfect lib without launch. |

---

## 10. Anti-roadmap (что точно НЕ делать в этом цикле)

- ❌ Не делать второй library, даже если "идея похожа".
- ❌ Не делать documentation site (Sphinx/MkDocs/docusaurus). README + 3 .md files достаточно для v0.1.
- ❌ Не делать TypeScript / JS port.
- ❌ Не делать "voice-langgraph cloud" hosted version.
- ❌ Не интегрировать конкретные STT/TTS providers в core lib (только interfaces).
- ❌ Не делать YouTube видео параллельно с blog posts (это +20 часов производства, не окупается на этом этапе).
- ❌ Не запускать Discord server / community. Issues + Discussions на GitHub достаточно.
- ❌ Не пилить EnglishFriend параллельно (frozen за исключением bugfix).

---

## 11. Outputs (deliverables) на конец 6-й недели

- `github.com/<username>/voice-langgraph` — public repo, v0.1.0 на PyPI
- 4 published blog posts с cross-links между собой
- 1 launch announcement (X/HN/LinkedIn)
- Updated GitHub profile (pinned repo, bio mentions library)
- Updated LinkedIn headline + featured section с library + post links
- Updated CV: одна новая bullet "Open-sourced `voice-langgraph` (Python lib for voice runtime on LangGraph state machines): X stars, Y downloads"

---

## 12. Connection back to EnglishFriend

После завершения этого цикла EnglishFriend остаётся **frozen на новые фичи**, но lives on как:

1. **Reference implementation** для library (linked from README as "real-world usage").
2. **Subject of Post #4** (personal narrative).
3. **Portfolio piece** во время interview rounds — "I extracted this open-source lib from this product I built".
4. **Optional**: через 6–12 месяцев, если у тебя будет работа с runway, и реакция на library + посты покажет реальный спрос на vertical voice coaching → можно вернуться к EnglishFriend с уже готовой audience и сильной hiring позицией.

---

## 13. Hand-off для следующих сессий

Если ты возвращаешься к этому плану через несколько дней / недель, проверь:

- [ ] Какая текущая фаза (Week 1–6)?
- [ ] Что в плане отмечено completed (галочка в section 3.1, table 7)?
- [ ] Что в blockers (запиши в bottom of file: `## Current blockers` если появляются)?
- [ ] Не пора ли pivot в anti-pattern section 8.3?

Если ты Claude/Codex агент, читающий этот файл:
- Не предлагай добавлять scope. Anti-roadmap (section 10) сильнее, чем твоё желание помочь.
- Не предлагай documentation site, framework features, multi-language ports.
- Если автор спрашивает "что дальше после 6 недель" — посмотри section 12 и не отвечай за него. Это решение принимается на основе результатов.
