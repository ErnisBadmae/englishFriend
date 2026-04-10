#!/bin/bash
# manage_partitions.sh
# Automatic partition management for English Friend database
# Usage: ./manage_partitions.sh [create|cleanup] [months_ahead] [retention_months]

set -euo pipefail

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-englishfriend_dev}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"

# Default values
MONTHS_AHEAD="${MONTHS_AHEAD:-3}"
RETENTION_MONTHS="${RETENTION_MONTHS:-12}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Function to execute SQL
execute_sql() {
    local sql="$1"
    local description="$2"
    
    log "Executing: $description"
    
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -c "$sql" \
        -t -A
}

# Function to create partitions
create_partitions() {
    local months_ahead="$1"
    
    log "Creating partitions for next $months_ahead months"
    
    local sessions_result
    sessions_result=$(execute_sql \
        "SELECT create_sessions_partitions_ahead($months_ahead);" \
        "Creating sessions partitions")
    
    if [ $? -eq 0 ]; then
        echo "$sessions_result" | while IFS= read -r line; do
            if [ -n "$line" ]; then
                log "  $line"
            fi
        done
    else
        error "Failed to create sessions partitions"
        return 1
    fi

    local xp_result
    xp_result=$(execute_sql \
        "DO \$\$
        DECLARE
            start_month date := date_trunc('month', current_date)::date;
            start_date date;
            end_date date;
            partition_name text;
            i int;
        BEGIN
            FOR i IN 0..$months_ahead LOOP
                start_date := (start_month + (i || ' months')::interval)::date;
                end_date := (start_month + ((i + 1) || ' months')::interval)::date;
                partition_name := 'xp_events_' || to_char(start_date, 'YYYY_MM');

                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS %I PARTITION OF xp_events FOR VALUES FROM (%L) TO (%L)',
                    partition_name,
                    start_date,
                    end_date
                );

                EXECUTE format(
                    'CREATE INDEX IF NOT EXISTS %I ON %I (user_id, happened_at DESC)',
                    partition_name || '_user_idx',
                    partition_name
                );
            END LOOP;
        END
        \$\$;" \
        "Creating xp_events partitions")

    if [ $? -eq 0 ]; then
        log "Partition creation completed successfully"
        echo "$xp_result" | while IFS= read -r line; do
            if [ -n "$line" ]; then
                log "  $line"
            fi
        done
    else
        error "Failed to create xp_events partitions"
        return 1
    fi
}

# Function to cleanup old partitions
cleanup_partitions() {
    local retention_months="$1"
    
    log "Cleaning up partitions older than $retention_months months"
    
    local sessions_result
    sessions_result=$(execute_sql \
        "SELECT drop_old_sessions_partitions($retention_months);" \
        "Cleaning up old partitions")
    
    if [ $? -eq 0 ]; then
        echo "$sessions_result" | while IFS= read -r line; do
            if [ -n "$line" ]; then
                log "  $line"
            fi
        done
    else
        error "Failed to cleanup sessions partitions"
        return 1
    fi

    local xp_result
    xp_result=$(execute_sql \
        "DO \$\$
        DECLARE
            cutoff_date date := date_trunc('month', current_date - ($retention_months || ' months')::interval)::date;
            partition_record record;
            partition_date date;
        BEGIN
            FOR partition_record IN
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename LIKE 'xp_events_%'
                  AND tablename ~ '^xp_events_[0-9]{4}_[0-9]{2}$'
            LOOP
                partition_date := to_date(
                    regexp_replace(partition_record.tablename, 'xp_events_([0-9]{4})_([0-9]{2})', '\1-\2-01'),
                    'YYYY-MM-DD'
                );

                IF partition_date < cutoff_date THEN
                    EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', partition_record.tablename);
                END IF;
            END LOOP;
        END
        \$\$;" \
        "Cleaning up old xp_events partitions")

    if [ $? -eq 0 ]; then
        log "Partition cleanup completed successfully"
        echo "$xp_result" | while IFS= read -r line; do
            if [ -n "$line" ]; then
                log "  $line"
            fi
        done
    else
        error "Failed to cleanup xp_events partitions"
        return 1
    fi
}

# Function to show current partitions
show_partitions() {
    log "Current sessions partitions:"
    
    execute_sql \
        "SELECT 
            schemaname, 
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
         FROM pg_tables 
         WHERE schemaname = 'public' 
         AND tablename LIKE 'sessions_%'
         ORDER BY tablename;" \
        "Listing current partitions"

    log "Current xp_events partitions:"

    execute_sql \
        "SELECT 
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
         FROM pg_tables
         WHERE schemaname = 'public'
           AND tablename LIKE 'xp_events_%'
         ORDER BY tablename;" \
        "Listing current xp_events partitions"
}

# Function to check if database is accessible
check_database() {
    log "Checking database connectivity..."
    
    if execute_sql "SELECT 1;" "Database connectivity test" > /dev/null 2>&1; then
        log "Database connection successful"
        return 0
    else
        error "Cannot connect to database"
        return 1
    fi
}

# Main function
main() {
    local action="${1:-create}"
    local months_ahead="${2:-$MONTHS_AHEAD}"
    local retention_months="${3:-$RETENTION_MONTHS}"
    
    log "Starting partition management"
    log "Action: $action"
    log "Months ahead: $months_ahead"
    log "Retention months: $retention_months"
    
    # Check database connectivity
    if ! check_database; then
        exit 1
    fi
    
    case "$action" in
        "create")
            create_partitions "$months_ahead"
            ;;
        "cleanup")
            cleanup_partitions "$retention_months"
            ;;
        "show")
            show_partitions
            ;;
        "both")
            create_partitions "$months_ahead"
            cleanup_partitions "$retention_months"
            ;;
        *)
            error "Unknown action: $action"
            echo "Usage: $0 [create|cleanup|show|both] [months_ahead] [retention_months]"
            exit 1
            ;;
    esac
    
    log "Partition management completed"
}

# Run main function with all arguments
main "$@"
