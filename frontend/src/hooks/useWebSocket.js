import { useEffect, useState, useRef } from 'react';
import { io } from 'socket.io-client';

/**
 * Connects to the AgentOps backend WebSocket, subscribes to all 4 channels,
 * and exposes connection status + the last received event.
 */
export function useWebSocket() {
  const [status, setStatus] = useState('connecting');
  const [lastEvent, setLastEvent] = useState(null);
  const [eventCount, setEventCount] = useState(0);
  const socketRef = useRef(null);

  useEffect(() => {
    const WS_URL = import.meta.env.VITE_WS_URL || 'http://localhost:4000';
    const TOKEN = import.meta.env.VITE_WS_TOKEN || 'dev_ws_token_replace_me_in_prod';

    const socket = io(WS_URL, {
      auth: { token: TOKEN },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setStatus('connected');
      socket.emit('subscribe', ['pipelines', 'approvals', 'deployments', 'incidents']);
    });

    socket.on('disconnect', () => {
      setStatus('disconnected');
    });

    socket.on('connect_error', () => {
      setStatus('disconnected');
    });

    socket.on('event', (envelope) => {
      setLastEvent(envelope);
      setEventCount((n) => n + 1);
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, []);

  return { status, lastEvent, eventCount, socket: socketRef.current };
}
