-- 003_sessions_utterances.sql
-- Purpose: conversational storage (sessions, utterances, feedback, corrections) with partitioning and RLS.

begin;

create table if not exists sessions (
  id uuid default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  started_at timestamptz not null,
  ended_at timestamptz,
  audio_url text,
  lang_code text not null default 'en',
  call_quality jsonb,
  constraint sessions_time_check check (ended_at is null or ended_at >= started_at),
  primary key (id, started_at)
) partition by range (started_at);

create index if not exists sessions_user_started_idx
  on sessions using btree (user_id, started_at desc);

create table if not exists sessions_2025_10
  partition of sessions
  for values from ('2025-10-01') to ('2025-11-01');

create table if not exists utterances (
  id uuid default gen_random_uuid(),
  session_id uuid not null,
  speaker text not null check (speaker in ('user','assistant')),
  t_start_ms int not null,
  t_end_ms int not null,
  text text not null,
  phonemes jsonb,
  topics jsonb,
  emotion_code text references dim_emotion(code),
  emotion_score real,
  grammar_score real,
  pronunciation_score real,
  constraint utterances_time_check check (t_end_ms >= t_start_ms),
  primary key (id, session_id)
) partition by hash (session_id);

do $$
declare
  mod_parts int := 8;
  i int;
begin
  for i in 0..mod_parts-1 loop
    execute format('create table if not exists utterances_p%s partition of utterances for values with (modulus %s, remainder %s);', i, mod_parts, i);
    execute format('create index if not exists utterances_p%s_session_idx on utterances_p%s (session_id, t_start_ms);', i, i);
    execute format('create index if not exists utterances_p%s_topics_gin_idx on utterances_p%s using gin (topics jsonb_path_ops);', i, i);
  end loop;
end $$;

create table if not exists feedback (
  session_id uuid primary key,
  overall_grammar real,
  overall_pronunciation real,
  summary_md text,
  tips_md text
);

create table if not exists corrections (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null,
  utterance_id uuid,
  user_text text not null,
  corrected_text text not null,
  rule_tag text,
  explanation_md text
);

create index if not exists corrections_session_idx on corrections (session_id);

-- RLS policies for conversational data
alter table sessions enable row level security;
do $$ begin
  create policy sessions_isolation on sessions
    using (user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1));
exception
  when duplicate_object then null;
end $$;

alter table utterances enable row level security;
do $$ begin
  create policy utterances_isolation on utterances
    using (
      exists (
        select 1
        from sessions s
        where s.id = utterances.session_id
          and s.user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1)
      )
    );
exception
  when duplicate_object then null;
end $$;

commit;
