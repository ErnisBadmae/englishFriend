-- Append-only senior analysis of bounded ML technical progress snapshots.
-- Attempts, scores, sessions and question lifecycle remain owned by their
-- existing tables; a progress review can only reference a canonical snapshot.

begin;

create table if not exists ml_progress_reviews (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null references users(id) on delete cascade,
  context_schema_version integer not null default 1,
  context_hash varchar(64) not null,
  context_snapshot jsonb not null,
  findings jsonb not null,
  recommendations jsonb not null,
  reviewer_type varchar(30) not null,
  reviewer_id varchar(160) not null,
  model_id varchar(160),
  prompt_version varchar(120) not null,
  created_at timestamptz not null,
  constraint ml_progress_reviews_id_user_id_key unique (id, user_id),
  constraint ml_progress_reviews_schema_version_check check (
    context_schema_version = 1
  ),
  constraint ml_progress_reviews_context_hash_check check (
    context_hash ~ '^[0-9a-f]{64}$'
  ),
  constraint ml_progress_reviews_context_object_check check (
    jsonb_typeof(context_snapshot) = 'object'
  ),
  constraint ml_progress_reviews_findings_array_check check (
    jsonb_typeof(findings) = 'array'
  ),
  constraint ml_progress_reviews_recommendations_array_check check (
    jsonb_typeof(recommendations) = 'array'
  ),
  constraint ml_progress_reviews_reviewer_type_check check (
    reviewer_type in ('model', 'human')
  ),
  constraint ml_progress_reviews_model_provenance_check check (
    reviewer_type <> 'model' or model_id is not null
  )
);

create index if not exists ml_progress_reviews_user_created_idx
  on ml_progress_reviews(user_id, created_at desc, id desc);
create index if not exists ml_progress_reviews_user_context_idx
  on ml_progress_reviews(user_id, context_hash);

alter table ml_progress_reviews enable row level security;
do $$ begin
  create policy ml_progress_reviews_isolation on ml_progress_reviews
    using (
      user_id = coalesce(
        nullif(current_setting('app.user_id', true), '')::bigint,
        -1
      )
    );
exception
  when duplicate_object then null;
end $$;

create or replace function ml_progress_review_append_only_guard()
returns trigger language plpgsql as $$
begin
  raise exception 'ml_progress_reviews are append-only' using errcode = '55000';
end $$;

drop trigger if exists ml_progress_review_append_only_guard_trigger
  on ml_progress_reviews;
create trigger ml_progress_review_append_only_guard_trigger
before update or delete on ml_progress_reviews
for each row execute function ml_progress_review_append_only_guard();

commit;
