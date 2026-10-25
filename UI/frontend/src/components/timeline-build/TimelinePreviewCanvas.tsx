import React from 'react';
import {
  Sparkles,
  SkipBack,
  ChevronLeft,
  Pause,
  Play,
  ChevronRight,
  SkipForward
} from 'lucide-react';

export interface TimelinePreviewCanvasProps {
  aspect: string;
  activeScene: any;
  activeKineticText: any;
  activeGraphic: any;
  currentFrame: number;
  totalFrames: number;
  fps: number;
  isPlaying: boolean;
  setIsPlaying: React.Dispatch<React.SetStateAction<boolean>>;
  setCurrentFrame: React.Dispatch<React.SetStateAction<number>>;
  formatTimecode: (frame: number, fps: number) => string;
  formatSeconds: (s: number) => string;
  waveformPeaks: number[];
  segmentationScenes: any[];
  showVisualsTrack: boolean;
  setShowVisualsTrack: React.Dispatch<React.SetStateAction<boolean>>;
  showAudioTrack: boolean;
  setShowAudioTrack: React.Dispatch<React.SetStateAction<boolean>>;
  showCaptionsTrack: boolean;
  setShowCaptionsTrack: React.Dispatch<React.SetStateAction<boolean>>;
  showTypographyTrack: boolean;
  setShowTypographyTrack: React.Dispatch<React.SetStateAction<boolean>>;
  showMotionFxTrack: boolean;
  setShowMotionFxTrack: React.Dispatch<React.SetStateAction<boolean>>;
}

export const TimelinePreviewCanvas: React.FC<TimelinePreviewCanvasProps> = ({
  aspect,
  activeScene,
  activeKineticText,
  activeGraphic,
  currentFrame,
  totalFrames,
  fps,
  isPlaying,
  setIsPlaying,
  setCurrentFrame,
  formatTimecode,
  formatSeconds,
  waveformPeaks,
  segmentationScenes,
  showVisualsTrack,
  setShowVisualsTrack,
  showAudioTrack,
  setShowAudioTrack,
  showCaptionsTrack,
  setShowCaptionsTrack,
  showTypographyTrack,
  setShowTypographyTrack,
  showMotionFxTrack,
  setShowMotionFxTrack
}) => {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'minmax(320px, 520px) minmax(0, 1fr)',
      gap: '24px',
      alignItems: 'start'
    }}>
      {/* VIDEO PREVIEW CANVAS */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#030712',
        borderRadius: '8px',
        border: '1px solid var(--border-card)',
        overflow: 'hidden',
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)'
      }}>
        {/* Canvas Viewport */}
        <div style={{
          position: 'relative',
          width: '100%',
          aspectRatio: aspect === '9:16' ? '9/16' : '16/9',
          maxHeight: '340px',
          backgroundColor: '#050B18',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          overflow: 'hidden'
        }}>
          {/* Background Ambient Grid */}
          <div style={{
            position: 'absolute',
            inset: 0,
            backgroundImage: 'radial-gradient(rgba(34, 211, 238, 0.12) 1px, transparent 1px)',
            backgroundSize: '24px 24px',
            opacity: 0.6
          }} />

          {/* Simulated Live Composition Layers at currentFrame */}
          <div style={{
            position: 'relative',
            zIndex: 2,
            textAlign: 'center',
            padding: '20px',
            maxWidth: '85%'
          }}>
            {/* Active Scene Badge */}
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '16px',
              backgroundColor: 'rgba(34, 211, 238, 0.2)',
              border: '1px solid var(--accent-cyan)',
              color: 'var(--accent-cyan)',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.05em',
              marginBottom: '14px',
              textTransform: 'uppercase'
            }}>
              <Sparkles size={12} />
              {activeScene ? `${activeScene.scene_id} (${activeScene.pattern || 'custom_motion'})` : 'No Scene Active'}
            </div>

            {/* Component Badge */}
            <div style={{
              fontSize: '12px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)',
              marginBottom: '12px'
            }}>
              TSX Component: <span style={{ color: '#FCD34D' }}>scene_{parseInt(activeScene?.scene_id?.replace(/\D/g, '') || '1', 10)}.tsx</span>
            </div>

            {/* Kinetic Typography Preview Layer */}
            {activeKineticText && (
              <div style={{
                fontSize: '18px',
                fontWeight: 800,
                color: '#FFFFFF',
                textShadow: '0 2px 10px rgba(0, 0, 0, 0.8)',
                padding: '8px 14px',
                backgroundColor: 'rgba(0, 0, 0, 0.4)',
                borderRadius: '6px',
                border: '1px dashed rgba(255, 255, 255, 0.2)',
                display: 'inline-block',
                animation: 'fadeIn 0.3s ease-out'
              }}>
                {activeKineticText.text}
                <div style={{ fontSize: '10px', color: 'var(--accent-cyan)', fontWeight: 600, marginTop: '4px' }}>
                  [{activeKineticText.style || 'headline'} • {activeKineticText.preset || 'bounce'}]
                </div>
              </div>
            )}

            {/* Graphic Overlay Badge */}
            {activeGraphic && (
              <div style={{
                marginTop: '10px',
                fontSize: '11px',
                color: '#9CA3AF',
                backgroundColor: 'rgba(15, 23, 42, 0.6)',
                padding: '3px 8px',
                borderRadius: '4px',
                display: 'inline-block'
              }}>
                Overlay: {activeGraphic.preset} ({activeGraphic.why || 'motion effect'})
              </div>
            )}
          </div>

          {/* Aspect Ratio Guide Frame */}
          <div style={{
            position: 'absolute',
            inset: '8px',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            pointerEvents: 'none',
            borderRadius: '4px'
          }} />
        </div>

        {/* Transport Controls Bar */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          backgroundColor: 'var(--bg-elevated)',
          borderTop: '1px solid var(--border-subtle)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => setCurrentFrame(0)}
              style={{ background: 'none', border: 'none', color: 'var(--text-primary)', cursor: 'pointer', padding: '6px' }}
              title="Jump to Start (Home)"
            >
              <SkipBack size={16} />
            </button>
            <button
              onClick={() => setCurrentFrame(prev => Math.max(0, prev - 1))}
              style={{ background: 'none', border: 'none', color: 'var(--text-primary)', cursor: 'pointer', padding: '6px' }}
              title="Step Backward 1 Frame (J / Left Arrow)"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              onClick={() => setIsPlaying(p => !p)}
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: isPlaying ? '#EF4444' : 'var(--accent-cyan)',
                color: isPlaying ? '#FFFFFF' : '#0F172A',
                border: 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                boxShadow: '0 0 12px rgba(34, 211, 238, 0.4)'
              }}
              title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
            >
              {isPlaying ? <Pause size={18} /> : <Play size={18} style={{ marginLeft: '2px' }} />}
            </button>
            <button
              onClick={() => setCurrentFrame(prev => Math.min(totalFrames - 1, prev + 1))}
              style={{ background: 'none', border: 'none', color: 'var(--text-primary)', cursor: 'pointer', padding: '6px' }}
              title="Step Forward 1 Frame (L / Right Arrow)"
            >
              <ChevronRight size={18} />
            </button>
            <button
              onClick={() => setCurrentFrame(totalFrames - 1)}
              style={{ background: 'none', border: 'none', color: 'var(--text-primary)', cursor: 'pointer', padding: '6px' }}
              title="Jump to End (End)"
            >
              <SkipForward size={16} />
            </button>
          </div>

          {/* Timecode Readout */}
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '13px',
            fontWeight: 700,
            color: 'var(--accent-cyan)',
            backgroundColor: 'rgba(34, 211, 238, 0.08)',
            padding: '4px 10px',
            borderRadius: '4px',
            border: '1px solid rgba(34, 211, 238, 0.2)'
          }}>
            {formatTimecode(currentFrame, fps)}
          </div>
        </div>
      </div>

      {/* LIVE FRAME & SCENE INSPECTOR HUD */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--bg-elevated)',
        borderRadius: '8px',
        border: '1px solid var(--border-card)',
        padding: '20px',
        gap: '16px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
            Frame Inspection HUD
          </h3>
          <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            Frame {currentFrame} / {totalFrames} ({formatSeconds(currentFrame / fps)})
          </span>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '12px'
        }}>
          <div style={{ backgroundColor: 'var(--bg-card)', padding: '12px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Timecode</div>
            <div style={{ fontSize: '15px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)', marginTop: '4px' }}>
              {formatTimecode(currentFrame, fps)}
            </div>
          </div>

          <div style={{ backgroundColor: 'var(--bg-card)', padding: '12px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Active Scene</div>
            <div style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', marginTop: '4px' }}>
              {activeScene ? activeScene.scene_id : 'None'}
            </div>
          </div>

          <div style={{ backgroundColor: 'var(--bg-card)', padding: '12px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Scene Window</div>
            <div style={{ fontSize: '13px', fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', marginTop: '4px' }}>
              {activeScene ? `F${activeScene.start_frame} - F${activeScene.end_frame}` : '—'}
            </div>
          </div>

          <div style={{ backgroundColor: 'var(--bg-card)', padding: '12px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Audio Waveform</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: waveformPeaks.length > 0 ? 'var(--status-completed)' : 'var(--text-muted)', marginTop: '4px' }}>
              {waveformPeaks.length > 0 ? `${waveformPeaks.length} Peaks Decoded` : 'Not Loaded'}
            </div>
          </div>
        </div>

        {/* Active Spoken Narration Segment */}
        {segmentationScenes.length > 0 && (
          <div style={{
            backgroundColor: 'var(--bg-card)',
            borderRadius: '6px',
            border: '1px solid var(--border-subtle)',
            padding: '14px'
          }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
              Active Narration Segment (Telugu Audio)
            </div>
            <div style={{ fontSize: '13.5px', color: 'var(--text-primary)', lineHeight: 1.6 }}>
              {(() => {
                const currSec = currentFrame / fps;
                const seg = segmentationScenes.find((s: any) => currSec >= (s.start_seconds || 0) && currSec <= (s.end_seconds || 0));
                return seg ? (seg.narration || seg.transcript || seg.meaning || `Speech Segment ${seg.id || ''}`) : 'Audio silence / inter-scene gap';
              })()}
            </div>
          </div>
        )}

        {/* Track Visibility Quick Filters */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginRight: '4px' }}>Tracks:</span>
          <button
            onClick={() => setShowVisualsTrack(v => !v)}
            style={{
              fontSize: '11px',
              fontWeight: 600,
              padding: '4px 9px',
              borderRadius: '4px',
              backgroundColor: showVisualsTrack ? 'rgba(34, 211, 238, 0.15)' : 'var(--bg-card)',
              color: showVisualsTrack ? 'var(--accent-cyan)' : 'var(--text-muted)',
              border: '1px solid currentColor',
              cursor: 'pointer'
            }}
          >
            Visuals
          </button>
          <button
            onClick={() => setShowAudioTrack(v => !v)}
            style={{
              fontSize: '11px',
              fontWeight: 600,
              padding: '4px 9px',
              borderRadius: '4px',
              backgroundColor: showAudioTrack ? 'rgba(59, 130, 246, 0.15)' : 'var(--bg-card)',
              color: showAudioTrack ? '#60A5FA' : 'var(--text-muted)',
              border: '1px solid currentColor',
              cursor: 'pointer'
            }}
          >
            Audio Waveform
          </button>
          <button
            onClick={() => setShowCaptionsTrack(v => !v)}
            style={{
              fontSize: '11px',
              fontWeight: 600,
              padding: '4px 9px',
              borderRadius: '4px',
              backgroundColor: showCaptionsTrack ? 'rgba(16, 185, 129, 0.15)' : 'var(--bg-card)',
              color: showCaptionsTrack ? 'var(--status-completed)' : 'var(--text-muted)',
              border: '1px solid currentColor',
              cursor: 'pointer'
            }}
          >
            Captions
          </button>
          <button
            onClick={() => setShowTypographyTrack(v => !v)}
            style={{
              fontSize: '11px',
              fontWeight: 600,
              padding: '4px 9px',
              borderRadius: '4px',
              backgroundColor: showTypographyTrack ? 'rgba(245, 158, 11, 0.15)' : 'var(--bg-card)',
              color: showTypographyTrack ? '#F59E0B' : 'var(--text-muted)',
              border: '1px solid currentColor',
              cursor: 'pointer'
            }}
          >
            Kinetic Text
          </button>
          <button
            onClick={() => setShowMotionFxTrack(v => !v)}
            style={{
              fontSize: '11px',
              fontWeight: 600,
              padding: '4px 9px',
              borderRadius: '4px',
              backgroundColor: showMotionFxTrack ? 'rgba(168, 85, 247, 0.15)' : 'var(--bg-card)',
              color: showMotionFxTrack ? '#C084FC' : 'var(--text-muted)',
              border: '1px solid currentColor',
              cursor: 'pointer'
            }}
          >
            Motion FX
          </button>
        </div>
      </div>
    </div>
  );
};
