# Live Tester Findings

Документ фиксирует баги и product-проблемы, обнаруженные через синтетический eval (`--scenario-set live_tester`).  
Каждый баг включает сценарий-репродьюсер, фактическое vs ожидаемое поведение, и корневую причину.

**Принцип:** этот файл только собирает баги. Фиксы назначаются отдельно.

---

## БАГ-001 — LLM-экстракция создаёт неканонические context-имена

**Обнаружен:** 2026-04-22, сценарий `vague_progressive_interview`  
**Severity:** Medium  
**Компонент:** `app/agent/nodes_v2/onboarding.py` → LLM goal extraction → `goal_brief.main_contexts`

### Описание

Когда пользователь даёт размытый/прогрессивный ввод, LLM-экстракция цели может записать в `goal_brief.main_contexts[0]` произвольную строку вместо канонического значения из контракта.

**Воспроизводящий сценарий:**
```
Turn 1: "I want improve my English for get better job."
Turn 2: "I am ML engineer and want work in international company abroad."
Turn 3: "I need practice interview in English. Want pass interview for ML engineer position."
```

**Ожидаемое:** `main_contexts[0] == "interviews"`  
**Фактическое:** `main_contexts[0] == "job interview"`

### Симптом

Routing в `hr_intro` + `foundation_speaking_drill` сработал корректно — система правильно направила в первую миссию. Но `primary_context` в snapshot содержит `"job interview"` вместо `"interviews"`. Любой downstream-код, делающий `== "interviews"`, может сломаться.

### Корневая причина (гипотеза)

`goal_brief_contract.py` определяет канонические значения, но LLM-экстракция в `onboarding.py` не валидирует/нормализует возвращаемый `main_contexts` к допустимому набору. LLM генерирует свободный текст.

### Где смотреть

- `app/agent/nodes_v2/onboarding.py` — LLM extraction + goal brief merge
- `app/services/goal_brief_contract.py` — canonical context names
- Нужна постобработка: нормализовать `main_contexts` к enum после LLM-ответа

---

## БАГ-002 — Correction lane не перезаписывает routing после draft=interviews

**Обнаружен:** 2026-04-22, сценарий `explicit_correction_to_project`  
**Severity:** High  
**Компонент:** `app/agent/nodes_v2/onboarding.py` → `_infer_goal_brief_correction_from_message` → sticky routing

### Описание

Пользователь явно пишет "not interview, I need project walkthrough". Correction lane должен обновить `main_contexts` на `project_walkthrough`. Но routing остаётся на `interviews`.

**Воспроизводящий сценарий:**
```
Turn 1: "I want practice English interview. I ML engineer, need interview preparation for job abroad."
         → система устанавливает goal_brief.status=draft, main_contexts=["interviews"]
Turn 2: "Actually no, not interview. More important is explain my ML project. I need project walkthrough practice."
         → явный "not interview" + "project walkthrough" → correction lane должен сработать
Turn 3: "Yes I build recommendation system. Want explain architecture and design decision in English."
```

**Ожидаемое:** `primary_context == "project_walkthrough"`, `recommended_track == "project_walkthrough"`  
**Фактическое:** `primary_context == "interviews"`, `recommended_track == "hr_intro"`

### Симптом

10 проверок: 7/10 pass, score=70%. Routing-ready goal выставлен после turn 1. В turn 2 correction не меняет `main_contexts[0]`.

### Корневая причина (гипотеза)

Возможные варианты:
1. `_infer_goal_brief_correction_from_message` не обрабатывает шаблон "not interview" когда он идёт вместе с другим контекстом в одном сообщении
2. Sticky routing (инвариант: после `status=draft` primary_context защищён) блокирует correction lane
3. Correction обновляет `main_contexts` но `goal_routing.py` читает из sticky state и не перечитывает обновлённый brief

### Где смотреть

- `app/agent/nodes_v2/onboarding.py` — `_infer_goal_brief_correction_from_message()`, `_merge_goal_brief()`
- `app/services/routing/goal_routing.py` — sticky primary logic (строки ~263-288)
- `app/services/goal_brief_contract.py` — status transitions при correction

### Критичность для продукта

Пользователи, которые сначала упомянули interview, а потом исправились на project/workplace, получат неправильную первую миссию. Это прямой UX-баг.

---

## Наблюдение-001 — "model result" перехватывается как project-сигнал

**Обнаружен:** 2026-04-22, первая версия `broken_english_workplace`  
**Severity:** Low  
**Компонент:** `app/agent/nodes_v2/onboarding.py` — сигнальные паттерны

### Описание

Фраза "explain model result to manager" вызвала routing в `project_walkthrough` вместо `workplace_communication`. Паттерн `"model"` или `"model result"` засчитывается как project-сигнал, перевешивая `"manager"` как workplace-сигнал.

**Вход:** `"I need speak better English at work. I explain model result to manager, they not technical person."`  
**Ожидаемое:** `workplace_communication`  
**Фактическое:** `project_walkthrough`

### Контекст

После замены "model result" на "to manager in team meeting" routing исправился (PASS 100%). Значит сигнальные паттерны не учитывают контекст ("model" в workplace-фразе ≠ project).

### Где смотреть

- `app/agent/nodes_v2/onboarding.py` — `PROJECT_SIGNAL_PATTERNS` vs `WORKPLACE_SIGNAL_PATTERNS`
- Возможно нужен контекстный весовой коэффициент: "model + manager" → workplace, "model + architecture/deploy/pipeline" → project

---

## БАГ-003 — Нестабильность в batch-прогоне: сценарии 6+ падают с needs_goal

**Обнаружен:** 2026-04-22, сценарии `data_engineer_interview` (позиция 6) и `backend_engineer_interview` (позиция 8) при `--scenario-set live_tester`  
**Severity:** Medium  
**Компонент:** Groq API / timing / onboarding completion под нагрузкой

### Описание

Сценарии, которые проходят на 100% при одиночном запуске, падают при последовательном прогоне 10 сценариев подряд. Начиная с 6-го сценария.

**Симптом при падении:**
```
setup_state: expected=ready_for_program, actual=needs_goal
assessment_source: expected=embedded_first_mission, actual=None
latest_evidence_task_type: expected=foundation_speaking_drill, actual=free_conversation
```

`setup_state=needs_goal` означает, что онбординг не завершился — goal_brief не достиг routing-ready. Сессия завершилась как `free_conversation`, не как `foundation_speaking_drill`.

**Воспроизводится:** только при batch (10 сценариев последовательно), не при одиночном запуске.

### Корневая причина (гипотеза)

1. **Groq rate limiting** — после 5-6 последовательных сессий с LLM-вызовами Groq начинает throttle, response time растёт, onboarding LLM-вызов не укладывается в `turn_timeout=25s`
2. **Session state accumulation** — последовательное создание пользователей и сессий, возможно накапливается нагрузка на PostgreSQL connection pool
3. **Timing race** — предыдущая сессия ещё финализирует persistence когда следующая уже стартует

### Доказательство изоляции

| Запуск | `data_engineer_interview` | `backend_engineer_interview` |
|--------|--------------------------|------------------------------|
| Одиночный | PASS 100% | PASS 100% |
| Batch (позиция 6/8 из 10) | FAIL 50% | FAIL 50% |

### Где смотреть

- Groq API rate limits (RPM/RPD для `llama-3.3-70b-versatile`)
- `app/agent/nodes_v2/onboarding.py` — timeout handling при медленном LLM
- `app/core/database.py` — connection pool настройки под нагрузкой
- Возможное решение: добавить `--delay-between-scenarios N` параметр в eval-скрипт

---

## БАГ-004 — Отрицание контекста не убирает его из сигналов: "don't want interviews" → interview signal

**Обнаружен:** 2026-04-22, сценарий `negative_context_no_interview`  
**Severity:** High  
**Компонент:** `app/agent/nodes_v2/onboarding.py` — сигнальные паттерны, negation detection

### Описание

Когда пользователь явно говорит "I don't want to practice interviews", слово `"interviews"` всё равно засчитывается как положительный interview-сигнал. Система одновременно видит workplace-сигналы из "team meetings" и interview-сигнал из слова "interviews" в отрицательной фразе. Результат: конфликт, `setup_state=needs_goal`, цикл.

**Воспроизводящий сценарий:**
```
Turn 1: "I don't want to practice interviews. I need help with team meetings and manager communication."
Turn 2: "My goal is workplace English, not interview preparation."
Turn 3: "I need explain better to stakeholder and colleague at work."
```

**Ожидаемое:** `primary_context=workplace_communication`, `setup_state=ready_for_program`  
**Фактическое:** `primary_context=None`, `setup_state=needs_goal`, `recommended_track=hr_intro`

**Ответ ассистента (показательно):**
```
"I already heard a direction around workplace communication, interviews. 
 Which role is closest right now: ML engineer, data scientist, or applied scientist?"
```
Система видит оба контекста (workplace + interviews) одновременно и не может выбрать.

### Корневая причина

Сигнальные паттерны делают поиск по ключевым словам без учёта отрицания (`don't want`, `not`, `no`). Фраза "don't want to practice **interviews**" содержит `interviews` → засчитывается как interview-сигнал, несмотря на отрицание.

### Где смотреть

- `app/agent/nodes_v2/onboarding.py` — `INTERVIEW_SIGNAL_PATTERNS`, функция подсчёта сигналов
- Нужна предобработка: если перед сигнальным словом идёт отрицание (don't, not, no, never, without), исключать из positive signals
- Или добавить отрицательные паттерны в `NEGATIVE_SIGNALS` и вычитать из счёта

---

## БАГ-005 — Односложные ответы не набирают threshold: routing застревает в needs_goal

**Обнаружен:** 2026-04-22, сценарий `one_word_answers_interview`  
**Severity:** Medium  
**Компонент:** `app/agent/nodes_v2/onboarding.py` — `signal_count` threshold, low-signal detection

### Описание

Пользователь даёт 1-3 слова на каждый turn с явными сигналами: "interviews", "ML engineer", "abroad, FAANG interview". Каждый turn содержит interview-сигналы, но система не набирает `signal_count >= 2` для перехода в routing-ready.

**Воспроизводящий сценарий:**
```
Turn 1: "interviews"
Turn 2: "ML engineer"
Turn 3: "abroad, FAANG interview"
```

**Ожидаемое:** `primary_context=interviews`, `setup_state=ready_for_program`  
**Фактическое:** `primary_context=None`, `setup_state=needs_goal`, `recommended_track=hr_intro` (частичное определение)

**Ответ ассистента:**
```
Turn 1: "Let's keep going. Tell me in one sentence what you want to practice..."
Turn 2: "Let's keep going. Tell me in one sentence..." (повтор)
Turn 3: "I already heard a direction around interviews. Which role is closest right now..."
```

Система видит direction, но не может перейти в routing-ready — `primary_context` не сохраняется в `goal_brief.main_contexts`.

### Корневая причина

Однословные ответы не удовлетворяют минимальному порогу контента (`_is_low_signal_assessment_answer`: < 2 content tokens). Сигналы детектируются (track определяется), но goal_brief не считается routing-ready без полного набора полей (primary_goal, target_role, domain, main_contexts).

### Где смотреть

- `app/agent/nodes_v2/onboarding.py` — `_is_low_signal_assessment_answer`, goal_brief merge
- `app/services/goal_brief_contract.py` — routing-ready требования
- Вопрос: если из 3 turn суммарно набрано достаточно сигналов, должен ли system делать вывод о routing-readiness даже без полных полей?

### Критичность для продукта

Реальные пользователи с broken English часто дают короткие ответы. Если система застревает в цикле после трёх попыток — это плохой UX. Нужен fallback: after N low-signal turns, force-route на самый сильный detected context.

---

## БАГ-006 — "client meeting" routing в interviews вместо workplace

**Обнаружен:** 2026-04-22, сценарий `freelancer_client_workplace`  
**Severity:** Medium  
**Компонент:** `app/agent/nodes_v2/onboarding.py` — `WORKPLACE_SIGNAL_PATTERNS` vs `INTERVIEW_SIGNAL_PATTERNS`

### Описание

ML-фрилансер говорит о встречах с клиентами ("client meeting", "client presentation"). Система роутит в `interviews` вместо `workplace_communication`.

**Воспроизводящий сценарий:**
```
Turn 1: "I am ML freelancer. I need explain my work to client in English better."
Turn 2: "I have client meeting in English, need explain project result and recommendation to client."
Turn 3: "My goal improve English for client presentation and meeting."
```

**Ожидаемое:** `primary_context=workplace_communication`, `recommended_track=workplace_communication`  
**Фактическое:** `primary_context=interviews`, `recommended_track=hr_intro`

### Корневая причина (гипотеза)

Слово `"client"` или комбинация `"client meeting"` / `"client presentation"` не входит в `WORKPLACE_SIGNAL_PATTERNS`, но может попадать в interview-контекст через паттерн типа "meeting with someone" или через LLM-интерпретацию "client" как "potential employer". 

Freelancer-контекст полностью отсутствует в сигнальных паттернах: нет слов `"client"`, `"freelance"`, `"consulting"`.

### Где смотреть

- `app/agent/nodes_v2/onboarding.py` — `WORKPLACE_SIGNAL_PATTERNS`
- Добавить: `"client meeting"`, `"client presentation"`, `"freelance"`, `"consulting"`, `"explain to client"` как workplace-сигналы

---

## БАГ-007 — Функциональные роли ("team lead") не заполняют target_role → goal не routing-ready

**Обнаружен:** 2026-04-22, сценарий `team_lead_workplace`  
**Severity:** High  
**Компонент:** `app/agent/nodes_v2/onboarding.py` — role extraction, goal_brief target_role

### Описание

Пользователь описывает себя через функцию ("team lead", "leading team"), а не через каноническое название роли ("ML engineer", "data scientist"). Система ВИДИТ workplace-направление (ассистент говорит "I already heard a direction around workplace communication"), но `goal_brief` не достигает routing-ready: `primary_context=None`, `setup_state=needs_goal`.

**Воспроизводящий сценарий:**
```
Turn 1: "I become team lead recently. I need improve English for leading team meeting and technical discussion."
Turn 2: "I need explain technical decision to non-technical manager and business stakeholder."
Turn 3: "My goal is better workplace English for team lead communication and presentation."
```

**Фактическое поведение ассистента:**
```
Turn 1: "Let's keep going. Tell me in one sentence what you want to practice..."
Turn 2: "Let's keep going. Tell me in one sentence..." (повтор)
Turn 3: "I already heard a direction around workplace communication. Which role is closest right now: ML engineer, data scientist..."
```

**Фактическое:** `primary_context=None`, `setup_state=needs_goal`, `recommended_track=hr_intro` (неверный)  
**Ожидаемое:** `primary_context=workplace_communication`, `setup_state=ready_for_program`

### Корневая причина

`goal_brief` требует `target_role` для routing-ready статуса. Роль "team lead" не распознаётся как каноническая (`ML engineer`, `data scientist`, `applied scientist`, `backend engineer` и т.п.). Без `target_role` — goal неполный даже с явными workplace-сигналами.

Также интересно: `recommended_track=hr_intro` — система видит "technical discussion" и предлагает interview track, хотя сама же сказала "I heard workplace communication".

### Где смотреть

- `app/agent/nodes_v2/onboarding.py` — роли, которые распознаются как canonical target_role
- `app/services/routing/goal_routing.py` — как handling `target_role=None` при известном `main_contexts`
- Возможное решение: если `main_contexts` заполнен, routing-ready не должен блокироваться отсутствием `target_role`

---

## БАГ-008 — No-context пользователь зависает в бесконечном цикле "Tell me in one sentence"

**Обнаружен:** 2026-04-22, сценарии `grammar_only_no_context` и `anxiety_vague_no_context`  
**Severity:** High (UX)  
**Компонент:** `app/agent/nodes_v2/onboarding.py` — low-signal loop, forced routing fallback

### Описание

Пользователь, который не называет профессию/контекст (говорит только о грамматике или выражает тревогу), получает один и тот же вопрос три раза подряд без прогресса. Система не переходит в первую миссию даже после N итераций.

**Воспроизводящий сценарий A (grammar):**
```
Turn 1: "I need improve my grammar in English. I make many mistakes."
Turn 2: "I have problem with articles and tenses. My English not good."
Turn 3: "I want better vocabulary for professional English communication."
```

**Воспроизводящий сценарий B (anxiety):**
```
Turn 1: "My English is very bad. I cannot speak well in English at all."
Turn 2: "I am afraid to speak English. I make many mistake."
Turn 3: "I need improve English but don't know where to start."
```

**Поведение в обоих случаях:**
```
Turn 1: "Let's keep going. Tell me in one sentence..."
Turn 2: "Let's keep going. Tell me in one sentence..." (идентичный повтор)
Turn 3: "Let's keep going. Tell me in one sentence..." (идентичный повтор)
```

**Фактическое:** `primary_context=None`, `setup_state=needs_goal`, task_type=`free_conversation`  
**Ожидаемое:** после 3 low-signal turns — force-route в default (`interviews`) или вывести уточняющий choice

### Корневая причина

Система детектирует low-signal ответы, просит переформулировать, но не имеет exit-condition после N попыток. Нет forced routing после exceeded threshold. Пользователь застревает навсегда — или до таймаута сессии.

### Где смотреть

- `app/agent/nodes_v2/onboarding.py` — `low_signal_streak` counter, что происходит при streak >= 3
- Текущее поведение: "suggest voice-to-text fallback" при streak >= 3, но это не force-routes
- Нужен: `if low_signal_streak >= N: force_route_to_default_context()`

### Критичность

Это самый частый реальный сценарий для целевой аудитории: русскоязычный пользователь с плохим English заходит первый раз и пишет "I want speak better English". Система должна взять его в работу, а не крутить в цикле.

---

## БАГ-009 — Emoji в тексте ломает сигнальные паттерны → needs_goal

**Обнаружен:** 2026-04-22, сценарий `emoji_in_message_workplace`  
**Severity:** Medium  
**Компонент:** `app/agent/nodes_v2/onboarding.py` — regex/string signal matching

### Описание

Сообщения с emoji ("work 💼", "manager 👔", "stakeholder 📊") не дают routing-ready. `primary_context=None`, `setup_state=needs_goal`, хотя text-сигналы workplace явны.

**Воспроизводящий сценарий:**
```
"I need better English for work 💼. I explain to manager 👔 in team meetings."
"My goal is workplace communication 📊 with stakeholder and non-technical colleague."
```

**Фактическое:** `primary_context=None`, `setup_state=needs_goal`

### Корневая причина (гипотеза)

Emoji-символы между словами нарушают word-boundary matching в regex-паттернах. Например, `"manager 👔 in"` — паттерн `\bmanager\b` может не матчить если между словами нестандартные символы. Или токенизация разбивает "work 💼" на 3 токена, снижая content_ratio ниже порога.

### Где смотреть

- `app/agent/nodes_v2/onboarding.py` — предобработка текста перед signal matching
- Добавить: strip/normalize unicode non-word characters перед pattern matching

---

## БАГ-010 — Tiebreaker при равных сигналах выбирает project, а не interviews

**Обнаружен:** 2026-04-22, сценарий `three_contexts_equal_signals`  
**Severity:** Medium  
**Компонент:** `app/services/routing/goal_routing.py` — `_pick_primary_from_scores`, canonical order

### Описание

Когда пользователь упоминает все три контекста в равной мере, tiebreaker должен брать первый по canonical order (`interviews`). Фактически система выбирает `project_walkthrough`.

**Воспроизводящий сценарий:**
```
"I need interview practice, improve work communication, and explain my ML projects better."
"I have interviews next month, team meetings every week, and project presentations too."
"All three are important: interview preparation, workplace English, project walkthrough."
```

**Ожидаемое:** `primary_context=interviews` (первый в canonical order при ничьей)  
**Фактическое:** `primary_context=project_walkthrough`

### Корневая причина (гипотеза)

Либо в `three_contexts_equal_signals` сигналы не равны по счёту (последнее сообщение содержит "project walkthrough" — возможно project получил score+1), либо canonical order тай-брейкер не работает как задокументировано. Возможно `_pick_primary_from_scores` сортирует по имени (lexicographic), а не по canonical priority list.

### Где смотреть

- `app/services/routing/goal_routing.py` — `_pick_primary_from_scores()`, tie-breaking logic
- Проверить: canonical порядок явно задан как список приоритетов, или это артефакт dict-порядка?

---

## БАГ-011 — Correction lane не работает ни в одном направлении (project→workplace тоже не меняется)

**Обнаружен:** 2026-04-22, сценарий `project_correction_to_workplace`  
**Severity:** High  
**Компонент:** `app/agent/nodes_v2/onboarding.py` — `_infer_goal_brief_correction_from_message`

### Описание

БАГ-002 (interview→project не меняется) подтверждён в обратную сторону: project→workplace тоже не меняется. Correction lane сломан во всех направлениях.

**Воспроизводящий сценарий:**
```
Turn 1: "I need explain my ML project better in English."     → draft=project_walkthrough
Turn 2: "Actually more important is my daily work communication with manager and team at office."
Turn 3: "Yes workplace English is my real goal, not project explanation."
```

**Фактическое:** `primary_context=project_walkthrough` (не изменился)

### Наблюдение

Два сценария — `explicit_correction_to_project` (interview→project) и `project_correction_to_workplace` (project→workplace) — оба FAIL 70%. Correction lane не работает ни в одном направлении после того, как goal_brief получил статус draft.

---

## БАГ-012 — DevOps/SRE роль не распознаётся как valid domain → needs_goal

**Обнаружен:** 2026-04-22, сценарий `devops_sre_interview`  
**Severity:** Medium  
**Компонент:** `app/agent/nodes_v2/onboarding.py` — domain/role recognition

### Описание

DevOps/SRE инженер с явным intent ("prepare for SRE interview", "FAANG company", "job abroad") не получает routing-ready. Аналогично БАГ-007 (team_lead): роль не в canonical set.

**Воспроизводящий сценарий:**
```
"I am DevOps engineer. I want prepare for senior SRE interview at international company."
"I work with Kubernetes, CI/CD, cloud infrastructure AWS. Need interview practice."
"I need pass DevOps SRE interview for job abroad at big tech company."
```

**Фактическое:** `primary_context=None`, `setup_state=needs_goal`, `recommended_track=hr_intro` (частичное)

### Паттерн

Роли без ML/AI маркера ("ML engineer", "data scientist") не проходят domain/role extraction даже при наличии interview-сигналов. Проблема повторяется для: DevOps, SRE, team lead, backend engineer (частично).

---

## БАГ-013 — STT-шум (фонетические опечатки) полностью ломает routing

**Обнаружен:** 2026-04-22, сценарий `stt_noise_interview`  
**Severity:** High (для voice-first продукта)  
**Компонент:** `app/agent/nodes_v2/onboarding.py` — сигнальные паттерны, STT robustness

### Описание

Фонетически написанные слова ("intarview", "ML injineer", "abrod", "internashenal compny") дают `needs_goal` — сигналы не матчат ни один паттерн.

**Воспроизводящий сценарий:**
```
"I wont intarview practis for ML injineer jab abrod."
"I need prepear for teknikal intarview at internashenal compny."
"Intarview preparashon iz my goal for ML injineer pozishon."
```

**Фактическое:** `primary_context=None`, `setup_state=needs_goal`

### Критичность

Это критично для **voice-first** продукта. Реальный Vosk-транскрипт ломаного English регулярно даёт такие искажения. Если routing полностью зависит от точного keyword match — весь voice path ненадёжен для целевой аудитории (русскоязычные с акцентом).

### Где смотреть

- `app/agent/nodes_v2/onboarding.py` — signal patterns: добавить fuzzy variants ключевых слов
- Или: LLM-нормализация транскрипта перед signal extraction
- Или: использовать LLM для intent classification вместо regex (но это scope expansion)
- Ключевые слова с частыми искажениями: interview→intarview/intrview, engineer→injineer/enginer, abroad→abrod/abrod

---

## Наблюдение-002 — off_topic_then_interview: ассистент повторяет начальный вопрос

**Обнаружен:** 2026-04-22, сценарий `off_topic_then_interview`  
**Severity:** Low  
**Компонент:** onboarding flow — обработка off-topic первого сообщения

### Описание

Когда пользователь пишет off-topic в первом turn ("What can I practice here?"), ассистент правильно не ломается, но в batch-запуске на Turn 1 вернул повторный начальный вопрос:

```
Turn 1 assistant: "Let's keep going. Tell me in one sentence what you want to practice in English — interviews, team meetings, or project walkthroughs?"
```

Это нормальное fallback-поведение. PASS 100%, не блокирующее.

---

## Шаблон для новых находок

```markdown
## БАГ-NNN — Краткое название

**Обнаружен:** YYYY-MM-DD, сценарий `slug`
**Severity:** Low / Medium / High / Critical
**Компонент:** путь к файлу → функция

### Описание
...

### Воспроизводящий сценарий
```
Turn 1: "..."
Turn N: "..."
```

### Ожидаемое vs Фактическое
...

### Корневая причина (гипотеза)
...

### Где смотреть
- файл:строка
```

---

*Последнее обновление: 2026-04-22 | Источник: синтетический eval `--scenario-set live_tester`*
