-- 002_demo_data.sql
-- Demo data for CDC testing. Safe to rerun.

begin;

-- Insert demo user
insert into users (id, telegram_id, username, language_level, primary_channel, accent_pref)
values
  (1, 123456789, 'demo_user_1', 'B1', 'telegram', 'us_general')
on conflict (id) do update
  set telegram_id = excluded.telegram_id,
      username = excluded.username,
      language_level = excluded.language_level,
      primary_channel = excluded.primary_channel,
      accent_pref = excluded.accent_pref;

-- Insert demo sessions
insert into sessions (id, user_id, started_at, ended_at, lang_code)
values
  ('00000000-0000-0000-0000-000000000001', 1, '2025-10-25T10:00:00Z', '2025-10-25T10:30:00Z', 'en'),
  ('00000000-0000-0000-0000-000000000002', 1, '2025-10-25T11:00:00Z', '2025-10-25T11:15:00Z', 'en')
on conflict (id, started_at) do update
  set user_id = excluded.user_id,
      started_at = excluded.started_at,
      ended_at = excluded.ended_at,
      lang_code = excluded.lang_code;

-- Insert demo utterances
insert into utterances (id, session_id, speaker, t_start_ms, t_end_ms, text, topics, emotion_code, emotion_score)
values
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'user', 0, 1200, 'Hello, I want to learn English', '["technology"]', 'joy', 0.8),
  ('00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001', 'assistant', 1200, 2400, 'Great! Let''s start with basic conversation', '["technology"]', 'calm', 0.6),
  ('00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000002', 'user', 0, 800, 'I like movies', '["movies"]', 'joy', 0.7)
on conflict (id, session_id) do update
  set speaker = excluded.speaker,
      t_start_ms = excluded.t_start_ms,
      t_end_ms = excluded.t_end_ms,
      text = excluded.text,
      topics = excluded.topics,
      emotion_code = excluded.emotion_code,
      emotion_score = excluded.emotion_score;

-- Insert demo corrections
insert into corrections (id, session_id, utterance_id, user_text, corrected_text, rule_tag, explanation_md)
values
  ('00000000-0000-0000-0000-000000000020', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000010', 'I go to school', 'I go to school', 'grammar', 'Use present tense')
on conflict (id) do update
  set session_id = excluded.session_id,
      utterance_id = excluded.utterance_id,
      user_text = excluded.user_text,
      corrected_text = excluded.corrected_text,
      rule_tag = excluded.rule_tag,
      explanation_md = excluded.explanation_md;

-- Insert demo user interests
insert into user_interest (user_id, topic_id, weight, last_mentioned)
values
  (1, '11111111-1111-1111-1111-111111111111', 0.8, '2025-10-25T10:00:00Z'),
  (1, '22222222-2222-2222-2222-222222222222', 0.6, '2025-10-25T10:00:00Z'),
  (1, '33333333-3333-3333-3333-333333333333', 0.9, '2025-10-25T11:00:00Z')
on conflict (user_id, topic_id) do update
  set weight = excluded.weight,
      last_mentioned = excluded.last_mentioned;

-- Insert demo memories
insert into memories (id, user_id, kind, content, meta, salience)
values
  ('00000000-0000-0000-0000-000000000030', 1, 'episodic', 'User likes technology topics', '{"source": "conversation", "confidence": 0.8}', 0.7),
  ('00000000-0000-0000-0000-000000000031', 1, 'semantic', 'User is at B1 level', '{"level": "B1", "assessed": true}', 0.9),
  ('00000000-0000-0000-0000-000000000032', 1, 'episodic', 'User enjoys movies', '{"source": "conversation", "confidence": 0.9}', 0.8)
on conflict (id) do update
  set user_id = excluded.user_id,
      kind = excluded.kind,
      content = excluded.content,
      meta = excluded.meta,
      salience = excluded.salience;

-- Insert demo learning plan
insert into learning_plan (id, user_id, level_target, next_review_at, roadmap)
values
  ('00000000-0000-0000-0000-000000000040', 1, 'B2', '2025-11-01T10:00:00Z', '{"focus": ["grammar", "vocabulary"], "progress": 0.3}')
on conflict (id) do update
  set user_id = excluded.user_id,
      level_target = excluded.level_target,
      next_review_at = excluded.next_review_at,
      roadmap = excluded.roadmap;

-- Insert demo xp events
insert into xp_events (id, user_id, session_id, kind, points, happened_at)
values
  ('00000000-0000-0000-0000-000000000050', 1, '00000000-0000-0000-0000-000000000001', 'session_completed', 100, '2025-10-25T10:30:00Z'),
  ('00000000-0000-0000-0000-000000000051', 1, '00000000-0000-0000-0000-000000000001', 'grammar_improvement', 50, '2025-10-25T10:25:00Z'),
  ('00000000-0000-0000-0000-000000000052', 1, '00000000-0000-0000-0000-000000000002', 'session_completed', 80, '2025-10-25T11:15:00Z')
on conflict (id, happened_at) do update
  set user_id = excluded.user_id,
      session_id = excluded.session_id,
      kind = excluded.kind,
      points = excluded.points,
      happened_at = excluded.happened_at;

commit;
