import { useEffect, useState } from 'react';
import { HomePage } from './components/HomePage';
import { ProgressPage } from './components/ProgressPage';
import { ReviewPage } from './components/ReviewPage';
import { VoiceChatV2 } from './components/VoiceChatV2';
import { API_BASE, WS_BASE, getProgramSnapshot, resolveOrCreateUser, type ProgramSnapshot } from './lib/api';
import './App.css';

type Screen = 'home' | 'session' | 'review' | 'progress';

function readScreenFromHash(): Screen {
  const normalized = window.location.hash.replace('#', '');
  if (normalized === 'session' || normalized === 'review' || normalized === 'progress') {
    return normalized;
  }
  return 'home';
}

function App() {
  const [telegramId, setTelegramId] = useState<number>(1);
  const [telegramUsername, setTelegramUsername] = useState<string>('Local User');
  const [userId, setUserId] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<ProgramSnapshot | null>(null);
  const [screen, setScreen] = useState<Screen>(readScreenFromHash());
  const [isReady, setIsReady] = useState(false);
  const [isResolvingUser, setIsResolvingUser] = useState(true);
  const [isLoadingSnapshot, setIsLoadingSnapshot] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsUrl = `${WS_BASE}/api/v1/voice/chat`;

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

  async function refreshSnapshot() {
    if (!userId) {
      return;
    }

    setIsLoadingSnapshot(true);
    setError(null);
    try {
      const data = await getProgramSnapshot(userId);
      setSnapshot(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load program snapshot');
    } finally {
      setIsLoadingSnapshot(false);
    }
  }

  useEffect(() => {
    void refreshSnapshot();
  }, [userId]);

  useEffect(() => {
    if (screen === 'home') {
      void refreshSnapshot();
    }
  }, [screen]);

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
                onStartSession={() => setScreen('session')}
                onOpenReview={() => setScreen('review')}
                onOpenProgress={() => setScreen('progress')}
                onRefresh={() => {
                  void refreshSnapshot();
                }}
              />
            )}
            {screen === 'session' && <VoiceChatV2 userId={userId} wsUrl={wsUrl} />}
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
        <button className={screen === 'session' ? 'nav-item active' : 'nav-item'} onClick={() => setScreen('session')}>
          Session
        </button>
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
