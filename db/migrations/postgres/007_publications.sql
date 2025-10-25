-- 007_publications.sql
-- Ensure publications include partitioned parents so Debezium can stream sessions data.

begin;

-- Drop and recreate memories publication with explicit table list.
do $$
begin
  execute 'drop publication if exists memories_publication';
  execute 'create publication memories_publication for table public.memories';
exception
  when others then
    raise notice 'memories_publication reset failed: %', sqlerrm;
end;
$$;

-- Drop and recreate graph publication to include parent tables (partitions inherit).
do $$
begin
  execute 'drop publication if exists graph_publication';
  execute 'create publication graph_publication for table public.sessions, public.utterances, public.corrections, public.user_interest with (publish_via_partition_root = true)';
exception
  when others then
    raise notice 'graph_publication reset failed: %', sqlerrm;
end;
$$;

commit;
