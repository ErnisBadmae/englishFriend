import { useEffect, useState } from 'react';
import {
  getInterviewTracks,
  type InterviewRun,
  type InterviewSummary,
  type InterviewTrack,
} from '../lib/api';

const TRACK_WHAT_IT_TRAINS: Record<string, string> = {
  hr_intro: "STAR storytelling, concise motivation, and behavioral answers for HR rounds.",
  project_walkthrough: "Technical explanation, architecture trade-offs, and business impact framing.",
  workplace_communication: "Standup updates, blocker escalation, and stakeholder communication.",
};

const TRACK_WHAT_IS_EVALUATED: Record<string, string[]> = {
  hr_intro: ["Structure (STAR)", "Clarity", "Confidence"],
  project_walkthrough: ["Vocabulary", "Technical depth", "Impact framing"],
  workplace_communication: ["Brevity", "Clarity", "Professional tone"],
};

interface InterviewPageProps {
  userId: number;
  onStartTrack: (track: InterviewTrack) => void;
}

export function InterviewPage({ userId, onStartTrack }: InterviewPageProps) {
  const [tracks, setTracks] = useState<InterviewTrack[]>([]);
  const [summary, setSummary] = useState<InterviewSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadInterviewData() {
      setIsLoading(true);
      setError(null);
      try {
        const payload = await getInterviewTracks(userId);
        if (!cancelled) {
          setTracks(payload.tracks);
          setSummary(payload.summary);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load interview missions');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadInterviewData();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (isLoading) {
    return (
      <div className="miniapp-page center-page">
        <p>Loading interview missions...</p>
      </div>
    );
  }

  return (
    <div className="miniapp-page">
      <section className="content-card">
        <div className="section-label">Career loop</div>
        <h1>
          {summary?.readiness_score ? `Readiness ${summary.readiness_score}/10` : 'Build interview readiness'}
        </h1>
        <p>
          {summary?.completed_runs
            ? `Completed ${summary.completed_runs} interview runs. Trend: ${summary.trend.replace('_', ' ')}.`
            : 'Pick one focused mission and build evidence from real spoken answers.'}
        </p>
      </section>

      {error && <div className="inline-error">{error}</div>}

      <section className="content-card">
        <div className="section-row">
          <div>
            <div className="section-label">Recommended mission</div>
            <h3>{summary?.recommended_track.title || 'Interview mission'}</h3>
          </div>
          {summary?.recommended_track && (
            <button
              className="primary-action"
              onClick={() => {
                const track = tracks.find((item) => item.id === summary.recommended_track.id);
                if (track) {
                  onStartTrack(track);
                }
              }}
            >
              Start
            </button>
          )}
        </div>
        {summary?.recommended_track && <p>{summary.recommended_track.subtitle}</p>}
      </section>

      <section className="content-card">
        <div className="section-label">Tracks</div>
        <div className="list-stack">
          {tracks.map((track) => (
            <article key={track.id} className="list-item interview-track-card">
              <div className="section-row">
                <div>
                  <strong>{track.title}</strong>
                  <span className="muted-line">{track.subtitle}</span>
                </div>
                <div className="track-badge-group">
                  {track.recommended && <span className="tiny-pill">recommended</span>}
                  {track.completed_runs > 0 && (
                    <span className="tiny-pill">{track.completed_runs} runs</span>
                  )}
                </div>
              </div>
              {TRACK_WHAT_IT_TRAINS[track.id] && (
                <p className="track-description">{TRACK_WHAT_IT_TRAINS[track.id]}</p>
              )}
              <div className="section-label" style={{ marginTop: 8 }}>What is evaluated</div>
              <div className="pill-row">
                {(TRACK_WHAT_IS_EVALUATED[track.id] ?? track.rubric_focus.slice(0, 3)).map((item) => (
                  <span key={`${track.id}-${item}`} className="pill">
                    {item.replace('_', ' ')}
                  </span>
                ))}
              </div>
              {summary?.recent_runs.some((r) => r.track_id === track.id) && (
                <p className="muted-line">
                  Best score:{' '}
                  {Math.max(
                    ...summary.recent_runs
                      .filter((r) => r.track_id === track.id)
                      .map((r) => r.scores.overall),
                  ).toFixed(1)}/10
                </p>
              )}
              <button className="primary-action" onClick={() => onStartTrack(track)}>
                Start this mission
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="content-card">
        <div className="section-label">Recent runs</div>
        <div className="list-stack">
          {summary?.recent_runs.length ? (
            summary.recent_runs.slice(0, 4).map((run) => (
              <InterviewRunCard key={run.id} run={run} />
            ))
          ) : (
            <div className="list-empty">No interview history yet.</div>
          )}
        </div>
      </section>
    </div>
  );
}

function InterviewRunCard({ run }: { run: InterviewRun }) {
  return (
    <div className="list-item">
      <div className="section-row">
        <strong>{run.track_title}</strong>
        <span className="tiny-pill">{run.scores.overall}/10</span>
      </div>
      <span className="muted-line">{new Date(run.recorded_at).toLocaleString()}</span>
      <p className="session-summary">{run.summary}</p>
    </div>
  );
}
