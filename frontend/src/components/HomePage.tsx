import type { ProgramSnapshot } from '../lib/api';

interface HomePageProps {
  snapshot: ProgramSnapshot;
  onStartSession: () => void;
  onOpenReview: () => void;
  onOpenProgress: () => void;
  onRefresh: () => void;
}

export function HomePage({
  snapshot,
  onStartSession,
  onOpenReview,
  onOpenProgress,
  onRefresh,
}: HomePageProps) {
  const latestSession = snapshot.progress.recent_sessions[0];
  const xp = snapshot.gamification.xp;
  const streak = snapshot.gamification.streak;

  return (
    <div className="miniapp-page">
      <section className="hero-card">
        <div className="eyebrow">EnglishFriend</div>
        <h1>Career English coach for your next real conversation</h1>
        <p className="hero-copy">
          {snapshot.goal.text || 'Set a concrete goal to turn practice into a program.'}
        </p>
        <div className="hero-actions">
          <button className="primary-action" onClick={onStartSession}>
            Start 10-min mission
          </button>
          <button className="secondary-action" onClick={onRefresh}>
            Refresh
          </button>
        </div>
      </section>

      <section className="mission-card">
        <div className="section-label">Today&apos;s mission</div>
        <h2>{snapshot.mission.title}</h2>
        <p>{snapshot.mission.reason}</p>
        <div className="pill-row">
          <span className="pill">{snapshot.mission.mode.replace('_', ' ')}</span>
          {snapshot.assessment?.level && <span className="pill">CEFR {snapshot.assessment.level}</span>}
          <span className="pill">Level {xp.level}</span>
        </div>
      </section>

      <section className="stats-grid">
        <article className="stat-card">
          <span className="stat-label">XP</span>
          <strong>{xp.total_xp}</strong>
          <small>{Math.round(xp.progress * 100)}% to next level</small>
        </article>
        <article className="stat-card">
          <span className="stat-label">Streak</span>
          <strong>{streak.current} days</strong>
          <small>{streak.at_risk ? 'At risk today' : 'On track'}</small>
        </article>
        <article className="stat-card clickable" onClick={onOpenReview}>
          <span className="stat-label">Due words</span>
          <strong>{snapshot.vocabulary.stats.due_now}</strong>
          <small>Open review queue</small>
        </article>
        <article className="stat-card clickable" onClick={onOpenProgress}>
          <span className="stat-label">Sessions</span>
          <strong>{snapshot.progress.sessions_completed}</strong>
          <small>See progress</small>
        </article>
      </section>

      <section className="content-card">
        <div className="section-label">Current focus</div>
        <div className="list-stack">
          {snapshot.goal.focus_areas.length > 0 ? (
            snapshot.goal.focus_areas.map((focus) => (
              <div key={focus} className="list-item">
                {focus}
              </div>
            ))
          ) : (
            <div className="list-empty">No focus areas yet. Complete onboarding in a session.</div>
          )}
        </div>
      </section>

      <section className="content-card">
        <div className="section-row">
          <div>
            <div className="section-label">Vocabulary preview</div>
            <h3>Words already queued for reinforcement</h3>
          </div>
          <button className="link-action" onClick={onOpenReview}>
            Review
          </button>
        </div>
        <div className="list-stack">
          {snapshot.vocabulary.due_preview.length > 0 ? (
            snapshot.vocabulary.due_preview.map((card) => (
              <div key={card.id} className="list-item split">
                <div>
                  <strong>{card.word}</strong>
                  {card.translation && <span className="muted-line">{card.translation}</span>}
                </div>
                <span className="tiny-pill">due</span>
              </div>
            ))
          ) : (
            <div className="list-empty">No cards due right now.</div>
          )}
        </div>
      </section>

      <section className="content-card">
        <div className="section-label">Last session</div>
        {latestSession ? (
          <>
            <h3>{latestSession.duration_minutes ? `${latestSession.duration_minutes} min session` : 'Recent session'}</h3>
            <p>{latestSession.summary || 'Session completed. Open progress to inspect details.'}</p>
            <div className="pill-row">
              <span className="pill">{latestSession.corrections_count} corrections</span>
              <span className="pill">{new Date(latestSession.started_at).toLocaleDateString()}</span>
            </div>
          </>
        ) : (
          <div className="list-empty">No completed sessions yet.</div>
        )}
      </section>
    </div>
  );
}
