import { useCallback, useEffect, useState } from 'react';

export interface VoiceDebugEvent {
  id: number;
  timestamp: string;
  source: string;
  event: string;
  data?: Record<string, unknown>;
}

export interface VoiceDebugSnapshot {
  exportedAt: string;
  session: Record<string, unknown>;
  events: VoiceDebugEvent[];
}

interface UseVoiceDebugSessionReturn {
  enabled: boolean;
  events: VoiceDebugEvent[];
  sessionMeta: Record<string, unknown>;
  logEvent: (source: string, event: string, data?: Record<string, unknown>) => void;
  setSessionMeta: (data: Record<string, unknown>) => void;
  clearEvents: () => void;
  copyJson: () => Promise<boolean>;
  downloadJson: () => void;
}

function buildSnapshot(
  sessionMeta: Record<string, unknown>,
  events: VoiceDebugEvent[],
): VoiceDebugSnapshot {
  return {
    exportedAt: new Date().toISOString(),
    session: sessionMeta,
    events,
  };
}

const LATEST_KEY = 'englishfriend.voiceDebug.latest';
const SESSION_KEY_PREFIX = 'englishfriend.voiceDebug.session.';

/** Drop debug snapshots from earlier sessions; only the current one is useful. */
function dropOtherSessionSnapshots(currentKey: string) {
  const stale: string[] = [];
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (key && key.startsWith(SESSION_KEY_PREFIX) && key !== currentKey) {
      stale.push(key);
    }
  }
  stale.forEach((key) => window.localStorage.removeItem(key));
}

/**
 * Debug capture must never break a session. It used to write the full snapshot
 * under two keys on every event and never clean up older sessions, so the
 * storage quota eventually threw mid-mission and took the screen down with it.
 */
function persistSnapshot(snapshot: VoiceDebugSnapshot, sessionMeta: Record<string, unknown>) {
  const sessionId = String(sessionMeta.sessionId || 'pending');
  const sessionKey = `${SESSION_KEY_PREFIX}${sessionId}`;
  const payload = JSON.stringify(snapshot);

  const write = () => {
    window.localStorage.setItem(sessionKey, payload);
    window.localStorage.setItem(LATEST_KEY, payload);
  };

  try {
    write();
  } catch {
    try {
      dropOtherSessionSnapshots(sessionKey);
      write();
    } catch {
      // Still no room: keep the session running without debug persistence.
      console.warn('[VoiceDebug] Snapshot not persisted: storage quota exceeded');
    }
  }
}

export function useVoiceDebugSession(enabled: boolean): UseVoiceDebugSessionReturn {
  const [events, setEvents] = useState<VoiceDebugEvent[]>([]);
  const [sessionMeta, setSessionMetaState] = useState<Record<string, unknown>>({});

  useEffect(() => {
    if (!enabled) {
      return;
    }
    persistSnapshot(buildSnapshot(sessionMeta, events), sessionMeta);
  }, [enabled, events, sessionMeta]);

  const logEvent = useCallback((source: string, event: string, data?: Record<string, unknown>) => {
    if (!enabled) {
      return;
    }

    setEvents((previous) => {
      const nextId = previous.length > 0 ? previous[previous.length - 1].id + 1 : 1;
      const next: VoiceDebugEvent = {
        id: nextId,
        timestamp: new Date().toISOString(),
        source,
        event,
        data,
      };
      return [...previous.slice(-399), next];
    });
  }, [enabled]);

  const setSessionMeta = useCallback((data: Record<string, unknown>) => {
    if (!enabled) {
      return;
    }

    setSessionMetaState((previous) => ({
      ...previous,
      ...data,
    }));
  }, [enabled]);

  const clearEvents = useCallback(() => {
    if (!enabled) {
      return;
    }
    setEvents([]);
  }, [enabled]);

  const copyJson = useCallback(async () => {
    if (!enabled) {
      return false;
    }

    const payload = JSON.stringify(buildSnapshot(sessionMeta, events), null, 2);
    try {
      await navigator.clipboard.writeText(payload);
      return true;
    } catch (error) {
      console.error('[VoiceDebug] Failed to copy JSON:', error);
      return false;
    }
  }, [enabled, events, sessionMeta]);

  const downloadJson = useCallback(() => {
    if (!enabled) {
      return;
    }

    const payload = JSON.stringify(buildSnapshot(sessionMeta, events), null, 2);
    const blob = new Blob([payload], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `voice-debug-${String(sessionMeta.sessionId || 'session')}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }, [enabled, events, sessionMeta]);

  return {
    enabled,
    events,
    sessionMeta,
    logEvent,
    setSessionMeta,
    clearEvents,
    copyJson,
    downloadJson,
  };
}
