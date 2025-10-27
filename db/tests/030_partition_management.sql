-- 030_partition_management.sql
-- Tests for automatic partition management functionality

begin;

select plan(10);

-- Test 1: Check that partition management functions exist
select has_function(
  'public',
  'create_sessions_partition',
  'create_sessions_partition function exists'
);

select has_function(
  'public',
  'create_sessions_partitions_ahead',
  'create_sessions_partitions_ahead function exists'
);

select has_function(
  'public',
  'drop_old_sessions_partitions',
  'drop_old_sessions_partitions function exists'
);

-- Test 2: Test creating a partition for a specific date
select lives_ok(
  $q$
    select create_sessions_partition('2026-02-15')
  $q$,
  'create_sessions_partition works for specific date'
);

-- Test 3: Test creating partitions ahead
select lives_ok(
  $q$
    select create_sessions_partitions_ahead(1)
  $q$,
  'create_sessions_partitions_ahead works'
);

-- Test 4: Verify partitions were created
select has_table(
  'public',
  'sessions_2026_02',
  'sessions_2026_02 partition exists'
);

-- Test 5: Test partition structure (should have at least 4 partitions)
select ok(
  (select count(*) >= 4 from pg_tables 
   where schemaname = 'public' 
   and tablename like 'sessions_%'),
  'sufficient number of partitions exist'
);

-- Test 6: Test partition indexes exist
select has_index(
  'public',
  'sessions_2026_02',
  'sessions_2026_02_user_started_idx',
  'partition has user/started index'
);

-- Test 7: Test cleanup function (should not drop recent partitions)
select lives_ok(
  $q$
    select drop_old_sessions_partitions(12)
  $q$,
  'drop_old_sessions_partitions works without dropping recent partitions'
);

-- Test 8: Verify partitions still exist after cleanup
select ok(
  (select count(*) >= 4 from pg_tables 
   where schemaname = 'public' 
   and tablename like 'sessions_%'),
  'partitions still exist after cleanup'
);

select * from finish();

rollback;
