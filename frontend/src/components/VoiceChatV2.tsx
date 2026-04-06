import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useVoskWithVAD } from '../hooks/useVoskWithVAD';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import type { MissionSummary } from '../lib/api';
import './VoiceChat.css';

interface VoiceChatV2Props {
  userId: number;
  wsUrl: string;
  mode?: string;
  interviewTrackId?: string;
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
  mission,
  title,
  subtitle,
  reviewBeforeSend = false,
  onSessionEnded,
}: VoiceChatV2Props) {
  const [draftText, setDraftText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const autoCompletionHandledRef = useRef(false);
  const autoCompleteHandlerRef = useRef<(payload: {
    reason: string;
    returnScreen?: string;
  }) => void>(() => {});
  const latestMessagesRef = useRef<Array<{ role: 'user' | 'assistant'; text: string }>>([]);
  const latestSessionIdRef = useRef<string | null>(null);
  const latestListeningRef = useRef(false);
  const isStrictMission = mission?.task_type === 'foundation_speaking_drill'
    || mission?.task_type === 'grammar_rescue';

  const guidedReviewMode = useMemo(
    () => reviewBeforeSend || isStrictMission || mode === 'assessment' || mode === 'guided_setup' || !mode,
    [isStrictMission, mode, reviewBeforeSend]
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
      mission_task_type: mission?.task_type,
      mission_title: mission?.title,
      mission_reason: mission?.reason,
      mission_success_signal: mission?.success_signal,
      mission_linked_goal_context: mission?.linked_goal_context,
    }),
    [mode, interviewTrackId, mission]
  );
  const forwardSessionComplete = useCallback((payload: {
    reason: string;
    returnScreen?: string;
  }) => {
    autoCompleteHandlerRef.current(payload);
  }, []);
  const handleWsConnect = useCallback(() => {
    console.log('[VoiceChatV2] Connected');
  }, []);

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
    silenceTimeoutMs: guidedReviewMode ? 4000 : 2500,
    onFinalResult: (text) => {
      console.log('[VoiceChatV2] Final:', text);
    },
    onSilenceDetected: () => {
      console.log('[VoiceChatV2] Silence detected - ready to send');
    },
  });

  const { isPlaying, play } = useAudioPlayer();
  const handleWsAudio = useCallback((audioData: ArrayBuffer) => {
    play(audioData);
  }, [play]);

  const {
    isConnected,
    isConnecting,
    sessionId,
    messages,
    sendText,
    connect,
    disconnect,
    error: wsError,
  } = useWebSocket({
    url: wsUrl,
    userId,
    query: wsQuery,
    onAudio: handleWsAudio,
    onConnect: handleWsConnect,
    onSessionComplete: forwardSessionComplete,
  });

  useEffect(() => {
    autoCompleteHandlerRef.current = (payload) => {
      if (autoCompletionHandledRef.current) {
        return;
      }
      autoCompletionHandledRef.current = true;
      const transcriptSnapshot = [...latestMessagesRef.current];
      if (latestListeningRef.current) {
        cancelAndReset();
      }
      disconnect({ resetMessages: false });
      window.setTimeout(() => {
        onSessionEnded?.({
          sessionId: latestSessionIdRef.current,
          messages: transcriptSnapshot,
          completionReason: payload.reason,
          returnScreen: payload.returnScreen,
        });
      }, 900);
    };
  }, [cancelAndReset, disconnect, onSessionEnded]);

  useEffect(() => {
    latestMessagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    latestSessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    latestListeningRef.current = isListening;
  }, [isListening]);

  useEffect(() => {
    if (!isModelLoaded || isConnected || isConnecting) {
      return;
    }

    const timer = window.setTimeout(() => {
      connect();
    }, 150);

    return () => {
      window.clearTimeout(timer);
    };
  }, [isModelLoaded, isConnected, isConnecting, connect]);

  useEffect(() => {
    if (voiceStatus !== 'ready_to_send' || !transcript.trim()) {
      return;
    }

    if (guidedReviewMode) {
      stopListening();
      setDraftText((previous) => mergeTranscriptDraft(previous, transcript));
      return;
    }

    const text = confirmSend();
    if (text) {
      console.log('[VoiceChatV2] Auto-sending:', text);
      sendText(text);
    }
  }, [voiceStatus, transcript, guidedReviewMode, stopListening, confirmSend, sendText]);

  const handleSendGuidedDraft = useCallback(() => {
    const text = draftText.trim();
    if (!text) {
      return;
    }
    cancelAndReset();
    setDraftText('');
    sendText(text);
  }, [draftText, cancelAndReset, sendText]);

  const handlePrimaryAction = useCallback(async () => {
    if (!isConnected) {
      connect();
      return;
    }

    if (guidedReviewMode) {
      if (isListening) {
        stopListening();
        if (transcript.trim()) {
          setDraftText((previous) => mergeTranscriptDraft(previous, transcript));
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
        sendText(text);
      } else {
        cancelAndReset();
      }
      return;
    }

    try {
      await startListening();
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
    stopListening,
    handleSendGuidedDraft,
    startListening,
    confirmSend,
    sendText,
    cancelAndReset,
  ]);

  const handleRetryGuided = useCallback(() => {
    cancelAndReset();
    setDraftText('');
  }, [cancelAndReset]);

  const handleTypeInstead = useCallback(() => {
    const currentTranscript = transcript.trim();
    if (isListening) {
      stopListening();
    }
    if (currentTranscript) {
      setDraftText((previous) => mergeTranscriptDraft(previous, currentTranscript));
    }
    window.setTimeout(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(draftText.length, draftText.length);
    }, 0);
  }, [draftText.length, isListening, stopListening, transcript]);

  const handleInsertChip = useCallback((chip: string) => {
    setDraftText((previous) => mergeTranscriptDraft(previous, chip));
    window.setTimeout(() => {
      textareaRef.current?.focus();
    }, 0);
  }, []);

  const handleEndSession = useCallback(() => {
    autoCompletionHandledRef.current = true;
    const transcriptSnapshot = [...messages];
    if (isListening) {
      cancelAndReset();
    }
    disconnect();
    window.setTimeout(() => {
      onSessionEnded?.({
        sessionId,
        messages: transcriptSnapshot,
      });
    }, 700);
  }, [messages, sessionId, isListening, cancelAndReset, disconnect, onSessionEnded]);

  const getStatusMessage = () => {
    if (isModelLoading) return 'Loading speech recognition...';
    if (!isModelLoaded) return 'Failed to load model';
    if (isConnecting) return 'Connecting...';
    if (!isConnected) return 'Disconnected';
    if (isPlaying) return 'Coach is speaking...';

    if (guidedReviewMode) {
      switch (voiceStatus) {
        case 'listening':
          return 'Listening. Short English is enough.';
        case 'thinking':
          return 'Pause detected. We will keep the transcript in the composer.';
        case 'ready_to_send':
          return 'Transcript ready. Edit key words before sending.';
        case 'processing':
          return 'Coach is responding...';
        default:
          return draftText.trim()
            ? 'Edit the key words, then send.'
            : 'Say or type your answer.';
      }
    }

    switch (voiceStatus) {
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
    if (isListening) cls += ' listening';
    if (voiceStatus === 'thinking') cls += ' thinking';
    if (voiceStatus === 'ready_to_send') cls += ' ready';
    if (isPlaying) cls += ' playing';
    return cls;
  };

  const getPrimaryButtonText = () => {
    if (guidedReviewMode) {
      if (isListening) {
        return 'Finish capture';
      }
      if (draftText.trim()) {
        return 'Send';
      }
      return 'Speak';
    }
    if (isListening) {
      return voiceStatus === 'thinking' ? 'Thinking...' : 'Tap to send';
    }
    return 'Start speaking';
  };

  const error = voskError?.message || wsError;
  const primaryDisabled = guidedReviewMode
    ? (isPlaying || (!draftText.trim() && (!isModelLoaded || isModelLoading)))
    : (!isModelLoaded || isModelLoading || isPlaying);

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

        {isListening && (
          <div className={`message user current ${voiceStatus}`}>
            <div className="message-content">
              {transcript || '...'}
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

        {voiceStatus === 'processing' && (
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
          {isListening ? (
            <>
              <span className="pulse-ring"></span>
              <span className="btn-icon">Mic</span>
              <span className="btn-text">{getPrimaryButtonText()}</span>
            </>
          ) : (
            <>
              <span className="btn-icon">{guidedReviewMode && draftText.trim() ? 'Send' : 'Mic'}</span>
              <span className="btn-text">{getPrimaryButtonText()}</span>
            </>
          )}
        </button>

        {isListening && (
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
        ) : isListening ? (
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
    </div>
  );
}
