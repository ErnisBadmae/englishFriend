# OSS Roadmap — 18-месячная последовательность extract'ов

> **Назначение**: roadmap для соло-разработчика на 18 месяцев. Какие OSS lib и blog posts извлекать из production кода (EnglishFriend + Центр госэкспертизы СПб), в каком порядке, когда не делать, и почему. Self-contained для шаринга между сессиями.
>
> **Аудитория**: автор сам + будущие Claude/Codex сессии.
>
> **Базовые планы (не отменяет, расширяет)**:
> - `SCENARIO_GATE_EXTRACT_PLAN.md` — детальный план первого extract (Q2-Q3 2026)
> - `SCENARIO_GATE_TEAM_PITCH.md` — pitch для команды Центра госэкспертизы
>
> **Источник research**: deep research agent (a75e9a07954070182 в conversation history) + предыдущий research (ad83e9949297b2b5a). Все code examples взяты из официальных docs / repos / issues конкурентов.
>
> **Дата составления**: 2026-05-16.

---

## 0. Главные принципы (sticky правила)

Это то, что **не** должно нарушаться при будущих переоценках roadmap:

1. **Один active OSS thread максимум.** Соло-разработчик с двумя параллельными libs получает два полу-готовых repo с 20 stars каждый вместо одного с 300.
2. **No lib без production driver.** Каждый extract должен расти из реальной работы в одном из двух threads (EnglishFriend / Центр госэкспертизы). Speculative libs мертвы.
3. **Pattern emerges, then extract.** Не engineer abstraction in advance — будет wrong. Жди 3-6 месяцев production usage **перед** extract.
4. **Content > lib для thin patterns.** Если паттерн < 500 LOC — blog post сильнее. Lib < 500 LOC = тупик: maintenance burden vs малая ценность.
5. **Honest gap check перед каждым extract.** Research existing OSS landscape. Если 80% gap уже покрывает existing lib — лучше contribute туда, не делать новый.
6. **One paragraph "почему мы не используем X"** в README каждого extract. Если не можешь написать честно — extract нельзя делать.

---

## 1. Текущее активное состояние (на 2026-05-16)

Параллельно идут **два рабочих направления**:

- **Направление №1 (full-time, старт 2026-05-18)**: Центр государственной экспертизы СПб — соло-архитектор AI агента для анализа проектной документации. **Это не OSS extract**, это коммерческий full-time проект — поэтому он **не нарушает** правило "один OSS thread параллельно" из section 0.
- **Направление №2 (OSS, 5-8ч в неделю по вечерам/выходным)**: extract `scenario-gate` библиотеки — план в `SCENARIO_GATE_EXTRACT_PLAN.md`, выпуск v0.1.0 ориентировочно конец июля 2026.

**Замороженные направления**:
- **EnglishFriend** — продукт frozen на новые фичи (только багфиксы). Кодовая база остаётся как **источник для extract'ов** (eval framework → scenario-gate; routing → sticky router; etc.) и как **reference implementation** в README будущих библиотек.
- **voice-langgraph extract** (план в `OSS_EXTRACT_PLAN.md`) — заморожен, потому что voice-направление не релевантно новому full-time проекту в Центре госэкспертизы (там анализ документов, не голос). Этот файл оставлен как **исторический документ**, явно помечен 🔒 в header'е.

После выпуска scenario-gate v0.1.0 (ориентировочно июль-август 2026) — следующее направление выбирается по этому roadmap (section 2).

---

## 2. Recommended 18-month sequencing

| Период | Active thread | Status | Effort | Hire signal | Rationale |
|---|---|---|---|---|---|
| **Q2-Q3 2026** (май-июль) | `scenario-gate` v0.1.0 + 3 blog posts | **CURRENT** | ~40ч | Very High | Уже в плане. См. `SCENARIO_GATE_EXTRACT_PLAN.md` |
| **Q3 2026** (август-сентябрь) | Sticky Router pattern: blog post + micro-lib `langgraph-sticky-router` | next | ~15-20ч | Medium-High | Cheapest, есть production evidence в твоём repo. Builds "production agent reliability" track record. |
| **Q4 2026** (октябрь-декабрь) | Truth-State Template repo + 2-3 blog posts (методология работы с AI coding agents) | planned | ~25-30ч | Medium (High as thought-leadership) | Низкое усилие, compounds с sticky router (методология сделала возможным sticky router). |
| **Q1-Q2 2027** (январь-июнь) | **`langgraph-doc-audit` framework v0.1.0** + launch + post series | major bet | ~100-150ч | **HIGH** | После 6-12 мес production work в Центре. Hire signal anchor. Wait until pattern stable. |
| **Q3 2027+** | Maintenance + evaluate next | TBD | — | — | По результатам |

**Skip standalone**: `cite-or-refuse` decorator (Candidate 2 из research) — fold into `langgraph-doc-audit` как `doc_audit.citations` submodule. Standalone competes с Instructor brand, читается как wrapper.

---

## 3. Per-candidate deep dive

### 3.0 Currently active: scenario-gate (Q2-Q3 2026)

См. `SCENARIO_GATE_EXTRACT_PLAN.md` для детального плана. Краткое summary:

- LangGraph-native eval framework с blocking mainline / advisory expanded tier model
- 22ч extract + ~15-20ч blog posts = ~40ч total
- Reuse в Центре госэкспертизы с дня 1 как regression gate
- v0.1.0 на PyPI к концу июля 2026

---

### 3.1 Q3 2026: Sticky Router (липкий роутинг) — Candidate 4

#### Что это

Паттерн + маленькая библиотека для многошаговых диалогов с LangGraph-агентом. Решает известную проблему: агент "забывает" о чём говорили на 3-5 сообщении назад и уходит в другую тему.

**Три части паттерна**:

1. **Накопительная оценка контекста** (cumulative scoring) — не оцениваем интент пользователя на каждом сообщении заново, а накапливаем уверенность по всему диалогу. Чем дольше пользователь говорит про X, тем выше score, что речь именно про X.
2. **Липкое решение** (sticky decision) — как только система уверена куда направить диалог (например, на тренировку технических собесов), она **фиксирует** это решение и **не пересматривает** на каждом следующем сообщении. Иначе агент будет переключать тему каждый раз когда пользователь упомянет смежное.
3. **Явная полоса коррекции** (explicit correction lane) — пользователь может в любой момент явно сказать "давай поговорим о другом". Это единственный способ разблокировать sticky-решение. Без этой полосы система становится упрямой и злит пользователя.

**Пример из EnglishFriend**:

```
Turn 1: User: "Готовлюсь к собесу на ML инженера"
        → routing: контекст=собесы, score=0.95, decision=ЗАФИКСИРОВАНО

Turn 2: User: "А ещё у меня слабый английский"
        → naive подход: переключиться на general_english (это упоминание!)
        → sticky подход: не пересматриваем. Score контекста собесов остаётся высоким.

Turn 5: User: "Знаешь, давай вообще другой разговор"
        → открываем correction lane, спрашиваем явно: "Что вы хотите обсудить вместо собесов?"
        → только теперь можем переключиться
```

**Состав extract**:
- Пост на 2000-3000 слов (заголовки для разных аудиторий см. section 4)
- Микро-библиотека `langgraph-sticky-router` (200-400 строк кода): объект `StickyRouter` (хранит state) + накопительный счётчик + lane запроса коррекции + метрика дрейфа

#### Existing landscape

**Research-hot, OSS-cold**. Академические papers все 2025-2026:
- [arXiv 2505.02709](https://arxiv.org/abs/2505.02709) "Evaluating Goal Drift in LM Agents"
- [arXiv 2511.04032](https://arxiv.org/abs/2511.04032) "Detecting Silent Failures in Multi-Agentic AI Trajectories" — XGBoost 98% / SVDD 96% detection accuracy
- [arXiv 2601.04170](https://arxiv.org/abs/2601.04170) "Agent Drift in Multi-Agent Systems" — ~50% multi-agent workflows drift к 600 interactions
- [arXiv 2602.16935](https://arxiv.org/html/2602.16935v1) "DeepContext" — real-time adversarial intent-drift detection

Practitioner-side:
- LangChain ["How we build evals for Deep Agents"](https://blog.langchain.com/how-we-build-evals-for-deep-agents/) — ideal-trajectory primitive, judge-drift warnings
- MindStudio "6 ways agents fail" (March 2026) — specification drift named
- Augment Code ["Why multi-agent LLM systems fail"](https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them) — DAG fallback + clarification-on-low-confidence

**Что OSS НЕ делает**:
- LangChain `agentevals` имеет trajectory match + LLM-judge но **нет drift-specific evaluator**
- Нет OSS lib для "sticky decision once routed + correction lane + cumulative scoring" как reusable pattern
- LangGraph examples показывают persistent state, но не sticky-intent
- Production teams clearly hit это (HN / dev.to "agent went in circles"), но published advice generic ("use DAG", "fallback domain")

#### Real gap

> Нет `langgraph-sticky-router` или `agentevals` extension для goal-drift detection. Reusable evaluator "given a trajectory, score drift vs initial intent" — directly missing.

#### Honest assessment: **YES — blog first, micro-lib second**

Working evidence уже есть в твоём EnglishFriend repo (routing classifier rollout rule в CLAUDE.md — это exactly этот pattern):
- `app/services/routing/goal_routing.py` — sticky context
- `app/services/routing/scope_gate.py` — cumulative scoring + explicit correction lane
- 96 passing tests подтверждают что pattern работает

**Sequencing**:
1. **Blog post first** (Aug 2026) — 2000-3000 слов с code snippets из routing classifier, comparison к "naive per-turn LLM router" подход. Distribution: dev.to → LangChain Discord → HackerNews → r/LangChain
2. **Если blog получил reaction** (50+ comments, 5+ "give me the code" DMs) — extract micro-lib (Sep 2026)
3. **Если blog flopped** — оставить как Reference post в scenario-gate README, не extract

#### Effort + timing

- Blog post: 8-12ч (включая AI editing pass для English B1)
- Micro-lib (если идём): 200-400 LOC, ~15-20ч с tests и README
- **Total**: 15-30ч calendar 4-6 weeks

#### Hire signal: **MEDIUM-HIGH for blog, MEDIUM for lib**

Goal drift — 2026 research-paper trend + practitioner pain. Один good blog с measurable before/after на real product = high signal. Anthropic Applied AI / OpenAI Forward Deployed Engineer roles ($350-550k) ценят exactly это: "production agent reliability". Lib без blog — medium, потому что 200-400 LOC слишком thin для standalone repo brand.

#### References

См. above + arXiv links.

---

### 3.2 Q4 2026: Truth-State Methodology + Template Repo (Candidate 3)

#### Что это

Process know-how для работы с AI coding agents (Claude Code, Codex, Cursor, Aider) в больших long-lived проектах. **Не Python lib**: template repository + blog series.

**Состав**:
- Template repo `prod-agent-project-template` с stubs:
  - `CLAUDE.md` / `AGENTS.md` (cross-tool)
  - `.claude/rules/` с canonical rules examples
  - `!DOC/operations/CURRENT_STATE.md` template
  - `MEMORY.md` index pattern
  - Eval harness link (scenario-gate by default)
  - README с философией
- 2-3 blog posts:
  - "Truth-State Docs: Stop AI Agents from Drifting Your Codebase"
  - "Multi-Agent Collaboration Without Conflicts (Claude + Codex + Human)"
  - "When Memory Lies: How I Found My Agent Reading Stale Project State"

#### Existing landscape

**Saturated на index-of-snippets level, immature на operational-truth-state level**:

| Repo | Stars | Что это |
|---|---|---|
| [PatrickJS/awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules) | 39.3k | 163 файла rules для Cursor |
| [hesreallyhim/awesome-claude-code](https://claudefa.st/blog/tools/resources/awesome-claude-code) | 36.8k | Curated index Claude Code resources |
| Everything Claude Code (Augment) | ~170k | 48 agents / 184 skills / 79 commands |
| [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit) | ~10k | 135 agents / 35 skills / 15 rules |

**AGENTS.md** становится cross-tool standard (Cursor / Cline / Aider / Continue все consume его).

**Memory layers**:
- CLAUDE.md (L1 instruction) + persona (L2) + auto MEMORY.md (L4) — есть [Bijit Ghosh complete guide](https://medium.com/@bijit211987/the-complete-guide-to-claude-md-memory-rules-loading-and-cross-tool-compression-97cc12ed037b)
- [Persistent memory system Claude Code](https://www.mindstudio.ai/blog/persistent-memory-system-claude-code-agents)

**Что НЕ packaged**:
- Canonical "operational truth-state doc" pattern для long-lived multi-agent projects (твой `CURRENT_PRODUCT_STATE.md` + `reporting-continuity.md` rule)
- Closest analog: [Hamel's eval-first methodology](https://hamel.dev/blog/posts/evals/), Simon Willison's "context offloading", O'Reilly ["How to Write a Good Spec for AI Agents"](https://www.oreilly.com/radar/how-to-write-a-good-spec-for-ai-agents/) — все blog-grade, не template

#### Real gap

Конкретно underserved topics:
- Rule для "next agent resumes в <2 минуты"
- Merge-conflict discipline для `CURRENT_STATE.md`
- Когда truth-state contradicts memory — кто wins
- Multi-agent (Claude + Codex + Aider + human) collaboration patterns
- AGENTS.md converges но **content patterns** (что писать, как layer с rules) не стандартизированы

Цитата из [2026 Productivity Paradox](https://blog.exceeds.ai/ai-coding-agents-productivity-paradox/):
> Senior engineers -19% productivity from validation overhead; 98% more PRs, 91% longer reviews.

Это **fuel** для angle "вот как держать AI агентов от регрессии команды".

#### Honest assessment: **YES — template + blog, NOT code library**

Star ceiling на template repos реальный (hesreallyhim hit 36.8k), но конкуренция с everything-claude-code мега-агрегаторами серьёзная. Differentiation:
- **Operational truth-state focus** (не collection of snippets)
- **Multi-month project lifecycle** (как агенты остаются synced через месяцы)
- **Reference implementation** через scenario-gate + EnglishFriend как real example (не toy)

**Sequencing**:
1. Blog post #1 first (Oct 2026) — validate audience reaction
2. Если резонирует — template repo + 2 more blog posts (Nov-Dec 2026)
3. Если flop — записать learnings в scenario-gate ARCHITECTURE.md, не делать template

#### Effort + timing

- Blog post #1: 10-15ч (включая AI editing)
- Template repo + 2 more posts: 15-20ч
- **Total**: 25-35ч calendar 8-10 weeks

#### Hire signal: **MEDIUM (LOW для code-lib framing, HIGH для thought-leadership)**

"Agent-driven engineering" / "AI engineering productivity" roles появляются: Sourcegraph, Augment Code, MindStudio explicitly нанимают на это. Сильнее для DevRel / DX / Tooling roles, чем для core Applied AI. Anthropic/OpenAI care меньше (core applied roles), но **Anthropic Developer Experience** team / **GitHub Copilot agent mode** team / **Cursor** / **Augment** активно интересуются.

#### References

- [PatrickJS/awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules)
- [hesreallyhim/awesome-claude-code](https://claudefa.st/blog/tools/resources/awesome-claude-code)
- [Everything Claude Code 170k stars](https://www.augmentcode.com/learn/everything-claude-code-github-stars)
- [Complete guide to CLAUDE.md (Bijit Ghosh)](https://medium.com/@bijit211987/the-complete-guide-to-claude-md-memory-rules-loading-and-cross-tool-compression-97cc12ed037b)
- [Persistent memory system for Claude Code](https://www.mindstudio.ai/blog/persistent-memory-system-claude-code-agents)
- [Simon Willison — engineering practices for coding agents (YouTube)](https://www.youtube.com/watch?v=owmJyKVu5f8)
- [How to write a good spec for AI agents — O'Reilly](https://www.oreilly.com/radar/how-to-write-a-good-spec-for-ai-agents/)
- [2026 Productivity Paradox](https://blog.exceeds.ai/ai-coding-agents-productivity-paradox/)

---

### 3.3 Q1-Q2 2027: `langgraph-doc-audit` framework (Candidate 1) — **MAJOR EXTRACT**

#### Что это

Generic OSS framework для document-audit agents — structured findings (severity / citation / rule_id / evidence_span), hierarchical RAG над regulated documents, audit logger, vendor-neutral на parser и LLM. **Это hire signal anchor extract** на горизонте 18 месяцев.

**Public API draft**:
```python
from langgraph_doc_audit import (
    DocumentSession,       # lifecycle of audit
    AuditFinding,          # Pydantic schema: severity / rule_id / citation / evidence_span / confidence
    AuditLogger,           # compliance audit trail
    HierarchicalChunker,   # раздел → пункт → подпункт chunking
    HybridRetriever,       # BM25 + vector над regulated docs
    RuleRegistry,          # rule_id → check_fn mapping
    DocAuditGraph,         # LangGraph state machine для audit pipeline
)
```

**Состав release**:
- Lib v0.1.0 (~3-5k LOC)
- Один полный working example: simplified contract review (3 rules, 1 document type)
- Series of 3 blog posts: architecture / production lessons / case study
- HackerNews launch

#### Existing landscape

Document AI пространство в 2026: **dense на parser layer**, **crowded на platform layer**, **thin на opinionated audit-pipeline layer**.

**Parsers** (готовы, можно reuse):
- [Docling](https://github.com/docling-project/docling) — ~58k stars, IBM, USPTO/JATS/XBRL schemas, OpenShift Operator для банков
- [Unstructured.io](https://github.com/Unstructured-IO/unstructured) — typed elements (Title/NarrativeText/Table)
- [Marker-PDF](https://github.com/VikParuchuri/marker) — `--use_llm` cleanup
- MinerU, PyMuPDF4LLM, Kreuzberg

**Platforms** (closed или partial):
- LlamaCloud / LlamaParse + [Agentic Document Workflows](https://www.llamaindex.ai/blog/introducing-agentic-document-workflows) — JSON + page+coordinate citations, [contract-review notebook](https://github.com/run-llama/llamacloud-demo/blob/main/examples/document_workflows/contract_review/contract_review.ipynb), но vendor-anchored к LlamaCloud
- LlamaAgents — one-click deploy templates для invoice/contract/claims
- Haystack 2.x — pipelines + parsing only, **no audit-finding schema**
- [Microsoft GraphRAG](https://github.com/microsoft/graphrag) — cost issues (~$33k indexing на large datasets), entity-resolution by name only
- [Hebbia](https://www.hebbia.com/blog/inside-hebbias-deeper-research-agent) — Iterative Source Decomposition, closed
- [Harvey](https://medium.com/@takafumi.endo/how-harvey-built-trust-in-legal-ai-a-case-study-for-builders-786cc23c3b6d) — cascade-LLMs + RAG + o1 orchestration, closed
- [OpenContracts](https://github.com/Open-Source-Legal/OpenContracts) — MIT, **annotation-first** (humans label, then AI), не pipeline-first

#### Real gap

Цитата из research:
> No widely-adopted OSS lib offers the combination: **LangGraph-native audit graph + structured findings (severity/rule_id/citation/evidence_span) + hierarchical RAG over regulated docs**.

Конкретно:
- LlamaIndex contract-review notebook — **пример, не framework**: нет reusable `Finding` schema, нет rule registry, нет severity model, нет hierarchical-section retriever
- Docling парсит, но **нет audit pipeline**
- OpenContracts annotation-first
- Microsoft GraphRAG community complaints: governance/permissions/audit lifecycle "sits outside the framework"; [72-80% enterprise RAG never reaches production](https://medium.com/graph-praxis/graph-rag-in-2026-a-practitioners-guide-to-what-actually-works-dca4962e7517)
- Hebbia/Harvey patterns (citation-first, hyperlinked) — в blog posts, нет OSS reimplementation
- **Russian government regulated docs (твой госэкспертизы domain) — effectively zero OSS audit tooling**

#### Honest assessment: **YES-BUT-WAIT (6-12 months)**

Это **highest-leverage extract** в roadmap. **Но**:

**Два precondition'а перед start**:
1. Ship 2-3 audit projects internally (госэкспертиза + хотя бы один другой vertical через ту же framework) → Finding schema стабилизируется через real use. Если extract до 3 use cases → bake in госэкспертиза-specific assumptions.
2. Wait until LlamaIndex Agentic Document Workflows settle их API — сейчас они ship'ают fast, твой extract risks duplicating их direction.

**Realistic scope**: ~3-5k LOC. Deps: `langgraph`, `pydantic`, optional adapters для `docling` / `unstructured` / `marker` (no hard binding). Sweet spot: **audit-graph + Finding schema + rule registry + hierarchical retriever, vendor-neutral на parser и LLM**.

**Cite-or-refuse decoration fold-in**: Не делать standalone `cite-or-refuse` lib (Candidate 2 из research). Fold pattern (Instructor wrapper + reciprocal-verify + explicit refuse type) в `langgraph-doc-audit` как `doc_audit.citations` submodule. Standalone competes с Instructor brand, читается как wrapper. Внутри audit framework это **load-bearing infrastructure** с clear motivation.

#### Effort + timing

- v0.1.0 framework: ~3-5k LOC, ~100-130ч работы
- 3 blog posts + launch: ~25-30ч
- Documentation polish: ~10-15ч
- **Total**: ~140-175ч calendar 12-16 weeks parallel с full-time expertise работой
- **Start trigger**: Jan-Feb 2027 (после 6-9 мес production usage)
- **v0.1.0 ship**: April-June 2027

#### Hire signal: **HIGH**

Document AI — explicit [a16z "Big Idea for 2026"](https://www.linkedin.com/pulse/big-ideas-2026-according-a16z-partners-rub%C3%A9n-dom%C3%ADnguez-ibar-e3pme) (structuring unstructured enterprise data). Sequoia thesis: "workflow replacement with measurable efficiency, not general AI". 

**Anthropic Applied AI / OpenAI Forward Deployed Engineer roles** ($350-550k mid-senior; Anthropic median $600k) literally describe эту работу: embed with enterprise, build production document pipelines. Harvey / Hebbia / Spellbook hiring aggressively на ту же shape.

**Plus unique angle для CV**: "Open-sourced langgraph-doc-audit (X stars), deployed at Russian Federation Center of State Expertise for building permit document analysis" — это рассказ который **никто не может скопировать**.

#### NDA / Publication safety

**Перед стартом extract** (Q4 2026 — заранее):
- Получить explicit письменное согласие от руководства Центра на публикацию generic patterns
- Domain content (правила, scenarios, реальные документы, workflow Центра) — никогда не публикуется
- Architecture patterns + Finding schema + rule registry abstraction + retrieval strategy — generic, безопасно
- Optional: mention "deployed at state expertise center" в README — нужно отдельное разрешение

#### References

- [LlamaIndex contract review notebook](https://github.com/run-llama/llamacloud-demo/blob/main/examples/document_workflows/contract_review/contract_review.ipynb)
- [LlamaIndex Agentic Document Workflows](https://www.llamaindex.ai/blog/introducing-agentic-document-workflows)
- [Docling repo](https://github.com/docling-project/docling)
- [Unstructured-IO/unstructured](https://github.com/Unstructured-IO/unstructured)
- [OpenContracts](https://github.com/Open-Source-Legal/OpenContracts)
- [Hebbia ISD audit-trail blog](https://www.hebbia.com/blog/inside-hebbias-deeper-research-agent)
- [Harvey trust case study](https://medium.com/@takafumi.endo/how-harvey-built-trust-in-legal-ai-a-case-study-for-builders-786cc23c3b6d)
- [GraphRAG production limitations](https://medium.com/graph-praxis/graph-rag-in-2026-a-practitioners-guide-to-what-actually-works-dca4962e7517)
- [Best PDF parsers 2026](https://www.firecrawl.dev/blog/best-pdf-parsers)
- [a16z Big Ideas 2026](https://www.linkedin.com/pulse/big-ideas-2026-according-a16z-partners-rub%C3%A9n-dom%C3%ADnguez-ibar-e3pme)

---

### 3.4 SKIP STANDALONE: `cite-or-refuse` decorator (Candidate 2)

#### Почему **не** делать standalone

Research findings unambiguous:

- **Instructor уже делает 70%** того что нужно — [exact citations example](https://python.useinstructor.com/examples/exact_citations/) с Fact / QuestionAnswer schema, substring_quote validated против source, semantic validators, self-healing retries
- **rag-citation** (PyPI, March 2026) — SpaCy NER + sentence-transformers, hallucination flag на entities, beta
- **Outlines / llguidance / Guidance** — constrained generation, regex/CFG, но нет citation semantics
- **Pydantic AI** — structured output, model-agnostic, но **explicitly no uncertainty/refusal primitives**
- **Relari agent-contracts** — preconditions/pathconditions/postconditions, fits "refuse if precondition fails" pattern но contract DSL, не citation decorator

**Honest gap**:
> Нет lib которая делает (a) format-validated citations + (b) explicit refuse + (c) optional reciprocal verification в одном interface. Но gap **слишком thin** для standalone repo brand — это будет читаться как Instructor wrapper.

#### Куда fold

В `langgraph-doc-audit` (Candidate 1) как `doc_audit.citations` submodule. Там это **load-bearing infrastructure** с clear motivation (regulated documents требуют cite-or-refuse для compliance). Standalone — wrapper. Внутри audit framework — feature.

#### Exception (когда всё-таки делать standalone)

**Только если** найдёшь время для arXiv-grade benchmark (RAGTruth или ArchEHR-QA) показывающего measurable hallucination reduction vs Instructor-baseline. Тогда:
- Standalone lib + paper combo = strong hire signal
- Но это +50-80ч на benchmark + paper writing
- Не приоритет на 18-month horizon

#### References

- [Instructor exact citations example](https://python.useinstructor.com/examples/exact_citations/)
- [Instructor semantic validation](https://python.useinstructor.com/blog/2025/05/20/understanding-semantic-validation-with-structured-outputs/)
- [rag-citation PyPI](https://pypi.org/project/rag-citation/)
- [Stanford Legal RAG hallucination study](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf) — commercial legal RAG hallucinates 17-33%
- [Mitigating hallucination survey](https://arxiv.org/html/2510.24476v1)
- [FACTUM paper](https://arxiv.org/abs/2601.05866)
- [Citation-Grounded Code Comprehension (arXiv 2512.12117)](https://arxiv.org/abs/2512.12117)

---

## 4. Дополнительные посты (без привязки к библиотеке)

Возможные посты из накопленного опыта, которые **не требуют** extract библиотеки. Можно вставлять между основными работами для поддержания регулярности публикаций.

Для каждого поста — **два заголовка**: для англоязычной аудитории (dev.to / Medium / LinkedIn / Hacker News) и для русскоязычной (Habr). Конкретный угол подачи (hook) показывает с чего начинать пост, чтобы читатель не закрыл вкладку.

### 1. Обязательные vs наблюдательные тесты для AI агента (Q3 2026, ~10ч)

- **EN**: *"Mainline vs Advisory: How I Stopped My LangGraph CI From Failing on Every Push"*
- **RU (Habr)**: *"Делим тесты AI-агента на обязательные и наблюдательные: как заставить CI не падать на каждой мелочи"*
- **Hook**: "За первый месяц CI нашего AI-агента падал 47 раз. Из них 3 — настоящие баги, 44 — флаки eval'ов. Команда начала игнорировать красные сборки. Решение оказалось простым: разделить тесты на две категории."
- **Источник**: работа над scenario-gate

### 2. Скрытые сбои в conversational AI (Q3 2026, ~8ч)

- **EN**: *"The Secret Failure Mode No One Talks About: When AI Quietly Says Nothing"*
- **RU (Habr)**: *"AI-агент тихо сломался — и никто не заметил. Как ловить такие ошибки в CI"*
- **Hook**: "Вы пишете промпт, тесты проходят, продакшен работает. Через неделю эксперт находит: на 30% запросов агент вместо ответа выдаёт уклончивое 'я не могу проанализировать этот документ'. Логи чистые, метрики зелёные. Что произошло?"
- **Источник**: проверка `fallback_leak` в scenario-gate

### 3. Внедрение scenario-gate в продакшен (Q3 2026, ~12ч)

- **EN**: *"6 Months of scenario-gate in Production: What Worked, What Broke"*
- **RU (Habr)**: *"Как мы внедрили автоматическую проверку качества AI-агента в продакшен: 6 месяцев в Центре госэкспертизы"*
- **Hook**: "Шесть месяцев назад мы поставили условие: ни один pull request с изменением AI-агента не мержится без зелёного scenario-gate. За эти полгода: 12 пойманных регрессий, 3 политических конфликта с экспертами, одна крупная переделка концепции после первого месяца. Делюсь конкретными цифрами."
- **Источник**: EnglishFriend + Центр госэкспертизы (после 6 месяцев работы)
- **NDA**: только generic уроки, без конкретики о документах или правилах Центра

### 4. Sticky-routing: почему агент "забывает" о чём говорили (Q3 2026, ~12ч)

- **EN**: *"Sticky Routing: Why Your LangGraph Agent Drifts on Turn 3 (And How to Fix It)"*
- **RU (Habr)**: *"AI-агент 'забывает' о чём вы говорили на 3-м сообщении: причины и решение для LangGraph"*
- **Hook**: "Пользователь говорит 'помоги подготовиться к собесу на ML-инженера'. Первый ответ агента — отлично. Второй — про английский. Третий — про вокабуляр. К пятому сообщению агент уже на другой планете. Это известная проблема: на каждом ходу LLM-роутер заново решает, что хочет пользователь, и иногда меняет своё решение. Покажу простой паттерн который это лечит."
- **Источник**: routing classifier в EnglishFriend

### 5. Документ актуального состояния проекта vs AI-агент (Q4 2026, ~12ч)

- **EN**: *"Truth-State Docs: How to Stop AI Coding Agents from Drifting Your Codebase"*
- **RU (Habr)**: *"Как не дать AI-агентам сломать ваш проект: 'документ актуального состояния' как защита от регрессии"*
- **Hook**: "На большом проекте, где Claude Code и Codex работают параллельно с человеком, через месяц начинается дрейф: один агент пишет код противоречащий другому, оба ссылаются на устаревшие соглашения. Спасает один файл — единый источник правды о текущем состоянии проекта, который агенты обязаны читать и обновлять."
- **Источник**: pattern `.claude/rules/` + `CURRENT_PRODUCT_STATE.md` в EnglishFriend

### 6. Совместная работа Claude + Codex + человек (Q4 2026, ~10ч)

- **EN**: *"Claude, Codex and Me: How Three Agents Work on One Codebase Without Stepping on Each Other"*
- **RU (Habr)**: *"Claude, Codex и я: как трём агентам работать над одним проектом без конфликтов"*
- **Hook**: "У меня в проекте параллельно работают два AI-инструмента (Claude Code и Codex CLI) плюс я сам. Без общих правил это хаос: каждый делает по-своему, версии конфликтуют, документация устаревает на разных скоростях. Расскажу про правила игры, которые позволяют троим не наступать друг другу на ноги."
- **Источник**: реальный опыт работы

### 7. Когда память агента врёт (Q4 2026, ~8ч)

- **EN**: *"When Memory Lies: My Agent Spent a Month Reading Stale Project State"*
- **RU (Habr)**: *"Когда память агента врёт: как Claude месяц читал устаревшее состояние моего проекта"*
- **Hook**: "Claude Code умеет сохранять заметки между сессиями. Это супер удобно — но опасно. Месяц назад я обнаружил, что половина моей памяти про проект устарела, а агент уверенно ссылался на эти заметки как на текущее состояние. Что пошло не так и как защититься."
- **Источник**: реальный инцидент с memory system

### 8. Qwen on-prem для AI в гос-секторе (Q1 2027, ~15ч)

- **EN**: *"Self-Hosted Qwen for Regulated AI: A Field Report from a Russian Government Project"*
- **RU (Habr)**: *"Qwen на собственном железе для AI в гос-секторе: что не пишут в туториалах"*
- **Hook**: "Все туториалы про vLLM показывают как развернуть модель за 10 минут. В реальном продакшене для гос-проекта это: согласование железа 2 месяца, vendor-lock у NVIDIA, обновление CUDA ломающее всё, thinking-режим Qwen3 жрущий все токены в `<think>...</think>`. Расскажу про подводные камни на конкретном проекте (без конкретики о домене — NDA)."
- **Источник**: Центр госэкспертизы (после 6+ мес работы)
- **NDA**: только технические уроки, без упоминания типов документов или правил

### 9. Почему я не использую LangSmith (Q2 2026, ~10ч)

- **EN**: *"Why I'm Not Using LangSmith (And Built My Own Eval Framework Instead)"*
- **RU (Habr)**: *"Почему я отказался от LangSmith в пользу собственного решения (с цифрами и инцидентами безопасности)"*
- **Hook**: "LangSmith — стандарт по умолчанию для LangChain-проектов. Сотни тысяч пользователей. Я не использую его. Расскажу про три конкретные причины: ценник в 5-значных цифрах при росте трафика, лок на их инфраструктуру, два инцидента безопасности в 2025-2026. Для гос-проекта это deal-breaker."
- **Источник**: scenario-gate motivation + research конкурентов

### 10. Год строил AI для российского строительного нормирования (Q3 2027, ~15ч, capstone)

- **EN**: *"Building AI for Russian Building Code: A Year of Surprises"*
- **RU (Habr)**: *"Год строил AI для проверки проектной документации в России. Что оказалось совсем не так, как я думал"*
- **Hook**: "Год назад меня пригласили построить AI-систему для одной из госструктур, проверяющих проектную документацию. Я думал: PDF → LangGraph → готово. На деле: чертежи в DWG, нормативы пересекаются и противоречат друг другу, эксперты не доверяют любому ответу без точной цитаты, regулятор требует объяснения каждого решения. Делюсь главными уроками."
- **Источник**: Центр госэкспертизы (capstone после года работы)
- **NDA**: только generic уроки, без конкретики о Центре или правилах

### Правило ритма

Один пост в 2-4 недели — это устойчивый темп без выгорания. 10 постов × ~10ч в среднем = ~100ч календарного времени за 6-12 месяцев. Идёт параллельно с работой над библиотеками.

### Стратегия распространения каждого поста

- **Первая публикация**: dev.to (англоязычная аудитория разработчиков)
- **День 3**: Hashnode (дополнительная индексация)
- **День 5**: LinkedIn (для видимости рекрутёрами)
- **День 7**: тред в X/Twitter с ключевыми мыслями
- **День 10**: Habr (русскоязычная аудитория, для бренда в RU-сообществе) — **с русским заголовком**, не транслитерацией английского
- **Hacker News "Show HN"**: только для запусков библиотек (1-2 раза в год максимум, иначе спам)

---

## 5. Anti-roadmap (что точно НЕ делать в эти 18 месяцев)

Если возникнет соблазн — вернись к этому списку:

- ❌ **Не делать 2 OSS lib параллельно.** Anti-pattern №1 для соло-разработчика.
- ❌ **Не возвращаться к voice-langgraph.** Voice не релевантен active threads. Заморожен в `SCENARIO_GATE_EXTRACT_PLAN.md`.
- ❌ **Не делать `cite-or-refuse` standalone.** Fold в `langgraph-doc-audit`. Без benchmark — wrapper.
- ❌ **Не engineer `langgraph-doc-audit` до 3+ use cases.** Будет wrong abstraction.
- ❌ **Не запускать Discord servers / community channels** для каждой lib. GitHub Issues + Discussions хватит на 100+ users. Discord = full-time community management.
- ❌ **Не делать documentation sites** (Sphinx / MkDocs / Docusaurus) для v0.1-v0.2 libs. README + 3-4 .md файла достаточно. Documentation site = когда лib > 50 contributors.
- ❌ **Не делать TypeScript / JS / Rust ports** any lib. Python audience огромная сама по себе.
- ❌ **Не пытаться монетизировать любую OSS lib** в этом horizon. Cloud hosted version / paid tier — это новый бизнес, не extract. Hire signal первоочередно.
- ❌ **Не делать "scenario-gate cloud" hosted service** — у нас уже LangSmith этого боимся, не повторять mistake.
- ❌ **Не публиковать ничего связанное с domain content** Центра госэкспертизы. Generic patterns OK с письменным разрешением; правила/документы/workflow — никогда.
- ❌ **Не делать YouTube channel параллельно с blog posts.** Video production = +20ч per video, нет окупаемости на этом этапе.
- ❌ **Не contribute к закрытым / dying проектам.** AgentEvals от LangChain — small but active, contribute. NeMo Guardrails — слишком вендорно. Inspect AI — government-backed, активен. Выбор partner важен.

---

## 6. Validation gates (когда re-evaluate этот roadmap)

Этот документ написан 2026-05-16. Следующие checkpoint'ы для пересмотра:

### Checkpoint 1: после scenario-gate v0.1.0 launch (август 2026)
- Что измеряем: stars trajectory, PyPI downloads, blog post reads, inbound DMs/issues
- Если 90th percentile result (200+ stars, 1500+ downloads) → следуем плану (Candidate 4 next)
- Если < 50 stars → diagnose positioning, possibly skip Candidate 4 и go straight to Candidate 3 (template repo может resonate better)
- Если viral (1000+ stars, HN front page) → consider бросать expertise project ради full-time на OSS thread? **Нет** — runway важнее. Просто accelerate timeline.

### Checkpoint 2: после Q3 2026 sticky router (октябрь 2026)
- Validates ли rules в section 4 (blog-first approach work для thin patterns)?
- Если sticky router blog получил traction но lib flop — rule "content > thin lib" подтверждена
- Если оба провалились — pivot strategy

### Checkpoint 3: перед `langgraph-doc-audit` extract (декабрь 2026 — январь 2027)
- Have we shipped 2-3 audit projects internally в Центре?
- Stabilized Finding schema?
- Получили ли мы NDA согласие на generic patterns publication?
- Если нет любого из 3 → defer на 3 месяца, не start

### Annual review (Май 2027)
- Сравнить actual results vs predictions в section 2
- Update hire signal estimates based on market changes
- Possible new candidates (AI инфра rapidly меняется, через год могут появиться новые gap'ы)

---

## 7. Cross-comparison final priorities table

| # | Candidate | Gap size | Hire signal | Effort | Audience | Timing | Recommendation |
|---|-----------|----------|-------------|--------|----------|--------|----------------|
| 0 | **scenario-gate** (CURRENT) | Large | Very High | 40ч | 100k+ LangGraph users | Q2-Q3 2026 | **ACTIVE — see SCENARIO_GATE_EXTRACT_PLAN.md** |
| 4 | Sticky Router + drift | Medium | Med-High | 15-30ч | LangGraph + multi-turn agent builders | Q3 2026 | **NEXT — blog first** |
| 3 | Truth-State Template + blog | Medium | Med (High thought-leadership) | 25-35ч | All AI-coding-agent users | Q4 2026 | **AFTER #4** |
| 1 | **langgraph-doc-audit** | **Large** | **HIGH** | 140-175ч | Vertical AI builders, legal/medical/govt | Q1-Q2 2027 | **MAJOR EXTRACT — wait for production stability** |
| 2 | cite-or-refuse | Medium-small | Medium | 30ч standalone OR fold-in | RAG builders | — | **SKIP standalone, fold into #1** |

---

## 8. Hand-off для следующих сессий

Если возвращаешься к этому документу через дни/недели/месяцы:

- [ ] Какой текущий active thread? (см. section 1, обновлять)
- [ ] Прошёл ли последний planned validation gate? (см. section 6)
- [ ] Появились ли новые market signals (a16z reports / Anthropic careers updates / new arXiv papers) что меняют hire signal estimates?
- [ ] Что в `## Current decisions log` (записывай ниже когда принимаешь decision)?

Если ты Claude/Codex агент, читающий этот файл:
- **Section 5 (Anti-roadmap) — sticky правило.** Не предлагай нарушать без явного user override.
- При предложении нового кандидата extract — сначала проверить research format из section 3 (existing landscape → real gap → honest assessment → effort → hire signal → references). Без этого формата — predprovedeniy не давай.
- **Если автор спрашивает про competing thread в active period** — напомни principle "one active OSS thread maximum" и предложи waiting / reordering, не parallel start.
- **Один section в этом файле обновляется при milestone**: section 1 (current state) после каждого launch / freeze / major decision.

---

## Current decisions log

(будет пополняться при каждом milestone)

- **2026-05-16**: Roadmap создан. Active threads = expertise project (full-time) + scenario-gate (parallel). Sequencing approved: scenario-gate → sticky router → truth-state template → langgraph-doc-audit. cite-or-refuse skip standalone, fold в doc-audit.
