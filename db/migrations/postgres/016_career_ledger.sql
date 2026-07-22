-- Career execution ledger v0: owner-confirmed manual applications only.
-- No auto-apply, no letter/CV generation, no external send path. PostgreSQL
-- remains canonical; PERSONAL_STRATEGY.md stays a separate, read-only source.

begin;

create table if not exists career_vacancy_snapshots (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  source varchar(40) not null,
  external_id varchar(200),
  company varchar(200) not null,
  role_title varchar(200) not null,
  url text,
  raw_description text,
  content_hash varchar(64) not null,
  created_at timestamptz not null,
  constraint career_vacancy_snapshots_id_user_id_key unique (id, user_id),
  constraint career_vacancy_snapshots_idempotency_key
    unique (user_id, source, content_hash),
  constraint career_vacancy_snapshots_source_check check (
    source in ('telegram_manual', 'web_manual')
  ),
  constraint career_vacancy_snapshots_company_len_check check (
    char_length(company) between 1 and 200
  ),
  constraint career_vacancy_snapshots_role_len_check check (
    char_length(role_title) between 1 and 200
  ),
  constraint career_vacancy_snapshots_url_len_check check (
    url is null or char_length(url) <= 500
  ),
  constraint career_vacancy_snapshots_description_len_check check (
    raw_description is null or char_length(raw_description) <= 4000
  ),
  constraint career_vacancy_snapshots_content_hash_check check (
    content_hash ~ '^[0-9a-f]{64}$'
  )
);

create index if not exists career_vacancy_snapshots_user_created_idx
  on career_vacancy_snapshots(user_id, created_at desc);

alter table career_vacancy_snapshots enable row level security;
do $$ begin
  create policy career_vacancy_snapshots_isolation on career_vacancy_snapshots
    using (
      user_id = coalesce(
        nullif(current_setting('app.user_id', true), '')::bigint,
        -1
      )
    );
exception
  when duplicate_object then null;
end $$;

create or replace function career_vacancy_snapshot_append_only_guard()
returns trigger language plpgsql as $$
begin
  raise exception 'career_vacancy_snapshots are immutable' using errcode = '55000';
end $$;

drop trigger if exists career_vacancy_snapshot_append_only_guard_trigger
  on career_vacancy_snapshots;
create trigger career_vacancy_snapshot_append_only_guard_trigger
before update or delete on career_vacancy_snapshots
for each row execute function career_vacancy_snapshot_append_only_guard();

create table if not exists career_applications (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  vacancy_snapshot_id uuid not null,
  status varchar(20) not null default 'applied',
  applied_at timestamptz not null,
  resume_ref text,
  resume_hash varchar(64),
  cover_letter_ref text,
  cover_letter_hash varchar(64),
  next_action varchar(200),
  next_action_due_date date,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  constraint career_applications_id_user_id_key unique (id, user_id),
  constraint career_applications_snapshot_fkey
    foreign key (vacancy_snapshot_id, user_id)
    references career_vacancy_snapshots(id, user_id) on delete restrict,
  constraint career_applications_status_check check (
    status in (
      'applied', 'screening', 'technical', 'rejected', 'offer', 'withdrawn'
    )
  ),
  constraint career_applications_resume_hash_check check (
    resume_hash is null or resume_hash ~ '^[0-9a-f]{64}$'
  ),
  constraint career_applications_cover_letter_hash_check check (
    cover_letter_hash is null or cover_letter_hash ~ '^[0-9a-f]{64}$'
  ),
  constraint career_applications_next_action_len_check check (
    next_action is null or char_length(next_action) <= 200
  )
);

create unique index if not exists career_applications_one_active_key
  on career_applications(user_id, vacancy_snapshot_id)
  where status in ('applied', 'screening', 'technical');
create index if not exists career_applications_user_status_idx
  on career_applications(user_id, status);
create index if not exists career_applications_user_updated_idx
  on career_applications(user_id, updated_at desc);
create index if not exists career_applications_next_action_due_idx
  on career_applications(user_id, next_action_due_date)
  where next_action_due_date is not null;

alter table career_applications enable row level security;
do $$ begin
  create policy career_applications_isolation on career_applications
    using (
      user_id = coalesce(
        nullif(current_setting('app.user_id', true), '')::bigint,
        -1
      )
    );
exception
  when duplicate_object then null;
end $$;

create table if not exists career_application_events (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  application_id uuid not null,
  event_type varchar(30) not null,
  from_status varchar(20),
  to_status varchar(20),
  actor_type varchar(20) not null,
  actor_id varchar(160) not null,
  metadata jsonb not null default '{}'::jsonb,
  idempotency_key varchar(200),
  occurred_at timestamptz not null,
  constraint career_application_events_app_user_fkey
    foreign key (application_id, user_id)
    references career_applications(id, user_id) on delete cascade,
  constraint career_application_events_type_check check (
    event_type in ('created', 'status_changed', 'note')
  ),
  constraint career_application_events_actor_type_check check (
    actor_type in ('owner', 'system')
  ),
  constraint career_application_events_actor_id_len_check check (
    char_length(actor_id) between 1 and 160
  ),
  constraint career_application_events_metadata_object_check check (
    jsonb_typeof(metadata) = 'object'
  )
);

create unique index if not exists career_application_events_idempotency_key
  on career_application_events(user_id, idempotency_key)
  where idempotency_key is not null;
create index if not exists career_application_events_app_occurred_idx
  on career_application_events(application_id, occurred_at);
create index if not exists career_application_events_user_occurred_idx
  on career_application_events(user_id, occurred_at desc);

alter table career_application_events enable row level security;
do $$ begin
  create policy career_application_events_isolation on career_application_events
    using (
      user_id = coalesce(
        nullif(current_setting('app.user_id', true), '')::bigint,
        -1
      )
    );
exception
  when duplicate_object then null;
end $$;

create or replace function career_application_event_append_only_guard()
returns trigger language plpgsql as $$
begin
  raise exception 'career_application_events are append-only' using errcode = '55000';
end $$;

drop trigger if exists career_application_event_append_only_guard_trigger
  on career_application_events;
create trigger career_application_event_append_only_guard_trigger
before update or delete on career_application_events
for each row execute function career_application_event_append_only_guard();

commit;
