import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { 
  fetchTimelineBuildData, 
  fetchTimelineJson, 
  fetchTimelineWaveform, 
  fetchMotionData, 
  fetchSceneSegmentation,
  API_BASE 
} from '../services/api';
import { TimelinePreviewCanvas } from './timeline-build/TimelinePreviewCanvas';
import { TimelineTrackCanvas } from './timeline-build/TimelineTrackCanvas';
import { TimelineSceneInspector } from './timeline-build/TimelineSceneInspector';
import { TimelineHeaderBar } from './timeline-build/TimelineHeaderBar';

interface TimelineBuildVisualViewProps {
  projectId: string;
  onRetryTimeline?: () => void;
  isPipelineRunning?: boolean;
}

export interface TimelineSceneItem {
  item_id: string;
  scene_id: string;
  start_frame: number;
  end_frame: number;
  duration_frames: number;
  source_start_seconds: number;
  source_end_seconds: number;
  narration_start_frame?: number;
  narration_end_frame?: number;
  narration_start_seconds?: number;
  narration_end_seconds?: number;
  pattern?: string;
  camera?: string;
  descriptor_refs?: string[];
  composition_ref?: string;
  layers?: any[];
  transition_out?: any;
}

export function formatTimecode(frame: number, fps: number = 30): string {
  const totalSeconds = Math.max(0, frame) / fps;
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);
  const frames = Math.floor(frame % fps);
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}:${String(frames).padStart(2, '0')}`;
}

export function formatSeconds(sec: number): string {
  return `${sec.toFixed(2)}s`;
}

export const TimelineBuildVisualView: React.FC<TimelineBuildVisualViewProps> = ({
  projectId,
  onRetryTimeline,
  isPipelineRunning = false
}) => {
  // State
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [timelineBuildReport, setTimelineBuildReport] = useState<any | null>(null);
  const [timelineData, setTimelineData] = useState<any | null>(null);
  const [waveformPeaks, setWaveformPeaks] = useState<number[]>([]);
  const [motionPlan, setMotionPlan] = useState<any | null>(null);
  const [segmentationScenes, setSegmentationScenes] = useState<any[]>([]);

  // Navigation & Playback State
  const [currentFrame, setCurrentFrame] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [copiedArtifact, setCopiedArtifact] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<'details' | 'layers' | 'validation' | 'raw_json'>('details');

  // Track Visibility Toggles
  const [showVisualsTrack, setShowVisualsTrack] = useState<boolean>(true);
  const [showAudioTrack, setShowAudioTrack] = useState<boolean>(true);
  const [showCaptionsTrack, setShowCaptionsTrack] = useState<boolean>(true);
  const [showTypographyTrack, setShowTypographyTrack] = useState<boolean>(true);
  const [showMotionFxTrack, setShowMotionFxTrack] = useState<boolean>(true);

  // Audio Ref for preview synchronization
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timelineScrollRef = useRef<HTMLDivElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // 1. Fetch authoritative timeline datasets
  const loadTimelineDatasets = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);

    try {
      const [buildRes, tlRes, wfRes, motionRes, segRes] = await Promise.all([
        fetchTimelineBuildData(projectId),
        fetchTimelineJson(projectId),
        fetchTimelineWaveform(projectId),
        fetchMotionData(projectId),
        fetchSceneSegmentation(projectId)
      ]);

      if (buildRes.ok) setTimelineBuildReport(buildRes.data);
      if (tlRes.ok) setTimelineData(tlRes.data);
      if (wfRes.ok && Array.isArray(wfRes.data?.peaks)) setWaveformPeaks(wfRes.data.peaks);
      if (motionRes.ok && motionRes.data?.plan) setMotionPlan(motionRes.data.plan);
      if (segRes.ok && Array.isArray(segRes.data?.scenes)) setSegmentationScenes(segRes.data.scenes);

      if (!buildRes.ok && !tlRes.ok) {
        setError(buildRes.error || tlRes.error || 'Failed to load timeline build data.');
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load timeline dataset.');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadTimelineDatasets();
  }, [loadTimelineDatasets]);

  // Derived Project Parameters
  const fps = 30;
  const totalFrames = useMemo(() => {
    if (timelineBuildReport?.counts?.duration_frames) return timelineBuildReport.counts.duration_frames;
    if (timelineData?.timing?.total_frames) return timelineData.timing.total_frames;
    const sceneTrack = timelineData?.tracks?.find((t: any) => t.track_type === 'composition' || t.track_id === 'video_scenes');
    if (sceneTrack?.items?.length) {
      const last = sceneTrack.items[sceneTrack.items.length - 1];
      return last.end_frame || (last.start_frame + (last.duration_frames || 0));
    }
    return 980;
  }, [timelineBuildReport, timelineData]);

  const totalDurationSeconds = useMemo(() => {
    if (timelineBuildReport?.counts?.duration_seconds) return timelineBuildReport.counts.duration_seconds;
    return totalFrames / fps;
  }, [timelineBuildReport, totalFrames, fps]);

  const aspect = useMemo(() => {
    return timelineBuildReport?.aspect || timelineData?.aspect || '16:9';
  }, [timelineBuildReport, timelineData]);

  // Derived Scenes
  const scenesList: TimelineSceneItem[] = useMemo(() => {
    const sceneTrack = timelineData?.tracks?.find((t: any) => t.track_type === 'composition' || t.track_id === 'video_scenes');
    if (!sceneTrack?.items?.length) return [];
    return sceneTrack.items.map((it: any, idx: number) => {
      const start = it.start_frame !== undefined ? it.start_frame : 0;
      const end = it.end_frame !== undefined ? it.end_frame : (start + (it.duration_frames || 0));
      return {
        item_id: it.item_id || `scene_clip_${idx + 1}`,
        scene_id: it.scene_id || `scene_${idx + 1}`,
        start_frame: start,
        end_frame: end,
        duration_frames: end - start,
        source_start_seconds: it.source_start_seconds ?? (start / fps),
        source_end_seconds: it.source_end_seconds ?? (end / fps),
        narration_start_frame: it.narration_start_frame,
        narration_end_frame: it.narration_end_frame,
        narration_start_seconds: it.narration_start_seconds,
        narration_end_seconds: it.narration_end_seconds,
        pattern: it.pattern,
        camera: it.camera,
        descriptor_refs: it.descriptor_refs,
        composition_ref: it.composition_ref,
        layers: it.layers,
        transition_out: it.transition_out
      };
    });
  }, [timelineData, fps]);

  // Active Scene based on playhead
  const activeScene = useMemo(() => {
    if (!scenesList.length) return null;
    const found = scenesList.find(s => currentFrame >= s.start_frame && currentFrame < s.end_frame);
    return found || scenesList[scenesList.length - 1];
  }, [scenesList, currentFrame]);

  // Currently selected scene details
  const selectedScene = useMemo(() => {
    if (!selectedSceneId && scenesList.length > 0) return scenesList[0];
    return scenesList.find(s => s.scene_id === selectedSceneId || s.item_id === selectedSceneId) || activeScene || scenesList[0];
  }, [scenesList, selectedSceneId, activeScene]);

  // Motion Plan scene data corresponding to active scene
  const activeMotionScene = useMemo(() => {
    if (!motionPlan?.scenes || !activeScene) return null;
    const sceneNum = parseInt(activeScene.scene_id.replace(/\D/g, ''), 10);
    return motionPlan.scenes.find((s: any) => s.id === sceneNum) || null;
  }, [motionPlan, activeScene]);

  // Active kinetic typography text at current playhead frame
  const activeKineticText = useMemo(() => {
    if (!activeMotionScene?.texts?.length || !activeScene) return null;
    const sceneLocalSec = (currentFrame - activeScene.start_frame) / fps;
    const found = activeMotionScene.texts.find((t: any) => {
      const enter = t.at ?? t.enter_s ?? 0;
      const exit = t.until ?? (activeScene.duration_frames / fps);
      return sceneLocalSec >= enter && sceneLocalSec <= exit;
    });
    return found || activeMotionScene.texts[0];
  }, [activeMotionScene, activeScene, currentFrame, fps]);

  // Active graphic overlay at current frame
  const activeGraphic = useMemo(() => {
    if (!activeMotionScene?.graphics?.length || !activeScene) return null;
    const sceneLocalSec = (currentFrame - activeScene.start_frame) / fps;
    return activeMotionScene.graphics.find((g: any) => {
      const start = g.start ?? 0;
      const end = g.end ?? (activeScene.duration_frames / fps);
      return sceneLocalSec >= start && sceneLocalSec <= end;
    }) || activeMotionScene.graphics[0];
  }, [activeMotionScene, activeScene, currentFrame, fps]);

  // Check for timing conflicts or gaps
  const timelineConflicts = useMemo(() => {
    const conflicts: { type: 'gap' | 'overlap'; startFrame: number; endFrame: number; message: string }[] = [];
    for (let i = 0; i < scenesList.length - 1; i++) {
      const curr = scenesList[i];
      const next = scenesList[i + 1];
      if (curr.end_frame < next.start_frame) {
        conflicts.push({
          type: 'gap',
          startFrame: curr.end_frame,
          endFrame: next.start_frame,
          message: `Uncovered gap: ${next.start_frame - curr.end_frame} frames (${formatSeconds((next.start_frame - curr.end_frame) / fps)}) between ${curr.scene_id} and ${next.scene_id}`
        });
      } else if (curr.end_frame > next.start_frame) {
        conflicts.push({
          type: 'overlap',
          startFrame: next.start_frame,
          endFrame: curr.end_frame,
          message: `Scene overlap: ${curr.end_frame - next.start_frame} frames collision between ${curr.scene_id} and ${next.scene_id}`
        });
      }
    }
    return conflicts;
  }, [scenesList, fps]);

  // Playback Control Loop
  useEffect(() => {
    if (!isPlaying) {
      if (audioRef.current && !audioRef.current.paused) {
        audioRef.current.pause();
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      return;
    }

    if (audioRef.current) {
      const expectedAudioTime = currentFrame / fps;
      if (Math.abs(audioRef.current.currentTime - expectedAudioTime) > 0.15) {
        audioRef.current.currentTime = expectedAudioTime;
      }
      audioRef.current.play().catch(() => {});
    }

    let lastTime = performance.now();
    const frameDuration = 1000 / fps;

    const tick = (now: number) => {
      const delta = now - lastTime;
      if (delta >= frameDuration) {
        setCurrentFrame((prev) => {
          if (prev >= totalFrames - 1) {
            setIsPlaying(false);
            return 0;
          }
          return prev + 1;
        });
        lastTime = now - (delta % frameDuration);
      }
      animationFrameRef.current = requestAnimationFrame(tick);
    };

    animationFrameRef.current = requestAnimationFrame(tick);

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [isPlaying, fps, totalFrames]);

  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying(p => !p);
      } else if (e.code === 'ArrowLeft' || e.key.toLowerCase() === 'j') {
        e.preventDefault();
        setIsPlaying(false);
        setCurrentFrame(prev => Math.max(0, prev - (e.shiftKey ? 15 : 1)));
      } else if (e.code === 'ArrowRight' || e.key.toLowerCase() === 'l') {
        e.preventDefault();
        setIsPlaying(false);
        setCurrentFrame(prev => Math.min(totalFrames - 1, prev + (e.shiftKey ? 15 : 1)));
      } else if (e.code === 'Home') {
        e.preventDefault();
        setCurrentFrame(0);
      } else if (e.code === 'End') {
        e.preventDefault();
        setCurrentFrame(totalFrames - 1);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [totalFrames]);

  // Scrubbing on Timeline
  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const progress = Math.max(0, Math.min(1, clickX / rect.width));
    const targetFrame = Math.round(progress * (totalFrames - 1));
    setCurrentFrame(targetFrame);
    if (audioRef.current) {
      audioRef.current.currentTime = targetFrame / fps;
    }
  };

  // Zoom Pixel Width Computation
  const timelinePixelWidth = useMemo(() => {
    const baseWidth = 1100;
    return Math.max(baseWidth, baseWidth * zoomLevel);
  }, [zoomLevel]);

  const frameToPx = useCallback((frame: number) => {
    if (totalFrames <= 0) return 0;
    return (frame / totalFrames) * timelinePixelWidth;
  }, [totalFrames, timelinePixelWidth]);

  // Dynamic Ruler Interval
  const rulerTicks = useMemo(() => {
    const pxPerSec = timelinePixelWidth / Math.max(1, totalDurationSeconds);
    let stepSec = 5;
    if (pxPerSec > 220) stepSec = 0.5;
    else if (pxPerSec > 110) stepSec = 1;
    else if (pxPerSec > 55) stepSec = 2;
    else stepSec = 5;

    const ticks: { sec: number; frame: number; leftPx: number }[] = [];
    for (let s = 0; s <= totalDurationSeconds + 0.1; s += stepSec) {
      const frame = Math.round(s * fps);
      ticks.push({ sec: Number(s.toFixed(2)), frame, leftPx: frameToPx(frame) });
    }
    return ticks;
  }, [timelinePixelWidth, totalDurationSeconds, fps, frameToPx]);

  // Copy helper
  const handleCopyJson = (content: any, label: string) => {
    navigator.clipboard.writeText(JSON.stringify(content, null, 2));
    setCopiedArtifact(label);
    setTimeout(() => setCopiedArtifact(null), 2500);
  };

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
        activeKineticText={activeKineticText}
        activeGraphic={activeGraphic}
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
        segmentationScenes={segmentationScenes}
        motionPlan={motionPlan}
      />

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
