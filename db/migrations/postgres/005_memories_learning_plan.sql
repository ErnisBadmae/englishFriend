-- 005_memories_learning_plan.sql
-- Purpose: memory storage, learning plan, and xp events with partitioning.

begin;

create table if not exists memories (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  kind memory_kind not null,
  content text not null,
  meta jsonb,
  salience real not null default 0.5 check (salience between 0 and 1),
  last_refreshed timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists memories_user_kind_idx on memories (user_id, kind);
create index if not exists mem_meta_gin on memories using gin (meta jsonb_path_ops);

create or replace function trg_memories_touch_last_refreshed()
returns trigger
language plpgsql
as $$
begin
  new.last_refreshed := now();
  return new;
end;
$$;

drop trigger if exists memories_touch_last_refreshed on memories;
create trigger memories_touch_last_refreshed
before update on memories
for each row
execute function trg_memories_touch_last_refreshed();

-- Optional pgvector column when extension is available.
do $$
begin
  if exists (select 1 from pg_extension where extname = 'vector') then
    begin
      alter table memories add column if not exists embedding vector(1536);
      create index if not exists mem_vec_idx on memories using ivfflat (embedding vector_cosine) with (lists = 200);
    exception when others then
      raise notice 'Vector column/index already configured: %', sqlerrm;
    end;
  end if;
end;
$$;

alter table memories enable row level security;
do $$ begin
  create policy memories_isolation on memories
    using (user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1));
exception
  when duplicate_object then null;
end $$;

create table if not exists learning_plan (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  level_target cefr_level,
  next_review_at timestamptz,
  roadmap jsonb,
  updated_at timestamptz not null default now()
);
create unique index if not exists learning_plan_user_idx on learning_plan (user_id);

alter table learning_plan enable row level security;
do $$ begin
  create policy learning_plan_isolation on learning_plan
    using (user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1));
exception
  when duplicate_object then null;
end $$;

create table if not exists xp_events (
  id uuid default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  session_id uuid,
  kind text,
  points int not null,
  happened_at timestamptz not null default now(),
  primary key (id, happened_at)
) partition by range (happened_at);

create table if not exists xp_events_2025_10
  partition of xp_events
  for values from ('2025-10-01') to ('2025-11-01');

create index if not exists xp_events_2025_10_user_idx
  on xp_events_2025_10 (user_id, happened_at desc);

alter table xp_events enable row level security;
do $$ begin
  create policy xp_events_isolation on xp_events
    using (user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1));
exception
  when duplicate_object then null;
end $$;

commit;
