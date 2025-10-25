-- 002_users.sql
-- Purpose: core user tables and interests.

begin;

create table if not exists users (
  id bigserial primary key,
  telegram_id bigint unique,
  username varchar(255),
  language_level cefr_level,
  primary_channel access_channel not null default 'telegram',
  accent_pref text references dim_accent(code),
  pii_envelope bytea,
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists user_channel_identity (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  channel access_channel not null,
  external_id text not null,
  auth_payload jsonb,
  linked_at timestamptz not null default now(),
  unique (channel, external_id),
  unique (user_id, channel)
);
create index if not exists user_channel_identity_uidx on user_channel_identity (user_id, channel);

create table if not exists user_interest (
  user_id bigint not null references users(id) on delete cascade,
  topic_id uuid not null references dim_topic(id) on delete cascade,
  weight real not null default 0 check (weight >= 0 and weight <= 1),
  last_mentioned timestamptz,
  primary key (user_id, topic_id)
);
create index if not exists user_interest_user_weight_idx on user_interest (user_id, weight desc);

commit;
