/**
 * Кнопка записи голоса.
 * Push-to-talk: зажми чтобы говорить.
 */

import { useCallback } from 'react';
import './VoiceButton.css';

interface VoiceButtonProps {
  isListening: boolean;
  isProcessing: boolean;
  isDisabled: boolean;
  onStart: () => void;
  onStop: () => void;
}

export function VoiceButton({
  isListening,
  isProcessing,
  isDisabled,
  onStart,
  onStop,
}: VoiceButtonProps) {
  const handleMouseDown = useCallback(() => {
    if (!isDisabled && !isProcessing) {
      onStart();
    }
  }, [isDisabled, isProcessing, onStart]);

  const handleMouseUp = useCallback(() => {
    if (isListening) {
      onStop();
    }
  }, [isListening, onStop]);

  // Touch events для мобильных
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    e.preventDefault();
    handleMouseDown();
  }, [handleMouseDown]);

  const handleTouchEnd = useCallback((e: React.TouchEvent) => {
    e.preventDefault();
    handleMouseUp();
  }, [handleMouseUp]);

  let buttonClass = 'voice-button';
  let statusText = 'Hold to speak';

  if (isDisabled) {
    buttonClass += ' disabled';
    statusText = 'Loading...';
  } else if (isProcessing) {
    buttonClass += ' processing';
    statusText = 'Processing...';
  } else if (isListening) {
    buttonClass += ' listening';
    statusText = 'Listening...';
  }

  return (
    <div className="voice-button-container">
      <button
        className={buttonClass}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        disabled={isDisabled}
      >
        <div className="voice-button-icon">
          {isListening ? (
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
            </svg>
          )}
        </div>
        {isListening && <div className="voice-button-pulse" />}
      </button>
      <div className="voice-button-status">{statusText}</div>
    </div>
  );
}
