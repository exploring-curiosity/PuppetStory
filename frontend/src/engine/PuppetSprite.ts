/**
 * PuppetSprite — wraps a PixiJS Sprite for a single puppet character.
 * Manages loading the texture, positioning, and applying interpolated state.
 */

import { Sprite, Texture, Assets } from 'pixi.js';
import type { InterpolatedState } from './KeyframeEngine';

const BASE_PUPPET_SIZE = 280; // px at scale=1.0

export class PuppetSprite {
  public readonly id: string;
  public sprite: Sprite;
  private _loaded = false;

  // Current state (for smooth fallback when no sequence is active)
  public currentState: InterpolatedState = {
    x: 50,
    y: 65,
    rotation: 0,
    scale: 1,
    opacity: 1,
  };

  constructor(id: string) {
    this.id = id;
    this.sprite = new Sprite();
    this.sprite.anchor.set(0.5, 0.5);
    this.sprite.visible = false;
  }

  async loadTexture(dataUri: string): Promise<void> {
    try {
      const texture = await Assets.load(dataUri);
      this.sprite.texture = texture;
      this._loaded = true;
      this.sprite.visible = true;
    } catch (e) {
      console.warn(`[PuppetSprite] Failed to load texture for ${this.id}:`, e);
      // Try as an image element fallback
      try {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        await new Promise<void>((resolve, reject) => {
          img.onload = () => resolve();
          img.onerror = reject;
          img.src = dataUri;
        });
        const texture = Texture.from(img);
        this.sprite.texture = texture;
        this._loaded = true;
        this.sprite.visible = true;
      } catch (e2) {
        console.error(`[PuppetSprite] Fallback also failed for ${this.id}:`, e2);
      }
    }
  }

  get loaded(): boolean {
    return this._loaded;
  }

  /**
   * Apply an interpolated state to the sprite, converting from
   * percentage coordinates to pixel coordinates.
   */
  applyState(state: InterpolatedState, stageWidth: number, stageHeight: number): void {
    this.currentState = state;

    // Convert percentage to pixels
    this.sprite.x = (state.x / 100) * stageWidth;
    this.sprite.y = (state.y / 100) * stageHeight;

    // Rotation (degrees to radians)
    this.sprite.rotation = (state.rotation * Math.PI) / 180;

    // Scale — puppet size relative to stage
    const baseSize = BASE_PUPPET_SIZE * state.scale;
    if (this.sprite.texture && this.sprite.texture.width > 0) {
      const texW = this.sprite.texture.width;
      const texH = this.sprite.texture.height;
      const aspect = texW / texH;
      if (aspect >= 1) {
        this.sprite.width = baseSize;
        this.sprite.height = baseSize / aspect;
      } else {
        this.sprite.height = baseSize;
        this.sprite.width = baseSize * aspect;
      }
    } else {
      this.sprite.width = baseSize;
      this.sprite.height = baseSize;
    }

    // Opacity
    this.sprite.alpha = state.opacity;
    this.sprite.visible = state.opacity > 0.01;
  }

  /**
   * Smoothly transition to a new state over a number of frames.
   * Used when set_scene provides initial positions.
   */
  setPosition(x: number, y: number, scale: number = 1, rotation: number = 0, opacity: number = 1): void {
    this.currentState = { x, y, scale, rotation, opacity };
  }

  destroy(): void {
    this.sprite.destroy({ children: true });
  }
}
