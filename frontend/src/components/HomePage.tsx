import type { ProgramSnapshot } from '../lib/api';

interface HomePageProps {
  snapshot: ProgramSnapshot;
  onStartSession: () => void;
  onOpenReview: () => void;
  onOpenProgress: () => void;
  onOpenInterview: () => void;
  onRefresh: () => void;
}

export function HomePage({
  snapshot,
  onStartSession,
  onOpenReview,
  onOpenProgress,
  onOpenInterview,
  onRefresh,
}: HomePageProps) {
  const latestSession = snapshot.progress.recent_sessions[0];
  const xp = snapshot.gamification.xp;
  const streak = snapshot.gamification.streak;
  const goalBrief = snapshot.goal.brief;
  const setupIncomplete = snapshot.setup.needs_attention;
  const missionLabel = setupIncomplete ? 'Next step' : "Today's mission";

  return (
    <div className="miniapp-page">
      <section className="hero-card">
        <div className="eyebrow">EnglishFriend</div>
        <h1>{snapshot.program.title}</h1>
        <p className="hero-copy">
          {goalBrief?.summary || 'Turn vague English practice into a concrete career program.'}
        </p>
        <div className="hero-actions">
          <button className="primary-action" onClick={onStartSession}>
            {setupIncomplete ? 'Continue setup' : "Start today's mission"}
          </button>
          <button className="secondary-action" onClick={onRefresh}>
            Refresh
          </button>
        </div>
      </section>

      <section className="content-card">
        <div className="section-label">Your target</div>
        <h2>{goalBrief?.target_role || 'Career target not locked yet'}</h2>
        <p>{goalBrief?.primary_goal || 'The coach is still turning your goal into a concrete target.'}</p>
        <div className="pill-row">
          {goalBrief?.target_market && <span className="pill">{goalBrief.target_market.replace(/_/g, ' ')}</span>}
          {goalBrief?.deadline_type && <span className="pill">{goalBrief.deadline_type.replace(/_/g, ' ')}</span>}
          {(goalBrief?.main_contexts || []).map((context) => (
            <span key={context} className="pill">{context.replace(/_/g, ' ')}</span>
          ))}
        </div>
      </section>

      <section className="mission-card">
        <div className="section-label">{missionLabel}</div>
        <h2>{snapshot.mission.title}</h2>
        <p>{snapshot.mission.reason}</p>
        {snapshot.mission.why_now && <p className="muted-line">{snapshot.mission.why_now}</p>}
        <div className="pill-row">
          <span className="pill">{snapshot.mission.mode.replace(/_/g, ' ')}</span>
          {snapshot.mission.linked_goal_context && (
            <span className="pill">{snapshot.mission.linked_goal_context.replace(/_/g, ' ')}</span>
          )}
          {snapshot.mission.from_interview && <span className="pill interview-source-pill">from last interview</span>}
        </div>
        {setupIncomplete && snapshot.goal.missing_fields.length > 0 && (
          <div className="pill-row" style={{ marginTop: 12 }}>
            {snapshot.goal.missing_fields.map((item) => (
              <span key={item} className="pill">{item}</span>
            ))}
          </div>
        )}
      </section>

      <section className="content-card">
        <div className="section-label">Current baseline</div>
        <h2>{snapshot.assessment?.level ? `CEFR ${snapshot.assessment.level}` : 'Baseline not measured yet'}</h2>
        <p>
          {snapshot.assessment
            ? `Goal readiness ${snapshot.assessment.goal_readiness}/10. The coach is routing from your measured baseline, not generic conversation.`
            : 'Complete the baseline so the coach can decide whether to focus on grammar, clarity, or career scenarios first.'}
        </p>
        <div className="pill-row">
          <span className="pill">{snapshot.program.stage_label}</span>
          <span className="pill">{snapshot.program.time_horizon_days} days</span>
          {goalBrief?.domain && <span className="pill">{goalBrief.domain.replace(/_/g, ' ')}</span>}
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
          <small>See trajectory</small>
        </article>
      </section>

      <section className="content-card">
        <div className="section-label">Program stage</div>
        <h2>{snapshot.program.stage_label}</h2>
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

      <section className="content-card">
        <div className="section-label">This week&apos;s focus</div>
        <div className="list-stack">
          {snapshot.program.weekly_focus.length > 0 ? (
            snapshot.program.weekly_focus.map((focus) => (
              <div key={focus} className="list-item">{focus}</div>
            ))
          ) : (
            <div className="list-empty">The coach will populate weekly focus after setup.</div>
          )}
        </div>
      </section>

      <section className="content-card">
        <div className="section-label">What blocks the goal now</div>
        <div className="list-stack">
          {snapshot.assessment?.critical_gaps?.length ? (
            snapshot.assessment.critical_gaps.map((gap) => (
              <div key={gap} className="list-item">{gap}</div>
            ))
          ) : goalBrief?.current_blockers?.length ? (
            goalBrief.current_blockers.map((gap) => (
              <div key={gap} className="list-item">{gap}</div>
            ))
          ) : (
            <div className="list-empty">The coach will surface the main blockers after setup and baseline.</div>
          )}
        </div>
      </section>

      <section className="content-card">
        <div className="section-row">
          <div>
            <div className="section-label">Career missions</div>
            <h3>
              {snapshot.interview.readiness_score
                ? `${snapshot.interview.readiness_score}/10 interview readiness`
                : snapshot.assessment?.goal_readiness
                  ? `${snapshot.assessment.goal_readiness}/10 goal readiness`
                : 'Unlock career missions'}
            </h3>
          </div>
          {!setupIncomplete && (
            <button className="link-action" onClick={onOpenInterview}>
              Open
            </button>
          )}
        </div>
        {snapshot.setup.assessment_complete ? (
          <p>
            {snapshot.interview.completed_runs
              ? `${snapshot.interview.completed_runs} runs completed. Recommended track: ${snapshot.interview.recommended_track.title}.`
              : `Recommended track: ${snapshot.interview.recommended_track.title}.`}
          </p>
        ) : (
          <p>Complete setup and baseline first. Then the coach will route you into interview and workplace missions with evidence.</p>
        )}
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
