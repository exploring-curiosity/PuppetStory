import { useRef, useState, useCallback, useEffect } from 'react';
import type { SetSceneData } from '../engine/SceneManager';
import type { ActionSequence } from '../engine/KeyframeEngine';

export interface Transcript {
  role: 'narrator' | 'user';
  text: string;
  ts: number;
}

type AudioCallback = (data: ArrayBuffer) => void;
type TurnCompleteCallback = () => void;
type SetSceneCallback = (data: SetSceneData) => void;
type ActionSequenceCallback = (data: ActionSequence) => void;

interface UseStorySocketReturn {
  connected: boolean;
  transcripts: Transcript[];
  connect: (storyId: string) => void;
  disconnect: () => void;
  sendAudio: (data: ArrayBuffer) => void;
  sendText: (text: string) => void;
  sendWindDown: () => void;
  setOnAudio: (cb: AudioCallback) => void;
  setOnTurnComplete: (cb: TurnCompleteCallback) => void;
  setOnSetScene: (cb: SetSceneCallback) => void;
  setOnActionSequence: (cb: ActionSequenceCallback) => void;
}

export function useStorySocket(): UseStorySocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const onAudioRef = useRef<AudioCallback | null>(null);
  const onTurnCompleteRef = useRef<TurnCompleteCallback | null>(null);
  const onSetSceneRef = useRef<SetSceneCallback | null>(null);
  const onActionSequenceRef = useRef<ActionSequenceCallback | null>(null);

  const setOnAudio = useCallback((cb: AudioCallback) => { onAudioRef.current = cb; }, []);
  const setOnTurnComplete = useCallback((cb: TurnCompleteCallback) => { onTurnCompleteRef.current = cb; }, []);
  const setOnSetScene = useCallback((cb: SetSceneCallback) => { onSetSceneRef.current = cb; }, []);
  const setOnActionSequence = useCallback((cb: ActionSequenceCallback) => { onActionSequenceRef.current = cb; }, []);

  const connect = useCallback((storyId: string) => {
    if (wsRef.current) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/story`;
    console.log('[WS] Connecting to', wsUrl, 'with story:', storyId);

    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WS] Connected, sending init');
      // Send init message with story_id
      ws.send(JSON.stringify({ type: 'init', story_id: storyId }));
      setConnected(true);
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        onAudioRef.current?.(event.data);
      } else {
        try {
          const msg = JSON.parse(event.data);

          if (msg.type === 'set_scene') {
            console.log('[WS] set_scene:', msg.data?.background_id);
            onSetSceneRef.current?.(msg.data);
          } else if (msg.type === 'action_sequence') {
            console.log('[WS] action_sequence:', Object.keys(msg.data?.puppets || {}));
            onActionSequenceRef.current?.(msg.data);
          } else if (msg.type === 'transcript') {
            setTranscripts(prev => [...prev, { role: msg.role, text: msg.text, ts: Date.now() }]);
          } else if (msg.type === 'narration_text') {
            setTranscripts(prev => [...prev, { role: 'narrator', text: msg.text, ts: Date.now() }]);
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
    return () => { wsRef.current?.close(); };
  }, []);

  return {
    connected,
    transcripts,
    connect,
    disconnect,
    sendAudio,
    sendText,
    sendWindDown,
    setOnAudio,
    setOnTurnComplete,
    setOnSetScene,
    setOnActionSequence,
  };
}
