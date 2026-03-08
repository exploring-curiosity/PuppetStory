import React from 'react';

export interface SceneElementData {
  id: string;
  description?: string;
  is_new?: boolean;
  image?: string;
  position_x: number;
  position_y: number;
  scale?: number;
  z_index: number;
  animation: {
    type: string;
    speed: string;
    intensity?: number;
  };
}

interface Props {
  element: SceneElementData;
}

const speedClass: Record<string, string> = {
  slow: 'anim-slow',
  medium: 'anim-medium',
  fast: 'anim-fast',
};

const SceneElement: React.FC<Props> = ({ element }) => {
  const { id, image, position_x, position_y, scale = 1, z_index, animation } = element;

  const animClass = `anim-${animation.type}`;
  const spdClass = speedClass[animation.speed] || 'anim-medium';

  // Map intensity to CSS custom properties
  const intensity = animation.intensity ?? 0.5;
  const intensityPx = intensity * 20;
  const intensityDeg = intensity * 25;
  const intensityScale = 1 + intensity * 0.2;

  // Size based on scale — base size 350px for visible puppets
  const size = 350 * scale;

  const style: React.CSSProperties = {
    left: `${position_x}%`,
    top: `${position_y}%`,
    width: `${size}px`,
    height: `${size}px`,
    zIndex: z_index,
    transform: `translate(-50%, -50%)`,
    ['--intensity' as string]: `${-intensityPx}px`,
    ['--intensity-x' as string]: `${intensityPx}px`,
    ['--intensity-deg' as string]: `${intensityDeg}deg`,
    ['--intensity-scale' as string]: intensityScale,
    ['--rot-range' as string]: `${intensityDeg}deg`,
  };

  return (
    <div
      className={`scene-element ${animClass} ${spdClass}`}
      style={style}
      data-element-id={id}
    >
      {image ? (
        <img
          src={image}
          alt={element.description || id}
          draggable={false}
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
        />
      ) : (
        <div style={{
          width: '100%', height: '100%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(255,255,255,0.1)', borderRadius: '12px',
          color: 'rgba(255,255,255,0.5)', fontSize: 12,
        }}>
          {id}
        </div>
      )}
    </div>
  );
};

export default SceneElement;
