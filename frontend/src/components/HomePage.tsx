import type { ProgramSnapshot } from '../lib/api';

interface HomePageProps {
  snapshot: ProgramSnapshot;
  onStartSession: () => void;
  onOpenProgress: () => void;
  onRefresh: () => void;
}

export function HomePage({
  snapshot,
  onStartSession,
  onOpenProgress,
  onRefresh,
}: HomePageProps) {
  const goalBrief = snapshot.goal.brief;
  const goalStatus = goalBrief?.status || null;
  const draftGoal = goalStatus === 'draft';
  const setupState = snapshot.setup.state;
  const setupIncomplete = snapshot.setup.needs_attention;
  const readyForProgram = setupState === 'ready_for_program';
  const needsAssessment = setupState === 'needs_assessment';
  const missionLabel = setupIncomplete ? 'Next step' : "Today's mission";
  const targetTitle = goalBrief?.target_role
    ? `${goalBrief.target_role}${draftGoal ? ' (draft)' : ''}`
    : 'Career target not locked yet';
  const targetCopy = goalBrief?.primary_goal
    || (draftGoal
      ? 'The coach already has a draft career target and can move you into baseline assessment.'
      : 'The coach is still turning your goal into a concrete target.');
  const setupActionLabel = snapshot.setup.state === 'needs_assessment'
    ? 'Take baseline assessment'
    : 'Continue setup';

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
            {setupIncomplete ? setupActionLabel : "Start today's mission"}
          </button>
          {readyForProgram ? (
            <button className="secondary-action" onClick={onOpenProgress}>
              Review progress
            </button>
          ) : (
            <button className="secondary-action" onClick={onRefresh}>
              Refresh
            </button>
          )}
        </div>
      </section>

      <section className="content-card">
        <div className="section-label">Your target</div>
        <h2>{targetTitle}</h2>
        <p>{targetCopy}</p>
        <div className="pill-row">
          {draftGoal && <span className="pill interview-source-pill">draft target</span>}
          {goalBrief?.target_market && <span className="pill">{goalBrief.target_market.replace(/_/g, ' ')}</span>}
          {goalBrief?.deadline_type && <span className="pill">{goalBrief.deadline_type.replace(/_/g, ' ')}</span>}
          {(goalBrief?.main_contexts || []).map((context) => (
            <span key={context} className="pill">{context.replace(/_/g, ' ')}</span>
          ))}
        </div>
      </section>

      {needsAssessment && (
        <section className="content-card">
          <div className="section-label">Why baseline matters</div>
          <h2>One quick speaking baseline first</h2>
          <p>
            The coach already has a usable draft target. One short baseline is enough to decide
            whether your first program stage should focus on grammar, clarity, vocabulary, or
            career scenarios.
          </p>
          <div className="pill-row">
            {(goalBrief?.main_contexts || []).slice(0, 3).map((context) => (
              <span key={context} className="pill">{context.replace(/_/g, ' ')}</span>
            ))}
          </div>
        </section>
      )}

      <section className="mission-card">
        <div className="section-label">{missionLabel}</div>
        <h2>{snapshot.mission.title}</h2>
        <p>{snapshot.mission.reason}</p>
        {snapshot.mission.why_now && <p className="muted-line">{snapshot.mission.why_now}</p>}
        <div className="pill-row">
          <span className="pill">{snapshot.mission.mode.replace(/_/g, ' ')}</span>
          <span className="pill">{snapshot.mission.task_type.replace(/_/g, ' ')}</span>
          <span className="pill">{snapshot.mission.estimated_minutes} min</span>
          {snapshot.mission.linked_goal_context && (
            <span className="pill">{snapshot.mission.linked_goal_context.replace(/_/g, ' ')}</span>
          )}
          {snapshot.mission.from_interview && <span className="pill interview-source-pill">from last interview</span>}
        </div>
        <div className="list-stack mission-detail-stack">
          <div className="list-item">
            <strong>Expected outcome</strong>
            <p className="muted-line">{snapshot.mission.expected_outcome}</p>
          </div>
          <div className="list-item">
            <strong>Success signal</strong>
            <p className="muted-line">{snapshot.mission.success_signal}</p>
          </div>
        </div>
        {setupIncomplete && snapshot.goal.missing_fields.length > 0 && (
          <>
            <p className="muted-line" style={{ marginTop: 12 }}>Need to confirm:</p>
            <div className="pill-row" style={{ marginTop: 12 }}>
              {snapshot.goal.missing_fields.map((item) => (
                <span key={item} className="pill">{item}</span>
              ))}
            </div>
          </>
        )}
      </section>

      {setupState !== 'needs_goal' && (
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
      )}

      {readyForProgram && (
        <section className="content-card">
          <div className="section-label">Current stage</div>
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
      )}

      {needsAssessment && (
        <section className="content-card">
          <div className="section-label">What we will optimize first</div>
          <div className="list-stack">
            {goalBrief?.current_blockers?.length ? (
              goalBrief.current_blockers.slice(0, 3).map((item) => (
                <div key={item} className="list-item">{item}</div>
              ))
            ) : (
              <div className="list-item">Turn your goal into a useful baseline, then route the first career mission.</div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
