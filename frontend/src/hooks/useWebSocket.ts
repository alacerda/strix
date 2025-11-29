import { useEffect, useRef, useState } from 'react';
import { WebSocketClient } from '@/lib/websocket';
import type { WebSocketMessage } from '@/types';

export function useWebSocket(scanId: string | null = null) {
  const [connected, setConnected] = useState(false);
  const clientRef = useRef<WebSocketClient | null>(null);

  useEffect(() => {
    const client = new WebSocketClient(scanId);
    clientRef.current = client;

    const unsubscribeConnection = client.onConnectionChange(setConnected);
    client.connect();

    return () => {
      unsubscribeConnection();
      client.disconnect();
    };
  }, [scanId]);

  const on = (eventType: string, handler: (message: WebSocketMessage) => void) => {
    if (clientRef.current) {
      return clientRef.current.on(eventType, handler);
    }
    return () => {};
  };

  const subscribe = (scanIds: string[]) => {
    if (clientRef.current) {
      clientRef.current.subscribe(scanIds);
    }
  };

  const unsubscribe = (scanIds: string[]) => {
    if (clientRef.current) {
      clientRef.current.unsubscribe(scanIds);
    }
  };

  return {
    connected,
    on,
    subscribe,
    unsubscribe,
  };
}

