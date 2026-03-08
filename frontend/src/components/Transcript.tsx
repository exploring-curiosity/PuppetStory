import React, { useEffect, useRef } from 'react';

interface TranscriptEntry {
  role: 'narrator' | 'user';
  text: string;
  ts: number;
}

interface Props {
  entries: TranscriptEntry[];
  visible: boolean;
}

const Transcript: React.FC<Props> = ({ entries, visible }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  if (!visible || entries.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      right: 16,
      top: 16,
      bottom: 80,
      width: '300px',
      background: 'rgba(0,0,0,0.5)',
      backdropFilter: 'blur(8px)',
      borderRadius: '12px',
      padding: '16px',
      overflowY: 'auto',
      zIndex: 1500,
      fontFamily: 'system-ui, sans-serif',
      fontSize: '13px',
      lineHeight: 1.5,
    }}>
      <div style={{ color: 'rgba(255,255,255,0.5)', marginBottom: 8, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>
        Transcript
      </div>
      {entries.map((e, i) => (
        <span
          key={i}
          style={{
            color: e.role === 'narrator' ? 'rgba(255,255,255,0.85)' : '#a78bfa',
          }}
        >
          {e.text}
        </span>
      ))}
      <div ref={bottomRef} />
    </div>
  );
};

export default Transcript;
