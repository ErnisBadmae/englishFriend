import { type InterviewRun, type MissionSummary } from '../lib/api';

interface InterviewResultsPageProps {
  run: InterviewRun;
  mission?: MissionSummary;
  onRunAgain: () => void;
  onBack: () => void;
  onStartMission?: () => void;
}

export function InterviewResultsPage({ run, mission, onRunAgain, onBack, onStartMission }: InterviewResultsPageProps) {
  const delta = run.delta_vs_previous;
  const deltaLabel =
    delta === null || delta === undefined
      ? null
      : delta > 0
        ? `+${delta}`
        : `${delta}`;
  const deltaClass =
    delta === null || delta === undefined
      ? ''
      : delta > 0
        ? 'delta-positive'
        : delta < 0
          ? 'delta-negative'
          : 'delta-neutral';

  const subScores: Array<{ key: keyof typeof run.scores; label: string }> = [
    { key: 'clarity', label: 'Clarity' },
    { key: 'structure', label: 'Structure' },
    { key: 'accuracy', label: 'Accuracy' },
    { key: 'vocabulary', label: 'Vocabulary' },
    { key: 'confidence', label: 'Confidence' },
  ];
  const pronunciationSourceLabel =
    run.pronunciation?.assessment_mode === 'text_heuristic'
      ? 'text-based estimate'
      : run.pronunciation?.provider || 'speech assessment';

  return (
    <div className="miniapp-page">
      {/* Hero score card */}
      <section className="hero-card interview-results-hero">
        <div className="eyebrow">{run.track_title}</div>
        <div className="results-score-row">
          <span className="results-score">{run.scores.overall.toFixed(1)}</span>
          <span className="results-score-denom">/10</span>
          {deltaLabel && (
            <span className={`results-delta ${deltaClass}`}>{deltaLabel}</span>
          )}
        </div>
        <p className="hero-copy">{run.track_subtitle}</p>
      </section>

      {/* Summary */}
      {run.summary && (
        <section className="content-card">
          <div className="section-label">Summary</div>
          <p>{run.summary}</p>
        </section>
      )}

      {/* Score breakdown */}
      <section className="content-card">
        <div className="section-label">Score breakdown</div>
        <div className="stats-grid">
          {subScores.map(({ key, label }) => (
            <div key={key} className="stat-card">
              <span className="stat-label">{label}</span>
              <strong>{run.scores[key].toFixed(1)}</strong>
            </div>
          ))}
        </div>
      </section>

      {/* Strengths */}
      {run.strengths.length > 0 && (
        <section className="content-card">
          <div className="section-label">What went well</div>
          <div className="list-stack">
            {run.strengths.slice(0, 3).map((s, i) => (
              <div key={i} className="list-item results-feedback-item results-strength">
                {s}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Rubric notes */}
      {run.rubric_notes && run.rubric_notes.length > 0 && (
        <section className="content-card">
          <div className="section-label">Rubric notes</div>
          <div className="list-stack">
            {run.rubric_notes.slice(0, 3).map((note, i) => (
              <div key={i} className="list-item results-feedback-item">
                {note}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Next focus */}
      {run.next_focus.length > 0 && (
        <section className="content-card">
          <div className="section-label">Focus next</div>
          <div className="list-stack">
            {run.next_focus.slice(0, 3).map((f, i) => (
              <div key={i} className="list-item results-feedback-item results-next-focus">
                {f}
              </div>
            ))}
          </div>
        </section>
      )}

      {run.pronunciation && (
        <section className="content-card">
          <div className="section-label">Speech feedback</div>
          <h3>{run.pronunciation.overall_score.toFixed(1)}/10 speech signal</h3>
          <p>{run.pronunciation.notes}</p>
          <div className="pill-row">
            <span className="pill">{pronunciationSourceLabel}</span>
            <span className="pill">{run.pronunciation.confidence.toFixed(2)} confidence</span>
          </div>
          <div className="stats-grid">
            <div className="stat-card">
              <span className="stat-label">Accuracy</span>
              <strong>{run.pronunciation.accuracy_score.toFixed(1)}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Fluency</span>
              <strong>{run.pronunciation.fluency_score.toFixed(1)}</strong>
            </div>
          </div>
          <div className="list-stack">
            {run.pronunciation.recommended_focus.slice(0, 3).map((item) => (
              <div key={item} className="list-item results-feedback-item results-next-focus">
                {item}
              </div>
            ))}
            {!run.pronunciation.recommended_focus.length && run.pronunciation.word_feedback.slice(0, 3).map((item) => (
              <div key={`${item.word}-${item.issue}`} className="list-item results-feedback-item">
                <strong>{item.word}</strong>: {item.tip}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Recommended next step */}
      {mission && (
        <section className="mission-card">
          <div className="section-label">Recommended next step</div>
          <h2>{mission.title}</h2>
          <p>{mission.reason}</p>
          {onStartMission && (
            <div className="hero-actions">
              <button className="primary-action" onClick={onStartMission}>
                Start now
              </button>
            </div>
          )}
        </section>
      )}

      {/* CTAs */}
      <section className="content-card">
        <div className="hero-actions">
          <button className="primary-action" onClick={onRunAgain}>
            Try again
          </button>
          <button className="primary-action" onClick={onBack}>
            Interview hub
          </button>
        </div>
      </section>
    </div>
  );
}
