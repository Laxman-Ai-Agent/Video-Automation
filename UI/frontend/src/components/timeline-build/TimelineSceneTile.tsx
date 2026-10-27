import React from 'react';
import styles from './TimelineSceneTile.module.css';
import { sceneFilmstrip, type Still } from './timelineStills';

export interface TimelineSceneTileProps {
  scene: { scene_id: string; start_frame: number; end_frame: number; duration_frames: number; pattern?: string };
  stills: Still[];
  fps: number;
  leftPx: number;
  widthPx: number;
  selected: boolean;
  current: boolean;
  onSelect: () => void;
  formatSeconds: (s: number) => string;
}

// One scene on the Visuals track: the real frames of the scene (entry, middle, before the exit) side by side behind the name and the length.
export const TimelineSceneTile: React.FC<TimelineSceneTileProps> = ({ scene, stills, fps, leftPx, widthPx, selected, current, onSelect, formatSeconds }) => {
  const frames = sceneFilmstrip(stills, scene.scene_id);
  const cls = [styles.tile, selected ? styles.selected : current ? styles.current : ''].join(' ');
  return (
    <div
      className={cls}
      style={{ left: `${leftPx}px`, width: `${Math.max(12, widthPx)}px` }}
      onClick={(e) => { e.stopPropagation(); onSelect(); }}
      title={`Scene ${scene.scene_id}: F${scene.start_frame} - F${scene.end_frame} (${formatSeconds(scene.duration_frames / fps)})`}
      data-testid={`timeline-scene-tile-${scene.scene_id}`}
    >
      {frames.length > 0 && (
        <div className={styles.filmstrip}>
          {frames.map(f => <img key={f.url} className={styles.frame} src={f.url} alt="" draggable={false} />)}
        </div>
      )}
      <div className={styles.label}>
        <div className={styles.row}>
          <span className={styles.name}>{scene.scene_id}</span>
          <span className={styles.frames}>{scene.duration_frames}f</span>
        </div>
        <div className={styles.meta}>{scene.pattern || 'custom_motion'} • {formatSeconds(scene.duration_frames / fps)}</div>
      </div>
    </div>
  );
};
