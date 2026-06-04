-- pgTAP suite for memories, learning_plan, and xp_events.
begin;

select plan(24);

select has_table('public', 'memories', 'memories table exists');
select has_index('public', 'memories', 'memories_user_kind_idx', 'memories user/kind index exists');
select has_index('public', 'memories', 'mem_meta_gin', 'memories meta gin index exists');

select lives_ok(
  $$insert into users (username) values ('memories_test_user')$$,
  'insert user for memories tests'
);

select lives_ok(
  $$insert into memories (user_id, kind, content, meta)
  values (currval('users_id_seq'), 'episodic', 'First memory', '{"source_session":"00000000-0000-0000-0000-000000000000"}')$$,
  'insert memory for trigger test'
);

select lives_ok(
  $$insert into memories (user_id, kind, content)
  values (currval('users_id_seq'), 'fact', 'Learner is preparing for remote ML roles')$$,
  'insert fact memory succeeds'
);

select lives_ok(
  $$insert into memories (user_id, kind, content)
  values (currval('users_id_seq'), 'preference', 'Learner prefers short guided drills')$$,
  'insert preference memory succeeds'
);

select lives_ok(
  $$insert into memories (user_id, kind, content)
  values (currval('users_id_seq'), 'experience', 'Learner built a recommendation project')$$,
  'insert experience memory succeeds'
);

select lives_ok(
  $$insert into memories (user_id, kind, content)
  values (currval('users_id_seq'), 'goal', 'Learner wants a remote hard-currency role')$$,
  'insert goal memory succeeds'
);

select lives_ok(
  $$insert into memories (user_id, kind, content)
  values (currval('users_id_seq'), 'error_pattern', 'Learner omits articles before nouns')$$,
  'insert error_pattern memory succeeds'
);

select lives_ok(
  $$update memories set content = 'Updated memory' where user_id = currval('users_id_seq')$$,
  'update memory triggers last_refreshed update'
);

select lives_ok(
  $$insert into learning_plan (user_id, level_target, roadmap) values (currval('users_id_seq'), 'B2', '{"units":3}'::jsonb)$$,
  'insert learning plan succeeds'
);

select throws_ok(
  $$insert into learning_plan (user_id, level_target) values (currval('users_id_seq'), 'C1')$$,
  '23505',
  'duplicate key value violates unique constraint "learning_plan_user_idx"'
);

select has_table('public', 'xp_events', 'xp_events table exists');
select results_eq(
  $$select partstrat::text from pg_partitioned_table where partrelid = 'xp_events'::regclass$$,
  $$values ('r')$$,
  'xp_events uses range partitioning'
);
select has_table('public', 'xp_events_2025_10', 'xp_events sample partition exists');
select has_index('public', 'xp_events_2025_10', 'xp_events_2025_10_user_idx', 'xp_events partition index exists');

select lives_ok(
  $$insert into xp_events (user_id, kind, points, happened_at)
    values (currval('users_id_seq'), 'session_complete', 15, '2025-10-15 10:00:00+00')$$,
  'xp event inserted into sample partition'
);

-- RLS smoke check using application GUC with regular user
create user test_rls_user_memories;
grant usage on schema public to test_rls_user_memories;
grant select, insert, update, delete on all tables in schema public to test_rls_user_memories;
grant usage, select on all sequences in schema public to test_rls_user_memories;

select set_config('app.user_id', currval('users_id_seq')::text, true);
set role test_rls_user_memories;
select results_eq($$select count(*) from memories$$, $$values (6::bigint)$$, 'RLS exposes memories for current user');
select results_eq($$select count(*) from learning_plan$$, $$values (1::bigint)$$, 'RLS exposes learning_plan for current user');
select results_eq($$select count(*) from xp_events$$, $$values (1::bigint)$$, 'RLS exposes xp_events for current user');
set role postgres;

select set_config('app.user_id', '0', true);
set role test_rls_user_memories;
select results_eq($$select count(*) from memories$$, $$values (0::bigint)$$, 'RLS hides memories for other user');
select results_eq($$select count(*) from learning_plan$$, $$values (0::bigint)$$, 'RLS hides learning_plan for other user');
select results_eq($$select count(*) from xp_events$$, $$values (0::bigint)$$, 'RLS hides xp_events for other user');
set role postgres;

select set_config('app.user_id', '', true);

select * from finish();

rollback;
