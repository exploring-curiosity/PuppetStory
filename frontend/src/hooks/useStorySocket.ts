import { useRef, useState, useCallback, useEffect } from 'react';
import type { SceneData } from '../components/StoryStage';

export interface Transcript {
  role: 'narrator' | 'user';
  text: string;
  ts: number;
}

type AudioCallback = (data: ArrayBuffer) => void;
type TurnCompleteCallback = () => void;

interface UseStorySocketReturn {
  connected: boolean;
  scene: SceneData | null;
  transcripts: Transcript[];
  connect: () => void;
  disconnect: () => void;
  sendAudio: (data: ArrayBuffer) => void;
  sendText: (text: string) => void;
  sendWindDown: () => void;
  setOnAudio: (cb: AudioCallback) => void;
  setOnTurnComplete: (cb: TurnCompleteCallback) => void;
}

export function useStorySocket(): UseStorySocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [scene, setScene] = useState<SceneData | null>(null);
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const onAudioRef = useRef<AudioCallback | null>(null);
  const onTurnCompleteRef = useRef<TurnCompleteCallback | null>(null);

  const setOnAudio = useCallback((cb: AudioCallback) => {
    onAudioRef.current = cb;
  }, []);

  const setOnTurnComplete = useCallback((cb: TurnCompleteCallback) => {
    onTurnCompleteRef.current = cb;
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/story`;
    console.log('[WS] Connecting to', wsUrl);

    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WS] Connected');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Stream audio directly to the playback callback — no state accumulation
        onAudioRef.current?.(event.data);
      } else {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'scene') {
            console.log('[WS] Scene received:', msg.data?.scene_title);
            setScene(msg.data);
          } else if (msg.type === 'transcript') {
            setTranscripts((prev) => [
              ...prev,
              { role: msg.role, text: msg.text, ts: Date.now() },
            ]);
          } else if (msg.type === 'narration_text') {
            // Also add narration text to transcript (it's already spoken by browser TTS or audio)
            setTranscripts((prev) => [
              ...prev,
              { role: 'narrator', text: msg.text, ts: Date.now() },
            ]);
          } else if (msg.type === 'turn_complete') {
            console.log('[WS] Turn complete');
            onTurnCompleteRef.current?.();
          } else if (msg.type === 'error') {
            console.error('[WS] Server error:', msg.message);
          }
        } catch (e) {
          console.warn('[WS] Failed to parse message', e);
        }
      }
    };

    ws.onclose = () => {
      console.log('[WS] Disconnected');
      wsRef.current = null;
      setConnected(false);
    };

    ws.onerror = (e) => {
      console.error('[WS] Error', e);
    };
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
      setConnected(false);
    }
  }, []);

  const sendAudio = useCallback((data: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  const sendText = useCallback((text: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'user_text', text }));
    }
  }, []);

  const sendWindDown = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'wind_down' }));
    }
  }, []);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return {
    connected,
    scene,
    transcripts,
    connect,
    disconnect,
    sendAudio,
    sendText,
    sendWindDown,
    setOnAudio,
    setOnTurnComplete,
  };
}
