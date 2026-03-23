/**
 * PuppetCanvas — React wrapper around PixiJS Application + SceneManager.
 * Handles mount/unmount, resize, and exposes the SceneManager via ref.
 */

import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import { Application } from 'pixi.js';
import { SceneManager, type SetSceneData } from '../engine/SceneManager';
import type { ActionSequence } from '../engine/KeyframeEngine';

export interface PuppetCanvasHandle {
  setScene: (data: SetSceneData) => Promise<void>;
  playActionSequence: (data: ActionSequence) => void;
  preloadPuppet: (characterId: string, dataUri: string) => Promise<void>;
}

const PuppetCanvas = forwardRef<PuppetCanvasHandle>((_props, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const managerRef = useRef<SceneManager | null>(null);

  useImperativeHandle(ref, () => ({
    setScene: async (data: SetSceneData) => {
      if (managerRef.current) {
        await managerRef.current.setScene(data);
      }
    },
    playActionSequence: (data: ActionSequence) => {
      if (managerRef.current) {
        managerRef.current.playActionSequence(data);
      }
    },
    preloadPuppet: async (characterId: string, dataUri: string) => {
      if (managerRef.current) {
        await managerRef.current.preloadPuppet(characterId, dataUri);
      }
    },
  }));

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let destroyed = false;

    (async () => {
      const app = new Application();
      await app.init({
        background: '#0a0a1a',
        resizeTo: container,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
      });

      if (destroyed) {
        app.destroy(true);
        return;
      }

      container.appendChild(app.canvas as HTMLCanvasElement);
      appRef.current = app;

      const manager = new SceneManager(app);
      managerRef.current = manager;
      manager.start();

      // Handle resize
      const onResize = () => {
        app.renderer.resize(container.clientWidth, container.clientHeight);
        manager.resize(container.clientWidth, container.clientHeight);
      };
      window.addEventListener('resize', onResize);

      // Cleanup on unmount
      return () => {
        window.removeEventListener('resize', onResize);
      };
    })();

    return () => {
      destroyed = true;
      if (managerRef.current) {
        managerRef.current.destroy();
        managerRef.current = null;
      }
      if (appRef.current) {
        appRef.current.destroy(true);
        appRef.current = null;
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0"
      style={{ zIndex: 0 }}
    />
  );
});

PuppetCanvas.displayName = 'PuppetCanvas';

export default PuppetCanvas;
