// What the Timeline page draws from the final transcript and from the timeline's transitions (pure functions: tests/frontend/timeline_captions.test.mjs).
export interface TranscriptSegment { id: number; start: number; end: number; text: string }
export interface Transition { transition_id: string; from_scene: string; to_scene: string; start_frame: number; end_frame: number; boundary_frame: number; type: string; supported?: boolean }

export interface CaptionBlock { id: number; startFrame: number; endFrame: number; text: string }

// One caption per spoken segment of the final transcript; a segment without words (noise, a pause) makes none.
export function captionBlocks(segments: TranscriptSegment[], fps: number): CaptionBlock[] {
  return segments
    .filter(s => (s.text || '').trim().length > 0 && s.end > s.start)
    .map(s => ({ id: s.id, startFrame: Math.round(s.start * fps), endFrame: Math.round(s.end * fps), text: s.text.trim() }));
}

// The words spoken while a scene is on screen: the segments whose middle lies inside the scene's frames, in order.
export function sceneNarration(segments: TranscriptSegment[], startFrame: number, endFrame: number, fps: number): string {
  return segments
    .filter(s => (s.text || '').trim() && ((s.start + s.end) / 2) * fps >= startFrame && ((s.start + s.end) / 2) * fps < endFrame)
    .map(s => s.text.trim())
    .join(' ');
}

// The transitions that touch a scene: the one into it and the one out of it.
export function sceneTransitions(transitions: Transition[], sceneId: string): { into: Transition | null; out: Transition | null } {
  return { into: transitions.find(t => t.to_scene === sceneId) ?? null, out: transitions.find(t => t.from_scene === sceneId) ?? null };
}
