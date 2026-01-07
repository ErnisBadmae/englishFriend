/**
 * Hook для локального TTS через Piper (в браузере).
 *
 * Piper TTS работает полностью в браузере через WebAssembly.
 * Модель ~100MB загружается один раз и кешируется в Origin Private File System.
 *
 * Преимущества:
 * - Полностью офлайн
 * - Низкая latency (~100-300ms)
 * - Приватность (голос синтезируется локально)
 *
 * @see https://github.com/Mintplex-Labs/piper-tts-web
 */

import { useState, useCallback, useRef, useEffect } from 'react';

// Типы для Piper TTS Web
interface PiperTTSModule {
  predict: (options: { text: string; voiceId: string }) => Promise<Blob>;
  download: (voiceId: string, onProgress?: (progress: { loaded: number; total: number }) => void) => Promise<void>;
  stored: () => Promise<string[]>;
}

interface UsePiperTTSOptions {
  voiceId?: string;
  onProgress?: (progress: number) => void;
  onError?: (error: Error) => void;
}

interface UsePiperTTSReturn {
  isLoading: boolean;
  isModelLoaded: boolean;
  isSpeaking: boolean;
  speak: (text: string) => Promise<void>;
  stop: () => void;
  downloadProgress: number;
  error: Error | null;
}

// Доступные голоса Piper
export const PIPER_VOICES = {
  // Американский английский
  US_FEMALE_MEDIUM: 'en_US-hfc_female-medium',
  US_MALE_MEDIUM: 'en_US-hfc_male-medium',
  US_FEMALE_LOW: 'en_US-lessac-low',
  US_MALE_LOW: 'en_US-kusal-medium',

  // Британский английский
  GB_FEMALE_MEDIUM: 'en_GB-cori-medium',
  GB_MALE_MEDIUM: 'en_GB-alan-medium',
} as const;

// Загрузка модуля Piper TTS (lazy loading)
let piperModulePromise: Promise<PiperTTSModule> | null = null;

async function loadPiperModule(): Promise<PiperTTSModule> {
  if (piperModulePromise) {
    return piperModulePromise;
  }

  piperModulePromise = (async () => {
    // Динамический импорт через CDN
    const module = await import(
      /* webpackIgnore: true */
      'https://cdn.jsdelivr.net/npm/@mintplex-labs/piper-tts-web@1.0.3/dist/piper-tts-web.js'
    );
    return module as PiperTTSModule;
  })();

  return piperModulePromise;
}

export function usePiperTTS(options: UsePiperTTSOptions = {}): UsePiperTTSReturn {
  const {
    voiceId = PIPER_VOICES.US_FEMALE_MEDIUM,
    onProgress,
    onError,
  } = options;

  const [isLoading, setIsLoading] = useState(false);
  const [isModelLoaded, setIsModelLoaded] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [error, setError] = useState<Error | null>(null);

  const piperRef = useRef<PiperTTSModule | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  // Инициализация Piper TTS
  const initialize = useCallback(async () => {
    if (piperRef.current && isModelLoaded) return;

    setIsLoading(true);
    setError(null);

    try {
      console.log('[Piper TTS] Loading module...');
      const piper = await loadPiperModule();
      piperRef.current = piper;

      // Проверяем, есть ли уже скачанная модель
      const storedVoices = await piper.stored();
      console.log('[Piper TTS] Stored voices:', storedVoices);

      if (!storedVoices.includes(voiceId)) {
        console.log(`[Piper TTS] Downloading voice model: ${voiceId} (~100MB)...`);
        await piper.download(voiceId, (progress) => {
          const percent = Math.round((progress.loaded / progress.total) * 100);
          setDownloadProgress(percent);
          onProgress?.(percent);
          if (percent % 10 === 0) {
            console.log(`[Piper TTS] Download progress: ${percent}%`);
          }
        });
        console.log('[Piper TTS] Voice model downloaded and cached');
      }

      setIsModelLoaded(true);
      console.log('[Piper TTS] Ready');
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to load Piper TTS');
      setError(error);
      onError?.(error);
      console.error('[Piper TTS] Initialization failed:', err);
    } finally {
      setIsLoading(false);
    }
  }, [voiceId, isModelLoaded, onProgress, onError]);

  // Загружаем модуль при монтировании
  useEffect(() => {
    initialize();

    return () => {
      // Cleanup audio URL
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
    };
  }, [initialize]);

  // Синтез речи
  const speak = useCallback(async (text: string) => {
    if (!piperRef.current) {
      throw new Error('Piper TTS not initialized');
    }

    // Останавливаем предыдущее аудио
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    // Очищаем предыдущий URL
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
    }

    setIsSpeaking(true);
    const startTime = performance.now();

    try {
      console.log(`[Piper TTS] Synthesizing: "${text.substring(0, 50)}..."`);

      // Синтезируем речь
      const wavBlob = await piperRef.current.predict({
        text,
        voiceId,
      });

      const synthesisTime = performance.now() - startTime;
      console.log(`[Piper TTS] Synthesis completed in ${synthesisTime.toFixed(0)}ms`);

      // Создаём URL для воспроизведения
      audioUrlRef.current = URL.createObjectURL(wavBlob);

      // Воспроизводим
      const audio = new Audio(audioUrlRef.current);
      audioRef.current = audio;

      audio.onended = () => {
        setIsSpeaking(false);
      };

      audio.onerror = (e) => {
        console.error('[Piper TTS] Audio playback error:', e);
        setIsSpeaking(false);
      };

      await audio.play();
    } catch (err) {
      const error = err instanceof Error ? err : new Error('TTS synthesis failed');
      setError(error);
      onError?.(error);
      setIsSpeaking(false);
      console.error('[Piper TTS] Synthesis failed:', err);
    }
  }, [voiceId, onError]);

  // Остановка воспроизведения
  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setIsSpeaking(false);
  }, []);

  return {
    isLoading,
    isModelLoaded,
    isSpeaking,
    speak,
    stop,
    downloadProgress,
    error,
  };
}
