/**
 * Hook для распознавания речи через Vosk с умным VAD.
 *
 * Особенности:
 * - Не отправляет сразу при остановке записи
 * - Ждёт паузу в речи (silence timeout) перед отправкой
 * - Даёт время на размышление
 * - Показывает статус: говорит / думает / готово
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { createModel, Model } from 'vosk-browser';

// Настройки VAD
const VAD_CONFIG = {
  // Порог громкости для определения "тишины" (0.0 - 1.0)
  silenceThreshold: 0.01,
  // Время тишины перед автоотправкой (мс)
  silenceTimeoutMs: 2500,
  // Минимальная длина фразы для отправки (символов)
  minTextLength: 2,
};

export type VoiceStatus =
  | 'idle'           // Ожидание
  | 'listening'      // Слушает (есть голос)
  | 'thinking'       // Пауза в речи (пользователь думает)
  | 'ready_to_send'  // Пауза > threshold, готов отправить
  | 'processing';    // Отправлено, ждём ответ

interface UseVoskWithVADOptions {
  modelUrl?: string;
  silenceTimeoutMs?: number;
  onFinalResult?: (text: string) => void;
  onPartialResult?: (text: string) => void;
  onSilenceDetected?: () => void;
  onError?: (error: Error) => void;
  onDebugEvent?: (source: string, event: string, data?: Record<string, unknown>) => void;
}

interface UseVoskWithVADReturn {
  isModelLoading: boolean;
  isModelLoaded: boolean;
  isListening: boolean;
  voiceStatus: VoiceStatus;
  transcript: string;
  silenceProgress: number; // 0-100, прогресс до автоотправки
  startListening: () => Promise<void>;
  stopListening: () => void;
  cancelAndReset: () => void;
  confirmSend: () => string | null; // Принудительная отправка
  error: Error | null;
}

const DEFAULT_MODEL_URL = '/vosk-model-small-en-us-0.15.zip';

export function useVoskWithVAD(options: UseVoskWithVADOptions = {}): UseVoskWithVADReturn {
  const {
    modelUrl = DEFAULT_MODEL_URL,
    silenceTimeoutMs = VAD_CONFIG.silenceTimeoutMs,
    onFinalResult,
    onPartialResult,
    onSilenceDetected,
    onError,
    onDebugEvent,
  } = options;

  const [isModelLoading, setIsModelLoading] = useState(false);
  const [isModelLoaded, setIsModelLoaded] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>('idle');
  const [transcript, setTranscript] = useState('');
  const [silenceProgress, setSilenceProgress] = useState(0);
  const [error, setError] = useState<Error | null>(null);

  const modelRef = useRef<Model | null>(null);
  const recognizerRef = useRef<any>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  // VAD state
  const silenceStartRef = useRef<number | null>(null);
  const silenceTimerRef = useRef<number | null>(null);
  const lastTranscriptRef = useRef<string>('');
  const hasSpokenRef = useRef<boolean>(false);

  // Аккумулятор для накопления финальных результатов
  // Решает проблему фрагментации: когда пользователь делает паузы,
  // Vosk выдаёт несколько "final" результатов - теперь они накапливаются
  const accumulatedTextRef = useRef<string>('');
  const currentPartialRef = useRef<string>('');

  // Refs для отслеживания состояния (чтобы избежать зависимости от state)
  const isLoadingRef = useRef(false);
  const isMountedRef = useRef(true);

  // Загрузка модели
  const loadModel = useCallback(async () => {
    // Используем ref вместо state для проверки
    if (modelRef.current || isLoadingRef.current) return;

    isLoadingRef.current = true;
    setIsModelLoading(true);
    setError(null);

    try {
      console.log('[VoskVAD] Loading model from:', modelUrl);
      onDebugEvent?.('vosk', 'model_loading_started', { modelUrl });
      const model = await createModel(modelUrl);

      // Проверяем, что компонент ещё смонтирован
      if (!isMountedRef.current) {
        console.log('[VoskVAD] Component unmounted during model load, cleaning up');
        model.terminate();
        return;
      }

      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Model initialization timeout'));
        }, 30000);

        const checkReady = () => {
          if (!isMountedRef.current) {
            clearTimeout(timeout);
            reject(new Error('Component unmounted'));
            return;
          }
          if (model && typeof model.KaldiRecognizer !== 'undefined') {
            clearTimeout(timeout);
            resolve();
          } else {
            setTimeout(checkReady, 100);
          }
        };
        checkReady();
      });

      // Ещё раз проверяем перед сохранением
      if (!isMountedRef.current) {
        model.terminate();
        return;
      }

      modelRef.current = model;
      setIsModelLoaded(true);
      console.log('[VoskVAD] Model loaded and ready');
      onDebugEvent?.('vosk', 'model_loaded', { modelUrl });
    } catch (err) {
      if (!isMountedRef.current) return; // Игнорируем ошибки после unmount
      const error = err instanceof Error ? err : new Error('Failed to load Vosk model');
      setError(error);
      onError?.(error);
      console.error('[VoskVAD] Failed to load model:', err);
      onDebugEvent?.('vosk', 'model_load_failed', { message: error.message });
    } finally {
      isLoadingRef.current = false;
      if (isMountedRef.current) {
        setIsModelLoading(false);
      }
    }
  }, [modelUrl, onDebugEvent, onError]);

  useEffect(() => {
    isMountedRef.current = true;
    loadModel();

    return () => {
      isMountedRef.current = false;

      // Cleanup recognizer
      if (recognizerRef.current) {
        try {
          recognizerRef.current.remove();
        } catch (e) {
          console.warn('[VoskVAD] Error removing recognizer:', e);
        }
        recognizerRef.current = null;
      }
      // Terminate model and clear reference
      if (modelRef.current) {
        try {
          modelRef.current.terminate();
        } catch (e) {
          console.warn('[VoskVAD] Error terminating model:', e);
        }
        modelRef.current = null;
      }
      if (silenceTimerRef.current) {
        clearInterval(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
      // Reset state so model can be reloaded on remount
      isLoadingRef.current = false;
    };
  }, [loadModel]);

  // Обновление прогресса тишины
  const updateSilenceProgress = useCallback(() => {
    if (silenceStartRef.current === null) {
      setSilenceProgress(0);
      return;
    }

    const elapsed = Date.now() - silenceStartRef.current;
    const progress = Math.min(100, (elapsed / silenceTimeoutMs) * 100);
    setSilenceProgress(progress);

    if (progress >= 100 && hasSpokenRef.current) {
      // Пауза достаточно длинная - готов к отправке
      setVoiceStatus('ready_to_send');
      onSilenceDetected?.();
      onDebugEvent?.('vosk', 'silence_detected', {
        text: lastTranscriptRef.current,
        transcriptPreview: lastTranscriptRef.current.slice(0, 120),
        charCount: lastTranscriptRef.current.length,
      });
    }
  }, [onDebugEvent, onSilenceDetected, silenceTimeoutMs]);

  // Начать запись
  const startListening = useCallback(async () => {
    // Check if model is loaded and ready
    if (!modelRef.current || !isModelLoaded) {
      const err = new Error('Model not loaded. Please wait for model to initialize.');
      setError(err);
      onError?.(err);
      console.error('[VoskVAD] Cannot start: model not ready');
      onDebugEvent?.('vosk', 'start_failed', { message: err.message });
      return;
    }

    // Check if KaldiRecognizer is available
    if (typeof modelRef.current.KaldiRecognizer === 'undefined') {
      const err = new Error('Model not fully initialized. KaldiRecognizer unavailable.');
      setError(err);
      onError?.(err);
      console.error('[VoskVAD] Cannot start: KaldiRecognizer not available');
      onDebugEvent?.('vosk', 'start_failed', { message: err.message });
      return;
    }

    if (isListening) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;
      const actualSampleRate = audioContext.sampleRate;

      const VOSK_SAMPLE_RATE = 16000;
      const recognizer = new modelRef.current.KaldiRecognizer(VOSK_SAMPLE_RATE);
      recognizerRef.current = recognizer;

      // Результаты распознавания (финальные)
      // ВАЖНО: Аккумулируем результаты вместо перезаписи!
      // Это решает проблему когда пользователь думает между фразами
      recognizer.on('result', (message: any) => {
        const text = message.result?.text?.trim();
        if (text) {
          // Накапливаем текст вместо перезаписи
          if (accumulatedTextRef.current) {
            accumulatedTextRef.current += ' ' + text;
          } else {
            accumulatedTextRef.current = text;
          }
          currentPartialRef.current = ''; // Сбрасываем partial

          // Показываем весь накопленный текст
          const fullText = accumulatedTextRef.current;
          lastTranscriptRef.current = fullText;
          setTranscript(fullText);
          onFinalResult?.(fullText);

          console.log('[VoskVAD] accumulated:', fullText);
          onDebugEvent?.('vosk', 'transcript_accumulated', {
            text: fullText,
            textPreview: fullText.slice(0, 120),
            charCount: fullText.length,
          });
        }
      });

      // Промежуточные результаты (partial) - показываем накопленное + текущее
      recognizer.on('partialresult', (message: any) => {
        const partial = message.result?.partial?.trim();
        if (partial) {
          currentPartialRef.current = partial;

          // Показываем: уже накопленное + текущий partial
          const displayText = accumulatedTextRef.current
            ? accumulatedTextRef.current + ' ' + partial
            : partial;

          lastTranscriptRef.current = displayText;
          setTranscript(displayText);
          onPartialResult?.(displayText);
          onDebugEvent?.('vosk', 'transcript_partial', {
            text: displayText,
            textPreview: displayText.slice(0, 120),
            charCount: displayText.length,
          });

          // Сброс таймера тишины при новом тексте
          hasSpokenRef.current = true;
          silenceStartRef.current = null;
          setVoiceStatus('listening');
          setSilenceProgress(0);
        }
      });

      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      // Resampling function
      const resampleAudio = (inputBuffer: AudioBuffer, targetSampleRate: number): Float32Array => {
        const inputData = inputBuffer.getChannelData(0);
        const inputSampleRate = inputBuffer.sampleRate;

        if (inputSampleRate === targetSampleRate) {
          return inputData;
        }

        const sampleRateRatio = inputSampleRate / targetSampleRate;
        const outputLength = Math.floor(inputData.length / sampleRateRatio);
        const output = new Float32Array(outputLength);

        for (let i = 0; i < outputLength; i++) {
          const srcIndex = i * sampleRateRatio;
          const srcIndexFloor = Math.floor(srcIndex);
          const srcIndexCeil = Math.min(srcIndexFloor + 1, inputData.length - 1);
          const t = srcIndex - srcIndexFloor;
          output[i] = inputData[srcIndexFloor] * (1 - t) + inputData[srcIndexCeil] * t;
        }

        return output;
      };

      processor.onaudioprocess = (event) => {
        try {
          const inputBuffer = event.inputBuffer;
          const channelData = inputBuffer.getChannelData(0);

          // VAD: проверяем уровень звука
          const amplitude = Math.max(...Array.from(channelData).map(Math.abs));
          const isSilent = amplitude < VAD_CONFIG.silenceThreshold;

          if (isSilent) {
            // Начинаем отсчёт тишины
            if (silenceStartRef.current === null && hasSpokenRef.current) {
              silenceStartRef.current = Date.now();
              setVoiceStatus('thinking');
            }
          } else {
            // Есть звук - сбрасываем таймер
            silenceStartRef.current = null;
            if (hasSpokenRef.current) {
              setVoiceStatus('listening');
            }
            setSilenceProgress(0);
          }

          // Resample и отправляем в Vosk
          let audioData: Float32Array;
          if (actualSampleRate !== VOSK_SAMPLE_RATE) {
            audioData = resampleAudio(inputBuffer, VOSK_SAMPLE_RATE);
          } else {
            audioData = channelData;
          }

          const resampledBuffer = audioContext.createBuffer(1, audioData.length, VOSK_SAMPLE_RATE);
          resampledBuffer.getChannelData(0).set(audioData);
          recognizer.acceptWaveform(resampledBuffer);
        } catch (error) {
          console.error('[VoskVAD] acceptWaveform failed:', error);
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      // Таймер обновления прогресса
      silenceTimerRef.current = window.setInterval(updateSilenceProgress, 100);

      setIsListening(true);
      setVoiceStatus('listening');
      setTranscript('');
      setSilenceProgress(0);
      hasSpokenRef.current = false;
      silenceStartRef.current = null;
      // Сбрасываем аккумулятор при начале новой записи
      accumulatedTextRef.current = '';
      currentPartialRef.current = '';

      console.log('[VoskVAD] Started listening with VAD (accumulator reset)');
      onDebugEvent?.('vosk', 'listening_started', { silenceTimeoutMs });
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to start listening');
      setError(error);
      onError?.(error);
      console.error('[VoskVAD] Failed to start listening:', err);
      onDebugEvent?.('vosk', 'start_failed', { message: error.message });
    }
  }, [isListening, isModelLoaded, onDebugEvent, onFinalResult, onPartialResult, onError, silenceTimeoutMs, updateSilenceProgress]);

  // Остановить запись
  const stopListening = useCallback(() => {
    if (!isListening) return;

    if (silenceTimerRef.current) {
      clearInterval(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    if (recognizerRef.current) {
      recognizerRef.current.remove();
      recognizerRef.current = null;
    }

    setIsListening(false);
    setVoiceStatus('idle');
    setSilenceProgress(0);
    console.log('[VoskVAD] Stopped listening');
    onDebugEvent?.('vosk', 'listening_stopped');
  }, [isListening, onDebugEvent]);

  // Отмена и сброс (включая аккумулятор)
  const cancelAndReset = useCallback(() => {
    stopListening();
    setTranscript('');
    lastTranscriptRef.current = '';
    hasSpokenRef.current = false;
    // Сбрасываем аккумулятор при отмене
    accumulatedTextRef.current = '';
    currentPartialRef.current = '';
  }, [stopListening]);

  // Принудительная отправка - возвращает ВЕСЬ накопленный текст
  const confirmSend = useCallback((): string | null => {
    const text = accumulatedTextRef.current.trim();
    if (text.length >= VAD_CONFIG.minTextLength) {
      stopListening();
      setVoiceStatus('processing');
      // Сбрасываем аккумулятор после отправки
      accumulatedTextRef.current = '';
      currentPartialRef.current = '';
      console.log('[VoskVAD] confirmSend:', text);
      onDebugEvent?.('vosk', 'confirm_send', {
        textPreview: text.slice(0, 120),
        charCount: text.length,
      });
      return text;
    }
    return null;
  }, [onDebugEvent, stopListening]);

  return {
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
    error,
  };
}
