import { useEffect, useRef, useCallback, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import PuppetCanvas, { type PuppetCanvasHandle } from '../components/PuppetCanvas';
import { useStorySocket } from '../hooks/useStorySocket';
import { useAudio } from '../hooks/useAudio';
import { fetchStory, fetchAssets, type StoryData } from '../lib/api';
import { Mic, MicOff, Moon, ArrowLeft, MessageSquare, X } from 'lucide-react';

export default function PlaybackPage() {
  const { storyId } = useParams<{ storyId: string }>();
  const navigate = useNavigate();
  const canvasRef = useRef<PuppetCanvasHandle>(null);

  const [story, setStory] = useState<StoryData | null>(null);
  const [micActive, setMicActive] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const [mood, setMood] = useState('calm');
  const [status, setStatus] = useState<'loading' | 'connecting' | 'live' | 'ended'>('loading');

  const {
    connected,
    transcripts,
    connect: wsConnect,
    disconnect: wsDisconnect,
    sendAudio,
    sendWindDown,
    setOnAudio,
    setOnTurnComplete,
    setOnSetScene,
    setOnActionSequence,
  } = useStorySocket();

  const { startMic, stopMic, playAudioChunk, stopPlayback } = useAudio(sendAudio);

  // Stable ref for audio callback
  const playAudioChunkRef = useRef(playAudioChunk);
  playAudioChunkRef.current = playAudioChunk;

  // Wire audio playback
  useEffect(() => {
    setOnAudio((data: ArrayBuffer) => {
      playAudioChunkRef.current(data);
    });
  }, [setOnAudio]);

  // Wire set_scene callback
  useEffect(() => {
    setOnSetScene(async (data) => {
      setMood(data.mood || 'calm');
      if (canvasRef.current) {
        await canvasRef.current.setScene(data);
      }
    });
  }, [setOnSetScene]);

  // Wire action_sequence callback
  useEffect(() => {
    setOnActionSequence((data) => {
      if (canvasRef.current) {
        canvasRef.current.playActionSequence(data);
      }
    });
  }, [setOnActionSequence]);

  // Wire turn complete
  useEffect(() => {
    setOnTurnComplete(() => {
      // Could use this for UI indicators
    });
  }, [setOnTurnComplete]);

  // Load story + assets + connect WebSocket
  useEffect(() => {
    if (!storyId) return;
    let cancelled = false;

    (async () => {
      try {
        const [storyData, assetData] = await Promise.all([
          fetchStory(storyId),
          fetchAssets(storyId),
        ]);

        if (cancelled) return;
        setStory(storyData);

        // Preload puppet textures into PixiJS
        if (canvasRef.current && assetData.assets) {
          const preloadPromises = [];
          for (const char of storyData.characters) {
            if (assetData.assets[char.id]) {
              preloadPromises.push(
                canvasRef.current.preloadPuppet(char.id, assetData.assets[char.id])
              );
            }
          }
          await Promise.all(preloadPromises);
        }

        setStatus('connecting');
        wsConnect(storyId);
      } catch (e) {
        console.error('[PlaybackPage] Failed to load:', e);
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storyId]);

  // Update status when connected
  useEffect(() => {
    if (connected) {
      setStatus('live');
    }
  }, [connected]);

  const handleMicToggle = useCallback(async () => {
    if (micActive) {
      stopMic();
      setMicActive(false);
    } else {
      await startMic();
      setMicActive(true);
    }
  }, [micActive, startMic, stopMic]);

  const handleWindDown = useCallback(() => {
    sendWindDown();
  }, [sendWindDown]);

  const handleExit = useCallback(() => {
    stopMic();
    stopPlayback();
    wsDisconnect();
    navigate('/');
  }, [stopMic, stopPlayback, wsDisconnect, navigate]);

  // Mood gradient overlays
  const moodOverlay: Record<string, string> = {
    exciting: 'bg-gradient-to-b from-orange-900/20 to-transparent',
    calm: 'bg-gradient-to-b from-blue-900/10 to-transparent',
    mysterious: 'bg-gradient-to-b from-purple-900/30 to-transparent',
    funny: 'bg-gradient-to-b from-yellow-900/15 to-transparent',
    magical: 'bg-gradient-to-b from-violet-900/20 to-transparent',
    sleepy: 'bg-gradient-to-b from-indigo-950/40 to-transparent',
    tense: 'bg-gradient-to-b from-red-900/20 to-transparent',
    triumphant: 'bg-gradient-to-b from-amber-900/20 to-transparent',
  };

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black">
      {/* PixiJS Canvas */}
      <PuppetCanvas ref={canvasRef} />

      {/* Mood overlay */}
      <div className={`absolute inset-0 pointer-events-none transition-all duration-1000 ${moodOverlay[mood] || ''}`} />

      {/* Story title */}
      {story && status === 'live' && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 pointer-events-none">
          <span className="text-sm text-white/40 font-serif italic">
            {story.title}
          </span>
        </div>
      )}

      {/* Loading / connecting overlay */}
      {status !== 'live' && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="text-center">
            <div className="w-10 h-10 border-4 border-violet-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-slate-300 text-lg">
              {status === 'loading' ? 'Loading story...' : 'Connecting to Puppet Master...'}
            </p>
          </div>
        </div>
      )}

      {/* Transcript panel */}
      {showTranscript && (
        <div className="absolute top-0 right-0 bottom-16 w-80 z-20 bg-black/70 backdrop-blur-md border-l border-white/10 flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
            <span className="text-sm font-medium text-white/70">Transcript</span>
            <button onClick={() => setShowTranscript(false)} className="text-white/40 hover:text-white transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {transcripts.length === 0 && (
              <p className="text-white/30 text-sm italic text-center mt-8">Story will appear here...</p>
            )}
            {transcripts.map((t, i) => (
              <div
                key={i}
                className={`text-sm px-3 py-2 rounded-lg ${
                  t.role === 'narrator'
                    ? 'bg-violet-500/10 text-violet-200 border-l-2 border-violet-500'
                    : 'bg-amber-500/10 text-amber-200 border-l-2 border-amber-500'
                }`}
              >
                <span className="text-xs opacity-50 block mb-1">
                  {t.role === 'narrator' ? 'Puppet Master' : 'You'}
                </span>
                {t.text}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bottom control bar */}
      <div className="absolute bottom-0 left-0 right-0 z-20 flex items-center justify-center gap-4 py-4 px-6 bg-gradient-to-t from-black/80 to-transparent">
        {/* Back button */}
        <button
          onClick={handleExit}
          className="p-3 rounded-full bg-white/10 hover:bg-white/20 text-white/60 hover:text-white transition-all"
          title="Exit story"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>

        {/* Mic toggle */}
        <button
          onClick={handleMicToggle}
          disabled={status !== 'live'}
          className={`p-4 rounded-full transition-all shadow-lg ${
            micActive
              ? 'bg-red-500 hover:bg-red-400 text-white shadow-red-500/30'
              : 'bg-violet-600 hover:bg-violet-500 text-white shadow-violet-500/30'
          } disabled:opacity-30 disabled:cursor-not-allowed`}
          title={micActive ? 'Mute microphone' : 'Unmute microphone'}
        >
          {micActive ? <Mic className="w-6 h-6" /> : <MicOff className="w-6 h-6" />}
        </button>

        {/* Wind down */}
        <button
          onClick={handleWindDown}
          disabled={status !== 'live'}
          className="p-3 rounded-full bg-white/10 hover:bg-indigo-500/30 text-white/60 hover:text-indigo-300 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
          title="Sleepy time — wind down the story"
        >
          <Moon className="w-5 h-5" />
        </button>

        {/* Transcript toggle */}
        <button
          onClick={() => setShowTranscript(!showTranscript)}
          className={`p-3 rounded-full transition-all ${
            showTranscript
              ? 'bg-violet-500/30 text-violet-300'
              : 'bg-white/10 hover:bg-white/20 text-white/60 hover:text-white'
          }`}
          title="Toggle transcript"
        >
          <MessageSquare className="w-5 h-5" />
        </button>

        {/* Connection indicator */}
        <div className="absolute right-6 flex items-center gap-2 text-xs text-white/40">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 shadow-sm shadow-emerald-400' : 'bg-red-400'}`} />
          {connected ? 'Live' : 'Offline'}
        </div>
      </div>
    </div>
  );
}
