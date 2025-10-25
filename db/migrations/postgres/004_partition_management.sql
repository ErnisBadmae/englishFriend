-- 004_partition_management.sql
-- Purpose: Automatic partition management for sessions table

begin;

-- Function to create monthly partitions for sessions table
create or replace function create_sessions_partition(partition_date date)
returns text
language plpgsql
as $$
declare
    partition_name text;
    start_date date;
    end_date date;
    sql_stmt text;
begin
    -- Calculate partition boundaries (first day of month to first day of next month)
    start_date := date_trunc('month', partition_date);
    end_date := start_date + interval '1 month';
    
    -- Generate partition name (e.g., sessions_2025_11)
    partition_name := 'sessions_' || to_char(start_date, 'YYYY_MM');
    
    -- Check if partition already exists
    if exists (
        select 1 from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relname = partition_name
    ) then
        return 'Partition ' || partition_name || ' already exists';
    end if;
    
    -- Create the partition
    sql_stmt := format('
        create table %I partition of sessions
        for values from (%L) to (%L)',
        partition_name, start_date, end_date
    );
    
    execute sql_stmt;
    
    -- Create indexes on the new partition
    execute format('create index %I on %I (user_id, started_at desc)',
        partition_name || '_user_started_idx', partition_name);
    
    return 'Created partition ' || partition_name || ' for ' || start_date || ' to ' || end_date;
end;
$$;

-- Function to create partitions for the next N months
create or replace function create_sessions_partitions_ahead(months_ahead int default 3)
returns text[]
language plpgsql
as $$
declare
    result text[];
    i int;
    start_date date;
    partition_result text;
begin
    result := array[]::text[];
    start_date := current_date;
    
    for i in 0..months_ahead-1 loop
        partition_result := create_sessions_partition((start_date + (i || ' months')::interval)::date);
        result := array_append(result, partition_result);
    end loop;
    
    return result;
end;
$$;

-- Function to drop old partitions (older than retention_months)
create or replace function drop_old_sessions_partitions(retention_months int default 12)
returns text[]
language plpgsql
as $$
declare
    result text[];
    partition_record record;
    cutoff_date date;
    sql_stmt text;
begin
    result := array[]::text[];
    cutoff_date := current_date - (retention_months || ' months')::interval;
    
    -- Find partitions older than cutoff_date
    for partition_record in
        select schemaname, tablename
        from pg_tables
        where schemaname = 'public'
        and tablename like 'sessions_%'
        and tablename ~ '^sessions_[0-9]{4}_[0-9]{2}$'
        and to_date(
            regexp_replace(tablename, 'sessions_([0-9]{4})_([0-9]{2})', '\1-\2-01'),
            'YYYY-MM-DD'
        ) < cutoff_date
    loop
        sql_stmt := format('drop table if exists %I.%I cascade',
            partition_record.schemaname, partition_record.tablename);
        
        execute sql_stmt;
        result := array_append(result, 'Dropped partition ' || partition_record.tablename);
    end loop;
    
    return result;
end;
$$;

-- Create initial partitions for the next 3 months
select create_sessions_partitions_ahead(3);

commit;
