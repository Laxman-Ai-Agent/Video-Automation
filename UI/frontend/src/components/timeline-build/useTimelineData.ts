import { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  fetchTimelineBuildData, 
  fetchTimelineJson, 
  fetchTimelineWaveform, 
  fetchTimelineStills,
  fetchMotionData, 
  fetchSceneSegmentation 
} from '../../services/api';
import type { StillsResponse } from './timelineStills';

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

export function useTimelineData(projectId: string, currentFrame: number, selectedSceneId: string | null) {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [timelineBuildReport, setTimelineBuildReport] = useState<any | null>(null);
  const [timelineData, setTimelineData] = useState<any | null>(null);
  const [waveformPeaks, setWaveformPeaks] = useState<number[]>([]);
  const [motionPlan, setMotionPlan] = useState<any | null>(null);
  const [segmentationScenes, setSegmentationScenes] = useState<any[]>([]);
  const [stills, setStills] = useState<StillsResponse>({ current: false, exists: false, samples: [] });

  const fps = 30;

  const loadTimelineDatasets = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);

    try {
      const [buildRes, tlRes, wfRes, motionRes, segRes, stillsRes] = await Promise.all([
        fetchTimelineBuildData(projectId),
        fetchTimelineJson(projectId),
        fetchTimelineWaveform(projectId),
        fetchMotionData(projectId),
        fetchSceneSegmentation(projectId),
        fetchTimelineStills(projectId)
      ]);

      if (buildRes.ok) setTimelineBuildReport(buildRes.data);
      if (tlRes.ok) setTimelineData(tlRes.data);
      if (wfRes.ok && Array.isArray(wfRes.data?.peaks)) setWaveformPeaks(wfRes.data.peaks);
      if (motionRes.ok && motionRes.data?.plan) setMotionPlan(motionRes.data.plan);
      if (segRes.ok && Array.isArray(segRes.data?.scenes)) setSegmentationScenes(segRes.data.scenes);
      if (stillsRes.ok) setStills(stillsRes.data as StillsResponse);

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

  const activeScene = useMemo(() => {
    if (!scenesList.length) return null;
    const found = scenesList.find(s => currentFrame >= s.start_frame && currentFrame < s.end_frame);
    return found || scenesList[scenesList.length - 1];
  }, [scenesList, currentFrame]);

  const selectedScene = useMemo(() => {
    if (!selectedSceneId && scenesList.length > 0) return scenesList[0];
    return scenesList.find(s => s.scene_id === selectedSceneId || s.item_id === selectedSceneId) || activeScene || scenesList[0];
  }, [scenesList, selectedSceneId, activeScene]);

  const activeMotionScene = useMemo(() => {
    if (!motionPlan?.scenes || !activeScene) return null;
    const sceneNum = parseInt(activeScene.scene_id.replace(/\D/g, ''), 10);
    return motionPlan.scenes.find((s: any) => s.id === sceneNum) || null;
  }, [motionPlan, activeScene]);

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

  const activeGraphic = useMemo(() => {
    if (!activeMotionScene?.graphics?.length || !activeScene) return null;
    const sceneLocalSec = (currentFrame - activeScene.start_frame) / fps;
    return activeMotionScene.graphics.find((g: any) => {
      const start = g.start ?? 0;
      const end = g.end ?? (activeScene.duration_frames / fps);
      return sceneLocalSec >= start && sceneLocalSec <= end;
    }) || activeMotionScene.graphics[0];
  }, [activeMotionScene, activeScene, currentFrame, fps]);

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

  return {
    loading,
    error,
    timelineBuildReport,
    timelineData,
    waveformPeaks,
    motionPlan,
    segmentationScenes,
    stills,
    fps,
    totalFrames,
    totalDurationSeconds,
    aspect,
    scenesList,
    activeScene,
    selectedScene,
    activeKineticText,
    activeGraphic,
    timelineConflicts
  };
}
