import { useCallback, useEffect, useRef, useState } from 'react';

export interface AudioPlaybackMeta {
  phase?: string;
  mode?: string;
  turnId?: string;
  turnIndex?: number;
  runtime?: string;
}

interface UseAudioPlayerReturn {
  isPlaying: boolean;
  isAudioReady: boolean;
  unlock: () => Promise<void>;
  play: (audioData: ArrayBuffer, meta?: AudioPlaybackMeta) => Promise<void>;
  stop: () => void;
  error: Error | null;
}

interface UseAudioPlayerOptions {
  onDebugEvent?: (source: string, event: string, data?: Record<string, unknown>) => void;
  onPlaybackStart?: (meta?: AudioPlaybackMeta) => void;
  onPlaybackEnd?: (meta?: AudioPlaybackMeta) => void;
  onPlaybackError?: (error: Error, meta?: AudioPlaybackMeta) => void;
}

export function useAudioPlayer(options: UseAudioPlayerOptions = {}): UseAudioPlayerReturn {
  const {
    onDebugEvent,
    onPlaybackStart,
    onPlaybackEnd,
    onPlaybackError,
  } = options;
  const [isPlaying, setIsPlaying] = useState(false);
  const [isAudioReady, setIsAudioReady] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const sourceMetaRef = useRef<AudioPlaybackMeta | undefined>(undefined);
  const playbackTokenRef = useRef(0);

  const unlock = useCallback(async () => {
    if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
      audioContextRef.current = new AudioContext();
    }

    const audioContext = audioContextRef.current;
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
    }

    const ready = audioContext.state === 'running';
    setIsAudioReady(ready);
    onDebugEvent?.('audio', 'audio_unlocked', {
      state: audioContext.state,
      ready,
    });
  }, [onDebugEvent]);

  const play = useCallback(async (audioData: ArrayBuffer, meta?: AudioPlaybackMeta) => {
    const playbackToken = playbackTokenRef.current + 1;
    playbackTokenRef.current = playbackToken;

    try {
      if (sourceRef.current) {
        sourceRef.current.stop();
        sourceRef.current = null;
      }

      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        audioContextRef.current = new AudioContext();
      }

      const audioContext = audioContextRef.current;
      if (audioContext.state === 'suspended') {
        await audioContext.resume();
      }

      setIsAudioReady(audioContext.state === 'running');

      const audioBuffer = await audioContext.decodeAudioData(audioData.slice(0));
      if (playbackToken !== playbackTokenRef.current) {
        onDebugEvent?.('audio', 'play_superseded', {
          bytes: audioData.byteLength,
          phase: meta?.phase,
          turnId: meta?.turnId,
        });
        return;
      }

      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);

      sourceRef.current = source;
      sourceMetaRef.current = meta;
      setIsPlaying(true);
      setError(null);
      onDebugEvent?.('audio', 'play_started', {
        bytes: audioData.byteLength,
        durationSeconds: audioBuffer.duration,
        phase: meta?.phase,
        turnId: meta?.turnId,
      });
      onPlaybackStart?.(meta);

      source.onended = () => {
        if (sourceRef.current !== source) {
          return;
        }

        const endedMeta = sourceMetaRef.current;
        setIsPlaying(false);
        sourceRef.current = null;
        sourceMetaRef.current = undefined;
        onDebugEvent?.('audio', 'play_ended', {
          phase: endedMeta?.phase,
          turnId: endedMeta?.turnId,
        });
        onPlaybackEnd?.(endedMeta);
      };

      source.start(0);
    } catch (err) {
      const playbackError = err instanceof Error ? err : new Error('Failed to play audio');
      const failedMeta = sourceMetaRef.current ?? meta;
      setError(playbackError);
      setIsPlaying(false);
      console.error('Audio playback error:', err);
      onDebugEvent?.('audio', 'play_failed', {
        message: playbackError.message,
        phase: failedMeta?.phase,
        turnId: failedMeta?.turnId,
      });
      onPlaybackError?.(playbackError, failedMeta);
    }
  }, [onDebugEvent, onPlaybackEnd, onPlaybackError, onPlaybackStart]);

  const stop = useCallback(() => {
    playbackTokenRef.current += 1;
    if (sourceRef.current) {
      sourceRef.current.stop();
      sourceRef.current = null;
    }
    sourceMetaRef.current = undefined;
    setIsPlaying(false);
    onDebugEvent?.('audio', 'play_stopped');
  }, [onDebugEvent]);

  useEffect(() => () => {
    playbackTokenRef.current += 1;
    if (sourceRef.current) {
      try {
        sourceRef.current.stop();
      } catch {
        // ignore teardown race
      }
      sourceRef.current = null;
    }
    sourceMetaRef.current = undefined;
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      void audioContextRef.current.close();
      audioContextRef.current = null;
    }
  }, []);

  return {
    isPlaying,
    isAudioReady,
    unlock,
    play,
    stop,
    error,
  };
}
