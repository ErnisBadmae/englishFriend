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
    
    local result
    result=$(execute_sql \
        "SELECT create_sessions_partitions_ahead($months_ahead);" \
        "Creating sessions partitions")
    
    if [ $? -eq 0 ]; then
        log "Partition creation completed successfully"
        echo "$result" | while IFS= read -r line; do
            if [ -n "$line" ]; then
                log "  $line"
            fi
        done
    else
        error "Failed to create partitions"
        return 1
    fi
}

# Function to cleanup old partitions
cleanup_partitions() {
    local retention_months="$1"
    
    log "Cleaning up partitions older than $retention_months months"
    
    local result
    result=$(execute_sql \
        "SELECT drop_old_sessions_partitions($retention_months);" \
        "Cleaning up old partitions")
    
    if [ $? -eq 0 ]; then
        log "Partition cleanup completed successfully"
        echo "$result" | while IFS= read -r line; do
            if [ -n "$line" ]; then
                log "  $line"
            fi
        done
    else
        error "Failed to cleanup partitions"
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
