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
  draft_available?: boolean;
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
  status?: string | null;
  provisional?: boolean;
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
  task_type: string;
  expected_outcome: string;
  estimated_minutes: number;
  success_signal: string;
}

export interface CareerContextSummary {
  target_role?: string | null;
  company_type?: string | null;
  interview_date?: string | null;
  target_market?: string | null;
  vacancy_present: boolean;
  vacancy_summary?: string | null;
}

export interface InterviewPackSummary {
  target_role?: string | null;
  must_answer_questions: string[];
  project_story_prompts: string[];
  key_terms: string[];
  top_blockers: string[];
  recommended_track?: string | null;
  recommended_track_title?: string | null;
  summary?: string | null;
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

export interface PronunciationWordFeedback {
  word: string;
  issue: string;
  severity: string;
  tip: string;
}

export interface InterviewPronunciationResult {
  session_id: string;
  track_id?: string | null;
  recorded_at: string;
  provider: string;
  assessment_mode: string;
  overall_score: number;
  accuracy_score: number;
  fluency_score: number;
  prosody_score?: number | null;
  confidence: number;
  notes: string;
  recommended_focus: string[];
  word_feedback: PronunciationWordFeedback[];
}

export interface PronunciationSummary {
  latest_score?: number | null;
  accuracy_score?: number | null;
  fluency_score?: number | null;
  prosody_score?: number | null;
  focus: string[];
  word_feedback: PronunciationWordFeedback[];
  source?: string | null;
  assessment_mode?: string | null;
  confidence?: number | null;
  last_assessed_at?: string | null;
  trend: string;
  history_count: number;
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
  pronunciation?: InterviewPronunciationResult | null;
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

export interface SessionEvidence {
  id: string;
  session_id: string;
  mission_type: string;
  mission_title: string;
  summary: string;
  what_was_trained: string;
  what_went_well: string[];
  main_issue?: string | null;
  next_focus: string[];
  evidence_signals: string[];
  recorded_at: string;
  duration_minutes: number;
}

export interface MonetizationSummary {
  show_paid_cta: boolean;
  paid_intent_submitted: boolean;
  latest_paid_intent_at?: string | null;
  latest_paid_intent_context?: string | null;
}

export interface ProgramSnapshot {
  user: UserIdentity;
  goal: GoalSummary;
  assessment?: AssessmentSummary | null;
  program: ProgramSummary;
  career_context: CareerContextSummary;
  interview_pack?: InterviewPackSummary | null;
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
  pronunciation: PronunciationSummary;
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
    improvement_signals: string[];
  };
  session_evidence: {
    latest?: SessionEvidence | null;
    recent: SessionEvidence[];
  };
  setup: {
    goal_complete: boolean;
    assessment_complete: boolean;
    needs_attention: boolean;
    state: string;
    next_question_type?: string | null;
    progress: number;
  };
  monetization: MonetizationSummary;
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

interface SubmitVacancyPayload {
  vacancy_text: string;
  interview_date?: string;
}

interface SubmitPaidIntentPayload {
  source: string;
  note?: string;
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

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {};
}

function normalizeInterviewRun(raw: unknown): InterviewRun | null {
  const record = asRecord(raw);
  if (!record.id || !record.session_id || !record.track_id) {
    return null;
  }

  const scores = asRecord(record.scores);
  const meta = asRecord(record.meta);
  const pronunciationRecord = record.pronunciation ? asRecord(record.pronunciation) : null;

  return {
    id: String(record.id),
    session_id: String(record.session_id),
    track_id: String(record.track_id),
    track_title: typeof record.track_title === 'string' ? record.track_title : 'Interview run',
    track_subtitle: typeof record.track_subtitle === 'string' ? record.track_subtitle : '',
    recorded_at: typeof record.recorded_at === 'string' ? record.recorded_at : new Date().toISOString(),
    scores: {
      overall: Number(scores.overall ?? 0),
      clarity: Number(scores.clarity ?? 0),
      structure: Number(scores.structure ?? 0),
      accuracy: Number(scores.accuracy ?? 0),
      vocabulary: Number(scores.vocabulary ?? 0),
      confidence: Number(scores.confidence ?? 0),
    },
    strengths: asStringArray(record.strengths),
    next_focus: asStringArray(record.next_focus),
    rubric_notes: asStringArray(record.rubric_notes),
    summary: typeof record.summary === 'string' ? record.summary : '',
    meta: {
      user_turns: Number(meta.user_turns ?? 0),
      avg_words_per_turn: Number(meta.avg_words_per_turn ?? 0),
      corrections_count: Number(meta.corrections_count ?? 0),
      weakest_area: typeof meta.weakest_area === 'string' ? meta.weakest_area : 'unknown',
      strongest_area: typeof meta.strongest_area === 'string' ? meta.strongest_area : 'unknown',
    },
    delta_vs_previous: record.delta_vs_previous == null ? null : Number(record.delta_vs_previous),
    pronunciation: pronunciationRecord ? {
      session_id: typeof pronunciationRecord.session_id === 'string' ? pronunciationRecord.session_id : String(record.session_id),
      track_id: typeof pronunciationRecord.track_id === 'string' ? pronunciationRecord.track_id : null,
      recorded_at: typeof pronunciationRecord.recorded_at === 'string' ? pronunciationRecord.recorded_at : new Date().toISOString(),
      provider: typeof pronunciationRecord.provider === 'string' ? pronunciationRecord.provider : 'heuristic_text',
      assessment_mode: typeof pronunciationRecord.assessment_mode === 'string' ? pronunciationRecord.assessment_mode : 'text_heuristic',
      overall_score: Number(pronunciationRecord.overall_score ?? 0),
      accuracy_score: Number(pronunciationRecord.accuracy_score ?? 0),
      fluency_score: Number(pronunciationRecord.fluency_score ?? 0),
      prosody_score: pronunciationRecord.prosody_score == null ? null : Number(pronunciationRecord.prosody_score),
      confidence: Number(pronunciationRecord.confidence ?? 0),
      notes: typeof pronunciationRecord.notes === 'string' ? pronunciationRecord.notes : '',
      recommended_focus: asStringArray(pronunciationRecord.recommended_focus),
      word_feedback: Array.isArray(pronunciationRecord.word_feedback)
        ? pronunciationRecord.word_feedback.map((item) => {
            const feedback = asRecord(item);
            return {
              word: typeof feedback.word === 'string' ? feedback.word : '',
              issue: typeof feedback.issue === 'string' ? feedback.issue : '',
              severity: typeof feedback.severity === 'string' ? feedback.severity : 'medium',
              tip: typeof feedback.tip === 'string' ? feedback.tip : '',
            };
          }).filter((item) => item.word)
        : [],
    } : null,
  };
}

function normalizeSessionEvidence(raw: unknown): SessionEvidence | null {
  const record = asRecord(raw);
  if (!record.session_id) {
    return null;
  }

  return {
    id: typeof record.id === 'string' ? record.id : String(record.session_id),
    session_id: String(record.session_id),
    mission_type: typeof record.mission_type === 'string' ? record.mission_type : 'free_conversation',
    mission_title: typeof record.mission_title === 'string' ? record.mission_title : 'Guided mission',
    summary: typeof record.summary === 'string' ? record.summary : '',
    what_was_trained: typeof record.what_was_trained === 'string' ? record.what_was_trained : '',
    what_went_well: asStringArray(record.what_went_well),
    main_issue: typeof record.main_issue === 'string' ? record.main_issue : null,
    next_focus: asStringArray(record.next_focus),
    evidence_signals: asStringArray(record.evidence_signals),
    recorded_at: typeof record.recorded_at === 'string' ? record.recorded_at : new Date().toISOString(),
    duration_minutes: Number(record.duration_minutes ?? 0),
  };
}

function normalizeProgramSnapshot(raw: unknown, fallbackUserId: number): ProgramSnapshot {
  const record = asRecord(raw);
  const goal = asRecord(record.goal);
  const brief = asRecord(goal.brief);
  const assessmentRecord = record.assessment ? asRecord(record.assessment) : null;
  const program = asRecord(record.program);
  const mission = asRecord(record.mission);
  const careerContext = asRecord(record.career_context);
  const interviewPack = record.interview_pack ? asRecord(record.interview_pack) : null;
  const gamification = asRecord(record.gamification);
  const xp = asRecord(gamification.xp);
  const streak = asRecord(gamification.streak);
  const interview = asRecord(record.interview);
  const pronunciation = asRecord(record.pronunciation);
  const vocabulary = asRecord(record.vocabulary);
  const vocabularyStats = asRecord(vocabulary.stats);
  const progress = asRecord(record.progress);
  const sessionEvidenceRecord = asRecord(record.session_evidence);
  const setup = asRecord(record.setup);
  const monetization = asRecord(record.monetization);

  const goalBrief = Object.keys(brief).length > 0 ? {
    primary_goal: typeof brief.primary_goal === 'string' ? brief.primary_goal : null,
    target_role: typeof brief.target_role === 'string' ? brief.target_role : null,
    domain: typeof brief.domain === 'string' ? brief.domain : null,
    target_market: typeof brief.target_market === 'string' ? brief.target_market : null,
    deadline_type: typeof brief.deadline_type === 'string' ? brief.deadline_type : null,
    main_contexts: asStringArray(brief.main_contexts),
    current_blockers: asStringArray(brief.current_blockers),
    motivation: typeof brief.motivation === 'string' ? brief.motivation : null,
    confidence: brief.confidence == null ? null : Number(brief.confidence),
    status: typeof brief.status === 'string' ? brief.status : null,
    summary: typeof brief.summary === 'string' ? brief.summary : null,
  } : null;

  const assessment = assessmentRecord ? {
    date: typeof assessmentRecord.date === 'string' ? assessmentRecord.date : null,
    level: typeof assessmentRecord.level === 'string' ? assessmentRecord.level : 'Unknown',
    scores: asRecord(assessmentRecord.scores) as Record<string, number>,
    notes: typeof assessmentRecord.notes === 'string' ? assessmentRecord.notes : null,
    confidence: assessmentRecord.confidence == null ? null : Number(assessmentRecord.confidence),
    status: typeof assessmentRecord.status === 'string' ? assessmentRecord.status : null,
    provisional: Boolean(assessmentRecord.provisional),
    goal_readiness: assessmentRecord.goal_readiness == null ? null : Number(assessmentRecord.goal_readiness),
    critical_gaps: asStringArray(assessmentRecord.critical_gaps),
    skill_axes: asRecord(assessmentRecord.skill_axes) as Record<string, number | null>,
  } : null;

  const goalMissingFields = asStringArray(goal.missing_fields);
  const goalComplete = typeof setup.goal_complete === 'boolean'
    ? setup.goal_complete
    : Boolean(goalBrief && ['draft', 'confirmed'].includes(goalBrief.status || '') && goalMissingFields.length === 0);
  const assessmentComplete = typeof setup.assessment_complete === 'boolean'
    ? setup.assessment_complete
    : Boolean(assessment?.level && assessment.level !== 'Unknown');
  const needsAttention = typeof setup.needs_attention === 'boolean'
    ? setup.needs_attention
    : !(goalComplete && assessmentComplete);

  const defaultMission: MissionSummary = needsAttention
    ? {
        mode: 'guided_setup',
        launch_mode: 'assessment',
        title: 'Complete your setup',
        reason: 'Clarify your goal and baseline so the coach can build a useful program.',
        why_now: 'Without a confirmed target and baseline, daily practice is too generic.',
        linked_goal_context: null,
        linked_skill_gap: null,
        from_interview: false,
        interview_track_id: null,
        task_type: 'goal_setup',
        expected_outcome: 'A confirmed goal and baseline.',
        estimated_minutes: 4,
        success_signal: 'Your next mission becomes concrete instead of generic.',
      }
    : {
        mode: 'free_conversation',
        launch_mode: 'free_conversation',
        title: 'Start today’s mission',
        reason: 'Use the next session to reinforce your current program stage.',
        why_now: 'A short focused session keeps your program moving forward.',
        linked_goal_context: null,
        linked_skill_gap: null,
        from_interview: false,
        interview_track_id: null,
        task_type: 'guided_speaking_session',
        expected_outcome: 'One useful guided repetition tied to your program.',
        estimated_minutes: 8,
        success_signal: 'You finish with one clearer next step.',
      };

  const latestRun = normalizeInterviewRun(interview.latest_run);
  const recentRuns = Array.isArray(interview.recent_runs)
    ? interview.recent_runs.map(normalizeInterviewRun).filter((item): item is InterviewRun => Boolean(item))
    : [];

  return {
    user: {
      id: Number(asRecord(record.user).id ?? fallbackUserId),
      telegram_id: asRecord(record.user).telegram_id == null ? null : Number(asRecord(record.user).telegram_id),
      username: typeof asRecord(record.user).username === 'string' ? String(asRecord(record.user).username) : null,
      language_level: typeof asRecord(record.user).language_level === 'string' ? String(asRecord(record.user).language_level) : null,
    },
    goal: {
      text: typeof goal.text === 'string' ? goal.text : goalBrief?.primary_goal ?? null,
      preferred_mode: typeof goal.preferred_mode === 'string' ? goal.preferred_mode : 'free_conversation',
      target_level: typeof goal.target_level === 'string' ? goal.target_level : null,
      focus_areas: asStringArray(goal.focus_areas),
      draft_available: Boolean(goal.draft_available),
      brief: goalBrief,
      missing_fields: goalMissingFields,
    },
    assessment,
    program: {
      title: typeof program.title === 'string' ? program.title : 'Career English Program',
      time_horizon_days: Number(program.time_horizon_days ?? 90),
      current_stage: typeof program.current_stage === 'string' ? program.current_stage : (needsAttention ? 'setup' : 'core_career_communication'),
      stage_label: typeof program.stage_label === 'string' ? program.stage_label : (needsAttention ? 'Setup' : 'Core Career Communication'),
      weekly_focus: asStringArray(program.weekly_focus),
      success_metric: typeof program.success_metric === 'string'
        ? program.success_metric
        : (needsAttention ? 'Lock your goal and baseline before daily missions.' : 'Build confidence toward your target role.'),
      next_milestone: typeof program.next_milestone === 'string'
        ? program.next_milestone
        : (needsAttention ? 'Complete setup' : 'Finish your next mission'),
      stages: Array.isArray(program.stages) ? program.stages as Array<{ id: string; label: string; status: string }> : [],
      preferred_mode: typeof program.preferred_mode === 'string' ? program.preferred_mode : 'free_conversation',
      focus_areas: asStringArray(program.focus_areas),
    },
    career_context: {
      target_role: typeof careerContext.target_role === 'string' ? careerContext.target_role : null,
      company_type: typeof careerContext.company_type === 'string' ? careerContext.company_type : null,
      interview_date: typeof careerContext.interview_date === 'string' ? careerContext.interview_date : null,
      target_market: typeof careerContext.target_market === 'string' ? careerContext.target_market : null,
      vacancy_present: Boolean(careerContext.vacancy_present),
      vacancy_summary: typeof careerContext.vacancy_summary === 'string' ? careerContext.vacancy_summary : null,
    },
    interview_pack: interviewPack ? {
      target_role: typeof interviewPack.target_role === 'string' ? interviewPack.target_role : null,
      must_answer_questions: asStringArray(interviewPack.must_answer_questions),
      project_story_prompts: asStringArray(interviewPack.project_story_prompts),
      key_terms: asStringArray(interviewPack.key_terms),
      top_blockers: asStringArray(interviewPack.top_blockers),
      recommended_track: typeof interviewPack.recommended_track === 'string' ? interviewPack.recommended_track : null,
      recommended_track_title: typeof interviewPack.recommended_track_title === 'string' ? interviewPack.recommended_track_title : null,
      summary: typeof interviewPack.summary === 'string' ? interviewPack.summary : null,
    } : null,
    mission: {
      mode: typeof mission.mode === 'string' ? mission.mode : defaultMission.mode,
      launch_mode: typeof mission.launch_mode === 'string' ? mission.launch_mode : defaultMission.launch_mode ?? null,
      title: typeof mission.title === 'string' ? mission.title : defaultMission.title,
      reason: typeof mission.reason === 'string' ? mission.reason : defaultMission.reason,
      why_now: typeof mission.why_now === 'string' ? mission.why_now : defaultMission.why_now ?? null,
      linked_goal_context: typeof mission.linked_goal_context === 'string' ? mission.linked_goal_context : defaultMission.linked_goal_context ?? null,
      linked_skill_gap: typeof mission.linked_skill_gap === 'string' ? mission.linked_skill_gap : defaultMission.linked_skill_gap ?? null,
      from_interview: typeof mission.from_interview === 'boolean' ? mission.from_interview : false,
      interview_track_id: typeof mission.interview_track_id === 'string' ? mission.interview_track_id : null,
      task_type: typeof mission.task_type === 'string' ? mission.task_type : defaultMission.task_type,
      expected_outcome: typeof mission.expected_outcome === 'string' ? mission.expected_outcome : defaultMission.expected_outcome,
      estimated_minutes: Number(mission.estimated_minutes ?? defaultMission.estimated_minutes),
      success_signal: typeof mission.success_signal === 'string' ? mission.success_signal : defaultMission.success_signal,
    },
    gamification: {
      xp: {
        total_xp: Number(xp.total_xp ?? 0),
        level: Number(xp.level ?? 1),
        current_level_xp: Number(xp.current_level_xp ?? 0),
        next_level_xp: Number(xp.next_level_xp ?? 100),
        progress: Number(xp.progress ?? 0),
      },
      streak: {
        current: Number(streak.current ?? 0),
        max: Number(streak.max ?? 0),
        at_risk: Boolean(streak.at_risk),
        last_activity: typeof streak.last_activity === 'string' ? streak.last_activity : null,
      },
    },
    interview: {
      completed_runs: Number(interview.completed_runs ?? recentRuns.length),
      readiness_score: interview.readiness_score == null
        ? assessment?.goal_readiness ?? null
        : Number(interview.readiness_score),
      trend: typeof interview.trend === 'string' ? interview.trend : 'Not enough data yet',
      recommended_track: {
        id: typeof asRecord(interview.recommended_track).id === 'string' ? String(asRecord(interview.recommended_track).id) : 'hr_intro',
        title: typeof asRecord(interview.recommended_track).title === 'string' ? String(asRecord(interview.recommended_track).title) : 'HR Interview',
        subtitle: typeof asRecord(interview.recommended_track).subtitle === 'string' ? String(asRecord(interview.recommended_track).subtitle) : 'Practice concise career answers',
      },
      latest_run: latestRun,
      recent_runs: recentRuns,
      weakest_area: typeof interview.weakest_area === 'string' ? interview.weakest_area : null,
      interview_focus: asStringArray(interview.interview_focus),
      last_track: typeof interview.last_track === 'string' ? interview.last_track : null,
    },
    pronunciation: {
      latest_score: pronunciation.latest_score == null ? null : Number(pronunciation.latest_score),
      accuracy_score: pronunciation.accuracy_score == null ? null : Number(pronunciation.accuracy_score),
      fluency_score: pronunciation.fluency_score == null ? null : Number(pronunciation.fluency_score),
      prosody_score: pronunciation.prosody_score == null ? null : Number(pronunciation.prosody_score),
      focus: asStringArray(pronunciation.focus),
      word_feedback: Array.isArray(pronunciation.word_feedback)
        ? pronunciation.word_feedback.map((item) => {
            const feedback = asRecord(item);
            return {
              word: typeof feedback.word === 'string' ? feedback.word : '',
              issue: typeof feedback.issue === 'string' ? feedback.issue : '',
              severity: typeof feedback.severity === 'string' ? feedback.severity : 'medium',
              tip: typeof feedback.tip === 'string' ? feedback.tip : '',
            };
          }).filter((item) => item.word)
        : [],
      source: typeof pronunciation.source === 'string' ? pronunciation.source : null,
      assessment_mode: typeof pronunciation.assessment_mode === 'string' ? pronunciation.assessment_mode : null,
      confidence: pronunciation.confidence == null ? null : Number(pronunciation.confidence),
      last_assessed_at: typeof pronunciation.last_assessed_at === 'string' ? pronunciation.last_assessed_at : null,
      trend: typeof pronunciation.trend === 'string' ? pronunciation.trend : 'building',
      history_count: Number(pronunciation.history_count ?? 0),
    },
    vocabulary: {
      stats: {
        total: Number(vocabularyStats.total ?? 0),
        new: Number(vocabularyStats.new ?? 0),
        learning: Number(vocabularyStats.learning ?? 0),
        review: Number(vocabularyStats.review ?? 0),
        relearning: Number(vocabularyStats.relearning ?? 0),
        due_now: Number(vocabularyStats.due_now ?? 0),
      },
      due_preview: Array.isArray(vocabulary.due_preview) ? vocabulary.due_preview as VocabularyCard[] : [],
    },
    progress: {
      sessions_completed: Number(progress.sessions_completed ?? 0),
      milestones: Array.isArray(progress.milestones) ? progress.milestones as Array<Record<string, unknown>> : [],
      recommended_vocabulary: asStringArray(progress.recommended_vocabulary),
      top_error_patterns: Array.isArray(progress.top_error_patterns) ? progress.top_error_patterns as ErrorPattern[] : [],
      recent_sessions: Array.isArray(progress.recent_sessions) ? progress.recent_sessions as RecentSession[] : [],
      improvement_signals: asStringArray(progress.improvement_signals),
    },
    session_evidence: {
      latest: normalizeSessionEvidence(sessionEvidenceRecord.latest),
      recent: Array.isArray(sessionEvidenceRecord.recent)
        ? sessionEvidenceRecord.recent
          .map(normalizeSessionEvidence)
          .filter((item): item is SessionEvidence => Boolean(item))
        : [],
    },
    setup: {
      goal_complete: goalComplete,
      assessment_complete: assessmentComplete,
      needs_attention: needsAttention,
      state: typeof setup.state === 'string'
        ? setup.state
        : (goalComplete ? (assessmentComplete ? 'ready_for_program' : 'needs_assessment') : 'needs_goal'),
      next_question_type: typeof setup.next_question_type === 'string' ? setup.next_question_type : null,
      progress: Number(setup.progress ?? (goalComplete ? (assessmentComplete ? 100 : 75) : (goalBrief ? 40 : 0))),
    },
    monetization: {
      show_paid_cta: Boolean(monetization.show_paid_cta),
      paid_intent_submitted: Boolean(monetization.paid_intent_submitted),
      latest_paid_intent_at: typeof monetization.latest_paid_intent_at === 'string' ? monetization.latest_paid_intent_at : null,
      latest_paid_intent_context: typeof monetization.latest_paid_intent_context === 'string' ? monetization.latest_paid_intent_context : null,
    },
  };
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
  const raw = await fetchJson<unknown>(`/api/v1/programs/${userId}/snapshot`);
  return normalizeProgramSnapshot(raw, userId);
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

export async function submitVacancy(userId: number, payload: SubmitVacancyPayload): Promise<void> {
  await fetchJson(`/api/v1/career/${userId}/vacancy`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function submitPaidIntent(userId: number, payload: SubmitPaidIntentPayload): Promise<void> {
  await fetchJson(`/api/v1/career/${userId}/paid-intent`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
