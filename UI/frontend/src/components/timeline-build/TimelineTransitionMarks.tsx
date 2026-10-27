import React from 'react';
import styles from './TimelineTransitionMarks.module.css';
import type { Transition } from './timelineCaptions';

export interface TimelineTransitionMarksProps {
  transitions: Transition[];
  frameToPx: (frame: number) => number;
  fps: number;
}

// The transition windows between scenes, drawn along the bottom edge of the Visuals track (they never intercept a click).
export const TimelineTransitionMarks: React.FC<TimelineTransitionMarksProps> = ({ transitions, frameToPx, fps }) => (
  <>
    {transitions.map(t => (
      <div
        key={t.transition_id}
        className={`${styles.mark} ${t.supported === false ? styles.unsupported : ''}`}
        style={{ left: `${frameToPx(t.start_frame)}px`, width: `${Math.max(6, frameToPx(t.end_frame - t.start_frame))}px` }}
        title={`${t.type} • ${t.from_scene} → ${t.to_scene} • ${t.end_frame - t.start_frame} frames (${((t.end_frame - t.start_frame) / fps).toFixed(2)}s)${t.supported === false ? ' • not supported' : ''}`}
        data-testid={`timeline-transition-${t.transition_id}`}
      />
    ))}
  </>
);
