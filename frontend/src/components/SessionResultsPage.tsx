import { type MissionSummary, type SessionEvidence } from '../lib/api';

interface SessionResultsPageProps {
  evidence: SessionEvidence;
  mission?: MissionSummary;
  onBack: () => void;
  onStartMission?: () => void;
}

export function SessionResultsPage({
  evidence,
  mission,
  onBack,
  onStartMission,
}: SessionResultsPageProps) {
  return (
    <div className="miniapp-page">
      <section className="hero-card session-results-hero">
        <div className="eyebrow">{evidence.mission_title}</div>
        <h1>Mission completed</h1>
        <p className="hero-copy">{evidence.summary}</p>
        <div className="pill-row">
          <span className="pill">{evidence.mission_type.replace(/_/g, ' ')}</span>
          {evidence.duration_minutes > 0 && (
            <span className="pill">{evidence.duration_minutes} min</span>
          )}
        </div>
      </section>

      <section className="content-card">
        <div className="section-label">What you trained</div>
        <h2>{evidence.what_was_trained}</h2>
        {evidence.main_issue && (
          <p className="muted-line">Main issue surfaced: {evidence.main_issue}</p>
        )}
      </section>

      {evidence.what_went_well.length > 0 && (
        <section className="content-card">
          <div className="section-label">What went well</div>
          <div className="list-stack">
            {evidence.what_went_well.slice(0, 3).map((item) => (
              <div key={item} className="list-item results-feedback-item results-strength">
                {item}
              </div>
            ))}
          </div>
        </section>
      )}

      {evidence.next_focus.length > 0 && (
        <section className="content-card">
          <div className="section-label">Focus next</div>
          <div className="list-stack">
            {evidence.next_focus.slice(0, 3).map((item) => (
              <div key={item} className="list-item results-feedback-item results-next-focus">
                {item}
              </div>
            ))}
          </div>
        </section>
      )}

      {evidence.evidence_signals.length > 0 && (
        <section className="content-card">
          <div className="section-label">Evidence</div>
          <div className="list-stack">
            {evidence.evidence_signals.slice(0, 3).map((item) => (
              <div key={item} className="list-item">
                {item}
              </div>
            ))}
          </div>
        </section>
      )}

      {mission && (
        <section className="mission-card">
          <div className="section-label">Recommended next step</div>
          <h2>{mission.title}</h2>
          <p>{mission.reason}</p>
          <p className="muted-line">{mission.success_signal}</p>
          {onStartMission && (
            <div className="hero-actions">
              <button className="primary-action" onClick={onStartMission}>
                Start next mission
              </button>
            </div>
          )}
        </section>
      )}

      <section className="content-card">
        <div className="hero-actions">
          <button className="primary-action" onClick={onBack}>
            Back home
          </button>
        </div>
      </section>
    </div>
  );
}
