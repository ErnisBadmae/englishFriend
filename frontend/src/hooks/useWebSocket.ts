import { useCallback, useEffect, useRef, useState } from 'react';

interface Message {
  role: 'user' | 'assistant';
  text: string;
}

interface WebSocketMessage {
  type: 'connected' | 'transcript' | 'audio' | 'error' | 'session_complete';
  role?: 'user' | 'assistant';
  text?: string;
  data?: string;
  format?: string;
  message?: string;
  session_id?: string;
  greeting?: string;
  reason?: string;
  return_screen?: string;
}

interface UseWebSocketOptions {
  url: string;
  userId: number;
  onMessage?: (message: Message) => void;
  onAudio?: (audioData: ArrayBuffer) => void;
  onError?: (error: string) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onSessionComplete?: (payload: {
    reason: string;
    returnScreen?: string;
  }) => void;
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
  sendText: (text: string) => void;
  connect: () => void;
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

  const connect = useCallback(() => {
    if (
      wsRef.current?.readyState === WebSocket.OPEN
      || wsRef.current?.readyState === WebSocket.CONNECTING
      || isConnectingRef.current
    ) {
      return;
    }

    manualCloseRef.current = false;
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

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      isConnectingRef.current = false;
      setIsConnected(true);
      setIsConnecting(false);
      reconnectAttemptsRef.current = 0;
      onConnect?.();
    };

    ws.onmessage = (event) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data);
        console.log('WebSocket message:', data);

        switch (data.type) {
          case 'connected':
            console.log('Session started:', data.session_id);
            setSessionId(data.session_id || null);
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
              onMessage?.(greetingMessage);
            }
            break;

          case 'transcript':
            if (data.role && data.text) {
              const message: Message = {
                role: data.role,
                text: data.text,
              };
              setMessages((previous) => (
                shouldSuppressAssistantDuplicate(previous, message)
                  ? previous
                  : [...previous, message]
              ));
              onMessage?.(message);
            }
            break;

          case 'audio':
            if (data.data) {
              const binaryString = atob(data.data);
              const bytes = new Uint8Array(binaryString.length);
              for (let index = 0; index < binaryString.length; index++) {
                bytes[index] = binaryString.charCodeAt(index);
              }
              onAudio?.(bytes.buffer);
            }
            break;

          case 'error': {
            const errorMessage = data.message || 'Unknown error';
            setError(errorMessage);
            onError?.(errorMessage);
            break;
          }

          case 'session_complete':
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
    };

    ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
      isConnectingRef.current = false;
      setIsConnected(false);
      setIsConnecting(false);
      setSessionId(null);
      wsRef.current = null;
      onDisconnect?.();

      if (manualCloseRef.current) {
        manualCloseRef.current = false;
        return;
      }

      if (event.code !== 1000 && reconnectAttemptsRef.current < 3) {
        reconnectAttemptsRef.current++;
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log(`Reconnect attempt ${reconnectAttemptsRef.current}/3...`);
          connect();
        }, 5000);
      } else if (reconnectAttemptsRef.current >= 3) {
        console.log('Max reconnect attempts reached');
        setError('Cannot connect to server. Please refresh the page.');
      }
    };
  }, [url, userId, query, onAudio, onConnect, onDisconnect, onError, onMessage, onSessionComplete]);

  const disconnect = useCallback((options: DisconnectOptions = {}) => {
    const {
      sendEnd = true,
      resetMessages = true,
      reason = 'User disconnected',
    } = options;

    manualCloseRef.current = true;
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
    if (resetMessages) {
      setMessages([]);
    }
  }, []);

  const sendText = useCallback((text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected');
      return;
    }

    wsRef.current.send(JSON.stringify({
      type: 'text',
      text,
    }));
    console.log('Sent text:', text);
  }, []);

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
    disconnect,
    error,
  };
}
