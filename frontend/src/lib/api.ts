const rawApiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function normalizeBaseUrl(baseUrl: string, protocol: 'http' | 'ws'): string {
  const trimmed = baseUrl.replace(/\/+$/, '');
  if (protocol === 'http') {
    return trimmed.replace(/^ws/i, 'http');
  }
  return trimmed.replace(/^http/i, 'ws');
}

export const API_BASE = normalizeBaseUrl(rawApiBase, 'http');
export const WS_BASE = normalizeBaseUrl(rawApiBase, 'ws');

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export interface UserIdentity {
  id: number;
  telegram_id?: number | null;
  username?: string | null;
  language_level?: string | null;
}

export interface GoalSummary {
  text?: string | null;
  preferred_mode: string;
  target_level?: string | null;
  focus_areas: string[];
  brief?: {
    primary_goal?: string | null;
    target_role?: string | null;
    domain?: string | null;
    target_market?: string | null;
    deadline_type?: string | null;
    main_contexts: string[];
    current_blockers: string[];
    motivation?: string | null;
    confidence?: number | null;
    status?: string | null;
    summary?: string | null;
  } | null;
  missing_fields: string[];
}

export interface AssessmentSummary {
  date?: string | null;
  level: string;
  scores: Record<string, number>;
  notes?: string | null;
  confidence?: number | null;
  goal_readiness?: number | null;
  critical_gaps: string[];
  skill_axes: Record<string, number | null>;
}

export interface MissionSummary {
  mode: string;
  launch_mode?: string | null;
  title: string;
  reason: string;
  why_now?: string | null;
  linked_goal_context?: string | null;
  linked_skill_gap?: string | null;
  from_interview?: boolean;
  interview_track_id?: string | null;
}

export interface ProgramSummary {
  title: string;
  time_horizon_days: number;
  current_stage: string;
  stage_label: string;
  weekly_focus: string[];
  success_metric: string;
  next_milestone: string;
  stages: Array<{ id: string; label: string; status: string }>;
  preferred_mode: string;
  focus_areas: string[];
}

export interface InterviewScores {
  overall: number;
  clarity: number;
  structure: number;
  accuracy: number;
  vocabulary: number;
  confidence: number;
}

export interface InterviewRunMeta {
  user_turns: number;
  avg_words_per_turn: number;
  corrections_count: number;
  weakest_area: string;
  strongest_area: string;
}

export interface InterviewRun {
  id: string;
  session_id: string;
  track_id: string;
  track_title: string;
  track_subtitle: string;
  recorded_at: string;
  scores: InterviewScores;
  strengths: string[];
  next_focus: string[];
  rubric_notes?: string[];
  summary: string;
  meta: InterviewRunMeta;
  delta_vs_previous?: number | null;
}

export interface InterviewTrack {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  prompt_focus: string;
  starter_question: string;
  rubric_focus: string[];
  recommended: boolean;
  completed_runs: number;
}

export interface InterviewSummary {
  completed_runs: number;
  readiness_score?: number | null;
  trend: string;
  recommended_track: {
    id: string;
    title: string;
    subtitle: string;
  };
  latest_run?: InterviewRun | null;
  recent_runs: InterviewRun[];
  weakest_area?: string | null;
  interview_focus?: string[];
  last_track?: string | null;
}

export interface VocabularyStats {
  total: number;
  new: number;
  learning: number;
  review: number;
  relearning: number;
  due_now: number;
}

export interface VocabularyCard {
  id: string;
  word: string;
  translation?: string | null;
  example_sentence?: string | null;
  phonetic?: string | null;
  due_at: string;
  fsrs_state?: number;
  state?: number;
  review_count?: number;
  correct_count?: number;
}

export interface ErrorPattern {
  label: string;
  count: number;
}

export interface RecentSession {
  id: string;
  started_at: string;
  ended_at?: string | null;
  duration_minutes?: number | null;
  corrections_count: number;
  summary?: string | null;
}

export interface ProgramSnapshot {
  user: UserIdentity;
  goal: GoalSummary;
  assessment?: AssessmentSummary | null;
  program: ProgramSummary;
  mission: MissionSummary;
  gamification: {
    xp: {
      total_xp: number;
      level: number;
      current_level_xp: number;
      next_level_xp: number;
      progress: number;
    };
    streak: {
      current: number;
      max: number;
      at_risk: boolean;
      last_activity?: string | null;
    };
  };
  interview: InterviewSummary;
  vocabulary: {
    stats: VocabularyStats;
    due_preview: VocabularyCard[];
  };
  progress: {
    sessions_completed: number;
    milestones: Array<Record<string, unknown>>;
    recommended_vocabulary: string[];
    top_error_patterns: ErrorPattern[];
    recent_sessions: RecentSession[];
  };
  setup: {
    goal_complete: boolean;
    assessment_complete: boolean;
    needs_attention: boolean;
  };
}

interface ReviewPayload {
  card_id: string;
  rating: number;
  session_id?: string;
  duration_ms?: number;
}

interface InterviewTracksResponse {
  summary: InterviewSummary;
  tracks: InterviewTrack[];
}

interface CreateInterviewRunPayload {
  session_id: string;
  track_id?: string;
  corrections_count?: number;
  reviewed_words?: Array<Record<string, unknown>>;
  conversation_history: Array<{
    role: string;
    content: string;
  }>;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const data = await response.json() as { detail?: string };
      if (data.detail) {
        detail = data.detail;
      }
    } catch {
      // Ignore JSON parse failures.
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function resolveOrCreateUser(telegramId: number, username?: string): Promise<UserIdentity> {
  try {
    return await fetchJson<UserIdentity>(`/api/v1/users/telegram/${telegramId}`);
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) {
      throw error;
    }
  }

  return fetchJson<UserIdentity>('/api/v1/users/', {
    method: 'POST',
    body: JSON.stringify({
      telegram_id: telegramId,
      username: username || `tg_${telegramId}`,
      language_level: 'B1',
    }),
  });
}

export async function getProgramSnapshot(userId: number): Promise<ProgramSnapshot> {
  return fetchJson<ProgramSnapshot>(`/api/v1/programs/${userId}/snapshot`);
}

export async function getDueVocabulary(userId: number, limit = 10): Promise<VocabularyCard[]> {
  return fetchJson<VocabularyCard[]>(`/api/v1/vocabulary/${userId}/due?limit=${limit}`);
}

export async function reviewVocabularyCard(userId: number, payload: ReviewPayload): Promise<VocabularyCard> {
  return fetchJson<VocabularyCard>(`/api/v1/vocabulary/${userId}/review`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getInterviewTracks(userId: number): Promise<InterviewTracksResponse> {
  return fetchJson<InterviewTracksResponse>(`/api/v1/interviews/${userId}/tracks`);
}

export async function getInterviewRuns(userId: number, limit = 10): Promise<InterviewRun[]> {
  return fetchJson<InterviewRun[]>(`/api/v1/interviews/${userId}/runs?limit=${limit}`);
}

export async function createInterviewRun(userId: number, payload: CreateInterviewRunPayload): Promise<InterviewRun> {
  return fetchJson<InterviewRun>(`/api/v1/interviews/${userId}/runs`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
