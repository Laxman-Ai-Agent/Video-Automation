// The media settings of a project: every video is 100% motion graphics with real photographs and clips drawn inside it in any amount, so the only choice is whether AI-made pictures are wanted.
// It is chosen once, when the audio is uploaded; the server keeps it and nothing changes it afterwards (SYSTEM/core/media_kinds.py is the source of truth).
export type MediaFamily = 'motion' | 'image' | 'video';

export interface MediaMix {
  ai_images: boolean;
  motion_kit: boolean;   // the optional motion kit (SYSTEM/memory/store.py motion_kit); the server keeps it as its own project key, not inside `media`
  captions: boolean;     // word-timed captions over the scenes (SYSTEM/memory/store.py captions); own project key, on by default
}

export const FAMILIES: MediaFamily[] = ['motion', 'image', 'video'];
export const DEFAULT_MEDIA: MediaMix = { ai_images: false, motion_kit: false, captions: true };
export const FAMILY_LABEL: Record<MediaFamily, string> = { motion: 'Motion graphics', image: 'Images', video: 'Videos' };
