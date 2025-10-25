#!/usr/bin/env python3
"""Generate synthetic sessions/utterances rows to exercise CDC/Neo4j merge."""
import argparse
import random
import string
from datetime import datetime, timedelta

import psycopg2


def random_uuid(prefix: str) -> str:
    suffix = ''.join(random.choices('0123456789abcdef', k=12))
    return f"{prefix}{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--events', type=int, default=1000)
    parser.add_argument('--dsn', default='postgresql://postgres:postgres@localhost:5432/englishfriend_dev')
    args = parser.parse_args()

    conn = psycopg2.connect(args.dsn)
    conn.autocommit = True
    cur = conn.cursor()

    now = datetime.utcnow()
    for i in range(args.events):
        user_id = (i % 10) + 1
        session_id = random_uuid('00000000-0000-0000-0000-')
        started = now - timedelta(minutes=i)
        cur.execute(
            "insert into sessions (id, user_id, started_at) values (%s, %s, %s) on conflict do nothing",
            (session_id, user_id, started)
        )
        utt_id = random_uuid('11111111-1111-1111-1111-')
        cur.execute(
            "insert into utterances (id, session_id, speaker, t_start_ms, t_end_ms, text, topics) values (%s, %s, 'user', 0, 1000, %s, '[]'::jsonb) on conflict do nothing",
            (utt_id, session_id, f"Synthetic utterance {i}")
        )
    print(f"Inserted {args.events} synthetic events.")


if __name__ == '__main__':
    main()
