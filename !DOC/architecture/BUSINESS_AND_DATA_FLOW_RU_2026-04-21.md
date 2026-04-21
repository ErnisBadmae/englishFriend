---
last_updated: 2026-04-21
status: Russian business and data-flow schematic
---

# Архитектура Продукта: Бизнес-Логика И Движение Данных

Этот документ нужен для наглядного ответа на три вопроса:

1. Какую проблему пользователя решает EnglishFriend.
2. Как продукт это делает шаг за шагом.
3. Как именно текут данные внутри системы и где у нас появляется moat.

Короткая формула:

`не просто voice tutor -> а career-state engine -> evidence loop -> adaptive missions`

## 1. Какая у пользователя проблема

Наш пользователь обычно выглядит так:

- это русскоязычный ML/AI или соседний IT-специалист
- он хочет международную работу, интервью, сильнее звучать в команде
- у него есть реальные навыки, но слабый spoken English под давлением
- он знает "что делал", но плохо упаковывает это в уверенный английский ответ
- на интервью и в рабочих разговорах он теряет структуру, темп и точность

Проблема пользователя не сводится к "я не знаю английский".

На деле проблема такая:

```text
У меня есть карьерная цель
  ->
я не умею стабильно говорить под эту цель на английском
  ->
я заваливаю интервью / project walkthrough / workplace communication
  ->
я теряю деньги, офферы и скорость карьерного роста
```

## 2. Почему обычный AI tutor не решает эту проблему

Обычный tutor или generic LLM чаще всего делает так:

```text
пользователь спросил что-то
  ->
модель ответила
  ->
пользователь еще что-то спросил
  ->
еще один хороший ответ
```

Это полезно, но этого мало, потому что:

- у generic tutor нет жесткой привязки к карьерной цели
- он не хранит состояние "относительно вакансии и слабых мест"
- он не строит следующую миссию из провала прошлой сессии
- он не превращает project experience в карьерный speaking asset

То есть он помогает "учиться", но плохо помогает "пройти путь к офферу".

## 3. Как EnglishFriend решает проблему

Наш продукт должен вести пользователя по управляемому карьерному циклу.

### Схема бизнес-логики

```text
Карьерное намерение пользователя
  +
слабый spoken English под давлением
        |
        v
Система уточняет цель
  target role / target market / тип коммуникации
        |
        v
Система оценивает текущий baseline
  что человек уже умеет говорить, а что ломается
        |
        v
Система дает одну следующую миссию
  не "все сразу", а один ближайший полезный speaking task
        |
        v
Пользователь проходит guided session
        |
        v
Система собирает evidence
  ошибки, слабые места, score, improvement, blockers
        |
        v
Следующая миссия адаптируется
  repeat / narrow / advance
        |
        v
Пользователь начинает звучать сильнее
  на интервью, в project walkthrough, в рабочих разговорах
        |
        v
Растет вероятность оффера и уверенной международной работы
```

### Что пользователь покупает на самом деле

Пользователь платит не за "чат с голосом".

Он платит за сокращение расстояния между:

```text
текущий уровень речи
        ->
уровень речи, достаточный для оффера и уверенной работы
```

То есть продукт продает:

- больше шансов пройти интервью
- лучше упакованный project story
- более уверенную речь в рабочих сценариях
- понятный следующий шаг, а не хаотичную учебу

## 4. Схема продукта на одном экране

Вот самая важная схема в упрощенном виде.

```text
Сигналы на входе
  текст + голос + вакансия + project notes + история сессий
        |
        v
Career State Engine
  цель + baseline + stage + blockers + readiness
        |
        v
Mission Router
  что делать дальше и почему
        |
        v
Session Runtime
  guided voice/text session
        |
        v
Evidence Layer
  outcome_score + weakness_tags + error_patterns + adaptation_hint
        |
        v
Artifacts + Memory
  interview pack + project story pack + learner profile
        |
        v
Home / Snapshot
  следующая миссия, reason, прогресс, артефакты
```

## 5. Как движутся данные внутри системы

Ниже схема уже ближе к реальной архитектуре продукта.

Важно: выше я показывал упрощенную продуктовую схему.

Она отвечала на вопрос:

- как работает основной карьерный loop

Но она не показывала полный infra contour:

- PostgreSQL как source of truth
- CDC / Debezium / Kafka как транспорт изменений
- sync-vector / sync-graph как асинхронные consumer services
- Qdrant / Neo4j как вторичные специализированные хранилища

Ниже обе схемы разведены явно.

### Продуктовый data flow

```text
Пользователь
  |
  | 1. вводит текст / говорит / вставляет vacancy / пишет project notes
  v
Frontend
  HomePage / VoiceChatV2 / формы вакансии и проекта
  |
  | 2. отправляет данные в API
  v
Backend API
  /api/v1/programs/*
  /api/v1/career/*
  /api/v1/voice/*
  |
  | 3. обновляет product state
  v
State Services
  LearningPlanService
  ProgramSnapshotService
  voice_session service
  |
  | 4. запускает session runtime или rebuild snapshot
  v
Session Runtime
  /chat/v2 или /realtime
  STT -> coach runtime -> TTS
  |
  | 5. по завершению сессии сохраняет outcome
  v
Persistence
  learning_plan.roadmap
  session_evidence[]
  memories
  xp_events
  interview/project artifacts
  |
  | 6. snapshot читает обновленное состояние
  v
ProgramSnapshot
  mission + adaptation_reason + evidence_source + packs
  |
  | 7. frontend показывает что делать дальше
  v
Пользователь видит следующую миссию и причину
```

### Что важно в этой схеме

- Frontend не должен сам решать pedagogy и routing.
- Product state живет на сервере.
- Session transcript сам по себе не равен progress.
- Progress появляется только когда transcript превращается в evidence.

### Полный системный data flow

Вот уже не упрощенная product-схема, а полная схема движения данных с инфраструктурным контуром.

```text
Пользователь
  |
  v
Frontend
  HomePage / VoiceChatV2 / vacancy / project notes
  |
  v
Backend API
  /programs /career /voice
  |
  v
Core Services
  LearningPlanService
  ProgramSnapshotService
  voice_session service
  MemoryPipeline
  |
  v
PostgreSQL
  users
  sessions
  utterances
  learning_plan
  memories
  xp_events
  interview artifacts
  project artifacts
  |
  | source of truth
  |
  +------------------------------+
  |                              |
  | A. sync mainline reads       | B. async replication / indexing
  |                              |
  v                              v
ProgramSnapshot / Home      Debezium CDC
mission + reason            |
evidence + roadmap          v
                            Kafka topics
                            |
                            +--------------------------+
                            |                          |
                            v                          v
                       sync-vector                 sync-graph
                            |                          |
                            v                          v
                         Qdrant                     Neo4j
                 semantic memory index      graph of sessions / interests / relations
```

### Что куда идет на самом деле

#### PostgreSQL

`PostgreSQL` у нас не выключен и не опущен.

Наоборот, это главный слой системы:

- основной source of truth
- вся продуктовая запись сначала должна оказаться здесь
- отсюда строится `ProgramSnapshot`
- отсюда живут roadmap, session evidence, artifacts, XP, memories

То есть product loop держится именно на PostgreSQL.

#### Qdrant

`Qdrant` нужен не как основная база продукта, а как semantic retrieval layer.

Он нужен для:

- поиска релевантных memories по смыслу
- retrieval в prompt context
- долгосрочной персонализации там, где обычных SQL-фильтров уже мало

Важно: в текущем коде `Qdrant` участвует как retrieval layer в mainline, но запись в него должна идти вне пользовательского request path после PostgreSQL commit.

То есть сегодня у нас есть direct path:

```text
MemoryPipeline
  ->
PostgreSQL memories
  ->
best-effort background sync into Qdrant
```

И отдельно есть более широкая infra-логика через CDC, которая описана в `DB.md` и `SYSTEM_OVERVIEW.md`.

#### Neo4j

`Neo4j` не является главным хранилищем текущего product loop.

Его роль:

- relation layer
- graph analytics
- interest graph
- потенциальные recommendation paths

На текущем wedge он не должен стоять в hot path каждого пользовательского действия.

Именно поэтому в сокращенной продуктовой схеме он не был нарисован как обязательный шаг перед каждой миссией.

#### Debezium + Kafka + CDC

Этот слой нужен не для прямой бизнес-логики на каждом экране, а для надежной асинхронной доставки изменений из PostgreSQL в специализированные хранилища.

Смысл такой:

```text
PostgreSQL
  ->
Debezium читает WAL / logical replication
  ->
Kafka topics
  ->
sync services
  ->
Qdrant / Neo4j
```

То есть этот слой не "вместо backend".
Это infra bus поверх backend.

## 5.1. Два контура системы: hot path и async path

Чтобы не было путаницы, систему лучше видеть как два разных контура.

### Контур 1. Hot path

Это то, что критично для UX прямо сейчас.

```text
Frontend
  ->
Backend API
  ->
PostgreSQL
  ->
ProgramSnapshot / session runtime / Home
```

Это должно быть:

- быстро
- надежно
- детерминированно

Именно этот контур двигает продукт сегодня.

### Контур 2. Async knowledge path

Это контур обогащения и индексации.

```text
PostgreSQL
  ->
CDC / Debezium
  ->
Kafka
  ->
sync-vector / sync-graph
  ->
Qdrant / Neo4j
```

Это должно быть:

- асинхронно
- идемпотентно
- наблюдаемо
- устойчиво к ретраям и отставанию

Этот контур не обязан участвовать в каждом ответе системы синхронно.

## 5.2. Что реально используется сегодня, а что архитектурно важно

Это важное различие.

### Что реально в текущем mainline ближе всего к продукту

- `Frontend -> Backend API -> PostgreSQL`
- `ProgramSnapshot` читает product state из PostgreSQL
- `MemoryPipeline` сохраняет memory в PostgreSQL
- `MemoryPipeline` уже умеет best-effort background sync в `Qdrant` после PostgreSQL commit
- `MemoryPipeline` уже умеет retrieval из `Qdrant` для relevant context

### Что существует как infra direction и system layer

- `Debezium`
- `Kafka`
- `sync-vector`
- `sync-graph`
- `Neo4j` graph layer
- более полный CDC-driven sync между хранилищами

То есть они не "выключены".
Они просто не были показаны в упрощенной схеме mainline loop.

## 5.3. Роли каждого слоя без путаницы

Вот короткая таблица смысла каждого слоя.

```text
Frontend
  интерфейс и input capture

Backend API + services
  бизнес-логика, pedagogy, state transitions, routing

PostgreSQL
  source of truth

Qdrant
  semantic retrieval and vector memory index

Neo4j
  graph relations, interests, recommendation/analytics layer

Debezium + Kafka
  async event transport and replication layer

sync-vector / sync-graph
  consumers, которые превращают изменения из PG в materialized secondary stores
```

## 5.4. Исправленная итоговая схема

Если рисовать одну максимально честную схему, она должна выглядеть так:

```text
Пользователь
  ->
Frontend
  ->
Backend API
  ->
Core services
  ->
PostgreSQL  [source of truth]
  ->
ProgramSnapshot / Home / mission routing

И параллельно:

PostgreSQL
  ->
Debezium CDC
  ->
Kafka
  ->
sync-vector -> Qdrant
  ->
semantic retrieval back into prompts

И параллельно:

PostgreSQL
  ->
Debezium CDC
  ->
Kafka
  ->
sync-graph -> Neo4j
  ->
graph analytics / recommendation layer
```

## 6. Движение данных внутри одной сессии

### Runtime flow

```text
Пользователь говорит
  |
  v
STT
  browser Vosk или backend Parakeet
  |
  v
Текст попадает в bounded coach runtime
  |
  v
Coach runtime смотрит на:
  mission contract
  learner profile
  relevant memory
  current stage
  |
  v
LLM/coach решает следующий pedagogical move
  уточнить / сузить / поправить / продвинуть / завершить
  |
  v
TTS или текстовый ответ пользователю
  |
  v
В конце сессии:
  summary + evidence + memory extraction + XP + next mission routing
```

### Где чаще всего ломается UX

Исторически у нас слабые точки были здесь:

- STT плохо слышит broken English
- post-session path падал на `xp_events` или memory extraction
- следующая миссия назначалась слишком детерминированно, без жесткой связи с реальным провалом

Именно поэтому текущий roadmap такой:

1. стабилизировать mainline demo path
2. улучшить STT через backend Parakeet
3. замкнуть evidence loop
4. усилить wedge через project story pack

## 7. Как продукт реально помогает пользователю

Ниже важна не архитектура системы, а логика результата.

### До продукта

```text
У меня есть опыт
  ->
я плохо объясняю его на английском
  ->
я путаюсь на интервью
  ->
получаю слабый outcome
```

### После нескольких циклов продукта

```text
У меня есть целевая роль и контекст вакансии
  ->
система знает мои слабые speaking patterns
  ->
я тренирую не "английский вообще", а конкретный карьерный task
  ->
после каждой сессии система понимает, что именно повторить или продвинуть
  ->
мои ответы становятся короче, точнее, увереннее и структурнее
  ->
я лучше прохожу реальные интервью и рабочие разговоры
```

### В чем тут бизнес-ценность

Продукт уменьшает три вида потерь пользователя:

1. Потеря офферов:
   хорошие специалисты отпадают не из-за hard skills, а из-за слабой verbal packaging.
2. Потеря времени:
   люди тратят месяцы на хаотичную практику без связи с реальной карьерной целью.
3. Потеря уверенности:
   после нескольких неудачных speaking ситуаций человек начинает избегать международных возможностей.

Значит, EnglishFriend должен давать:

- faster time to interview readiness
- выше конверсию из опыта в сильный spoken answer
- меньше хаоса в learning path

## 8. Где именно находится moat

Moat не в одном компоненте.

Он складывается из четырех слоев.

### 1. Goal-relative state

Мы храним не просто "профиль пользователя", а состояние относительно цели:

- какая роль нужна
- какой тип коммуникации важен
- какие слабые места мешают именно этой цели

### 2. Pedagogy for weak English

Мы строим coaching для людей, которые:

- отвечают неровно
- смешивают языки
- ломаются под давлением
- еще не могут дать чистый STAR или project walkthrough

### 3. Evidence-driven routing

Следующая миссия должна вытекать из прошлой:

```text
session
  ->
evidence
  ->
weakness pattern
  ->
repeat or advance
  ->
next mission
```

Именно это отличает продукт от generic tutor.

### 4. Audience-specific artifact flywheel

Со временем система начинает копить очень ценные артефакты для узкой аудитории:

- типовые ошибки русскоязычных IT-специалистов
- типовые слабые места в project storytelling
- типовые провалы в interview answers
- миссии, которые реально помогают этому сегменту

Это и есть накапливаемый moat.

## 9. Почему Parakeet важнее PersonaPlex на этом этапе

Эти технологии решают разные задачи.

### Parakeet

`Parakeet` улучшает ядро mainline loop:

- лучше слышит пользователя
- уменьшает количество ложных ошибок
- улучшает качество evidence
- делает guided session физически более полезной

То есть он усиливает moat напрямую.

### PersonaPlex

`PersonaPlex` улучшает в первую очередь delivery:

- full-duplex experience
- premium-feel
- более "живой" conversational UX

Это ценно, но это не первый множитель moat.

### Практическое правило

Если вопрос звучит так:

- "что сильнее улучшит core product?" -> `Parakeet`
- "что сильнее улучшит premium voice experience?" -> `PersonaPlex`

## 10. К чему мы стремимся архитектурно

Итоговая цель архитектуры:

```text
Не tutor platform
Не agent shell
Не notebook workspace

А:

career-English operating loop
  с узким ICP
  с server-owned product state
  с evidence-driven routing
  с replaceable voice layer
  с растущим artifact flywheel
```

## 11. Что смотреть вместе с этим документом

- Целевая архитектура в краткой форме: [./TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md](./TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md)
- Активный roadmap: [../strategy/ROADMAP.md](../strategy/ROADMAP.md)
- Текущее состояние продукта: [../operations/CURRENT_PRODUCT_STATE.md](../operations/CURRENT_PRODUCT_STATE.md)
