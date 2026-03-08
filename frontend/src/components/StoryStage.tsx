import React from 'react';
import SceneElement from './SceneElement';
import type { SceneElementData } from './SceneElement';
import '../styles/stage.css';
import '../styles/animations.css';

export interface SceneData {
  scene_title: string;
  mood: string;
  transition: string;
  elements: SceneElementData[];
}

interface Props {
  scene: SceneData | null;
}

function isBackground(el: SceneElementData): boolean {
  if (el.z_index > 0) return false;
  if (el.z_index === 0) return true;
  const id = (el.id || '').toLowerCase();
  const bgKeywords = ['background', 'backdrop', 'scenery', 'landscape', 'environment', 'setting'];
  return bgKeywords.some(kw => id.includes(kw));
}

const StoryStage: React.FC<Props> = ({ scene }) => {
  const mood = scene?.mood || '';
  const transition = scene?.transition || 'fade';
  const elements = scene?.elements || [];

  const bgElements = elements.filter(isBackground);
  const puppetElements = elements.filter(el => !isBackground(el));

  const transitionClass = transition === 'fade' ? 'stage-transition-fade' : '';

  return (
    <div className={`story-stage mood-${mood} ${transitionClass}`}>
      {/* Starfield for sleepy/magical moods */}
      {(mood === 'sleepy' || mood === 'magical') && (
        <div className="starfield">
          {Array.from({ length: 20 }).map((_, i) => (
            <div
              key={i}
              className="star anim-twinkle anim-slow"
              style={{
                position: 'absolute',
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 60}%`,
                width: `${2 + Math.random() * 4}px`,
                height: `${2 + Math.random() * 4}px`,
                borderRadius: '50%',
                background: 'white',
                opacity: 0.6,
                animationDelay: `${Math.random() * 3}s`,
              }}
            />
          ))}
        </div>
      )}

      {/* Scene title overlay */}
      {scene?.scene_title && (
        <div style={{
          position: 'absolute',
          top: 12,
          left: '50%',
          transform: 'translateX(-50%)',
          color: 'rgba(255,255,255,0.6)',
          fontSize: '14px',
          fontFamily: 'Georgia, serif',
          fontStyle: 'italic',
          zIndex: 1000,
          pointerEvents: 'none',
        }}>
          {scene.scene_title}
        </div>
      )}

      {/* Background elements — fullscreen */}
      {bgElements.map((el) => (
        <div
          key={el.id}
          className="scene-background"
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 0,
            overflow: 'hidden',
          }}
        >
          {el.image && (
            <img
              src={el.image}
              alt=""
              draggable={false}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                display: 'block',
              }}
            />
          )}
        </div>
      ))}

      {/* Puppet elements — positioned on stage */}
      {puppetElements.map((el) => (
        <SceneElement key={el.id} element={el} />
      ))}

      {/* Empty state */}
      {!scene && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'rgba(255,255,255,0.5)',
          fontFamily: 'Georgia, serif',
          gap: '16px',
        }}>
          <div style={{ fontSize: '64px' }}>🌙</div>
          <div style={{ fontSize: '24px' }}>Dream Weaver</div>
          <div style={{ fontSize: '14px', opacity: 0.6 }}>Press the mic to start your bedtime story...</div>
        </div>
      )}
    </div>
  );
};

export default StoryStage;
