-- pgTAP suite for ml_technical durable practice evidence.
begin;

select plan(35);

select has_table('public', 'ml_technical_sessions', 'ml_technical_sessions table exists');
select has_table('public', 'ml_technical_session_items', 'ml_technical_session_items table exists');
select has_table('public', 'ml_technical_attempts', 'ml_technical_attempts table exists');
select has_table('public', 'ml_technical_external_reviews', 'ml_technical_external_reviews table exists');

select has_index('public', 'ml_technical_sessions', 'ml_technical_sessions_user_daily_key', 'daily unique index exists');
select has_index('public', 'ml_technical_attempts', 'ml_technical_attempts_source_event_key', 'source event unique index exists');
select has_index('public', 'ml_technical_session_items', 'ml_technical_session_items_session_status_idx', 'session item status index exists');
select has_index('public', 'ml_technical_external_reviews', 'ml_technical_external_reviews_user_created_idx', 'external review user/time index exists');

select col_is_pk('public', 'ml_technical_sessions', 'id', 'sessions id primary key');
select col_is_pk('public', 'ml_technical_session_items', 'id', 'session items id primary key');
select col_is_pk('public', 'ml_technical_attempts', 'id', 'attempts id primary key');
select col_is_pk('public', 'ml_technical_external_reviews', 'id', 'external reviews id primary key');

select fk_ok('public', 'ml_technical_sessions', 'user_id', 'public', 'users', 'id', 'sessions owned by users');
select has_fk('public', 'ml_technical_session_items', 'session items have composite owner fk');
select has_fk('public', 'ml_technical_attempts', 'attempts have composite owner fk');
select has_fk('public', 'ml_technical_external_reviews', 'external reviews have composite owner fk');

select lives_ok(
  $$insert into users (username) values ('ml_technical_pgtap_user')$$,
  'insert ml technical test user'
);

select lives_ok(
  $$insert into ml_technical_sessions (id, user_id, mode, channel, topic_id, status, created_at)
    values ('00000000-0000-0000-0000-000000000601', currval('users_id_seq'), 'topic', 'web', 'dl_training', 'active', now())$$,
  'insert topic session succeeds'
);

select throws_ok(
  $$insert into ml_technical_sessions (id, user_id, mode, channel, topic_id, practice_date, status, created_at)
    values ('00000000-0000-0000-0000-000000000602', currval('users_id_seq'), 'daily', 'web', 'dl_training', current_date, 'active', now())$$,
  '23514',
  null,
  'daily session rejects topic_id'
);

select lives_ok(
  $$insert into ml_technical_sessions (id, user_id, mode, channel, practice_date, status, created_at)
    values ('00000000-0000-0000-0000-000000000603', currval('users_id_seq'), 'daily', 'telegram', current_date, 'active', now())$$,
  'insert daily session succeeds'
);

select throws_ok(
  $$insert into ml_technical_sessions (id, user_id, mode, channel, practice_date, status, created_at)
    values ('00000000-0000-0000-0000-000000000604', currval('users_id_seq'), 'daily', 'telegram', current_date, 'active', now())$$,
  '23505',
  null,
  'daily session is unique per user/date'
);

select lives_ok(
  $$insert into ml_technical_session_items (id, user_id, session_id, question_id, position, status, created_at, updated_at)
    values ('00000000-0000-0000-0000-000000000611', currval('users_id_seq'), '00000000-0000-0000-0000-000000000601', 'mltech_001', 1, 'pending', now(), now())$$,
  'insert session item succeeds'
);

select throws_ok(
  $$insert into ml_technical_session_items (id, user_id, session_id, question_id, position, status, created_at, updated_at)
    values ('00000000-0000-0000-0000-000000000612', currval('users_id_seq'), '00000000-0000-0000-0000-000000000601', 'mltech_001', 2, 'pending', now(), now())$$,
  '23505',
  null,
  'duplicate session/question item rejected'
);

select lives_ok(
  $$insert into ml_technical_attempts (id, user_id, session_id, question_id, topic_id, answer_kind, answer_language, raw_answer, source_channel, source_event_id, answered_at, review)
    values ('00000000-0000-0000-0000-000000000621', currval('users_id_seq'), '00000000-0000-0000-0000-000000000601', 'mltech_001', 'dl_training', 'normal', 'ru_knowledge', 'answer', 'telegram', 'update-1', now(), '{"status":"graded","score_percent":80}'::jsonb)$$,
  'insert attempt succeeds'
);

select throws_ok(
  $$insert into ml_technical_attempts (id, user_id, session_id, question_id, topic_id, answer_kind, answer_language, raw_answer, source_channel, answered_at, review)
    values ('00000000-0000-0000-0000-000000000622', currval('users_id_seq'), '00000000-0000-0000-0000-000000000601', 'mltech_001', 'dl_training', 'dont_know', 'ru_knowledge', '', 'web', now(), '{"status":"graded","score_percent":0}'::jsonb)$$,
  '23505',
  null,
  'duplicate attempt session/question rejected'
);

select throws_ok(
  $$insert into ml_technical_attempts (id, user_id, session_id, question_id, topic_id, answer_kind, answer_language, raw_answer, source_channel, source_event_id, answered_at, review)
    values ('00000000-0000-0000-0000-000000000623', currval('users_id_seq'), '00000000-0000-0000-0000-000000000601', 'mltech_002', 'dl_training', 'normal', 'ru_knowledge', 'answer', 'telegram', 'update-1', now(), '{"status":"graded","score_percent":70}'::jsonb)$$,
  '23505',
  null,
  'duplicate source event rejected'
);

select lives_ok(
  $$insert into ml_technical_external_reviews (id, user_id, attempt_id, reviewer, verdict, notes, created_at)
    values ('00000000-0000-0000-0000-000000000631', currval('users_id_seq'), '00000000-0000-0000-0000-000000000621', 'codex', 'agree', 'append only', now())$$,
  'append external review succeeds'
);

select lives_ok(
  $$insert into ml_technical_sessions (id, user_id, mode, channel, topic_id, status, created_at)
    values ('00000000-0000-0000-0000-000000000601', currval('users_id_seq'), 'topic', 'web', 'dl_training', 'active', now())
    on conflict (id) do nothing$$,
  'session backfill insert is idempotent'
);

select results_eq(
  $$select count(*) from ml_technical_sessions where id = '00000000-0000-0000-0000-000000000601'$$,
  $$values (1::bigint)$$,
  'idempotent insert creates no duplicate session'
);

create user test_rls_user_ml_technical;
grant usage on schema public to test_rls_user_ml_technical;
grant select, insert, update, delete on all tables in schema public to test_rls_user_ml_technical;
grant usage, select on all sequences in schema public to test_rls_user_ml_technical;

select set_config('app.user_id', currval('users_id_seq')::text, true);
set role test_rls_user_ml_technical;
select results_eq($$select count(*) from ml_technical_sessions$$, $$values (2::bigint)$$, 'RLS exposes sessions for current user');
select results_eq($$select count(*) from ml_technical_session_items$$, $$values (1::bigint)$$, 'RLS exposes session items for current user');
select results_eq($$select count(*) from ml_technical_attempts$$, $$values (1::bigint)$$, 'RLS exposes attempts for current user');
select results_eq($$select count(*) from ml_technical_external_reviews$$, $$values (1::bigint)$$, 'RLS exposes external reviews for current user');
set role postgres;

select set_config('app.user_id', '0', true);
set role test_rls_user_ml_technical;
select results_eq($$select count(*) from ml_technical_sessions$$, $$values (0::bigint)$$, 'RLS hides sessions for other user');
select results_eq($$select count(*) from ml_technical_attempts$$, $$values (0::bigint)$$, 'RLS hides attempts for other user');
set role postgres;

select set_config('app.user_id', '', true);

select * from finish();

rollback;
