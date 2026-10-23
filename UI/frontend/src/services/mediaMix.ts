// The media mix of a project: how much of the video is motion graphics, real photographs and real video clips (a share of the time, the three add up to 100).
// It is chosen once, when the audio is uploaded; the server keeps it and nothing changes it afterwards (SYSTEM/core/media_kinds.py is the source of truth).
export type MediaFamily = 'motion' | 'image' | 'video';

export interface MediaMix {
  motion: number;
  image: number;
  video: number;
  ai_images: boolean;
}

export const FAMILIES: MediaFamily[] = ['motion', 'image', 'video'];
export const DEFAULT_MEDIA: MediaMix = { motion: 60, image: 30, video: 10, ai_images: false };
export const FAMILY_LABEL: Record<MediaFamily, string> = { motion: 'Motion graphics', image: 'Images', video: 'Videos' };

export const total = (m: MediaMix): number => m.motion + m.image + m.video;

/** Set one share; the other two move in proportion to what they had (equally when both were 0) so that the three still add up to 100. */
export function rebalance(mix: MediaMix, family: MediaFamily, value: number): MediaMix {
  const v = Math.max(0, Math.min(100, Math.round(Number.isFinite(value) ? value : 0)));
  const [a, b] = FAMILIES.filter((f) => f !== family);
  const rest = 100 - v;
  const have = mix[a] + mix[b];
  const next: MediaMix = { ...mix, [family]: v };
  next[a] = have === 0 ? Math.ceil(rest / 2) : Math.round((rest * mix[a]) / have);
  next[b] = rest - next[a];
  return next;
}
