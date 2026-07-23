-- Career Inbox v0 (Slice A of career/CAREER_TELEGRAM_COCKPIT_SPEC.md): owner-curated
-- leads from manual paste, plus feedback events attached to an application. Schema is
-- also shaped to receive Slice B's deterministic telegram-digest import later, but this
-- migration wires no import path - only manual lead intake and feedback preview/confirm.
-- No auto-send, no scheduler, no cross-repo dependency. PostgreSQL remains canonical.

begin;

create table if not exists career_inbox_items (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  source varchar(40) not null,
  external_id varchar(200),
  content_hash varchar(64) not null,
  source_snapshot jsonb not null default '{}'::jsonb,
  company varchar(200),
  role_title varchar(200),
  location varchar(200),
  url text,
  route varchar(20),
  gates jsonb,
  questions_for_recruiter jsonb not null default '[]'::jsonb,
  owner_verdict varchar(20),
  owner_reason text,
  linked_application_id uuid,
  idempotency_key varchar(200),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  decided_at timestamptz,
  constraint career_inbox_items_id_user_id_key unique (id, user_id),
  constraint career_inbox_items_source_check check (
    source in (
      'telegram_digest', 'linkedin_inbound', 'headhunter_inbound',
      'telegram_inbound', 'manual'
    )
  ),
  constraint career_inbox_items_verdict_check check (
    owner_verdict is null
    or owner_verdict in ('ask', 'prepare', 'skip', 'false_positive', 'applied')
  ),
  constraint career_inbox_items_route_check check (
    route is null or route in ('apply_candidate', 'outreach')
  ),
  constraint career_inbox_items_applied_requires_link_check check (
    owner_verdict is distinct from 'applied' or linked_application_id is not null
  ),
  constraint career_inbox_items_company_len_check check (
    company is null or char_length(company) between 1 and 200
  ),
  constraint career_inbox_items_role_len_check check (
    role_title is null or char_length(role_title) between 1 and 200
  ),
  constraint career_inbox_items_location_len_check check (
    location is null or char_length(location) <= 200
  ),
  constraint career_inbox_items_url_len_check check (
    url is null or char_length(url) <= 500
  ),
  constraint career_inbox_items_content_hash_check check (
    content_hash ~ '^[0-9a-f]{64}$'
  ),
  constraint career_inbox_items_linked_application_fkey
    foreign key (linked_application_id, user_id)
    references career_applications(id, user_id) on delete set null
);

create index if not exists career_inbox_items_user_created_idx
  on career_inbox_items(user_id, created_at desc);
create unique index if not exists career_inbox_items_idempotency_key
  on career_inbox_items(user_id, idempotency_key)
  where idempotency_key is not null;

alter table career_inbox_items enable row level security;
do $$ begin
  create policy career_inbox_items_isolation on career_inbox_items
    using (
      user_id = coalesce(
        nullif(current_setting('app.user_id', true), '')::bigint,
        -1
      )
    );
exception
  when duplicate_object then null;
end $$;

create table if not exists career_feedback_events (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  application_id uuid,
  inbox_item_id uuid,
  category varchar(40) not null,
  raw_feedback text not null,
  evidence_quote text,
  next_action varchar(200),
  actor_type varchar(20) not null,
  actor_id varchar(160) not null,
  idempotency_key varchar(200),
  occurred_at timestamptz not null,
  constraint career_feedback_events_target_check check (
    application_id is not null or inbox_item_id is not null
  ),
  constraint career_feedback_events_category_check check (
    category in (
      'positive_next_step', 'role_scope_mismatch', 'legal_or_authorization',
      'language', 'compensation', 'technical_gap', 'seniority_or_management',
      'generic_rejection', 'process_delay', 'unknown'
    )
  ),
  constraint career_feedback_events_actor_type_check check (
    actor_type in ('owner', 'system')
  ),
  constraint career_feedback_events_actor_id_len_check check (
    char_length(actor_id) between 1 and 160
  ),
  constraint career_feedback_events_raw_feedback_len_check check (
    char_length(raw_feedback) between 1 and 4000
  ),
  constraint career_feedback_events_evidence_len_check check (
    evidence_quote is null or char_length(evidence_quote) <= 1000
  ),
  constraint career_feedback_events_next_action_len_check check (
    next_action is null or char_length(next_action) <= 200
  ),
  constraint career_feedback_events_app_user_fkey
    foreign key (application_id, user_id)
    references career_applications(id, user_id) on delete cascade,
  constraint career_feedback_events_inbox_user_fkey
    foreign key (inbox_item_id, user_id)
    references career_inbox_items(id, user_id) on delete cascade
);

create index if not exists career_feedback_events_app_occurred_idx
  on career_feedback_events(application_id, occurred_at);
create index if not exists career_feedback_events_user_occurred_idx
  on career_feedback_events(user_id, occurred_at desc);
create unique index if not exists career_feedback_events_idempotency_key
  on career_feedback_events(user_id, idempotency_key)
  where idempotency_key is not null;

alter table career_feedback_events enable row level security;
do $$ begin
  create policy career_feedback_events_isolation on career_feedback_events
    using (
      user_id = coalesce(
        nullif(current_setting('app.user_id', true), '')::bigint,
        -1
      )
    );
exception
  when duplicate_object then null;
end $$;

create or replace function career_feedback_event_append_only_guard()
returns trigger language plpgsql as $$
begin
  raise exception 'career_feedback_events are append-only' using errcode = '55000';
end $$;

drop trigger if exists career_feedback_event_append_only_guard_trigger
  on career_feedback_events;
create trigger career_feedback_event_append_only_guard_trigger
before update or delete on career_feedback_events
for each row execute function career_feedback_event_append_only_guard();

-- Widen the existing single-row pending-intent table (017) with two more
-- multi-turn owner flows and an ephemeral draft payload (the LLM suggestion
-- pending owner confirm/cancel). Nothing here changes canonical inbox/feedback
-- state - only the pending intent row itself, same TTL/expiry contract as before.
alter table career_telegram_pending_inputs
  add column if not exists payload jsonb;

alter table career_telegram_pending_inputs
  drop constraint if exists career_telegram_pending_inputs_intent_check;
alter table career_telegram_pending_inputs
  add constraint career_telegram_pending_inputs_intent_check check (
    intent in (
      'career_add', 'career_next_action', 'career_manual_lead', 'career_feedback'
    )
  );

alter table career_telegram_pending_inputs
  drop constraint if exists career_telegram_pending_inputs_application_scope_check;
alter table career_telegram_pending_inputs
  add constraint career_telegram_pending_inputs_application_scope_check check (
    (
      intent in ('career_next_action', 'career_feedback')
      and application_id is not null
    ) or (
      intent in ('career_add', 'career_manual_lead')
      and application_id is null
    )
  );

commit;
