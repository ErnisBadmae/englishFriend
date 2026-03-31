import { useEffect, useState } from 'react';
import { HomePage } from './components/HomePage';
import { InterviewPage } from './components/InterviewPage';
import { InterviewResultsPage } from './components/InterviewResultsPage';
import { ProgressPage } from './components/ProgressPage';
import { ReviewPage } from './components/ReviewPage';
import { VoiceChatV2 } from './components/VoiceChatV2';
import {
  API_BASE,
  WS_BASE,
  getProgramSnapshot,
  resolveOrCreateUser,
  type InterviewRun,
  type InterviewTrack,
  type MissionSummary,
  type ProgramSnapshot,
} from './lib/api';
import './App.css';

type Screen = 'home' | 'session' | 'interview' | 'review' | 'progress' | 'interview_results';

interface SessionConfig {
  wsUrl: string;
  mode?: string;
  interviewTrackId?: string;
  title?: string;
  subtitle?: string;
  returnScreen: Screen;
}

function readScreenFromHash(): Screen {
  const normalized = window.location.hash.replace('#', '');
  if (
    normalized === 'session'
    || normalized === 'interview'
    || normalized === 'review'
    || normalized === 'progress'
    || normalized === 'interview_results'
  ) {
    return normalized as Screen;
  }
  return 'home';
}

function App() {
  const [telegramId, setTelegramId] = useState<number>(1);
  const [telegramUsername, setTelegramUsername] = useState<string>('Local User');
  const [userId, setUserId] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<ProgramSnapshot | null>(null);
  const [screen, setScreen] = useState<Screen>(readScreenFromHash());
  const [sessionConfig, setSessionConfig] = useState<SessionConfig>({
    wsUrl: `${WS_BASE}/api/v1/voice/chat`,
    returnScreen: 'progress',
  });
  const [lastInterviewRun, setLastInterviewRun] = useState<InterviewRun | null>(null);
  const [lastMission, setLastMission] = useState<MissionSummary | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [isResolvingUser, setIsResolvingUser] = useState(true);
  const [isLoadingSnapshot, setIsLoadingSnapshot] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;

    if (tg) {
      tg.ready();
      tg.expand();

      const tgUser = tg.initDataUnsafe?.user;
      if (tgUser?.id) {
        setTelegramId(tgUser.id);
        setTelegramUsername(tgUser.username || tgUser.first_name || `tg_${tgUser.id}`);
        console.log('Telegram user ID:', tgUser.id);
      }

      document.documentElement.style.setProperty(
        '--tg-theme-bg-color',
        tg.themeParams?.bg_color || '#ffffff'
      );
      document.documentElement.style.setProperty(
        '--tg-theme-text-color',
        tg.themeParams?.text_color || '#000000'
      );
      document.documentElement.style.setProperty(
        '--tg-theme-hint-color',
        tg.themeParams?.hint_color || '#999999'
      );
      document.documentElement.style.setProperty(
        '--tg-theme-button-color',
        tg.themeParams?.button_color || '#667eea'
      );
      document.documentElement.style.setProperty(
        '--tg-theme-button-text-color',
        tg.themeParams?.button_text_color || '#ffffff'
      );
      document.documentElement.style.setProperty(
        '--tg-theme-secondary-bg-color',
        tg.themeParams?.secondary_bg_color || '#f0f0f0'
      );

      console.log('Telegram WebApp initialized');
    } else {
      console.log('Running outside Telegram');
    }

    setIsReady(true);
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      setScreen(readScreenFromHash());
    };

    window.addEventListener('hashchange', onHashChange);
    return () => {
      window.removeEventListener('hashchange', onHashChange);
    };
  }, []);

  useEffect(() => {
    const nextHash = screen === 'home' ? '' : `#${screen}`;
    if (window.location.hash !== nextHash) {
      window.location.hash = nextHash;
    }
  }, [screen]);

  useEffect(() => {
    if (!isReady) {
      return;
    }

    let cancelled = false;

    async function resolveUser() {
      setIsResolvingUser(true);
      setError(null);
      try {
        const resolved = await resolveOrCreateUser(telegramId, telegramUsername);
        if (!cancelled) {
          setUserId(resolved.id);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to resolve user identity');
        }
      } finally {
        if (!cancelled) {
          setIsResolvingUser(false);
        }
      }
    }

    void resolveUser();
    return () => {
      cancelled = true;
    };
  }, [isReady, telegramId, telegramUsername]);

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
      setError(err instanceof Error ? err.message : 'Failed to load program snapshot');
      return null;
    } finally {
      setIsLoadingSnapshot(false);
    }
  }

  useEffect(() => {
    void refreshSnapshot();
  }, [userId]);

  useEffect(() => {
    if (screen === 'home' || screen === 'progress' || screen === 'interview') {
      void refreshSnapshot();
    }
  }, [screen]);

  function startGuidedSession() {
    if (!snapshot) {
      return;
    }

    if (snapshot.mission.mode === 'mock_interview') {
      const recommendedTrackId = snapshot.mission.interview_track_id ?? snapshot.interview.recommended_track.id;
      const track: InterviewTrack = {
        id: recommendedTrackId,
        title: snapshot.mission.title,
        subtitle: snapshot.mission.reason,
        description: '',
        prompt_focus: '',
        starter_question: '',
        rubric_focus: [],
        recommended: recommendedTrackId === snapshot.interview.recommended_track.id,
        completed_runs: 0,
      };
      startInterviewTrack(track);
      return;
    }

    if (snapshot.mission.mode === 'guided_setup') {
      setSessionConfig({
        wsUrl: `${WS_BASE}/api/v1/voice/chat`,
        title: snapshot.mission.title,
        subtitle: snapshot.mission.reason,
        returnScreen: 'home',
      });
      setScreen('session');
      return;
    }

    setSessionConfig({
      wsUrl: `${WS_BASE}/api/v1/voice/chat`,
      mode: snapshot.mission.launch_mode ?? snapshot.mission.mode,
      title: snapshot.mission.title,
      subtitle: snapshot.mission.reason,
      returnScreen: 'progress',
    });
    setScreen('session');
  }

  function startInterviewTrack(track: InterviewTrack) {
    setSessionConfig({
      wsUrl: `${WS_BASE}/api/v1/voice/chat`,
      mode: 'mock_interview',
      interviewTrackId: track.id,
      title: track.title,
      subtitle: track.subtitle,
      returnScreen: 'interview',
    });
    setScreen('session');
  }

  async function handleSessionEnded(_payload: {
    sessionId: string | null;
    messages: Array<{ role: 'user' | 'assistant'; text: string }>;
  }) {
    const fresh = await refreshSnapshot();
    if (sessionConfig.mode === 'mock_interview' && fresh?.interview.latest_run) {
      setLastInterviewRun(fresh.interview.latest_run);
      setLastMission(fresh.mission);
      setScreen('interview_results');
    } else {
      setScreen(sessionConfig.returnScreen);
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
          <span>{snapshot?.user.username || telegramUsername}</span>
          <span className="header-endpoint">{API_BASE}</span>
        </div>
      </header>

      {error && <div className="app-error">{error}</div>}

      <main className={`app-content ${screen === 'session' ? 'session-layout' : ''}`}>
        {isLoadingSnapshot && !snapshot ? (
          <div className="loading page-loading">
            <div className="loading-spinner"></div>
            <p>Loading your program...</p>
          </div>
        ) : null}

        {snapshot ? (
          <>
            {screen === 'home' && (
              <HomePage
                snapshot={snapshot}
                onStartSession={startGuidedSession}
                onOpenInterview={() => setScreen('interview')}
                onOpenReview={() => setScreen('review')}
                onOpenProgress={() => setScreen('progress')}
                onRefresh={() => {
                  void refreshSnapshot();
                }}
              />
            )}
            {screen === 'session' && (
              <VoiceChatV2
                userId={userId}
                wsUrl={sessionConfig.wsUrl}
                mode={sessionConfig.mode}
                interviewTrackId={sessionConfig.interviewTrackId}
                title={sessionConfig.title}
                subtitle={sessionConfig.subtitle}
                onSessionEnded={(payload) => {
                  void handleSessionEnded(payload);
                }}
              />
            )}
            {screen === 'interview' && (
              <InterviewPage
                userId={userId}
                onStartTrack={startInterviewTrack}
              />
            )}
            {screen === 'interview_results' && lastInterviewRun && (
              <InterviewResultsPage
                run={lastInterviewRun}
                mission={lastMission ?? undefined}
                onRunAgain={() => {
                  const track: InterviewTrack = {
                    id: lastInterviewRun.track_id,
                    title: lastInterviewRun.track_title,
                    subtitle: lastInterviewRun.track_subtitle,
                    description: '',
                    prompt_focus: '',
                    starter_question: '',
                    rubric_focus: [],
                    recommended: false,
                    completed_runs: 0,
                  };
                  startInterviewTrack(track);
                }}
                onBack={() => setScreen('interview')}
                onStartMission={() => {
                  if (!lastMission) return;
                  if (lastMission.mode === 'mock_interview') {
                    setScreen('interview');
                  } else {
                    setSessionConfig({
                      wsUrl: `${WS_BASE}/api/v1/voice/chat`,
                      mode: lastMission.launch_mode ?? undefined,
                      title: lastMission.title,
                      subtitle: lastMission.reason,
                      returnScreen: 'progress',
                    });
                    setScreen('session');
                  }
                }}
              />
            )}
            {screen === 'review' && (
              <ReviewPage
                userId={userId}
                onReviewed={() => {
                  void refreshSnapshot();
                }}
              />
            )}
            {screen === 'progress' && <ProgressPage snapshot={snapshot} />}
          </>
        ) : (
          <div className="empty-state-card">
            <h2>Program data unavailable</h2>
            <p>Could not load your snapshot yet. Try refreshing or open a session to bootstrap your profile.</p>
            <button className="primary-action" onClick={() => void refreshSnapshot()}>
              Retry
            </button>
          </div>
        )}
      </main>

      <nav className="bottom-nav">
        <button className={screen === 'home' ? 'nav-item active' : 'nav-item'} onClick={() => setScreen('home')}>
          Home
        </button>
        {snapshot?.setup?.assessment_complete ? (
          <button className={screen === 'interview' ? 'nav-item active' : 'nav-item'} onClick={() => setScreen('interview')}>
            Career
          </button>
        ) : null}
        <button className={screen === 'review' ? 'nav-item active' : 'nav-item'} onClick={() => setScreen('review')}>
          Review
        </button>
        <button className={screen === 'progress' ? 'nav-item active' : 'nav-item'} onClick={() => setScreen('progress')}>
          Progress
        </button>
      </nav>
    </div>
  );
}

export default App;
