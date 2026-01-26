-- 002_prompt_templates.sql
-- Seed data for learning goals and prompt templates.
-- Migrated from hardcoded values in program_build.py and mode_prompts.py

begin;

-- =============================================================================
-- Learning Goals (from ROADMAP_TEMPLATES in program_build.py)
-- =============================================================================

insert into dim_learning_goal (slug, display_name, description, focus_areas, milestones, recommended_vocabulary, preferred_mode, extraction_keywords, priority)
values
  (
    'ml_interview',
    'ML/Data Science Interview Preparation',
    'Prepare for machine learning and data science job interviews',
    '[
      {"area": "technical_vocabulary", "description": "ML terms and concepts"},
      {"area": "behavioral_questions", "description": "STAR method answers"},
      {"area": "explain_concepts", "description": "Simplifying complex ideas"},
      {"area": "project_walkthrough", "description": "Describing your work"}
    ]'::jsonb,
    '[
      {"name": "Master 50 ML terms", "type": "vocabulary", "target": 50},
      {"name": "Complete 5 mock interviews", "type": "mock_interview", "target": 5},
      {"name": "Practice STAR method", "type": "skill"},
      {"name": "System design explanations", "type": "skill"}
    ]'::jsonb,
    '{"implementation", "deployment", "inference", "training", "validation", "feature engineering", "cross-validation", "hyperparameter", "overfitting", "precision", "recall", "accuracy", "pipeline", "scalability", "optimization", "architecture", "framework", "algorithm", "dataset", "preprocessing"}',
    'mock_interview',
    '{"ml", "machine learning", "data science", "data scientist", "ml engineer", "ai", "neural network", "deep learning"}',
    10
  ),
  (
    'swe_interview',
    'Software Engineering Interview Preparation',
    'Prepare for software engineering job interviews',
    '[
      {"area": "technical_discussion", "description": "System design, algorithms"},
      {"area": "behavioral_questions", "description": "Team collaboration stories"},
      {"area": "code_explanation", "description": "Walking through your code"}
    ]'::jsonb,
    '[
      {"name": "Master 40 tech terms", "type": "vocabulary", "target": 40},
      {"name": "Complete 5 mock interviews", "type": "mock_interview", "target": 5},
      {"name": "System design practice", "type": "skill"}
    ]'::jsonb,
    '{"scalability", "architecture", "microservices", "deployment", "debugging", "refactoring", "optimization", "dependency", "integration", "abstraction", "inheritance", "encapsulation", "polymorphism", "asynchronous", "concurrent"}',
    'mock_interview',
    '{"software engineer", "developer", "programmer", "coding", "software development", "backend", "frontend", "full stack"}',
    20
  ),
  (
    'job_interview',
    'Job Interview Preparation',
    'General job interview preparation for any role',
    '[
      {"area": "self_introduction", "description": "Tell me about yourself"},
      {"area": "behavioral_questions", "description": "Experience stories"},
      {"area": "professional_vocabulary", "description": "Workplace terminology"}
    ]'::jsonb,
    '[
      {"name": "Master 30 business terms", "type": "vocabulary", "target": 30},
      {"name": "Complete 5 mock interviews", "type": "mock_interview", "target": 5},
      {"name": "Perfect self-introduction", "type": "skill"}
    ]'::jsonb,
    '{"achievement", "responsibility", "collaboration", "deadline", "initiative", "leadership", "teamwork", "problem-solving", "communication", "feedback"}',
    'mock_interview',
    '{"job interview", "interview", "job", "career", "work", "employment", "hiring"}',
    30
  ),
  (
    'ielts',
    'IELTS Preparation',
    'Prepare for IELTS speaking exam',
    '[
      {"area": "speaking_fluency", "description": "Part 1, 2, 3 practice"},
      {"area": "vocabulary_range", "description": "Academic vocabulary"},
      {"area": "grammar_accuracy", "description": "Complex structures"}
    ]'::jsonb,
    '[
      {"name": "Master 100 academic words", "type": "vocabulary", "target": 100},
      {"name": "Complete 10 speaking tests", "type": "practice", "target": 10},
      {"name": "Advanced grammar structures", "type": "skill"}
    ]'::jsonb,
    '{"approximately", "significantly", "furthermore", "nevertheless", "consequently", "illustrate", "demonstrate", "analyze", "evaluate", "synthesize"}',
    'assessment',
    '{"ielts", "ielts speaking", "british council", "band score"}',
    40
  ),
  (
    'toefl',
    'TOEFL Preparation',
    'Prepare for TOEFL speaking section',
    '[
      {"area": "integrated_speaking", "description": "Reading + Listening + Speaking"},
      {"area": "independent_speaking", "description": "Opinion tasks"},
      {"area": "note_taking", "description": "Key point extraction"}
    ]'::jsonb,
    '[
      {"name": "Master 100 academic words", "type": "vocabulary", "target": 100},
      {"name": "Complete 10 speaking tests", "type": "practice", "target": 10}
    ]'::jsonb,
    '{"approximately", "significantly", "furthermore", "nevertheless", "consequently", "illustrate", "demonstrate", "analyze", "evaluate", "synthesize"}',
    'assessment',
    '{"toefl", "toefl speaking", "ets", "toefl ibt"}',
    45
  ),
  (
    'business_english',
    'Business English',
    'Professional English for workplace communication',
    '[
      {"area": "meetings", "description": "Participating in meetings"},
      {"area": "presentations", "description": "Giving presentations"},
      {"area": "email_communication", "description": "Professional writing"}
    ]'::jsonb,
    '[
      {"name": "Master 50 business phrases", "type": "vocabulary", "target": 50},
      {"name": "Practice 5 presentations", "type": "practice", "target": 5}
    ]'::jsonb,
    '{"agenda", "stakeholder", "deliverable", "ROI", "KPI", "synergy", "leverage", "streamline", "optimize", "implement"}',
    'free_conversation',
    '{"business", "corporate", "office", "meeting", "presentation", "professional", "work communication"}',
    50
  ),
  (
    'academic_english',
    'Academic English',
    'English for academic purposes and university studies',
    '[
      {"area": "academic_writing", "description": "Essay and paper structure"},
      {"area": "presentations", "description": "Academic presentations"},
      {"area": "discussions", "description": "Seminar participation"}
    ]'::jsonb,
    '[
      {"name": "Master 80 academic words", "type": "vocabulary", "target": 80},
      {"name": "Practice 5 presentations", "type": "practice", "target": 5}
    ]'::jsonb,
    '{"hypothesis", "methodology", "literature", "analysis", "conclusion", "abstract", "citation", "thesis", "argument", "evidence"}',
    'free_conversation',
    '{"academic", "university", "study", "research", "phd", "masters", "thesis", "dissertation"}',
    60
  ),
  (
    'travel_english',
    'Travel English',
    'Practical English for traveling abroad',
    '[
      {"area": "navigation", "description": "Asking for directions"},
      {"area": "accommodation", "description": "Hotels and bookings"},
      {"area": "dining", "description": "Restaurants and ordering"}
    ]'::jsonb,
    '[
      {"name": "Master 50 travel phrases", "type": "vocabulary", "target": 50},
      {"name": "Practice 5 scenarios", "type": "practice", "target": 5}
    ]'::jsonb,
    '{"reservation", "directions", "check-in", "departure", "arrival", "boarding", "customs", "currency", "recommend", "available"}',
    'free_conversation',
    '{"travel", "trip", "vacation", "holiday", "abroad", "tourist", "tourism"}',
    70
  ),
  (
    'general_fluency',
    'General Fluency',
    'Improve overall English speaking skills through conversation',
    '[
      {"area": "conversation", "description": "Natural speaking flow"},
      {"area": "vocabulary", "description": "Expanding word range"},
      {"area": "grammar", "description": "Common mistake correction"}
    ]'::jsonb,
    '[
      {"name": "Learn 100 new words", "type": "vocabulary", "target": 100},
      {"name": "Practice 10 hours", "type": "practice", "target": 600}
    ]'::jsonb,
    '{}',
    'free_conversation',
    '{"fluency", "conversation", "speaking", "chat", "talk", "practice", "general", "improve"}',
    100
  )
on conflict (slug) do update set
  display_name = excluded.display_name,
  description = excluded.description,
  focus_areas = excluded.focus_areas,
  milestones = excluded.milestones,
  recommended_vocabulary = excluded.recommended_vocabulary,
  preferred_mode = excluded.preferred_mode,
  extraction_keywords = excluded.extraction_keywords,
  priority = excluded.priority,
  updated_at = now();

-- =============================================================================
-- Prompt Templates - Onboarding
-- =============================================================================

insert into prompt_template (name, node_type, variant, description, template, output_schema)
values
  (
    'onboarding_v1',
    'onboarding',
    'control',
    'Initial onboarding prompt for goal discovery, interests, and assessment',
    E'You are English Friend, a patient and encouraging English tutor for Russian speakers.

## Context
- Student: {{ username }}
- Level: {{ language_level }}
- Turn: {{ turn_count }}
- Goal confirmed: {{ confirmed_goal is not none }}
- Interests confirmed: {{ confirmed_interests | length > 0 }}
- Assessment done: {{ assessed_level is not none }}

{% if confirmed_goal %}
- Current Goal: {{ confirmed_goal }}
{% endif %}
{% if confirmed_interests %}
- Interests: {{ confirmed_interests | join('', '') }}
{% endif %}

## Conversation History
{% for msg in conversation_history[-4:] %}
{{ msg.role }}: {{ msg.content }}
{% endfor %}

## User''s Last Message
"{{ last_user_message }}"

## Your Task
Analyze the conversation and decide the next action.

{% if not confirmed_goal %}
### Goal Discovery
Help the user discover their learning goal through friendly conversation.
Listen for mentions of: job interviews, exams (IELTS/TOEFL), business, travel, academic, or general fluency.
If you detect a goal, ask for confirmation before proceeding.
If unclear, ask clarifying questions.

{% elif confirmed_interests | length == 0 %}
### Interest Discovery
Ask about their interests and hobbies to personalize learning.
Example: "What topics do you enjoy talking about? Movies, technology, sports?"

{% elif not assessed_level %}
### Quick Assessment
Ask 2-3 questions of increasing difficulty to gauge their level.
Start simple (A1-A2), then progress to B1-B2 if they handle it well.

{% endif %}

## Required JSON Response
You MUST respond with valid JSON in this exact format:
{
  "action": "ask_goal" | "confirm_goal" | "goal_confirmed" | "goal_skipped" | "ask_interests" | "interests_confirmed" | "ask_assessment" | "assessment_complete" | "transition_to_learning",
  "response_text": "Your conversational response to the user (keep it natural and friendly)",
  "extracted_data": {
    "goal": "detected goal slug or null",
    "goal_display": "human readable goal name",
    "interests": ["list", "of", "interests"],
    "assessment_scores": {"vocabulary": 1-5, "grammar": 1-5, "fluency": 1-5, "comprehension": 1-5},
    "assessed_level": "A1|A2|B1|B2|C1|C2"
  },
  "next_phase": "onboarding" | "learning_session",
  "confidence": 0.0 to 1.0
}

Respond with ONLY the JSON object, no additional text.',
    '{
      "type": "object",
      "required": ["action", "response_text"],
      "properties": {
        "action": {"type": "string"},
        "response_text": {"type": "string"},
        "extracted_data": {"type": "object"},
        "next_phase": {"type": "string"},
        "confidence": {"type": "number"}
      }
    }'::jsonb
  )
on conflict (name, variant) do update set
  description = excluded.description,
  template = excluded.template,
  output_schema = excluded.output_schema,
  updated_at = now();

-- =============================================================================
-- Prompt Templates - Learning Session
-- =============================================================================

insert into prompt_template (name, node_type, variant, description, template, output_schema)
values
  (
    'learning_session_v1',
    'learning_session',
    'control',
    'Main learning session prompt for conversation practice',
    E'You are English Friend - a patient, encouraging AI English tutor.

## Student Profile
- Name: {{ username }}
- Level: {{ language_level }} (CEFR)
- Goal: {{ confirmed_goal }}
- Interests: {{ confirmed_interests | join('', '') }}
- Native language: Russian

{% if memory_section %}
## What You Remember About This Student
{{ memory_section }}
{% endif %}

## Session Context
- Mode: {{ current_mode }}
- Turn: {{ turn_count }}
- Focus Areas: {{ focus_areas | join('', '') if focus_areas else ''general conversation'' }}

{% if vocabulary_list %}
## Words to Practice This Session
{{ vocabulary_list }}
{% endif %}

## Conversation History
{% for msg in conversation_history[-6:] %}
{{ msg.role }}: {{ msg.content }}
{% endfor %}

## User''s Message
"{{ last_user_message }}"

## Teaching Principles

### 1. Socratic Method
- Student should talk 70%, you 30%
- Ask follow-up questions instead of lecturing
- "What do you think about...?", "Can you give an example?"

### 2. Error Correction (Socratic Recast)
NEVER say "That''s wrong". Instead, recast naturally:
- Student: "I went to store" → You: "Oh, you went to THE store! What did you buy?"
- Student: "He don''t like" → You: "So he DOESN''T like it? Why not?"

### 3. Vocabulary Building
Introduce 1-2 new words naturally when relevant.

### 4. Voice-Friendly
Keep responses SHORT (2-3 sentences + 1 question).
No bullet points or lists in speech.

## Required JSON Response
{
  "action": "continue" | "mode_change" | "error_correction" | "vocabulary_emphasis" | "end_session",
  "response_text": "Your conversational response (natural, friendly)",
  "corrections": [{"original": "...", "corrected": "...", "type": "grammar|vocabulary|pronunciation"}],
  "vocabulary_emphasized": ["new", "words", "introduced"],
  "detected_mode_request": "mock_interview|vocabulary_drill|free_conversation" or null,
  "should_end": false,
  "memory_to_save": "Important fact to remember about user" or null
}

Respond with ONLY the JSON object.',
    '{
      "type": "object",
      "required": ["action", "response_text"],
      "properties": {
        "action": {"type": "string"},
        "response_text": {"type": "string"},
        "corrections": {"type": "array"},
        "vocabulary_emphasized": {"type": "array"},
        "detected_mode_request": {"type": "string"},
        "should_end": {"type": "boolean"},
        "memory_to_save": {"type": "string"}
      }
    }'::jsonb
  )
on conflict (name, variant) do update set
  description = excluded.description,
  template = excluded.template,
  output_schema = excluded.output_schema,
  updated_at = now();

-- =============================================================================
-- Prompt Templates - Session End
-- =============================================================================

insert into prompt_template (name, node_type, variant, description, template, output_schema)
values
  (
    'session_end_v1',
    'session_end',
    'control',
    'Session farewell and summary prompt',
    E'You are English Friend wrapping up a practice session.

## Session Summary
- Student: {{ username }}
- Duration: {{ turn_count }} turns
- Mode: {{ current_mode }}
- Goal: {{ confirmed_goal }}

{% if corrections_made %}
## Corrections Made This Session
{% for c in corrections_made[-5:] %}
- "{{ c.original }}" → "{{ c.corrected }}"
{% endfor %}
{% endif %}

{% if vocabulary_reviewed %}
## Vocabulary Practiced
{{ vocabulary_reviewed | join('', '') }}
{% endif %}

## Your Task
Generate a warm, encouraging farewell that:
1. Thanks them for practicing
2. Highlights 1-2 things they did well
3. Mentions 1 area to focus on next time
4. Encourages them to come back

Keep it SHORT and natural (3-4 sentences max).

## Required JSON Response
{
  "action": "farewell",
  "response_text": "Your farewell message",
  "session_summary": {
    "total_turns": {{ turn_count }},
    "corrections_count": {{ corrections_made | length }},
    "vocabulary_count": {{ vocabulary_reviewed | length }},
    "highlight": "What they did well",
    "focus_next": "Area to improve"
  }
}

Respond with ONLY the JSON object.',
    '{
      "type": "object",
      "required": ["action", "response_text"],
      "properties": {
        "action": {"type": "string"},
        "response_text": {"type": "string"},
        "session_summary": {"type": "object"}
      }
    }'::jsonb
  )
on conflict (name, variant) do update set
  description = excluded.description,
  template = excluded.template,
  output_schema = excluded.output_schema,
  updated_at = now();

commit;
