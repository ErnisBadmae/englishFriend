-- 011_goal_prompts_ab.sql
-- Purpose: Learning goals from DB, prompt templates with A/B testing support.
-- Part of agent architecture refactoring: hardcoded → LLM-driven with goals.

begin;

-- =============================================================================
-- Learning Goals (replace hardcoded ROADMAP_TEMPLATES in program_build.py)
-- =============================================================================

create table if not exists dim_learning_goal (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,                          -- 'ml_interview', 'general_fluency'
  display_name text not null,                         -- 'ML/Data Science Interview Preparation'
  description text,                                   -- Optional longer description
  focus_areas jsonb not null default '[]'::jsonb,     -- [{"area": "...", "description": "..."}]
  milestones jsonb not null default '[]'::jsonb,      -- [{"name": "...", "type": "...", "target": N}]
  recommended_vocabulary text[] default '{}',         -- Keywords for vocab drill
  preferred_mode text not null default 'free_conversation',
  extraction_keywords text[] default '{}',            -- Keywords for LLM extraction
  priority int not null default 100,                  -- Sort order (lower = higher priority)
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists dim_learning_goal_active_idx
  on dim_learning_goal (is_active, priority);

comment on table dim_learning_goal is 'Learning goal templates - replaces hardcoded ROADMAP_TEMPLATES';
comment on column dim_learning_goal.slug is 'URL-safe identifier: ml_interview, ielts, general_fluency';
comment on column dim_learning_goal.extraction_keywords is 'Keywords to help LLM detect this goal from user message';

-- =============================================================================
-- Prompt Templates with A/B Versioning
-- =============================================================================

create table if not exists prompt_template (
  id uuid primary key default gen_random_uuid(),
  name text not null,                                 -- 'onboarding_v1', 'learning_session_v2'
  node_type text not null,                            -- 'onboarding', 'learning_session', 'session_end'
  variant text not null default 'control',            -- 'control', 'variant_a', 'variant_b'
  description text,                                   -- Human-readable description
  template text not null,                             -- Jinja2-style template with {{ placeholders }}
  output_schema jsonb,                                -- Expected JSON structure from LLM
  is_active boolean not null default true,
  weight int not null default 100,                    -- A/B weight (0-100), used when no experiment
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(name, variant)
);

create index if not exists prompt_template_node_active_idx
  on prompt_template (node_type, is_active);

comment on table prompt_template is 'System prompt templates for LLM-driven agent nodes';
comment on column prompt_template.template is 'Jinja2 template with {{ username }}, {{ language_level }}, etc.';
comment on column prompt_template.output_schema is 'Expected JSON schema for structured LLM output';

-- =============================================================================
-- A/B Test Experiments
-- =============================================================================

create type ab_experiment_status as enum ('draft', 'running', 'paused', 'completed');

create table if not exists ab_experiment (
  id uuid primary key default gen_random_uuid(),
  name text unique not null,                          -- 'onboarding_rewrite_2024'
  description text,
  node_type text not null,                            -- Which node this experiment affects
  control_template_id uuid references prompt_template(id) on delete set null,
  variant_template_id uuid references prompt_template(id) on delete set null,
  traffic_percent int not null default 50 check (traffic_percent between 0 and 100),
  status ab_experiment_status not null default 'draft',
  start_at timestamptz,
  end_at timestamptz,
  metrics jsonb default '{}'::jsonb,                  -- Aggregated results
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists ab_experiment_status_idx
  on ab_experiment (status, node_type);

comment on table ab_experiment is 'A/B test configurations for prompt comparison';
comment on column ab_experiment.traffic_percent is 'Percent of traffic to variant (0-100)';

-- =============================================================================
-- Session Prompt Log (A/B Analytics)
-- =============================================================================

create table if not exists session_prompt_log (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null,                           -- References sessions (no FK due to partitioning)
  user_id bigint not null references users(id) on delete cascade,
  node_type text not null,
  prompt_template_id uuid references prompt_template(id) on delete set null,
  experiment_id uuid references ab_experiment(id) on delete set null,
  variant text not null,
  turn_number int,
  input_context jsonb,                                -- State snapshot (optional, can be large)
  llm_response text,                                  -- Raw LLM response
  parsed_action jsonb,                                -- Parsed structured action
  parse_success boolean not null default true,
  latency_ms int,
  created_at timestamptz not null default now()
);

create index if not exists session_prompt_log_session_idx
  on session_prompt_log (session_id);
create index if not exists session_prompt_log_user_idx
  on session_prompt_log (user_id, created_at desc);
create index if not exists session_prompt_log_variant_idx
  on session_prompt_log (variant, node_type, created_at);
create index if not exists session_prompt_log_experiment_idx
  on session_prompt_log (experiment_id) where experiment_id is not null;

comment on table session_prompt_log is 'Tracks which prompt variant was used per session turn for A/B analytics';

-- RLS for session_prompt_log
alter table session_prompt_log enable row level security;
do $$ begin
  create policy session_prompt_log_isolation on session_prompt_log
    using (user_id = coalesce(nullif(current_setting('app.user_id', true), '')::bigint, -1));
exception
  when duplicate_object then null;
end $$;

-- =============================================================================
-- Updated_at triggers
-- =============================================================================

create or replace function trg_update_timestamp()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists dim_learning_goal_updated_at on dim_learning_goal;
create trigger dim_learning_goal_updated_at
before update on dim_learning_goal
for each row execute function trg_update_timestamp();

drop trigger if exists prompt_template_updated_at on prompt_template;
create trigger prompt_template_updated_at
before update on prompt_template
for each row execute function trg_update_timestamp();

drop trigger if exists ab_experiment_updated_at on ab_experiment;
create trigger ab_experiment_updated_at
before update on ab_experiment
for each row execute function trg_update_timestamp();

commit;
