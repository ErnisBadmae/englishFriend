-- 001_reference_tables.sql
-- Purpose: enums and static reference tables.

begin;

do $$ begin
  create type cefr_level as enum ('A1','A2','B1','B2','C1','C2');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type memory_kind as enum ('episodic','semantic','persona','skill');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type access_channel as enum ('telegram','mobile_app','web');
exception
  when duplicate_object then null;
end $$;

create table if not exists dim_emotion (
  code text primary key,
  name_ru text not null,
  valence int not null check (valence between -5 and 5),
  arousal int not null check (arousal between 0 and 5),
  updated_at timestamptz not null default now()
);

create table if not exists dim_topic (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  display_name text not null,
  parent_id uuid references dim_topic(id) on delete set null,
  updated_at timestamptz not null default now()
);

create table if not exists dim_accent (
  code text primary key,
  display_name text not null,
  updated_at timestamptz not null default now()
);

commit;
