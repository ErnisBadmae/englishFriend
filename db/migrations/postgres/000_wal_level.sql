-- 000_wal_level.sql
-- Purpose: Configure PostgreSQL for CDC (Change Data Capture)

-- Enable logical replication for CDC
ALTER SYSTEM SET wal_level = logical;
SELECT pg_reload_conf();
