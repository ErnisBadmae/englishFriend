-- 009_vocabulary_srs.sql
-- Purpose: Vocabulary cards with FSRS spaced repetition scheduling.

begin;

-- Таблица для хранения словарных карточек с FSRS-алгоритмом
create table if not exists vocabulary_cards (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,

  -- Слово и контекст
  word text not null,                          -- Изучаемое слово/фраза
  translation text,                            -- Перевод (опционально)
  example_sentence text,                       -- Пример из диалога
  phonetic text,                               -- IPA транскрипция

  -- FSRS алгоритм (параметры карточки)
  fsrs_state smallint not null default 0,      -- 0=New, 1=Learning, 2=Review, 3=Relearning
  fsrs_step smallint not null default 0,       -- Шаг в learning/relearning фазе
  fsrs_stability real not null default 0,      -- Стабильность памяти (дни)
  fsrs_difficulty real not null default 0,     -- Сложность карточки (0-10)

  -- Планирование
  due_at timestamptz not null default now(),   -- Когда показать следующий раз
  last_reviewed_at timestamptz,                -- Последний review

  -- Статистика
  review_count int not null default 0,         -- Сколько раз повторяли
  correct_count int not null default 0,        -- Сколько раз правильно

  -- Мета
  source_session_id uuid,  -- No FK due to partitioned sessions table
  created_at timestamptz not null default now(),

  -- Уникальность: один пользователь - одно слово
  constraint vocabulary_cards_user_word_unique unique (user_id, word)
);

-- Индексы для быстрого поиска карточек к повторению
create index if not exists vocab_cards_user_due_idx
  on vocabulary_cards (user_id, due_at)
  where fsrs_state > 0;  -- Только не-новые карточки

create index if not exists vocab_cards_user_state_idx
  on vocabulary_cards (user_id, fsrs_state);

-- Текстовый поиск по словам
create index if not exists vocab_cards_word_trgm_idx
  on vocabulary_cards using gin (word gin_trgm_ops);

-- RLS
alter table vocabulary_cards enable row level security;
do $$ begin
  create policy vocabulary_cards_isolation on vocabulary_cards
    using (user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1));
exception
  when duplicate_object then null;
end $$;

-- Таблица истории повторений (для аналитики и оптимизации FSRS)
create table if not exists vocabulary_reviews (
  id uuid primary key default gen_random_uuid(),
  card_id uuid not null references vocabulary_cards(id) on delete cascade,
  user_id bigint not null references users(id) on delete cascade,

  -- Результат review
  rating smallint not null check (rating between 1 and 4),  -- 1=Again, 2=Hard, 3=Good, 4=Easy

  -- Состояние ДО review (для анализа)
  prev_state smallint not null,
  prev_stability real not null,
  prev_difficulty real not null,

  -- Когда и как долго
  reviewed_at timestamptz not null default now(),
  review_duration_ms int,  -- Сколько думали (опционально)

  -- Контекст (в каком диалоге повторяли)
  session_id uuid  -- No FK due to partitioned sessions table
);

create index if not exists vocab_reviews_card_idx
  on vocabulary_reviews (card_id, reviewed_at desc);

create index if not exists vocab_reviews_user_idx
  on vocabulary_reviews (user_id, reviewed_at desc);

-- RLS
alter table vocabulary_reviews enable row level security;
do $$ begin
  create policy vocabulary_reviews_isolation on vocabulary_reviews
    using (user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1));
exception
  when duplicate_object then null;
end $$;

-- Функция для получения карточек к повторению
create or replace function get_due_vocabulary(
  p_user_id bigint,
  p_limit int default 10
)
returns table (
  id uuid,
  word text,
  translation text,
  example_sentence text,
  fsrs_state smallint,
  due_at timestamptz
)
language sql
stable
as $$
  select
    vc.id,
    vc.word,
    vc.translation,
    vc.example_sentence,
    vc.fsrs_state,
    vc.due_at
  from vocabulary_cards vc
  where vc.user_id = p_user_id
    and vc.due_at <= now()
  order by vc.due_at asc
  limit p_limit;
$$;

commit;
