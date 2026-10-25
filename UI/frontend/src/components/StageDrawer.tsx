import React, { useState, useEffect, useMemo } from 'react';
import { 
  FileAudio,
  Scissors,
  Compass,
  Film,
  Sparkles,
  Layers,
  CheckCircle2,
  Cpu,
  Info,
  FileText,
  Terminal
} from 'lucide-react';
import { StageConfig, StageState, StageStatus } from '../types/pipeline';
import { 
  fetchTimelineApprovalState, 
  decideTimelineApproval, 
  fetchRenderVideoState,
  fetchSceneSegmentation,
  fetchAudioAnalysis,
  fetchVisualPlanning,
  fetchMotionPlanning,
  runLlmReview,
  runStage,
  fetchStageSubtasks,
  StageSubtasks
} from '../services/api';
import { StageDrawerHeader } from './stage-views/StageDrawerHeader';
import { StageRightNavBar } from './stage-views/StageRightNavBar';
import { StageContentRouter } from './stage-views/StageContentRouter';
import styles from './StageDrawer.module.css';

interface StageDrawerProps {
  config: StageConfig;
  state?: StageState;
  projectId?: string;
  isFullPage?: boolean;
  onClose: () => void;
  onRunStage?: (stageId: string) => void;
  onStopStage?: (stageId: string) => void;
  onRetryStage?: (stageId: string) => void;
  onOpenAudioAnalysis?: () => void;
  isPipelineRunning?: boolean;
}

export const StageDrawer: React.FC<StageDrawerProps> = ({
  config,
  state,
  projectId,
  isFullPage = false,
  onClose,
  onRunStage,
  onStopStage,
  onRetryStage,
  onOpenAudioAnalysis: _onOpenAudioAnalysis,
  isPipelineRunning = false
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'scenes' | 'subtasks' | 'agent' | 'artifacts' | 'logs' | 'about'>('subtasks');
  const [sceneData, setSceneData] = useState<any | null>(null);
  const [sceneLoading, setSceneLoading] = useState<boolean>(false);
  const [sceneSearch, setSceneSearch] = useState<string>('');
  const [expandedScenes, setExpandedScenes] = useState<Record<string, boolean>>({});
  const [timelineApproval, setTimelineApproval] = useState<any | null>(null);
  const [renderVideo, setRenderVideo] = useState<any | null>(null);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [llmReviewLoading, setLlmReviewLoading] = useState<boolean>(false);
  const [llmReviewMessage, setLlmReviewMessage] = useState<string | null>(null);
  const [visualPlanData, setVisualPlanData] = useState<any | null>(null);
  const [visualPlanLoading, setVisualPlanLoading] = useState<boolean>(false);
  const [motionPlanData, setMotionPlanData] = useState<any | null>(null);
  const [motionPlanLoading, setMotionPlanLoading] = useState<boolean>(false);
  const [expandedMotionScenes, setExpandedMotionScenes] = useState<Record<string, boolean>>({});
  const [showRawMotionJson, setShowRawMotionJson] = useState<Record<string, boolean>>({});
  const [copiedMotionSceneId, setCopiedMotionSceneId] = useState<string | null>(null);
  const [copiedAllMotion, setCopiedAllMotion] = useState<boolean>(false);
  const [rightNavCollapsed, setRightNavCollapsed] = useState<boolean>(false);

  const handleRunLlmReview = async () => {
    if (!projectId) return;
    setLlmReviewLoading(true);
    setLlmReviewMessage('Running LLM Review & Vocabulary Standardization...');
    try {
      const res = await runLlmReview(projectId);
      if (res.ok && res.data) {
        setSceneData({
          source: 'scene_segmentation.json',
          scenes: res.data.scenes || [],
          raw: res.data
        });

        try {
          if (onRunStage) {
            onRunStage('planning');
            setLlmReviewMessage(`LLM Review Complete (${res.corrections_count ?? 0} corrections). Auto-starting Visual Planning...`);
          } else {
            await runStage(projectId, 'planning');
            setLlmReviewMessage(`LLM Review Complete (${res.corrections_count ?? 0} corrections). Auto-starting Visual Planning...`);
          }
        } catch (autoErr: any) {
          console.warn('Auto-start Visual Planning note:', autoErr);
          setLlmReviewMessage(`LLM Review Complete: ${res.corrections_count ?? 0} vocabulary corrections applied. Run Stage button for Visual Planning is now activated.`);
        }
      } else {
        const segRes = await fetchSceneSegmentation(projectId);
        if (segRes.ok && segRes.data?.scenes) {
          setSceneData({
            source: 'scene_segmentation.json',
            scenes: segRes.data.scenes,
            raw: segRes.data
          });
        }
        setLlmReviewMessage('LLM Review completed successfully. Run Stage button for Visual Planning is now activated.');
      }
      setTimeout(() => setLlmReviewMessage(null), 4000);
    } catch (err: any) {
      alert(`LLM Review failed: ${err.message}`);
      setLlmReviewMessage(null);
    } finally {
      setLlmReviewLoading(false);
    }
  };

  // Live timer for elapsed duration
  const [elapsedSec, setElapsedSec] = useState<number>(0);
  const [nowTs, setNowTs] = useState<number>(Date.now());

  const status: StageStatus = state?.status || 'waiting';
  const isRunning = status === 'running';
  const isRetrying = status === 'retrying' || status === 'recovering';
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';
  const isBlocked = status === 'blocked';
  const isCancelled = status === 'cancelled';

  useEffect(() => {
    if (!isRunning && !isRetrying) {
      if (state?.durationMs) {
        setElapsedSec(state.durationMs / 1000);
      }
      return;
    }

    const start = state?.startedAt ? new Date(state.startedAt).getTime() : Date.now();
    const tick = () => {
      const current = Date.now();
      setNowTs(current);
      setElapsedSec(Math.max(0, (current - start) / 1000));
    };

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [isRunning, isRetrying, state?.startedAt, state?.durationMs]);

  const lastActiveTs = state?.lastActivityAt 
    ? new Date(state.lastActivityAt).getTime() 
    : (state?.startedAt ? new Date(state.startedAt).getTime() : null);
  const isStaleProgress = isRunning && lastActiveTs !== null && (nowTs - lastActiveTs > 30000);

  // Sub-stages recording
  const [realSub, setRealSub] = useState<StageSubtasks | null>(null);
  useEffect(() => {
    if (!projectId) return;
    let alive = true;
    const load = () => fetchStageSubtasks(projectId, config.id).then((d) => { if (alive) setRealSub(d); });
    load();
    const t = setInterval(load, isRunning || realSub?.llm_checks_running ? 3000 : 10000);
    return () => { alive = false; clearInterval(t); };
  }, [projectId, config.id, isRunning, status, realSub?.llm_checks_running]);
  const subSteps = realSub?.steps || [];
  const subDone = subSteps.filter((s) => s.status === 'completed' || s.status === 'passed').length;

  useEffect(() => {
    setActiveTab('subtasks');
  }, [config.id]);

  useEffect(() => {
    if (!projectId) return;

    if (config.id === 'segmentation') {
      setSceneLoading(true);
      fetchSceneSegmentation(projectId).then(async (res) => {
        if (res.ok && res.data?.scenes && res.data.scenes.length > 0) {
          setSceneData({
            source: 'scene_segmentation.json',
            scenes: res.data.scenes,
            raw: res.data
          });
          const firstId = res.data.scenes[0].scene_id || '0';
          setExpandedScenes({ [firstId]: true });
        } else {
          const audioRes = await fetchAudioAnalysis(projectId);
          if (audioRes.ok && audioRes.data?.utterances && audioRes.data.utterances.length > 0) {
            const fallbackScenes = audioRes.data.utterances.map((u: any, idx: number) => ({
              scene_id: u.utterance_id || `utt_${idx}`,
              scene_index: idx + 1,
              start_time: u.start_seconds || 0,
              end_time: u.end_seconds || 0,
              transcript: u.llm_transcript || u.text,
              llm_transcript: u.llm_transcript || u.text,
              whisper_transcript: u.whisper_transcript || null,
              semantic_beat: u.llm_transcript || u.text,
              is_source_utterance: true
            }));
            setSceneData({
              source: 'audio_analysis.json',
              scenes: fallbackScenes,
              isFallback: true
            });
            setExpandedScenes({ [fallbackScenes[0].scene_id]: true });
          } else {
            setSceneData(null);
          }
        }
        setSceneLoading(false);
      });
    } else if (config.id === 'planning') {
      setVisualPlanLoading(true);
      fetchVisualPlanning(projectId).then((res) => {
        if (res.ok && res.data) {
          setVisualPlanData(res.data);
        } else {
          setVisualPlanData(null);
        }
        setVisualPlanLoading(false);
      });
    } else if (config.id === 'motion_plan') {
      setMotionPlanLoading(true);
      fetchMotionPlanning(projectId).then((res) => {
        if (res.ok && res.data) {
          setMotionPlanData(res.data);
          const firstScene = res.data.scenes?.[0]?.scene_id || 'scene_01';
          setExpandedMotionScenes({ [firstScene]: true });
        } else {
          setMotionPlanData(null);
        }
        setMotionPlanLoading(false);
      });
    } else if (config.id === 'approval') {
      fetchTimelineApprovalState(projectId).then((data) => {
        if (data) setTimelineApproval(data);
      });
    } else if (config.id === 'render') {
      fetchRenderVideoState(projectId).then((data) => {
        if (data) setRenderVideo(data);
      });
    }
  }, [projectId, config.id]);

  const toggleScene = (id: string) => {
    setExpandedScenes((prev) => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const visualScenesList: any[] = visualPlanData?.scenes || [];
  const motionScenesList: any[] = motionPlanData?.scenes || [];
  const filteredMotionScenes = useMemo(() => {
    if (!sceneSearch.trim()) return motionScenesList;
    const q = sceneSearch.toLowerCase().trim();
    return motionScenesList.filter((s: any) => 
      s.scene_id?.toLowerCase().includes(q) ||
      s.motion_intent?.purpose?.toLowerCase().includes(q) ||
      s.motion_intent?.attention_goal?.toLowerCase().includes(q) ||
      s.motion_intent?.mood?.toLowerCase().includes(q) ||
      s.motion_intent?.intensity?.toLowerCase().includes(q) ||
      s.visual_scene_data?.narration?.text?.toLowerCase().includes(q) ||
      s.visual_scene_data?.narration?.text_en?.toLowerCase().includes(q) ||
      s.segmentation_data?.llm_transcript?.toLowerCase().includes(q) ||
      s.motion_plan_scene?.pattern?.toLowerCase().includes(q) ||
      s.motion_plan_scene?.texts?.some((t: any) => t.preset?.toLowerCase().includes(q) || t.text?.toLowerCase().includes(q)) ||
      s.motion_plan_scene?.graphics?.some((g: any) => g.preset?.toLowerCase().includes(q) || g.why?.toLowerCase().includes(q)) ||
      s.elements?.some((el: any) => el.registry_id?.toLowerCase().includes(q) || el.element_id?.toLowerCase().includes(q)) ||
      s.sequence?.some((seq: any) => seq.preset?.toLowerCase().includes(q) || seq.target?.toLowerCase().includes(q))
    );
  }, [motionScenesList, sceneSearch]);

  const toggleMotionScene = (id: string) => {
    setExpandedMotionScenes((prev) => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const toggleRawMotionJson = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setShowRawMotionJson((prev) => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const handleCopyMotionSceneJson = (scene: any, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const jsonStr = JSON.stringify(scene, null, 2);
      navigator.clipboard.writeText(jsonStr);
      const scId = scene.scene_id || String(scene.plan_scene_id);
      setCopiedMotionSceneId(scId);
      setTimeout(() => setCopiedMotionSceneId(null), 2000);
    } catch (err) {
      console.error('Failed to copy motion scene JSON:', err);
    }
  };

  const handleCopyAllMotionPlanJson = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!motionPlanData) return;
    try {
      const jsonStr = JSON.stringify(motionPlanData, null, 2);
      navigator.clipboard.writeText(jsonStr);
      setCopiedAllMotion(true);
      setTimeout(() => setCopiedAllMotion(false), 2000);
    } catch (err) {
      console.error('Failed to copy all motion plan JSON:', err);
    }
  };

  const scenesList = sceneData?.scenes || [];
  const hasAnyMissingLlm = scenesList.length > 0 && scenesList.some((s: any) => !s.llm_transcript);
  const filteredScenes = useMemo(() => {
    if (!sceneSearch.trim()) return scenesList;
    const q = sceneSearch.toLowerCase().trim();
    return scenesList.filter((s: any) => 
      s.llm_transcript?.toLowerCase().includes(q) ||
      s.whisper_transcript?.toLowerCase().includes(q) ||
      s.transcript?.toLowerCase().includes(q) ||
      s.semantic_beat?.toLowerCase().includes(q) ||
      s.scene_objective?.toLowerCase().includes(q)
    );
  }, [scenesList, sceneSearch]);

  const handleApproveTimeline = async (decision: 'approved' | 'changes_requested') => {
    if (!projectId) return;
    try {
      setActionLoading(true);
      setActionMessage(null);
      const reviewId = timelineApproval?.review_id || `rev-${Date.now()}`;
      const fingerprint = timelineApproval?.expected_fingerprint || 'fp-authoritative';
      await decideTimelineApproval(projectId, decision, reviewId, fingerprint);
      const updated = await fetchTimelineApprovalState(projectId);
      if (updated) setTimelineApproval(updated);

      if (decision === 'approved') {
        try {
          if (onRunStage) {
            onRunStage('render');
            setActionMessage('Timeline approved! Auto-starting Render Video...');
          } else {
            await runStage(projectId, 'render');
            setActionMessage('Timeline approved! Auto-starting Render Video...');
          }
        } catch (autoErr: any) {
          console.warn('Auto-start Render Video note:', autoErr);
          setActionMessage('Timeline approved! Run Stage button for Render Video is now activated.');
        }
      } else {
        setActionMessage('Changes requested.');
      }
    } catch (err: any) {
      setActionMessage(`Error: ${err?.message || 'Failed to submit decision'}`);
    } finally {
      setActionLoading(false);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const overallProgressValue = (() => {
    if (realSub?.overall_progress !== undefined && realSub.overall_progress !== null) {
      return realSub.overall_progress;
    }
    if (subSteps.length > 0) {
      const verifiedCount = subSteps.filter((s) => s.llm_check?.current && s.llm_check.verdict === 'confirms').length;
      const hasErrors = subSteps.some(
        (s) =>
          ['failed', 'error', 'blocked'].includes((s.status || '').toLowerCase()) ||
          s.llm_check?.verdict === 'rejects' ||
          s.llm_check?.verdict === 'error'
      );
      const avgDeterministic =
        subSteps.reduce((acc, s) => acc + (s.completion_percent ?? (s.status === 'completed' ? 100 : 0)), 0) /
        subSteps.length;
      if (hasErrors) {
        return Math.min(Math.round(avgDeterministic * 0.75), 80);
      }
      if (status === 'completed' && verifiedCount === subSteps.length && avgDeterministic >= 99.9) {
        return 100;
      }
      return Math.round(avgDeterministic * 0.8 + ((verifiedCount / subSteps.length) * 100) * 0.2);
    }
    if (state?.percentage !== undefined && state?.percentage !== null) {
      return state.percentage;
    }
    return status === 'completed' ? 100 : null;
  })();

  const percentage = overallProgressValue !== null ? `${overallProgressValue}%` : '—';

  const availableTabs = useMemo(() => [
    ...(config.id === 'analyzer' ? [{
      id: 'scenes',
      label: 'Audio & Transcript',
      icon: <FileAudio size={18} strokeWidth={activeTab === 'scenes' ? 2.3 : 1.8} />
    }] : []),
    ...(config.id === 'segmentation' ? [{
      id: 'scenes',
      label: scenesList.length > 0 ? `Scenes (${scenesList.length})` : 'Scenes & Script',
      icon: <Scissors size={18} strokeWidth={activeTab === 'scenes' ? 2.3 : 1.8} />
    }] : []),
    ...(config.id === 'planning' ? [{
      id: 'scenes',
      label: visualScenesList.length > 0 ? `Visual Scenes (${visualScenesList.length})` : 'Visual Scenes & Plan',
      icon: <Compass size={18} strokeWidth={activeTab === 'scenes' ? 2.3 : 1.8} />
    }] : []),
    ...(config.id === 'assets' ? [{
      id: 'scenes',
      label: 'Collected Media',
      icon: <Film size={18} strokeWidth={activeTab === 'scenes' ? 2.3 : 1.8} />
    }] : []),
    ...(config.id === 'motion_plan' ? [{
      id: 'scenes',
      label: motionScenesList.length > 0 ? `Motion Scenes (${motionScenesList.length})` : 'Motion Scenes & Plan',
      icon: <Sparkles size={18} strokeWidth={activeTab === 'scenes' ? 2.3 : 1.8} />
    }] : []),
    ...(config.id === 'timeline' ? [{
      id: 'scenes',
      label: 'Visual Timeline',
      icon: <Film size={18} strokeWidth={activeTab === 'scenes' ? 2.3 : 1.8} />
    }] : []),
    { id: 'overview', label: 'Overview', icon: <Layers size={18} strokeWidth={activeTab === 'overview' ? 2.3 : 1.8} /> },
    { id: 'subtasks', label: `Subtasks (${subSteps.length})`, icon: <CheckCircle2 size={18} strokeWidth={activeTab === 'subtasks' ? 2.3 : 1.8} /> },
    { id: 'agent', label: 'Agent', icon: <Cpu size={18} strokeWidth={activeTab === 'agent' ? 2.3 : 1.8} /> },
    { id: 'about', label: 'About', icon: <Info size={18} strokeWidth={activeTab === 'about' ? 2.3 : 1.8} /> },
    { id: 'artifacts', label: 'Artifacts', icon: <FileText size={18} strokeWidth={activeTab === 'artifacts' ? 2.3 : 1.8} /> },
    { id: 'logs', label: 'Live Logs', icon: <Terminal size={18} strokeWidth={activeTab === 'logs' ? 2.3 : 1.8} /> }
  ], [config.id, scenesList.length, visualScenesList.length, motionScenesList.length, subSteps.length, activeTab]);

  return (
    <aside 
      data-testid={isFullPage ? "stage-detail-full-view" : "stage-detail-drawer"}
      className={isFullPage ? styles.fullView : styles.drawerView}
    >
      {/* CENTER CONTENT CONTAINER */}
      <div 
        data-testid="stage-drawer-center-content"
        className={styles.centerContent}
        style={{
          height: isFullPage ? '100%' : undefined,
        }}
      >
        {/* Header Card */}
        <div data-testid="stage-drawer-header-card">
          <StageDrawerHeader
            config={config}
            state={state}
            isFullPage={isFullPage}
            onClose={onClose}
            onRunStage={onRunStage}
            onStopStage={onStopStage}
            onRetryStage={onRetryStage}
            isPipelineRunning={isPipelineRunning}
            isRunning={isRunning}
            isRetrying={isRetrying}
            isFailed={isFailed}
            isBlocked={isBlocked}
            isCancelled={isCancelled}
            isCompleted={isCompleted}
            scenesList={scenesList}
            hasAnyMissingLlm={hasAnyMissingLlm}
            handleRunLlmReview={handleRunLlmReview}
            llmReviewLoading={llmReviewLoading}
            actionMessage={actionMessage}
            percentage={percentage}
          />
        </div>

        {/* Main Tab Views Routed via StageContentRouter */}
        <StageContentRouter
          activeTab={activeTab}
          config={config}
          state={state}
          projectId={projectId}
          isFullPage={isFullPage}
          isPipelineRunning={isPipelineRunning}
          isRunning={isRunning}
          isRetrying={isRetrying}
          isCompleted={isCompleted}
          isFailed={isFailed}
          isBlocked={isBlocked}
          isStaleProgress={isStaleProgress}
          elapsedSec={elapsedSec}
          subSteps={subSteps}
          subDone={subDone}
          realSub={realSub}
          setRealSub={setRealSub}
          sceneData={sceneData}
          scenesList={scenesList}
          filteredScenes={filteredScenes}
          sceneSearch={sceneSearch}
          setSceneSearch={setSceneSearch}
          sceneLoading={sceneLoading}
          expandedScenes={expandedScenes}
          toggleScene={toggleScene}
          llmReviewLoading={llmReviewLoading}
          llmReviewMessage={llmReviewMessage}
          hasAnyMissingLlm={hasAnyMissingLlm}
          handleRunLlmReview={handleRunLlmReview}
          visualPlanData={visualPlanData}
          visualPlanLoading={visualPlanLoading}
          motionPlanData={motionPlanData}
          motionScenesList={motionScenesList}
          filteredMotionScenes={filteredMotionScenes}
          motionPlanLoading={motionPlanLoading}
          expandedMotionScenes={expandedMotionScenes}
          toggleMotionScene={toggleMotionScene}
          showRawMotionJson={showRawMotionJson}
          toggleRawMotionJson={toggleRawMotionJson}
          copiedMotionSceneId={copiedMotionSceneId}
          copiedAllMotion={copiedAllMotion}
          handleCopyMotionSceneJson={handleCopyMotionSceneJson}
          handleCopyAllMotionPlanJson={handleCopyAllMotionPlanJson}
          timelineApproval={timelineApproval}
          actionMessage={actionMessage}
          actionLoading={actionLoading}
          renderVideo={renderVideo}
          onRunStage={onRunStage}
          onRetryStage={onRetryStage}
          handleApproveTimeline={handleApproveTimeline}
          setActiveTab={setActiveTab}
        />
      </div>

      {/* FULL-HEIGHT RIGHT-SIDE NAVIGATION BAR */}
      <StageRightNavBar
        isFullPage={isFullPage}
        rightNavCollapsed={rightNavCollapsed}
        setRightNavCollapsed={setRightNavCollapsed}
        availableTabs={availableTabs}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        subStepsCount={subSteps.length}
      />
    </aside>
  );
};
