-- Career Telegram pending input v0.2.1: PostgreSQL-canonical pending intent
-- state, replacing the reply-metadata/marker design defect described in
-- !DOC/architecture/SONNET_CAREER_PENDING_INPUT_V021_TASK.md. Routing must
-- not depend on Telegram ForceReply/reply_to_message metadata; the owner's
-- active intent (if any) lives here instead of an in-memory FSM.

begin;

create table if not exists career_telegram_pending_inputs (
  user_id bigint primary key references users(id) on delete cascade,
  intent varchar(30) not null,
  application_id uuid,
  created_at timestamptz not null,
  expires_at timestamptz not null,
  constraint career_telegram_pending_inputs_intent_check check (
    intent in ('career_add', 'career_next_action')
  ),
  constraint career_telegram_pending_inputs_application_scope_check check (
    (intent = 'career_next_action' and application_id is not null) or
    (intent = 'career_add' and application_id is null)
  ),
  constraint career_telegram_pending_inputs_application_fkey
    foreign key (application_id, user_id)
    references career_applications(id, user_id) on delete cascade
);

create index if not exists career_telegram_pending_inputs_expires_idx
  on career_telegram_pending_inputs(expires_at);

alter table career_telegram_pending_inputs enable row level security;
do $$ begin
  create policy career_telegram_pending_inputs_isolation
    on career_telegram_pending_inputs
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
