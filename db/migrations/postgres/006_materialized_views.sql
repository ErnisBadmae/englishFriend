-- 006_materialized_views.sql
-- Purpose: analytics materialized views.

begin;

create materialized view if not exists mv_weekly_user_summary as
select
  u.id as user_id,
  date_trunc('week', s.started_at) as week,
  count(distinct s.id) as sessions_cnt,
  avg(f.overall_grammar) as avg_grammar,
  avg(f.overall_pronunciation) as avg_pron
from users u
left join sessions s on s.user_id = u.id
left join feedback f on f.session_id = s.id
where s.started_at >= now() - interval '8 weeks'
group by 1,2;

create unique index if not exists mv_weekly_user_summary_uidx
  on mv_weekly_user_summary (user_id, week);

commit;
