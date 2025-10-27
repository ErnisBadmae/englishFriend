# Database CI Integration

This document describes how to integrate the English Friend database migrations and tests into CI/CD pipelines.

## Migration Tools

### Flyway Integration

**Configuration File**: `flyway.conf`

```bash
# Run migrations
flyway -configFiles=flyway.conf migrate

# Validate migrations
flyway -configFiles=flyway.conf validate

# Clean database (dev only)
flyway -configFiles=flyway.conf clean
```

**Migration Files**: Located in `db/migrations/postgres/`
- `000_init.sql` - Base extensions
- `001_reference_tables.sql` - Enums and reference tables
- `002_users.sql` - User tables and constraints
- `003_sessions_utterances.sql` - Partitioned conversational storage
- `004_partition_management.sql` - Session partition automation helpers
- `005_memories_learning_plan.sql` - Memory store, learning plans, XP events
- `006_materialized_views.sql` - Weekly analytics materialized view

### Liquibase Integration

**Configuration File**: `liquibase.properties`

```bash
# Run migrations
liquibase --defaults-file=liquibase.properties update

# Validate migrations
liquibase --defaults-file=liquibase.properties validate

# Generate rollback scripts
liquibase --defaults-file=liquibase.properties futureRollbackSQL
```

**Changelog Files**: Located in `db/changelog/`
- `db.changelog-master.xml` - Master changelog
- `000-init.xml` - Base extensions
- `001-reference-tables.xml` - Reference tables
- `002-users.xml` - User tables
- `003-sessions-utterances.xml` - Sessions, utterances, feedback, corrections
- `004-partition-management.xml` - Partition helper functions
- `005-memories-learning-plan.xml` - Memories, learning_plan, xp_events
- `006-materialized-views.xml` - Weekly summary MV

## Testing

### pgTAP Tests

**Test Files**:
- `db/tests/010_users_channel_identity.sql`
- `db/tests/020_sessions_utterances.sql`
- `db/tests/030_partition_management.sql`
- `db/tests/040_memories_learning_plan.sql`
- `db/tests/050_mv_weekly_summary.sql`
- `graph/tests/schema_checks.cypher`
- `graph/tests/query_checks.cypher`
- `sync-graph/tests/test_transform.py`
- `sync-graph/tests/test_batch_metrics.py`

```bash
# Run tests with pg_prove
pg_prove -U postgres -d englishfriend_dev db/tests/010_users_channel_identity.sql
pg_prove -U postgres -d englishfriend_dev db/tests/020_sessions_utterances.sql
pg_prove -U postgres -d englishfriend_dev db/tests/030_partition_management.sql
pg_prove -U postgres -d englishfriend_dev db/tests/040_memories_learning_plan.sql
pg_prove -U postgres -d englishfriend_dev db/tests/050_mv_weekly_summary.sql

# Run tests with psql (alternative)
psql -U postgres -d englishfriend_dev -f db/tests/010_users_channel_identity.sql
psql -U postgres -d englishfriend_dev -f db/tests/020_sessions_utterances.sql
psql -U postgres -d englishfriend_dev -f db/tests/030_partition_management.sql
psql -U postgres -d englishfriend_dev -f db/tests/040_memories_learning_plan.sql
psql -U postgres -d englishfriend_dev -f db/tests/050_mv_weekly_summary.sql
```

**Test Coverage**:
- Enum type validation
- Table existence
- Constraint behavior (unique keys, foreign keys)
- Data integrity
- Partition/index presence and RLS behavior for conversational data
- Partition management routines, memory triggers, and analytics materialized views
- Neo4j constraints/queries and CDC flow health (sync-vector / sync-graph services)

## Docker Setup

**Docker Compose**: `docker-compose.yml`

```bash
# Start database
docker compose up -d postgres

# Run migrations
docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/000_init.sql
docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/001_reference_tables.sql
docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/002_users.sql
docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/003_sessions_utterances.sql
docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/004_partition_management.sql
docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/005_memories_learning_plan.sql
docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/006_materialized_views.sql

# Run seed data
docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/seed/001_reference_seed.sql

# Run tests
docker compose exec postgres bash -c "cat > /tmp/test_users.sql" < db/tests/010_users_channel_identity.sql
docker compose exec postgres bash -c "cat > /tmp/test_sessions.sql" < db/tests/020_sessions_utterances.sql
docker compose exec postgres bash -c "cat > /tmp/test_partitions.sql" < db/tests/030_partition_management.sql
docker compose exec postgres bash -c "cat > /tmp/test_memories.sql" < db/tests/040_memories_learning_plan.sql
docker compose exec postgres bash -c "cat > /tmp/test_mv.sql" < db/tests/050_mv_weekly_summary.sql
docker compose exec postgres pg_prove -U postgres -d englishfriend_dev /tmp/test_users.sql
docker compose exec postgres pg_prove -U postgres -d englishfriend_dev /tmp/test_sessions.sql
docker compose exec postgres pg_prove -U postgres -d englishfriend_dev /tmp/test_partitions.sql
docker compose exec postgres pg_prove -U postgres -d englishfriend_dev /tmp/test_memories.sql
docker compose exec postgres pg_prove -U postgres -d englishfriend_dev /tmp/test_mv.sql
```

## CI Pipeline Examples

### GitHub Actions

```yaml
name: Database Tests
on: [push, pull_request]

jobs:
  test-database:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: englishfriend_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3
      
      - name: Install pgTAP
        run: |
          sudo apt-get update
          sudo apt-get install -y postgresql-15-pgtap
      
      - name: Run migrations
        run: |
          psql $DATABASE_URL -f db/migrations/postgres/000_init.sql
          psql $DATABASE_URL -f db/migrations/postgres/001_reference_tables.sql
          psql $DATABASE_URL -f db/migrations/postgres/002_users.sql
          psql $DATABASE_URL -f db/migrations/postgres/003_sessions_utterances.sql
          psql $DATABASE_URL -f db/migrations/postgres/004_partition_management.sql
          psql $DATABASE_URL -f db/migrations/postgres/005_memories_learning_plan.sql
          psql $DATABASE_URL -f db/migrations/postgres/006_materialized_views.sql
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/englishfriend_test
      
      - name: Run seed data
        run: psql $DATABASE_URL -f db/seed/001_reference_seed.sql
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/englishfriend_test
      
      - name: Run tests
        run: |
          pg_prove -U postgres -d englishfriend_test db/tests/010_users_channel_identity.sql
          pg_prove -U postgres -d englishfriend_test db/tests/020_sessions_utterances.sql
          pg_prove -U postgres -d englishfriend_test db/tests/030_partition_management.sql
          pg_prove -U postgres -d englishfriend_test db/tests/040_memories_learning_plan.sql
          pg_prove -U postgres -d englishfriend_test db/tests/050_mv_weekly_summary.sql
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    
    environment {
        DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/englishfriend_test'
    }
    
    stages {
        stage('Setup Database') {
            steps {
                sh 'docker compose up -d postgres'
                sh 'sleep 10' // Wait for database to be ready
            }
        }
        
        stage('Run Migrations') {
            steps {
                sh 'docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/000_init.sql'
                sh 'docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/001_reference_tables.sql'
                sh 'docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/002_users.sql'
                sh 'docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/003_sessions_utterances.sql'
                sh 'docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/004_partition_management.sql'
                sh 'docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/005_memories_learning_plan.sql'
                sh 'docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/migrations/postgres/006_materialized_views.sql'
            }
        }
        
        stage('Run Seed Data') {
            steps {
                sh 'docker compose exec postgres psql -U postgres -d englishfriend_dev -f /dev/stdin < db/seed/001_reference_seed.sql'
            }
        }
        
        stage('Run Tests') {
            steps {
                sh 'docker compose exec postgres bash -c "cat > /tmp/test_users.sql" < db/tests/010_users_channel_identity.sql'
                sh 'docker compose exec postgres bash -c "cat > /tmp/test_sessions.sql" < db/tests/020_sessions_utterances.sql'
                sh 'docker compose exec postgres bash -c "cat > /tmp/test_partitions.sql" < db/tests/030_partition_management.sql'
                sh 'docker compose exec postgres bash -c "cat > /tmp/test_memories.sql" < db/tests/040_memories_learning_plan.sql'
                sh 'docker compose exec postgres bash -c "cat > /tmp/test_mv.sql" < db/tests/050_mv_weekly_summary.sql'
                sh 'docker compose exec postgres pg_prove -U postgres -d englishfriend_dev /tmp/test_users.sql'
                sh 'docker compose exec postgres pg_prove -U postgres -d englishfriend_dev /tmp/test_sessions.sql'
                sh 'docker compose exec postgres pg_prove -U postgres -d englishfriend_dev /tmp/test_partitions.sql'
                sh 'docker compose exec postgres pg_prove -U postgres -d englishfriend_dev /tmp/test_memories.sql'
                sh 'docker compose exec postgres pg_prove -U postgres -d englishfriend_dev /tmp/test_mv.sql'
            }
        }
    }
    
    post {
        always {
            sh 'docker compose down'
        }
    }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/englishfriend_dev` |
| `POSTGRES_DB` | Database name | `englishfriend_dev` |
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Database password | `postgres` |

## Notes

- All migrations are idempotent and can be safely re-run
- Tests use pgTAP and require the extension to be installed
- Docker setup includes pgTAP installation
- Flyway and Liquibase configurations are provided for different CI preferences
- Seed data is deterministic and safe to re-run
- CDC connectors can be registered during CI smoke tests via `scripts/register_connector.sh cdc/connectors/*.json`; use `docker-compose.cdc.yml` when end-to-end validation (sync-vector + sync-graph) is required.
