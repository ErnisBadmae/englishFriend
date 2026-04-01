import { useCallback, useEffect, useMemo, useState } from 'react';
import { useVoskWithVAD } from '../hooks/useVoskWithVAD';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import './VoiceChat.css';

interface VoiceChatV2Props {
  userId: number;
  wsUrl: string;
  mode?: string;
  interviewTrackId?: string;
  title?: string;
  subtitle?: string;
  reviewBeforeSend?: boolean;
  onSessionEnded?: (payload: {
    sessionId: string | null;
    messages: Array<{ role: 'user' | 'assistant'; text: string }>;
  }) => void;
}

export function VoiceChatV2({
  userId,
  wsUrl,
  mode,
  interviewTrackId,
  title,
  subtitle,
  reviewBeforeSend = false,
  onSessionEnded,
}: VoiceChatV2Props) {
  const [reviewDraft, setReviewDraft] = useState('');
  const [showTranscriptReview, setShowTranscriptReview] = useState(false);

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
    silenceTimeoutMs: 2500,
    onFinalResult: (text) => {
      console.log('[VoiceChatV2] Final:', text);
    },
    onSilenceDetected: () => {
      console.log('[VoiceChatV2] Silence detected - ready to send');
    },
  });

  const { isPlaying, play } = useAudioPlayer();

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
    query: {
      mode,
      interview_track: interviewTrackId,
    },
    onAudio: (audioData) => {
      play(audioData);
    },
    onConnect: () => {
      console.log('[VoiceChatV2] Connected');
    },
  });

  const guidedReviewMode = useMemo(
    () => reviewBeforeSend || mode === 'assessment' || mode === 'guided_setup' || !mode,
    [mode, reviewBeforeSend]
  );

  useEffect(() => {
    if (isModelLoaded && !isConnected && !isConnecting) {
      connect();
    }
  }, [isModelLoaded, isConnected, isConnecting, connect]);

  useEffect(() => {
    if (voiceStatus !== 'ready_to_send' || !transcript.trim()) {
      return;
    }

    if (guidedReviewMode) {
      stopListening();
      setReviewDraft(transcript.trim());
      setShowTranscriptReview(true);
      return;
    }

    const text = confirmSend();
    if (text) {
      console.log('[VoiceChatV2] Auto-sending:', text);
      sendText(text);
    }
  }, [voiceStatus, transcript, guidedReviewMode, stopListening, confirmSend, sendText]);

  const handleButtonClick = useCallback(async () => {
    if (!isModelLoaded) {
      console.log('[VoiceChatV2] Model not loaded yet');
      return;
    }

    if (!isConnected) {
      connect();
      return;
    }

    if (isListening) {
      if (guidedReviewMode) {
        stopListening();
        if (transcript.trim()) {
          setReviewDraft(transcript.trim());
          setShowTranscriptReview(true);
        } else {
          cancelAndReset();
        }
        return;
      }

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
      setShowTranscriptReview(false);
      setReviewDraft('');
      await startListening();
    } catch (err) {
      console.error('[VoiceChatV2] Failed to start:', err);
    }
  }, [
    isModelLoaded,
    isConnected,
    isListening,
    guidedReviewMode,
    transcript,
    connect,
    stopListening,
    confirmSend,
    sendText,
    cancelAndReset,
    startListening,
  ]);

  const handleCancel = useCallback(() => {
    cancelAndReset();
    setShowTranscriptReview(false);
    setReviewDraft('');
  }, [cancelAndReset]);

  const handleSendReviewedTranscript = useCallback(() => {
    const text = reviewDraft.trim();
    if (!text) {
      return;
    }
    setShowTranscriptReview(false);
    setReviewDraft('');
    sendText(text);
  }, [reviewDraft, sendText]);

  const handleRetryTranscript = useCallback(() => {
    setShowTranscriptReview(false);
    setReviewDraft('');
    cancelAndReset();
  }, [cancelAndReset]);

  const handleEndSession = useCallback(() => {
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
    if (isPlaying) return 'Mentor is speaking...';
    if (showTranscriptReview) return 'Review transcript before sending';

    switch (voiceStatus) {
      case 'listening':
        return guidedReviewMode ? 'Listening... say it simply, you can edit later' : 'Listening... speak in English';
      case 'thinking':
        return guidedReviewMode ? 'Pause detected... preparing transcript review' : 'Take your time to think...';
      case 'ready_to_send':
        return guidedReviewMode ? 'Transcript ready for review' : 'Sending...';
      case 'processing':
        return 'Mentor is thinking...';
      default:
        return guidedReviewMode ? 'Tap to speak, then review the transcript' : 'Tap to start speaking';
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

  const error = voskError?.message || wsError;

  return (
    <div className="voice-chat">
      <div className="voice-chat-header">
        <h1>English Mentor</h1>
        {title && <p className="voice-session-subtitle">{title}</p>}
        {subtitle && <p className="voice-session-subtitle">{subtitle}</p>}
        {guidedReviewMode && (
          <p className="voice-session-note">
            Say your answer in simple English. You can edit the transcript before sending it.
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
                ? 'Tap the button, say your goal or answer, then review the transcript before it is sent.'
                : "Tap the button and speak. I will wait if you need time to think."}
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

        {showTranscriptReview && (
          <div className="transcript-review-card">
            <div className="transcript-review-header">
              <strong>Review transcript</strong>
              <span>Fix important words before the coach sees them.</span>
            </div>
            <textarea
              className="transcript-review-input"
              value={reviewDraft}
              onChange={(event) => setReviewDraft(event.target.value)}
              rows={4}
              placeholder="Edit the transcript here"
            />
            <div className="transcript-review-actions">
              <button className="secondary-action review-action-button" onClick={handleRetryTranscript}>
                Retry
              </button>
              <button
                className="primary-action review-action-button"
                onClick={handleSendReviewedTranscript}
                disabled={!reviewDraft.trim()}
              >
                Send
              </button>
            </div>
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

      <div className="voice-chat-controls-v2">
        <button
          className={getButtonClass()}
          onClick={handleButtonClick}
          disabled={!isModelLoaded || isModelLoading || isPlaying || showTranscriptReview}
        >
          {isListening ? (
            <>
              <span className="pulse-ring"></span>
              <span className="btn-icon">Mic</span>
              <span className="btn-text">
                {guidedReviewMode ? 'Finish and review' : voiceStatus === 'thinking' ? 'Thinking...' : 'Tap to send'}
              </span>
            </>
          ) : (
            <>
              <span className="btn-icon">Mic</span>
              <span className="btn-text">{guidedReviewMode ? 'Tap to speak' : 'Start speaking'}</span>
            </>
          )}
        </button>

        {isListening && (
          <button className="cancel-button" onClick={handleCancel}>
            Cancel
          </button>
        )}
      </div>

      <div className="voice-chat-hint">
        {isListening ? (
          <p>
            {guidedReviewMode
              ? 'Pause whenever you need. You will be able to edit the transcript before it is sent.'
              : "Take your time. I will wait 2.5 seconds of silence before responding."}
          </p>
        ) : showTranscriptReview ? (
          <p>Check the transcript, fix the key words, then send it to the coach.</p>
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
