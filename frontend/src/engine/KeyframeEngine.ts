/**
 * KeyframeEngine — interpolates between keyframes for smooth puppet animation.
 * Runs on PixiJS ticker (requestAnimationFrame loop).
 */

export interface Keyframe {
  t: number;      // time in seconds from sequence start
  x: number;      // 0-100 percentage
  y: number;      // 0-100 percentage
  rotation?: number;  // degrees
  scale?: number;     // multiplier
  opacity?: number;   // 0-1
}

export interface PuppetKeyframes {
  keyframes: Keyframe[];
  easing?: 'linear' | 'ease-in' | 'ease-out' | 'ease-in-out';
}

export interface ActionSequence {
  duration: number;
  puppets: Record<string, PuppetKeyframes>;
}

export interface InterpolatedState {
  x: number;
  y: number;
  rotation: number;
  scale: number;
  opacity: number;
}

// Easing functions
function easeLinear(t: number): number { return t; }
function easeIn(t: number): number { return t * t; }
function easeOut(t: number): number { return t * (2 - t); }
function easeInOut(t: number): number { return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; }

const EASING_MAP: Record<string, (t: number) => number> = {
  'linear': easeLinear,
  'ease-in': easeIn,
  'ease-out': easeOut,
  'ease-in-out': easeInOut,
};

/**
 * Interpolate between two keyframes at a given time.
 */
function lerpKeyframe(a: Keyframe, b: Keyframe, t: number, easingFn: (t: number) => number): InterpolatedState {
  const range = b.t - a.t;
  const rawProgress = range > 0 ? Math.max(0, Math.min(1, (t - a.t) / range)) : 1;
  const p = easingFn(rawProgress);

  return {
    x: a.x + (b.x - a.x) * p,
    y: a.y + (b.y - a.y) * p,
    rotation: (a.rotation ?? 0) + ((b.rotation ?? 0) - (a.rotation ?? 0)) * p,
    scale: (a.scale ?? 1) + ((b.scale ?? 1) - (a.scale ?? 1)) * p,
    opacity: (a.opacity ?? 1) + ((b.opacity ?? 1) - (a.opacity ?? 1)) * p,
  };
}

/**
 * Given a keyframe array and a time, return the interpolated state.
 */
export function interpolateAt(
  keyframes: Keyframe[],
  time: number,
  easing: string = 'ease-in-out'
): InterpolatedState {
  if (keyframes.length === 0) {
    return { x: 50, y: 50, rotation: 0, scale: 1, opacity: 1 };
  }
  if (keyframes.length === 1) {
    const kf = keyframes[0];
    return {
      x: kf.x,
      y: kf.y,
      rotation: kf.rotation ?? 0,
      scale: kf.scale ?? 1,
      opacity: kf.opacity ?? 1,
    };
  }

  const easingFn = EASING_MAP[easing] || easeInOut;

  // Before first keyframe
  if (time <= keyframes[0].t) {
    const kf = keyframes[0];
    return {
      x: kf.x, y: kf.y,
      rotation: kf.rotation ?? 0,
      scale: kf.scale ?? 1,
      opacity: kf.opacity ?? 1,
    };
  }

  // After last keyframe
  if (time >= keyframes[keyframes.length - 1].t) {
    const kf = keyframes[keyframes.length - 1];
    return {
      x: kf.x, y: kf.y,
      rotation: kf.rotation ?? 0,
      scale: kf.scale ?? 1,
      opacity: kf.opacity ?? 1,
    };
  }

  // Find the two surrounding keyframes
  for (let i = 0; i < keyframes.length - 1; i++) {
    if (time >= keyframes[i].t && time <= keyframes[i + 1].t) {
      return lerpKeyframe(keyframes[i], keyframes[i + 1], time, easingFn);
    }
  }

  // Fallback
  const last = keyframes[keyframes.length - 1];
  return {
    x: last.x, y: last.y,
    rotation: last.rotation ?? 0,
    scale: last.scale ?? 1,
    opacity: last.opacity ?? 1,
  };
}


/**
 * ActiveSequence tracks a running action_sequence with its start time.
 */
export class ActiveSequence {
  public readonly sequence: ActionSequence;
  public readonly startTime: number;

  constructor(sequence: ActionSequence, startTime: number) {
    this.sequence = sequence;
    this.startTime = startTime;
  }

  get duration(): number {
    return this.sequence.duration;
  }

  isComplete(currentTime: number): boolean {
    return (currentTime - this.startTime) >= this.duration;
  }

  getElapsed(currentTime: number): number {
    return currentTime - this.startTime;
  }

  /**
   * Get the interpolated state of a puppet at the current time.
   * Returns null if this sequence doesn't contain the puppet.
   */
  getPuppetState(puppetId: string, currentTime: number): InterpolatedState | null {
    const puppetData = this.sequence.puppets[puppetId];
    if (!puppetData) return null;

    const elapsed = this.getElapsed(currentTime);
    return interpolateAt(puppetData.keyframes, elapsed, puppetData.easing);
  }
}
