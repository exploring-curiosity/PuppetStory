/**
 * SceneManager — orchestrates the PixiJS stage, background transitions,
 * puppet lifecycle, and action sequence playback.
 */

import { Application, Sprite, Texture, Assets, Container } from 'pixi.js';
import { PuppetSprite } from './PuppetSprite';
import { ActiveSequence, type ActionSequence, type InterpolatedState } from './KeyframeEngine';

export interface SetSceneData {
  background_id: string;
  background_image: string;
  mood: string;
  transition: string;
  puppets: Array<{
    character_id: string;
    image?: string;
    x: number;
    y: number;
    scale?: number;
    rotation?: number;
    opacity?: number;
  }>;
}

export class SceneManager {
  private app: Application;
  private bgContainer: Container;
  private puppetContainer: Container;
  private puppets: Map<string, PuppetSprite> = new Map();
  private activeSequences: ActiveSequence[] = [];
  private _running = false;

  constructor(app: Application) {
    this.app = app;

    // Background layer
    this.bgContainer = new Container();
    this.app.stage.addChild(this.bgContainer);

    // Puppet layer (on top of background)
    this.puppetContainer = new Container();
    this.app.stage.addChild(this.puppetContainer);
  }

  /**
   * Start the animation ticker.
   */
  start(): void {
    if (this._running) return;
    this._running = true;
    this.app.ticker.add(this._tick, this);
  }

  /**
   * Stop the animation ticker.
   */
  stop(): void {
    this._running = false;
    this.app.ticker.remove(this._tick, this);
  }

  /**
   * Set a new scene — swap background and position puppets.
   */
  async setScene(data: SetSceneData): Promise<void> {
    const { background_image, puppets, transition } = data;
    const w = this.app.screen.width;
    const h = this.app.screen.height;

    // Swap background
    if (background_image) {
      await this._setBackground(background_image, transition);
    }

    // Track which puppets should be visible
    const activePuppetIds = new Set(puppets.map(p => p.character_id));

    // Hide puppets not in this scene
    for (const [id, puppet] of this.puppets) {
      if (!activePuppetIds.has(id)) {
        puppet.sprite.visible = false;
      }
    }

    // Position and show scene puppets
    for (const p of puppets) {
      let puppet = this.puppets.get(p.character_id);

      if (!puppet) {
        puppet = new PuppetSprite(p.character_id);
        this.puppets.set(p.character_id, puppet);
        this.puppetContainer.addChild(puppet.sprite);
      }

      // Load texture if image provided and not already loaded
      if (p.image && !puppet.loaded) {
        await puppet.loadTexture(p.image);
      }

      // Set initial position
      const state: InterpolatedState = {
        x: p.x,
        y: p.y,
        scale: p.scale ?? 1,
        rotation: p.rotation ?? 0,
        opacity: p.opacity ?? 1,
      };
      puppet.setPosition(state.x, state.y, state.scale, state.rotation, state.opacity);
      puppet.applyState(state, w, h);
      puppet.sprite.visible = true;
    }
  }

  /**
   * Play an action sequence — animate puppets with keyframes.
   */
  playActionSequence(data: ActionSequence): void {
    const now = performance.now() / 1000;
    const sequence = new ActiveSequence(data, now);
    this.activeSequences.push(sequence);
  }

  /**
   * Preload a puppet texture for later use.
   */
  async preloadPuppet(characterId: string, dataUri: string): Promise<void> {
    let puppet = this.puppets.get(characterId);
    if (!puppet) {
      puppet = new PuppetSprite(characterId);
      this.puppets.set(characterId, puppet);
      this.puppetContainer.addChild(puppet.sprite);
      puppet.sprite.visible = false;
    }
    if (!puppet.loaded) {
      await puppet.loadTexture(dataUri);
    }
  }

  /**
   * Animation tick — called every frame by PixiJS ticker.
   */
  private _tick = (): void => {
    const now = performance.now() / 1000;
    const w = this.app.screen.width;
    const h = this.app.screen.height;

    // Process active sequences — latest sequence wins per puppet
    const puppetStates: Map<string, InterpolatedState> = new Map();

    // Remove completed sequences, but keep latest state
    this.activeSequences = this.activeSequences.filter(seq => {
      const complete = seq.isComplete(now);

      // Get state for each puppet in this sequence
      for (const puppetId of Object.keys(seq.sequence.puppets)) {
        const state = seq.getPuppetState(puppetId, now);
        if (state) {
          puppetStates.set(puppetId, state); // Latest sequence overwrites
        }
      }

      // Keep sequence if not complete
      return !complete;
    });

    // Apply states to puppets
    for (const [puppetId, state] of puppetStates) {
      const puppet = this.puppets.get(puppetId);
      if (puppet && puppet.loaded) {
        puppet.applyState(state, w, h);
      }
    }

    // For puppets NOT in any active sequence, apply their last known state
    for (const [id, puppet] of this.puppets) {
      if (!puppetStates.has(id) && puppet.loaded && puppet.sprite.visible) {
        puppet.applyState(puppet.currentState, w, h);
      }
    }
  };

  /**
   * Set the background image with optional transition.
   */
  private async _setBackground(dataUri: string, transition: string = 'crossfade'): Promise<void> {
    try {
      let texture: Texture;
      try {
        texture = await Assets.load(dataUri);
      } catch {
        // Fallback: load via Image element
        const img = new Image();
        img.crossOrigin = 'anonymous';
        await new Promise<void>((resolve, reject) => {
          img.onload = () => resolve();
          img.onerror = reject;
          img.src = dataUri;
        });
        texture = Texture.from(img);
      }

      const newBg = new Sprite(texture);
      newBg.width = this.app.screen.width;
      newBg.height = this.app.screen.height;

      if (transition === 'crossfade' && this.bgContainer.children.length > 0) {
        // Crossfade: add new bg on top, fade in, then remove old
        newBg.alpha = 0;
        this.bgContainer.addChild(newBg);

        // Simple fade-in over 30 frames (~0.5s at 60fps)
        let frame = 0;
        const fadeIn = () => {
          frame++;
          newBg.alpha = Math.min(1, frame / 30);
          if (frame >= 30) {
            this.app.ticker.remove(fadeIn);
            // Remove old backgrounds
            while (this.bgContainer.children.length > 1) {
              const old = this.bgContainer.children[0];
              this.bgContainer.removeChild(old);
              old.destroy();
            }
          }
        };
        this.app.ticker.add(fadeIn);
      } else {
        // Cut: replace immediately
        while (this.bgContainer.children.length > 0) {
          const old = this.bgContainer.children[0];
          this.bgContainer.removeChild(old);
          old.destroy();
        }
        this.bgContainer.addChild(newBg);
      }
    } catch (e) {
      console.error('[SceneManager] Failed to load background:', e);
    }
  }

  /**
   * Handle window resize — update background and puppet positions.
   */
  resize(width: number, height: number): void {
    // Resize backgrounds
    for (const child of this.bgContainer.children) {
      if (child instanceof Sprite) {
        child.width = width;
        child.height = height;
      }
    }
    // Re-apply puppet positions
    for (const [, puppet] of this.puppets) {
      if (puppet.loaded && puppet.sprite.visible) {
        puppet.applyState(puppet.currentState, width, height);
      }
    }
  }

  /**
   * Clean up everything.
   */
  destroy(): void {
    this.stop();
    this.activeSequences = [];
    for (const [, puppet] of this.puppets) {
      puppet.destroy();
    }
    this.puppets.clear();
    this.bgContainer.destroy({ children: true });
    this.puppetContainer.destroy({ children: true });
  }
}
