-- Adds the "review" route to career_inbox_items' route whitelist (018).
--
-- Upstream (telegram-digest) used to treat an unresolved role_scope gate as a
-- rejection and delete the vacancy: 196 of 543 triaged posts were dropped that
-- way, 99 of which mentioned ML/AI/NLP work. role_scope was the only gate where
-- `unknown` meant reject - legal_hire_from_rf and language_path already routed
-- their unknowns to the owner. It now routes them to `review` instead, so those
-- cards import here and are surfaced in a second, lower-priority queue.
--
-- No new table, no new column, no data migration: existing rows keep their
-- route, the constraint only widens.

begin;

alter table career_inbox_items
  drop constraint if exists career_inbox_items_route_check;
alter table career_inbox_items
  add constraint career_inbox_items_route_check check (
    route is null or route in ('apply_candidate', 'outreach', 'review')
  );

commit;
