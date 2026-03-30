/**
 * Улучшенный голосовой чат с умным VAD.
 *
 * Особенности:
 * - Кнопка toggle: нажми для старта, нажми для отправки
 * - Визуальный индикатор паузы (кружок заполняется)
 * - Автоотправка после 2.5 сек тишины
 * - Показывает статус: слушает / думает / готов
 * - Даёт время на размышление
 */

import { useCallback, useEffect } from 'react';
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
  onSessionEnded,
}: VoiceChatV2Props) {

  // Vosk с VAD
  const {
    isModelLoading,
    isModelLoaded,
    isListening,
    voiceStatus,
    transcript,
    silenceProgress,
    startListening,
    cancelAndReset,
    confirmSend,
    error: voskError,
  } = useVoskWithVAD({
    silenceTimeoutMs: 2500, // 2.5 секунды паузы для размышления
    onFinalResult: (text) => {
      console.log('[VoiceChatV2] Final:', text);
    },
    onSilenceDetected: () => {
      console.log('[VoiceChatV2] Silence detected - ready to send');
    },
  });

  // Audio player
  const { isPlaying, play } = useAudioPlayer();

  // WebSocket
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

  // Автоподключение
  useEffect(() => {
    if (isModelLoaded && !isConnected && !isConnecting) {
      connect();
    }
  }, [isModelLoaded, isConnected, isConnecting, connect]);

  // Автоотправка при ready_to_send
  useEffect(() => {
    if (voiceStatus === 'ready_to_send' && transcript.trim()) {
      const text = confirmSend();
      if (text) {
        console.log('[VoiceChatV2] Auto-sending:', text);
        sendText(text);
      }
    }
  }, [voiceStatus, transcript, confirmSend, sendText]);

  // Обработка кнопки
  const handleButtonClick = useCallback(async () => {
    // Не начинать, пока модель не загружена
    if (!isModelLoaded) {
      console.log('[VoiceChatV2] Model not loaded yet');
      return;
    }

    if (!isConnected) {
      connect();
      return;
    }

    if (isListening) {
      // Уже слушаем - принудительная отправка
      const text = confirmSend();
      if (text) {
        console.log('[VoiceChatV2] Manual send:', text);
        sendText(text);
      } else {
        // Нет текста - просто останавливаем
        cancelAndReset();
      }
    } else {
      // Начинаем слушать
      try {
        await startListening();
      } catch (err) {
        console.error('[VoiceChatV2] Failed to start:', err);
      }
    }
  }, [isModelLoaded, isConnected, isListening, connect, startListening, confirmSend, sendText, cancelAndReset]);

  // Отмена записи (долгое нажатие или ESC)
  const handleCancel = useCallback(() => {
    cancelAndReset();
  }, [cancelAndReset]);

  // Завершить сессию
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

  // Статус для отображения
  const getStatusMessage = () => {
    if (isModelLoading) return 'Loading speech recognition...';
    if (!isModelLoaded) return 'Failed to load model';
    if (isConnecting) return 'Connecting...';
    if (!isConnected) return 'Disconnected';
    if (isPlaying) return 'Mentor is speaking...';

    switch (voiceStatus) {
      case 'listening':
        return 'Listening... (speak in English)';
      case 'thinking':
        return 'Take your time to think... 🤔';
      case 'ready_to_send':
        return 'Sending...';
      case 'processing':
        return 'Mentor is thinking...';
      default:
        return 'Tap to start speaking';
    }
  };

  // Стиль кнопки в зависимости от статуса
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
      {/* Header */}
      <div className="voice-chat-header">
        <h1>🎓 English Mentor</h1>
        {title && <p className="voice-session-subtitle">{title}</p>}
        {subtitle && <p className="voice-session-subtitle">{subtitle}</p>}
        <p className="status">{getStatusMessage()}</p>
        {error && <p className="error">{error}</p>}
      </div>

      {/* Messages */}
      <div className="voice-chat-messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <p>👋 Hi! I'm your English mentor.</p>
            <p className="hint">Tap the button and speak. Take your time - I'll wait!</p>
            <p className="hint">Можете говорить медленно, я подожду пока вы думаете.</p>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            <div className="message-content">{message.text}</div>
          </div>
        ))}

        {/* Current transcript with thinking indicator */}
        {isListening && (
          <div className={`message user current ${voiceStatus}`}>
            <div className="message-content">
              {transcript || '...'}
              {voiceStatus === 'thinking' && (
                <span className="thinking-dots"> 🤔</span>
              )}
            </div>
            {/* Progress bar for silence */}
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

        {/* Processing indicator */}
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

      {/* Voice Button */}
      <div className="voice-chat-controls-v2">
        <button
          className={getButtonClass()}
          onClick={handleButtonClick}
          disabled={!isModelLoaded || isModelLoading || isPlaying}
        >
          {isListening ? (
            <>
              <span className="pulse-ring"></span>
              <span className="btn-icon">🎤</span>
              <span className="btn-text">
                {voiceStatus === 'thinking' ? 'Thinking...' : 'Tap to send'}
              </span>
            </>
          ) : (
            <>
              <span className="btn-icon">🎤</span>
              <span className="btn-text">Tap to speak</span>
            </>
          )}
        </button>

        {isListening && (
          <button className="cancel-button" onClick={handleCancel}>
            ✕ Cancel
          </button>
        )}
      </div>

      {/* Hint */}
      <div className="voice-chat-hint">
        {isListening ? (
          <p>Take your time! I'll wait 2.5 seconds of silence before responding.</p>
        ) : (
          <p>Speak naturally. I understand beginners and will help with mistakes.</p>
        )}
      </div>

      {/* End Session Button */}
      {isConnected && messages.length > 0 && (
        <div className="end-session-container">
          <button className="end-session-button" onClick={handleEndSession}>
            📊 End Session & See Summary
          </button>
        </div>
      )}
    </div>
  );
}
