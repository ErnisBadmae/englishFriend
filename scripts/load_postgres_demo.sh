#!/bin/bash
set -euo pipefail

echo "Loading demo data into PostgreSQL..."

# Wait for PostgreSQL to be ready
for i in {1..30}; do
  if pg_isready -h postgres -U postgres; then
    echo "PostgreSQL is ready!"
    break
  fi
  echo "Waiting for PostgreSQL... ($i/30)"
  sleep 2
done

# Load demo data
echo "Loading reference seed data..."
PGPASSWORD=postgres psql -h postgres -U postgres -d englishfriend_dev -f /app/seed/001_reference_seed.sql

echo "Loading demo data..."
PGPASSWORD=postgres psql -h postgres -U postgres -d englishfriend_dev -f /app/seed/002_demo_data.sql

echo "Demo data loaded successfully!"
