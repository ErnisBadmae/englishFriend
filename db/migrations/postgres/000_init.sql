-- 000_init.sql
-- Purpose: base extensions required by English Friend data layer.

begin;

create extension if not exists pgcrypto;     -- gen_random_uuid()
create extension if not exists btree_gin;
create extension if not exists pg_trgm;
-- optional vector extension (disabled by default, uncomment if fallback chosen)
-- create extension if not exists vector;

commit;
