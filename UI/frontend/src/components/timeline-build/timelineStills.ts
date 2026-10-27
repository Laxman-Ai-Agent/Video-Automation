// The preview stills of the current composition (the frames Motion Validation drew) as the Timeline page uses them: which ones belong to a scene and which one shows a given frame.
export interface Still { scene_id: string; kind: string; frame: number; time_s: number | null; url: string }
export interface StillsResponse { current: boolean; exists: boolean; samples: Still[] }

const sceneNumber = (id: string): number => parseInt(id.replace(/\D/g, ''), 10);   // "scene_01" (stills) and "scene_001" (timeline) are the same scene

export function stillsOfScene(samples: Still[], sceneId: string): Still[] {
  const n = sceneNumber(sceneId);
  return samples.filter(s => sceneNumber(s.scene_id) === n).sort((a, b) => a.frame - b.frame);
}

// The frames of a scene that show the scene itself; the transition still is a blend with the next scene.
export const sceneFilmstrip = (samples: Still[], sceneId: string): Still[] => stillsOfScene(samples, sceneId).filter(s => s.kind !== 'transition');

// The still nearest to `frame` inside the scene that is playing (never a frame of the neighbouring scene); null when the scene has none.
export function stillAt(samples: Still[], sceneId: string, frame: number): Still | null {
  const own = stillsOfScene(samples, sceneId);
  if (!own.length) return null;
  return own.reduce((best, s) => (Math.abs(s.frame - frame) < Math.abs(best.frame - frame) ? s : best));
}

// The thumbnail sheet of the rendered video: one small frame per `interval_s` seconds, `cols` per row, read left to right and top to bottom.
export interface Thumbs { available: boolean; url?: string; interval_s?: number; cols?: number; rows?: number; count?: number; tile_w?: number; tile_h?: number }

// CSS that shows the sheet's picture for `frame` (the picture at or before it) inside any box of the video's shape; null when there is no sheet.
export function thumbStyle(t: Thumbs | null, frame: number, fps: number): { backgroundImage: string; backgroundSize: string; backgroundPosition: string } | null {
  if (!t || !t.available || !t.url || !t.cols || !t.rows || !t.count || !t.interval_s) return null;
  const i = Math.min(t.count - 1, Math.max(0, Math.floor(frame / fps / t.interval_s)));
  const col = i % t.cols, row = Math.floor(i / t.cols);
  return {
    backgroundImage: `url(${t.url})`,
    backgroundSize: `${t.cols * 100}% ${t.rows * 100}%`,
    backgroundPosition: `${t.cols > 1 ? (col / (t.cols - 1)) * 100 : 0}% ${t.rows > 1 ? (row / (t.rows - 1)) * 100 : 0}%`,
  };
}
