-- Career Cover Letter Draft v0 (career/CAREER_COVER_LETTER_DRAFT_SPEC.md, Slice 1).
-- LLM is an untrusted drafter: body text is owner-reviewed, never auto-sent. Draft
-- versions are immutable snapshots (a "regenerate" adds a new version row, never
-- edits an existing one); only `status` transitions in place, one-way, from
-- 'draft' to 'owner_approved' or 'rejected'. `owner_approved` never creates an
-- application or sends anything - that remains the existing cockpit confirm_applied
-- path. Not applied to the live DB by this migration file alone.

begin;

create table if not exists career_cover_letter_drafts (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  inbox_item_id uuid not null,
  version integer not null,
  body text not null,
  grounding_report jsonb not null default '{}'::jsonb,
  status varchar(20) not null default 'draft',
  actor_type varchar(20) not null,
  actor_id varchar(160) not null,
  idempotency_key varchar(200),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  constraint career_cover_letter_drafts_id_user_id_key unique (id, user_id),
  constraint career_cover_letter_drafts_inbox_user_fkey
    foreign key (inbox_item_id, user_id)
    references career_inbox_items(id, user_id) on delete cascade,
  constraint career_cover_letter_drafts_status_check check (
    status in ('draft', 'owner_approved', 'rejected')
  ),
  constraint career_cover_letter_drafts_actor_type_check check (
    actor_type in ('owner', 'system')
  ),
  constraint career_cover_letter_drafts_actor_id_len_check check (
    char_length(actor_id) between 1 and 160
  ),
  constraint career_cover_letter_drafts_version_positive_check check (version >= 1),
  constraint career_cover_letter_drafts_body_len_check check (
    char_length(body) between 1 and 8000
  ),
  constraint career_cover_letter_drafts_version_unique
    unique (inbox_item_id, version)
);

create index if not exists career_cover_letter_drafts_user_created_idx
  on career_cover_letter_drafts(user_id, created_at desc);
create index if not exists career_cover_letter_drafts_inbox_item_idx
  on career_cover_letter_drafts(inbox_item_id, version desc);
create unique index if not exists career_cover_letter_drafts_idempotency_key
  on career_cover_letter_drafts(user_id, idempotency_key)
  where idempotency_key is not null;

alter table career_cover_letter_drafts enable row level security;
do $$ begin
  create policy career_cover_letter_drafts_isolation on career_cover_letter_drafts
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
