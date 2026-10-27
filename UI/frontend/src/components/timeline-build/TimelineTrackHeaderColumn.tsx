import React from 'react';
import { Video, Volume2, Type, Sparkles, Layers } from 'lucide-react';

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
  return (
    <div style={{
      width: '180px',
      flexShrink: 0,
      backgroundColor: '#090D1A',
      borderRight: '1px solid var(--border-subtle)',
      zIndex: 10,
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Ruler label placeholder */}
      <div style={{ height: '36px', borderBottom: '1px solid var(--border-subtle)', padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
        Timecode / Frame
      </div>

      {/* Track Labels */}
      {showVisualsTrack && (
        <div style={{ height: '84px', borderBottom: '1px solid var(--border-subtle)', padding: '10px 12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Video size={16} color="var(--accent-cyan)" />
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>Visual Scenes</span>
        </div>
      )}

      {showAudioTrack && (
        <div style={{ height: '56px', borderBottom: '1px solid var(--border-subtle)', padding: '10px 12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Volume2 size={16} color="#60A5FA" />
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>Narration Waveform</span>
        </div>
      )}

      {showCaptionsTrack && (
        <div style={{ height: '52px', borderBottom: '1px solid var(--border-subtle)', padding: '10px 12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Type size={16} color="var(--status-completed)" />
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>Captions / Speech</span>
        </div>
      )}

      {showTypographyTrack && (
        <div style={{ height: '52px', borderBottom: '1px solid var(--border-subtle)', padding: '10px 12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={16} color="#F59E0B" />
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>Kinetic Text</span>
        </div>
      )}

      {showMotionFxTrack && (
        <div style={{ height: '52px', borderBottom: '1px solid var(--border-subtle)', padding: '10px 12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={16} color="#C084FC" />
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>Motion & FX</span>
        </div>
      )}
    </div>
  );
};
