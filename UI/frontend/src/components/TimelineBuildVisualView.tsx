import React, { useState } from 'react';
import { API_BASE } from '../services/api';
import { TimelinePreviewCanvas } from './timeline-build/TimelinePreviewCanvas';
import { TimelineTrackCanvas } from './timeline-build/TimelineTrackCanvas';
import { TimelineSceneInspector } from './timeline-build/TimelineSceneInspector';
import { TimelineHeaderBar } from './timeline-build/TimelineHeaderBar';
import { TimelineSceneModal } from './timeline-build/TimelineSceneModal';
import { useTimelineData, formatTimecode, formatSeconds } from './timeline-build/useTimelineData';
import { useTimelinePlayback } from './timeline-build/useTimelinePlayback';

export { formatTimecode, formatSeconds };
export type { TimelineSceneItem } from './timeline-build/useTimelineData';

interface TimelineBuildVisualViewProps {
  projectId: string;
  onRetryTimeline?: () => void;
  isPipelineRunning?: boolean;
}

export const TimelineBuildVisualView: React.FC<TimelineBuildVisualViewProps> = ({
  projectId,
  onRetryTimeline,
  isPipelineRunning = false
}) => {
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [popupSceneId, setPopupSceneId] = useState<string | null>(null);   // the scene popup (double click on a tile)
  const [inspectorTab, setInspectorTab] = useState<'details' | 'layers' | 'validation' | 'raw_json'>('details');

  // Track Visibility Toggles
  const [showVisualsTrack, setShowVisualsTrack] = useState<boolean>(true);
  const [showAudioTrack, setShowAudioTrack] = useState<boolean>(true);
  const [showCaptionsTrack, setShowCaptionsTrack] = useState<boolean>(true);
  const [showTypographyTrack, setShowTypographyTrack] = useState<boolean>(true);
  const [showMotionFxTrack, setShowMotionFxTrack] = useState<boolean>(true);

  // Playhead & Playback Hook
  const [frameForData, setFrameForData] = useState<number>(0);

  const {
    loading,
    error,
    timelineBuildReport,
    timelineData,
    waveformPeaks,
    motionPlan,
    segmentationScenes,
    stills,
    thumbs,
    transcriptSegments,
    transitions,
    fps,
    totalFrames,
    totalDurationSeconds,
    aspect,
    scenesList,
    activeScene,
    selectedScene,
    timelineConflicts
  } = useTimelineData(projectId, frameForData, selectedSceneId);

  const {
    currentFrame,
    setCurrentFrame,
    isPlaying,
    setIsPlaying,
    zoomLevel,
    setZoomLevel,
    audioRef,
    timelineScrollRef,
    timelinePixelWidth,
    frameToPx,
    rulerTicks,
    handleTimelineClick,
    handleCopyJson,
    copiedArtifact
  } = useTimelinePlayback(fps, totalFrames, totalDurationSeconds);

  // Keep frameForData in sync when currentFrame updates
  React.useEffect(() => {
    setFrameForData(currentFrame);
  }, [currentFrame]);

  const popupIdx = scenesList.findIndex(s => s.scene_id === popupSceneId);

  if (loading) {
    return (
      <div style={{
        padding: '60px 32px',
        textAlign: 'center',
        color: 'var(--text-muted)',
        fontFamily: 'var(--font-sans)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '16px'
      }}>
        <div style={{
          width: '36px',
          height: '36px',
          border: '3px solid rgba(34, 211, 238, 0.2)',
          borderTopColor: 'var(--accent-cyan)',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite'
        }} />
        <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
          Loading Frame-Accurate Timeline Data...
        </div>
        <div style={{ fontSize: '13px' }}>
          Extracting composition tracks, audio waveform peaks, and kinetic animation parameters.
        </div>
      </div>
    );
  }

  if (error && !timelineData && !timelineBuildReport) {
    return (
      <div style={{
        padding: '32px',
        textAlign: 'center',
        color: 'var(--status-failed)',
        backgroundColor: 'var(--bg-elevated)',
        borderRadius: '8px',
        border: '1px solid var(--border-card)'
      }}>
        {error}
      </div>
    );
  }

  return (
    <div 
      data-testid="timeline-build-visual-view"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '24px',
        backgroundColor: 'var(--bg-card)',
        borderRadius: '8px',
        border: '1px solid var(--border-card)',
        padding: '24px',
        color: 'var(--text-primary)',
        fontFamily: 'var(--font-sans)'
      }}
    >
      {/* Hidden Audio Element for synced playback */}
      <audio 
        ref={audioRef}
        src={`${API_BASE}/projects/${projectId}/timeline-build/audio`}
        preload="auto"
      />

      {/* TOP CONTROL HEADER & CONFLICTS BANNER */}
      <TimelineHeaderBar
        timelineBuildReport={timelineBuildReport}
        aspect={aspect}
        fps={fps}
        totalDurationSeconds={totalDurationSeconds}
        totalFrames={totalFrames}
        scenesCount={scenesList.length}
        onRetryTimeline={onRetryTimeline}
        isPipelineRunning={isPipelineRunning}
        zoomLevel={zoomLevel}
        setZoomLevel={setZoomLevel}
        timelineConflicts={timelineConflicts}
        formatSeconds={formatSeconds}
      />

      {/* UPPER SECTION: VIDEO PREVIEW CANVAS & LIVE FRAME HUD */}
      <TimelinePreviewCanvas
        aspect={aspect}
        activeScene={activeScene}
        stills={stills}
        thumbs={thumbs}
        currentFrame={currentFrame}
        totalFrames={totalFrames}
        fps={fps}
        isPlaying={isPlaying}
        setIsPlaying={setIsPlaying}
        setCurrentFrame={setCurrentFrame}
        formatTimecode={formatTimecode}
        formatSeconds={formatSeconds}
        waveformPeaks={waveformPeaks}
        segmentationScenes={segmentationScenes}
        showVisualsTrack={showVisualsTrack}
        setShowVisualsTrack={setShowVisualsTrack}
        showAudioTrack={showAudioTrack}
        setShowAudioTrack={setShowAudioTrack}
        showCaptionsTrack={showCaptionsTrack}
        setShowCaptionsTrack={setShowCaptionsTrack}
        showTypographyTrack={showTypographyTrack}
        setShowTypographyTrack={setShowTypographyTrack}
        showMotionFxTrack={showMotionFxTrack}
        setShowMotionFxTrack={setShowMotionFxTrack}
      />

      {/* LOWER SECTION: HORIZONTAL MULTI-TRACK TIMELINE CANVAS */}
      <TimelineTrackCanvas
        fps={fps}
        currentFrame={currentFrame}
        totalFrames={totalFrames}
        timelineScrollRef={timelineScrollRef}
        timelinePixelWidth={timelinePixelWidth}
        handleTimelineClick={handleTimelineClick}
        rulerTicks={rulerTicks}
        formatTimecode={formatTimecode}
        formatSeconds={formatSeconds}
        frameToPx={frameToPx}
        isPlaying={isPlaying}
        showVisualsTrack={showVisualsTrack}
        showAudioTrack={showAudioTrack}
        showCaptionsTrack={showCaptionsTrack}
        showTypographyTrack={showTypographyTrack}
        showMotionFxTrack={showMotionFxTrack}
        scenesList={scenesList}
        selectedScene={selectedScene}
        activeScene={activeScene}
        setSelectedSceneId={setSelectedSceneId}
        setCurrentFrame={setCurrentFrame}
        waveformPeaks={waveformPeaks}
        stills={stills}
        thumbs={thumbs}
        motionPlan={motionPlan}
        transcriptSegments={transcriptSegments}
        transitions={transitions}
        onOpenScene={setPopupSceneId}
      />

      {popupIdx >= 0 && (
        <TimelineSceneModal
          scene={scenesList[popupIdx]}
          idx={popupIdx}
          total={scenesList.length}
          fps={fps}
          stills={stills.samples}
          thumbs={thumbs}
          segments={transcriptSegments}
          transitions={transitions}
          formatSeconds={formatSeconds}
          onClose={() => setPopupSceneId(null)}
          onStep={(d) => setPopupSceneId(scenesList[popupIdx + d]?.scene_id ?? null)}
        />
      )}

      {/* SELECTED SCENE DEEP DETAILS INSPECTOR */}
      {selectedScene && (
        <TimelineSceneInspector
          selectedScene={selectedScene}
          inspectorTab={inspectorTab}
          setInspectorTab={setInspectorTab}
          formatSeconds={formatSeconds}
          fps={fps}
          projectId={projectId}
          handleCopyJson={handleCopyJson}
          copiedArtifact={copiedArtifact}
        />
      )}
    </div>
  );
};

export default TimelineBuildVisualView;
