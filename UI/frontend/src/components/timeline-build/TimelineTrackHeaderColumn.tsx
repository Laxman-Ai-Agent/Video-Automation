import React from 'react';
import { Video, Volume2, Type, Sparkles, Layers } from 'lucide-react';
import styles from './TimelineTrackHeaderColumn.module.css';

interface TimelineTrackHeaderColumnProps {
  showVisualsTrack: boolean;
  showAudioTrack: boolean;
  showCaptionsTrack: boolean;
  showTypographyTrack: boolean;
  showMotionFxTrack: boolean;
}

export const TimelineTrackHeaderColumn: React.FC<TimelineTrackHeaderColumnProps> = ({
  showVisualsTrack,
  showAudioTrack,
  showCaptionsTrack,
  showTypographyTrack,
  showMotionFxTrack,
}) => {
  // One row per track, in the order the tracks are drawn in TimelineTrackCanvas; `height` tells which rows are taller there.
  const tracks = [
    { key: 'visuals', show: showVisualsTrack, Icon: Video, color: 'var(--accent-cyan)', label: 'Visual Scenes', height: styles.visuals },
    { key: 'audio', show: showAudioTrack, Icon: Volume2, color: '#60A5FA', label: 'Narration Waveform', height: styles.audio },
    { key: 'captions', show: showCaptionsTrack, Icon: Type, color: 'var(--status-completed)', label: 'Captions / Speech', height: '' },
    { key: 'typography', show: showTypographyTrack, Icon: Sparkles, color: '#F59E0B', label: 'Kinetic Text', height: '' },
    { key: 'motionfx', show: showMotionFxTrack, Icon: Layers, color: '#C084FC', label: 'Motion & FX', height: '' },
  ];

  return (
    <div className={styles.column}>
      <div className={styles.rulerLabel}>Timecode / Frame</div>

      {tracks.filter((t) => t.show).map(({ key, Icon, color, label, height }) => (
        <div key={key} className={`${styles.row} ${height}`.trim()} data-testid={`timeline-track-label-${key}`}>
          <Icon size={16} color={color} />
          <span className={styles.label}>{label}</span>
        </div>
      ))}
    </div>
  );
};
