/**
 * REST API client for PuppetStory backend.
 */

const BASE = '';  // Proxied via Vite

export interface StoryCatalogItem {
  id: string;
  title: string;
  synopsis: string;
  cover_prompt: string;
  age_range: [number, number];
  duration_minutes: number;
  character_count: number;
  beat_count: number;
}

export interface StoryCharacter {
  id: string;
  name: string;
  description: string;
  visual_prompt: string;
  scale_factor: number;
}

export interface StoryBackground {
  id: string;
  description: string;
  visual_prompt: string;
}

export interface StoryBeat {
  id: string;
  act: number;
  scene: string;
  characters_present: string[];
  narration_guide: string;
  initial_positions: Record<string, { x: number; y: number; scale?: number; rotation?: number }>;
  interaction_hint?: string;
}

export interface StoryData {
  id: string;
  title: string;
  synopsis: string;
  cover_prompt: string;
  age_range: [number, number];
  duration_minutes: number;
  essence: string;
  characters: StoryCharacter[];
  backgrounds: StoryBackground[];
  beats: StoryBeat[];
}

export interface AssetMap {
  story_id: string;
  assets: Record<string, string>;  // element_id -> data URI
  count: number;
}

export interface AssetGenEvent {
  event: 'start' | 'progress' | 'cached' | 'error' | 'complete';
  total?: number;
  done?: number;
  current?: string;
  type?: string;
  element?: string;
  message?: string;
  duration_s?: number;
}

export async function fetchStories(): Promise<StoryCatalogItem[]> {
  const res = await fetch(`${BASE}/api/stories`);
  if (!res.ok) throw new Error(`Failed to fetch stories: ${res.status}`);
  return res.json();
}

export async function fetchStory(storyId: string): Promise<StoryData> {
  const res = await fetch(`${BASE}/api/stories/${storyId}`);
  if (!res.ok) throw new Error(`Failed to fetch story: ${res.status}`);
  return res.json();
}

export async function fetchAssets(storyId: string): Promise<AssetMap> {
  const res = await fetch(`${BASE}/api/stories/${storyId}/assets`);
  if (!res.ok) throw new Error(`Failed to fetch assets: ${res.status}`);
  return res.json();
}

export async function generateAssets(
  storyId: string,
  onEvent: (event: AssetGenEvent) => void,
): Promise<void> {
  const res = await fetch(`${BASE}/api/stories/${storyId}/generate-assets`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to start asset generation: ${res.status}`);
  if (!res.body) throw new Error('No response body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6)) as AssetGenEvent;
          onEvent(event);
        } catch {
          // skip malformed events
        }
      }
    }
  }
}
