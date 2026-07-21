-- Telegram v0 constraints for the canonical ML technical practice tables.

begin;

do $$
declare
  duplicate_user bigint;
begin
  select user_id
    into duplicate_user
  from ml_technical_sessions
  where channel = 'telegram'
    and status = 'active'
  group by user_id
  having count(*) > 1
  limit 1;

  if duplicate_user is not null then
    raise exception 'More than one active Telegram ML session for user %', duplicate_user
      using errcode = '23505';
  end if;
end $$;

create unique index if not exists ml_technical_sessions_one_active_telegram_key
  on ml_technical_sessions (user_id)
  where channel = 'telegram' and status = 'active';

create index if not exists ml_technical_session_items_pending_position_idx
  on ml_technical_session_items (user_id, session_id, position)
  where status = 'pending';

commit;
