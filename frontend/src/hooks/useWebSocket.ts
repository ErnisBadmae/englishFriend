import { useCallback, useEffect, useRef, useState } from 'react';
import type { AudioPlaybackMeta } from './useAudioPlayer';

interface Message {
  role: 'user' | 'assistant';
  text: string;
}

interface MessageMeta extends AudioPlaybackMeta {
  turnId?: string;
  turnIndex?: number;
}

interface DisconnectPayload {
  code: number;
  reason: string;
  manualClose: boolean;
  expectedServerClose: boolean;
}

interface WebSocketMessage {
  type: 'connected' | 'transcript' | 'audio' | 'error' | 'session_complete' | 'phase_changed';
  role?: 'user' | 'assistant';
  text?: string;
  data?: string;
  format?: string;
  message?: string;
  session_id?: string;
  greeting?: string;
  reason?: string;
  return_screen?: string;
  runtime?: string;
  agent_version?: string;
  stt_provider?: string;
  turn_id?: string;
  turn_index?: number;
  phase?: string;
  mode?: string;
  stage?: string;
}

interface UseWebSocketOptions {
  url: string;
  userId: number;
  onMessage?: (message: Message, meta?: MessageMeta) => void;
  onAudio?: (audioData: ArrayBuffer, meta?: AudioPlaybackMeta) => void;
  onError?: (error: string) => void;
  onConnect?: () => void;
  onDisconnect?: (payload: DisconnectPayload) => void;
  onSessionComplete?: (payload: {
    reason: string;
    returnScreen?: string;
  }) => void;
  onDebugEvent?: (source: string, event: string, data?: Record<string, unknown>) => void;
  query?: Record<string, string | number | undefined | null>;
}

interface DisconnectOptions {
  sendEnd?: boolean;
  resetMessages?: boolean;
  reason?: string;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  isConnecting: boolean;
  sessionId: string | null;
  messages: Message[];
  sendText: (text: string, meta?: { source?: string }) => void;
  connect: () => void;
  requestSessionEnd: () => void;
  disconnect: (options?: DisconnectOptions) => void;
  error: string | null;
}

function shouldSuppressAssistantDuplicate(previous: Message[], next: Message): boolean {
  if (next.role !== 'assistant') {
    return false;
  }
  if (previous.some((item) => item.role === 'user')) {
    return false;
  }
  return previous.some((item) => item.role === 'assistant' && item.text === next.text);
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    userId,
    onMessage,
    onAudio,
    onError,
    onConnect,
    onDisconnect,
    onSessionComplete,
    onDebugEvent,
    query,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const isConnectingRef = useRef<boolean>(false);
  const manualCloseRef = useRef<boolean>(false);
  const expectedServerCloseRef = useRef<boolean>(false);
  const endRequestedRef = useRef<boolean>(false);

  const connect = useCallback(() => {
    if (
      wsRef.current?.readyState === WebSocket.OPEN
      || wsRef.current?.readyState === WebSocket.CONNECTING
      || isConnectingRef.current
    ) {
      return;
    }

    manualCloseRef.current = false;
    expectedServerCloseRef.current = false;
    endRequestedRef.current = false;
    isConnectingRef.current = true;
    setIsConnecting(true);
    setError(null);

    const params = new URLSearchParams();
    params.set('user_id', String(userId));
    Object.entries(query || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.set(key, String(value));
      }
    });

    const wsUrl = `${url}?${params.toString()}`;
    console.log('Connecting to WebSocket:', wsUrl);
    onDebugEvent?.('websocket', 'ws_connecting', {
      url: wsUrl,
      userId,
    });

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      isConnectingRef.current = false;
      setIsConnected(true);
      setIsConnecting(false);
      reconnectAttemptsRef.current = 0;
      onConnect?.();
      onDebugEvent?.('websocket', 'ws_connected');
    };

    ws.onmessage = (event) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data);
        console.log('WebSocket message:', data);

        switch (data.type) {
          case 'connected':
            console.log('Session started:', data.session_id);
            setSessionId(data.session_id || null);
            onDebugEvent?.('websocket', 'ws_connected_payload', {
              sessionId: data.session_id,
              runtime: data.runtime,
              agentVersion: data.agent_version,
              sttProvider: data.stt_provider,
              mode: data.mode,
              phase: data.phase,
            });
            if (data.greeting) {
              const greetingMessage: Message = {
                role: 'assistant',
                text: data.greeting,
              };
              setMessages((previous) => (
                shouldSuppressAssistantDuplicate(previous, greetingMessage)
                  ? previous
                  : [...previous, greetingMessage]
              ));
              onMessage?.(greetingMessage, {
                phase: data.phase,
                mode: data.mode,
                runtime: data.runtime,
              });
            }
            break;

          case 'transcript':
            if (data.role && data.text) {
              const meta: MessageMeta = {
                turnId: data.turn_id,
                turnIndex: data.turn_index,
                runtime: data.runtime,
                phase: data.phase,
                mode: data.mode,
              };
              onDebugEvent?.('websocket', 'ws_transcript', {
                role: data.role,
                text: data.text,
                textPreview: data.text.slice(0, 120),
                turnId: data.turn_id,
                turnIndex: data.turn_index,
                runtime: data.runtime,
                phase: data.phase,
                mode: data.mode,
              });
              const message: Message = {
                role: data.role,
                text: data.text,
              };
              setMessages((previous) => (
                shouldSuppressAssistantDuplicate(previous, message)
                  ? previous
                  : [...previous, message]
              ));
              onMessage?.(message, meta);
            }
            break;

          case 'audio':
            if (data.data) {
              const meta: AudioPlaybackMeta = {
                turnId: data.turn_id,
                turnIndex: data.turn_index,
                runtime: data.runtime,
                phase: data.phase,
                mode: data.mode,
              };
              onDebugEvent?.('websocket', 'ws_audio', {
                turnId: data.turn_id,
                turnIndex: data.turn_index,
                runtime: data.runtime,
                phase: data.phase,
                mode: data.mode,
                payloadLength: data.data.length,
              });
              const binaryString = atob(data.data);
              const bytes = new Uint8Array(binaryString.length);
              for (let index = 0; index < binaryString.length; index++) {
                bytes[index] = binaryString.charCodeAt(index);
              }
              onAudio?.(bytes.buffer, meta);
            }
            break;

          case 'phase_changed':
            onDebugEvent?.('websocket', 'ws_phase_changed', {
              phase: data.phase,
              mode: data.mode,
              runtime: data.runtime,
              turnId: data.turn_id,
            });
            break;

          case 'error': {
            const errorMessage = data.message || 'Unknown error';
            setError(errorMessage);
            onError?.(errorMessage);
            onDebugEvent?.('websocket', 'ws_error_payload', {
              message: errorMessage,
              stage: data.stage,
              turnId: data.turn_id,
              runtime: data.runtime,
            });
            break;
          }

          case 'session_complete':
            onDebugEvent?.('websocket', 'ws_session_complete', {
              reason: data.reason,
              returnScreen: data.return_screen,
              runtime: data.runtime,
            });
            onSessionComplete?.({
              reason: data.reason || 'completed',
              returnScreen: data.return_screen || undefined,
            });
            break;
        }
      } catch (parseError) {
        console.error('Failed to parse WebSocket message:', parseError);
      }
    };

    ws.onerror = (event) => {
      console.error('WebSocket error:', event);
      setError('Connection error');
      onError?.('Connection error');
      onDebugEvent?.('websocket', 'ws_error');
    };

    ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
      const payload: DisconnectPayload = {
        code: event.code,
        reason: event.reason,
        manualClose: manualCloseRef.current,
        expectedServerClose: expectedServerCloseRef.current,
      };

      isConnectingRef.current = false;
      setIsConnected(false);
      setIsConnecting(false);
      setSessionId(null);
      wsRef.current = null;
      onDisconnect?.(payload);
      onDebugEvent?.('websocket', 'ws_closed', {
        code: payload.code,
        reason: payload.reason,
        manualClose: payload.manualClose,
        expectedServerClose: payload.expectedServerClose,
      });

      if (manualCloseRef.current || expectedServerCloseRef.current) {
        manualCloseRef.current = false;
        expectedServerCloseRef.current = false;
        endRequestedRef.current = false;
        return;
      }

      if (event.code !== 1000 && reconnectAttemptsRef.current < 3) {
        reconnectAttemptsRef.current++;
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log(`Reconnect attempt ${reconnectAttemptsRef.current}/3...`);
          onDebugEvent?.('websocket', 'ws_reconnect_attempt', {
            attempt: reconnectAttemptsRef.current,
          });
          connect();
        }, 5000);
      } else if (reconnectAttemptsRef.current >= 3) {
        console.log('Max reconnect attempts reached');
        setError('Cannot connect to server. Please refresh the page.');
      }
    };
  }, [url, userId, query, onAudio, onConnect, onDisconnect, onError, onMessage, onSessionComplete, onDebugEvent]);

  const requestSessionEnd = useCallback(() => {
    const activeSocket = wsRef.current;
    if (!activeSocket || activeSocket.readyState !== WebSocket.OPEN || endRequestedRef.current) {
      return;
    }

    expectedServerCloseRef.current = true;
    endRequestedRef.current = true;
    activeSocket.send(JSON.stringify({ type: 'end' }));
    console.log('[WS] Requested session end');
    onDebugEvent?.('websocket', 'ws_end_requested');
  }, [onDebugEvent]);

  const disconnect = useCallback((options: DisconnectOptions = {}) => {
    const {
      sendEnd = true,
      resetMessages = true,
      reason = 'User disconnected',
    } = options;

    manualCloseRef.current = true;
    expectedServerCloseRef.current = false;
    isConnectingRef.current = false;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    const activeSocket = wsRef.current;
    if (activeSocket && activeSocket.readyState === WebSocket.OPEN) {
      if (sendEnd) {
        activeSocket.send(JSON.stringify({ type: 'end' }));
        console.log('[WS] Sent end message for post-session processing');
        onDebugEvent?.('websocket', 'ws_end_sent');
        setTimeout(() => {
          if (wsRef.current === activeSocket) {
            activeSocket.close(1000, reason);
          }
        }, 500);
      } else {
        activeSocket.close(1000, reason);
      }
    } else if (activeSocket) {
      activeSocket.close(1000, reason);
    }

    setIsConnected(false);
    setIsConnecting(false);
    setSessionId(null);
    endRequestedRef.current = false;
    if (resetMessages) {
      setMessages([]);
    }
  }, [onDebugEvent]);

  const sendText = useCallback((text: string, meta?: { source?: string }) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected');
      return;
    }

    wsRef.current.send(JSON.stringify({
      type: 'text',
      text,
      source: meta?.source,
    }));
    console.log('Sent text:', text);
    onDebugEvent?.('websocket', 'ws_text_sent', {
      source: meta?.source || 'websocket_text',
      text,
      textPreview: text.slice(0, 120),
      charCount: text.length,
    });
  }, [onDebugEvent]);

  useEffect(() => () => {
    disconnect();
  }, [disconnect]);

  return {
    isConnected,
    isConnecting,
    sessionId,
    messages,
    sendText,
    connect,
    requestSessionEnd,
    disconnect,
    error,
  };
}
