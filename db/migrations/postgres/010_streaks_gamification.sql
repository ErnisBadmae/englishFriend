-- 010_streaks_gamification.sql
-- Purpose: Add gamification fields (streaks, total_xp) to users table
-- and create partitions for xp_events table for 2026.

BEGIN;

-- ============================================================================
-- Add gamification fields to users table
-- ============================================================================

-- Current streak (consecutive days of activity)
ALTER TABLE users ADD COLUMN IF NOT EXISTS current_streak INT NOT NULL DEFAULT 0;

-- Maximum streak ever achieved
ALTER TABLE users ADD COLUMN IF NOT EXISTS max_streak INT NOT NULL DEFAULT 0;

-- Last activity date (for streak calculation)
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_activity_date DATE;

-- Total XP accumulated (denormalized for fast reads)
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_xp BIGINT NOT NULL DEFAULT 0;

-- Index for leaderboard queries
CREATE INDEX IF NOT EXISTS users_total_xp_idx ON users (total_xp DESC) WHERE deleted_at IS NULL;

-- ============================================================================
-- Create xp_events partitions for 2026
-- ============================================================================

-- January 2026
CREATE TABLE IF NOT EXISTS xp_events_2026_01
  PARTITION OF xp_events
  FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE INDEX IF NOT EXISTS xp_events_2026_01_user_idx
  ON xp_events_2026_01 (user_id, happened_at DESC);

-- February 2026
CREATE TABLE IF NOT EXISTS xp_events_2026_02
  PARTITION OF xp_events
  FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE INDEX IF NOT EXISTS xp_events_2026_02_user_idx
  ON xp_events_2026_02 (user_id, happened_at DESC);

-- March 2026
CREATE TABLE IF NOT EXISTS xp_events_2026_03
  PARTITION OF xp_events
  FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE INDEX IF NOT EXISTS xp_events_2026_03_user_idx
  ON xp_events_2026_03 (user_id, happened_at DESC);

-- ============================================================================
-- Add check constraint for valid XP event kinds
-- ============================================================================

-- Comment documenting valid kinds (no hard constraint for flexibility)
COMMENT ON COLUMN xp_events.kind IS 'Valid kinds: session_complete, streak_bonus, vocabulary_learned, perfect_pronunciation, first_session, comeback, daily_goal';

COMMIT;
