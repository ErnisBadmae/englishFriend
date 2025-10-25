-- 001_reference_seed.sql
-- Deterministic seed data for lookup tables. Safe to rerun.

begin;

insert into dim_emotion (code, name_ru, valence, arousal, updated_at)
values
  ('joy', 'Радость', 4, 3, now()),
  ('calm', 'Спокойствие', 2, 1, now()),
  ('sadness', 'Грусть', -3, 2, now()),
  ('anxiety', 'Тревога', -2, 4, now())
on conflict (code) do update
  set name_ru = excluded.name_ru,
      valence = excluded.valence,
      arousal = excluded.arousal,
      updated_at = now();

insert into dim_accent (code, display_name, updated_at)
values
  ('us_general', 'General American', now()),
  ('uk_rp', 'Received Pronunciation', now()),
  ('aus', 'Australian', now())
on conflict (code) do update
  set display_name = excluded.display_name,
      updated_at = now();

insert into dim_topic (id, slug, display_name, parent_id, updated_at)
values
  ('11111111-1111-1111-1111-111111111111', 'technology', 'Technology', null, now()),
  ('22222222-2222-2222-2222-222222222222', 'movies', 'Movies & TV', null, now()),
  ('33333333-3333-3333-3333-333333333333', 'sports', 'Sports', null, now())
on conflict (slug) do update
  set display_name = excluded.display_name,
      updated_at = now();

commit;
