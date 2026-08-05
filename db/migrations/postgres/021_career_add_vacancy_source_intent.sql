-- Adds the "career_add_vacancy_source" pending-intent (owner adds a Telegram
-- vacancy source via the bot) to the existing single-row pending-intent
-- table's whitelist constraints (017/018). No new table, no new column -
-- this intent carries no application_id, same as career_add/career_manual_lead.

begin;

alter table career_telegram_pending_inputs
  drop constraint if exists career_telegram_pending_inputs_intent_check;
alter table career_telegram_pending_inputs
  add constraint career_telegram_pending_inputs_intent_check check (
    intent in (
      'career_add', 'career_next_action', 'career_manual_lead', 'career_feedback',
      'career_add_vacancy_source'
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
      intent in ('career_add', 'career_manual_lead', 'career_add_vacancy_source')
      and application_id is null
    )
  );

commit;
