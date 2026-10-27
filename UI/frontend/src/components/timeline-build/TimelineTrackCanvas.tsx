import React from 'react';
import { TimelineTrackHeaderColumn } from './TimelineTrackHeaderColumn';
import { TimelineSceneTile } from './TimelineSceneTile';
import { TimelineCaptionsTrack } from './TimelineCaptionsTrack';
import { TimelineTransitionMarks } from './TimelineTransitionMarks';
import { captionBlocks, type TranscriptSegment, type Transition } from './timelineCaptions';
import type { StillsResponse, Thumbs } from './timelineStills';
import styles from './TimelineTrackCanvas.module.css';

export interface TimelineTrackCanvasProps {
  fps: number;
  currentFrame: number;
  totalFrames: number;
  timelineScrollRef: React.RefObject<HTMLDivElement | null>;
  timelinePixelWidth: number;
  handleTimelineClick: (e: React.MouseEvent<HTMLDivElement>) => void;
  rulerTicks: Array<{ frame: number; sec: number; leftPx: number }>;
  formatTimecode: (frame: number, fps: number) => string;
  formatSeconds: (s: number) => string;
  frameToPx: (frame: number) => number;
  isPlaying: boolean;
  showVisualsTrack: boolean;
  showAudioTrack: boolean;
  showCaptionsTrack: boolean;
  showTypographyTrack: boolean;
  showMotionFxTrack: boolean;
  scenesList: any[];
  selectedScene: any;
  activeScene: any;
  setSelectedSceneId: (id: string) => void;
  setCurrentFrame: React.Dispatch<React.SetStateAction<number>>;
  waveformPeaks: number[];
  stills: StillsResponse;
  thumbs: Thumbs | null;
  motionPlan: any;
  transcriptSegments: TranscriptSegment[];
  transitions: Transition[];
  onOpenScene: (sceneId: string) => void;
}

export const TimelineTrackCanvas: React.FC<TimelineTrackCanvasProps> = ({
  fps,
  currentFrame,
  totalFrames: _totalFrames,
  timelineScrollRef,
  timelinePixelWidth,
  handleTimelineClick,
  rulerTicks,
  formatTimecode,
  formatSeconds,
  frameToPx,
  isPlaying,
  showVisualsTrack,
  showAudioTrack,
  showCaptionsTrack,
  showTypographyTrack,
  showMotionFxTrack,
  scenesList,
  selectedScene,
  activeScene,
  setSelectedSceneId,
  setCurrentFrame,
  waveformPeaks,
  stills,
  thumbs,
  motionPlan,
  transcriptSegments,
  transitions,
  onOpenScene
}) => {
  return (
    <div className={styles.canvas}>
      {/* Timeline Header Bar */}
      <div className={styles.headerBar}>
        <div>Click ruler or track to scrub playhead • Drag playhead for frame-by-frame inspection</div>
        <div className={styles.headerStats}>
          <span>Ruler Scale: <strong>{fps} fps</strong></span>
          <span>Current: <strong>Frame {currentFrame}</strong></span>
        </div>
      </div>

      {/* Multi-Track Grid Container (Synchronized Horizontal Scroll) */}
      <div className={styles.grid}>
        {/* Left Track Labels Header Column (Fixed 180px) */}
        <TimelineTrackHeaderColumn
          showVisualsTrack={showVisualsTrack}
          showAudioTrack={showAudioTrack}
          showCaptionsTrack={showCaptionsTrack}
          showTypographyTrack={showTypographyTrack}
          showMotionFxTrack={showMotionFxTrack}
        />

        {/* Right Scrollable Tracks Container */}
        <div ref={timelineScrollRef} className={styles.scroller}>
          <div className={styles.tracks} style={{ width: `${timelinePixelWidth}px` }} onClick={handleTimelineClick}>
            {/* TIME RULER TRACK (Timecode, Timestamps & Frame Numbers) */}
            <div className={styles.ruler}>
              {/* Major Second Ticks & Frame Marks (Dynamic, non-colliding) */}
              {rulerTicks.map((tick, idx) => {
                if (tick.leftPx > timelinePixelWidth) return null;
                return (
                  <div key={idx} className={styles.tick} style={{ left: `${tick.leftPx}px` }}>
                    <span className={styles.tickTimecode}>
                      {formatTimecode(tick.frame, fps)}
                    </span>
                    <span className={styles.tickFrame}>
                      F{tick.frame} ({tick.sec}s)
                    </span>
                  </div>
                );
              })}
            </div>

            {/* VERTICAL PLAYHEAD NEEDLE */}
            <div
              className={`${styles.playhead} ${isPlaying ? styles.playing : ''}`.trim()}
              style={{ left: `${frameToPx(currentFrame)}px` }}
            >
              {/* Playhead Marker Pin */}
              <div className={styles.playheadPin} />
            </div>

            {/* TRACK 1: SCENE VISUALS & MEDIA */}
            {showVisualsTrack && (
              <div className={`${styles.track} ${styles.visuals}`}>
                {scenesList.map((scene, idx) => (
                  <TimelineSceneTile
                    key={scene.item_id || idx}
                    scene={scene}
                    stills={stills.samples}
                    thumbs={thumbs}
                    fps={fps}
                    leftPx={frameToPx(scene.start_frame)}
                    widthPx={frameToPx(scene.duration_frames)}
                    selected={selectedScene?.scene_id === scene.scene_id}
                    current={activeScene?.scene_id === scene.scene_id}
                    onSelect={() => { setSelectedSceneId(scene.scene_id); setCurrentFrame(scene.start_frame); }}
                    onOpen={() => onOpenScene(scene.scene_id)}
                    formatSeconds={formatSeconds}
                  />
                ))}
                <TimelineTransitionMarks transitions={transitions} frameToPx={frameToPx} fps={fps} />
              </div>
            )}

            {/* TRACK 2: NARRATION AUDIO WAVEFORM */}
            {showAudioTrack && (
              <div className={`${styles.track} ${styles.audio}`}>
                {waveformPeaks.length > 0 ? (
                  <svg
                    className={styles.waveform}
                    preserveAspectRatio="none"
                    viewBox={`0 0 ${waveformPeaks.length} 100`}
                  >
                    <defs>
                      <linearGradient id="waveformGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#22D3EE" stopOpacity="0.8" />
                        <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.3" />
                      </linearGradient>
                    </defs>
                    {waveformPeaks.map((peak, idx) => {
                      const h = Math.max(4, Math.min(95, peak * 100));
                      return (
                        <rect
                          key={idx}
                          x={idx}
                          y={(100 - h) / 2}
                          width={0.8}
                          height={h}
                          fill="url(#waveformGrad)"
                        />
                      );
                    })}
                  </svg>
                ) : (
                  <div className={styles.noWaveform}>
                    Waveform visualization not generated.
                  </div>
                )}
              </div>
            )}

            {/* TRACK 3: CAPTIONS / SPEECH SEGMENTS */}
            {showCaptionsTrack && (
              <div className={styles.track}>
                <TimelineCaptionsTrack blocks={captionBlocks(transcriptSegments, fps)} frameToPx={frameToPx} fps={fps} formatSeconds={formatSeconds} />
              </div>
            )}

            {/* TRACK 4: KINETIC TYPOGRAPHY */}
            {showTypographyTrack && (
              <div className={`${styles.track} ${styles.typography}`}>
                {motionPlan?.scenes?.flatMap((s: any) => (s.texts || []).map((t: any, tIdx: number) => {
                  const sceneBaseSec = s.start || 0;
                  const enterSec = sceneBaseSec + (t.at ?? t.enter_s ?? 0);
                  const exitSec = t.until ? (sceneBaseSec + t.until) : (sceneBaseSec + (s.end - s.start));
                  const left = frameToPx(Math.round(enterSec * fps));
                  const width = frameToPx(Math.round((exitSec - enterSec) * fps));

                  return (
                    <div
                      key={`${s.id}-${tIdx}`}
                      className={`${styles.clip} ${styles.text}`}
                      style={{ left: `${left}px`, width: `${Math.max(20, width)}px` }}
                      title={`Kinetic Text: "${t.text}" (${t.preset || 'bounce'})`}
                    >
                      <span className={styles.clipLabel}>
                        "{t.text}" [{t.preset || 'text'}]
                      </span>
                    </div>
                  );
                }))}
              </div>
            )}

            {/* TRACK 5: MOTION GRAPHICS & FX */}
            {showMotionFxTrack && (
              <div className={styles.track}>
                {motionPlan?.scenes?.flatMap((s: any) => (s.graphics || []).map((g: any, gIdx: number) => {
                  const sceneBaseSec = s.start || 0;
                  const startSec = sceneBaseSec + (g.start ?? 0);
                  const endSec = g.end ? (sceneBaseSec + g.end) : (sceneBaseSec + (s.end - s.start));
                  const left = frameToPx(Math.round(startSec * fps));
                  const width = frameToPx(Math.round((endSec - startSec) * fps));

                  return (
                    <div
                      key={`${s.id}-${gIdx}`}
                      className={`${styles.clip} ${styles.fx}`}
                      style={{ left: `${left}px`, width: `${Math.max(16, width)}px` }}
                      title={`FX: ${g.preset} (${g.why || 'atmosphere'})`}
                    >
                      <span className={styles.clipLabel}>
                        {g.preset}
                      </span>
                    </div>
                  );
                }))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
