-- Adds the "later" owner verdict to career_inbox_items (018).
--
-- "Interesting, but not yet": the owner wants the vacancy later, not now. Before
-- this the only ways out of the working queue were rejection (skip /
-- false_positive) or starting work (prepare), so a vacancy the owner was not
-- ready for either cluttered the queue or had to be thrown away.
--
-- `later` is deliberately NOT settled: the owner will come back to it, so a
-- re-import must not resurrect it (import_snapshot freezes any decided vacancy)
-- while list_inbox_items keeps it out of the working queue and serves it from
-- its own list instead.
--
-- Constraint only widens; no data migration.

begin;

alter table career_inbox_items
  drop constraint if exists career_inbox_items_verdict_check;
alter table career_inbox_items
  add constraint career_inbox_items_verdict_check check (
    owner_verdict is null
    or owner_verdict in ('ask', 'prepare', 'skip', 'false_positive', 'applied', 'later')
  );

commit;
