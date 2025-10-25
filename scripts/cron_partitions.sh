#!/bin/bash
# cron_partitions.sh
# Cron job script for partition management

# Set environment variables
export DB_HOST="${DB_HOST:-postgres}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-englishfriend_dev}"
export DB_USER="${DB_USER:-postgres}"
export DB_PASSWORD="${DB_PASSWORD:-postgres}"

# Log file
LOG_FILE="/var/log/partition-management.log"

# Function to log with timestamp
log_with_timestamp() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Create partitions (run on 1st of each month)
if [ "$(date +%d)" = "01" ]; then
    log_with_timestamp "Creating new partitions for next 3 months"
    /usr/local/bin/manage_partitions.sh create 3 >> "$LOG_FILE" 2>&1
    
    log_with_timestamp "Cleaning up old partitions (older than 12 months)"
    /usr/local/bin/manage_partitions.sh cleanup 12 >> "$LOG_FILE" 2>&1
fi

# Show partition status (run weekly on Sunday)
if [ "$(date +%u)" = "7" ]; then
    log_with_timestamp "Weekly partition status check"
    /usr/local/bin/manage_partitions.sh show >> "$LOG_FILE" 2>&1
fi
