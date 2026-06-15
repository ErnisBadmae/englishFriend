> Active planning note, 2026-05-20: for current Codex/Claude Code work, use `!DOC/strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md` plus `!DOC/operations/CURRENT_PRODUCT_STATE.md` as the canonical planning and task-tracking source. This file is historical sprint material unless a newer user instruction says otherwise.

Discovery Phase 0 — Sprint Materials & Architectural Vision

▎ Активный артефакт спринта на discovery-first cycle. Создан после критического разбора плана Codex v2 + утверждения hybrid пути (calls + личные DMs warm контактам).

---

Контекст и архитектурное видение

Конечная цель текущего цикла (2.5–3 недели)

1 retained user который:

- Прошёл session 1
- Вернулся на session 2 в течение 7 дней
- Дошёл до evidence persistence stage в session 2
- Явно сказал "хочу session 3 в календарь" ИЛИ "заплачу $20 за сессию"

Один такой человек = первый внешний proof point. Без него все runtime cleanups, plans и архитектурные решения — техническая работа в вакууме.

Зачем именно discovery, а не сразу build

- 5 calls — самый дешёвый и самый информативный signal в pre-PMF
- Ad campaign / landing page → даёт демографию, не pain stories
- "Show MVP, don't ask" → работает после PMF, до PMF риск построить не то
- Discovery даёт word-for-word язык pain (это будущий messaging) + competitor intel + pricing reality

Wedge (locked)

- In scope: ML/SWE interview prep на английском
- Out: workplace_communication, project_walkthrough как standalone wedge
- project_walkthrough допустим только как interview-supporting артефакт

Modality (locked)

- Text-first baseline — composer как default STT во frontend
- Voice opt-in — остаётся как differentiator, но не блокирует retention validation
- Без auto-TTS на typed mainline (cost reasoning)

Sample policy

- 3 warm + 2 cold (минимум 1 cold обязателен)
- Warm-only return = soft signal, НЕ считается success
- Если cold user не вернулся — cycle не считается validation win

---

Текущее состояние продукта (по итогам сегодняшней работы)

Build progress (выполнено Codex)

- ✅ Voice runtime collapse — app/api/voice.py:800 делегирует в controller
- ✅ Session ordering fix — session_finishing → persist → session_complete
- ✅ Text-first baseline — composer как default STT в frontend/src/App.tsx:46
- ✅ Replay tool — scripts/replay_session.py
- ✅ 15 тестов проходят (tests/test_voice_runtime.py, tests/test_replay_session_script.py)
- ✅ Документация зафиксирована как канон цикла

Pending blockers

- ⏳ memory_kind enum migration не применена к реальной БД (миграция написана: db/changelog/007-memory-kind-alignment.xml). Apply + verify = 15 мин. Не блокирует discovery, блокирует Phase 1 verification.

Repo артефакты (актуальная operational truth)

- !DOC/strategy/ROADMAP.md — активный roadmap
- !DOC/operations/CURRENT_PRODUCT_STATE.md — текущее product state
- !DOC/architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md — архитектурные решения цикла
- !DOC/operations/VOICE_OBSERVABILITY_RUNBOOK.md — runbook для observability/replay
- !DOC/operations/DISCOVERY_PHASE0_RUNBOOK.md — основной discovery runbook
- !DOC/operations/DISCOVERY_TARGET_SHEET_TEMPLATE.csv — шаблон таблицы кандидатов
- !DOC/operations/DISCOVERY_OUTREACH_SCRIPTS.md — outreach пакет
- !DOC/operations/DISCOVERY_CALL_NOTES_TEMPLATE.md — шаблон заметок/ридаута
- !DOC/archive/ROADMAP_2026-05-05_pre_founder_sprint.md — архив старого плана

---

Outreach: warm contacts (личные DMs)

Сообщение для warm DMs (Telegram/WhatsApp/LinkedIn)

Привет! Я строю инструмент для подготовки ML/SWE инженеров
к англоязычным интервью. Хочу понять как ты сейчас
готовишься к ним — есть 15 минут на этой неделе на
короткий разговор?

Не продаю и ничего не показываю — только слушаю что
больно и что не работает в текущей подготовке. Твой
опыт мне очень поможет.

Когда удобно?

Что НЕ писать

- ❌ Описание продукта ("я делаю voice coach с adaptive evidence loop...")
- ❌ Приглашение попробовать ("хочешь бесплатный trial?")
- ❌ Pitch ("это решит твою проблему с...")
- ❌ "Just 5 minutes" — будет 15, не врите
- ❌ Эмодзи 🚀 💪 ✨

Цель outreach

К концу дня 2: 8 warm DMs отправлено → ожидаемая конверсия 50–60% → 4–5 принятых.

---

Discovery call structure (15 минут, на русском)

Главные правила (это критично)

1.  НЕ показывайте продукт. Никаких скриншотов, демо, описаний.
2.  НЕ продавайте. Не предлагайте trial, не давайте ссылок.
3.  Говорите < 20% времени. Слушаете остальные 80%.
4.  Записывайте дословно. Используйте точные слова собеседника, не свои перефразирования.
5.  Спрашивайте "почему?" "расскажи подробнее" "как именно?". Каждый ответ — дверь к следующему вопросу.
6.  15 минут максимум. Если затягивается — останавливайте.

Основные вопросы (4 фиксированных)

1.  Открывающий — про процесс

▎ Расскажи как ты сейчас готовишься к интервью на английском? Опиши свою последнюю неделю подготовки — что ты делал каждый день?

Ищем: реальный процесс, инструменты, частоту, время. НЕ "как я думаю должен готовиться", а "что я реально делаю".

2.  Pain дискавери

▎ Что в этой подготовке самое больное или раздражающее? Что заставляет тебя откладывать или избегать?

Ищем: эмоциональный язык. "Бесит", "страшно", "не понимаю что делать", "стыдно". Это сигналы реального pain.

3.  Competitor intel + churn reason

▎ Что ты пробовал из инструментов и забросил? Почему именно бросил?

Ищем: имена конкретных продуктов (iTalki, Pramp, ChatGPT, YouTube, books). И — главное — почему перестал. Это формула для вашей retention механики.

4.  Pain классификация

▎ Если бы я попросил поделить главную боль на 4 категории — это (а) свободное говорение, (б) структура ответа, (в) уверенность/нервы, (г) специфичные термины и формулировки — что для тебя главное? Что вторичное?

Ищем: реальный приоритет. Если 3+ из 5 говорят "уверенность" — ваш voice/speaking фокус правильный. Если 3+ говорят "структура" — pivot.

Бонус-вопросы (если есть время и поток идёт)

5.  История последнего интервью

▎ Расскажи про последнее интервью на английском — какой был самый страшный или неловкий момент?

Концентрированный pain. Часто здесь вылетает реальная история.

6.  Pricing reality

▎ Платил ли ты когда-нибудь за подготовку к интервью — репетитор, курс, coaching? Сколько? Стоило того?

Pricing anchor от их прошлого опыта. Если платили $30/час репетитору — $20/session реально. Если только бесплатное — будет тяжело монетизировать.

7.  Magic wand

▎ Если бы у тебя была волшебная палочка чтобы починить ОДНУ вещь в твоей подготовке — что бы это было?

Концентрированный wish. Часто здесь вылетает идея фичи.

Pricing test (в конце call, ОТДЕЛЬНО)

Только после того как услышали pain dosing, можно спросить:

▎ Если бы существовал инструмент который [пересказ их pain ИХ ЖЕ словами], сколько ты бы заплатил за это? Реально ли $20 за сессию? Реально ли $30 в месяц подписка?

Не предлагайте свой продукт. Спрашивайте про гипотетический.

Что слушать (помимо ответов)

- Энтузиазм vs вежливость. Реальный pain звучит эмоционально. Вежливые ответы — ровные.
- Конкретика vs обобщения. "Я открываю YouTube и смотрю мок-интервью" — данные. "Я обычно практикуюсь" — шум.
- Triggers — когда у них следующее интервью? за сколько начинают готовиться? кто сказал что надо готовиться?
- Money signals — сколько раз упомянули деньги? готовы ли тратить?

Типичные ошибки на первых calls

- Слишком много говорите сами ("дай я объясню что я делаю...") → перебивает их поток
- Закрытые вопросы ("ты используешь Pramp?" вместо "что ты используешь?")
- Подсказываете ответы ("наверное, тебе сложно с произношением?") → они согласятся из вежливости
- Защищаете свою гипотезу когда не подтверждается → discovery становится sales pitch
- Боитесь молчания → они додумывают важное в паузах, не заполняйте их

---

Decision framework (после 5 calls)

Day 8 readout: свести все 5 в один документ

Категории:

┌───────────────┬──────────────────────────┬────────────────────────────┐
│ Категория │ Критерий │ Что значит │
├───────────────┼──────────────────────────┼────────────────────────────┤
│ Repeated pain │ 3+ из 5 упомянули │ Core hypothesis confirmed │
├───────────────┼──────────────────────────┼────────────────────────────┤
│ Surprises │ Новый pain, не ожидали │ Потенциальный pivot signal │
├───────────────┼──────────────────────────┼────────────────────────────┤
│ Outliers │ 1–2 человек противоречат │ Noise или edge segment │
└───────────────┴──────────────────────────┴────────────────────────────┘

4 возможных решения

🟢 GO

- 3+ из 5 говорят: speaking + interview prep — top pain
- Pricing test: 2+ готовы к $20/session
- → Запускаете Phase 1 (memory_kind apply, smoke test)
- → Phase 4 pilot: те же 5 на free session

🟡 NARROW

- Pain confirmed, но в более узкой форме
- Например: "не speaking как таковой, а STAR framework structure под pressure"
- → Перепиливаете scope под уточнённый pain
- → Phase 1 с новым target

🟠 PIVOT

- Pain в другом месте
- Например: "не интервью, а ежедневные standup'ы / письма / презентации на английском"
- → Stop. Новая discovery волна на новый segment.

🔴 KILL

- Нет воспроизводимого pain
- Никто не платил за prep, никто не готов платить
- → Серьёзный вопрос: продолжать ли продукт.

---

Что НЕ делать сейчас (между discovery и build)

- ❌ Не делать ещё одну итерацию плана с Codex. План v2 хороший. Sourcing — founder execution.
- ❌ Не открывать build продукт между calls "потому что вспомнилась идея". Записать в backlog, дойти до readout.
- ❌ Не запускать Phase 4 pilot до Phase 0 readout. Соблазн будет ("и так всё ясно").
- ❌ Не выкладывать LinkedIn пост с описанием продукта (lock-in для имиджа до validation).

---

Что делать в фоне (параллельно discovery)

- ✅ memory_kind migration apply (15 мин) — Codex может сделать пока вы делаете calls
- ✅ Заполнить DISCOVERY_TARGET_SHEET_TEMPLATE.csv реальными именами (3 warm + cold candidates)
- ✅ После 2 первых calls — adapt вопросы (если какой-то вопрос даёт мало signal — заменить)

---

После discovery (план следующих 1.5–2 недель если GO)

Phase 1 (week 2): Verification

- memory_kind apply + verify memories persist
- next_mission_choice → session 2 routing — finish Plan C
- Один canonical interview synthetic eval green

Phase 2 (week 2): Text-first ready

- Typed/composer session проходит onboarding → mission → evidence → next mission без TTS
- Manual smoke на одном interview path

Phase 3 (already done): Replay tool

- ✅ scripts/replay_session.py готов
- Каждая pilot session должна иметь reproducible bundle по session_id

Phase 4 (week 3): Pilot

- 3–5 pilot sessions с теми же 5 discovery участниками
- Каждый debrief: что сломалось, релевантна ли next mission, нужен ли voice, придёт ли на session 2, придёт ли на session 3, $20/session реально, $30/month реально
- Failure classification: voice/STT friction | weak mission relevance | low perceived value | generic coaching | runtime failure

Success criteria цикла

- 3 real users прошли session 1
- 1+ cold или mixed-source user в выборке
- 1+ user вернулся на session 2 + дошёл до evidence + сказал "хочу session 3" ИЛИ "заплачу"

---

Architectural decisions log (что решили в ходе обсуждения)

1.  Wedge = только ML/SWE interview prep (не 3 бакета). Workplace + project_walkthrough заморожены до сигнала от пользователя.
2.  Voice → opt-in, не killer feature. Text-first baseline — это retention surface. Voice — differentiator после validation.
3.  Discovery before build — engineer trap "build first, user later" опасен. 5 calls с kill criteria = реальный gate.
4.  Cold user обязателен в sample — warm-only validation = self-deception.
5.  Pricing anchors конкретные — $20/session, $30/month. Тестируем в каждом debrief.
6.  Replay tool > Sentry/Datadog — на pre-PMF level один скрипт + session_id достаточно.
7.  Runtime collapse — voice.py thin wrapper, controller owns turn loop. Закрыто Codex.

- Failure classification: voice/STT friction | weak mission relevance | low perceived value | generic coaching | runtime failure

Success criteria цикла

- 3 real users прошли session 1
- 1+ cold или mixed-source user в выборке
- 1+ user вернулся на session 2 + дошёл до evidence + сказал "хочу session 3" ИЛИ "заплачу"

---

Architectural decisions log (что решили в ходе обсуждения)

1.  Wedge = только ML/SWE interview prep (не 3 бакета). Workplace + project_walkthrough заморожены до сигнала от пользователя.
2.  Voice → opt-in, не killer feature. Text-first baseline — это retention surface. Voice — differentiator после validation.
3.  Discovery before build — engineer trap "build first, user later" опасен. 5 calls с kill criteria = реальный gate.
4.  Cold user обязателен в sample — warm-only validation = self-deception.
5.  Pricing anchors конкретные — $20/session, $30/month. Тестируем в каждом debrief.
6.  Replay tool > Sentry/Datadog — на pre-PMF level один скрипт + session_id достаточно.
7.  Runtime collapse — voice.py thin wrapper, controller owns turn loop. Закрыто Codex.
8.  memory_kind enum migration не блокирует discovery — параллельная задача.
9.  LinkedIn пост ≠ discovery. Если использовать пост — только как lead gen для конверсии в 1-on-1 calls.
10. Engineer план оптимизирует build correctness. Founder план оптимизирует learning velocity. Разница принципиальная.

---

Если discovery даёт zero retained users

План не предусматривает "построить больше." План говорит: failure reasons диктуют следующий cycle. Если все 5 говорят что pain — не speaking, а structure → pivot scope. Если никто не готов платить → серьёзный  
 вопрос про viability продукта.

▎ "If no cold user returns, the cycle does not count as a real validation win even if warm users are supportive."

Это integrity rule. Не нарушайте даже если хочется.

---

Follow-up на следующую сессию (после перезагрузки)

1.  Открыть !DOC/operations/DISCOVERY_TARGET_SHEET_TEMPLATE.csv, заполнить 3 warm + cold candidates
2.  Скопировать outreach текст из этого plan file (раздел "Сообщение для warm DMs")
3.  Отправить 8 warm DMs за 1 час
4.  Назначить calls на эту неделю
5.  Перед первым call — перечитать "Главные правила" и "Типичные ошибки" из этого plan file

---

Артефакт сохранён перед перезагрузкой. Документация в repo (DISCOVERY\_.md) остаётся каноном — этот файл дополняет её русскоязычными discovery questions и architectural decisions log.\*
