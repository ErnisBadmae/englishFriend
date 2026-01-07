/**
 * Основной компонент голосового чата.
 */

import { useCallback, useEffect, useState } from 'react';
import { useVosk } from '../hooks/useVosk';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { VoiceButton } from './VoiceButton';
import './VoiceChat.css';

interface VoiceChatProps {
  userId: number;
  wsUrl: string;
}

export function VoiceChat({ userId, wsUrl }: VoiceChatProps) {
  const [currentTranscript, setCurrentTranscript] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // Vosk для распознавания речи
  const {
    isModelLoading,
    isModelLoaded,
    isListening,
    transcript,
    startListening,
    stopListening,
    error: voskError,
  } = useVosk({
    onResult: (text, isFinal) => {
      setCurrentTranscript(text);
      if (isFinal && text.trim()) {
        console.log('Final transcript:', text);
      }
    },
  });

  // Audio player для воспроизведения TTS
  const { isPlaying, play } = useAudioPlayer();

  // WebSocket для связи с бэкендом
  const {
    isConnected,
    isConnecting,
    messages,
    sendText,
    connect,
    error: wsError,
  } = useWebSocket({
    url: wsUrl,
    userId,
    onAudio: (audioData) => {
      setIsProcessing(false);
      play(audioData);
    },
    onMessage: (message) => {
      if (message.role === 'assistant') {
        setIsProcessing(false);
      }
    },
    onConnect: () => {
      console.log('Connected to voice chat');
    },
    onError: (error) => {
      setIsProcessing(false);
      console.error('WebSocket error:', error);
    },
  });

  // Автоподключение при загрузке модели
  useEffect(() => {
    if (isModelLoaded && !isConnected && !isConnecting) {
      connect();
    }
  }, [isModelLoaded, isConnected, isConnecting, connect]);

  // Обработка начала записи
  const handleStart = useCallback(async () => {
    if (!isConnected) {
      connect();
      return;
    }

    try {
      setCurrentTranscript('');
      await startListening();
    } catch (err) {
      console.error('Failed to start listening:', err);
    }
  }, [isConnected, connect, startListening]);

  // Обработка окончания записи
  const handleStop = useCallback(() => {
    stopListening();

    // Отправляем текст на сервер
    const textToSend = currentTranscript.trim() || transcript.trim();
    if (textToSend && isConnected) {
      setIsProcessing(true);
      sendText(textToSend);
      setCurrentTranscript('');
    }
  }, [stopListening, currentTranscript, transcript, isConnected, sendText]);

  // Статус загрузки
  const getStatusMessage = () => {
    if (isModelLoading) return 'Loading speech recognition...';
    if (!isModelLoaded) return 'Failed to load speech recognition';
    if (isConnecting) return 'Connecting to server...';
    if (!isConnected) return 'Disconnected from server';
    if (isPlaying) return 'Speaking...';
    if (isProcessing) return 'Thinking...';
    return 'Ready to chat!';
  };

  const error = voskError?.message || wsError;

  return (
    <div className="voice-chat">
      {/* Header */}
      <div className="voice-chat-header">
        <h1>English Friend</h1>
        <p className="status">{getStatusMessage()}</p>
        {error && <p className="error">{error}</p>}
      </div>

      {/* Messages */}
      <div className="voice-chat-messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <p>Hold the button and speak in English!</p>
            <p className="hint">I'll help you practice and correct your mistakes.</p>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={index}
            className={`message ${message.role}`}
          >
            <div className="message-content">
              {message.text}
            </div>
          </div>
        ))}

        {/* Current transcript */}
        {(isListening || currentTranscript) && (
          <div className="message user current">
            <div className="message-content">
              {currentTranscript || transcript || '...'}
            </div>
          </div>
        )}

        {/* Processing indicator */}
        {isProcessing && (
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
      <div className="voice-chat-controls">
        <VoiceButton
          isListening={isListening}
          isProcessing={isProcessing || isPlaying}
          isDisabled={!isModelLoaded || isModelLoading}
          onStart={handleStart}
          onStop={handleStop}
        />
      </div>
    </div>
  );
}
