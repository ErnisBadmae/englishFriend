/**
 * Hook для распознавания речи через Vosk (локально в браузере).
 *
 * Vosk работает полностью в браузере через WebAssembly.
 * Модель ~46MB загружается один раз и кешируется.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { createModel, Model } from 'vosk-browser';
import type { KaldiRecognizer } from 'vosk-browser';

interface UseVoskOptions {
  modelUrl?: string;
  onResult?: (text: string, isFinal: boolean) => void;
  onError?: (error: Error) => void;
}

interface UseVoskReturn {
  isModelLoading: boolean;
  isModelLoaded: boolean;
  isListening: boolean;
  transcript: string;
  startListening: () => Promise<void>;
  stopListening: () => void;
  error: Error | null;
}

// URL модели Vosk для английского языка (~46MB)
// Модель хостится локально чтобы избежать CORS
const DEFAULT_MODEL_URL = '/vosk-model-small-en-us-0.15.zip';

export function useVosk(options: UseVoskOptions = {}): UseVoskReturn {
  const {
    modelUrl = DEFAULT_MODEL_URL,
    onResult,
    onError,
  } = options;

  const [isModelLoading, setIsModelLoading] = useState(false);
  const [isModelLoaded, setIsModelLoaded] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<Error | null>(null);

  const modelRef = useRef<Model | null>(null);
  const recognizerRef = useRef<KaldiRecognizer | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  // Загрузка модели Vosk
  const loadModel = useCallback(async () => {
    if (modelRef.current || isModelLoading) return;

    setIsModelLoading(true);
    setError(null);

    try {
      console.log('Loading Vosk model from:', modelUrl);
      const model = await createModel(modelUrl);

      // Дожидаемся полной инициализации модели
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Model initialization timeout'));
        }, 30000); // 30 секунд таймаут

        // Проверяем готовность модели
        const checkReady = () => {
          if (model && typeof model.KaldiRecognizer !== 'undefined') {
            clearTimeout(timeout);
            resolve();
          } else {
            setTimeout(checkReady, 100);
          }
        };
        checkReady();
      });

      modelRef.current = model;
      setIsModelLoaded(true);
      console.log('Vosk model loaded and ready');
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to load Vosk model');
      setError(error);
      onError?.(error);
      console.error('Failed to load Vosk model:', err);
    } finally {
      setIsModelLoading(false);
    }
  }, [modelUrl, isModelLoading, onError]);

  // Загружаем модель при монтировании
  useEffect(() => {
    loadModel();

    return () => {
      // Cleanup при размонтировании
      if (recognizerRef.current) {
        recognizerRef.current.remove();
      }
      if (modelRef.current) {
        modelRef.current.terminate();
      }
    };
  }, [loadModel]);

  // Начать запись
  const startListening = useCallback(async () => {
    if (!modelRef.current) {
      throw new Error('Model not loaded');
    }

    if (isListening) return;

    try {
      // Запрашиваем доступ к микрофону
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
        },
      });
      streamRef.current = stream;

      // Создаём AudioContext
      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;
      const actualSampleRate = audioContext.sampleRate;
      console.log(`[Vosk] AudioContext created. Requested: 16000Hz, Actual: ${actualSampleRate}Hz`);

      // Vosk ВСЕГДА работает с 16000Hz
      const VOSK_SAMPLE_RATE = 16000;

      // Создаём recognizer с ФИКСИРОВАННЫМ sample rate 16000Hz
      const recognizer = new modelRef.current.KaldiRecognizer(VOSK_SAMPLE_RATE);
      recognizerRef.current = recognizer;
      console.log(`[Vosk] KaldiRecognizer created with sample rate: ${VOSK_SAMPLE_RATE}Hz`);

      // Обработка результатов
      recognizer.on('result', (message: any) => {
        console.log('[Vosk] Final result:', message);
        const text = message.result?.text;
        if (text) {
          setTranscript(text);
          onResult?.(text, true);
        }
      });

      recognizer.on('partialresult', (message: any) => {
        const partial = message.result?.partial;
        console.log('[Vosk] Partial result:', { partial, length: partial?.length, message });
        if (partial) {
          setTranscript(partial);
          onResult?.(partial, false);
        }
      });

      // Создаём источник из микрофона
      const source = audioContext.createMediaStreamSource(stream);

      // ScriptProcessor для обработки аудио (deprecated, но работает)
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      let audioChunkCount = 0;
      let maxAmplitude = 0;

      // Функция для resampling аудио с actualSampleRate -> 16000Hz
      const resampleAudio = (inputBuffer: AudioBuffer, targetSampleRate: number): Float32Array => {
        const inputData = inputBuffer.getChannelData(0);
        const inputSampleRate = inputBuffer.sampleRate;

        if (inputSampleRate === targetSampleRate) {
          return inputData;
        }

        const sampleRateRatio = inputSampleRate / targetSampleRate;
        const outputLength = Math.floor(inputData.length / sampleRateRatio);
        const output = new Float32Array(outputLength);

        // Linear interpolation resampling
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

          // Check audio level
          const amplitude = Math.max(...Array.from(channelData).map(Math.abs));
          maxAmplitude = Math.max(maxAmplitude, amplitude);

          // Resample если нужно
          let audioData: Float32Array;
          if (actualSampleRate !== VOSK_SAMPLE_RATE) {
            audioData = resampleAudio(inputBuffer, VOSK_SAMPLE_RATE);
          } else {
            audioData = channelData;
          }

          // Создаем новый AudioBuffer с правильным sample rate для Vosk
          const resampledBuffer = audioContext.createBuffer(
            1, // mono
            audioData.length,
            VOSK_SAMPLE_RATE
          );
          resampledBuffer.getChannelData(0).set(audioData);

          // Pass resampled buffer to Vosk
          const accepted = recognizer.acceptWaveform(resampledBuffer);
          audioChunkCount++;
          if (audioChunkCount % 50 === 0) {
            console.log(`[Vosk] Processed ${audioChunkCount} chunks | Max amplitude: ${maxAmplitude.toFixed(4)} | Input SR: ${actualSampleRate}Hz -> Vosk SR: ${VOSK_SAMPLE_RATE}Hz | Accepted:`, accepted);
          }
        } catch (error) {
          console.error('[Vosk] acceptWaveform failed:', error);
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      setIsListening(true);
      setTranscript('');
      console.log('Started listening');
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to start listening');
      setError(error);
      onError?.(error);
      console.error('Failed to start listening:', err);
    }
  }, [isListening, onResult, onError]);

  // Остановить запись
  const stopListening = useCallback(() => {
    if (!isListening) return;

    // Останавливаем обработку
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    // Закрываем AudioContext
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    // Останавливаем stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    // Получаем финальный результат
    if (recognizerRef.current) {
      recognizerRef.current.remove();
      recognizerRef.current = null;
    }

    setIsListening(false);
    console.log('Stopped listening');
  }, [isListening]);

  return {
    isModelLoading,
    isModelLoaded,
    isListening,
    transcript,
    startListening,
    stopListening,
    error,
  };
}
