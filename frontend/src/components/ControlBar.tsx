import React from 'react';

interface Props {
  connected: boolean;
  onStart: () => void;
  onStop: () => void;
  onWindDown: () => void;
}

const ControlBar: React.FC<Props> = ({ connected, onStart, onStop, onWindDown }) => {
  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      gap: '16px',
      padding: '16px 24px',
      background: 'rgba(0,0,0,0.6)',
      backdropFilter: 'blur(10px)',
      zIndex: 2000,
    }}>
      {!connected ? (
        <button onClick={onStart} style={btnStyle('#4ade80', '#166534')}>
          🎤 Start Story
        </button>
      ) : (
        <>
          <button onClick={onStop} style={btnStyle('#f87171', '#991b1b')}>
            ⏹ Stop
          </button>
          <button onClick={onWindDown} style={btnStyle('#a78bfa', '#4c1d95')}>
            😴 Sleepy Time
          </button>
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
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: connected ? '#4ade80' : '#f87171',
        }} />
        {connected ? 'Connected' : 'Disconnected'}
      </div>
    </div>
  );
};

function btnStyle(bg: string, _hoverBg?: string): React.CSSProperties {
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
    transition: 'transform 0.15s, box-shadow 0.15s',
    boxShadow: `0 4px 12px ${bg}40`,
  };
}

export default ControlBar;
