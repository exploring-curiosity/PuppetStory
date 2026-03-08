import { useRef, useCallback, useEffect } from 'react';

/**
 * Audio handler for Dream Weaver.
 * - Captures mic audio as 16kHz PCM and sends via callback
 * - Plays incoming 24kHz PCM audio using a ScriptProcessorNode ring buffer
 *   for gapless, jitter-free streaming playback
 * - Supports stopPlayback() to immediately silence audio
 */

const SAMPLE_RATE = 24000;
// Ring buffer: 10 seconds of audio capacity
const RING_BUFFER_SIZE = SAMPLE_RATE * 10;

interface UseAudioReturn {
  startMic: () => Promise<void>;
  stopMic: () => void;
  playAudioChunk: (data: ArrayBuffer) => void;
  stopPlayback: () => void;
}

export function useAudio(onAudioData: (pcm: ArrayBuffer) => void): UseAudioReturn {
  const micStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const scriptNodeRef = useRef<ScriptProcessorNode | null>(null);
  const micActiveRef = useRef(false);

  // Ring buffer for gapless playback
  const ringBufferRef = useRef(new Float32Array(RING_BUFFER_SIZE));
  const writeIndexRef = useRef(0);
  const readIndexRef = useRef(0);
  const playCtxRef = useRef<AudioContext | null>(null);
  const playProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const playingRef = useRef(false);

  const startMic = useCallback(async () => {
    if (micActiveRef.current) return;

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    micStreamRef.current = stream;
    const ctx = new AudioContext({ sampleRate: 16000 });
    audioContextRef.current = ctx;

    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    scriptNodeRef.current = processor;

    processor.onaudioprocess = (e) => {
      const float32 = e.inputBuffer.getChannelData(0);
      const int16 = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        const s = Math.max(-1, Math.min(1, float32[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      onAudioData(int16.buffer);
    };

    source.connect(processor);
    processor.connect(ctx.destination);
    micActiveRef.current = true;
  }, [onAudioData]);

  const stopMic = useCallback(() => {
    micActiveRef.current = false;
    scriptNodeRef.current?.disconnect();
    scriptNodeRef.current = null;
    audioContextRef.current?.close();
    audioContextRef.current = null;
    micStreamRef.current?.getTracks().forEach((t) => t.stop());
    micStreamRef.current = null;
  }, []);

  // Ensure playback AudioContext + ScriptProcessor are running
  const ensurePlayback = useCallback(() => {
    if (playingRef.current) return;

    const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
    playCtxRef.current = ctx;

    // ScriptProcessor pulls from ring buffer — guarantees gapless output
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    playProcessorRef.current = processor;

    processor.onaudioprocess = (e) => {
      const output = e.outputBuffer.getChannelData(0);
      const ring = ringBufferRef.current;
      let rIdx = readIndexRef.current;
      const wIdx = writeIndexRef.current;

      for (let i = 0; i < output.length; i++) {
        if (rIdx !== wIdx) {
          output[i] = ring[rIdx];
          rIdx = (rIdx + 1) % RING_BUFFER_SIZE;
        } else {
          output[i] = 0; // Silence when buffer is empty
        }
      }
      readIndexRef.current = rIdx;
    };

    // Connect processor -> destination (the processor is the source)
    processor.connect(ctx.destination);
    // ScriptProcessor needs an input to fire onaudioprocess
    // Create a silent oscillator as input
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    gain.gain.value = 0;
    osc.connect(gain);
    gain.connect(processor);
    osc.start();

    playingRef.current = true;
  }, []);

  const playAudioChunk = useCallback((data: ArrayBuffer) => {
    ensurePlayback();

    const int16 = new Int16Array(data);
    if (int16.length === 0) return;

    const ring = ringBufferRef.current;
    let wIdx = writeIndexRef.current;

    for (let i = 0; i < int16.length; i++) {
      ring[wIdx] = int16[i] / 0x8000;
      wIdx = (wIdx + 1) % RING_BUFFER_SIZE;
    }
    writeIndexRef.current = wIdx;
  }, [ensurePlayback]);

  const stopPlayback = useCallback(() => {
    // Clear ring buffer
    writeIndexRef.current = 0;
    readIndexRef.current = 0;
    ringBufferRef.current.fill(0);

    // Tear down playback context
    playProcessorRef.current?.disconnect();
    playProcessorRef.current = null;
    if (playCtxRef.current && playCtxRef.current.state !== 'closed') {
      playCtxRef.current.close();
    }
    playCtxRef.current = null;
    playingRef.current = false;

    // Also stop browser TTS
    window.speechSynthesis?.cancel();
  }, []);

  useEffect(() => {
    return () => {
      stopMic();
      stopPlayback();
    };
  }, [stopMic, stopPlayback]);

  return {
    startMic,
    stopMic,
    playAudioChunk,
    stopPlayback,
  };
}
