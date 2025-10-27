-- pgTAP suite for mv_weekly_user_summary materialized view.
begin;

select plan(4);

select results_eq(
  $$select count(*) from pg_matviews where matviewname = 'mv_weekly_user_summary'$$,
  $$values (1::bigint)$$,
  'mv_weekly_user_summary exists'
);

select has_index('public', 'mv_weekly_user_summary', 'mv_weekly_user_summary_uidx', 'mv weekly unique index exists');

create temporary table tmp_mv_user (user_id bigint primary key);
insert into users (username) values ('mv_user_test');
insert into tmp_mv_user (user_id)
select id from users where username = 'mv_user_test';

create temporary table tmp_mv_session (session_id uuid primary key, user_id bigint);
insert into sessions (id, user_id, started_at)
select gen_random_uuid(), user_id, now()
from tmp_mv_user;
insert into tmp_mv_session (session_id, user_id)
select id, user_id from sessions where user_id in (select user_id from tmp_mv_user);

insert into feedback (session_id, overall_grammar, overall_pronunciation, summary_md)
select session_id, 0.8, 0.9, 'Good job'
from tmp_mv_session;

select lives_ok(
  'refresh materialized view concurrently mv_weekly_user_summary',
  'refresh mv_weekly_user_summary concurrently'
);

select results_eq(
  $$select sessions_cnt from mv_weekly_user_summary where user_id = (select user_id from tmp_mv_user)$$,
  $$values (1::bigint)$$,
  'mv_weekly_user_summary stores weekly aggregates'
);

select * from finish();

rollback;
