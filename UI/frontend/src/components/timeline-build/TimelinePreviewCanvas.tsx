import React from 'react';
import { SkipBack, ChevronLeft, Pause, Play, ChevronRight, SkipForward } from 'lucide-react';
import styles from './TimelinePreviewCanvas.module.css';
import { stillAt, thumbStyle, type StillsResponse, type Thumbs } from './timelineStills';

export interface TimelinePreviewCanvasProps {
  aspect: string;
  activeScene: any;
  stills: StillsResponse;
  thumbs: Thumbs | null;
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

// Why the viewport has no frame: said plainly instead of drawing a stand-in.
function noFrameReason(stills: StillsResponse): string {
  if (!stills.exists) return 'No preview stills yet. Run Motion Validation (Generate Preview) to draw the real frames of this video.';
  if (!stills.current) return 'The preview stills belong to an older composition or renderer. Generate the preview again to see the current frames.';
  return 'This scene has no preview still.';
}

export const TimelinePreviewCanvas: React.FC<TimelinePreviewCanvasProps> = ({
  aspect, activeScene, stills, thumbs, currentFrame, totalFrames, fps, isPlaying, setIsPlaying, setCurrentFrame, formatTimecode, formatSeconds, waveformPeaks, segmentationScenes,
  showVisualsTrack, setShowVisualsTrack, showAudioTrack, setShowAudioTrack, showCaptionsTrack, setShowCaptionsTrack, showTypographyTrack, setShowTypographyTrack, showMotionFxTrack, setShowMotionFxTrack
}) => {
  const frameOfVideo = thumbStyle(thumbs, currentFrame, fps);                         // the rendered video's own frame at this second: smooth while scrubbing or playing
  const still = activeScene ? stillAt(stills.samples, activeScene.scene_id, currentFrame) : null;
  const filters = [
    { label: 'Visuals', on: showVisualsTrack, set: setShowVisualsTrack, cls: styles.fVisuals },
    { label: 'Audio Waveform', on: showAudioTrack, set: setShowAudioTrack, cls: styles.fAudio },
    { label: 'Captions', on: showCaptionsTrack, set: setShowCaptionsTrack, cls: styles.fCaptions },
    { label: 'Kinetic Text', on: showTypographyTrack, set: setShowTypographyTrack, cls: styles.fText },
    { label: 'Motion FX', on: showMotionFxTrack, set: setShowMotionFxTrack, cls: styles.fFx },
  ];
  const currSec = currentFrame / fps;
  const seg = segmentationScenes.find((s: any) => currSec >= (s.start_seconds || 0) && currSec <= (s.end_seconds || 0));

  return (
    <div className={styles.layout}>
      <div className={styles.player}>
        <div className={styles.viewport} style={{ aspectRatio: aspect === '9:16' ? '9/16' : '16/9' }} data-testid="timeline-preview-viewport">
          {frameOfVideo ? (
            <>
              <div className={styles.videoFrame} style={frameOfVideo} data-testid="timeline-preview-video-frame" />
              <span className={styles.stillBadge}>rendered video • {formatTimecode(currentFrame, fps)}</span>
            </>
          ) : still ? (
            <>
              <img className={styles.still} src={still.url} alt={`${activeScene.scene_id} ${still.kind}`} data-testid="timeline-preview-still" />
              <span className={styles.stillBadge}>{activeScene.scene_id} • {still.kind} still F{still.frame}</span>
            </>
          ) : (
            <div className={styles.noFrame} data-testid="timeline-preview-empty">{noFrameReason(stills)}</div>
          )}
        </div>

        <div className={styles.transport}>
          <div className={styles.buttons}>
            <button className={styles.iconBtn} onClick={() => setCurrentFrame(0)} title="Jump to Start (Home)"><SkipBack size={16} /></button>
            <button className={styles.iconBtn} onClick={() => setCurrentFrame(prev => Math.max(0, prev - 1))} title="Step Backward 1 Frame (J / Left Arrow)"><ChevronLeft size={18} /></button>
            <button className={`${styles.playBtn} ${isPlaying ? styles.playing : ''}`} onClick={() => setIsPlaying(p => !p)} title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}>
              {isPlaying ? <Pause size={18} /> : <Play size={18} className={styles.playIcon} />}
            </button>
            <button className={styles.iconBtn} onClick={() => setCurrentFrame(prev => Math.min(totalFrames - 1, prev + 1))} title="Step Forward 1 Frame (L / Right Arrow)"><ChevronRight size={18} /></button>
            <button className={styles.iconBtn} onClick={() => setCurrentFrame(totalFrames - 1)} title="Jump to End (End)"><SkipForward size={16} /></button>
          </div>
          <div className={styles.timecode}>{formatTimecode(currentFrame, fps)}</div>
        </div>
      </div>

      <div className={styles.hud}>
        <div className={styles.hudHead}>
          <h3 className={styles.hudTitle}>Frame Inspection HUD</h3>
          <span className={styles.hudFrame}>Frame {currentFrame} / {totalFrames} ({formatSeconds(currentFrame / fps)})</span>
        </div>

        <div className={styles.cards}>
          <div className={styles.card}><div className={styles.cardLabel}>Timecode</div><div className={`${styles.cardValue} ${styles.cyan}`}>{formatTimecode(currentFrame, fps)}</div></div>
          <div className={styles.card}><div className={styles.cardLabel}>Active Scene</div><div className={styles.cardValue}>{activeScene ? activeScene.scene_id : 'None'}</div></div>
          <div className={styles.card}><div className={styles.cardLabel}>Scene Window</div><div className={`${styles.cardValue} ${styles.mono}`}>{activeScene ? `F${activeScene.start_frame} - F${activeScene.end_frame}` : '—'}</div></div>
          <div className={styles.card}>
            <div className={styles.cardLabel}>Audio Waveform</div>
            <div className={`${styles.cardValue} ${waveformPeaks.length > 0 ? styles.ok : styles.muted}`}>{waveformPeaks.length > 0 ? `${waveformPeaks.length} Peaks Decoded` : 'Not Loaded'}</div>
          </div>
        </div>

        {segmentationScenes.length > 0 && (
          <div className={styles.narration}>
            <div className={styles.cardLabel}>Active Narration Segment (Telugu Audio)</div>
            <div className={styles.narrationText}>{seg ? (seg.narration || seg.transcript || seg.meaning || `Speech Segment ${seg.id || ''}`) : 'Audio silence / inter-scene gap'}</div>
          </div>
        )}

        <div className={styles.filters}>
          <span className={styles.filtersLabel}>Tracks:</span>
          {filters.map(f => (
            <button key={f.label} className={`${styles.filter} ${f.cls} ${f.on ? styles.filterOn : ''}`} onClick={() => f.set(v => !v)}>{f.label}</button>
          ))}
        </div>
      </div>
    </div>
  );
};
