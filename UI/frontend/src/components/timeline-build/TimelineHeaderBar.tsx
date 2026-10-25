import React from 'react';
import { Film, RotateCcw, ZoomIn, ZoomOut, AlertTriangle } from 'lucide-react';

export interface TimelineHeaderBarProps {
  timelineBuildReport: any;
  aspect: string;
  fps: number;
  totalDurationSeconds: number;
  totalFrames: number;
  scenesCount: number;
  onRetryTimeline?: () => void;
  isPipelineRunning: boolean;
  zoomLevel: number;
  setZoomLevel: React.Dispatch<React.SetStateAction<number>>;
  timelineConflicts: { type: 'gap' | 'overlap'; startFrame: number; endFrame: number; message: string }[];
  formatSeconds: (sec: number) => string;
}

export const TimelineHeaderBar: React.FC<TimelineHeaderBarProps> = ({
  timelineBuildReport,
  aspect,
  fps,
  totalDurationSeconds,
  totalFrames,
  scenesCount,
  onRetryTimeline,
  isPipelineRunning,
  zoomLevel,
  setZoomLevel,
  timelineConflicts,
  formatSeconds
}) => {
  return (
    <>
      {/* TOP CONTROL HEADER */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '16px',
        borderBottom: '1px solid var(--border-subtle)',
        paddingBottom: '20px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '8px',
            backgroundColor: 'rgba(34, 211, 238, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent-cyan)',
            border: '1px solid rgba(34, 211, 238, 0.3)'
          }}>
            <Film size={22} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ fontSize: '19px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Frame-Accurate Visual Timeline
              </h2>
              <span style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '3px 9px',
                borderRadius: '4px',
                backgroundColor: timelineBuildReport?.status === 'completed' 
                  ? 'rgba(16, 185, 129, 0.15)' 
                  : (timelineBuildReport?.status === 'completed_with_warnings' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(34, 211, 238, 0.15)'),
                color: timelineBuildReport?.status === 'completed' 
                  ? 'var(--status-completed)' 
                  : (timelineBuildReport?.status === 'completed_with_warnings' ? '#F59E0B' : 'var(--accent-cyan)'),
                border: '1px solid currentColor',
                textTransform: 'uppercase'
              }}>
                {timelineBuildReport?.status || 'Active Timeline'}
              </span>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', gap: '14px' }}>
              <span>Aspect: <strong style={{ color: 'var(--text-primary)' }}>{aspect}</strong></span>
              <span>Rate: <strong style={{ color: 'var(--text-primary)' }}>{fps} FPS</strong></span>
              <span>Total Duration: <strong style={{ color: 'var(--accent-cyan)' }}>{formatSeconds(totalDurationSeconds)}</strong> ({totalFrames} frames)</span>
              <span>Scenes: <strong style={{ color: 'var(--text-primary)' }}>{scenesCount}</strong></span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {onRetryTimeline && (
            <button
              onClick={onRetryTimeline}
              disabled={isPipelineRunning}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-card)',
                borderRadius: '6px',
                color: 'var(--text-primary)',
                fontSize: '13px',
                fontWeight: 600,
                cursor: isPipelineRunning ? 'not-allowed' : 'pointer',
                opacity: isPipelineRunning ? 0.6 : 1,
                transition: 'all 0.15s ease'
              }}
              title="Re-run Timeline Build stage from composition"
            >
              <RotateCcw size={14} />
              Re-Build Timeline
            </button>
          )}

          <div style={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '6px',
            padding: '3px 8px',
            gap: '8px'
          }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Zoom:</span>
            <button
              onClick={() => setZoomLevel(z => Math.max(0.75, z - 0.5))}
              style={{ background: 'none', border: 'none', color: 'var(--text-primary)', cursor: 'pointer', padding: '4px' }}
              title="Zoom Out (-)"
            >
              <ZoomOut size={15} />
            </button>
            <span style={{ fontSize: '12px', fontWeight: 700, minWidth: '32px', textAlign: 'center' }}>
              {zoomLevel}x
            </span>
            <button
              onClick={() => setZoomLevel(z => Math.min(8, z + 0.5))}
              style={{ background: 'none', border: 'none', color: 'var(--text-primary)', cursor: 'pointer', padding: '4px' }}
              title="Zoom In (+)"
            >
              <ZoomIn size={15} />
            </button>
            <button
              onClick={() => setZoomLevel(1)}
              style={{
                background: 'none',
                border: '1px solid var(--border-subtle)',
                borderRadius: '4px',
                color: zoomLevel === 1 ? 'var(--accent-cyan)' : 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '11px',
                padding: '2px 6px',
                fontWeight: 600
              }}
              title="Fit entire timeline to width"
            >
              Fit
            </button>
          </div>
        </div>
      </div>

      {/* TIMELINE CONFLICTS WARNING BANNER (IF DETECTED) */}
      {timelineConflicts.length > 0 && (
        <div style={{
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.4)',
          borderRadius: '6px',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#F87171',
          fontSize: '13px'
        }}>
          <AlertTriangle size={18} />
          <div>
            <strong>Timing Anomalies Detected:</strong> {timelineConflicts.map(c => c.message).join('; ')}
          </div>
        </div>
      )}
    </>
  );
};
