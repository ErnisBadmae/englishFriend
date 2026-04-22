import { useState } from 'react';

import type { ProgramSnapshot } from '../lib/api';

interface HomePageProps {
  snapshot: ProgramSnapshot;
  onStartSession: () => void;
  onOpenProgress: () => void;
  onRefresh: () => void;
  onSubmitVacancy: (vacancyText: string) => Promise<void>;
  onSubmitProjectNotes: (projectNotes: string) => Promise<void>;
  onSubmitPaidIntent: () => Promise<void>;
}

export function HomePage({
  snapshot,
  onStartSession,
  onOpenProgress,
  onRefresh,
  onSubmitVacancy,
  onSubmitProjectNotes,
  onSubmitPaidIntent,
}: HomePageProps) {
  const [vacancyText, setVacancyText] = useState('');
  const [projectNotes, setProjectNotes] = useState('');
  const [isSubmittingVacancy, setIsSubmittingVacancy] = useState(false);
  const [isSubmittingProjectNotes, setIsSubmittingProjectNotes] = useState(false);
  const [isSubmittingPaidIntent, setIsSubmittingPaidIntent] = useState(false);
  const goalBrief = snapshot.goal.brief;
  const goalStatus = goalBrief?.status || null;
  const draftGoal = goalStatus === 'draft';
  const setupState = snapshot.setup.state;
  const setupIncomplete = snapshot.setup.needs_attention;
  const readyForProgram = setupState === 'ready_for_program';
  const needsFirstMission = setupState === 'needs_first_mission' || setupState === 'needs_assessment';
  const needsGoal = setupState === 'needs_goal';
  const earlySetup = needsGoal || needsFirstMission;
  const baselineStatus = snapshot.assessment?.status || (snapshot.assessment ? 'confirmed' : 'missing');
  const missionLabel = setupIncomplete ? 'Next step' : "Today's mission";
  const heroTitle = needsFirstMission
    ? 'Start your first useful mission'
    : needsGoal
      ? 'Complete your career English setup'
      : snapshot.program.title;
  const heroCopy = needsFirstMission
    ? 'The target is already clear enough. The first mission will produce a useful answer and the coach will infer a working baseline from real speaking.'
    : needsGoal
      ? 'Turn vague English practice into a concrete career target.'
      : (goalBrief?.summary || 'Turn vague English practice into a concrete career program.');
  const targetTitle = goalBrief?.target_role
    ? `${goalBrief.target_role}${draftGoal ? ' (draft)' : ''}`
    : goalBrief?.primary_goal
      ? `Draft target${draftGoal ? '' : ' (building)'}`
    : 'Career target not locked yet';
  const targetCopy = goalBrief?.primary_goal
    || (draftGoal
      ? 'The coach already has a draft career target and can move you into the first useful mission.'
      : 'The coach is still turning your goal into a concrete target.');
  const setupActionLabel = needsFirstMission
    ? 'Start first useful mission'
    : 'Continue setup';
  const showVacancyCard = readyForProgram;
  const careerContext = snapshot.career_context;
  const interviewPack = snapshot.interview_pack;
  const projectStoryPack = snapshot.project_story_pack;
  const showProjectStoryCard = readyForProgram && Boolean(interviewPack);
  const showPaidCta = snapshot.monetization.show_paid_cta || snapshot.monetization.paid_intent_submitted;

  async function handleVacancySubmit() {
    const trimmed = vacancyText.trim();
    if (!trimmed) {
      return;
    }
    setIsSubmittingVacancy(true);
    try {
      await onSubmitVacancy(trimmed);
      setVacancyText('');
    } finally {
      setIsSubmittingVacancy(false);
    }
  }

  async function handlePaidIntentSubmit() {
    setIsSubmittingPaidIntent(true);
    try {
      await onSubmitPaidIntent();
    } finally {
      setIsSubmittingPaidIntent(false);
    }
  }

  async function handleProjectNotesSubmit() {
    const trimmed = projectNotes.trim();
    if (!trimmed) {
      return;
    }
    setIsSubmittingProjectNotes(true);
    try {
      await onSubmitProjectNotes(trimmed);
      setProjectNotes('');
    } finally {
      setIsSubmittingProjectNotes(false);
    }
  }

  return (
    <div className="miniapp-page">
      <section className="hero-card">
        <div className="eyebrow">EnglishFriend</div>
        <h1>{heroTitle}</h1>
        <p className="hero-copy">{heroCopy}</p>
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
        <div className="pill-row" style={{ marginTop: 14 }}>
          <span className="pill">setup {snapshot.setup.progress}%</span>
          {snapshot.setup.next_question_type && <span className="pill">{snapshot.setup.next_question_type.replace(/_/g, ' ')}</span>}
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

      {earlySetup && (
        <section className="content-card">
          <div className="section-label">What happens next</div>
          <h2>{needsFirstMission ? 'The first mission comes before any standalone assessment' : 'The coach still needs a sharper target'}</h2>
          <p>
            {needsFirstMission
              ? 'You already have a draft target. The next session starts with a real guided task, and the coach will infer the working baseline from that answer instead of sending you into a separate exam.'
              : 'The next session will lock the role, company context, and speaking situations the program should optimize for.'}
          </p>
          {(goalBrief?.current_blockers?.length || goalBrief?.main_contexts?.length) ? (
            <div className="pill-row" style={{ marginTop: 12 }}>
              {(goalBrief?.current_blockers || []).slice(0, 2).map((item) => (
                <span key={item} className="pill">{item}</span>
              ))}
              {(goalBrief?.main_contexts || []).slice(0, 2).map((item) => (
                <span key={item} className="pill">{item.replace(/_/g, ' ')}</span>
              ))}
            </div>
          ) : null}
        </section>
      )}

      {showVacancyCard && (
        <section className="content-card">
          <div className="section-label">Target vacancy</div>
          <h2>{careerContext.vacancy_present ? 'Vacancy loaded' : 'Paste your target vacancy'}</h2>
          <p>
            {careerContext.vacancy_summary
              || 'A real vacancy sharpens the role, likely questions, key terms, and interview track.'}
          </p>
          <textarea
            className="text-area-input"
            rows={5}
            placeholder="Paste the job description here to make the interview plan more specific."
            value={vacancyText}
            onChange={(event) => setVacancyText(event.target.value)}
          />
          <div className="hero-actions">
            <button
              className="primary-action"
              onClick={() => void handleVacancySubmit()}
              disabled={isSubmittingVacancy || !vacancyText.trim()}
            >
              {isSubmittingVacancy ? 'Saving vacancy...' : 'Use this vacancy'}
            </button>
          </div>
          {careerContext.vacancy_present && (
            <div className="pill-row" style={{ marginTop: 12 }}>
              {careerContext.target_role && <span className="pill">{careerContext.target_role}</span>}
              {careerContext.company_type && <span className="pill">{careerContext.company_type.replace(/_/g, ' ')}</span>}
              {careerContext.target_market && <span className="pill">{careerContext.target_market.replace(/_/g, ' ')}</span>}
            </div>
          )}
        </section>
      )}

      <section className="mission-card">
        <div className="section-label">{missionLabel}</div>
        <h2>{snapshot.mission.title}</h2>
        {snapshot.mission.adaptation_reason && (
          <p className="muted-line">{snapshot.mission.adaptation_reason}</p>
        )}
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
          {snapshot.mission.repeat_vs_advance && snapshot.mission.repeat_vs_advance !== 'new' && (
            <span className="pill interview-source-pill">{snapshot.mission.repeat_vs_advance}</span>
          )}
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

      {!earlySetup && setupState !== 'needs_goal' && (
        <section className="content-card">
          <div className="section-label">Current baseline</div>
          <h2>
            {snapshot.assessment?.level
              ? `${snapshot.assessment.provisional ? 'Provisional ' : ''}CEFR ${snapshot.assessment.level}`
              : 'Baseline not measured yet'}
          </h2>
          <p>
            {snapshot.assessment
              ? `${snapshot.assessment.source === 'embedded_first_mission'
                ? 'This baseline was inferred from a real guided mission, not from a separate test.'
                : snapshot.assessment.provisional
                  ? 'This is a low-confidence first baseline, but it is enough to route your next mission.'
                  : 'The coach is routing from your measured baseline, not generic conversation.'} Goal readiness ${snapshot.assessment.goal_readiness}/10.`
              : 'Start the first useful mission and the coach will infer a working baseline from real speaking.'}
          </p>
          <div className="pill-row">
            <span className="pill">{snapshot.program.stage_label}</span>
            <span className="pill">{snapshot.program.time_horizon_days} days</span>
            <span className="pill">{baselineStatus.replace(/_/g, ' ')}</span>
            {goalBrief?.domain && <span className="pill">{goalBrief.domain.replace(/_/g, ' ')}</span>}
          </div>
        </section>
      )}

      {interviewPack && (
        <section className="content-card">
          <div className="section-label">Interview pack</div>
          <h2>{interviewPack.recommended_track_title || 'Target interview pack'}</h2>
          <p>{interviewPack.summary || 'A compact interview pack built from your goal, baseline, and latest evidence.'}</p>
          <div className="pill-row">
            {interviewPack.target_role && <span className="pill">{interviewPack.target_role}</span>}
            {interviewPack.recommended_track_title && <span className="pill interview-source-pill">{interviewPack.recommended_track_title}</span>}
            {careerContext.vacancy_present && <span className="pill">vacancy-based</span>}
          </div>
          <div className="list-stack mission-detail-stack">
            <div className="list-item">
              <strong>Must answer</strong>
              <p className="muted-line">{interviewPack.must_answer_questions[0]}</p>
            </div>
            <div className="list-item">
              <strong>Top blocker</strong>
              <p className="muted-line">{interviewPack.top_blockers[0] || 'Need one stronger answer to surface the main blocker.'}</p>
            </div>
            <div className="list-item">
              <strong>Key terms</strong>
              <div className="pill-row" style={{ marginTop: 10 }}>
                {interviewPack.key_terms.slice(0, 6).map((term) => (
                  <span key={term} className="pill">{term}</span>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {showProjectStoryCard && (
        <section className="content-card">
          <div className="section-label">Project story pack</div>
          <h2>{projectStoryPack ? 'Project story pack updated' : 'Add one project story'}</h2>
          <p>
            {projectStoryPack?.problem_statement
              || 'Paste rough notes about one project. The coach will turn them into an interview-ready story with problem, decision, metric, and weak spots.'}
          </p>
          <textarea
            className="text-area-input"
            rows={5}
            placeholder="Describe one project: problem, your contribution, technical choices, metrics, trade-offs, impact."
            value={projectNotes}
            onChange={(event) => setProjectNotes(event.target.value)}
          />
          <div className="hero-actions">
            <button
              className="primary-action"
              onClick={() => void handleProjectNotesSubmit()}
              disabled={isSubmittingProjectNotes || !projectNotes.trim()}
            >
              {isSubmittingProjectNotes ? 'Saving project story...' : 'Build project story pack'}
            </button>
          </div>
          {projectStoryPack && (
            <div className="list-stack mission-detail-stack" style={{ marginTop: 14 }}>
              <div className="list-item">
                <strong>Problem</strong>
                <p className="muted-line">{projectStoryPack.problem_statement}</p>
              </div>
              <div className="list-item">
                <strong>Approach</strong>
                <p className="muted-line">{projectStoryPack.approach_summary}</p>
              </div>
              <div className="list-item">
                <strong>Impact</strong>
                <p className="muted-line">{projectStoryPack.metrics_and_impact}</p>
              </div>
              <div className="list-item">
                <strong>Example answer</strong>
                <p className="muted-line">{projectStoryPack.english_example_answer}</p>
              </div>
              {projectStoryPack.weak_spots.length > 0 && (
                <div className="list-item">
                  <strong>Weak spots</strong>
                  <div className="pill-row" style={{ marginTop: 10 }}>
                    {projectStoryPack.weak_spots.map((item) => (
                      <span key={item} className="pill">{item}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
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

      {showPaidCta && (
        <section className="content-card">
          <div className="section-label">Paid beta</div>
          <h2>
            {snapshot.monetization.paid_intent_submitted
              ? 'Paid beta interest saved'
              : 'Unlock the full interview plan'}
          </h2>
          <p>
            {snapshot.monetization.paid_intent_submitted
              ? 'You already signaled willingness to pay. This is the metric we need to prove that interview outcome is valuable enough as a product.'
              : 'If this interview-prep loop already feels valuable, leave a paid-beta signal. The current goal is to prove real willingness to pay, not just engagement.'}
          </p>
          {!snapshot.monetization.paid_intent_submitted && (
            <div className="hero-actions">
              <button
                className="primary-action"
                onClick={() => void handlePaidIntentSubmit()}
                disabled={isSubmittingPaidIntent}
              >
                {isSubmittingPaidIntent ? 'Saving...' : 'Join paid beta'}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
