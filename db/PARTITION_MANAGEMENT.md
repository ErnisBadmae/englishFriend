# Automatic Partition Management

This document describes the automatic partition management system for the English Friend database, specifically for the `sessions` table.

## Overview

The partition management system automatically creates and maintains monthly partitions for the `sessions` table to ensure optimal performance and data organization. It includes:

- **Automatic partition creation** for future months
- **Old partition cleanup** based on retention policies
- **Cron job automation** for production environments
- **Manual management tools** for development and maintenance

## Database Functions

### `create_sessions_partition(partition_date date)`

Creates a single partition for the specified date.

```sql
-- Create partition for February 2026
SELECT create_sessions_partition('2026-02-15');
-- Returns: "Created partition sessions_2026_02 for 2026-02-01 to 2026-03-01"
```

### `create_sessions_partitions_ahead(months_ahead int)`

Creates partitions for the next N months starting from the current date.

```sql
-- Create partitions for next 3 months
SELECT create_sessions_partitions_ahead(3);
-- Returns: Array of creation results
```

### `drop_old_sessions_partitions(retention_months int)`

Removes partitions older than the specified retention period.

```sql
-- Drop partitions older than 12 months
SELECT drop_old_sessions_partitions(12);
-- Returns: Array of cleanup results
```

## Management Scripts

### `scripts/manage_partitions.sh`

A comprehensive shell script for partition management with the following features:

- **Database connectivity testing**
- **Partition creation and cleanup**
- **Status reporting**
- **Colored output and logging**

#### Usage

```bash
# Show current partitions
./scripts/manage_partitions.sh show

# Create partitions for next 3 months
./scripts/manage_partitions.sh create 3

# Cleanup partitions older than 12 months
./scripts/manage_partitions.sh cleanup 12

# Run both create and cleanup
./scripts/manage_partitions.sh both 3 12
```

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_HOST` | Database host | `localhost` |
| `DB_PORT` | Database port | `5432` |
| `DB_NAME` | Database name | `englishfriend_dev` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `postgres` |
| `MONTHS_AHEAD` | Default months ahead | `3` |
| `RETENTION_MONTHS` | Default retention | `12` |

## Cron Job Configuration

### System Crontab

Add to your system crontab (`crontab -e`):

```bash
# Create new partitions every month on the 1st at 2 AM
0 2 1 * * /path/to/englishFriend/scripts/manage_partitions.sh create 3

# Cleanup old partitions every month on the 1st at 3 AM
0 3 1 * * /path/to/englishFriend/scripts/manage_partitions.sh cleanup 12

# Show partition status every week on Sunday at 1 AM
0 1 * * 0 /path/to/englishFriend/scripts/manage_partitions.sh show
```

### Docker-based Cron

Use the provided `docker-compose.partitions.yml` for containerized cron management:

```bash
# Start partition management with cron
docker compose -f docker-compose.partitions.yml up -d

# View cron logs
docker compose -f docker-compose.partitions.yml logs partition-manager
```

## Testing

### Test Suite

The partition management system includes comprehensive tests in `db/tests/030_partition_management.sql`:

- Function existence validation
- Partition creation testing
- Index verification
- Cleanup functionality testing

### Running Tests

```bash
# Run partition management tests
docker compose exec postgres pg_prove -U postgres -d englishfriend_dev db/tests/030_partition_management.sql

# Run all database tests
docker compose exec postgres pg_prove -U postgres -d englishfriend_dev \
  db/tests/010_users_channel_identity.sql \
  db/tests/020_sessions_utterances.sql \
  db/tests/030_partition_management.sql
```

## Production Deployment

### 1. Database Migration

Ensure the partition management functions are installed:

```bash
# Run the partition management migration
docker compose exec postgres psql -U postgres -d englishfriend_dev \
  -f db/migrations/postgres/004_partition_management.sql
```

### 2. Initial Partition Creation

Create initial partitions for the next few months:

```bash
# Create partitions for next 3 months
docker compose exec postgres psql -U postgres -d englishfriend_dev \
  -c "SELECT create_sessions_partitions_ahead(3);"
```

### 3. Cron Job Setup

Choose one of the following approaches:

#### Option A: System Cron
```bash
# Install crontab
crontab scripts/crontab_partitions

# Verify installation
crontab -l
```

#### Option B: Docker Cron
```bash
# Start partition management container
docker compose -f docker-compose.partitions.yml up -d

# Monitor logs
docker compose -f docker-compose.partitions.yml logs -f partition-manager
```

### 4. Monitoring

Monitor partition management through:

- **Database queries**: Check partition existence and sizes
- **Cron logs**: Review execution logs for errors
- **Application metrics**: Monitor query performance

```sql
-- Check current partitions
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename LIKE 'sessions_%'
ORDER BY tablename;

-- Check partition boundaries
SELECT schemaname, tablename, 
       pg_get_expr(c.relpartbound, c.oid) as partition_bound
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' 
AND c.relname LIKE 'sessions_%'
AND c.relkind = 'r';
```

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure the database user has necessary privileges
2. **Connection Issues**: Verify database connectivity and credentials
3. **Partition Creation Failures**: Check for naming conflicts or date ranges
4. **Cleanup Issues**: Verify retention policies and partition ages

### Debug Commands

```bash
# Test database connectivity
docker compose exec postgres psql -U postgres -d englishfriend_dev -c "SELECT 1;"

# Check partition management functions
docker compose exec postgres psql -U postgres -d englishfriend_dev -c "
SELECT proname, prosrc FROM pg_proc 
WHERE proname LIKE '%sessions_partition%';"

# Test partition creation manually
docker compose exec postgres psql -U postgres -d englishfriend_dev -c "
SELECT create_sessions_partition('2026-03-15');"
```

## Performance Considerations

- **Partition Size**: Monthly partitions typically contain manageable data volumes
- **Index Maintenance**: Each partition has its own indexes for optimal performance
- **Query Planning**: PostgreSQL automatically uses partition pruning for time-based queries
- **Maintenance Windows**: Schedule partition operations during low-traffic periods

## Security

- **RLS Policies**: Partitions inherit RLS policies from the parent table
- **Access Control**: Ensure proper database user permissions
- **Audit Logging**: Monitor partition management operations
- **Backup Strategy**: Include partition management in backup procedures
