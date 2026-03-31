import type { ProgramSnapshot } from '../lib/api';

interface ProgressPageProps {
  snapshot: ProgramSnapshot;
}

export function ProgressPage({ snapshot }: ProgressPageProps) {
  const readiness = snapshot.assessment?.goal_readiness;
  const skillAxes = snapshot.assessment?.skill_axes ?? {};
  const goalBrief = snapshot.goal.brief;

  return (
    <div className="miniapp-page">
      <section className="content-card">
        <div className="section-label">Target trajectory</div>
        <h1>
          {snapshot.assessment
            ? `CEFR ${snapshot.assessment.level}${readiness ? ` · readiness ${readiness}/10` : ''}`
            : 'No baseline yet'}
        </h1>
        <p>
          {snapshot.assessment
            ? 'The coach is now routing practice from a measured baseline toward your target role.'
            : 'Complete the baseline assessment to unlock a real program instead of generic practice.'}
        </p>
      </section>

      <section className="content-card">
        <div className="section-label">Target role</div>
        <h3>{goalBrief?.target_role || 'Not confirmed yet'}</h3>
        <p>{goalBrief?.summary || 'The coach is still clarifying the job target and context.'}</p>
        <div className="pill-row">
          {goalBrief?.target_market && <span className="pill">{goalBrief.target_market.replace(/_/g, ' ')}</span>}
          {goalBrief?.deadline_type && <span className="pill">{goalBrief.deadline_type.replace(/_/g, ' ')}</span>}
          {(goalBrief?.main_contexts || []).map((context) => (
            <span key={context} className="pill">{context.replace(/_/g, ' ')}</span>
          ))}
        </div>
      </section>

      <section className="content-card">
        <div className="section-label">Current stage</div>
        <h3>{snapshot.program.stage_label}</h3>
        <p>{snapshot.program.success_metric}</p>
        <div className="pill-row">
          {snapshot.program.stages.map((stage) => (
            <span key={stage.id} className={`pill ${stage.status === 'current' ? 'interview-source-pill' : ''}`}>
              {stage.label}
            </span>
          ))}
        </div>
        <p className="muted-line">Next milestone: {snapshot.program.next_milestone}</p>
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
        <div className="section-label">Skill axes</div>
        <div className="list-stack">
          {Object.keys(skillAxes).length > 0 ? (
            Object.entries(skillAxes).map(([label, value]) => (
              <div key={label} className="list-item split">
                <strong>{label.replace(/_/g, ' ')}</strong>
                <span className="tiny-pill">{value ?? '-'}</span>
              </div>
            ))
          ) : (
            <div className="list-empty">Skill axes will appear after the baseline assessment.</div>
          )}
        </div>
      </section>

      <section className="content-card">
        <div className="section-label">Top gaps right now</div>
        <div className="list-stack">
          {snapshot.assessment?.critical_gaps?.length ? (
            snapshot.assessment.critical_gaps.map((gap) => (
              <div key={gap} className="list-item">{gap}</div>
            ))
          ) : (
            <div className="list-empty">No critical gaps surfaced yet.</div>
          )}
        </div>
      </section>

      <section className="content-card">
        <div className="section-label">Interview trajectory</div>
        {snapshot.interview.recent_runs.length > 0 ? (
          <div className="list-stack">
            {snapshot.interview.recent_runs.slice(0, 3).map((run) => (
              <div key={run.id} className="list-item">
                <strong>{run.track_title}</strong>
                <span className="muted-line">
                  {new Date(run.recorded_at).toLocaleString()} · overall {run.scores.overall}/10
                </span>
                <p className="session-summary">{run.summary}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="list-empty">Interview runs will appear here after your first career mission.</div>
        )}
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
                <strong>{session.duration_minutes ? `${session.duration_minutes} min session` : 'Session'}</strong>
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
