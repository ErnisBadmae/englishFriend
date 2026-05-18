# `scenario-gate` OSS Extract Plan — LangGraph-native eval framework as release gate

> **Назначение этого файла**: standalone план для соло-разработчика автора EnglishFriend на 5-6 недель работы параллельно со стартом нового full-time проекта (Центр госэкспертизы СПб, старт 2026-05-18). Документ предназначен для шаринга между сессиями (Claude, Codex, человек), поэтому self-contained.
>
> **Куда положить**: `!DOC/strategy/SCENARIO_GATE_EXTRACT_PLAN.md`.
>
> **Заменяет**: `OSS_EXTRACT_PLAN.md` (voice-langgraph план — заморожен, voice не релевантен новому проекту).

---

## 0. Context

**Автор**: соло-разработчик, ML/AI, русскоязычный, английский B1. С 2026-05-18 стартует full-time как соло-архитектор AI агента в Центре государственной экспертизы СПб (LangGraph + Qwen on-prem + Qdrant — тот же stack что в EnglishFriend).

**Бюджет времени**: ~5–8 часов в неделю × 5–6 недель = ~30–45 часов всего. Параллельно с onboarding/audit фазой на новом проекте (первые недели = разговоры с командой + изучение domain, не full-time coding).

**Источник решения**: research OSS landscape (полные результаты в conversation history, agent ad83e9949297b2b5a). Ключевые findings:

- **Gap**: ни один OSS eval framework не делает **mainline-must-pass vs expanded-advisory** как first-class concept. Promptfoo, DeepEval, LangWatch Scenario, Inspect AI — все обращаются с тестами равноценно.
- **Gap**: silent-fallback detection (HTTP 200 + canned generic ответ типа "I'm having trouble") и goal-drift detection (arXiv 2505.02709) — известные failure modes без OSS solution.
- **Tailwind**: a16z infra map называет AI eval/observability/compliance underinvested; Anthropic careers explicitly требуют "substantial OSS contributions at TOP of resume" для не-PhD кандидатов.
- **Audit реального кода**: ~40% extractable as-is, ~45% generic-refactor, ~15% rewrite — total ~22 часа на v0.1.0.

**Цель плана**:
1. Выпустить `scenario-gate` lib v0.1.0 на PyPI.
2. 3 technical blog posts с launch на HackerNews/dev.to/LinkedIn.
3. Получить hiring signal calibrated под Anthropic/OpenAI/Cohere/Mistral applied AI/MTS roles.
4. **Bonus**: использовать lib как regression gate в expertise project с дня 1 — это даёт production proof для README ("deployed at state expertise center handling government building permits").

**Принцип**: focused lib (одна вещь хорошо — release-gate для LangGraph) × consistent content × 5-6 weeks параллельно с expertise onboarding.

---

## 1. Стратегия одной строкой

`scenario-gate` lib + 3 blog posts + HN launch → hiring signal на уровне applied AI engineer + reuse в expertise project regression gate.

---

## 2. Что extract'им и что не extract'им

### 2.1 Extract scope (что входит в lib)

| Source в EnglishFriend | LOC | Что это | Куда в lib |
|---|---|---|---|
| `scripts/run_product_synthetic_eval.py` (1164 LOC) | core | scenario runner, mainline/expanded tier model, assertion categorization | `scenario_gate/runner.py` + `scenario_gate/scenarios.py` |
| `app/services/pedagogy_logger.py` (576 LOC) | 100% generic | structured decision logger (20+ methods, category markers) | `scenario_gate/audit/decision_logger.py` |
| Assertion logic (lines 673–686 в runner) | 7 LOC | silent-fallback detection (substring matching) | `scenario_gate/checks/fallback_leak.py` (generalized) |
| Routing classifier eval logic в `run_routing_classifier_eval.py` (535 LOC) | partial | shadow/gate/mainline rollout pattern для classifiers | `scenario_gate/rollout/` (как opt-in helper) |
| `tests/test_product_synthetic_eval_script.py` (200 LOC) | template | pytest patterns | `tests/` в lib (rewritten для generic) |

### 2.2 Что НЕ extract (явно)

- 52 EnglishFriend scenarios (hardcoded Python dicts) — это **examples**, не библиотечный код. Один simplified example идёт в `examples/`.
- 3 hardcoded contexts (`interviews`, `workplace_communication`, `project_walkthrough`) — domain-specific.
- Track IDs, task types, snapshot fields EnglishFriend (`hr_intro`, `goal.brief.main_contexts`, etc) — domain-specific.
- WebSocket-based runner — заменяется на **graph executor abstraction** (см. 2.3).
- Vosk/Parakeet/voice-specific code.
- Goal drift detection — пока в EnglishFriend это LLM-judge-based в `onboarding.py`, не structural. Откладываем до v0.2.0 когда будет clear pattern.

### 2.3 Главный refactor: graph executor abstraction

Сейчас runner запускает full WebSocket session к `/api/v1/voice/chat/v2` + HTTP fetch snapshot. Это плотно связано с EnglishFriend deployment.

**В lib**: интерфейс `GraphExecutor` который пользователь имплементирует:

```python
class GraphExecutor(Protocol):
    async def run_turn(self, session_id: str, user_input: str) -> TurnResult: ...
    async def fetch_state(self, session_id: str) -> dict: ...
    async def end_session(self, session_id: str) -> None: ...
```

Built-in implementations:
- `LangGraphInMemoryExecutor` — для unit-style тестирования compiled graphs напрямую
- `WebSocketExecutor` — для testing full-stack через WebSocket (как EnglishFriend сейчас)
- `HTTPExecutor` — для testing REST APIs

Это **самая важная архитектурная работа** в extract — это то что делает lib actually generic, а не EF-clone.

---

## 3. Lib architecture

### 3.1 Package layout

```
scenario_gate/
├── __init__.py             # Public API
├── scenarios.py            # Scenario, ScenarioSet (Pydantic models)
├── runner.py               # ScenarioRunner orchestrator
├── executors/
│   ├── base.py             # GraphExecutor Protocol
│   ├── langgraph.py        # In-memory LangGraph executor
│   ├── websocket.py        # WebSocket executor
│   └── http.py             # HTTP executor
├── checks/
│   ├── base.py             # Check protocol + result types
│   ├── fallback_leak.py    # Silent fallback detector
│   ├── state_assertion.py  # Snapshot/state field assertions
│   └── transcript.py       # Transcript-based checks
├── tiers/
│   └── __init__.py         # mainline (blocking) / expanded (advisory) / experimental
├── audit/
│   └── decision_logger.py  # Structured decision logger
├── reports/
│   ├── junit.py            # JUnit XML output for CI
│   ├── json.py             # Machine-readable report
│   └── console.py          # Human-readable console output
├── pytest_plugin.py        # pytest integration (auto-discovery)
└── cli.py                  # CLI entry point (`scenario-gate run ...`)

examples/
├── basic_langgraph/        # Quickstart, 50 lines
├── interview_coach/        # Realistic example based on EnglishFriend (simplified)
└── document_audit/         # Realistic example based on expertise project (anonymized)

tests/
├── test_runner.py
├── test_checks.py
├── test_executors.py
└── conftest.py

docs/
├── README.md
├── ARCHITECTURE.md         # Mainline vs expanded philosophy
├── EXECUTORS.md            # How to write custom GraphExecutor
├── CHECKS.md               # How to write custom checks
└── COMPARISON.md           # vs Promptfoo, DeepEval, LangWatch Scenario, Inspect AI

pyproject.toml
LICENSE                     # MIT
.github/workflows/
├── ci.yml                  # pytest + mypy + ruff
└── publish.yml             # PyPI publish on tag
```

### 3.2 Public API (стабилизуется до v1.0.0)

```python
from scenario_gate import (
    Scenario,              # Pydantic model
    ScenarioSet,
    ScenarioRunner,
    Tier,                  # Enum: MAINLINE | EXPANDED | EXPERIMENTAL
    Check,                 # Base check protocol
    GraphExecutor,         # Protocol for plugging in your graph
    DecisionLogger,
    Report,
)
from scenario_gate.checks import (
    FallbackLeakCheck,
    StateAssertionCheck,
    TranscriptCheck,
)
from scenario_gate.executors import (
    LangGraphInMemoryExecutor,
    WebSocketExecutor,
)
```

Maximum 15 public symbols. Small surface area = lower maintenance burden.

### 3.3 Dependencies

- **Hard**: `pydantic >= 2`, `typing-extensions`, `httpx`, `pytest`, `pytest-asyncio`
- **Optional extras**:
  - `langgraph` (for `LangGraphInMemoryExecutor`)
  - `websockets` (for `WebSocketExecutor`)
- Никаких LLM/STT/TTS provider deps в core.

### 3.4 Scenario DSL (YAML/JSON)

Mover от Python dicts к declarative YAML — это критично для adoption (не требует Python knowledge от QA/PM):

```yaml
# scenarios/mainline/interview_first_value.yaml
id: interview_first_value
tier: mainline
description: Verify interview opener routes to foundation drill
turns:
  - user: "I'm preparing for interviews at ML companies"
checks:
  - type: state_assertion
    path: routing.primary_context
    equals: interviews
  - type: state_assertion
    path: mission.task_type
    equals: foundation_speaking_drill
  - type: fallback_leak
    forbidden_phrases:
      - "I'm having trouble"
      - "what do you do now?"
```

Этот DSL — главное product-decision lib. Должен быть extensible (custom check types через plugin entry points) но обозримый для пользователя.

---

## 4. Phase plan (5-6 недель параллельно с expertise project)

Старт: 2026-05-18 (понедельник, день 1 на expertise).

### Week 1 (2026-05-18 — 2026-05-24): Foundation + scenario model

**6-7 часов вечерами/weekend.**

- Создать пустой repo `scenario-gate` на GitHub (проверить namespace на PyPI и GitHub до создания)
- `pyproject.toml`, MIT license, Python ≥ 3.11
- GitHub Actions CI skeleton (pytest + mypy + ruff)
- Pydantic models: `Scenario`, `ScenarioSet`, `Tier`, `TurnResult`, `CheckResult`, `Report`
- YAML loader для scenarios
- 70% test coverage на models + loader

**Deliverable**: empty repo с working CI, parsable YAML scenarios, no execution yet.

### Week 2 (2026-05-25 — 2026-05-31): GraphExecutor abstraction + first check

**6-7 часов.**

- `GraphExecutor` Protocol + `LangGraphInMemoryExecutor` implementation
- `Check` Protocol + `StateAssertionCheck` (path-based)
- `ScenarioRunner` минимальный — execute one scenario, return results
- Basic console reporter
- End-to-end test: один YAML scenario → execute через in-memory LangGraph → assert

**Deliverable**: minimal working pipeline для одного scenario.

### Week 3 (2026-06-01 — 2026-06-07): Fallback leak + tier model + pytest plugin

**6-7 часов.**

- `FallbackLeakCheck` (substring + regex + LLM-judge optional)
- `TranscriptCheck` для assertions над диалогом
- Mainline/expanded/experimental tier handling: blocking exit codes для mainline failures
- pytest plugin: auto-discover YAML scenarios → generate pytest tests
- JUnit XML reporter для CI integration

**Deliverable**: full v0.1.0 functionality, можно использовать в реальном CI.

### Week 4 (2026-06-08 — 2026-06-14): Examples + docs + v0.1.0 release

**7-8 часов.**

- `examples/basic_langgraph/` — quickstart 50 строк
- `examples/interview_coach/` — упрощённая версия из EnglishFriend (3 scenarios)
- README с архитектурной диаграммой
- `ARCHITECTURE.md`, `EXECUTORS.md`, `CHECKS.md`
- PyPI publish v0.1.0
- GitHub repo public
- **Post #1 draft started**

**Deliverable**: lib v0.1.0 на PyPI, repo public, документация работает.

### Week 5 (2026-06-15 — 2026-06-21): Запуск + Пост #1

**6-7 часов.**

- Полировка README после первых прогонов
- **Пост #1**: "Обязательные vs наблюдательные тесты для AI агента" (~1500 слов)
  - Полные заголовки для EN/RU аудиторий и hook — см. `OSS_ROADMAP.md` section 4, пост #1
  - Краткая суть: проблема (все тесты равновесны → CI постоянно красный → команда игнорирует) → решение (tier model) → code → сравнение с Promptfoo/DeepEval
- Распространение: dev.to → LinkedIn → X → r/LangChain → Habr (через 7-10 дней)
- HackerNews "Show HN" — вторник/среда 9am ET (лучший слот по статистике)
- Отвечать на все комментарии в первые 48 часов

**Deliverable**: запуск состоялся, метрики начинают накапливаться.

### Week 6 (2026-06-22 — 2026-06-28): Пост #2 + Пост #3

**5-7 часов.**

- **Пост #2**: "Скрытые сбои в conversational AI" (~1500 слов)
  - Полные заголовки — см. `OSS_ROADMAP.md` section 4, пост #2
  - Суть: failure modes (fallback leak, generic recovery), как обнаруживать, код из `FallbackLeakCheck`
  - Ссылка на arXiv 2505.02709 (goal drift)
- **Пост #3**: "Внедрение scenario-gate в продакшен — 6 месяцев работы" (~1500 слов)
  - Полные заголовки — см. `OSS_ROADMAP.md` section 4, пост #3
  - Суть: реальные кейсы из EnglishFriend (mainline 3/3 PASS как gate) + первые сигналы из expertise project (если уже есть данные)
  - Personal narrative + конкретные цифры

**Deliverable**: 3 поста опубликованы, перекрёстно связаны, v0.1.1 release с багфиксами по feedback.

**Total**: ~37-43 hours over 5-6 недель.

---

## 5. Connection to expertise project (unique strength этого плана)

Это **главное отличие** от voice-langgraph плана: lib имеет **immediate production use** в новом проекте, не только в frozen EnglishFriend.

### 5.1 Day 1 в expertise project (2026-05-18)

- При архитектурном аудите MVP — сразу проговорить с командой: "будем использовать scenario-gate как regression gate". Это позиционирует тебя как архитектор который приносит готовые solutions, не только написанный код.
- Создать 5-10 первых synthetic scenarios для defect detection (rule-based — детект violation норматива X в документе типа Y).

### 5.2 Through Phase 1 (weeks 1-4)

- По мере extract в lib — параллельно использовать локальную preview-версию в expertise repo.
- Реальные scenarios из expertise → battle-test для lib (если что-то не работает удобно → правится в lib).
- К моменту v0.1.0 lib — у тебя уже production usage внутри Центра госэкспертизы.

### 5.3 README badge of authenticity

После согласования с работодателем (см. NDA section ниже) — добавить в lib README:

> **Used in production at**: State expertise center (St. Petersburg, RU) for regression testing of AI-driven building permit document analysis.

Это **на порядок** сильнее чем "I built this" без production proof.

### 5.4 NDA / OSS publication safety

**Перед extract** в первую неделю на expertise project — explicit conversation с руководством:
- "Я планирую generic eval pattern опубликовать как OSS, без любого domain content (правила, документы, workflow). Это improves project quality и attracts talent. Письменное согласие нужно?"
- Использовать карт-бланш архитектора чтобы получить это формально.
- Если разрешения нет — публиковать lib **без** mention expertise center, только с EnglishFriend как reference. Это снижает hire signal на ~30%, но lib всё равно валидна.

---

## 6. Success metrics

### 6.1 Realistic targets (90th percentile of solo OSS launches с decent positioning)

- **GitHub stars after 8 weeks since launch**: 100-400 (`scenario-gate` имеет лучший positioning чем typical solo lib потому что нет direct competitor в этой нише)
- **PyPI downloads in first 2 months**: 500-3000
- **Total post reads (3 posts)**: 8000-25000
- **HackerNews**: цель top 30 для Post #1 (Show HN); realistic — top 100
- **Quality DMs/issues from real users**: 10-30
- **Recruiter inbound on LinkedIn**: 5-15

### 6.2 What would be exceptional

- LangGraph maintainer share / official LangChain blog mention → 50K+ reads, 1000+ stars
- Used by another funded startup that contributes back → strong story for interviews
- Inclusion в a16z / Latent Space AI infra map updates

### 6.3 Failure mode (what to do if < 20 stars after 8 weeks)

- Diagnose в order: positioning (README hook), distribution (где postили), category fit (была ли реальная нужда).
- Не abandon — pivot на single-extract `decision-trace` (#3 в research). Меньше audience, но более defensible niche.

### 6.4 Anti-metrics (не ловиться)

- X likes / LinkedIn reactions — noise.
- Discord joins — vanity.
- Stars от твоего собственного network — discount mentally.

---

## 7. Risks + mitigations

| Risk | Probability | Mitigation |
|---|---|---|
| Expertise project съест всё время в первые недели | HIGH | План построен под "5-8 ч/нед параллельно". Если в неделю X не получается — двинуть на неделю позже, не cancel. Lib не имеет внешнего deadline. |
| GraphExecutor abstraction окажется wrong abstraction | MEDIUM | Один полный example в expertise + один в EnglishFriend = два real users. Если interface не подходит обоим → переосмыслить до v0.1.0. |
| Competitor (LangWatch Scenario, DeepEval) выпустит tier model | MEDIUM | Не катастрофично — категория достаточно большая. Differentiate через quality of docs, opinionated CI integration, real production proof. |
| English B1 в blog posts | MEDIUM | AI editing pass mandatory (Claude/ChatGPT). Native speaker review для Post #1 перед HN launch. |
| NDA блокирует mention expertise center | MEDIUM | Опубликовать без mention. Lib всё равно валидна с EnglishFriend как reference. |
| Maintenance burden после launch | MEDIUM | README explicitly "maintained by 1 person, response within 7 days". Closing PRs которые увеличивают surface area. v0.2.0 features — only после 3 месяцев of real usage signals. |
| HN reactions negative | LOW-MEDIUM | Прочитать критику Show HN постов про competing tools заранее. Не отвечать defensive — acknowledge + ask question. |

---

## 8. Anti-roadmap (что НЕ делать в этом цикле)

- ❌ Не добавлять voice-specific features (это другая lib, `voice-langgraph` план заморожен).
- ❌ Не пилить documentation site (Sphinx/MkDocs/Docusaurus). README + 3 .md файла достаточно для v0.1.
- ❌ Не делать TypeScript port.
- ❌ Не делать "scenario-gate cloud" hosted version.
- ❌ Не добавлять built-in scenario generators / synthetic data generators — это другая категория.
- ❌ Не интегрировать конкретные LLM providers (Anthropic/OpenAI/etc) в core — пользователь подключает свой через GraphExecutor.
- ❌ Не делать GUI для редактирования scenarios — YAML editor в IDE достаточно.
- ❌ Не запускать Discord server / community. GitHub Issues + Discussions хватит.
- ❌ Не пилить EnglishFriend параллельно (frozen, только bugfix).
- ❌ Не нарушать NDA expertise project (документы, правила, workflow — никогда).

---

## 9. Hand-off для следующих сессий

Если возвращаешься через дни/недели — проверь:

- [ ] Какая текущая Week (1-6)?
- [ ] Что в deliverables checked (galki в section 4)?
- [ ] Был ли разговор с expertise руководством про OSS policy?
- [ ] Что в blockers? Запиши в bottom of file: `## Current blockers`.

Если ты Claude/Codex агент, читающий этот файл:
- Не предлагай добавлять scope в lib — anti-roadmap (section 8) sticky.
- Не предлагай делать voice-langgraph параллельно — заморожен.
- Не предлагай добавлять features в EnglishFriend — frozen.
- Если автор спрашивает "что после v0.1.0" — посмотри section 6 metrics. До 3 месяцев real usage не планировать v0.2.0 features.
- Если автор спрашивает про expertise project — это **отдельный thread**, не часть этого плана. Подготовка ему — отдельный документ `EXPERTISE_AGENT_PLAN.md` (см. предыдущие conversation drafts).

---

## 10. Critical files в исходном репо

Для extract critical чтение этих файлов:

- `/Users/macbook/Desktop/englishFriend/scripts/run_product_synthetic_eval.py` (1164 LOC) — main source
- `/Users/macbook/Desktop/englishFriend/scripts/run_routing_classifier_eval.py` (535 LOC) — secondary patterns
- `/Users/macbook/Desktop/englishFriend/app/services/pedagogy_logger.py` (576 LOC) — 100% reusable
- `/Users/macbook/Desktop/englishFriend/tests/test_product_synthetic_eval_script.py` (200 LOC) — test patterns
- `/Users/macbook/Desktop/englishFriend/!DOC/operations/PRODUCT_SYNTHETIC_EVAL_RUNBOOK.md` — how-to для текущего framework, шаблон для lib docs

---

## 11. Verification (как проверить что план выполнен end-to-end)

- [ ] `pip install scenario-gate` работает с PyPI
- [ ] `scenario-gate run examples/basic_langgraph/scenarios/` проходит без ошибок
- [ ] Repo `github.com/<username>/scenario-gate` public, pinned на твоём GitHub профиле
- [ ] 3 blog posts published, cross-linked
- [ ] HN Show HN post submitted
- [ ] CV/LinkedIn updated с bullet "Open-sourced `scenario-gate`: LangGraph-native eval framework, used at Center of State Expertise (SPb)"
- [ ] Lib используется как regression gate в expertise project (с pinned version в их CI)
- [ ] EnglishFriend `run_product_synthetic_eval.py` мигрирован на использование scenario-gate (proof что lib actually работает на реальном codebase)
