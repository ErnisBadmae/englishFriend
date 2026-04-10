import { useState } from 'react';
import type { VoiceDebugEvent } from '../hooks/useVoiceDebugSession';

interface VoiceDebugPanelProps {
  events: VoiceDebugEvent[];
  sessionMeta: Record<string, unknown>;
  onCopyJson: () => Promise<boolean>;
  onDownloadJson: () => void;
  onClear: () => void;
}

function stringifyPreview(data?: Record<string, unknown>): string {
  if (!data) {
    return '';
  }
  const raw = JSON.stringify(data);
  return raw.length > 220 ? `${raw.slice(0, 220)}...` : raw;
}

export function VoiceDebugPanel({
  events,
  sessionMeta,
  onCopyJson,
  onDownloadJson,
  onClear,
}: VoiceDebugPanelProps) {
  const [copyState, setCopyState] = useState<'idle' | 'done' | 'failed'>('idle');

  return (
    <details className="voice-debug-panel">
      <summary>Dev Debug ({events.length})</summary>
      <div className="voice-debug-panel-body">
        <div className="voice-debug-actions">
          <button type="button" className="guided-chip-button" onClick={() => {
            void onCopyJson().then((ok) => {
              setCopyState(ok ? 'done' : 'failed');
              window.setTimeout(() => setCopyState('idle'), 1800);
            });
          }}>
            {copyState === 'done' ? 'Copied' : copyState === 'failed' ? 'Copy failed' : 'Copy JSON'}
          </button>
          <button type="button" className="guided-chip-button" onClick={onDownloadJson}>
            Download JSON
          </button>
          <button type="button" className="guided-chip-button" onClick={onClear}>
            Clear
          </button>
        </div>

        <pre className="voice-debug-meta">
          {JSON.stringify(sessionMeta, null, 2)}
        </pre>

        <div className="voice-debug-events">
          {[...events].reverse().map((event) => (
            <div key={event.id} className="voice-debug-event">
              <div className="voice-debug-event-header">
                <strong>#{event.id}</strong>
                <span>{event.timestamp}</span>
                <span>{event.source}</span>
                <span>{event.event}</span>
              </div>
              {event.data && (
                <pre className="voice-debug-event-body">{stringifyPreview(event.data)}</pre>
              )}
            </div>
          ))}
        </div>
      </div>
    </details>
  );
}
