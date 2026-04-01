import type { ProgramSnapshot } from '../lib/api';

interface ProgressPageProps {
  snapshot: ProgramSnapshot;
}

export function ProgressPage({ snapshot }: ProgressPageProps) {
  const goalBrief = snapshot.goal.brief;
  const draftGoal = goalBrief?.status === 'draft';
  const hasBaseline = snapshot.setup.assessment_complete && Boolean(snapshot.assessment);
  const readiness = snapshot.assessment?.goal_readiness;
  const latestEvidence = snapshot.session_evidence.latest;

  return (
    <div className="miniapp-page">
      <section className="content-card">
        <div className="section-label">Target</div>
        <h1>
          {goalBrief?.target_role
            ? `${goalBrief.target_role}${draftGoal ? ' (draft)' : ''}`
            : 'Career target still being clarified'}
        </h1>
        <p>
          {goalBrief?.summary
            || 'The coach will turn your goal into a concrete career path before daily practice becomes more advanced.'}
        </p>
        <div className="pill-row">
          {draftGoal && <span className="pill interview-source-pill">draft target</span>}
          {goalBrief?.target_market && <span className="pill">{goalBrief.target_market.replace(/_/g, ' ')}</span>}
          {goalBrief?.deadline_type && <span className="pill">{goalBrief.deadline_type.replace(/_/g, ' ')}</span>}
          {(goalBrief?.main_contexts || []).slice(0, 3).map((context) => (
            <span key={context} className="pill">{context.replace(/_/g, ' ')}</span>
          ))}
        </div>
      </section>

      {!hasBaseline ? (
        <section className="content-card">
          <div className="section-label">Progress unlock</div>
          <h2>Baseline needed first</h2>
          <p>
            Progress becomes useful after one baseline assessment. Until then, the coach is still
            locking your target and deciding what should be trained first.
          </p>
          <div className="pill-row">
            <span className="pill">{snapshot.setup.state.replace(/_/g, ' ')}</span>
            <span className="pill">{snapshot.program.stage_label}</span>
          </div>
        </section>
      ) : (
        <>
          <section className="content-card">
            <div className="section-label">Current readiness</div>
            <h2>
              CEFR {snapshot.assessment?.level}
              {readiness != null ? ` · readiness ${readiness}/10` : ''}
            </h2>
            <p>
              {snapshot.program.success_metric}
            </p>
            <div className="pill-row">
              <span className="pill">{snapshot.program.stage_label}</span>
              <span className="pill">{snapshot.program.time_horizon_days} days</span>
              {goalBrief?.domain && <span className="pill">{goalBrief.domain.replace(/_/g, ' ')}</span>}
            </div>
          </section>

          <section className="content-card">
            <div className="section-label">What improved</div>
            <div className="list-stack">
              {snapshot.progress.improvement_signals.length > 0 ? (
                snapshot.progress.improvement_signals.slice(0, 4).map((signal) => (
                  <div key={signal} className="list-item">{signal}</div>
                ))
              ) : (
                <div className="list-empty">Finish a few guided missions to start building proof of progress.</div>
              )}
            </div>
          </section>

          <section className="content-card">
            <div className="section-label">What still blocks the goal</div>
            <div className="list-stack">
              {snapshot.assessment?.critical_gaps?.length ? (
                snapshot.assessment.critical_gaps.slice(0, 4).map((gap) => (
                  <div key={gap} className="list-item">{gap}</div>
                ))
              ) : (
                <div className="list-empty">No major blockers surfaced yet.</div>
              )}
            </div>
          </section>

          <section className="content-card">
            <div className="section-label">Latest evidence</div>
            {latestEvidence ? (
              <div className="list-stack">
                <div className="list-item">
                  <strong>{latestEvidence.mission_title}</strong>
                  <span className="muted-line">
                    {new Date(latestEvidence.recorded_at).toLocaleString()} · {latestEvidence.duration_minutes} min
                  </span>
                  <p className="session-summary">{latestEvidence.summary}</p>
                </div>
                {latestEvidence.next_focus.slice(0, 2).map((item) => (
                  <div key={item} className="list-item results-next-focus">{item}</div>
                ))}
              </div>
            ) : (
              <div className="list-empty">Finish one guided mission to see concrete evidence here.</div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
