-- 012_ml_technical_practice.sql
-- Purpose: durable relational evidence for ml_technical practice.

begin;

do $$
declare
  malformed_count integer;
begin
  select count(*)
    into malformed_count
  from learning_plan lp
  where lp.roadmap ? 'ml_technical'
    and (
      jsonb_typeof(lp.roadmap->'ml_technical') is distinct from 'object'
      or jsonb_typeof(lp.roadmap->'ml_technical'->'sessions') is distinct from 'array'
      or jsonb_typeof(lp.roadmap->'ml_technical'->'attempts') is distinct from 'array'
      or jsonb_typeof(lp.roadmap->'ml_technical'->'external_reviews') is distinct from 'array'
      or exists (
        select 1
        from jsonb_array_elements(
          case
            when jsonb_typeof(lp.roadmap->'ml_technical'->'sessions') = 'array'
              then lp.roadmap->'ml_technical'->'sessions'
            else '[]'::jsonb
          end
        ) s(elem)
        where jsonb_typeof(s.elem) is distinct from 'object'
          or jsonb_typeof(s.elem->'question_ids') is distinct from 'array'
          or jsonb_array_length(s.elem->'question_ids') = 0
          or nullif(s.elem->>'session_id', '') is null
          or (s.elem->>'session_id') !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
          or nullif(s.elem->>'topic_id', '') is null
          or nullif(s.elem->>'created_at', '') is null
          or exists (
            select 1
            from jsonb_array_elements(s.elem->'question_ids') q(elem)
            where jsonb_typeof(q.elem) is distinct from 'string'
              or nullif(q.elem #>> '{}', '') is null
          )
      )
      or exists (
        select 1
        from jsonb_array_elements(
          case
            when jsonb_typeof(lp.roadmap->'ml_technical'->'attempts') = 'array'
              then lp.roadmap->'ml_technical'->'attempts'
            else '[]'::jsonb
          end
        ) a(elem)
        where jsonb_typeof(a.elem) is distinct from 'object'
          or nullif(a.elem->>'attempt_id', '') is null
          or (a.elem->>'attempt_id') !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
          or nullif(a.elem->>'session_id', '') is null
          or (a.elem->>'session_id') !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
          or nullif(a.elem->>'question_id', '') is null
          or nullif(a.elem->>'topic_id', '') is null
          or nullif(a.elem->>'answered_at', '') is null
          or not (a.elem ? 'raw_answer')
          or jsonb_typeof(a.elem->'review') is distinct from 'object'
      )
      or exists (
        select 1
        from jsonb_array_elements(
          case
            when jsonb_typeof(lp.roadmap->'ml_technical'->'external_reviews') = 'array'
              then lp.roadmap->'ml_technical'->'external_reviews'
            else '[]'::jsonb
          end
        ) e(elem)
        where jsonb_typeof(e.elem) is distinct from 'object'
          or nullif(e.elem->>'review_id', '') is null
          or (e.elem->>'review_id') !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
          or nullif(e.elem->>'attempt_id', '') is null
          or (e.elem->>'attempt_id') !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
          or nullif(e.elem->>'reviewer', '') is null
          or nullif(e.elem->>'verdict', '') is null
          or nullif(e.elem->>'created_at', '') is null
      )
    );

  if malformed_count > 0 then
    raise exception 'Malformed roadmap.ml_technical JSONB in % learning_plan row(s)', malformed_count
      using errcode = '22023';
  end if;
end $$;

create table if not exists ml_technical_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  mode text not null,
  channel text not null,
  topic_id text,
  session_seed text,
  practice_date date,
  status text not null,
  created_at timestamptz not null,
  closed_at timestamptz,
  unique (id, user_id),
  constraint ml_technical_sessions_mode_check check (mode in ('topic', 'daily')),
  constraint ml_technical_sessions_channel_check check (channel in ('web', 'telegram', 'mcp')),
  constraint ml_technical_sessions_status_check check (status in ('active', 'completed', 'cancelled')),
  constraint ml_technical_sessions_mode_shape_check check (
    (mode = 'daily' and practice_date is not null and topic_id is null)
    or (mode = 'topic' and practice_date is null and topic_id is not null)
  )
);

create unique index if not exists ml_technical_sessions_user_daily_key
  on ml_technical_sessions (user_id, practice_date)
  where mode = 'daily';
create index if not exists ml_technical_sessions_user_created_idx
  on ml_technical_sessions (user_id, created_at desc);

create table if not exists ml_technical_session_items (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null,
  session_id uuid not null,
  question_id text not null,
  position integer not null,
  status text not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  constraint ml_technical_session_items_session_user_fkey
    foreign key (session_id, user_id)
    references ml_technical_sessions(id, user_id)
    on delete cascade,
  constraint ml_technical_session_items_session_question_key unique (session_id, question_id),
  constraint ml_technical_session_items_session_position_key unique (session_id, position),
  constraint ml_technical_session_items_position_check check (position > 0),
  constraint ml_technical_session_items_status_check check (status in ('pending', 'answered', 'skipped'))
);

create index if not exists ml_technical_session_items_user_updated_idx
  on ml_technical_session_items (user_id, updated_at desc);
create index if not exists ml_technical_session_items_session_status_idx
  on ml_technical_session_items (session_id, status);

create table if not exists ml_technical_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null,
  session_id uuid not null,
  question_id text not null,
  topic_id text not null,
  answer_kind text not null,
  answer_language text not null,
  raw_answer text not null,
  source_channel text not null,
  source_event_id text,
  answered_at timestamptz not null,
  provenance_id text,
  review jsonb not null,
  unique (id, user_id),
  constraint ml_technical_attempts_session_user_fkey
    foreign key (session_id, user_id)
    references ml_technical_sessions(id, user_id)
    on delete cascade,
  constraint ml_technical_attempts_session_question_key unique (session_id, question_id),
  constraint ml_technical_attempts_answer_kind_check check (answer_kind in ('normal', 'dont_know')),
  constraint ml_technical_attempts_source_channel_check check (source_channel in ('web', 'telegram', 'mcp'))
);

create unique index if not exists ml_technical_attempts_source_event_key
  on ml_technical_attempts (source_channel, source_event_id)
  where source_event_id is not null;
create index if not exists ml_technical_attempts_user_answered_idx
  on ml_technical_attempts (user_id, answered_at desc);
create index if not exists ml_technical_attempts_question_idx
  on ml_technical_attempts (question_id);

create table if not exists ml_technical_external_reviews (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null,
  attempt_id uuid not null,
  reviewer text not null,
  verdict text not null,
  notes text,
  created_at timestamptz not null,
  constraint ml_technical_external_reviews_attempt_user_fkey
    foreign key (attempt_id, user_id)
    references ml_technical_attempts(id, user_id)
    on delete cascade
);

create index if not exists ml_technical_external_reviews_user_created_idx
  on ml_technical_external_reviews (user_id, created_at desc);
create index if not exists ml_technical_external_reviews_attempt_idx
  on ml_technical_external_reviews (attempt_id);

alter table ml_technical_sessions enable row level security;
do $$ begin
  create policy ml_technical_sessions_isolation on ml_technical_sessions
    using (user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1));
exception
  when duplicate_object then null;
end $$;

alter table ml_technical_session_items enable row level security;
do $$ begin
  create policy ml_technical_session_items_isolation on ml_technical_session_items
    using (user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1));
exception
  when duplicate_object then null;
end $$;

alter table ml_technical_attempts enable row level security;
do $$ begin
  create policy ml_technical_attempts_isolation on ml_technical_attempts
    using (user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1));
exception
  when duplicate_object then null;
end $$;

alter table ml_technical_external_reviews enable row level security;
do $$ begin
  create policy ml_technical_external_reviews_isolation on ml_technical_external_reviews
    using (user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1));
exception
  when duplicate_object then null;
end $$;

with source_sessions as (
  select
    lp.user_id,
    s.elem,
    s.ordinality
  from learning_plan lp
  cross join lateral jsonb_array_elements(lp.roadmap->'ml_technical'->'sessions') with ordinality as s(elem, ordinality)
  where lp.roadmap ? 'ml_technical'
)
insert into ml_technical_sessions (
  id, user_id, mode, channel, topic_id, session_seed, practice_date, status, created_at, closed_at
)
select
  (ss.elem->>'session_id')::uuid,
  ss.user_id,
  'topic',
  coalesce(nullif(ss.elem->>'channel', ''), 'web'),
  ss.elem->>'topic_id',
  ss.elem->>'session_seed',
  null::date,
  'active',
  (ss.elem->>'created_at')::timestamptz,
  null::timestamptz
from source_sessions ss
on conflict (id) do nothing;

with source_sessions as (
  select
    lp.user_id,
    s.elem as session_elem
  from learning_plan lp
  cross join lateral jsonb_array_elements(lp.roadmap->'ml_technical'->'sessions') as s(elem)
  where lp.roadmap ? 'ml_technical'
),
source_items as (
  select
    ss.user_id,
    (ss.session_elem->>'session_id')::uuid as session_id,
    q.question_id,
    q.position,
    (ss.session_elem->>'created_at')::timestamptz as created_at
  from source_sessions ss
  cross join lateral jsonb_array_elements_text(ss.session_elem->'question_ids') with ordinality as q(question_id, position)
)
insert into ml_technical_session_items (
  id, user_id, session_id, question_id, position, status, created_at, updated_at
)
select
  (
    substr(md5(si.session_id::text || ':' || si.question_id), 1, 8) || '-' ||
    substr(md5(si.session_id::text || ':' || si.question_id), 9, 4) || '-' ||
    substr(md5(si.session_id::text || ':' || si.question_id), 13, 4) || '-' ||
    substr(md5(si.session_id::text || ':' || si.question_id), 17, 4) || '-' ||
    substr(md5(si.session_id::text || ':' || si.question_id), 21, 12)
  )::uuid,
  si.user_id,
  si.session_id,
  si.question_id,
  si.position::integer,
  'pending',
  si.created_at,
  si.created_at
from source_items si
on conflict on constraint ml_technical_session_items_session_question_key do nothing;

with source_attempts as (
  select
    lp.user_id,
    a.elem
  from learning_plan lp
  cross join lateral jsonb_array_elements(lp.roadmap->'ml_technical'->'attempts') as a(elem)
  where lp.roadmap ? 'ml_technical'
)
insert into ml_technical_attempts (
  id, user_id, session_id, question_id, topic_id, answer_kind, answer_language,
  raw_answer, source_channel, source_event_id, answered_at, provenance_id, review
)
select
  (elem->>'attempt_id')::uuid,
  user_id,
  (elem->>'session_id')::uuid,
  elem->>'question_id',
  elem->>'topic_id',
  coalesce(nullif(elem->>'answer_kind', ''), 'normal'),
  coalesce(nullif(elem->>'answer_language', ''), 'ru_knowledge'),
  coalesce(elem->>'raw_answer', ''),
  coalesce(nullif(elem->>'source_channel', ''), 'web'),
  nullif(elem->>'source_event_id', ''),
  (elem->>'answered_at')::timestamptz,
  elem->>'provenance_id',
  elem->'review'
from source_attempts
on conflict on constraint ml_technical_attempts_session_question_key do nothing;

update ml_technical_session_items item
set
  status = 'answered',
  updated_at = attempt.answered_at
from ml_technical_attempts attempt
where attempt.user_id = item.user_id
  and attempt.session_id = item.session_id
  and attempt.question_id = item.question_id
  and (
    item.status is distinct from 'answered'
    or item.updated_at is distinct from attempt.answered_at
  );

with source_session_ids as (
  select
    lp.user_id,
    (s.elem->>'session_id')::uuid as session_id
  from learning_plan lp
  cross join lateral jsonb_array_elements(lp.roadmap->'ml_technical'->'sessions') as s(elem)
  where lp.roadmap ? 'ml_technical'
),
completion as (
  select
    source.user_id,
    source.session_id,
    exists (
      select 1
      from ml_technical_session_items item
      where item.user_id = source.user_id
        and item.session_id = source.session_id
    )
    and not exists (
      select 1
      from ml_technical_session_items item
      where item.user_id = source.user_id
        and item.session_id = source.session_id
        and item.status = 'pending'
    ) as is_complete,
    (
      select max(attempt.answered_at)
      from ml_technical_attempts attempt
      where attempt.user_id = source.user_id
        and attempt.session_id = source.session_id
    ) as last_answered_at
  from source_session_ids source
)
update ml_technical_sessions session
set
  status = case when completion.is_complete then 'completed' else 'active' end,
  closed_at = case when completion.is_complete then completion.last_answered_at else null end
from completion
where session.user_id = completion.user_id
  and session.id = completion.session_id
  and (
    session.status is distinct from case when completion.is_complete then 'completed' else 'active' end
    or session.closed_at is distinct from case when completion.is_complete then completion.last_answered_at else null end
  );

with source_reviews as (
  select
    lp.user_id,
    e.elem
  from learning_plan lp
  cross join lateral jsonb_array_elements(lp.roadmap->'ml_technical'->'external_reviews') as e(elem)
  where lp.roadmap ? 'ml_technical'
)
insert into ml_technical_external_reviews (
  id, user_id, attempt_id, reviewer, verdict, notes, created_at
)
select
  (elem->>'review_id')::uuid,
  user_id,
  (elem->>'attempt_id')::uuid,
  elem->>'reviewer',
  elem->>'verdict',
  elem->>'notes',
  (elem->>'created_at')::timestamptz
from source_reviews
on conflict (id) do nothing;

commit;
