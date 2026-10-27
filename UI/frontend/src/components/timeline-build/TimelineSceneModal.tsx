import React, { useEffect } from 'react';
import { X, ChevronLeft, ChevronRight } from 'lucide-react';
import styles from './TimelineSceneModal.module.css';
import { sceneFilmstrip, thumbStyle, type Still, type Thumbs } from './timelineStills';
import { sceneNarration, sceneTransitions, type TranscriptSegment, type Transition } from './timelineCaptions';
import type { TimelineSceneItem } from './useTimelineData';

const CELLS = 4;   // frames cut from the rendered video's sheet when there are no preview stills

export interface TimelineSceneModalProps {
  scene: TimelineSceneItem;
  idx: number;
  total: number;
  fps: number;
  stills: Still[];
  thumbs: Thumbs | null;
  segments: TranscriptSegment[];
  transitions: Transition[];
  formatSeconds: (s: number) => string;
  onClose: () => void;
  onStep: (delta: number) => void;
}

const transitionText = (t: Transition | null) =>
  t ? `${t.type} • ${t.from_scene} → ${t.to_scene} • F${t.start_frame}-F${t.end_frame} (${t.end_frame - t.start_frame}f)` : 'none (first / last scene)';

/** One timeline scene in full: its real frames, the words spoken during it, the transitions into and out of it, and its layers. Opened by a double click on its tile. */
export const TimelineSceneModal: React.FC<TimelineSceneModalProps> = ({ scene, idx, total, fps, stills, thumbs, segments, transitions, formatSeconds, onClose, onStep }) => {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' && e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.stopImmediatePropagation();                                   // the popup owns these keys while it is open
      if (e.key === 'Escape') onClose();
      else onStep(e.key === 'ArrowLeft' ? -1 : 1);
    };
    window.addEventListener('keydown', onKey, true);                 // capture: runs before any listener of the page behind it
    return () => window.removeEventListener('keydown', onKey, true);
  }, [onClose, onStep]);

  const frames = sceneFilmstrip(stills, scene.scene_id);
  const sheet = thumbs?.available ? Array.from({ length: CELLS }, (_, i) => thumbStyle(thumbs, scene.start_frame + ((i + 0.5) / CELLS) * scene.duration_frames, fps)) : [];
  const narration = sceneNarration(segments, scene.start_frame, scene.end_frame, fps);
  const { into, out } = sceneTransitions(transitions, scene.scene_id);
  const layers = scene.layers ?? [];

  return (
    <div className={styles.overlay} data-testid="timeline-scene-modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={styles.modal} role="dialog" aria-label={`Timeline scene ${scene.scene_id}`} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.headLeft}>
            <span className={styles.badge}>{scene.scene_id.toUpperCase()}</span>
            <div>
              <h3 className={styles.title}>{scene.pattern || 'custom_motion'}</h3>
              <div className={styles.subtitle}>F{scene.start_frame} → F{scene.end_frame} • {scene.duration_frames} frames • {formatSeconds(scene.duration_frames / fps)}</div>
            </div>
          </div>
          <div className={styles.headRight}>
            <button className={styles.iconBtn} disabled={idx === 0} onClick={() => onStep(-1)} title="Previous scene (←)" data-testid="timeline-scene-modal-prev"><ChevronLeft size={16} /></button>
            <span className={styles.subtitle}>{idx + 1} / {total}</span>
            <button className={styles.iconBtn} disabled={idx >= total - 1} onClick={() => onStep(1)} title="Next scene (→)" data-testid="timeline-scene-modal-next"><ChevronRight size={16} /></button>
            <button className={styles.iconBtn} onClick={onClose} title="Close (Esc)" data-testid="timeline-scene-modal-close"><X size={16} /></button>
          </div>
        </div>
        <div className={styles.body}>
          <div className={styles.strip}>
            {sheet.length > 0
              ? sheet.map((s, i) => <div key={i} className={styles.still} style={s ?? undefined} />)
              : frames.map(f => <img key={f.url} className={styles.still} src={f.url} alt="" draggable={false} />)}
            {sheet.length === 0 && frames.length === 0 && <div className={styles.noFrames}>No real frames for this scene yet (Motion Validation stills or the render are missing).</div>}
          </div>
          <div>
            <div className={styles.sectionTitle}>Narration</div>
            <p className={styles.narration} data-testid="timeline-scene-modal-narration">{narration || 'No words are spoken in this scene.'}</p>
          </div>
          <div>
            <div className={styles.sectionTitle}>Transitions</div>
            <div className={styles.rows}>
              <div className={styles.row}><span className={styles.rowName}>In</span><span className={`${styles.mono} ${into?.supported === false ? styles.warn : ''}`}>{transitionText(into)}</span></div>
              <div className={styles.row}><span className={styles.rowName}>Out</span><span className={`${styles.mono} ${out?.supported === false ? styles.warn : ''}`}>{transitionText(out)}</span></div>
            </div>
          </div>
          <div>
            <div className={styles.sectionTitle}>Layers ({layers.length})</div>
            <div className={styles.rows}>
              {layers.map((l: any, i: number) => (
                <div key={l.layer_id || i} className={styles.row}>
                  <span><span className={styles.rowName}>{l.layer_id || `L${i + 1}`}</span> • <span className={styles.cyan}>{l.type}</span> • z {l.z ?? 10}</span>
                  <span className={styles.mono}>F{l.start_frame} → F{l.end_frame}</span>
                </div>
              ))}
              {layers.length === 0 && <div className={styles.noFrames}>No layers recorded.</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
