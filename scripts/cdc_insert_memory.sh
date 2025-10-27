#!/usr/bin/env bash
set -euo pipefail

DB_URL=${DB_URL:-postgresql://postgres:postgres@localhost:5432/englishfriend_dev}
ACTION=${1:-insert}

case "$ACTION" in
  insert)
    SQL="insert into memories (id, user_id, kind, content, meta, salience) values ('11111111-1111-1111-1111-111111111111', 1, 'episodic', 'First memory via CDC', '{"source_session":"00000000-0000-0000-0000-000000000001"}', 0.8) on conflict (id) do nothing;"
    ;;
  update)
    SQL="update memories set content = 'Updated memory via CDC', salience = 0.6 where id = '11111111-1111-1111-1111-111111111111';"
    ;;
  delete)
    SQL="delete from memories where id = '11111111-1111-1111-1111-111111111111';"
    ;;
  *)
    echo "Usage: $0 [insert|update|delete]" >&2
    exit 1
    ;;
esac

psql "$DB_URL" -c "$SQL"
