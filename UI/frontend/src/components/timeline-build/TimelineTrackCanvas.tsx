import React from 'react';
import { TimelineTrackHeaderColumn } from './TimelineTrackHeaderColumn';
import { TimelineSceneTile } from './TimelineSceneTile';
import { TimelineCaptionsTrack } from './TimelineCaptionsTrack';
import { TimelineTransitionMarks } from './TimelineTransitionMarks';
import { captionBlocks, type TranscriptSegment, type Transition } from './timelineCaptions';
import type { StillsResponse, Thumbs } from './timelineStills';

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
    <div style={{
      backgroundColor: '#030712',
      borderRadius: '8px',
      border: '1px solid var(--border-card)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Timeline Header Bar */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '10px 16px',
        backgroundColor: 'var(--bg-elevated)',
        borderBottom: '1px solid var(--border-subtle)',
        fontSize: '12px',
        color: 'var(--text-muted)'
      }}>
        <div>Click ruler or track to scrub playhead • Drag playhead for frame-by-frame inspection</div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <span>Ruler Scale: <strong>{fps} fps</strong></span>
          <span>Current: <strong>Frame {currentFrame}</strong></span>
        </div>
      </div>

      {/* Multi-Track Grid Container (Synchronized Horizontal Scroll) */}
      <div style={{ display: 'flex', position: 'relative' }}>
        {/* Left Track Labels Header Column (Fixed 180px) */}
        <TimelineTrackHeaderColumn
          showVisualsTrack={showVisualsTrack}
          showAudioTrack={showAudioTrack}
          showCaptionsTrack={showCaptionsTrack}
          showTypographyTrack={showTypographyTrack}
          showMotionFxTrack={showMotionFxTrack}
        />

        {/* Right Scrollable Tracks Container */}
        <div 
          ref={timelineScrollRef}
          style={{
            flex: 1,
            overflowX: 'auto',
            overflowY: 'hidden',
            position: 'relative',
            backgroundColor: '#020617'
          }}
        >
          <div 
            style={{
              width: `${timelinePixelWidth}px`,
              position: 'relative',
              userSelect: 'none'
            }}
            onClick={handleTimelineClick}
          >
            {/* TIME RULER TRACK (Timecode, Timestamps & Frame Numbers) */}
            <div style={{
              height: '36px',
              backgroundColor: '#0B1120',
              borderBottom: '1px solid var(--border-subtle)',
              position: 'relative',
              cursor: 'pointer'
            }}>
              {/* Major Second Ticks & Frame Marks (Dynamic, non-colliding) */}
              {rulerTicks.map((tick, idx) => {
                if (tick.leftPx > timelinePixelWidth) return null;
                return (
                  <div 
                    key={idx}
                    style={{
                      position: 'absolute',
                      left: `${tick.leftPx}px`,
                      top: 0,
                      bottom: 0,
                      borderLeft: '1px solid rgba(255, 255, 255, 0.25)',
                      paddingLeft: '5px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'center',
                      pointerEvents: 'none',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    <span style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)', fontWeight: 700 }}>
                      {formatTimecode(tick.frame, fps)}
                    </span>
                    <span style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      F{tick.frame} ({tick.sec}s)
                    </span>
                  </div>
                );
              })}
            </div>

            {/* VERTICAL PLAYHEAD NEEDLE */}
            <div 
              style={{
                position: 'absolute',
                left: `${frameToPx(currentFrame)}px`,
                top: 0,
                bottom: 0,
                width: '2px',
                backgroundColor: '#EF4444',
                boxShadow: '0 0 10px rgba(239, 68, 68, 0.8)',
                zIndex: 40,
                pointerEvents: 'none',
                transition: isPlaying ? 'none' : 'left 0.05s ease-out'
              }}
            >
              {/* Playhead Marker Pin */}
              <div style={{
                position: 'absolute',
                top: 0,
                left: '-6px',
                width: '14px',
                height: '14px',
                backgroundColor: '#EF4444',
                clipPath: 'polygon(0 0, 100% 0, 50% 100%)'
              }} />
            </div>

            {/* TRACK 1: SCENE VISUALS & MEDIA */}
            {showVisualsTrack && (
              <div style={{
                height: '84px',
                borderBottom: '1px solid var(--border-subtle)',
                position: 'relative',
                backgroundColor: 'rgba(15, 23, 42, 0.3)'
              }}>
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
              <div style={{
                height: '56px',
                borderBottom: '1px solid var(--border-subtle)',
                position: 'relative',
                backgroundColor: 'rgba(11, 19, 43, 0.4)'
              }}>
                {waveformPeaks.length > 0 ? (
                  <svg
                    style={{
                      width: '100%',
                      height: '100%',
                      display: 'block'
                    }}
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
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', padding: '18px 16px' }}>
                    Waveform visualization not generated.
                  </div>
                )}
              </div>
            )}

            {/* TRACK 3: CAPTIONS / SPEECH SEGMENTS */}
            {showCaptionsTrack && (
              <div style={{
                height: '52px',
                borderBottom: '1px solid var(--border-subtle)',
                position: 'relative',
                backgroundColor: 'rgba(15, 23, 42, 0.2)'
              }}>
                <TimelineCaptionsTrack blocks={captionBlocks(transcriptSegments, fps)} frameToPx={frameToPx} fps={fps} formatSeconds={formatSeconds} />
              </div>
            )}

            {/* TRACK 4: KINETIC TYPOGRAPHY */}
            {showTypographyTrack && (
              <div style={{
                height: '52px',
                borderBottom: '1px solid var(--border-subtle)',
                position: 'relative',
                backgroundColor: 'rgba(15, 23, 42, 0.3)'
              }}>
                {motionPlan?.scenes?.flatMap((s: any) => (s.texts || []).map((t: any, tIdx: number) => {
                  const sceneBaseSec = s.start || 0;
                  const enterSec = sceneBaseSec + (t.at ?? t.enter_s ?? 0);
                  const exitSec = t.until ? (sceneBaseSec + t.until) : (sceneBaseSec + (s.end - s.start));
                  const left = frameToPx(Math.round(enterSec * fps));
                  const width = frameToPx(Math.round((exitSec - enterSec) * fps));

                  return (
                    <div
                      key={`${s.id}-${tIdx}`}
                      style={{
                        position: 'absolute',
                        left: `${left}px`,
                        width: `${Math.max(20, width)}px`,
                        top: '6px',
                        bottom: '6px',
                        backgroundColor: 'rgba(245, 158, 11, 0.18)',
                        border: '1px solid rgba(245, 158, 11, 0.5)',
                        borderRadius: '4px',
                        padding: '4px 8px',
                        overflow: 'hidden',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                      title={`Kinetic Text: "${t.text}" (${t.preset || 'bounce'})`}
                    >
                      <span style={{ fontSize: '11px', color: '#FCD34D', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        "{t.text}" [{t.preset || 'text'}]
                      </span>
                    </div>
                  );
                }))}
              </div>
            )}

            {/* TRACK 5: MOTION GRAPHICS & FX */}
            {showMotionFxTrack && (
              <div style={{
                height: '52px',
                borderBottom: '1px solid var(--border-subtle)',
                position: 'relative',
                backgroundColor: 'rgba(15, 23, 42, 0.2)'
              }}>
                {motionPlan?.scenes?.flatMap((s: any) => (s.graphics || []).map((g: any, gIdx: number) => {
                  const sceneBaseSec = s.start || 0;
                  const startSec = sceneBaseSec + (g.start ?? 0);
                  const endSec = g.end ? (sceneBaseSec + g.end) : (sceneBaseSec + (s.end - s.start));
                  const left = frameToPx(Math.round(startSec * fps));
                  const width = frameToPx(Math.round((endSec - startSec) * fps));

                  return (
                    <div
                      key={`${s.id}-${gIdx}`}
                      style={{
                        position: 'absolute',
                        left: `${left}px`,
                        width: `${Math.max(16, width)}px`,
                        top: '6px',
                        bottom: '6px',
                        backgroundColor: 'rgba(168, 85, 247, 0.18)',
                        border: '1px solid rgba(168, 85, 247, 0.5)',
                        borderRadius: '4px',
                        padding: '4px 8px',
                        overflow: 'hidden',
                        display: 'flex',
                        alignItems: 'center'
                      }}
                      title={`FX: ${g.preset} (${g.why || 'atmosphere'})`}
                    >
                      <span style={{ fontSize: '11px', color: '#D8B4FE', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
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
