import { useEffect, useRef, useCallback, useState } from 'react';
import StoryStage from './components/StoryStage';
import Transcript from './components/Transcript';
import { useStorySocket } from './hooks/useStorySocket';
import { useAudio } from './hooks/useAudio';

// Demo script — event-driven, waits for AI turn to complete before next step
const DEMO_SCRIPT: DemoStep[] = [
  { speaker: 'parent', text: 'Hello Dream Weaver! My child wants a bedtime story tonight.', waitForTurn: true },
  { speaker: 'child', text: 'I want a story about a PINK DRAGON that lives on a snowy mountain!', waitForTurn: true },
  { speaker: 'child', text: 'And the dragon should have sparkly wings and be really friendly!', waitForTurn: true },
  { speaker: 'child', text: 'No wait! The dragon should blow RAINBOW BUBBLES instead of fire! And the bubbles make flowers grow everywhere!', waitForTurn: true, isInterrupt: true },
  { speaker: 'child', text: 'Can a little bunny come ride on the dragon? A fluffy white bunny named Snowball!', waitForTurn: true },
  { speaker: 'parent', text: 'sleepy_time', waitForTurn: true },
];

interface DemoStep {
  speaker: 'parent' | 'child';
  text: string;
  waitForTurn: boolean;
  isInterrupt?: boolean;
}

function App() {
  const {
    connected,
    scene,
    transcripts,
    connect: wsConnect,
    disconnect: wsDisconnect,
    sendAudio,
    sendText,
    sendWindDown,
    setOnAudio,
    setOnTurnComplete,
  } = useStorySocket();

  const { startMic, stopMic, playAudioChunk, stopPlayback } = useAudio(sendAudio);
  const [showTranscript, setShowTranscript] = useState(true);
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoStepIdx, setDemoStepIdx] = useState(-1);
  const [speechBubble, setSpeechBubble] = useState<{ speaker: string; text: string } | null>(null);
  const [waitingForAI, setWaitingForAI] = useState(false);

  // Refs for demo orchestration
  const demoRunningRef = useRef(false);
  const turnCompleteResolveRef = useRef<(() => void) | null>(null);
  const speechBubbleTimerRef = useRef<number>(0);

  // Stable ref to playAudioChunk so the onAudio callback doesn't get re-wired
  const playAudioChunkRef = useRef(playAudioChunk);
  playAudioChunkRef.current = playAudioChunk;

  // Wire audio playback once — uses ref to avoid re-wiring on every render
  useEffect(() => {
    setOnAudio((data: ArrayBuffer) => {
      playAudioChunkRef.current(data);
    });
  }, [setOnAudio]);

  // Wire turn complete — resolve the current wait promise
  useEffect(() => {
    setOnTurnComplete(() => {
      setWaitingForAI(false);
      if (turnCompleteResolveRef.current) {
        turnCompleteResolveRef.current();
        turnCompleteResolveRef.current = null;
      }
    });
  }, [setOnTurnComplete]);

  // Helper: wait for AI turn to complete (or timeout)
  const waitForTurnComplete = useCallback((): Promise<void> => {
    return new Promise((resolve) => {
      turnCompleteResolveRef.current = resolve;
      // Safety timeout — don't wait forever
      const timer = window.setTimeout(() => {
        if (turnCompleteResolveRef.current === resolve) {
          turnCompleteResolveRef.current = null;
          resolve();
        }
      }, 45000);
      // Clean up timer when resolved
      const origResolve = resolve;
      turnCompleteResolveRef.current = () => {
        clearTimeout(timer);
        origResolve();
      };
    });
  }, []);

  // Show speech bubble for a duration
  const showBubble = useCallback((speaker: string, text: string) => {
    clearTimeout(speechBubbleTimerRef.current);
    setSpeechBubble({ speaker, text });
    speechBubbleTimerRef.current = window.setTimeout(() => {
      setSpeechBubble(null);
    }, 4000);
  }, []);

  // Run the demo script — event-driven, one step at a time
  const runDemoScript = useCallback(async () => {
    for (let i = 0; i < DEMO_SCRIPT.length; i++) {
      if (!demoRunningRef.current) break;

      const step = DEMO_SCRIPT[i];
      setDemoStepIdx(i);

      // If this is a child interrupt, stop audio first
      if (step.isInterrupt) {
        stopPlayback();
        await sleep(500); // Brief pause before child speaks
      }

      // Show the speech bubble
      const label = step.speaker === 'child' ? 'Child' : 'Parent';
      const displayText = step.text === 'sleepy_time' ? 'Time for bed... sleepy time!' : step.text;
      showBubble(label, displayText);

      // Wait a moment so the user can see the speech bubble
      await sleep(1500);

      if (!demoRunningRef.current) break;

      // Send the message
      if (step.text === 'sleepy_time') {
        sendWindDown();
      } else {
        sendText(step.text);
      }

      setWaitingForAI(true);

      // Wait for AI to finish responding
      if (step.waitForTurn) {
        await waitForTurnComplete();
      }

      // Brief pause between turns for natural feel
      if (i < DEMO_SCRIPT.length - 1) {
        await sleep(2000);
      }
    }

    // Final wind-down listening period
    if (demoRunningRef.current) {
      setDemoStepIdx(DEMO_SCRIPT.length);
      setWaitingForAI(true);
      await waitForTurnComplete();
      setSpeechBubble({ speaker: 'System', text: 'Demo complete! The story has ended.' });
    }
  }, [sendText, sendWindDown, stopPlayback, waitForTurnComplete, showBubble]);

  // Start demo
  const startDemo = useCallback(() => {
    wsConnect();
    setDemoRunning(true);
    demoRunningRef.current = true;
    setDemoStepIdx(-1);
    setSpeechBubble(null);
  }, [wsConnect]);

  // When connected + demo mode, start the script
  useEffect(() => {
    if (!connected || !demoRunning || !demoRunningRef.current) return;
    // Small delay for session to stabilize
    const t = window.setTimeout(() => {
      runDemoScript();
    }, 2000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, demoRunning]);

  const handleStart = useCallback(async () => {
    wsConnect();
    await startMic();
  }, [wsConnect, startMic]);

  const handleStop = useCallback(() => {
    demoRunningRef.current = false;
    stopMic();
    stopPlayback();
    wsDisconnect();
    setDemoRunning(false);
    setDemoStepIdx(-1);
    setSpeechBubble(null);
    setWaitingForAI(false);
    // Resolve any pending wait
    if (turnCompleteResolveRef.current) {
      turnCompleteResolveRef.current();
      turnCompleteResolveRef.current = null;
    }
  }, [stopMic, stopPlayback, wsDisconnect]);

  const currentStep = demoStepIdx >= 0 && demoStepIdx < DEMO_SCRIPT.length ? DEMO_SCRIPT[demoStepIdx] : null;

  return (
    <div style={{ width: '100vw', height: '100vh', overflow: 'hidden', background: '#000' }}>
      <StoryStage scene={scene} />
      <Transcript entries={transcripts} visible={showTranscript} />

      {/* Speech bubble — shows what the parent/child is saying */}
      {speechBubble && (
        <div style={{
          position: 'fixed',
          bottom: 80,
          left: '50%',
          transform: 'translateX(-50%)',
          maxWidth: '600px',
          padding: '14px 24px',
          borderRadius: '20px',
          background: speechBubble.speaker === 'Child'
            ? 'linear-gradient(135deg, #fbbf24, #f59e0b)'
            : speechBubble.speaker === 'Parent'
            ? 'linear-gradient(135deg, #60a5fa, #3b82f6)'
            : 'linear-gradient(135deg, #a78bfa, #7c3aed)',
          color: '#fff',
          fontSize: 16,
          fontFamily: 'Georgia, serif',
          textAlign: 'center',
          zIndex: 2500,
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          animation: 'fade_in 0.3s ease-out',
        }}>
          <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 4, fontFamily: 'system-ui', textTransform: 'uppercase', letterSpacing: 1 }}>
            {speechBubble.speaker === 'Child' ? '👦 Child says...' :
             speechBubble.speaker === 'Parent' ? '👨 Parent says...' : '✨'}
          </div>
          {speechBubble.text}
        </div>
      )}

      {/* Demo progress bar */}
      {demoRunning && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 3000,
        }}>
          {/* Progress dots */}
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            gap: 8,
            padding: '10px 20px',
            background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(8px)',
          }}>
            {DEMO_SCRIPT.map((step, i) => (
              <div key={i} style={{
                width: 12, height: 12, borderRadius: '50%',
                background: i < demoStepIdx ? '#4ade80'
                  : i === demoStepIdx ? (waitingForAI ? '#fbbf24' : '#8b5cf6')
                  : 'rgba(255,255,255,0.2)',
                border: i === demoStepIdx ? '2px solid #fff' : '2px solid transparent',
                transition: 'all 0.3s',
                boxShadow: i === demoStepIdx ? '0 0 8px rgba(139,92,246,0.8)' : 'none',
              }}
                title={`Step ${i+1}: ${step.speaker} — ${step.text.slice(0, 40)}`}
              />
            ))}
            <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12, marginLeft: 8, lineHeight: '16px' }}>
              {waitingForAI ? '🎙️ AI narrating...' :
               currentStep ? `${currentStep.speaker === 'child' ? '👦' : '👨'} ${currentStep.speaker}` :
               demoStepIdx >= DEMO_SCRIPT.length ? '✨ Complete' : 'Starting...'}
            </span>
          </div>
        </div>
      )}

      {/* Bottom control bar */}
      <div style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: '16px',
        padding: '12px 24px',
        background: 'rgba(0,0,0,0.7)',
        backdropFilter: 'blur(10px)',
        zIndex: 2000,
      }}>
        {!connected ? (
          <>
            <button onClick={startDemo} style={btnStyle('#8b5cf6')}>
              🎬 Run Demo
            </button>
            <button onClick={handleStart} style={btnStyle('#4ade80')}>
              🎤 Live Mode (Mic)
            </button>
          </>
        ) : (
          <>
            <button onClick={handleStop} style={btnStyle('#f87171')}>
              ⏹ Stop
            </button>
            {!demoRunning && (
              <button onClick={sendWindDown} style={btnStyle('#a78bfa')}>
                😴 Sleepy Time
              </button>
            )}
          </>
        )}

        <div style={{
          position: 'absolute',
          right: 24,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: 'rgba(255,255,255,0.6)',
          fontSize: 12,
        }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: connected ? '#4ade80' : '#f87171',
            boxShadow: connected ? '0 0 8px #4ade80' : 'none',
          }} />
          {connected ? 'Live' : 'Offline'}
        </div>
      </div>

      {/* Transcript toggle */}
      <button
        onClick={() => setShowTranscript(!showTranscript)}
        style={{
          position: 'fixed',
          top: demoRunning ? 44 : 16,
          left: 16,
          zIndex: 2000,
          background: 'rgba(0,0,0,0.4)',
          border: '1px solid rgba(255,255,255,0.2)',
          borderRadius: 8,
          color: '#fff',
          padding: '6px 12px',
          fontSize: 12,
          cursor: 'pointer',
          transition: 'top 0.3s ease',
        }}
      >
        {showTranscript ? 'Hide' : 'Show'} Transcript
      </button>
    </div>
  );
}

function btnStyle(bg: string): React.CSSProperties {
  return {
    padding: '12px 28px',
    fontSize: '16px',
    fontWeight: 600,
    fontFamily: 'system-ui, sans-serif',
    border: 'none',
    borderRadius: '999px',
    background: bg,
    color: '#fff',
    cursor: 'pointer',
    boxShadow: `0 4px 14px ${bg}50`,
    transition: 'transform 0.1s',
  };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default App;
