/**
 * Hook для воспроизведения аудио ответов от TTS.
 */

import { useState, useRef, useCallback } from 'react';

interface UseAudioPlayerReturn {
  isPlaying: boolean;
  play: (audioData: ArrayBuffer) => Promise<void>;
  stop: () => void;
  error: Error | null;
}

export function useAudioPlayer(): UseAudioPlayerReturn {
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);

  // Воспроизвести аудио
  const play = useCallback(async (audioData: ArrayBuffer) => {
    try {
      // Останавливаем предыдущее воспроизведение
      if (sourceRef.current) {
        sourceRef.current.stop();
        sourceRef.current = null;
      }

      // Создаём или переиспользуем AudioContext
      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        audioContextRef.current = new AudioContext();
      }

      const audioContext = audioContextRef.current;

      // Возобновляем контекст если он приостановлен (требуется для мобильных)
      if (audioContext.state === 'suspended') {
        await audioContext.resume();
      }

      // Декодируем аудио данные
      const audioBuffer = await audioContext.decodeAudioData(audioData.slice(0));

      // Создаём источник
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);

      sourceRef.current = source;
      setIsPlaying(true);
      setError(null);

      // Обработка завершения
      source.onended = () => {
        setIsPlaying(false);
        sourceRef.current = null;
      };

      // Начинаем воспроизведение
      source.start(0);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to play audio');
      setError(error);
      setIsPlaying(false);
      console.error('Audio playback error:', err);
    }
  }, []);

  // Остановить воспроизведение
  const stop = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.stop();
      sourceRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  return {
    isPlaying,
    play,
    stop,
    error,
  };
}
