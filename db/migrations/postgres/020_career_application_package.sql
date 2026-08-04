-- Career Application Package v0 (career/CAREER_OPERATING_SYSTEM_V1_SPEC.md, Slice D1a).
-- Immutable, content-hashed snapshot of one prepared application package: exact
-- inbox item version, final gates, owner-approved cover draft, CV variant and
-- facts_bank state at prepare time. `status` transitions once, one-way, from
-- 'ready' to 'submitted' or 'expired'. `submitted` only ever links to an
-- application/event created via the existing career_ledger write path - this
-- table never creates one itself and never sends anything externally.
-- Not applied to the live DB by this migration file alone.

begin;

create table if not exists career_application_packages (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  inbox_item_id uuid not null,
  inbox_item_content_hash varchar(64) not null,
  company varchar(200) not null,
  role_title varchar(200) not null,
  source_url text,
  gates_snapshot jsonb not null default '{}'::jsonb,
  gates_hash varchar(64) not null,
  questions_for_recruiter jsonb not null default '[]'::jsonb,
  policy_ref varchar(200) not null,
  cover_draft_id uuid not null,
  cover_version integer not null,
  cover_text_hash varchar(64) not null,
  used_fact_ids jsonb not null default '[]'::jsonb,
  facts_bank_hash varchar(64) not null,
  cv_variant_id varchar(80) not null,
  cv_content_hash varchar(64) not null,
  package_kind varchar(20) not null default 'application',
  package_content_hash varchar(64) not null,
  status varchar(20) not null default 'ready',
  actor_id varchar(160) not null,
  idempotency_key varchar(200),
  created_at timestamptz not null,
  ready_at timestamptz not null,
  submitted_at timestamptz,
  linked_application_id uuid,
  linked_event_id uuid,
  constraint career_application_packages_id_user_id_key unique (id, user_id),
  constraint career_application_packages_inbox_user_fkey
    foreign key (inbox_item_id, user_id)
    references career_inbox_items(id, user_id) on delete cascade,
  constraint career_application_packages_draft_user_fkey
    foreign key (cover_draft_id, user_id)
    references career_cover_letter_drafts(id, user_id) on delete cascade,
  constraint career_application_packages_application_user_fkey
    foreign key (linked_application_id, user_id)
    references career_applications(id, user_id) on delete set null,
  constraint career_application_packages_kind_check check (
    package_kind in ('application')
  ),
  constraint career_application_packages_status_check check (
    status in ('ready', 'submitted', 'expired')
  ),
  constraint career_application_packages_actor_id_len_check check (
    char_length(actor_id) between 1 and 160
  ),
  constraint career_application_packages_submitted_fields_check check (
    (status <> 'submitted')
    or (submitted_at is not null and linked_application_id is not null
        and linked_event_id is not null)
  ),
  constraint career_application_packages_content_hash_unique
    unique (user_id, inbox_item_id, package_content_hash)
);

create index if not exists career_application_packages_user_created_idx
  on career_application_packages(user_id, created_at desc);
create index if not exists career_application_packages_inbox_item_idx
  on career_application_packages(inbox_item_id, created_at desc);
create unique index if not exists career_application_packages_idempotency_key
  on career_application_packages(user_id, idempotency_key)
  where idempotency_key is not null;

alter table career_application_packages enable row level security;
do $$ begin
  create policy career_application_packages_isolation on career_application_packages
    using (
      user_id = coalesce(
        nullif(current_setting('app.user_id', true), '')::bigint,
        -1
      )
    );
exception
  when duplicate_object then null;
end $$;

commit;
