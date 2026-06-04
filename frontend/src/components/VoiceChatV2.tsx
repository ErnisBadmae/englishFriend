import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useVoskWithVAD } from '../hooks/useVoskWithVAD';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { useVoiceDebugSession } from '../hooks/useVoiceDebugSession';
import { transcribeVoiceAudio, type MissionSummary } from '../lib/api';
import { VoiceDebugPanel } from './VoiceDebugPanel';
import './VoiceChat.css';

interface VoiceChatV2Props {
  userId: number;
  wsUrl: string;
  mode?: string;
  interviewTrackId?: string;
  sttProvider?: string;
  mission?: MissionSummary;
  title?: string;
  subtitle?: string;
  reviewBeforeSend?: boolean;
  onSessionEnded?: (payload: {
    sessionId: string | null;
    messages: Array<{ role: 'user' | 'assistant'; text: string }>;
    completionReason?: string;
    returnScreen?: string;
  }) => void;
}

const GOAL_SETUP_CHIPS = [
  'ML engineer job abroad',
  'Interview English',
  'Project discussions',
  'Vocabulary for machine learning',
  'Global remote team',
  'Open-ended timeline',
];

const BASELINE_CHIPS = [
  'I work as a data analyst now',
  'I want to become an ML engineer',
  'One project is about predictions for users',
];

const FOUNDATION_CHIPS = [
  'I work as a data scientist',
  'My recent project was a recommendation model',
  'My next step is to improve grammar for project answers',
];

function mergeTranscriptDraft(previous: string, incoming: string): string {
  const next = incoming.trim();
  if (!next) {
    return previous;
  }
  const current = previous.trim();
  if (!current) {
    return next;
  }
  if (current.toLowerCase().includes(next.toLowerCase())) {
    return current;
  }
  return `${current} ${next}`.trim();
}

export function VoiceChatV2({
  userId,
  wsUrl,
  mode,
  interviewTrackId,
  sttProvider = 'browser_vosk',
  mission,
  title,
  subtitle,
  reviewBeforeSend = false,
  onSessionEnded,
}: VoiceChatV2Props) {
  const debugEnabled = import.meta.env.DEV;
  const missionTaskType = mission?.task_type || null;
  const missionTitle = mission?.title || null;
  const missionReason = mission?.reason || null;
  const missionSuccessSignal = mission?.success_signal || null;
  const missionLinkedGoalContext = mission?.linked_goal_context || null;
  const [draftText, setDraftText] = useState('');
  const [backendIsListening, setBackendIsListening] = useState(false);
  const [backendIsProcessing, setBackendIsProcessing] = useState(false);
  const [backendTranscript, setBackendTranscript] = useState('');
  const [backendError, setBackendError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaChunksRef = useRef<Blob[]>([]);
  const discardNextRecordingRef = useRef(false);
  const completionTimeoutRef = useRef<number | null>(null);
  const farewellTimeoutRef = useRef<number | null>(null);
  const latestPlaybackMetaRef = useRef<{ phase?: string; turnId?: string } | null>(null);
  const latestPlaybackActiveRef = useRef(false);
  const sendTextRef = useRef<(text: string, meta?: { source?: string }) => void>(() => {});
  const completionFlowRef = useRef<{
    active: boolean;
    finalized: boolean;
    endRequested: boolean;
    waitingForCurrentAudio: boolean;
    farewellTranscriptSeen: boolean;
    farewellAudioStarted: boolean;
    reason?: string;
    returnScreen?: string;
  }>({
    active: false,
    finalized: false,
    endRequested: false,
    waitingForCurrentAudio: false,
    farewellTranscriptSeen: false,
    farewellAudioStarted: false,
    reason: undefined,
    returnScreen: undefined,
  });
  const autoCompleteHandlerRef = useRef<(payload: {
    reason: string;
    returnScreen?: string;
  }) => void>(() => {});
  const latestMessagesRef = useRef<Array<{ role: 'user' | 'assistant'; text: string }>>([]);
  const latestSessionIdRef = useRef<string | null>(null);
  const latestListeningRef = useRef(false);
  const finalizeSessionRef = useRef<(source: string) => void>(() => {});
  const requestCompletionRef = useRef<(payload?: { reason?: string; returnScreen?: string; source?: string }) => void>(() => {});
  const isStrictMission = mission?.task_type === 'foundation_speaking_drill'
    || mission?.task_type === 'grammar_rescue';
  const usesBackendStt = sttProvider !== 'browser_vosk' && sttProvider !== 'composer';
  const debugSession = useVoiceDebugSession(debugEnabled);
  const {
    events: debugEvents,
    sessionMeta: debugSessionMeta,
    logEvent,
    setSessionMeta,
    clearEvents,
    copyJson,
    downloadJson,
  } = debugSession;

  const guidedReviewMode = useMemo(
    () => usesBackendStt || reviewBeforeSend || isStrictMission || mode === 'assessment' || mode === 'guided_setup' || !mode,
    [isStrictMission, mode, reviewBeforeSend, usesBackendStt]
  );

  const composerChips = useMemo(
    () => (
      isStrictMission
        ? FOUNDATION_CHIPS
        : mode === 'assessment'
          ? BASELINE_CHIPS
          : GOAL_SETUP_CHIPS
    ),
    [isStrictMission, mode]
  );
  const wsQuery = useMemo(
    () => ({
      mode,
      interview_track: interviewTrackId,
      mission_task_type: missionTaskType,
      mission_title: missionTitle,
      mission_reason: missionReason,
      mission_success_signal: missionSuccessSignal,
      mission_linked_goal_context: missionLinkedGoalContext,
      stt_provider: sttProvider,
    }),
    [
      interviewTrackId,
      missionLinkedGoalContext,
      missionReason,
      missionSuccessSignal,
      missionTaskType,
      missionTitle,
      mode,
      sttProvider,
    ]
  );
  useEffect(() => {
    setSessionMeta({
      userId,
      mode: mode || null,
      interviewTrackId: interviewTrackId || null,
      missionTaskType,
      missionTitle,
      missionReason,
      missionSuccessSignal,
      missionLinkedGoalContext,
      sttProvider,
      reviewBeforeSend: guidedReviewMode,
      wsUrl,
    });
    logEvent('session', 'session_config_initialized', {
      mode: mode || null,
      missionTaskType,
      sttProvider,
      reviewBeforeSend: guidedReviewMode,
    });
  }, [
    guidedReviewMode,
    interviewTrackId,
    logEvent,
    missionLinkedGoalContext,
    missionReason,
    missionSuccessSignal,
    missionTaskType,
    missionTitle,
    mode,
    setSessionMeta,
    sttProvider,
    userId,
    wsUrl,
  ]);

  const clearCompletionTimers = useCallback(() => {
    if (completionTimeoutRef.current !== null) {
      window.clearTimeout(completionTimeoutRef.current);
      completionTimeoutRef.current = null;
    }
    if (farewellTimeoutRef.current !== null) {
      window.clearTimeout(farewellTimeoutRef.current);
      farewellTimeoutRef.current = null;
    }
  }, []);

  const armCompletionFallback = useCallback((source: string, delayMs: number) => {
    if (farewellTimeoutRef.current !== null) {
      window.clearTimeout(farewellTimeoutRef.current);
    }
    farewellTimeoutRef.current = window.setTimeout(() => {
      logEvent('session', 'completion_fallback_triggered', {
        source,
        delayMs,
      });
      finalizeSessionRef.current(source);
    }, delayMs);
  }, [logEvent]);

  const handlePlaybackStart = useCallback((meta?: { phase?: string; turnId?: string }) => {
    latestPlaybackMetaRef.current = meta ?? null;
    latestPlaybackActiveRef.current = true;
    if (!latestMessagesRef.current.some((item) => item.role === 'user') && meta?.phase) {
      logEvent('session', 'initial_greeting_play_started', {
        phase: meta.phase,
        turnId: meta.turnId,
      });
    }
    const completion = completionFlowRef.current;
    if (!completion.active || meta?.phase !== 'session_end') {
      return;
    }

    completion.farewellAudioStarted = true;
    if (farewellTimeoutRef.current !== null) {
      window.clearTimeout(farewellTimeoutRef.current);
      farewellTimeoutRef.current = null;
    }
    logEvent('session', 'farewell_audio_started', {
      turnId: meta.turnId,
    });
  }, [logEvent]);

  const handlePlaybackEnd = useCallback((meta?: { phase?: string; turnId?: string }) => {
    latestPlaybackActiveRef.current = false;
    latestPlaybackMetaRef.current = null;
    if (!latestMessagesRef.current.some((item) => item.role === 'user') && meta?.phase) {
      logEvent('session', 'initial_greeting_play_ended', {
        phase: meta.phase,
        turnId: meta.turnId,
      });
    }

    const completion = completionFlowRef.current;
    if (!completion.active) {
      return;
    }

    if (completion.waitingForCurrentAudio && meta?.phase !== 'session_end') {
      completion.waitingForCurrentAudio = false;
      logEvent('session', 'completion_current_audio_finished');
      requestCompletionRef.current({ source: 'current_audio_finished' });
      return;
    }

    if (meta?.phase === 'session_end') {
      logEvent('session', 'farewell_audio_ended', {
        turnId: meta.turnId,
      });
      finalizeSessionRef.current('farewell_audio_ended');
    }
  }, [logEvent]);

  const handlePlaybackError = useCallback((playbackError: Error, meta?: { phase?: string; turnId?: string }) => {
    latestPlaybackActiveRef.current = false;
    latestPlaybackMetaRef.current = null;
    logEvent('audio', 'playback_flow_error', {
      message: playbackError.message,
      phase: meta?.phase,
      turnId: meta?.turnId,
    });
    if (completionFlowRef.current.active && meta?.phase === 'session_end') {
      armCompletionFallback('farewell_audio_failed', 400);
    }
  }, [armCompletionFallback, logEvent]);

  const handleWsConnect = useCallback(() => {
    console.log('[VoiceChatV2] Connected');
    logEvent('session', 'ws_connected_surface');
  }, [logEvent]);

  const handleWsMessage = useCallback((message: { role: 'user' | 'assistant'; text: string }, meta?: {
    phase?: string;
    mode?: string;
    runtime?: string;
    turnId?: string;
    turnIndex?: number;
  }) => {
    if (message.role !== 'assistant') {
      return;
    }

    if (!latestMessagesRef.current.some((item) => item.role === 'user')) {
      logEvent('session', 'initial_greeting_received', {
        phase: meta?.phase,
        turnId: meta?.turnId,
      });
    }

    const completion = completionFlowRef.current;
    if (!completion.active || meta?.phase !== 'session_end') {
      return;
    }

    completion.farewellTranscriptSeen = true;
    logEvent('session', 'farewell_transcript_seen', {
      turnId: meta?.turnId,
    });
    if (!completion.farewellAudioStarted) {
      armCompletionFallback('farewell_transcript_only', 2200);
    }
  }, [armCompletionFallback, logEvent]);

  const cleanupBackendCapture = useCallback(() => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.ondataavailable = null;
      mediaRecorderRef.current.onstop = null;
      mediaRecorderRef.current.onerror = null;
      mediaRecorderRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    mediaChunksRef.current = [];
  }, []);

  const handleBackendTranscription = useCallback(async (audioBlob: Blob) => {
    setBackendIsProcessing(true);
    setBackendError(null);
    setBackendTranscript('');
    try {
      const result = await transcribeVoiceAudio(
        userId,
        audioBlob,
        sttProvider,
        latestSessionIdRef.current
      );
      const text = result.text.trim();
      setBackendTranscript(text);
      logEvent('session', 'backend_stt_transcribed', {
        sttProvider,
        textPreview: text.slice(0, 120),
        charCount: text.length,
        confidence: result.confidence,
      });
      if (!text) {
        return;
      }
      if (guidedReviewMode) {
        setDraftText((previous) => mergeTranscriptDraft(previous, text));
        return;
      }
      sendTextRef.current(text, { source: sttProvider });
      setBackendTranscript('');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Backend transcription failed';
      setBackendError(message);
      logEvent('session', 'backend_stt_failed', {
        sttProvider,
        message,
      });
    } finally {
      setBackendIsProcessing(false);
    }
  }, [guidedReviewMode, logEvent, sttProvider, userId]);

  const stopBackendCapture = useCallback((discard = false) => {
    const recorder = mediaRecorderRef.current;
    discardNextRecordingRef.current = discard;
    setBackendIsListening(false);
    if (!recorder) {
      if (discard) {
        setBackendTranscript('');
      }
      cleanupBackendCapture();
      return;
    }
    if (recorder.state !== 'inactive') {
      recorder.stop();
      return;
    }
    cleanupBackendCapture();
  }, [cleanupBackendCapture]);

  const startBackendCapture = useCallback(async () => {
    if (backendIsListening || backendIsProcessing) {
      return;
    }
    setBackendError(null);
    setBackendTranscript('');
    discardNextRecordingRef.current = false;

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
    mediaStreamRef.current = stream;
    mediaChunksRef.current = [];

    const preferredMimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';
    const recorder = new MediaRecorder(stream, { mimeType: preferredMimeType });
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        mediaChunksRef.current.push(event.data);
      }
    };
    recorder.onerror = () => {
      setBackendError('Audio recording failed');
      setBackendIsListening(false);
      cleanupBackendCapture();
    };
    recorder.onstop = () => {
      const shouldDiscard = discardNextRecordingRef.current;
      discardNextRecordingRef.current = false;
      const chunks = [...mediaChunksRef.current];
      const mimeType = recorder.mimeType || preferredMimeType;
      cleanupBackendCapture();
      if (shouldDiscard || chunks.length === 0) {
        setBackendTranscript('');
        return;
      }
      void handleBackendTranscription(new Blob(chunks, { type: mimeType }));
    };

    recorder.start();
    setBackendIsListening(true);
    logEvent('session', 'backend_stt_capture_started', {
      sttProvider,
      mimeType: preferredMimeType,
    });
  }, [backendIsListening, backendIsProcessing, cleanupBackendCapture, handleBackendTranscription, logEvent, sttProvider]);

  const {
    isModelLoading,
    isModelLoaded,
    isListening,
    voiceStatus,
    transcript,
    silenceProgress,
    startListening,
    stopListening,
    cancelAndReset,
    confirmSend,
    error: voskError,
  } = useVoskWithVAD({
    enabled: !usesBackendStt,
    silenceTimeoutMs: guidedReviewMode ? 4000 : 2500,
    onFinalResult: (text) => {
      console.log('[VoiceChatV2] Final:', text);
    },
    onSilenceDetected: () => {
      console.log('[VoiceChatV2] Silence detected - ready to send');
    },
    onDebugEvent: logEvent,
  });

  const {
    isPlaying,
    isAudioReady,
    unlock,
    play,
    stop: stopAudio,
  } = useAudioPlayer({
    onDebugEvent: logEvent,
    onPlaybackStart: handlePlaybackStart,
    onPlaybackEnd: handlePlaybackEnd,
    onPlaybackError: handlePlaybackError,
  });
  const handleWsAudio = useCallback((audioData: ArrayBuffer, meta?: {
    phase?: string;
    mode?: string;
    turnId?: string;
    turnIndex?: number;
    runtime?: string;
  }) => {
    void play(audioData, meta);
  }, [play]);

  const {
    isConnected,
    isConnecting,
    sessionId,
    messages,
    sendText,
    connect,
    requestSessionEnd,
    disconnect,
    error: wsError,
  } = useWebSocket({
    url: wsUrl,
    userId,
    query: wsQuery,
    onMessage: handleWsMessage,
    onAudio: handleWsAudio,
    onConnect: handleWsConnect,
    onDisconnect: (payload) => {
      logEvent('session', 'ws_disconnect_surface', {
        code: payload.code,
        reason: payload.reason,
        manualClose: payload.manualClose,
        expectedServerClose: payload.expectedServerClose,
      });
      const completion = completionFlowRef.current;
      if (completion.active && !completion.finalized) {
        if (
          latestPlaybackActiveRef.current
          && latestPlaybackMetaRef.current?.phase === 'session_end'
        ) {
          logEvent('session', 'farewell_socket_closed_while_audio_playing');
          return;
        }
        finalizeSessionRef.current(payload.expectedServerClose ? 'session_end_socket_closed' : 'socket_closed');
      }
    },
    onSessionComplete: (payload) => {
      logEvent('session', 'session_complete_forwarded', payload);
      autoCompleteHandlerRef.current(payload);
    },
    onDebugEvent: logEvent,
  });

  const activeListening = usesBackendStt ? backendIsListening : isListening;
  const activeVoiceStatus = usesBackendStt
    ? (backendIsProcessing
      ? 'processing'
      : backendIsListening
        ? 'listening'
        : (backendTranscript.trim() || draftText.trim())
          ? 'ready_to_send'
          : 'idle')
    : voiceStatus;
  const activeTranscript = usesBackendStt ? backendTranscript : transcript;
  const speechRecognitionReady = usesBackendStt ? true : isModelLoaded;
  const speechRecognitionLoading = usesBackendStt ? false : isModelLoading;
  const error = backendError || voskError?.message || wsError;

  useEffect(() => {
    sendTextRef.current = sendText;
  }, [sendText]);

  useEffect(() => {
    requestCompletionRef.current = (payload) => {
      const completion = completionFlowRef.current;
      if (!completion.active) {
        completion.active = true;
        completion.finalized = false;
      }
      completion.reason = payload?.reason ?? completion.reason;
      completion.returnScreen = payload?.returnScreen ?? completion.returnScreen;

      if (latestListeningRef.current) {
        if (usesBackendStt) {
          stopBackendCapture(true);
        } else {
          cancelAndReset();
        }
      }

      if (completionTimeoutRef.current === null) {
        completionTimeoutRef.current = window.setTimeout(() => {
          logEvent('session', 'completion_timeout_triggered');
          finalizeSessionRef.current('completion_timeout');
        }, 9000);
      }

      if (latestPlaybackActiveRef.current && latestPlaybackMetaRef.current?.phase !== 'session_end') {
        completion.waitingForCurrentAudio = true;
        logEvent('session', 'completion_waiting_for_current_audio', {
          phase: latestPlaybackMetaRef.current?.phase,
        });
        return;
      }

      if (!completion.endRequested) {
        completion.endRequested = true;
        logEvent('session', 'end_requested', {
          source: payload?.source || 'session_complete',
        });
        requestSessionEnd();
      }
    };
  }, [cancelAndReset, logEvent, requestSessionEnd, stopBackendCapture, usesBackendStt]);

  useEffect(() => {
    finalizeSessionRef.current = (source: string) => {
      const completion = completionFlowRef.current;
      if (completion.finalized) {
        return;
      }

      completion.finalized = true;
      clearCompletionTimers();
      stopAudio();
      if (usesBackendStt) {
        stopBackendCapture(true);
      }
      disconnect({
        sendEnd: false,
        resetMessages: false,
        reason: 'Session finalized',
      });
      logEvent('session', 'redirect_triggered', {
        source,
        reason: completion.reason,
        returnScreen: completion.returnScreen,
      });
      const transcriptSnapshot = [...latestMessagesRef.current];
      window.setTimeout(() => {
        onSessionEnded?.({
          sessionId: latestSessionIdRef.current,
          messages: transcriptSnapshot,
          completionReason: completion.reason,
          returnScreen: completion.returnScreen,
        });
      }, debugEnabled ? 700 : 200);
    };
  }, [clearCompletionTimers, debugEnabled, disconnect, logEvent, onSessionEnded, stopAudio, stopBackendCapture, usesBackendStt]);

  useEffect(() => {
    autoCompleteHandlerRef.current = (payload) => {
      requestCompletionRef.current({
        reason: payload.reason,
        returnScreen: payload.returnScreen,
        source: 'session_complete',
      });
    };
  }, []);

  useEffect(() => {
    latestMessagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    latestSessionIdRef.current = sessionId;
    if (sessionId) {
      setSessionMeta({ sessionId });
    }
  }, [sessionId, setSessionMeta]);

  useEffect(() => {
    latestListeningRef.current = activeListening;
  }, [activeListening]);

  useEffect(() => {
    latestPlaybackActiveRef.current = isPlaying;
  }, [isPlaying]);

  useEffect(() => {
    setSessionMeta({
      latestDraftText: draftText || null,
      latestTranscriptPreview: activeTranscript || null,
      isListening: activeListening,
      voiceStatus: activeVoiceStatus,
      isAudioReady,
    });
  }, [activeListening, activeTranscript, activeVoiceStatus, draftText, isAudioReady, setSessionMeta]);

  useEffect(() => {
    if (usesBackendStt) {
      return;
    }
    if (voiceStatus !== 'ready_to_send' || !transcript.trim()) {
      return;
    }

    if (guidedReviewMode) {
      stopListening();
      setDraftText((previous) => mergeTranscriptDraft(previous, transcript));
      logEvent('session', 'guided_transcript_buffered', {
        textPreview: transcript.slice(0, 120),
        charCount: transcript.length,
      });
      return;
    }

    const text = confirmSend();
    if (text) {
      console.log('[VoiceChatV2] Auto-sending:', text);
      logEvent('session', 'voice_auto_send', {
        textPreview: text.slice(0, 120),
        charCount: text.length,
      });
      sendText(text, { source: 'browser_vosk' });
    }
  }, [voiceStatus, transcript, guidedReviewMode, stopListening, confirmSend, logEvent, sendText, usesBackendStt]);

  const handleSendGuidedDraft = useCallback(() => {
    const text = draftText.trim();
    if (!text) {
      return;
    }
    cancelAndReset();
    setDraftText('');
    setBackendTranscript('');
    logEvent('session', 'composer_send', {
      textPreview: text.slice(0, 120),
      charCount: text.length,
    });
    sendText(text, { source: 'composer' });
  }, [cancelAndReset, draftText, logEvent, sendText]);

  const handlePrimaryAction = useCallback(async () => {
    if (!isConnected) {
      logEvent('session', 'primary_action_connect');
      try {
        await unlock();
      } catch (err) {
        console.error('[VoiceChatV2] Failed to unlock audio:', err);
        logEvent('audio', 'audio_unlock_failed', {
          message: err instanceof Error ? err.message : 'unknown',
        });
      }
      connect();
      return;
    }

    if (usesBackendStt) {
      if (backendIsProcessing) {
        return;
      }
      if (backendIsListening) {
        stopBackendCapture(false);
        return;
      }
      if (draftText.trim()) {
        handleSendGuidedDraft();
        return;
      }
      try {
        await startBackendCapture();
        logEvent('session', 'listening_requested', {
          guidedReviewMode: true,
          sttProvider,
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to start recording';
        setBackendError(message);
        logEvent('audio', 'backend_capture_failed', { message, sttProvider });
      }
      return;
    }

    if (guidedReviewMode) {
      if (isListening) {
        stopListening();
        if (transcript.trim()) {
          setDraftText((previous) => mergeTranscriptDraft(previous, transcript));
          logEvent('session', 'guided_capture_finished', {
            textPreview: transcript.slice(0, 120),
            charCount: transcript.length,
          });
        }
        return;
      }

      if (draftText.trim()) {
        handleSendGuidedDraft();
        return;
      }

      if (!isModelLoaded) {
        console.log('[VoiceChatV2] Model not loaded yet');
        return;
      }

      try {
        await startListening();
        logEvent('session', 'listening_requested', {
          guidedReviewMode: true,
        });
      } catch (err) {
        console.error('[VoiceChatV2] Failed to start:', err);
      }
      return;
    }

    if (!isModelLoaded) {
      console.log('[VoiceChatV2] Model not loaded yet');
      return;
    }

    if (isListening) {
      const text = confirmSend();
      if (text) {
        console.log('[VoiceChatV2] Manual send:', text);
        logEvent('session', 'voice_manual_send', {
          textPreview: text.slice(0, 120),
          charCount: text.length,
        });
        sendText(text, { source: 'browser_vosk' });
      } else {
        cancelAndReset();
      }
      return;
    }

    try {
      await startListening();
      logEvent('session', 'listening_requested', {
        guidedReviewMode: false,
      });
    } catch (err) {
      console.error('[VoiceChatV2] Failed to start:', err);
    }
  }, [
    isModelLoaded,
    isConnected,
    guidedReviewMode,
    isListening,
    transcript,
    draftText,
    connect,
    unlock,
    logEvent,
    stopListening,
    handleSendGuidedDraft,
    startListening,
    confirmSend,
    sendText,
    cancelAndReset,
    backendIsListening,
    backendIsProcessing,
    setBackendError,
    startBackendCapture,
    stopBackendCapture,
    sttProvider,
    usesBackendStt,
  ]);

  const handleRetryGuided = useCallback(() => {
    if (usesBackendStt) {
      stopBackendCapture(true);
      setBackendTranscript('');
      setBackendError(null);
    } else {
      cancelAndReset();
    }
    setDraftText('');
  }, [cancelAndReset, stopBackendCapture, usesBackendStt]);

  const handleTypeInstead = useCallback(() => {
    const currentTranscript = activeTranscript.trim();
    if (activeListening) {
      if (usesBackendStt) {
        stopBackendCapture(true);
      } else {
        stopListening();
      }
    }
    if (currentTranscript) {
      setDraftText((previous) => mergeTranscriptDraft(previous, currentTranscript));
    }
    logEvent('session', 'type_instead_selected', {
      transcriptPreview: currentTranscript.slice(0, 120),
      transcriptChars: currentTranscript.length,
    });
    window.setTimeout(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(draftText.length, draftText.length);
    }, 0);
  }, [activeListening, activeTranscript, draftText.length, logEvent, stopBackendCapture, stopListening, usesBackendStt]);

  const handleInsertChip = useCallback((chip: string) => {
    setDraftText((previous) => mergeTranscriptDraft(previous, chip));
    logEvent('session', 'composer_chip_inserted', { chip });
    window.setTimeout(() => {
      textareaRef.current?.focus();
    }, 0);
  }, [logEvent]);

  const handleEndSession = useCallback(() => {
    if (activeListening) {
      if (usesBackendStt) {
        stopBackendCapture(true);
      } else {
        cancelAndReset();
      }
    }
    if (isListening && !usesBackendStt) {
      cancelAndReset();
    }
    logEvent('session', 'session_end_clicked', {
      messageCount: messages.length,
      sessionId,
    });
    requestCompletionRef.current({
      reason: 'manual_end',
      returnScreen: 'home',
      source: 'manual_end_button',
    });
  }, [activeListening, cancelAndReset, isListening, logEvent, messages.length, sessionId, stopBackendCapture, usesBackendStt]);

  useEffect(() => () => {
    clearCompletionTimers();
    stopAudio();
    if (usesBackendStt) {
      stopBackendCapture(true);
    }
  }, [clearCompletionTimers, stopAudio, stopBackendCapture, usesBackendStt]);

  const getStatusMessage = () => {
    if (speechRecognitionLoading) return 'Loading speech recognition...';
    if (!speechRecognitionReady && !usesBackendStt) return 'Failed to load model';
    if (isConnecting) return 'Connecting and preparing voice...';
    if (!isConnected) {
      return isAudioReady
        ? 'Tap Start session to hear the coach and begin.'
        : 'Tap Start session to unlock audio and begin.';
    }
    if (isPlaying) return 'Coach is speaking...';

    if (guidedReviewMode) {
      switch (activeVoiceStatus) {
        case 'listening':
          return usesBackendStt
            ? 'Recording. Tap again when the answer is complete.'
            : 'Listening. Short English is enough.';
        case 'thinking':
          return 'Pause detected. We will keep the transcript in the composer.';
        case 'ready_to_send':
          return usesBackendStt
            ? 'Transcript ready. Edit key words before sending.'
            : 'Transcript ready. Edit key words before sending.';
        case 'processing':
          return usesBackendStt
            ? 'Transcribing your audio...'
            : 'Coach is responding...';
        default:
          return draftText.trim()
            ? 'Edit the key words, then send.'
            : 'Say or type your answer.';
      }
    }

    switch (activeVoiceStatus) {
      case 'listening':
        return 'Listening... speak in English';
      case 'thinking':
        return 'Take your time to think...';
      case 'ready_to_send':
        return 'Sending...';
      case 'processing':
        return 'Mentor is thinking...';
      default:
        return 'Tap to start speaking';
    }
  };

  const getButtonClass = () => {
    let cls = 'voice-button-v2';
    if (activeListening) cls += ' listening';
    if (activeVoiceStatus === 'thinking') cls += ' thinking';
    if (activeVoiceStatus === 'ready_to_send') cls += ' ready';
    if (isPlaying) cls += ' playing';
    return cls;
  };

  const getPrimaryButtonText = () => {
    if (!isConnected) {
      return 'Start session';
    }
    if (guidedReviewMode) {
      if (activeListening) {
        return usesBackendStt ? 'Finish recording' : 'Finish capture';
      }
      if (draftText.trim()) {
        return 'Send';
      }
      return usesBackendStt ? 'Record' : 'Speak';
    }
    if (activeListening) {
      return activeVoiceStatus === 'thinking' ? 'Thinking...' : 'Tap to send';
    }
    return 'Start speaking';
  };

  const usesComposerInput = sttProvider === 'composer';
  const speechInputUnavailable = !usesComposerInput && !usesBackendStt && (!speechRecognitionReady || speechRecognitionLoading);

  const primaryDisabled = guidedReviewMode
    ? (!isConnected
      ? (isConnecting || speechInputUnavailable)
      : (isPlaying || backendIsProcessing || (!draftText.trim() && speechInputUnavailable)))
    : (!isConnected
      ? (isConnecting || speechInputUnavailable)
      : (speechInputUnavailable || isPlaying || backendIsProcessing));

  return (
    <div className="voice-chat">
      <div className="voice-chat-header">
        <h1>{guidedReviewMode ? 'EnglishFriend Coach' : 'English Mentor'}</h1>
        {title && <p className="voice-session-subtitle">{title}</p>}
        {subtitle && <p className="voice-session-subtitle">{subtitle}</p>}
        {guidedReviewMode && (
          <p className="voice-session-note">
            Say or type your answer. Short English is enough, and you can fix key words before sending.
          </p>
        )}
        <p className="status">{getStatusMessage()}</p>
        {error && <p className="error">{error}</p>}
      </div>

      <div className="voice-chat-messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <p>Hi! I am your English mentor.</p>
            <p className="hint">
              {guidedReviewMode
                ? 'Use voice or text. The goal is to keep meaning, not to speak perfectly.'
                : 'Tap the button and speak. I will wait if you need time to think.'}
            </p>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            <div className="message-content">{message.text}</div>
          </div>
        ))}

        {activeListening && (
          <div className={`message user current ${activeVoiceStatus}`}>
            <div className="message-content">
              {activeTranscript || '...'}
            </div>
            {silenceProgress > 0 && (
              <div className="silence-progress">
                <div
                  className="silence-progress-bar"
                  style={{ width: `${silenceProgress}%` }}
                />
              </div>
            )}
          </div>
        )}

        {activeVoiceStatus === 'processing' && (
          <div className="message assistant processing">
            <div className="message-content">
              <span className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </span>
            </div>
          </div>
        )}
      </div>

      {guidedReviewMode && (
        <div className="guided-composer-card">
          <div className="guided-composer-header">
            <strong>
              {mode === 'assessment'
                ? 'Answer composer'
                : isStrictMission
                  ? 'Mission composer'
                  : 'Goal composer'}
            </strong>
            <span>
              {mode === 'assessment'
                ? 'Keep only the important words. You can answer in simple English or mixed Russian and English.'
                : isStrictMission
                  ? 'Keep one short career answer. The coach should get your role, project, or next step without guessing.'
                  : 'Add the key words the coach must understand. Typing is normal if recognition is weak.'}
            </span>
          </div>
          <textarea
            ref={textareaRef}
            className="guided-composer-input"
            value={draftText}
            onChange={(event) => setDraftText(event.target.value)}
            rows={4}
            placeholder={mode === 'assessment'
              ? 'Type your short answer here if speech recognition is weak'
              : isStrictMission
                ? 'Type one short career answer here if speech recognition is weak'
                : 'Type your goal or key words here if speech recognition is weak'}
          />
          <div className="guided-chip-row">
            {composerChips.map((chip) => (
              <button
                key={chip}
                type="button"
                className="guided-chip-button"
                onClick={() => handleInsertChip(chip)}
              >
                {chip}
              </button>
            ))}
          </div>
          <div className="guided-secondary-actions">
            <button type="button" className="secondary-action guided-secondary-button" onClick={handleTypeInstead}>
              Type instead
            </button>
            <button type="button" className="secondary-action guided-secondary-button" onClick={handleRetryGuided}>
              Retry
            </button>
          </div>
        </div>
      )}

      <div className="voice-chat-controls-v2">
        <button
          className={getButtonClass()}
          onClick={() => void handlePrimaryAction()}
          disabled={primaryDisabled}
        >
          {activeListening ? (
            <>
              <span className="pulse-ring"></span>
              <span className="btn-icon">Mic</span>
              <span className="btn-text">{getPrimaryButtonText()}</span>
            </>
          ) : (
            <>
              <span className="btn-icon">
                {isConnected && guidedReviewMode && draftText.trim() ? 'Send' : 'Mic'}
              </span>
              <span className="btn-text">{getPrimaryButtonText()}</span>
            </>
          )}
        </button>

        {activeListening && (
          <button className="cancel-button" onClick={handleRetryGuided}>
            Cancel
          </button>
        )}
      </div>

      <div className="voice-chat-hint">
        {guidedReviewMode ? (
          <p>
            {draftText.trim()
              ? 'Check the key words, then send. If recognition is weak, type the important parts instead.'
              : 'Tap Speak, or type directly if Vosk misses too much.'}
          </p>
        ) : activeListening ? (
          <p>Take your time. I will wait 2.5 seconds of silence before responding.</p>
        ) : (
          <p>Speak naturally. I understand beginners and will help with mistakes.</p>
        )}
      </div>

      {isConnected && messages.length > 0 && (
        <div className="end-session-container">
          <button className="end-session-button" onClick={handleEndSession}>
            End Session and See Summary
          </button>
        </div>
      )}

      {debugEnabled && (
        <VoiceDebugPanel
          events={debugEvents}
          sessionMeta={debugSessionMeta}
          onCopyJson={copyJson}
          onDownloadJson={downloadJson}
          onClear={clearEvents}
        />
      )}
    </div>
  );
}
