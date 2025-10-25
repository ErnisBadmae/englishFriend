-- Requires pgTAP (https://pgtap.org). Run via `pg_prove`.
begin;

select plan(7);

select has_type(
  'public',
  'access_channel',
  'access_channel enum exists'
);

select has_table(
  'public',
  'user_channel_identity',
  'user_channel_identity table exists'
);

select lives_ok($q$
  insert into users (username, primary_channel)
  values ('test_user_channel_identity', 'telegram');
$q$, 'insert test user');

select lives_ok($q$
  insert into user_channel_identity (user_id, channel, external_id)
  values (currval('users_id_seq'), 'telegram', 'tg-test-001');
$q$, 'link telegram identity');

select throws_ok(
  $q$
    insert into user_channel_identity (user_id, channel, external_id)
    values (currval('users_id_seq'), 'telegram', 'tg-test-002');
  $q$,
  '23505',
  'duplicate key value violates unique constraint "user_channel_identity_user_id_channel_key"'
);

select throws_ok(
  $q$
    insert into user_channel_identity (user_id, channel, external_id)
    values (currval('users_id_seq'), 'discord', 'discord-1');
  $q$,
  '22P02',
  'invalid input value for enum access_channel: "discord"'
);

select lives_ok($q$
  delete from user_channel_identity where user_id = currval('users_id_seq');
  delete from users where id = currval('users_id_seq');
$q$, 'cleanup test rows');

select * from finish();

rollback;
