import type { ProgramSnapshot } from '../lib/api';

interface ProgressPageProps {
  snapshot: ProgramSnapshot;
}

export function ProgressPage({ snapshot }: ProgressPageProps) {
  return (
    <div className="miniapp-page">
      <section className="content-card">
        <div className="section-label">Progress snapshot</div>
        <h1>{snapshot.assessment ? `CEFR ${snapshot.assessment.level}` : 'No baseline yet'}</h1>
        <p>
          {snapshot.assessment
            ? 'Your coach can now route practice based on a measured starting point.'
            : 'Complete one assessment session to unlock structured routing and progress tracking.'}
        </p>
      </section>

      <section className="stats-grid">
        <article className="stat-card">
          <span className="stat-label">Completed sessions</span>
          <strong>{snapshot.progress.sessions_completed}</strong>
        </article>
        <article className="stat-card">
          <span className="stat-label">Total words</span>
          <strong>{snapshot.vocabulary.stats.total}</strong>
        </article>
        <article className="stat-card">
          <span className="stat-label">Review state</span>
          <strong>{snapshot.vocabulary.stats.review}</strong>
        </article>
        <article className="stat-card">
          <span className="stat-label">Current streak</span>
          <strong>{snapshot.gamification.streak.current}</strong>
        </article>
      </section>

      <section className="content-card">
        <div className="section-label">Top error patterns</div>
        <div className="list-stack">
          {snapshot.progress.top_error_patterns.length > 0 ? (
            snapshot.progress.top_error_patterns.map((pattern) => (
              <div key={pattern.label} className="list-item split">
                <strong>{pattern.label}</strong>
                <span className="tiny-pill">{pattern.count}</span>
              </div>
            ))
          ) : (
            <div className="list-empty">No recurring error patterns recorded yet.</div>
          )}
        </div>
      </section>

      <section className="content-card">
        <div className="section-label">Milestones</div>
        <div className="list-stack">
          {snapshot.progress.milestones.length > 0 ? (
            snapshot.progress.milestones.map((milestone, index) => (
              <div key={`${String(milestone.name)}-${index}`} className="list-item">
                <strong>{String(milestone.name || 'Milestone')}</strong>
                <span className="muted-line">
                  {milestone.done
                    ? 'Completed'
                    : milestone.target
                      ? `${String(milestone.progress ?? milestone.count ?? 0)} / ${String(milestone.target)}`
                      : 'In progress'}
                </span>
              </div>
            ))
          ) : (
            <div className="list-empty">Milestones will appear after onboarding and goal confirmation.</div>
          )}
        </div>
      </section>

      <section className="content-card">
        <div className="section-label">Recent sessions</div>
        <div className="list-stack">
          {snapshot.progress.recent_sessions.length > 0 ? (
            snapshot.progress.recent_sessions.map((session) => (
              <div key={session.id} className="list-item">
                <strong>
                  {session.duration_minutes ? `${session.duration_minutes} min session` : 'Session'}
                </strong>
                <span className="muted-line">
                  {new Date(session.started_at).toLocaleString()} · {session.corrections_count} corrections
                </span>
                {session.summary && <p className="session-summary">{session.summary}</p>}
              </div>
            ))
          ) : (
            <div className="list-empty">No recent sessions yet.</div>
          )}
        </div>
      </section>
    </div>
  );
}
