/**
 * Hook для WebSocket соединения с бэкендом.
 *
 * Протокол:
 * - Client -> Server: {"type": "text", "text": "распознанный текст"}
 * - Server -> Client: {"type": "transcript", "role": "assistant", "text": "ответ"}
 * - Server -> Client: {"type": "audio", "data": "<base64 MP3>", "format": "mp3"}
 */

import { useState, useEffect, useRef, useCallback } from 'react';

interface Message {
  role: 'user' | 'assistant';
  text: string;
}

interface WebSocketMessage {
  type: 'connected' | 'transcript' | 'audio' | 'error';
  role?: 'user' | 'assistant';
  text?: string;
  data?: string;
  format?: string;
  message?: string;
  session_id?: string;
}

interface UseWebSocketOptions {
  url: string;
  userId: number;
  onMessage?: (message: Message) => void;
  onAudio?: (audioData: ArrayBuffer) => void;
  onError?: (error: string) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  isConnecting: boolean;
  messages: Message[];
  sendText: (text: string) => void;
  connect: () => void;
  disconnect: () => void;
  error: string | null;
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
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);

  // Подключение к WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (isConnecting) return;

    setIsConnecting(true);
    setError(null);

    const wsUrl = `${url}?user_id=${userId}`;
    console.log('Connecting to WebSocket:', wsUrl);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      setIsConnecting(false);
      reconnectAttemptsRef.current = 0; // Reset on success
      onConnect?.();
    };

    ws.onmessage = (event) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data);
        console.log('WebSocket message:', data);

        switch (data.type) {
          case 'connected':
            console.log('Session started:', data.session_id);
            break;

          case 'transcript':
            if (data.role && data.text) {
              const message: Message = {
                role: data.role,
                text: data.text,
              };
              setMessages(prev => [...prev, message]);
              onMessage?.(message);
            }
            break;

          case 'audio':
            if (data.data) {
              // Декодируем base64 в ArrayBuffer
              const binaryString = atob(data.data);
              const bytes = new Uint8Array(binaryString.length);
              for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
              }
              onAudio?.(bytes.buffer);
            }
            break;

          case 'error':
            const errorMsg = data.message || 'Unknown error';
            setError(errorMsg);
            onError?.(errorMsg);
            break;
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    ws.onerror = (event) => {
      console.error('WebSocket error:', event);
      setError('Connection error');
      onError?.('Connection error');
    };

    ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
      setIsConnected(false);
      setIsConnecting(false);
      wsRef.current = null;
      onDisconnect?.();

      // Автоматическое переподключение через 5 секунд (максимум 3 попытки)
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
  }, [url, userId, isConnecting, onConnect, onDisconnect, onMessage, onAudio, onError]);

  // Отключение
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected');
      wsRef.current = null;
    }

    setIsConnected(false);
    setMessages([]);
  }, []);

  // Отправка текста
  const sendText = useCallback((text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected');
      return;
    }

    const message = JSON.stringify({
      type: 'text',
      text: text,
    });

    wsRef.current.send(message);
    console.log('Sent text:', text);
  }, []);

  // Cleanup при размонтировании
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    isConnecting,
    messages,
    sendText,
    connect,
    disconnect,
    error,
  };
}
