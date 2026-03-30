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
}

export interface AssessmentSummary {
  date?: string | null;
  level: string;
  scores: Record<string, number>;
  notes?: string | null;
}

export interface MissionSummary {
  mode: string;
  title: string;
  reason: string;
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
}

interface ReviewPayload {
  card_id: string;
  rating: number;
  session_id?: string;
  duration_ms?: number;
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
