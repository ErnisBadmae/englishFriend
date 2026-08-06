import { useEffect, useState } from "react";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { HomePage } from "./components/HomePage";
import { InterviewPage } from "./components/InterviewPage";
import { InterviewResultsPage } from "./components/InterviewResultsPage";
import { MlTechnicalPage } from "./components/MlTechnicalPage";
import { ProgressPage } from "./components/ProgressPage";
import { ReviewPage } from "./components/ReviewPage";
import { SessionResultsPage } from "./components/SessionResultsPage";
import { VoiceChatV2 } from "./components/VoiceChatV2";
import {
  API_BASE,
  WS_BASE,
  getProgramSnapshot,
  resolveOrCreateUser,
  submitPaidIntent,
  submitProjectNotes,
  submitVacancy,
  type InterviewRun,
  type InterviewTrack,
  type MissionSummary,
  type ProgramSnapshot,
  type SessionEvidence
} from "./lib/api";
import "./App.css";

type Screen =
  | "home"
  | "session"
  | "interview"
  | "ml_technical"
  | "review"
  | "progress"
  | "interview_results"
  | "session_results";

interface SessionConfig {
  wsUrl: string;
  mode?: string;
  interviewTrackId?: string;
  sttProvider?: string;
  title?: string;
  subtitle?: string;
  reviewBeforeSend?: boolean;
  mission?: MissionSummary;
  returnScreen: Screen;
}

const DEFAULT_STT_PROVIDER = import.meta.env.VITE_STT_PROVIDER || "composer";

interface TelegramIdentity {
  telegramId: number;
  username: string;
}

/**
 * Telegram ids are external identifiers. Only a positive safe integer is
 * accepted, and there is no fallback person: an unusable value must surface as
 * a setup error instead of silently resolving somebody else's profile.
 */
function parseTelegramId(raw: unknown): number | null {
  if (typeof raw === "number") {
    return Number.isSafeInteger(raw) && raw > 0 ? raw : null;
  }
  if (typeof raw === "string" && /^\d+$/.test(raw.trim())) {
    const parsed = Number(raw.trim());
    return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
  }
  return null;
}

function resolveTelegramIdentity(
  telegramUser: { id?: unknown; username?: unknown; first_name?: unknown } | undefined,
  localEnvValue: unknown
): TelegramIdentity | null {
  const telegramWebAppId = parseTelegramId(telegramUser?.id);
  if (telegramWebAppId !== null) {
    const named =
      (typeof telegramUser?.username === "string" && telegramUser.username) ||
      (typeof telegramUser?.first_name === "string" && telegramUser.first_name) ||
      "";
    return {
      telegramId: telegramWebAppId,
      username: named || `tg_${telegramWebAppId}`
    };
  }

  const localId = parseTelegramId(localEnvValue);
  if (localId !== null) {
    return { telegramId: localId, username: `tg_${localId}` };
  }

  return null;
}

const IDENTITY_SETUP_ERROR =
  "No profile identity available. Open this app inside Telegram, or set " +
  "VITE_LOCAL_TELEGRAM_ID to your existing Telegram id in frontend/.env.local " +
  "and restart the dev server.";

function shouldForceGuidedReview(mission?: MissionSummary | null): boolean {
  if (!mission) {
    return false;
  }
  return (
    mission.mode === "assessment" ||
    mission.mode === "guided_setup" ||
    mission.task_type === "foundation_speaking_drill" ||
    mission.task_type === "grammar_rescue"
  );
}

function buildMissionSessionConfig(
  mission: MissionSummary,
  returnScreen: Screen
): SessionConfig {
  const mode =
    mission.mode === "guided_setup"
      ? undefined
      : (mission.launch_mode ?? mission.mode);
  return {
    wsUrl: `${WS_BASE}/api/v1/voice/chat/v2`,
    mode,
    interviewTrackId: mission.interview_track_id ?? undefined,
    sttProvider: DEFAULT_STT_PROVIDER,
    title: mission.title,
    subtitle: mission.reason,
    reviewBeforeSend: shouldForceGuidedReview(mission),
    mission,
    returnScreen
  };
}

function readScreenFromHash(): Screen {
  const normalized = window.location.hash.replace("#", "");
  if (
    normalized === "session" ||
    normalized === "interview" ||
    normalized === "ml_technical" ||
    normalized === "review" ||
    normalized === "progress" ||
    normalized === "interview_results" ||
    normalized === "session_results"
  ) {
    return normalized as Screen;
  }
  return "home";
}

function App() {
  const [identity, setIdentity] = useState<TelegramIdentity | null>(null);
  const [identityError, setIdentityError] = useState<string | null>(null);
  const [userId, setUserId] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<ProgramSnapshot | null>(null);
  const [screen, setScreen] = useState<Screen>(readScreenFromHash());
  const [sessionConfig, setSessionConfig] = useState<SessionConfig>({
    wsUrl: `${WS_BASE}/api/v1/voice/chat/v2`,
    sttProvider: DEFAULT_STT_PROVIDER,
    reviewBeforeSend: false,
    returnScreen: "progress"
  });
  const [lastInterviewRun, setLastInterviewRun] = useState<InterviewRun | null>(
    null
  );
  const [lastSessionEvidence, setLastSessionEvidence] =
    useState<SessionEvidence | null>(null);
  const [lastMission, setLastMission] = useState<MissionSummary | null>(null);
  const [mlTechnicalReturnScreen, setMlTechnicalReturnScreen] =
    useState<"home" | "interview">("home");
  const [isReady, setIsReady] = useState(false);
  const [isResolvingUser, setIsResolvingUser] = useState(true);
  const [isLoadingSnapshot, setIsLoadingSnapshot] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;

    const resolved = resolveTelegramIdentity(
      tg?.initDataUnsafe?.user,
      import.meta.env.VITE_LOCAL_TELEGRAM_ID
    );
    setIdentity(resolved);
    setIdentityError(resolved ? null : IDENTITY_SETUP_ERROR);

    if (tg) {
      tg.ready();
      tg.expand();

      document.documentElement.style.setProperty(
        "--tg-theme-bg-color",
        tg.themeParams?.bg_color || "#ffffff"
      );
      document.documentElement.style.setProperty(
        "--tg-theme-text-color",
        tg.themeParams?.text_color || "#000000"
      );
      document.documentElement.style.setProperty(
        "--tg-theme-hint-color",
        tg.themeParams?.hint_color || "#999999"
      );
      document.documentElement.style.setProperty(
        "--tg-theme-button-color",
        tg.themeParams?.button_color || "#667eea"
      );
      document.documentElement.style.setProperty(
        "--tg-theme-button-text-color",
        tg.themeParams?.button_text_color || "#ffffff"
      );
      document.documentElement.style.setProperty(
        "--tg-theme-secondary-bg-color",
        tg.themeParams?.secondary_bg_color || "#f0f0f0"
      );

      console.log("Telegram WebApp initialized");
    } else {
      console.log("Running outside Telegram");
    }

    setIsReady(true);
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      setScreen(readScreenFromHash());
    };

    window.addEventListener("hashchange", onHashChange);
    return () => {
      window.removeEventListener("hashchange", onHashChange);
    };
  }, []);

  useEffect(() => {
    const nextHash = screen === "home" ? "" : `#${screen}`;
    if (window.location.hash !== nextHash) {
      window.location.hash = nextHash;
    }
  }, [screen]);

  useEffect(() => {
    if (!isReady) {
      return;
    }

    // Fail closed: without a validated external identity we never call the
    // resolution endpoint, so no accidental profile can be created.
    if (!identity) {
      setIsResolvingUser(false);
      setUserId(null);
      return;
    }

    let cancelled = false;

    async function resolveUser(current: TelegramIdentity) {
      setIsResolvingUser(true);
      setError(null);
      try {
        // External Telegram id in, canonical internal users.id out. Only the
        // internal id is passed to snapshots and WebSocket sessions.
        const resolved = await resolveOrCreateUser(
          current.telegramId,
          current.username
        );
        if (!cancelled) {
          setUserId(resolved.id);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to resolve user identity"
          );
        }
      } finally {
        if (!cancelled) {
          setIsResolvingUser(false);
        }
      }
    }

    void resolveUser(identity);
    return () => {
      cancelled = true;
    };
  }, [isReady, identity]);

  async function refreshSnapshot(): Promise<ProgramSnapshot | null> {
    if (!userId) {
      return null;
    }

    setIsLoadingSnapshot(true);
    setError(null);
    try {
      const data = await getProgramSnapshot(userId);
      setSnapshot(data);
      return data;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load program snapshot"
      );
      return null;
    } finally {
      setIsLoadingSnapshot(false);
    }
  }

  useEffect(() => {
    void refreshSnapshot();
  }, [userId]);

  useEffect(() => {
    if (
      screen === "home" ||
      screen === "progress" ||
      screen === "interview" ||
      screen === "ml_technical"
    ) {
      void refreshSnapshot();
    }
  }, [screen]);

  function startGuidedSession() {
    if (!snapshot) {
      return;
    }

    if (snapshot.mission.mode === "mock_interview") {
      const recommendedTrackId =
        snapshot.mission.interview_track_id ??
        snapshot.interview.recommended_track.id;
      const track: InterviewTrack = {
        id: recommendedTrackId,
        title: snapshot.mission.title,
        subtitle: snapshot.mission.reason,
        description: "",
        prompt_focus: "",
        starter_question: "",
        rubric_focus: [],
        recommended:
          recommendedTrackId === snapshot.interview.recommended_track.id,
        completed_runs: 0
      };
      startInterviewTrack(track);
      return;
    }

    if (snapshot.mission.mode === "guided_setup") {
      setSessionConfig(buildMissionSessionConfig(snapshot.mission, "home"));
      setScreen("session");
      return;
    }

    setSessionConfig(buildMissionSessionConfig(snapshot.mission, "progress"));
    setScreen("session");
  }

  function startInterviewTrack(track: InterviewTrack) {
    if (track.id === "ml_technical") {
      setMlTechnicalReturnScreen("interview");
      setScreen("ml_technical");
      return;
    }
    setSessionConfig({
      wsUrl: `${WS_BASE}/api/v1/voice/chat/v2`,
      mode: "mock_interview",
      interviewTrackId: track.id,
      sttProvider: DEFAULT_STT_PROVIDER,
      title: track.title,
      subtitle: track.subtitle,
      reviewBeforeSend: false,
      returnScreen: "interview"
    });
    setScreen("session");
  }

  async function handleSessionEnded(_payload: {
    sessionId: string | null;
    messages: Array<{ role: "user" | "assistant"; text: string }>;
    completionReason?: string;
    returnScreen?: Screen | string;
  }) {
    const fresh = await refreshSnapshot();
    const requestedReturnScreen =
      _payload.returnScreen === "home" ||
      _payload.returnScreen === "session" ||
      _payload.returnScreen === "interview" ||
      _payload.returnScreen === "ml_technical" ||
      _payload.returnScreen === "review" ||
      _payload.returnScreen === "progress" ||
      _payload.returnScreen === "interview_results" ||
      _payload.returnScreen === "session_results"
        ? _payload.returnScreen
        : undefined;
    if (_payload.completionReason === "baseline_complete") {
      setScreen(requestedReturnScreen ?? "home");
      return;
    }
    if (
      sessionConfig.mode === "mock_interview" &&
      fresh?.interview.latest_run
    ) {
      setLastInterviewRun(fresh.interview.latest_run);
      setLastMission(fresh.mission);
      setScreen("interview_results");
    } else if (fresh?.session_evidence.latest) {
      setLastSessionEvidence(fresh.session_evidence.latest);
      setLastMission(fresh.mission);
      setScreen("session_results");
    } else {
      setScreen(requestedReturnScreen ?? sessionConfig.returnScreen);
    }
  }

  if (!isReady) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }

  if (identityError) {
    return (
      <div className="empty-state-card">
        <h2>Profile not configured</h2>
        <p>{identityError}</p>
      </div>
    );
  }

  if (isResolvingUser || !userId) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <p>Resolving profile...</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <span className="header-kicker">Telegram Mini App</span>
          <h1>EnglishFriend</h1>
        </div>
        <div className="header-meta">
          <span>{snapshot?.user.username || identity?.username}</span>
          <span className="header-endpoint">{API_BASE}</span>
        </div>
      </header>

      {error && <div className="app-error">{error}</div>}

      <main
        className={`app-content ${
          screen === "session" ? "session-layout" : ""
        }`}
      >
        {isLoadingSnapshot && !snapshot ? (
          <div className="loading page-loading">
            <div className="loading-spinner"></div>
            <p>Loading your program...</p>
          </div>
        ) : null}

        {snapshot ? (
          <ErrorBoundary
            key={screen}
            onReset={() => {
              setScreen("home");
              void refreshSnapshot();
            }}
          >
            {screen === "home" && (
              <HomePage
                snapshot={snapshot}
                onStartSession={startGuidedSession}
                onOpenMlTechnical={() => {
                  setMlTechnicalReturnScreen("home");
                  setScreen("ml_technical");
                }}
                onOpenProgress={() => setScreen("progress")}
                onRefresh={() => {
                  void refreshSnapshot();
                }}
                onSubmitVacancy={async (vacancyText) => {
                  if (!userId) return;
                  try {
                    setError(null);
                    await submitVacancy(userId, { vacancy_text: vacancyText });
                    await refreshSnapshot();
                  } catch (err) {
                    setError(
                      err instanceof Error
                        ? err.message
                        : "Failed to save vacancy"
                    );
                  }
                }}
                onSubmitProjectNotes={async (projectNotes) => {
                  if (!userId) return;
                  try {
                    setError(null);
                    await submitProjectNotes(userId, {
                      project_notes: projectNotes
                    });
                    await refreshSnapshot();
                  } catch (err) {
                    setError(
                      err instanceof Error
                        ? err.message
                        : "Failed to save project notes"
                    );
                  }
                }}
                onSubmitPaidIntent={async () => {
                  if (!userId) return;
                  try {
                    setError(null);
                    const ctaSource =
                      snapshot?.monetization.cta_source || "generic";
                    const valueStage =
                      snapshot?.product_signals.value_stage || "unknown";
                    await submitPaidIntent(userId, {
                      source: `home_cta:${ctaSource}:${valueStage}`
                    });
                    await refreshSnapshot();
                  } catch (err) {
                    setError(
                      err instanceof Error
                        ? err.message
                        : "Failed to save paid beta intent"
                    );
                  }
                }}
              />
            )}
            {screen === "session" && (
              <VoiceChatV2
                userId={userId}
                wsUrl={sessionConfig.wsUrl}
                mode={sessionConfig.mode}
                interviewTrackId={sessionConfig.interviewTrackId}
                sttProvider={sessionConfig.sttProvider}
                mission={sessionConfig.mission}
                title={sessionConfig.title}
                subtitle={sessionConfig.subtitle}
                reviewBeforeSend={sessionConfig.reviewBeforeSend}
                onSessionEnded={(payload) => {
                  void handleSessionEnded(payload);
                }}
              />
            )}
            {screen === "interview" && (
              <InterviewPage
                userId={userId}
                onStartTrack={startInterviewTrack}
              />
            )}
            {screen === "ml_technical" && (
              <MlTechnicalPage
                userId={userId}
                onBack={() => setScreen(mlTechnicalReturnScreen)}
              />
            )}
            {screen === "interview_results" && lastInterviewRun && (
              <InterviewResultsPage
                run={lastInterviewRun}
                mission={lastMission ?? undefined}
                onRunAgain={() => {
                  const track: InterviewTrack = {
                    id: lastInterviewRun.track_id,
                    title: lastInterviewRun.track_title,
                    subtitle: lastInterviewRun.track_subtitle,
                    description: "",
                    prompt_focus: "",
                    starter_question: "",
                    rubric_focus: [],
                    recommended: false,
                    completed_runs: 0
                  };
                  startInterviewTrack(track);
                }}
                onBack={() => setScreen("interview")}
                onStartMission={() => {
                  if (!lastMission) return;
                  if (lastMission.mode === "mock_interview") {
                    setScreen("interview");
                  } else {
                    setSessionConfig(
                      buildMissionSessionConfig(lastMission, "progress")
                    );
                    setScreen("session");
                  }
                }}
              />
            )}
            {screen === "session_results" && lastSessionEvidence && (
              <SessionResultsPage
                evidence={lastSessionEvidence}
                mission={lastMission ?? undefined}
                onBack={() => setScreen("home")}
                onStartMission={() => {
                  if (!lastMission) return;
                  if (lastMission.mode === "mock_interview") {
                    setScreen("interview");
                    return;
                  }
                  setSessionConfig(
                    buildMissionSessionConfig(lastMission, "progress")
                  );
                  setScreen("session");
                }}
              />
            )}
            {screen === "review" && (
              <ReviewPage
                userId={userId}
                onReviewed={() => {
                  void refreshSnapshot();
                }}
              />
            )}
            {screen === "progress" && <ProgressPage snapshot={snapshot} />}
          </ErrorBoundary>
        ) : (
          <div className="empty-state-card">
            <h2>Program data unavailable</h2>
            <p>
              Could not load your snapshot yet. Try refreshing or open a session
              to bootstrap your profile.
            </p>
            <button
              className="primary-action"
              onClick={() => void refreshSnapshot()}
            >
              Retry
            </button>
          </div>
        )}
      </main>

      <nav className="bottom-nav">
        <button
          className={screen === "home" ? "nav-item active" : "nav-item"}
          onClick={() => setScreen("home")}
        >
          Home
        </button>
        {snapshot?.vocabulary?.stats?.due_now ? (
          <button
            className={screen === "review" ? "nav-item active" : "nav-item"}
            onClick={() => setScreen("review")}
          >
            Review
          </button>
        ) : null}
        {snapshot?.setup?.assessment_complete ? (
          <button
            className={screen === "progress" ? "nav-item active" : "nav-item"}
            onClick={() => setScreen("progress")}
          >
            Progress
          </button>
        ) : null}
        {snapshot?.setup?.state === "ready_for_program" ? (
          <button
            className={screen === "interview" ? "nav-item active" : "nav-item"}
            onClick={() => setScreen("interview")}
          >
            Career
          </button>
        ) : null}
      </nav>
    </div>
  );
}

export default App;
