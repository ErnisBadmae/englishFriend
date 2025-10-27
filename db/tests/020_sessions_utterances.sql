-- Requires pgTAP installed. Verifies partitioning, indexes, and RLS for sessions/utterances.
begin;

select plan(12);

select has_table('public', 'sessions', 'sessions table exists');
select has_table('public', 'sessions_2025_10', 'sample monthly partition exists');

select results_eq(
  $$select partstrat::text from pg_partitioned_table where partrelid = 'sessions'::regclass$$,
  $$values ('r')$$,
  'sessions use range partitioning'
);

select has_index('public', 'sessions', 'sessions_user_started_idx', 'sessions user/start index exists');

select has_table('public', 'utterances', 'utterances table exists');

select results_eq(
  $$select count(*) from pg_inherits where inhparent = 'utterances'::regclass$$,
  $$values (8::bigint)$$,
  'eight utterances partitions exist'
);

select has_index('public', 'utterances_p0', 'utterances_p0_session_idx', 'utterances_p0 session index exists');
select has_index('public', 'utterances_p0', 'utterances_p0_topics_gin_idx', 'utterances_p0 topics gin index exists');

create temporary table tmp_test_users (id bigint primary key);
insert into users (username)
values ('sessions_rls_user1'), ('sessions_rls_user2');
insert into tmp_test_users (id)
select id from users where username in ('sessions_rls_user1', 'sessions_rls_user2');

create temporary table tmp_test_sessions (id uuid, user_id bigint);

with src as (
  select id,
         row_number() over (order by id) - 1 as rn
  from tmp_test_users
),
ins as (
  insert into sessions (id, user_id, started_at)
  select gen_random_uuid(), id, timestamp '2025-10-15 12:00:00+00' + (rn * interval '1 hour')
  from src
  returning id, user_id
)
insert into tmp_test_sessions (id, user_id)
select id, user_id from ins;

insert into utterances (session_id, speaker, t_start_ms, t_end_ms, text, topics)
select id, 'user', 0, 1000, 'hello world', '[]'::jsonb
from tmp_test_sessions;

-- Test RLS by creating a regular user (RLS doesn't apply to superuser postgres)
create user test_rls_user;
grant usage on schema public to test_rls_user;
grant select, insert, update, delete on all tables in schema public to test_rls_user;
grant usage, select on all sequences in schema public to test_rls_user;

-- Test RLS with regular user
select set_config('app.user_id', (select id::text from tmp_test_users order by id limit 1), true);
set role test_rls_user;
select results_eq($$select count(*) from sessions$$, $$values (1::bigint)$$, 'RLS limits sessions to first user');
select results_eq($$select count(*) from utterances$$, $$values (1::bigint)$$, 'RLS limits utterances to first user');
set role postgres;

select set_config('app.user_id', (select id::text from tmp_test_users order by id desc limit 1), true);
set role test_rls_user;
select results_eq($$select count(*) from sessions$$, $$values (1::bigint)$$, 'RLS limits sessions to second user');
select results_eq($$select count(*) from utterances$$, $$values (1::bigint)$$, 'RLS limits utterances to second user');
set role postgres;

select set_config('app.user_id', '', true);

select * from finish();

rollback;
