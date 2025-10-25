Ниже — готовое ТЗ для команды, которая реализует **PostgreSQL**, **Vector DB** и **Graph DB** для проекта «ИИ-репетитор-компаньон». Документ ориентирован на быструю разработку: есть чёткие схемы, индексы, политики, API-контракты, тесты и критерии приёмки.

---

# ТЗ: Хранилища данных (PostgreSQL + VectorDB + GraphDB)

## 0) Цель и объём работ

**Цель:** спроектировать и развернуть надёжный слой данных:

* **Источник истины:** PostgreSQL.
* **Поиск по смыслам:** VectorDB (Qdrant или Pinecone; допустим pgvector как fallback).
* **Графовые выводы и рекомендации:** Neo4j или Memgraph.

**В scope:**

* DDL/миграции для PostgreSQL, индексы, партиции, RLS.
* Схемы коллекций и запросов VectorDB, код синхронизации.
* Модель графа, ограничения, базовые Cypher-запросы, код синхронизации.
* Политики ретенции/безопасности, базовые матвью и отчёты.
* Тестовые данные, нагрузочные и приёмочные тесты.
* Docker-окружение для локального запуска (compose).

**Вне scope:** бэкенд-API/бот, WebRTC, Realtime-модель — только контракт с хранилищами.

---

## 1) Архитектура данных (обзор)

* **PostgreSQL (источник истины)**
  Сущности: пользователи, сессии, реплики (utterances), обратная связь, исправления, интересы, план обучения, очки/события.
  Особенности: партиционирование больших таблиц, JSONB + GIN там, где нужна гибкость, RLS по `user_id`, CDC для синхронизации наружу.

* **VectorDB (Qdrant/Pinecone, опционально pgvector)**
  Коллекция `memories`: эпизодическая/семантическая/персона/скилл память.
  Гибридный запрос: ANN + фильтры (`user_id`, `kind`) + буст важности/свежести в приложении.

* **GraphDB (Neo4j/Memgraph)**
  Узлы: `User`, `Session`, `Utterance`, `Topic`, `Emotion`, `Memory`, `Persona`.
  Связи с весами и временными метками. Используется для рекомендаций тем и анализа эмоций/интересов.

* **Синхронизация:** CDC (Debezium/Kafka) или периодические батчи. Идемпотентные upsert-ы по `id`.

---

## 2) PostgreSQL — модель и миграции

### 2.1 Расширения

```sql
-- расширения (поставить в 000_init.sql)
create extension if not exists pgcrypto;     -- gen_random_uuid()
create extension if not exists btree_gin;
create extension if not exists pg_trgm;      -- поиск по тексту
-- если выбран pgvector как fallback:
-- create extension if not exists vector;
```

### 2.2 Типы и справочники

```sql
create type cefr_level as enum ('A1','A2','B1','B2','C1','C2');
create type memory_kind as enum ('episodic','semantic','persona','skill');
create type access_channel as enum ('telegram','mobile_app','web');

create table dim_emotion (
  code text primary key,
  name_ru text not null,
  valence int not null check (valence between -5 and 5),
  arousal int not null check (arousal between 0 and 5)
);

create table dim_topic (
  id uuid primary key,
  slug text unique not null,
  display_name text not null,
  parent_id uuid references dim_topic(id) on delete set null
);

create table dim_accent (
  code text primary key,
  display_name text not null
);
```

### 2.3 Пользователи и интересы

```sql
create table users (
  id bigserial primary key,
  telegram_id bigint unique,
  username varchar(255),
  language_level cefr_level,
  primary_channel access_channel not null default 'telegram',
  accent_pref text references dim_accent(code),
  pii_envelope bytea,                      -- опционально: зашифрованный PII
  created_at timestamptz default now(),
  deleted_at timestamptz
);

create table user_channel_identity (
  id uuid primary key,
  user_id bigint references users(id) on delete cascade,
  channel access_channel not null,
  external_id text not null,
  auth_payload jsonb,
  linked_at timestamptz default now(),
  unique (channel, external_id),
  unique (user_id, channel)
);
create index user_channel_identity_uidx on user_channel_identity (user_id, channel);

create table user_interest (
  user_id bigint references users(id) on delete cascade,
  topic_id uuid references dim_topic(id) on delete cascade,
  weight real not null default 0,          -- [0..1]
  last_mentioned timestamptz,
  primary key (user_id, topic_id)
);

create index user_interest_u_w on user_interest (user_id, weight desc);
```

### 2.4 Сессии, реплики, обратная связь

> **Партиционирование:** по месяцам для `sessions`, `utterances`, `xp_events`.

```sql
-- родитель
create table sessions (
  id uuid primary key,
  user_id bigint references users(id) on delete cascade,
  started_at timestamptz not null,
  ended_at timestamptz,
  audio_url text,
  lang_code text default 'en',
  call_quality jsonb,
  constraint chk_time check (ended_at is null or ended_at >= started_at)
) partition by range (started_at);

-- пример партиции (скрипт/джоб для создания ежемесячно)
create table sessions_2025_10 partition of sessions
for values from ('2025-10-01') to ('2025-11-01');

-- utterances
create table utterances (
  id uuid primary key,
  session_id uuid references sessions(id) on delete cascade,
  speaker text not null check (speaker in ('user','assistant')),
  t_start_ms int not null,
  t_end_ms int not null,
  text text not null,
  phonemes jsonb,
  topics jsonb,                             -- [{topic_id,score}]
  emotion_code text references dim_emotion(code),
  emotion_score real,
  grammar_score real,
  pronunciation_score real
) partition by hash (session_id);

-- пример шард-партиций (кол-во тюним под объём)
create table utterances_p0 partition of utterances for values with (modulus 8, remainder 0);
create table utterances_p1 partition of utterances for values with (modulus 8, remainder 1);
-- ... p2..p7

create index on utterances_p0 (session_id, t_start_ms);
create index utter_topics_gin_p0 on utterances_p0 using gin (topics jsonb_path_ops);
-- (создать соответствующие индексы для p1..p7)

create table feedback (
  session_id uuid primary key references sessions(id) on delete cascade,
  overall_grammar real,
  overall_pronunciation real,
  summary_md text,
  tips_md text
);

create table corrections (
  id uuid primary key,
  session_id uuid references sessions(id) on delete cascade,
  utterance_id uuid references utterances(id) on delete set null,
  user_text text not null,
  corrected_text text not null,
  rule_tag text,
  explanation_md text
);
create index on corrections (session_id);
```

### 2.5 Память (канонические записи)

Если используем **внешний VectorDB** — в Postgres храним канон без векторов:

```sql
create table memories (
  id uuid primary key,
  user_id bigint references users(id) on delete cascade,
  kind memory_kind not null,
  content text not null,
  meta jsonb,                               -- {source_session, emotion, topic_ids[], ...}
  salience real default 0.5,
  last_refreshed timestamptz default now(),
  created_at timestamptz default now()
);
create index on memories (user_id, kind);
create index mem_meta_gin on memories using gin (meta jsonb_path_ops);
```

Если fallback **pgvector**, добавить:

```sql
-- create extension vector; (см. выше)
alter table memories add column embedding vector(1536);
create index mem_vec_idx on memories using ivfflat (embedding vector_cosine) with (lists = 200);
```

### 2.6 Игровые/планировочные сущности

```sql
create table learning_plan (
  id uuid primary key,
  user_id bigint references users(id) on delete cascade,
  level_target cefr_level,
  next_review_at timestamptz,
  roadmap jsonb
);

create table xp_events (
  id uuid primary key,
  user_id bigint references users(id) on delete cascade,
  session_id uuid references sessions(id) on delete set null,
  kind text,
  points int not null,
  happened_at timestamptz default now()
) partition by range (happened_at);

create table xp_events_2025_10 partition of xp_events
for values from ('2025-10-01') to ('2025-11-01');
create index on xp_events_2025_10 (user_id, happened_at desc);
```

### 2.7 RLS и безопасность

```sql
-- включить RLS
alter table users enable row level security;
alter table sessions enable row level security;
alter table utterances enable row level security;
alter table memories enable row level security;
alter table user_interest enable row level security;
alter table feedback enable row level security;
alter table corrections enable row level security;

-- роли: app_api, ingest, analytics (только чтение агрегатов)
-- пример политики (приведённо для app_api):
create policy users_isolation on users
  for select using (id = current_setting('app.user_id')::bigint);

create policy sessions_isolation on sessions
  for all using (user_id = current_setting('app.user_id')::bigint);

-- для сервисов ingest использовать отдельные роли с BYPASSRLS = false,
-- и технические политики (например, по API-ключу в custom GUC).
```

### 2.8 Материализованные представления (отчёты)

```sql
create materialized view mv_weekly_user_summary as
select
  u.id as user_id,
  date_trunc('week', s.started_at) as week,
  count(distinct s.id) as sessions_cnt,
  avg(f.overall_grammar) as avg_grammar,
  avg(f.overall_pronunciation) as avg_pron
from users u
left join sessions s on s.user_id = u.id
left join feedback f on f.session_id = s.id
where s.started_at >= now() - interval '8 weeks'
group by 1,2;

-- обновление по расписанию (cron/pgagent): refresh materialized view concurrently mv_weekly_user_summary;
```

---

## 3) VectorDB — схема и операции

### 3.1 Коллекция `user_memories`

**Embedding:** 1536 (пример под OpenAI text-embedding-3-large; число можно вынести в конфиг).
**Метрика:** cosine.
**Поля-фильтры (payload):**
`user_id: int64`, `kind: enum{'episodic','semantic','persona','skill'}`,
`salience: float`, `created_at: int64 (epoch)`, `last_refreshed: int64`,
`emotion_code: string?`, `topic_ids: string[]`, `source_session: uuid?`, `source_utterance: uuid?`.

### 3.2 Qdrant (предпочтительный вариант)

**Создание коллекции (HNSW + quantization по объёму):**

```json
{
  "name": "user_memories",
  "vectors": { "size": 1536, "distance": "Cosine" },
  "hnsw_config": { "m": 16, "ef_construct": 128 },
  "optimizers_config": { "default_segment_number": 4 },
  "quantization_config": { "scalar": { "type": "int8", "always_ram": true } }
}
```

**Upsert (идемпотентно по `id` = UUID из Postgres):**

```json
{
  "points": [{
    "id": "UUID",
    "vector": [ ...1536... ],
    "payload": {
      "user_id": 123,
      "kind": "episodic",
      "salience": 0.62,
      "created_at": 1730000000,
      "last_refreshed": 1730000000,
      "emotion_code": "joy",
      "topic_ids": ["<uuid>","<uuid>"],
      "source_session": "<uuid>",
      "source_utterance": "<uuid>"
    }
  }]
}
```

**Query (top-k=12, фильтры + буст в приложении):**

```json
{
  "vector": [ ... ],
  "limit": 12,
  "filter": {
    "must": [
      {"key": "user_id", "match": {"value": 123}},
      {"key": "kind", "match": {"value": "episodic"}}
    ],
    "should": [
      {"key": "topic_ids", "match": {"any": ["<uuid>"]}}
    ]
  },
  "with_payload": true
}
```

> Примечание: после получения результатов — **пересчитать итоговый score**:
> `score_final = alpha * cosine + beta * salience + gamma * recency_boost(created_at)`.

**Удаление (право «быть забытым»):** по `id` или по фильтру `user_id`.

### 3.3 Pinecone (альтернатива)

* Namespace: `user_{user_id}` или глобальный + метаданные.
* Метрика: cosine.
* Метаданные аналогичны Qdrant payload.

### 3.4 Fallback: pgvector

* Колонка `embedding vector(1536)` в `memories`.
* Индекс IVFFlat/HNSW (в зависимости от версии).
* Запрос:

```sql
select id, content, salience, meta
from memories
where user_id = $1 and kind = any('{episodic,semantic}')
order by embedding <=> $2
limit 12;
```

---

## 4) GraphDB — модель и операции (Neo4j)

### 4.1 Узлы и свойства

* `User{userId: int, level: string, accent: string}`
* `Session{id: uuid, startedAt: datetime}`
* `Utterance{id: uuid, tStart: int, tEnd: int, speaker: 'user'|'assistant'}`
* `Topic{id: uuid, slug: string, name: string}`
* `Emotion{code: string, valence: int, arousal: int}`
* `Memory{id: uuid, kind: string, salience: float}`
* `Persona{trait: 'O'|'C'|'E'|'A'|'N', score: float}`

### 4.2 Связи (свойства)

* `(:User)-[:PARTICIPATED_IN]->(:Session)`
* `(:Session)-[:CONTAINS]->(:Utterance)`
* `(:Utterance)-[:ABOUT {score:float, first_seen:datetime, last_seen:datetime, count:int}]->(:Topic)`
* `(:Utterance)-[:EXPRESSES {score:float}]->(:Emotion)`
* `(:User)-[:INTEREST_IN {weight:float, first_seen, last_seen, count, decay_ts}]->(:Topic)`
* `(:User)-[:HAS_MEMORY {since:datetime, last_refreshed:datetime}]->(:Memory)`
* `(:Topic)-[:RELATED_TO {weight:float, method:string}]->(:Topic)`
* `(:User)-[:HAS_TRAIT {score:float}]->(:Persona)`

### 4.3 Ограничения/индексы

```cypher
create constraint if not exists user_id_unique for (u:User) require u.userId is unique;
create constraint if not exists topic_id_unique for (t:Topic) require t.id is unique;
create index if not exists topic_slug_idx for (t:Topic) on (t.slug);
create constraint if not exists session_id_unique for (s:Session) require s.id is unique;
create constraint if not exists utter_id_unique for (u:Utterance) require u.id is unique;
create constraint if not exists memory_id_unique for (m:Memory) require m.id is unique;
```

### 4.4 Идемпотентные MERGE-скрипты (ингест)

```cypher
// сессия и участие
merge (u:User {userId:$userId})
merge (s:Session {id:$sessionId})
  on create set s.startedAt = datetime($startedAt)
merge (u)-[:PARTICIPATED_IN]->(s);

// реплика
merge (utt:Utterance {id:$uttId})
  on create set utt.tStart=$tStart, utt.tEnd=$tEnd, utt.speaker=$speaker
merge (s)-[:CONTAINS]->(utt);

// тема
merge (t:Topic {id:$topicId})
  on create set t.slug=$slug, t.name=$name
merge (utt)-[r:ABOUT]->(t)
  on create set r.score=$score, r.first_seen=datetime(), r.last_seen=datetime(), r.count=1
  on match  set r.score=$score, r.last_seen=datetime(), r.count=r.count+1;

// интерес с затуханием
merge (u)-[i:INTEREST_IN]->(t)
  on create set i.weight=$w, i.first_seen=datetime(), i.last_seen=datetime(), i.count=1
  on match  set i.weight=0.9*i.weight + 0.1*$w, i.last_seen=datetime(), i.count=i.count+1;
```

### 4.5 Базовые запросы

* **Рекомендации тем:**

```cypher
match (u:User {userId:$uid})-[i:INTEREST_IN]->(t:Topic)-[rel:RELATED_TO]->(t2:Topic)
with t2, sum(i.weight * rel.weight) as score
order by score desc
return t2.slug as topic, score
limit 10;
```

* **Эмоции за период:**

```cypher
match (:User {userId:$uid})-[:PARTICIPATED_IN]->(s:Session)-[:CONTAINS]->(:Utterance)-[e:EXPRESSES]->(emo:Emotion)
where s.startedAt >= datetime($since)
return emo.code as emotion, count(*) as cnt order by cnt desc;
```

---

## 5) Синхронизация (CDC/ETL)

### 5.1 Из PostgreSQL в VectorDB

* Триггер/CDC на `memories` (insert/update/delete).
* Worker (`sync-vector`) читает события, выполняет upsert/delete в Qdrant/Pinecone.
* Идемпотентность: ключ — `memories.id`.
* Ошибки/повторы ведут в DLQ (Kafka topic).
* Периодический reconcile-джоб сверяет количество записей и выборочно хеш-сэмплит содержимое.

### 5.2 Из PostgreSQL в GraphDB

* CDC на `sessions`, `utterances`, `corrections`, `user_interest`.
* Worker (`sync-graph`) батчит события в пачки по 500–1000 и делает Cypher-MERGE.
* Для `dim_topic`/`dim_emotion` — прайминг справочников перед основным потоком.

---

## 6) Политики данных

* **Ретенция аудио:** в PG хранится только `audio_url`. Реальные файлы — MinIO/S3 (SSE-S3/SSE-KMS). TTL для аудио: 90 дней (конфигурируемо).
* **«Право быть забытым»:**

  1. удалить из PG все строки по `user_id` (каскад).
  2. удалить точки из VectorDB по `user_id`.
  3. удалить узлы/рёбра в GraphDB по `userId`.
  4. удалить объекты в S3.
  5. снять снапшоты/бэкапы по регламенту.
* **Шифрование/секреты:** доступы в Vault/Secrets Manager; PII в `users.pii_envelope` шифровать (pgcrypto, app-side ключи).
* **RLS:** включена и обязательна для всех таблиц с `user_id`.

---

## 7) Наблюдаемость и бэкапы

* **Метрики:** PG (pg_stat_statements), Qdrant/Pinecone latency, Neo4j query time, размер индексов, hit ratio, VACUUM.
* **Логи:** структурированные, корреляция по `session_id`, `user_id`.
* **Бэкапы PG:** ежедневные инкрементальные + еженедельные полные (WAL-архив).
* **Бэкапы Neo4j:** snapshot/backup согласно вендору. Qdrant — snapshot + экспорт.
* **Алёрты:** p95 latency запросов > целевых порогов, рост dead tuples, отставание реплик/CDC.

---

## 8) Производительность (SLO/цели)

* **Vector top-k (12) с фильтрами:** p95 ≤ 150 мс при N=1e6 точек на ноде.
* **Cypher рекомендации тем:** p95 ≤ 200 мс на графе с 1e6 узлов/5e6 рёбер.
* **Поиск реплик по теме (GIN по JSONB):** p95 ≤ 120 мс на партиции до 10 млн строк.
* **Запись реплики:** ≤ 20 мс в PG (без ожидания CDC).
* **Обновление матвью (неделя):** ≤ 5 мин.

---

## 9) Тестирование и приёмка

### 9.1 Юнит/интеграционные

* DDL миграции применяются на пустую БД и на непустую (idempotent).
* RLS: пользователь не видит чужие строки (проверка через `set local app.user_id`).
* Индексы и партиции существуют, планы запросов используют их (EXPLAIN ANALYZE).

### 9.2 E2E сценарии (минимум)

1. **Инжест сессии:** создать `session`, `utterances`, `feedback`, `corrections` → записи появились в PG; в графе есть `User-Session-Utterances`; интересы обновились.
2. **Создание памяти:** upsert в PG → точка появилась в VectorDB; запрос ANN возвращает её в top-k.
3. **Удаление пользователя:** каскад в PG + очистка в Vector/Graph + S3.
4. **Рекомендации:** граф-запрос возвращает ожидаемые темы, латентность в норме.

### 9.3 Нагрузочные

* Генерация 100k пользователей, 10M реплик, 5M memories.
* Мерить p50/p95 latencies по целям из раздела 8.

---

## 10) Поставка (Deliverables)

1. **Репозиторий `/db`:**

   * `/migrations/postgres` — SQL миграции (Flyway/Liquibase).
   * `/seed` — минимальные справочники (эмоции, акценты, пары тем).
   * `/matviews` — скрипты матвью/обновления.
   * `/tests` — SQL-тесты (pgTAP либо простые psql-скрипты).

2. **Репозиторий `/sync`:**

   * `sync-vector/` — сервис CDC→Qdrant/Pinecone (upsert/delete, retry, DLQ).
   * `sync-graph/` — сервис CDC→Neo4j (батчи MERGE).
   * Общие proto/JSON-схемы событий CDC.

3. **Репозиторий `/graph`:**

   * `schema.cypher` — constraints/indexes, базовые MERGE-процедуры.
   * `queries.cypher` — рекомендательные/аналитические запросы.

4. **Docker Compose (`/ops/compose.yml`):**

   * `postgres`, `qdrant` (или `pinecone` stub), `neo4j`, `minio` (dev), `sync-*`.
   * Makefile для поднятия окружения, прогонки миграций и seed.

5. **Документация:**

   * README с инструкциями по запуску и тестам.
   * Политики ретенции/удаления, чек-лист оператора.

---

## 11) Приложение: пример контрактов

### 11.1 API «создать память» (внутренний)

```json
POST /internal/memories
{
  "id": "uuid",               // если не передан — генерит сервис
  "user_id": 123,
  "kind": "episodic",
  "content": "You love minimalist design.",
  "meta": {"emotion":"joy","topic_ids":["<uuid>"],"source_session":"<uuid>"},
  "embedding": [ ...1536... ],
  "salience": 0.7
}
```

**Ожидаемо:** запись в PG + upsert в VectorDB (асинхронно через CDC, но с подтверждением постановки в очередь).

### 11.2 Гибридный поиск (бэкенд → Vector + PG)

* VectorDB top-k (12) с фильтрами.
* Пост-ранжирование в приложении: `score_final = 0.7*cosine + 0.2*salience + 0.1*recency`.
* Из PG подтянуть `content/meta` по `id`.

---

## 12) Риски и решения

* **Рост JSONB без индексов** → обязательные GIN + регламент vacuum/analyze.
* **«Разъезд» канона и векторов** → reconcile-джобы и контроль кардинальности.
* **Графовые MERGE-батчи** → логи по конфликтам, ограничение размера батча, ретраи.
* **Секреты и PII** → Vault/KMS, аудит доступа, BYPASSRLS запрещён.

---

### Критерии приёмки (коротко)

* Все миграции применяются «с нуля» и на «грязной» БД без потери данных.
* RLS работает, чужие данные недоступны.
* Vector-поиск и граф-запросы укладываются в целевые p95.
* Удаление пользователя вычищает PG + Vector + Graph + S3.
* Матвью/отчёты обновляются и доступны.
* Полный локальный стенд запускается одной командой и проходит тест-скрипты.

---
