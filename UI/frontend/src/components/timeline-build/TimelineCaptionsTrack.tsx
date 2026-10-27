import React from 'react';
import styles from './TimelineCaptionsTrack.module.css';
import type { CaptionBlock } from './timelineCaptions';

export interface TimelineCaptionsTrackProps {
  blocks: CaptionBlock[];
  frameToPx: (frame: number) => number;
  fps: number;
  formatSeconds: (s: number) => string;
}

// The spoken text of the final transcript, one block per segment, at the frames it is spoken (nothing is drawn for noise or a pause).
export const TimelineCaptionsTrack: React.FC<TimelineCaptionsTrackProps> = ({ blocks, frameToPx, fps, formatSeconds }) => (
  <>
    {blocks.map(b => (
      <div
        key={b.id}
        className={styles.block}
        style={{ left: `${frameToPx(b.startFrame)}px`, width: `${Math.max(16, frameToPx(b.endFrame - b.startFrame))}px` }}
        title={`Speech ${formatSeconds((b.endFrame - b.startFrame) / fps)}: ${b.text}`}
        data-testid={`timeline-caption-${b.id}`}
      >
        <span className={styles.text}>{b.text}</span>
      </div>
    ))}
    {blocks.length === 0 && <div className={styles.empty}>No transcript loaded.</div>}
  </>
);
