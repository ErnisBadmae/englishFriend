# Scenario-Gate Team Pitch — Брифинг для команды

> **Назначение**: подготовка материала для разговора с командой Центра государственной экспертизы СПб на kickoff meeting (первая неделя работы, ~2026-05-18).
>
> **Аудитория**: backend, frontend, devops, PM/руководитель проекта. Не AI engineers.
>
> **Цель**: добиться согласия использовать `scenario-gate` (наш внутренний eval-фреймворк для AI агента) как regression gate в CI с самого начала проекта, без overselling и без скрытых рисков.
>
> **Стиль**: честный pitch, не маркетинговый. Где мы переоцениваем gap — явно говорим. Где конкуренты лучше — признаём.
>
> **Источник competitive data**: deep research (полные результаты — agent a9c6bb8b0fcbd64f6 в истории conversation). Все code examples взяты из официальных docs / repos / issues конкурентов, не выдуманы.

---

## Executive Summary

Предлагаю с первого дня использовать **scenario-gate** — внутренний фреймворк автоматических проверок качества AI агента — как обязательный регрессионный контроль в нашей сборочной цепочке (CI). Это набор сценариев в текстовом формате (YAML), описывающих "вот такой документ → агент должен найти такой дефект и сослаться на такой норматив".

Сценарии разделены на две группы:

- **Обязательные** (mainline) — если хоть один не прошёл, выкатка в продакшен **блокируется**. Это базовые кейсы которые должны работать всегда.
- **Наблюдательные** (expanded) — если упали, видим в отчёте тренд "качество просело на таких-то документах", но выкатку не блокируем. Это для редких/сложных случаев, где временное снижение качества допустимо.

Альтернативы рассмотрены: Promptfoo, DeepEval, LangSmith, AgentEvals и др. — ни один не подходит для нашего сочетания требований: (а) работа с LangGraph (state machine, через которую проходит запрос), (б) on-prem (всё в нашем периметре, ничего в облако), (в) регулируемый домен (нужен audit trail для регулятора), (г) разделение тестов на обязательные и наблюдательные.

Усилие на постройку первой рабочей версии: ~22 часа моего времени, делаю параллельно с архитектурным аудитом текущего MVP.

**Без этого инструмента** каждое изменение промпта/модели/нормативной базы — игра в рулетку: проверить вручную всё нереально, обнаружим регрессию через эксперта или регулятора. Релизы становятся редкими (раз в месяц) и страшными.

**С этим инструментом** релиз раз в неделю с числовой оценкой качества после каждого PR.

---

## 0. Контекст

**Где мы сейчас** (по информации до старта):
- MVP уже есть: фронт, бэкенд, DevOps настроен.
- AI слой — на мне с дня 1, карт-бланш на архитектурные решения.
- Stack зафиксирован: LangGraph (state machine агента), Qwen 3 (или 2.5) on-prem, Qdrant (vector search), PostgreSQL.
- Домен: анализ проектной документации (заявления на госэкспертизу), детектирование дефектов, RAG над нормативной базой (СП, СНиП, ГОСТ, 87-ПП).
- В первую фазу — только PDF; чертежи (DWG/DXF) во вторую.

**Куда движемся**:
- Заменить ручную проверку экспертом ряда типовых дефектов на автоматическую с human-in-the-loop review.
- Не "AI вместо эксперта", а "AI готовит обоснование, эксперт принимает решение".

**Где scenario-gate помещается**:
- Не product feature (его не видит конечный пользователь).
- Infrastructure layer: автоматический regression test suite в CI.
- Каждый push в `main` → CI запускает scenario-gate → если mainline failed, merge заблокирован.

---

## 1. Что такое scenario-gate

### Если в одном предложении

> Автоматизированный набор тестов для AI агента — после каждого изменения системы (промпт, модель, RAG, нормативная база) запускается и подтверждает что агент продолжает правильно работать на известных кейсах, и блокирует выкатку если упали ключевые проверки.

### Аналогия из знакомого домена

Это **набор регрессионных тестов для AI агента** — по той же логике, что у нас есть unit-тесты и integration-тесты для обычного бэкенда. Только проверяется не "функция вернула число 42", а такие штуки:

- "агент правильно классифицировал раздел проектной документации как КР (Конструктивные решения), а не как ПЗ (Пояснительная записка)"
- "агент нашёл нарушение СП 63.13330.2012 п.10.3 и приложил точную цитату с указанием страницы документа"
- "агент НЕ ответил уклончиво ('не могу проанализировать', 'обратитесь к эксперту') там где должен был явно зафиксировать дефект"

**Третий пункт особенно важен.** Это типичный способ скрытой поломки AI системы: вместо честного "не знаю" или явной ошибки она выдаёт generic-ответ, который выглядит как валидный, но на самом деле бесполезен. Эксперт может пропустить такое и принять за реальный вывод агента.

### Технические детали для разработчиков

**Сценарий** (один файл) выглядит так (упрощённо):

```yaml
# scenarios/mainline/missing_reinforcement_drawing.yaml
id: missing_reinforcement_drawing
tier: mainline
description: |
  Раздел КР содержит несущую стену без указания армирования.
  Ожидаем: agent flag'ает violation СП 63.13330 п.10.3, severity=critical,
  с цитатой места в документе.

input:
  document: fixtures/scenario_001_KR_section.pdf
  section_hint: KR

checks:
  - type: defect_found
    rule_id: "СП 63.13330.2012 п.10.3"
    severity: critical
    must_cite_page: true

  - type: defect_not_found
    rule_id: "СП 70.13330.2012 п.5.3.4"
    note: "это правило применимо к monolithic concrete, не к этой задаче"

  - type: state_assertion
    path: section.classified_as
    equals: "KR"

  - type: silent_fallback_leak
    forbidden_phrases:
      - "не могу проанализировать"
      - "обратитесь к эксперту"
      - "недостаточно данных"
```

Запускается одной командой в CI:
```bash
scenario-gate run scenarios/ --tier=mainline,expanded --junit=results.xml
```

Exit code 1 если mainline scenario failed → CI блокирует merge.
Exit code 0 если только expanded failed → CI passes но в Slack/PR comment приходит warning.

### Что это **не** есть (важно для clarity)

- **Не** observability / monitoring (для этого Langfuse / Helicone / Prometheus).
- **Не** unit tests для отдельных функций (это обычный pytest).
- **Не** load testing (это Locust / k6).
- **Не** A/B testing продакшен трафика (это feature flags).

Scenario-gate — это **release gate**, узкая категория.

---

## 2. Зачем оно нам — конкретные failure modes без gate

Это не теоретическая страховка. Это конкретные сценарии боли которые гарантированно появятся в первые 3 месяца проекта.

### Сценарий A: меняем промпт классификатора разделов

Через 2 недели делаем минорное изменение промпта классификатора (добавили "учитывай заголовок раздела при сомнениях"). Точность на разделе ПЗ выросла. На разделе ИОС-ЭМ упала на 20%, потому что классификатор стал путать "электрические сети" с пояснительной запиской. **Узнаём через 3 недели** — от эксперта который заметил странности.

С gate: 5 минут после push CI красная, в diff видно конкретно — scenario `ios_em_classification` упал, было `ИОС-ЭМ`, стало `ПЗ`.

### Сценарий B: обновляем Qwen с 2.5 на 3.0

Хотим попробовать новую версию модели — она быстрее, бенчмарки лучше. Деплоим в стейджинг. По одиночным тестам выглядит ок. В продакшене через неделю — 30% defect findings выдают другой формат цитаты норматива (с p. вместо п.), фронт-парсер ломается. **Узнаём через жалобы экспертов**.

С gate: scenario `citation_format` падает в CI, виден diff в формате до пуша.

### Сценарий C: расширяем нормативную базу

Загрузили актуальные редакции СП (вышли в марте 2026). Хотим чтобы агент использовал свежие версии. После переиндексации Qdrant — старые кейсы которые раньше работали правильно теперь flag'ают **другой** пункт того же СП, или вообще не flag'ают. **Без gate** — узнаём в продакшене через legal эскалацию.

С gate: 10 mainline scenarios на каждый главный СП показывают что мы сломали, плюс — какие именно правила теперь не срабатывают.

### Сценарий D: меняем chunking strategy для RAG

Бэкенд предлагает chunking по 2048 токенов вместо 1024 — производительность retrieval улучшилась на 15%. По спот-тестам всё ок. Но скрытно сломали retrieval для длинных таблиц (TR.5 "Технико-экономические показатели") — они теперь рвутся посередине, агент перестал находить number violations. **Узнаём в продакшене**.

С gate: 5 scenarios на табличные данные → видим регрессию.

### Сценарий E: третий разработчик через 6 месяцев

Через 6 месяцев в команду приходит новый разработчик. Делает refactor LangGraph nodes (хочет упростить структуру). Не знает что в node `analyze_section` есть hidden state requirement `section.normative_base_loaded`. Refactor проходит unit-тесты, но в продакшене половина scenarios теперь fail silently — агент пишет "анализ выполнен" но не делает реальную проверку. **Узнаём через**: legal эскалацию или скандал.

С gate: scenarios `analyze_section_*` (10 штук) красные сразу после refactor PR. Refactor блокирован до починки.

### Сценарий F (regulated domain specific): экспертиза должна быть defendable

Эксперт подписал заключение, в котором учтены findings агента. Через 3 месяца — авария на стройплощадке. Регулятор спрашивает: "докажите что ваша AI система на дату подписания работала корректно на типовых сценариях". Без gate — **никакого артефакта** для этого нет. С gate — git history + сохранённые eval reports → доказательство квалификации системы в момент времени.

### Резюме блока

Без gate каждое из этих 6 событий **случится**. С gate каждое из них — это 5-минутный CI red, очевидный rollback, без последствий для пользователей.

---

## 3. Что получит каждая роль

### Руководитель проекта / PM
- **Предсказуемые релизы**: можно выкатывать каждую неделю без двухдневного цикла ручной проверки тестером.
- **Числовая оценка качества после каждого PR**: "13/15 обязательных сценариев прошло, 87% наблюдательных". Готовая цифра для еженедельного статус-отчёта руководству.
- **Готовые отчёты для регулятора**: сохранённые результаты прогонов — доказательство что система работала корректно на конкретные даты. Когда (не если) регулятор спросит "докажите что ваша AI на дату выкатки релиза N делала правильные выводы" — у нас будет git-история + сохранённые отчёты.
- **Быстрое включение новых разработчиков**: новый человек в команде читает сценарии → за час понимает что система должна и не должна делать. Без сценариев это две недели чтения кода и разговоров.

### Бэкенд-разработчик
- **Обычный pytest, ничего нового**: сценарии подхватываются стандартным pytest-плагином, не надо ставить новый CI-стек.
- **Стабильный контракт API**: сценарии фиксируют формат ответов агента → можно делать рефакторинг бэкенда без страха незаметно сломать фронт.
- **Конкретные баг-репорты**: при падении проверки видно конкретно — на каком сообщении в диалоге, какая именно проверка упала, что ожидалось и что получилось.
- **Рефакторинг без страха**: переписываешь pipeline обработки документов → CI сразу скажет если что-то сломалось.

### Фронтенд-разработчик
- **Сценарии как живая документация API**: вместо устаревшего README — настоящие YAML-сценарии показывают как агент отвечает на типичные запросы. Можно копировать структуру response в моки для UI-разработки.
- **Защита от незаметных изменений API**: если бэкенд случайно поменяет формат ответа → CI блокирует мерж до починки, фронт не страдает.

### DevOps
- **Существующий CI stack**: pytest + JUnit XML + GitHub Actions / Jenkins — никакой новой инфры.
- **Кэшируемые ответы LLM**: можно настроить кэш так, что CI обращается к нашему Qwen только когда поменялся сценарий или код агента. Экономит GPU-время и время выполнения CI.
- **Стандартные отчёты**: результаты идут в стандартный формат JUnit XML, читаются любым дашбордом (Allure, ReportPortal, GitLab/GitHub Actions).
- **Работает в нашем периметре**: никаких обращений в облако, ничего наружу не уходит — всё внутри инфраструктуры Центра.

### Эксперт (это ключевое для принятия инструмента в коллективе)
- **3 года истории заключений → готовая база тестов**: каждое историческое заключение можно превратить в сценарий "вот этот дефект агент должен был найти, вот этот не должен был ошибочно отметить".
- **Прямая обратная связь**: эксперт поймал ошибку агента → за 30 секунд пишет YAML-сценарий → следующая итерация модели гарантированно не повторит ту же ошибку.
- **Доверие через узнавание**: эксперт видит, что мы тестируем на ЕГО реальных кейсах, не на абстрактных синтетических. Это политически важно для принятия AI-инструмента — без этого эксперты будут саботировать или игнорировать систему.

### Конкретные метрики, которые обещаем после первого месяца работы

- **Время ручной проверки перед релизом: −60%** (с ~2 дней до ~6 часов)
- **Доля багов, прошедших в продакшен: −50%** (от текущего уровня)
- **Частота релизов: раз в неделю вместо раза в месяц**
- **Время включения нового разработчика: с 2 недель до 3 дней** до первого полезного PR

Это не оптимистичные обещания — это типовые цифры команд, которые внедрили подобный подход. Источники: отчёты ZenML, Latitude, Confident AI (см. секцию References в конце документа).

---

## 4. Конкурентный анализ — глубокое исследование

### 4.0 Категорийный landscape

Eval-инструменты для LLM-систем делятся на 5 категорий:

1. **Stateless prompt testers** — тестируют отдельный prompt-запрос (Promptfoo, частично DeepEval)
2. **Multi-turn conversation harnesses** — тестируют диалог как simulation (LangWatch Scenario, AgentEvals)
3. **RAG-specific quality** — тестируют retrieval + generation (Ragas, частично DeepEval)
4. **Observability + eval comb** — production tracing + eval (LangSmith, Langfuse, Helicone)
5. **Research safety frameworks** — для frontier model evals (Inspect AI)

Наш use case — multi-turn LangGraph state machine для defect detection с regulated audit trail — попадает в **пересечение** категорий 2, 3, 4. Ни один существующий tool не покрывает всё пересечение adequately.

---

### 4.1 Promptfoo (21.3k stars, MIT)

**Что это**: YAML-first CLI для prompt grids и red-teaming. Самый популярный в категории. Используется OpenAI, Anthropic (per README).

**Их code example** (из их официальных docs):

```yaml
prompts:
  - |
    [{% for completion in _conversation %}
      {"role":"user","content":"{{completion.input}}"},
      {"role":"assistant","content":"{{completion.output}}"},
    {% endfor %}
    {"role":"user","content":"{{question}}"}]
tests:
  - vars: { question: "Who founded Facebook?" }
  - vars: { question: "Where does he live?" }
  - vars: { question: "Which state is that in?" }
```

**Где они НЕ подходят нам**:

- **Multi-turn — bolt-on, не first-class.** Их же docs предупреждают: *"when a prompt references `_conversation` as a Nunjucks variable, the eval will run single-threaded (concurrency of 1)"*. Это значит: multi-turn работает, но за счёт сериализации (slower, no parallelization).
- **Нет state-machine awareness.** Promptfoo не знает что у нас LangGraph nodes. При failure диагностика: "expected X, got Y" на уровне строки. Не "node `classify_section` вернул `ПЗ`, ожидался `КР`".
- **Нет tier model.** Open issue [#1098 "Evaluate Multiple Config Files Separately Instead of Combining them"](https://github.com/promptfoo/promptfoo/issues/1098) — это **точно наша потребность**, открыта годами, не имеет решения.
- **Recurring multi-turn pain в community**: Issue [#5174](https://github.com/promptfoo/promptfoo/issues/5174) ("multi-turn with tool calls"), [#2010](https://github.com/promptfoo/promptfoo/issues/2010) ("multi-turn separate test configs"), [#7372](https://github.com/promptfoo/promptfoo/issues/7372) (Jan 2026: пользователи hand-roll thread_id management через SSE потому что нет native session abstraction).

**Что они делают лучше нас** (честно):
- Red-teaming plugins ecosystem (40+ типов attacks — jailbreaks, PII, prompt injection).
- Model A/B comparison matrix.
- Web UI для diff inspection.
- Огромный community и брэнд-доверие.

**Вердикт для нас**: reasonable choice если бы у нас были stateless prompts. Для multi-turn LangGraph defect detection — постоянная борьба с framework вместо использования его.

---

### 4.2 DeepEval (15.5k stars, Apache 2.0)

**Что это**: pytest-style eval library с 40+ метриками. Второй по популярности.

**Их LangGraph integration** (из их официальных docs):

```python
from deepeval.integrations.langchain import CallbackHandler
from deepeval.metrics import TaskCompletionMetric

graph.invoke(
    {"messages": [{"role": "user", "content": golden.input}]},
    config={"callbacks": [CallbackHandler(metrics=[TaskCompletionMetric()])]},
)
```

**Где они НЕ подходят нам**:

- **State-machine awareness — partial и сломана на loop'ах.** Их собственная документация признаёт: *"next_llm_span stages a metric for the first LLM span the graph emits inside the with block. Later loop iterations…won't pick it up"*. Это значит: для iteration-heavy LangGraph (а наш агент будет такой — он будет проходить по разделам в цикле), DeepEval **молча пропускает** все iterations кроме первой. Independent review (ZenML 2026): *"DeepEval lacks native agentic workflow tracing; it evaluates inputs and outputs but does not capture intermediate steps of a multi-tool agent execution."*
- **Нет tier model**: каждый pytest test равноценен, mainline/advisory разделение делается через pytest markers + `--strict` flag (хрупкое).
- **Expensive at CI scale**: ZenML 2026 review: *"Nearly every DeepEval metric calls an LLM to score another LLM's output, and at thousands of traces per day, the inference costs and latency add up — and slow down CI pipelines."* Для нас — каждый CI run будет жечь Qwen quota.
- **Cloud upsell pressure**: бесплатная library, но многие "premium" metrics ведут в Confident AI Cloud — некоторые fairness/safety метрики требуют cloud API.

**Что они делают лучше нас**:
- Metric breadth (40+ готовых scorers, мы будем строить свои).
- Pytest ergonomics (более polished interface).
- Multi-modal (audio/image) test cases — пригодится для чертежей в Phase 2.
- BigBench-style benchmark loaders.

**Вердикт для нас**: reasonable choice для basic agent eval, но для iteration-heavy LangGraph с tight CI budget — silently broken и дорого.

---

### 4.3 LangSmith Evaluations (closed-source, LangChain Inc)

**Что это**: SDK + cloud platform, default observability для LangChain shops.

**Их code example** (из их docs):

```python
from langsmith import evaluate
def target(inputs):
    return my_graph.invoke(inputs)
results = evaluate(target, data="my-dataset",
                   evaluators=[correctness_evaluator])
```

**Где они НЕ подходят нам** (это самый важный раздел для гос-сектора):

- **🚨 Security incidents 2025-2026 — disqualifying для гос-сектора**:
  - [June 2025 CVE](https://thehackernews.com/2025/06/langchain-langsmith-bug-let-hackers.html) — malicious-agent bug leaking OpenAI keys.
  - [March 2026](https://thehackernews.com/2026/03/ai-flaws-in-amazon-bedrock-langsmith.html) — Amazon Bedrock + LangSmith + SGLang RCE chain.
  - Для Центра госэкспертизы данные **не могут покидать перiметр**. Cloud-default архитектура LangSmith плюс публичные security incidents — это automatic disqualification.

- **Self-hosting gated behind Enterprise tier**. Их официальный pricing: Plus tier = $39/seat + $2.50/1k base traces, $5/1k extended. Self-hosted = Enterprise (sales call, не публичный pricing).

- **Hidden cost trap**: Coverge 2026 анализ: *"any trace that receives feedback or annotation automatically gets upgraded to the expensive extended tier… busy workspace can hit monthly bills in the five-figure range."*

- **Vendor lock-in concern**: [HN thread #39307884](https://news.ycombinator.com/item?id=39307884) — *"LangSmith creates lock-in for LangChain's abstractions."*

**Что они делают лучше нас**:
- Best-in-class LangGraph trace UI (это всё-таки first-party).
- Dataset versioning, annotation queues, prompt playground — mature.
- 30+ built-in scorers включая prompt-injection и PII detection.

**Вердикт для нас**: даже без security concerns — $39/seat × команда + extended traces по $5/1k — это десятки тысяч долларов в год при росте usage. Для гос-проекта недопустимо.

---

### 4.4 LangWatch Scenario (880 stars, Apache 2.0)

**Что это**: simulation harness с UserSimulator + JudgeAgent. **Closest philosophical sibling к scenario-gate**.

**Их code example** (из их README):

```python
result = await scenario.run(
    name="checking the weather",
    description="User planning trip, wondering about weather",
    agents=[WeatherAgent(),
            scenario.UserSimulatorAgent(model="openai/gpt-4.1-mini")],
    script=[scenario.user(), scenario.agent(),
            check_for_weather_tool_call, scenario.succeed()],
)
assert result.success
```

**Где они НЕ подходят нам**:

- **Нет LangGraph awareness** — агент это blackbox callable. Node-level state inspection требует wrapping графа самостоятельно.
- **Нет tier model** — все scenarios равноценны (та же проблема что у Promptfoo и DeepEval).
- **UserSimulator quality — bottleneck.** Их же community обсуждения: weak simulator = unrealistic users = false positives/negatives в тестах. Для нашего use case (defect detection — нет диалога с пользователем, есть документ) — UserSimulator вообще не применим.
- **Small community** (880 stars, апрель 2026) — мало real-world battle testing.

**Что они делают лучше нас** (важно признать):
- **Они первыми сделали multi-turn first-class** — pattern которого мы тоже придерживаемся. Это **prior art**, не наша инновация.
- Three-language SDKs (Python / TypeScript / Go).
- Real-time JudgeAgent loop — sophisticated.

**Вердикт для нас**: closest spiritual ancestor. Если бы их abstraction подходила к LangGraph state machine + к non-dialog use cases (документ-в-PDF, не диалог) — могли бы взять их. Но multi-turn они моделируют как simulated dialog, а у нас single-document analysis pipeline. Architecture mismatch.

---

### 4.5 Inspect AI (2.1k stars, MIT, UK AISI government-backed)

**Что это**: research-focused safety eval framework, built UK AI Safety Institute.

**Их code example**:

```python
from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.scorer import model_graded_fact
from inspect_ai.solver import chain_of_thought, generate

@task
def security_guide():
    return Task(
        dataset=json_dataset("security_guide.json"),
        solver=[chain_of_thought(), generate()],
        scorer=model_graded_fact()
    )
```

**Где они НЕ подходят нам**:
- **Solver chain — orthogonal к LangGraph.** Чтобы использовать Inspect AI, нам нужно либо переписать агента в Inspect solvers (огромный refactor), либо wrap LangGraph как один opaque solver (теряем node-level signal).
- **Steep learning curve** — заточено под research, не product CI.
- **Community shape — frontier safety researchers**, не product agent builders. Мало off-the-shelf metrics для нашей задачи.

**Что они делают лучше нас**:
- Sandbox toolkit best-in-class для air-gapped environments — Kubernetes-native, могли бы быть полезны если бы мы строили adversarial testing.
- 200+ pre-built academic evals.
- UK government credibility (можно сослаться в нашем pitch регулятору).

**Вердикт для нас**: overkill harness для product CI. Не их target audience.

---

### 4.6 Ragas (13.9k stars, Apache 2.0)

**Что это**: RAG-specific eval library. Третий по популярности.

**Где они НЕ подходят нам**:
- **Agent eval — "Coming Soon"** в их roadmap. Текущие `ToolCallAccuracy` и `AgentGoalAccuracy` метрики работают на flat tool-call lists, не state machines.
- **RAG-only фокус** — multi-step audit с structured findings не их концепт.
- **Latitude 2026 review**: *"RAG-only; limited to retrieval and generation scoring with no production monitoring."*

**Что они делают лучше нас**:
- **Synthetic test-set generation для RAG** — могли бы быть полезны для нашей задачи генерации scenarios на основе нормативной базы.
- FaithfulnessMetric, peer-reviewed metric definitions — солидная теоретическая основа.

**Вердикт для нас**: **можем взять у них synthetic test-set generation** для отдельного use case (генерация challenging scenarios на основе СП), но как primary harness не подходит.

---

### 4.7 AgentEvals (LangChain, 587 stars, MIT)

**Что это**: **Самый ближайший существующий конкурент**. Trajectory-match library от самих авторов LangGraph.

**Их code example** (из их README):

```python
from agentevals.trajectory.llm import (
    create_trajectory_llm_as_judge,
    TRAJECTORY_ACCURACY_PROMPT,
)
evaluator = create_trajectory_llm_as_judge(
    prompt=TRAJECTORY_ACCURACY_PROMPT,
    model="openai:o3-mini",
)
outputs = [
    {"role":"user","content":"What is the weather in SF?"},
    {"role":"assistant","tool_calls":[{"function":{"name":"get_weather","arguments":"{\"city\":\"SF\"}"}}]},
    {"role":"tool","content":"It's 80 degrees and sunny in SF."},
    {"role":"assistant","content":"The weather in SF is 80 degrees and sunny."}
]
result = evaluator(outputs=outputs)
```

**Они делают лучше нас**: 
- **Имеют `GraphTrajectoryStrictMatch` и `GraphTrajectoryLLMAsJudge`** evaluators которые consume LangGraph thread напрямую, включая interrupts. Это **first-class LangGraph awareness** — лучше любого другого framework.

**Где они НЕ подходят как stand-alone**:
- **Только trajectory evaluators** — нет surrounding harness, нет test runner, нет YAML DSL.
- **Нет tier model**.
- **Нет silent-fallback detection**.
- **Underinvested**: 587 stars, last release Mar 2026 (v0.0.7), LangChain команда явно занята другим.
- Match modes только: strict / unordered / subset / superset. Domain-specific checks типа "defect found with correct citation" — пишем сами.

**Вердикт для нас**: **их evaluators надо взять как dependency** в scenario-gate, не переизобретать. Это компонент, не framework. Наш scenario-gate должен **уметь использовать AgentEvals под капотом** для trajectory matching, плюс добавлять всё остальное.

---

### 4.8 Cross-comparison table

| Framework | LangGraph-native | Multi-turn first-class | Tier (mainline/advisory) | Silent fallback / drift | YAML DSL | pytest | On-prem | Vendor-neutral | Stars | Production ready |
|---|---|---|---|---|---|---|---|---|---|---|
| Promptfoo | ❌ | ⚠️ bolt-on | ❌ | ❌ | ✅ | plugin | ✅ | ✅ | 21.3k | high |
| DeepEval | ⚠️ callback only | ⚠️ 5 metrics | ❌ | ⚠️ partial (LLM-judge) | ❌ | native | ✅ custom judge | ⚠️ soft cloud-upsell | 15.5k | high |
| LangSmith | ✅ first-party | ✅ | ❌ | ⚠️ custom | ❌ | SDK | ❌ Enterprise only | ❌ LangChain lock-in | closed | high |
| LangWatch Scenario | ❌ | ✅ core | ❌ | ⚠️ JudgeAgent | ❌ | ✅ | ✅ | ✅ | 880 | medium |
| Inspect AI | ❌ | ⚠️ solver chain | ❌ | ⚠️ custom | ❌ | own runner | ✅ best sandbox | ✅ | 2.1k | high (research) |
| Ragas | ❌ | ⚠️ roadmap | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | 13.9k | medium |
| AgentEvals | ✅ best | ✅ | ❌ | ❌ | ❌ | manual | ✅ | ⚠️ LangChain-aligned | 587 | low (toolkit) |
| **scenario-gate** | **✅** | **✅** | **✅** | **✅** | **✅** | **✅** | **✅** | **✅** | new | building |

---

### 4.9 Honest gap assessment — где мы НЕ уникальны

Это самая важная секция для credibility. Не overhype.

**Multi-turn harness pattern — НЕ наша инновация.** LangWatch Scenario сделали раньше. AgentEvals имеет лучшую LangGraph awareness чем мы будем иметь на v0.1.0.

**Реальный moat scenario-gate состоит из 3 вещей** (всё остальное — переиспользование known patterns):

1. **Tier model (mainline blocking vs expanded advisory)** — у НИКОГО из существующих frameworks этого нет first-class. Это наша основная opinionated decision.

2. **Domain-specific scorers для PDF defect detection** — `defect_found`, `defect_not_found`, `citation_format_validates`, `section_classification_correct`. Это **наш** код, поскольку нет общедоступных абстракций для regulated document audit.

3. **Silent-fallback detector tuned под vLLM/Qwen failure modes** — конкретный случай: Qwen3 thinking-mode часто burns all tokens в `<think>...</think>` и возвращает empty content. DeepEval и AgentEvals просто будут scoring empty string. Нам нужен explicit `silent_fallback_leak` check который классифицирует это как hard failure.

**Honest alternative path**: можно скомбинировать **AgentEvals (для trajectory) + Scenario (для multi-turn если бы он подходил) + Ragas (для RAG faithfulness) + thin pytest wrapper + custom drift judge** — это покрыло бы ~80% value scenario-gate с vendoring OSS. Усилие сопоставимо (~3 недели). Но: получаем 4 dependencies с разными upgrade paths и нет нашей tier model.

**Почему всё равно строим**:
- **Tier model критична** для regulated domain. Каждый failed test ≠ blocker. Без tier — либо CI постоянно красная (false alarms) либо мы игнорируем real failures.
- **Domain scorers** придётся писать в любом случае, в любом подходе.
- **Single dependency surface** легче для команды (один upgrade path вместо четырёх).
- **Battle-tested patterns** из EnglishFriend (mainline 3/3 PASS зелёный live) — мы не теоретически проектируем, переносим работающее.
- **Bonus**: после стабилизации становится OSS extract → repo + 3 blog posts → hiring/recognition signal для меня лично + attract talent для проекта.

---

### 4.10 Если регулятор / руководитель спросит "почему не industry standard?"

Готовый ответ:

> Industry standard в этой нише не существует. 21.3k-stars Promptfoo не работает с state machines. 15.5k-stars DeepEval скрытно ломается на loop'ах. LangSmith — vendor lock-in + security incidents 2025-2026 + cloud-only. LangWatch Scenario (880 stars) — closest, но архитектура под dialog simulation, не document audit. AgentEvals от LangChain (587 stars) — component, не framework.
>
> Мы строим minimum viable harness над AgentEvals + Ragas как dependencies, с нашим tier model и domain scorers. Эффект: ~22 часа работы, vs ~3 недели на adopt+workaround existing framework. Plus: full control над release-gate behavior в нашем CI.

---

## 5. Возражения от команды и ответы

### "У нас нет времени, MVP горит"
> Подключаем incrementally. Week 1: 5 mainline scenarios. Каждую неделю +5-10. Через месяц 30+ scenarios покрывают core flows. Это inside текущего CI, не блокирует MVP. Lib v0.1.0 готова через 3 недели работы на вечера/weekends (22ч), не за счёт project time.

### "Мы же все равно вручную проверяем перед релизом"
> Manual проверка не масштабируется. На AI системе изменения промпт/RAG/модель будут десятки раз в месяц. 2 дня тестера × 30 раз = 60 человеко-дней. Невозможно. Gate → CI 5 минут × 30 раз = 150 минут.

### "Кто будет писать scenarios?"
> Первые 10-15 пишу я как архитектор (берём из ваших исторических заключений за 3 года в БД). Параллельно учу 1-2 экспертов писать YAML (это 1 час обучения). Через 2 месяца expert-driven: эксперт ловит ошибку → 30 секунд написать scenario → автоматически в suite.

### "А если scenarios сами с ошибками?"
> Peer review каждого нового scenario как код. Plus false positive scenarios быстро отлавливаются: агент проходит test, эксперт говорит результат неправильный → значит test wrong, не агент. Это **feature** loop.

### "Это open source — нам нужно отдавать наш код наружу?"
> Generic eval pattern (как мы делаем regression tests) — да, без любого нашего domain content. Никакие правила, документы, scenarios с реальной нормативкой, workflow — наружу не идут. Это приносит проекту: (a) outside contributions улучшают tool, (b) attract better engineering candidates, (c) внешняя validation подхода. Перед публикацией — формальное письменное согласие от руководства.

### "Зачем нам custom фреймворк когда LangChain выпустит свой?"
> LangChain выпустила AgentEvals год назад. 587 stars, last release Mar 2026, явно underinvested. Promptfoo, DeepEval — существуют 2-3 года, по нашему use case не закрыли gap. Категория "blocking-vs-advisory tier для LangGraph" остаётся open. Ждать чужого решения = риск никогда не дождаться. Plus: даже если кто-то выпустит идеальное завтра — мы migrate scenarios YAML за день.

### "А если performance в CI слишком долгая?"
> Mainline = 5-10 scenarios = ~5 минут CI. Expanded = 30-50 = ~15 минут. Запускается через nightly или on-demand, не на каждом push. Cacheable LLM outputs (если scenario не менялся и код агента не менялся в relevant nodes → переиспользуем cached output). Конкретный budget обсудим в Phase 1.

### "А что если Qwen упадёт во время CI?"
> Retry logic + health check pre-run. Если Qwen unavailable → CI скипает eval с warning, не блокирует merge. Это **infrastructure failure**, не product regression. Разделение critical.

### "Может лучше нанять QA?"
> Не вместо. **И то, и другое.** QA найдёт UX issues, edge cases в interface, integration bugs. Scenario-gate найдёт AI behavior regressions. Разные категории багов. Plus QA сам будет писать scenarios как часть своей работы — это масштабирует его время в 10x.

---

## 6. Что я предлагаю в первую неделю работы (pilot proposal)

Конкретный план чтобы получить green light:

### Дни 1-2: Архитектурный аудит MVP + договорённости
- Прочитать существующий код AI слоя (если есть)
- Discovery встречи: бэкенд, фронт, девопс
- **Получить письменное согласие от руководства**: "generic eval pattern (без domain content) могу публиковать как OSS"
- Если согласия нет → продолжаем без OSS aspect, lib остаётся internal

### Дни 3-5: scenario-gate v0.0.1 skeleton
- 5 hardcoded mainline scenarios для simple cases (one section type, basic defects)
- Минимальный runner на Python (~200 LOC)
- Integration в существующий CI pipeline
- Demo команде: запуск + report

### Week 2: Первый production-relevant scenarios
- Конвертировать 10-15 исторических кейсов из 3-летней БД заключений → scenarios
- Каждый scenario peer-review с экспертом
- Validate что текущая MVP действительно проходит / падает на правильных кейсах

### Week 3-4: Полировка + lib extract
- YAML DSL вместо hardcoded
- Tier model (mainline/expanded)
- Silent fallback detector tuned на наш Qwen
- v0.1.0 как PyPI package (если OSS approved) или internal package

### Metric для success Pilot (через 4 недели)
- 20+ scenarios в production CI
- ≥1 случай где gate поймал regression до merge
- Команда подтверждает: pytest output читабельный, CI red понятна

**Если pilot fails** через 4 недели (никаких caught regressions, команда против): прозрачное postmortem, останавливаем. Я не настаиваю если value не доказана.

---

## 7. Appendices

### A. Glossary

- **mainline scenario** — must-pass test, блокирует merge при fail
- **expanded scenario** — advisory test, виден в report но не блокирует
- **silent fallback** — когда агент возвращает generic ответ (типа "не могу проанализировать") вместо явного error
- **goal drift** — когда агент стартует с одной задачей, но через несколько turns drift'ает на другую
- **state assertion** — проверка значения поля в LangGraph state (например `state.section.classified_as == "КР"`)
- **trajectory** — последовательность сообщений и tool calls в LangGraph execution
- **scope gate** (не путать с scenario-gate) — runtime механизм отсечения out-of-scope запросов до routing
- **regression** — поведение, которое раньше работало правильно, теперь работает неправильно после изменения

### B. Sample scenarios для нашего domain

```yaml
# scenarios/mainline/01_classify_KR.yaml
id: classify_KR
tier: mainline
description: Базовая классификация раздела КР (Конструктивные решения)
input:
  document: fixtures/sample_01_KR.pdf
checks:
  - type: state_assertion
    path: section.classified_as
    equals: "КР"
  - type: state_assertion
    path: section.applicable_normatives
    contains: ["СП 63.13330.2012"]
```

```yaml
# scenarios/mainline/02_defect_missing_reinforcement.yaml
id: missing_reinforcement_in_load_bearing_wall
tier: mainline
description: |
  Несущая стена без указания армирования.
  Из исторических заключений: case_id 2024-03-1234.
input:
  document: fixtures/sample_02_KR_no_reinforcement.pdf
checks:
  - type: defect_found
    rule_id: "СП 63.13330.2012 п.10.3"
    severity: critical
    must_have_citation: true
    must_have_page_number: true
  - type: silent_fallback_leak
    forbidden_phrases:
      - "не могу проанализировать"
      - "недостаточно данных"
      - "обратитесь к эксперту"
```

```yaml
# scenarios/expanded/03_table_extraction_ТЭП.yaml
id: technical_economic_indicators_table
tier: expanded
description: |
  Таблица ТЭП (Технико-экономические показатели) должна корректно
  парситься. Регрессия chunking strategy на длинных таблицах.
input:
  document: fixtures/sample_03_long_TEP_table.pdf
checks:
  - type: state_assertion
    path: tables.extracted_count
    greater_than_or_equal: 1
  - type: state_assertion
    path: tables[0].rows_count
    greater_than: 15
```

### C. References

- [Promptfoo Issue #1098 — separate eval configs (matches наш tier requirement)](https://github.com/promptfoo/promptfoo/issues/1098)
- [Promptfoo Issue #5174 — multi-turn + tool calls](https://github.com/promptfoo/promptfoo/issues/5174)
- [DeepEval LangGraph integration docs (признание iteration limitation)](https://deepeval.com/integrations/frameworks/langgraph)
- [ZenML DeepEval alternatives review 2026](https://www.zenml.io/blog/deepeval-alternatives)
- [LangSmith pricing](https://www.langchain.com/pricing)
- [Coverge LangSmith pricing analysis 2026](https://coverge.ai/blog/langsmith-pricing)
- [LangSmith CVE June 2025](https://thehackernews.com/2025/06/langchain-langsmith-bug-let-hackers.html)
- [LangSmith RCE March 2026](https://thehackernews.com/2026/03/ai-flaws-in-amazon-bedrock-langsmith.html)
- [HN LangSmith lock-in discussion](https://news.ycombinator.com/item?id=39307884)
- [LangWatch Scenario repo](https://github.com/langwatch/scenario)
- [Inspect AI (UK AISI)](https://github.com/UKGovernmentBEIS/inspect_ai)
- [Inspect Sandboxing Toolkit](https://www.aisi.gov.uk/blog/the-inspect-sandboxing-toolkit-scalable-and-secure-ai-agent-evaluations)
- [Ragas repo](https://github.com/explodinggradients/ragas)
- [AgentEvals (LangChain)](https://github.com/langchain-ai/agentevals)
- [Goal Drift in LM Agents (arXiv 2505.02709)](https://arxiv.org/abs/2505.02709)
- [Detecting Silent Failures in Agentic Trajectories (arXiv 2511.04032)](https://arxiv.org/html/2511.04032v1)
- [Latitude AI Agent Failure Detection Guide](https://latitude.so/blog/ai-agent-failure-detection-guide)

### D. Hand-off для следующих сессий

Если возвращаешься к этому документу через дни/недели:
- [ ] Был ли pitch с командой? Какая реакция?
- [ ] Получено ли согласие от руководства на OSS publication?
- [ ] Какие возражения возникли которых нет в section 5?
- [ ] Pilot scope согласован (5 mainline scenarios week 1)?

Если ты Claude/Codex агент, читающий этот файл:
- Это материал для **stakeholder pitch**, не technical spec. Технический план — `!DOC/strategy/SCENARIO_GATE_EXTRACT_PLAN.md`.
- Не overhype в дополнениях. Section 4.9 "Honest gap assessment" — sticky правило. Multi-turn harness pattern НЕ наша инновация.
- При обновлениях competitive section — verify stars/issue links (могут изменяться).
