import React, { useState, useEffect, useMemo } from 'react';
import { 
  X, 
  ArrowLeft,
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  FileText, 
  Cpu, 
  ShieldCheck, 
  RotateCcw, 
  ExternalLink,
  Terminal,
  Activity,
  Layers,
  Check,
  Video,
  Film,
  Sparkles,
  XCircle,
  FileAudio,
  AlertCircle,
  ChevronRight,
  ChevronDown,
  Scissors,
  Play,
  Square,
  Search,
  RefreshCw,
  Mic,
  Copy,
  Code,
  Compass,
  Eye,
  Palette,
  Info
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
  runStageStepChecks,
  StageSubtasks
} from '../services/api';
import { VisualPlanningView } from './VisualPlanningView';
import { AssetsView } from './AssetsView';
import { TimelineBuildVisualView } from './TimelineBuildVisualView';
import { AgentAboutTab } from './AgentAboutTab';

// Shared scene-table styling (segmentation / planning / motion plan)
const sceneTableStyle: React.CSSProperties = {
  width: '100%', tableLayout: 'fixed', borderCollapse: 'separate', borderSpacing: 0,
  border: '1px solid var(--border-card)', borderRadius: '10px', overflow: 'hidden',
  backgroundColor: 'var(--bg-elevated)'
};
const sceneThStyle: React.CSSProperties = {
  padding: '10px 14px', textAlign: 'left', fontSize: '11px', fontWeight: 700, letterSpacing: '0.05em',
  textTransform: 'uppercase', color: 'var(--text-muted)', backgroundColor: 'var(--bg-card)',
  borderBottom: '1px solid var(--border-card)'
};
const sceneTdStyle: React.CSSProperties = {
  padding: '12px 14px', verticalAlign: 'middle', borderBottom: '1px solid var(--border-subtle)', overflow: 'hidden'
};
const sceneRowStyle = (expanded: boolean): React.CSSProperties => ({
  cursor: 'pointer', userSelect: 'none', backgroundColor: expanded ? 'var(--bg-card-hover)' : 'transparent'
});

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

function formatElapsedSeconds(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
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
  onOpenAudioAnalysis,
  isPipelineRunning = false
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'scenes' | 'subtasks' | 'agent' | 'artifacts' | 'logs' | 'about'>(
    config.id === 'segmentation' || config.id === 'planning' || config.id === 'motion_plan' || config.id === 'timeline' ? 'scenes' : 'overview'
  );
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

        // Auto-start next stage (Visual Planning) upon successful LLM verification
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

  // Stale progress detection (>30s without update while running)
  const lastActiveTs = state?.lastActivityAt 
    ? new Date(state.lastActivityAt).getTime() 
    : (state?.startedAt ? new Date(state.startedAt).getTime() : null);
  const isStaleProgress = isRunning && lastActiveTs !== null && (nowTs - lastActiveTs > 30000);

  // Sub-stages: the steps the stage really recorded in its report (never estimated from the overall percentage); refreshed while it runs
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
    setActiveTab(config.id === 'segmentation' || config.id === 'planning' || config.id === 'assets' || config.id === 'motion_plan' || config.id === 'timeline' ? 'scenes' : 'overview');
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
          // Fallback to audio_analysis.json utterances if segmentation not run yet
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

  // Keyboard navigation: Escape closes drawer/full-page
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const percentage = state?.percentage !== undefined && state?.percentage !== null 
    ? `${state.percentage}%` 
    : (status === 'completed' ? '100%' : '—');

  return (
    <aside 
      data-testid={isFullPage ? "stage-detail-full-view" : "stage-detail-drawer"}
      style={isFullPage ? {
        width: '100%',
        minHeight: 'calc(100vh - 180px)',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: 'var(--font-sans)',
        color: 'var(--text-primary)'
      } : {
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: '520px',
        maxWidth: '100vw',
        backgroundColor: 'var(--bg-card)',
        borderLeft: '1px solid var(--border-card)',
        boxShadow: 'var(--shadow-drawer)',
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
        animation: 'slideInRight 0.22s ease-out'
      }}
    >
      {/* Header */}
      <div style={{
        padding: isFullPage ? '16px 24px' : '20px 24px',
        border: isFullPage ? '1px solid var(--border-card)' : undefined,
        borderBottom: isFullPage ? undefined : '1px solid var(--border-subtle)',
        borderRadius: isFullPage ? '10px' : undefined,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '14px',
        backgroundColor: 'var(--bg-elevated)',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
              <span style={{
                fontSize: '11px',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                color: 'var(--accent-cyan)',
                backgroundColor: 'var(--status-running-bg)',
                padding: '2px 8px',
                borderRadius: 'var(--radius-sm)'
              }}>
                STAGE {String(config.order).padStart(2, '0')}
              </span>

              {/* Authoritative Badge in Drawer Header */}
              {isCompleted && (
                <span style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  fontWeight: 700,
                  color: 'var(--status-completed)',
                  backgroundColor: 'var(--status-completed-bg)',
                  border: '1px solid var(--status-completed-border)',
                  padding: '2px 6px',
                  borderRadius: '3px'
                }}>
                  <CheckCircle2 size={12} />
                  COMPLETED
                </span>
              )}
              {isRunning && (
                <span style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  fontWeight: 700,
                  color: 'var(--status-running)',
                  backgroundColor: 'var(--status-running-bg)',
                  border: '1px solid var(--status-running-border)',
                  padding: '2px 6px',
                  borderRadius: '3px'
                }}>
                  <Activity size={12} className="animate-spin" />
                  ACTIVE
                </span>
              )}
              {isRetrying && (
                <span style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  fontWeight: 700,
                  color: 'var(--status-retrying)',
                  backgroundColor: 'var(--status-retrying-bg)',
                  border: '1px solid var(--status-retrying-border)',
                  padding: '2px 6px',
                  borderRadius: '3px'
                }}>
                  <RotateCcw size={12} className="animate-spin" />
                  RETRYING
                </span>
              )}
              {isFailed && (
                <span style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  fontWeight: 700,
                  color: 'var(--status-failed)',
                  backgroundColor: 'var(--status-failed-bg)',
                  border: '1px solid var(--status-failed-border)',
                  padding: '2px 6px',
                  borderRadius: '3px'
                }}>
                  <XCircle size={12} />
                  FAILED
                </span>
              )}
              {isBlocked && (
                <span style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  fontWeight: 700,
                  color: 'var(--status-blocked)',
                  backgroundColor: 'var(--status-blocked-bg)',
                  border: '1px solid var(--status-blocked-border)',
                  padding: '2px 6px',
                  borderRadius: '3px'
                }}>
                  <AlertTriangle size={12} />
                  BLOCKED
                </span>
              )}
              {isCancelled && (
                <span style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  fontWeight: 700,
                  color: 'var(--status-cancelled)',
                  backgroundColor: 'var(--status-cancelled-bg)',
                  border: '1px solid var(--status-cancelled-border)',
                  padding: '2px 6px',
                  borderRadius: '3px'
                }}>
                  <XCircle size={12} />
                  CANCELLED
                </span>
              )}
              {!isCompleted && !isRunning && !isRetrying && !isFailed && !isBlocked && !isCancelled && (
                <span style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'var(--text-muted)',
                  backgroundColor: 'var(--status-waiting-bg)',
                  border: '1px solid var(--status-waiting-border)',
                  padding: '2px 6px',
                  borderRadius: '3px'
                }}>
                  READY
                </span>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px', flexWrap: 'wrap' }}>
              <h2 style={{ fontSize: isFullPage ? '20px' : '18px', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.3px', margin: 0 }}>
                {config.label}
              </h2>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                <strong style={{ color: 'var(--accent-cyan)' }}>{config.agentName}</strong>
              </span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {/* Action Message feedback */}
          {actionMessage && (
            <span style={{
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              color: actionMessage.startsWith('Error') ? 'var(--status-failed)' : 'var(--accent-cyan)',
              backgroundColor: 'var(--bg-elevated)',
              padding: '4px 8px',
              borderRadius: '4px',
              border: '1px solid var(--border-subtle)',
              maxWidth: '220px',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {actionMessage}
            </span>
          )}

          {/* Stop Button while Running */}
          {(isRunning || isRetrying) && (
            <button
              onClick={() => {
                if (onStopStage) onStopStage(config.id);
                else if (onRetryStage) onRetryStage('cancel');
              }}
              data-testid="stage-drawer-stop-btn"
              title={`Stop ${config.label} Execution`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                borderRadius: '6px',
                color: '#EF4444',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#EF4444';
                e.currentTarget.style.color = '#FFFFFF';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.15)';
                e.currentTarget.style.color = '#EF4444';
              }}
            >
              <Square size={13} fill="currentColor" />
              <span>Stop Stage</span>
            </button>
          )}

          {/* Retry Button on Failure */}
          {isFailed && (
            <button
              onClick={() => {
                if (onRunStage) onRunStage(config.id);
                else if (onRetryStage) onRetryStage(config.id);
              }}
              data-testid="stage-drawer-retry-btn"
              title={`Retry ${config.label}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                backgroundColor: 'rgba(255, 77, 79, 0.15)',
                border: '1px solid rgba(255, 77, 79, 0.4)',
                borderRadius: '6px',
                color: 'var(--status-failed)',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--status-failed)';
                e.currentTarget.style.color = '#FFFFFF';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255, 77, 79, 0.15)';
                e.currentTarget.style.color = 'var(--status-failed)';
              }}
            >
              <RotateCcw size={13} />
              <span>Retry Stage</span>
            </button>
          )}

          {/* Run Button when Ready / Waiting / Cancelled */}
          {!isRunning && !isRetrying && !isFailed && !isCompleted && (
            <button
              onClick={() => {
                if (!isBlocked && !isRunning) {
                  if (onRunStage) onRunStage(config.id);
                  else if (onRetryStage) onRetryStage(config.id);
                }
              }}
              disabled={isBlocked || isRunning}
              data-testid="stage-drawer-run-btn"
              title={isBlocked ? (state?.blockers?.[0] || 'Prerequisites required') : (isRunning ? 'Stage is running' : `Run ${config.label}`)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                backgroundColor: isBlocked || isRunning ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 216, 245, 0.15)',
                border: `1px solid ${isBlocked || isRunning ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 216, 245, 0.35)'}`,
                borderRadius: '6px',
                color: isBlocked || isRunning ? 'var(--text-muted)' : 'var(--accent-cyan)',
                fontSize: '12px',
                fontWeight: 700,
                cursor: isBlocked || isRunning ? 'not-allowed' : 'pointer',
                opacity: isBlocked || isRunning ? 0.6 : 1,
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                if (!isBlocked && !isRunning) {
                  e.currentTarget.style.backgroundColor = 'var(--accent-cyan)';
                  e.currentTarget.style.color = '#000000';
                }
              }}
              onMouseLeave={(e) => {
                if (!isBlocked && !isRunning) {
                  e.currentTarget.style.backgroundColor = 'rgba(0, 216, 245, 0.15)';
                  e.currentTarget.style.color = 'var(--accent-cyan)';
                }
              }}
            >
              <Play size={13} fill="currentColor" />
              <span>Run Stage</span>
            </button>
          )}

          {/* Rerun Button when Completed */}
          {isCompleted && (
            <button
              onClick={() => {
                if (!isPipelineRunning) {
                  if (onRunStage) onRunStage(config.id);
                  else if (onRetryStage) onRetryStage(config.id);
                }
              }}
              disabled={isPipelineRunning}
              data-testid="stage-drawer-rerun-btn"
              title={`Rerun ${config.label}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 10px',
                backgroundColor: 'transparent',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '5px',
                color: 'var(--text-muted)',
                fontSize: '11px',
                fontWeight: 600,
                cursor: isPipelineRunning ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                if (!isPipelineRunning) {
                  e.currentTarget.style.borderColor = 'var(--accent-cyan)';
                  e.currentTarget.style.color = 'var(--accent-cyan)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isPipelineRunning) {
                  e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.15)';
                  e.currentTarget.style.color = 'var(--text-muted)';
                }
              }}
            >
              <RotateCcw size={11} />
              <span>Rerun Stage</span>
            </button>
          )}

          <div style={{
            fontSize: isFullPage ? '32px' : '28px',
            fontWeight: 800,
            fontFamily: 'var(--font-sans)',
            color: isCompleted ? 'var(--status-completed)' : (isFailed ? 'var(--status-failed)' : 'var(--accent-cyan)')
          }}>
            {percentage}
          </div>

          <button
            onClick={onClose}
            aria-label="Close stage details"
            data-testid="stage-drawer-close-btn"
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '8px',
              borderRadius: 'var(--radius-full)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'var(--bg-card)'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Tabs Bar */}
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        flexWrap: 'wrap',
        padding: isFullPage ? '0 0 14px' : '10px 20px',
        order: -1,
        position: 'sticky',
        top: 0,
        zIndex: 5,
        backgroundColor: 'var(--bg-app)',
        gap: '8px'
      }}>
        {[
          ...(config.id === 'segmentation' ? [{
            id: 'scenes',
            label: scenesList.length > 0 ? `Scenes (${scenesList.length})` : 'Scenes & Script',
            icon: <Scissors size={14} />
          }] : []),
          ...(config.id === 'planning' ? [{
            id: 'scenes',
            label: visualScenesList.length > 0 ? `Visual Scenes (${visualScenesList.length})` : 'Visual Scenes & Plan',
            icon: <Compass size={14} />
          }] : []),
          ...(config.id === 'assets' ? [{
            id: 'scenes',
            label: 'Collected Media',
            icon: <Film size={14} />
          }] : []),
          ...(config.id === 'motion_plan' ? [{
            id: 'scenes',
            label: motionScenesList.length > 0 ? `Motion Scenes (${motionScenesList.length})` : 'Motion Scenes & Plan',
            icon: <Sparkles size={14} />
          }] : []),
          ...(config.id === 'timeline' ? [{
            id: 'scenes',
            label: 'Frame-Accurate Visual Timeline',
            icon: <Film size={14} />
          }] : []),
          { id: 'overview', label: 'Overview', icon: <Layers size={14} /> },
          { id: 'subtasks', label: `Subtasks (${subSteps.length})`, icon: <CheckCircle2 size={14} /> },
          { id: 'agent', label: 'Agent', icon: <Cpu size={14} /> },
          { id: 'about', label: 'About', icon: <Info size={14} /> },
          { id: 'artifacts', label: 'Artifacts', icon: <FileText size={14} /> },
          { id: 'logs', label: 'Live Logs', icon: <Terminal size={14} /> }
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            data-testid={`stage-drawer-tab-${tab.id}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              height: '30px',
              padding: '0 14px',
              borderRadius: '6px',
              backgroundColor: activeTab === tab.id ? '#1890FF' : 'rgba(24, 144, 255, 0.12)',
              border: activeTab === tab.id ? '1px solid #1890FF' : '1px solid rgba(24, 144, 255, 0.35)',
              color: activeTab === tab.id ? '#FFFFFF' : '#38BDF8',
              fontSize: '12px',
              fontWeight: 600,
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
        <button
          onClick={onClose}
          data-testid="stage-drawer-back-btn"
          title="Back to Pipeline Flow (Esc)"
          style={{
            position: 'absolute', left: isFullPage ? 0 : '20px', top: isFullPage ? '15px' : '50%', transform: 'translateY(-50%)',
            display: 'inline-flex', alignItems: 'center', gap: '6px', height: '30px', padding: '0 14px',
            borderRadius: '6px', fontSize: '12px', fontWeight: 600, whiteSpace: 'nowrap', cursor: 'pointer',
            color: '#38BDF8', backgroundColor: 'rgba(24, 144, 255, 0.12)', border: '1px solid rgba(24, 144, 255, 0.35)'
          }}
        >
          <ArrowLeft size={13} />
          <span>Back to Pipeline</span>
        </button>
        {config.id === 'segmentation' && !hasAnyMissingLlm && scenesList.length > 0 && (
          <div
            data-testid="llm-verification-passed-banner"
            style={{ position: 'absolute', right: isFullPage ? 0 : '20px', top: isFullPage ? '15px' : '50%', transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: '5px', height: '26px', padding: '0 12px',
              borderRadius: '9999px', fontSize: '11px', fontWeight: 700, color: '#6EE7B7',
              backgroundColor: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.4)'
            }}>
              <CheckCircle2 size={13} /> Verified with LLM
            </span>
            <button
              onClick={handleRunLlmReview}
              disabled={llmReviewLoading}
              data-testid="rerun-llm-verification-btn"
              title="Re-run LLM Review"
              style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '26px', height: '26px',
                borderRadius: '50%', color: '#D8B4FE', backgroundColor: 'rgba(168, 85, 247, 0.15)',
                border: '1px solid rgba(168, 85, 247, 0.35)', cursor: llmReviewLoading ? 'not-allowed' : 'pointer',
                opacity: llmReviewLoading ? 0.7 : 1
              }}
            >
              {llmReviewLoading ? <RefreshCw size={12} className="animate-spin" /> : <Sparkles size={12} />}
            </button>
          </div>
        )}
      </div>

      {/* Content Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: isFullPage ? '20px 0 0' : '20px 24px' }}>
        {/* Scenes & Script Tab (Dedicated Scene Segmentation View matching exact UI) */}
        {activeTab === 'scenes' && config.id === 'segmentation' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }} data-testid="scene-segmentation-tab-content">
            {/* Summary Metadata Bar */}
            <div style={{
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-card)',
              borderRadius: '8px',
              padding: '14px 18px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(0, 216, 245, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--accent-cyan)'
                }}>
                  <Scissors size={16} />
                </div>
                <div>
                  <div style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    Scene Segmentation & Script Breakdown
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Method: <strong style={{ color: 'var(--accent-cyan)' }}>{sceneData?.raw?.segmentation_method || (sceneData?.isFallback ? 'source_utterances_preview' : 'llm_semantic_grouping')}</strong>
                    {sceneData?.raw?.language && <> • Language: <strong>{sceneData.raw.language.toUpperCase()}</strong></>}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Total Scenes</span>
                  <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                    {scenesList.length}
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Duration</span>
                  <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    {sceneData?.raw?.audio_duration_seconds 
                      ? `${sceneData.raw.audio_duration_seconds.toFixed(1)}s` 
                      : (scenesList.length > 0 && scenesList[scenesList.length - 1].end_time 
                          ? `${Number(scenesList[scenesList.length - 1].end_time).toFixed(1)}s` 
                          : '—')}
                  </div>
                </div>

                <span style={{
                  fontSize: '10.5px',
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 700,
                  backgroundColor: sceneData?.isFallback ? 'rgba(245, 158, 11, 0.15)' : 'rgba(0, 216, 245, 0.12)',
                  color: sceneData?.isFallback ? '#FBBF24' : 'var(--accent-cyan)',
                  padding: '3px 8px',
                  borderRadius: '4px',
                  border: sceneData?.isFallback ? '1px solid rgba(245, 158, 11, 0.3)' : '1px solid rgba(0, 216, 245, 0.25)'
                }}>
                  {sceneData?.source || 'scene_segmentation.json'}
                </span>
              </div>
            </div>

            {/* Fallback Notice if using audio_analysis.json utterances */}
            {sceneData?.isFallback && (
              <div style={{
                backgroundColor: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid rgba(245, 158, 11, 0.25)',
                borderRadius: '8px',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#FBBF24', fontSize: '12.5px' }}>
                  <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                  <span>
                    Displaying audio speech utterances as preview. The Scene Segmentation stage can be triggered to generate LLM semantic cut boundaries.
                  </span>
                </div>
                {onRetryStage && (
                  <button
                    onClick={() => onRetryStage(config.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 12px',
                      backgroundColor: 'rgba(0, 216, 245, 0.15)',
                      border: '1px solid rgba(0, 216, 245, 0.35)',
                      borderRadius: '4px',
                      color: 'var(--accent-cyan)',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      flexShrink: 0
                    }}
                  >
                    <Play size={12} fill="currentColor" />
                    <span>Run Scene Segmentation</span>
                  </button>
                )}
              </div>
            )}

            {/* LLM Review In-Flight / Success Message Toast */}
            {llmReviewMessage && (
              <div
                data-testid="llm-review-status-toast"
                style={{
                  backgroundColor: 'rgba(124, 58, 237, 0.15)',
                  border: '1px solid rgba(168, 85, 247, 0.4)',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  color: '#D8B4FE',
                  fontSize: '13px',
                  fontWeight: 600
                }}
              >
                {llmReviewLoading ? (
                  <RefreshCw size={16} className="animate-spin" color="#C084FC" />
                ) : (
                  <CheckCircle2 size={16} color="#34D399" />
                )}
                <span>{llmReviewMessage}</span>
              </div>
            )}

            {/* Mandatory LLM Verification Gate Banner */}
            {hasAnyMissingLlm && (
              <div 
                data-testid="llm-verification-gate-banner"
                style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.35)',
                  borderRadius: '8px',
                  padding: '14px 18px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '12px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
                  <AlertCircle size={20} color="#EF4444" style={{ flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: '#FCA5A5' }}>
                      ⚠️ LLM Verification Required Before Next Step
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Narration must be verified by LLM before Visual Planning and image generation can proceed. English technical terms must be standardized in English script and Telugu grammar verified.
                    </div>
                  </div>
                </div>
                <button
                  onClick={handleRunLlmReview}
                  disabled={llmReviewLoading}
                  data-testid="run-all-llm-verification-btn"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
                    backgroundColor: '#7C3AED',
                    border: '1px solid #A78BFA',
                    borderRadius: '6px',
                    color: '#FFFFFF',
                    fontSize: '12.5px',
                    fontWeight: 700,
                    cursor: llmReviewLoading ? 'not-allowed' : 'pointer',
                    opacity: llmReviewLoading ? 0.7 : 1,
                    flexShrink: 0,
                    boxShadow: '0 2px 8px rgba(124, 58, 237, 0.4)'
                  }}
                >
                  {llmReviewLoading ? <RefreshCw size={13} className="animate-spin" /> : <Sparkles size={13} />}
                  <span>{llmReviewLoading ? 'Verifying with LLM...' : 'Run LLM Verification'}</span>
                </button>
              </div>
            )}

            {/* Search Filter Input (matching reference screenshot) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ position: 'relative', flex: 1 }}>
                <input
                  type="text"
                  placeholder="Filter words or utterances..."
                  value={sceneSearch}
                  onChange={(e) => setSceneSearch(e.target.value)}
                  data-testid="scenes-filter-input"
                  style={{
                    width: '100%',
                    padding: '9px 14px 9px 36px',
                    backgroundColor: 'var(--bg-elevated)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '6px',
                    color: 'var(--text-primary)', 
                    fontSize: '13px',
                    outline: 'none',
                    boxSizing: 'border-box'
                  }}
                />
                <Search size={15} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              </div>
              {sceneSearch && (
                <button
                  onClick={() => setSceneSearch('')}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    fontSize: '12px',
                    padding: '6px 10px'
                  }}
                >
                  Clear
                </button>
              )}
            </div>

            {/* Loading State */}
            {sceneLoading && (
              <div style={{
                padding: '40px',
                textAlign: 'center',
                backgroundColor: 'var(--bg-elevated)',
                borderRadius: '8px',
                color: 'var(--text-muted)',
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '10px'
              }}>
                <RefreshCw size={16} className="animate-spin" color="var(--accent-cyan)" />
                <span>Loading scene segmentation details...</span>
              </div>
            )}

            {/* Scene List Cards */}
            {!sceneLoading && filteredScenes.length > 0 && (
              <table data-testid="segmentation-scenes-list" style={sceneTableStyle}>
                <colgroup>
                  <col style={{ width: '44px' }} /><col style={{ width: '72px' }} /><col style={{ width: '120px' }} />
                  <col /><col style={{ width: '170px' }} /><col style={{ width: '90px' }} />
                </colgroup>
                <thead>
                  <tr>
                    <th style={sceneThStyle}></th><th style={sceneThStyle}>#</th><th style={sceneThStyle}>Source</th>
                    <th style={sceneThStyle}>Narration</th><th style={sceneThStyle}>Time</th><th style={sceneThStyle}>Duration</th>
                  </tr>
                </thead>
                <tbody>
                {filteredScenes.map((s: any, idx: number) => {
                  const sceneId = s.scene_id || `scene_${idx + 1}`;
                  const isExpanded = !!expandedScenes[sceneId];
                  const sceneNum = String(s.scene_index !== undefined ? s.scene_index : idx + 1).padStart(2, '0');
                  const duration = (s.end_time !== undefined && s.start_time !== undefined)
                    ? (Number(s.end_time) - Number(s.start_time)).toFixed(1)
                    : null;

                  return (
                    <React.Fragment key={sceneId}>
                      {/* Scene Table Row */}
                      <tr
                        onClick={() => toggleScene(sceneId)}
                        data-testid={`scene-header-${idx}`}
                        style={sceneRowStyle(isExpanded)}
                      >
                        <td style={{ ...sceneTdStyle, paddingRight: 0, color: 'var(--text-muted)', borderLeft: `3px solid ${s.llm_transcript ? '#10B981' : '#6B7280'}` }}>
                          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </td>
                        <td style={sceneTdStyle}>
                          <span style={{
                            fontSize: '11px',
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 700,
                            color: 'var(--accent-cyan)',
                            backgroundColor: 'rgba(0, 216, 245, 0.1)',
                            padding: '2px 7px',
                            borderRadius: '4px',
                            flexShrink: 0
                          }}>
                            #{sceneNum}
                          </span>
                        </td>
                        <td style={sceneTdStyle}>
                          {s.llm_transcript ? (
                            <span 
                              data-testid={`scene-${sceneNum}-badge-llm`}
                              style={{
                                fontSize: '10px',
                                fontFamily: 'var(--font-mono)',
                                fontWeight: 700,
                                color: '#A7F3D0',
                                backgroundColor: 'rgba(16, 185, 129, 0.16)',
                                border: '1px solid rgba(16, 185, 129, 0.35)',
                                padding: '1px 6px',
                                borderRadius: '3px',
                                flexShrink: 0
                              }}
                            >
                              LLM FINAL
                            </span>
                          ) : (
                            <span 
                              data-testid={`scene-${sceneNum}-badge-raw`}
                              style={{
                                fontSize: '10px',
                                fontFamily: 'var(--font-mono)',
                                fontWeight: 700,
                                color: '#9CA3AF',
                                backgroundColor: 'rgba(107, 114, 128, 0.15)',
                                border: '1px solid rgba(107, 114, 128, 0.35)',
                                padding: '1px 6px',
                                borderRadius: '3px',
                                flexShrink: 0
                              }}
                            >
                              NO LLM
                            </span>
                          )}
                        </td>
                        <td style={sceneTdStyle}>
                          <span style={{
                            display: 'block',
                            fontSize: '13.5px',
                            fontWeight: 600,
                            color: 'var(--text-primary)', 
                            whiteSpace: isExpanded ? 'normal' : 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            lineHeight: 1.4
                          }}>
                            {s.llm_transcript || s.transcript || s.semantic_beat || 'Scene Unit'}
                          </span>
                        </td>
                        <td style={sceneTdStyle}>
                          <span style={{
                            fontSize: '11.5px',
                            fontFamily: 'var(--font-mono)',
                            color: 'var(--text-muted)',
                            whiteSpace: 'nowrap'
                          }}>
                            {s.start_time !== undefined ? `${Number(s.start_time).toFixed(2)}s` : '0.00s'} – {s.end_time !== undefined ? `${Number(s.end_time).toFixed(2)}s` : '—'}
                          </span>
                        </td>
                        <td style={sceneTdStyle}>
                          {duration && (
                            <span style={{
                              fontSize: '11px',
                              color: 'var(--accent-blue)',
                              fontWeight: 700,
                              backgroundColor: 'rgba(24, 144, 255, 0.12)',
                              padding: '2px 8px',
                              borderRadius: '12px',
                              fontFamily: 'var(--font-mono)'
                            }}>
                              {duration}s
                            </span>
                          )}
                        </td>
                      </tr>

                      {/* Expanded Details Pane */}
                      {isExpanded && (
                        <tr><td colSpan={6} style={{ padding: 0, borderBottom: '1px solid var(--border-subtle)' }}>
                        <div style={{ padding: '16px 20px', backgroundColor: 'var(--bg-card)', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                          {/* Dual Comparative Transcripts: Whisper Original ASR vs LLM-Processed Script */}
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                              <span style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                Scene Transcripts: Whisper Original vs LLM-Processed Output
                              </span>
                              {s.llm_transcript && (
                                <span style={{
                                  fontSize: '10.5px',
                                  color: '#A7F3D0',
                                  backgroundColor: 'rgba(16, 185, 129, 0.12)',
                                  border: '1px solid rgba(16, 185, 129, 0.3)',
                                  padding: '1px 8px',
                                  borderRadius: '12px',
                                  fontWeight: 600
                                }}>
                                  Telugu Script Preserved • English Technical Loanwords Standardized
                                </span>
                              )}
                            </div>

                            <div style={{
                              display: 'grid',
                              gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr',
                              gap: '14px'
                            }}>
                              {/* Panel 1: Whisper Original Output (Raw ASR) */}
                              <div 
                                data-testid={`scene-${sceneNum}-whisper-transcript`}
                                style={{
                                  backgroundColor: 'var(--bg-elevated)',
                                  padding: '14px 16px',
                                  borderRadius: '8px',
                                  border: '1px solid rgba(0, 216, 245, 0.25)',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  gap: '8px'
                                }}
                              >
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '6px' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <Mic size={14} color="var(--accent-cyan)" />
                                    <span style={{ fontSize: '11px', fontWeight: 800, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                      Whisper Original Output (ASR)
                                    </span>
                                  </div>
                                  <span style={{
                                    fontSize: '10px',
                                    fontWeight: 700,
                                    backgroundColor: 'rgba(0, 216, 245, 0.12)',
                                    color: 'var(--accent-cyan)',
                                    padding: '2px 8px',
                                    borderRadius: '12px',
                                    fontFamily: 'var(--font-mono)'
                                  }}>
                                    faster-whisper
                                  </span>
                                </div>
                                <div style={{
                                  fontSize: '14px',
                                  color: 'var(--text-primary)',
                                  lineHeight: 1.6,
                                  minHeight: '44px',
                                  fontFamily: 'system-ui, -apple-system, sans-serif'
                                }}>
                                  {s.whisper_transcript || (s.isFallback ? 'Whisper original transcript preserved separately' : 'Whisper original transcript preserved separately')}
                                </div>
                                <div style={{ fontSize: '11px', color: 'var(--text-muted)', borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '6px', fontStyle: 'italic' }}>
                                  Raw speech-to-text transcript before LLM vocabulary & loanword processing
                                </div>
                              </div>

                              {/* Panel 2: LLM-Processed Output (Telugu + Standard English Words) */}
                              <div 
                                data-testid={`scene-${sceneNum}-llm-transcript`}
                                style={{
                                  backgroundColor: 'var(--bg-elevated)',
                                  padding: '14px 16px',
                                  borderRadius: '8px',
                                  border: (s.llm_transcript || s.transcript) ? '1px solid rgba(168, 85, 247, 0.35)' : '1px dashed rgba(255, 255, 255, 0.15)',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  gap: '8px'
                                }}
                              >
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '6px' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <Sparkles size={14} color={(s.llm_transcript || s.transcript) ? '#C084FC' : 'var(--text-muted)'} />
                                    <span style={{
                                      fontSize: '11px',
                                      fontWeight: 800,
                                      color: (s.llm_transcript || s.transcript) ? '#C084FC' : 'var(--text-muted)',
                                      textTransform: 'uppercase',
                                      letterSpacing: '0.04em'
                                    }}>
                                      LLM-Processed Output (Corrected)
                                    </span>
                                  </div>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    {(s.llm_transcript || s.transcript) ? (
                                      <span style={{
                                        fontSize: '10px',
                                        fontWeight: 700,
                                        backgroundColor: 'rgba(168, 85, 247, 0.16)',
                                        color: '#D8B4FE',
                                        padding: '2px 8px',
                                        borderRadius: '12px',
                                        fontFamily: 'var(--font-mono)'
                                      }}>
                                        Claude LLM Verified
                                      </span>
                                    ) : (
                                      <span style={{
                                        fontSize: '10px',
                                        fontWeight: 600,
                                        backgroundColor: 'rgba(239, 68, 68, 0.15)',
                                        color: '#F87171',
                                        padding: '2px 8px',
                                        borderRadius: '12px',
                                        border: '1px solid rgba(239, 68, 68, 0.3)'
                                      }}>
                                        Not Run Yet
                                      </span>
                                    )}

                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleRunLlmReview();
                                      }}
                                      disabled={llmReviewLoading}
                                      data-testid={`scene-${sceneNum}-run-llm-btn`}
                                      style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '5px',
                                        padding: '3px 10px',
                                        backgroundColor: (s.llm_transcript || s.transcript) ? 'rgba(168, 85, 247, 0.2)' : '#7C3AED',
                                        border: (s.llm_transcript || s.transcript) ? '1px solid rgba(168, 85, 247, 0.4)' : '1px solid #A78BFA',
                                        borderRadius: '4px',
                                        color: (s.llm_transcript || s.transcript) ? '#7C3AED' : '#FFFFFF',
                                        fontSize: '11px',
                                        fontWeight: 600,
                                        cursor: llmReviewLoading ? 'not-allowed' : 'pointer',
                                        opacity: llmReviewLoading ? 0.7 : 1,
                                        transition: 'all 0.15s ease'
                                      }}
                                    >
                                      {llmReviewLoading ? (
                                        <RefreshCw size={11} className="animate-spin" />
                                      ) : (
                                        <Play size={10} fill="currentColor" />
                                      )}
                                      <span>
                                        {llmReviewLoading ? 'Running...' : ((s.llm_transcript || s.transcript) ? 'Re-run LLM Review' : 'Run LLM Review')}
                                      </span>
                                    </button>
                                  </div>
                                </div>
                                <div style={{
                                  fontSize: '14px',
                                  color: (s.llm_transcript || s.transcript) ? 'var(--text-primary)' : 'var(--text-muted)',
                                  lineHeight: 1.6,
                                  minHeight: '44px',
                                  fontFamily: 'system-ui, -apple-system, sans-serif'
                                }}>
                                  {(s.llm_transcript || s.transcript) ? (
                                    (s.llm_transcript || s.transcript)
                                  ) : (
                                    <span style={{ fontStyle: 'italic', fontSize: '13px' }}>
                                      LLM review not yet run for this project. Narration uses original Whisper transcript.
                                    </span>
                                  )}
                                </div>
                                <div style={{
                                  fontSize: '11px',
                                  color: s.llm_transcript ? '#6EE7B7' : '#FCA5A5',
                                  borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                                  paddingTop: '6px',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  flexWrap: 'wrap',
                                  gap: '6px'
                                }}>
                                  <span>
                                    {s.llm_transcript
                                      ? '✓ Authoritative Final Narration for Visual Planning • Loanwords Standardized'
                                      : '⚠️ LLM verification pending — next step is blocked until run'}
                                  </span>
                                  <span style={{ color: 'var(--text-muted)', fontSize: '10.5px', fontStyle: 'italic' }}>
                                    {s.llm_transcript ? 'Telugu script preserved' : 'Click Run LLM Review to verify'}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Semantic Beat & Scene Objective */}
                          <div style={{ display: 'grid', gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr', gap: '12px' }}>
                            {s.semantic_beat && (
                              <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '12px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                                <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase' }}>
                                  Semantic Beat (Story Point)
                                </span>
                                <p style={{ fontSize: '13px', color: 'var(--text-primary)', margin: '4px 0 0 0', lineHeight: 1.4 }}>
                                  {s.semantic_beat}
                                </p>
                              </div>
                            )}
                            {s.scene_objective && (
                              <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '12px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                                <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-blue)', textTransform: 'uppercase' }}>
                                  Scene Objective
                                </span>
                                <p style={{ fontSize: '13px', color: 'var(--text-primary)', margin: '4px 0 0 0', lineHeight: 1.4 }}>
                                  {s.scene_objective}
                                </p>
                              </div>
                            )}
                          </div>

                          {/* Cut Boundary Transition Details */}
                          {s.boundary_after && (
                            <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '12px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                                <Scissors size={13} color="var(--accent-cyan)" />
                                <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                                  Cut Boundary Transition
                                </span>
                                {s.boundary_after.type && (
                                  <span style={{
                                    fontSize: '10px',
                                    fontFamily: 'var(--font-mono)',
                                    backgroundColor: 'rgba(0, 216, 245, 0.12)',
                                    color: 'var(--accent-cyan)',
                                    padding: '1px 6px',
                                    borderRadius: '3px',
                                    fontWeight: 700
                                  }}>
                                    {s.boundary_after.type}
                                  </span>
                                )}
                              </div>
                              <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                                {s.boundary_after.reason || 'Semantic cut point transition.'}
                              </div>
                              {s.boundary_after.evidence && s.boundary_after.evidence.length > 0 && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
                                  <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>Evidence:</span>
                                  {s.boundary_after.evidence.map((ev: string, evIdx: number) => (
                                    <span key={evIdx} style={{
                                      fontSize: '10.5px',
                                      backgroundColor: 'rgba(255, 255, 255, 0.06)',
                                      color: 'var(--text-secondary)',
                                      padding: '1px 6px',
                                      borderRadius: '3px',
                                      fontFamily: 'var(--font-mono)'
                                    }}>
                                      {ev}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Timing & Metric Details */}
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '16px',
                            fontSize: '11.5px',
                            color: 'var(--text-muted)',
                            fontFamily: 'var(--font-mono)',
                            flexWrap: 'wrap',
                            paddingTop: '4px'
                          }}>
                            <span>Start: <strong style={{ color: 'var(--text-primary)' }}>{s.start_time !== undefined ? Number(s.start_time).toFixed(2) : '0.00'}s</strong></span>
                            <span>End: <strong style={{ color: 'var(--text-primary)' }}>{s.end_time !== undefined ? Number(s.end_time).toFixed(2) : '0.00'}s</strong></span>
                            <span>Duration: <strong style={{ color: 'var(--accent-cyan)' }}>{duration}s</strong></span>
                            {s.pause_after_seconds !== undefined && (
                              <span>Pause After: <strong style={{ color: 'var(--accent-blue)' }}>{s.pause_after_seconds}s</strong></span>
                            )}
                            {s.source_word_ids && (
                              <span>Words: <strong style={{ color: 'var(--text-primary)' }}>{s.source_word_ids.length}</strong></span>
                            )}
                            {s.timing_source && (
                              <span>Source: <strong>{s.timing_source}</strong></span>
                            )}
                          </div>
                        </div>
                        </td></tr>
                      )}
                    </React.Fragment>
                  );
                })}
                </tbody>
              </table>
            )}

            {/* Empty State */}
            {!sceneLoading && filteredScenes.length === 0 && (
              <div style={{
                padding: '48px 16px',
                textAlign: 'center',
                backgroundColor: 'var(--bg-elevated)',
                borderRadius: '8px',
                border: '1px dashed rgba(255, 255, 255, 0.1)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '12px'
              }}>
                <Scissors size={28} color="var(--text-muted)" />
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {sceneSearch ? 'No matching scenes found' : 'No scenes available'}
                </div>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0, maxWidth: '360px' }}>
                  {sceneSearch ? `Try adjusting your search query "${sceneSearch}"` : 'Run the Scene Segmentation stage to generate semantic scenes and cuts.'}
                </p>
                {sceneSearch && (
                  <button
                    onClick={() => setSceneSearch('')}
                    style={{
                      padding: '6px 14px',
                      backgroundColor: 'var(--bg-elevated)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '4px',
                      fontSize: '12px',
                      cursor: 'pointer'
                    }}
                  >
                    Clear Filter
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Asset Collection: every real photo or clip the Visual Plan asked for, with the file that was collected or why not */}
        {activeTab === 'scenes' && config.id === 'assets' && (
          <AssetsView projectId={projectId} refreshKey={state?.status} />
        )}

        {/* Visual Planning: the media mix chosen at upload against what the plan reached, the count of every kind of element and one row per scene */}
        {activeTab === 'scenes' && config.id === 'planning' && (
          <VisualPlanningView data={visualPlanData} loading={visualPlanLoading} />
        )}

        {/* Motion Scenes & Planning Tab (Dedicated Motion Planning View with Before/After, JSON Copy, & Key Motion Sequence Data) */}
        {activeTab === 'scenes' && config.id === 'motion_plan' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }} data-testid="motion-planning-tab-content">
            {/* Summary Metadata Bar */}
            <div style={{
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-card)',
              borderRadius: '8px',
              padding: '14px 18px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(0, 216, 245, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--accent-cyan)'
                }}>
                  <Sparkles size={16} />
                </div>
                <div>
                  <div style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    Motion Planning & Kinetic Synthesis
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Mode: <strong style={{ color: 'var(--accent-cyan)' }}>{motionPlanData?.project?.mode || 'motion_only'}</strong>
                    {motionPlanData?.project?.aspect_ratio && <> • Aspect: <strong>{motionPlanData.project.aspect_ratio}</strong></>}
                    {motionPlanData?.project?.fps && <> • FPS: <strong>{motionPlanData.project.fps}</strong></>}
                    {motionPlanData?.timing_policy?.pace && <> • Pace: <strong>{motionPlanData.timing_policy.pace}x</strong></>}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Motion Scenes</span>
                  <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                    {motionScenesList.length}
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Timeline Window</span>
                  <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    {motionScenesList.length > 0 && motionScenesList[motionScenesList.length - 1].timing?.end
                      ? `${Number(motionScenesList[motionScenesList.length - 1].timing.end).toFixed(1)}s`
                      : '—'}
                  </div>
                </div>

                <span style={{
                  fontSize: '10.5px',
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 700,
                  backgroundColor: 'rgba(0, 216, 245, 0.12)',
                  color: 'var(--accent-cyan)',
                  padding: '3px 8px',
                  borderRadius: '4px',
                  border: '1px solid rgba(0, 216, 245, 0.25)'
                }}>
                  motion_planning.json
                </span>

                <button
                  onClick={handleCopyAllMotionPlanJson}
                  data-testid="copy-all-motion-plan-json-btn"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 14px',
                    backgroundColor: copiedAllMotion ? 'rgba(16, 185, 129, 0.15)' : 'rgba(0, 216, 245, 0.12)',
                    border: copiedAllMotion ? '1px solid #10B981' : '1px solid rgba(0, 216, 245, 0.35)',
                    borderRadius: '6px',
                    color: copiedAllMotion ? '#10B981' : 'var(--accent-cyan)',
                    fontSize: '11.5px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  {copiedAllMotion ? <Check size={13} color="#10B981" /> : <Copy size={13} />}
                  <span>{copiedAllMotion ? 'Copied Full Motion Plan JSON!' : 'Copy Full Motion Plan JSON'}</span>
                </button>
              </div>
            </div>

            {/* Filter / Search Bar */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-card)',
              borderRadius: '6px',
              padding: '8px 14px'
            }}>
              <Search size={14} color="var(--text-muted)" />
              <input
                type="text"
                placeholder="Search motion scenes by preset, keyword, Telugu narration, mood, or timing..."
                value={sceneSearch}
                onChange={(e) => setSceneSearch(e.target.value)}
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-primary)',
                  fontSize: '13px',
                  outline: 'none'
                }}
              />
              {sceneSearch && (
                <button
                  onClick={() => setSceneSearch('')}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    fontSize: '11px'
                  }}
                >
                  Clear
                </button>
              )}
            </div>

            {/* Loading State */}
            {motionPlanLoading && (
              <div style={{
                padding: '40px',
                textAlign: 'center',
                backgroundColor: 'var(--bg-elevated)',
                borderRadius: '8px',
                border: '1px solid var(--border-card)',
                color: 'var(--text-muted)'
              }}>
                <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px auto', display: 'block', color: 'var(--accent-cyan)' }} />
                <div style={{ fontSize: '13.5px', color: 'var(--text-primary)', fontWeight: 600 }}>Loading Motion Planning Scenes & Animation Timelines...</div>
              </div>
            )}

            {/* Empty State */}
            {!motionPlanLoading && motionScenesList.length === 0 && (
              <div style={{
                padding: '40px',
                textAlign: 'center',
                backgroundColor: 'var(--bg-elevated)',
                borderRadius: '8px',
                border: '1px solid var(--border-card)'
              }}>
                <Sparkles size={32} color="var(--text-muted)" style={{ margin: '0 auto 12px auto', display: 'block' }} />
                <div style={{ fontSize: '14px', color: 'var(--text-primary)', fontWeight: 700, marginBottom: '6px' }}>
                  No Motion Planning Data Available
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '420px', margin: '0 auto 16px auto' }}>
                  Motion Planning has not been executed yet for this project. Run Motion Planning to generate kinetic typography, graphic presets, and action sequences.
                </div>
                {onRunStage && (
                  <button
                    onClick={() => onRunStage('motion_plan')}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 18px',
                      backgroundColor: 'var(--accent-cyan)',
                      color: '#000000',
                      border: 'none',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer'
                    }}
                  >
                    <Play size={13} fill="currentColor" />
                    <span>Run Motion Planning</span>
                  </button>
                )}
              </div>
            )}

            {/* Motion Scene List Cards */}
            {!motionPlanLoading && filteredMotionScenes.length > 0 && (
            <table data-testid="motion-scenes-list" style={sceneTableStyle}>
              <colgroup>
                <col style={{ width: '44px' }} /><col style={{ width: '120px' }} /><col />
                <col style={{ width: '175px' }} /><col style={{ width: '130px' }} /><col style={{ width: '230px' }} /><col style={{ width: '170px' }} />
              </colgroup>
              <thead>
                <tr>
                  <th style={sceneThStyle}></th><th style={sceneThStyle}>Scene</th><th style={sceneThStyle}>Purpose / Narration</th>
                  <th style={sceneThStyle}>Time</th><th style={sceneThStyle}>Frames</th><th style={sceneThStyle}>Pattern / Intensity</th><th style={sceneThStyle}>Actions</th>
                </tr>
              </thead>
              <tbody>
            {filteredMotionScenes.map((s: any, idx: number) => {
              const sceneKey = s.scene_id || s.plan_scene_id || String(idx + 1);
              const isExpanded = !!expandedMotionScenes[sceneKey];
              const isRawJsonOpen = !!showRawMotionJson[sceneKey];
              const sceneNum = String(idx + 1).padStart(2, '0');
              const isCopied = copiedMotionSceneId === sceneKey;

              const t0 = s.timing?.start ?? 0;
              const t1 = s.timing?.end ?? 0;
              const duration = Math.max(0, t1 - t0);
              const startFrame = s.timing?.start_frame ?? 0;
              const endFrame = s.timing?.end_frame ?? 0;
              const gapAfter = s.timing?.gap_after_seconds;

              const teluguNarration = s.visual_scene_data?.narration?.text || s.segmentation_data?.llm_transcript || s.segmentation_data?.transcript || '—';
              const englishNarration = s.visual_scene_data?.narration?.text_en || s.motion_intent?.takeaway || '—';

              const intent = s.motion_intent || {};
              const mpScene = s.motion_plan_scene || {};
              const texts: any[] = mpScene.texts || [];
              const graphics: any[] = mpScene.graphics || [];
              const pattern = mpScene.pattern || 'hero_text';
              const sequence: any[] = s.sequence || [];
              const elements: any[] = s.elements || [];

              return (
                <React.Fragment key={sceneKey}>
                  {/* Scene Table Row (Clickable) */}
                  <tr
                    onClick={() => toggleMotionScene(sceneKey)}
                    data-testid={`motion-scene-card-${sceneNum}`}
                    style={sceneRowStyle(isExpanded)}
                  >
                    <td style={{ ...sceneTdStyle, paddingRight: 0, color: isExpanded ? 'var(--accent-cyan)' : 'var(--text-muted)', borderLeft: `3px solid ${s.segmentation_data?.llm_transcript ? '#10B981' : '#6B7280'}` }}>
                      {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </td>
                    <td style={sceneTdStyle}>
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        backgroundColor: 'rgba(0, 216, 245, 0.1)',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        border: '1px solid rgba(0, 216, 245, 0.25)'
                      }}>
                        <span style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                          SCENE {sceneNum}
                        </span>
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          #{s.plan_scene_id || idx + 1}
                        </span>
                      </div>

                    </td>
                    <td style={sceneTdStyle}>
                      {/* Purpose & Attention Goal Preview */}
                      <div style={{ minWidth: 0 }}>
                        <div style={{
                          fontSize: '13px',
                          fontWeight: 700,
                          color: 'var(--text-primary)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          maxWidth: '480px'
                        }}>
                          <span style={{ color: 'var(--accent-cyan)', textTransform: 'capitalize' }}>{intent.purpose || 'Motion Beat'}:</span> {intent.attention_goal || intent.takeaway || 'Kinetic animation focus'}
                        </div>
                        <div style={{
                          fontSize: '11px',
                          color: 'var(--text-muted)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          maxWidth: '480px'
                        }}>
                          {teluguNarration}
                        </div>
                      </div>
                    </td>
                    <td style={sceneTdStyle}>
                      {/* Timing Badge */}
                      <span style={{
                        whiteSpace: 'nowrap',
                        fontSize: '11px',
                        fontFamily: 'var(--font-mono)',
                        backgroundColor: 'rgba(255, 255, 255, 0.05)',
                        color: 'var(--text-muted)',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        border: '1px solid var(--border-card)'
                      }}>
                        ⏱ {t0.toFixed(1)}s - {t1.toFixed(1)}s ({duration.toFixed(1)}s)
                      </span>
                    </td>
                    <td style={sceneTdStyle}>
                      {/* Frames Badge */}
                      <span style={{
                        whiteSpace: 'nowrap',
                        fontSize: '11px',
                        fontFamily: 'var(--font-mono)',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        color: '#60A5FA',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        border: '1px solid rgba(59, 130, 246, 0.25)'
                      }}>
                        🎞 {startFrame} - {endFrame}f
                      </span>
                    </td>
                    <td style={sceneTdStyle}>
                     <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      {/* Pattern Tag */}
                      <span style={{
                        fontSize: '10.5px',
                        backgroundColor: 'rgba(245, 158, 11, 0.12)',
                        color: '#FBBF24',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        border: '1px solid rgba(245, 158, 11, 0.25)',
                        fontFamily: 'var(--font-mono)'
                      }}>
                        {pattern}
                      </span>

                      {/* Intensity Tag */}
                      {intent.intensity && (
                        <span style={{
                          fontSize: '10.5px',
                          backgroundColor: 'rgba(168, 85, 247, 0.12)',
                          color: '#C084FC',
                          padding: '3px 8px',
                          borderRadius: '4px',
                          border: '1px solid rgba(168, 85, 247, 0.25)',
                          fontFamily: 'var(--font-mono)'
                        }}>
                          ⚡ {intent.intensity}
                        </span>
                      )}

                      {/* Actions Count */}
                      <span style={{
                        fontSize: '10.5px',
                        backgroundColor: 'rgba(16, 185, 129, 0.12)',
                        color: '#34D399',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        border: '1px solid rgba(16, 185, 129, 0.25)',
                        fontFamily: 'var(--font-mono)'
                      }}>
                        ✨ {sequence.length} actions
                      </span>
                     </div>
                    </td>
                    <td style={sceneTdStyle}>
                     <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {/* Copy Scene JSON Button */}
                      <button
                        onClick={(e) => handleCopyMotionSceneJson(s, e)}
                        data-testid={`motion-scene-${sceneNum}-copy-json-btn`}
                        title="Copy complete motion JSON for this scene"
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '5px',
                          padding: '4px 10px',
                          backgroundColor: isCopied ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.06)',
                          border: isCopied ? '1px solid #10B981' : '1px solid rgba(255, 255, 255, 0.15)',
                          borderRadius: '4px',
                          color: isCopied ? '#10B981' : '#E2E8F0',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {isCopied ? (
                          <>
                            <Check size={12} color="#10B981" />
                            <span>Copied JSON!</span>
                          </>
                        ) : (
                          <>
                            <Copy size={12} />
                            <span>Copy JSON</span>
                          </>
                        )}
                      </button>

                      {/* Toggle Raw JSON View Button */}
                      <button
                        onClick={(e) => toggleRawMotionJson(sceneKey, e)}
                        data-testid={`motion-scene-${sceneNum}-toggle-raw-json-btn`}
                        title="Toggle raw JSON view for this motion scene"
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '4px 8px',
                          backgroundColor: isRawJsonOpen ? 'rgba(0, 216, 245, 0.2)' : 'transparent',
                          border: isRawJsonOpen ? '1px solid var(--accent-cyan)' : '1px solid rgba(255, 255, 255, 0.1)',
                          borderRadius: '4px',
                          color: isRawJsonOpen ? 'var(--accent-cyan)' : 'var(--text-muted)',
                          fontSize: '11px',
                          cursor: 'pointer'
                        }}
                      >
                        <Code size={12} />
                        <span>JSON</span>
                      </button>
                     </div>
                    </td>
                  </tr>

                  {/* Expanded Content: BEFORE & AFTER PANEL + LAYOUTS */}
                  {isExpanded && (
                    <tr><td colSpan={7} style={{ padding: 0, borderBottom: '1px solid var(--border-subtle)' }}>
                    <div style={{
                      padding: '18px 20px',
                      borderTop: '1px solid var(--border-card)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '16px',
                      backgroundColor: 'var(--bg-app)'
                    }}>
                      {/* Section Title Banner: Before & After Transformation */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 12px',
                        backgroundColor: 'rgba(255, 255, 255, 0.03)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '6px'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontSize: '13px' }}>🔄</span>
                          <span style={{ fontSize: '12px', fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            Before vs After Scene Transformation
                          </span>
                        </div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          Input Visual Directives & Script ➔ Motion Planning & Kinetic Sequence
                        </span>
                      </div>

                      {/* 2-Column Comparative Grid */}
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr',
                        gap: '14px'
                      }}>
                        {/* COLUMN 1: BEFORE — Input Visual Directives & Script */}
                        <div style={{
                          backgroundColor: 'var(--bg-card)',
                          border: '1px solid var(--border-card)',
                          borderRadius: '8px',
                          padding: '14px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '10px'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <Compass size={13} color="var(--accent-cyan)" />
                              <span style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                BEFORE: Visual Directives & Script
                              </span>
                            </div>
                            <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                              From Visual Planning
                            </span>
                          </div>

                          {/* Telugu Spoken Narration (Preserved) */}
                          <div>
                            <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                              Spoken Narration (Telugu Script Preserved)
                            </div>
                            <div style={{
                              fontSize: '14px',
                              lineHeight: 1.6,
                              color: 'var(--text-primary)',
                              backgroundColor: 'var(--bg-elevated)',
                              padding: '10px 12px',
                              borderRadius: '6px',
                              border: '1px solid var(--border-subtle)',
                              fontFamily: 'system-ui, -apple-system, sans-serif'
                            }}>
                              {teluguNarration}
                            </div>
                          </div>

                          {/* English Translation */}
                          <div>
                            <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                              English Narration (Core Meaning)
                            </div>
                            <div style={{
                              fontSize: '13px',
                              fontStyle: 'italic',
                              lineHeight: 1.5,
                              color: 'var(--text-secondary)',
                              backgroundColor: 'var(--bg-elevated)',
                              padding: '8px 12px',
                              borderRadius: '6px',
                              border: '1px solid var(--border-subtle)'
                            }}>
                              "{englishNarration}"
                            </div>
                          </div>

                          {/* Visual Concept Directives */}
                          {(s.visual_scene_data?.visual_concept?.description || s.visual_scene_data?.scene_objective?.core_meaning) && (
                            <div>
                              <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                                Planned Visual Subject & Concept
                              </div>
                              <div style={{
                                fontSize: '12.5px',
                                color: 'var(--text-primary)',
                                backgroundColor: 'var(--bg-elevated)',
                                padding: '8px 12px',
                                borderRadius: '6px',
                                border: '1px solid var(--border-subtle)',
                                lineHeight: 1.4
                              }}>
                                {s.visual_scene_data?.visual_concept?.description || s.visual_scene_data?.scene_objective?.core_meaning}
                              </div>
                            </div>
                          )}

                          {/* Attention Goal & Hints from Visual Plan */}
                          <div style={{
                            display: 'grid',
                            gridTemplateColumns: '1fr',
                            gap: '8px',
                            backgroundColor: 'rgba(255, 255, 255, 0.02)',
                            padding: '8px 10px',
                            borderRadius: '6px'
                          }}>
                            {intent.hints && intent.hints.length > 0 && (
                              <div>
                                <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Visual Motion Hints:</span>
                                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
                                  {intent.hints.map((h: string, hIdx: number) => (
                                    <span key={hIdx} style={{
                                      fontSize: '10.5px',
                                      backgroundColor: 'rgba(0, 216, 245, 0.1)',
                                      color: 'var(--accent-cyan)',
                                      padding: '1px 6px',
                                      borderRadius: '3px',
                                      fontFamily: 'var(--font-mono)'
                                    }}>
                                      {h}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}

                            <div>
                              <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Audio Window:</span>
                              <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                                {t0.toFixed(2)}s → {t1.toFixed(2)}s ({duration.toFixed(2)}s)
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* COLUMN 2: AFTER — Motion Planning Synthesis */}
                        <div style={{
                          backgroundColor: 'var(--bg-card)',
                          border: '1px solid rgba(0, 216, 245, 0.3)',
                          borderRadius: '8px',
                          padding: '14px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '10px',
                          boxShadow: 'inset 0 0 20px rgba(0, 216, 245, 0.03)'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(0, 216, 245, 0.15)', paddingBottom: '8px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <Sparkles size={13} color="var(--accent-cyan)" />
                              <span style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                AFTER: Motion Planning Synthesis
                              </span>
                            </div>
                            <span style={{
                              fontSize: '10px',
                              fontWeight: 700,
                              backgroundColor: 'rgba(0, 216, 245, 0.15)',
                              color: 'var(--accent-cyan)',
                              padding: '2px 8px',
                              borderRadius: '10px',
                              fontFamily: 'var(--font-mono)'
                            }}>
                              Kinetic Choreography
                            </span>
                          </div>

                          {/* Motion Intent */}
                          <div>
                            <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase', marginBottom: '4px' }}>
                              Motion Intent & Focus
                            </div>
                            <div style={{
                              fontSize: '13px',
                              lineHeight: 1.5,
                              color: 'var(--text-primary)',
                              backgroundColor: 'rgba(0, 216, 245, 0.04)',
                              padding: '10px 12px',
                              borderRadius: '6px',
                              border: '1px solid rgba(0, 216, 245, 0.15)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '4px'
                            }}>
                              <div>
                                <strong style={{ color: 'var(--accent-cyan)' }}>Goal:</strong> {intent.attention_goal || 'Ignite core visual element'}
                              </div>
                              {intent.takeaway && (
                                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                                  <strong style={{ color: 'var(--text-primary)' }}>Takeaway:</strong> {intent.takeaway}
                                </div>
                              )}
                              <div style={{ display: 'flex', gap: '8px', marginTop: '4px', fontSize: '11px' }}>
                                <span style={{ color: 'var(--text-muted)' }}>Mood: <strong style={{ color: 'var(--text-primary)' }}>{intent.mood || 'majestic, awe'}</strong></span>
                                <span style={{ color: 'var(--text-muted)' }}>• Intensity: <strong style={{ color: '#FBBF24' }}>{intent.intensity || 'standard'}</strong></span>
                              </div>
                            </div>
                          </div>

                          {/* Kinetic Graphics */}
                          {graphics.length > 0 && (
                            <div>
                              <div style={{ fontSize: '10.5px', fontWeight: 700, color: '#60A5FA', textTransform: 'uppercase', marginBottom: '4px' }}>
                                Kinetic Graphics & Accents ({graphics.length})
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                {graphics.map((g: any, gIdx: number) => (
                                  <div
                                    key={gIdx}
                                    style={{
                                      backgroundColor: 'var(--bg-elevated)',
                                      padding: '8px 10px',
                                      borderRadius: '6px',
                                      border: '1px solid rgba(59, 130, 246, 0.2)',
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'space-between',
                                      gap: '8px'
                                    }}
                                  >
                                    <div>
                                      <span style={{ fontSize: '12px', fontWeight: 700, color: '#93C5FD', fontFamily: 'var(--font-mono)' }}>
                                        {g.preset}
                                      </span>
                                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '8px' }}>
                                        {g.why || (g.atmosphere ? 'Atmosphere' : 'Placed Graphic')}
                                      </span>
                                    </div>
                                    <div style={{ display: 'flex', gap: '6px', fontSize: '10.5px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                                      <span>Speed: <strong style={{ color: 'var(--text-primary)' }}>{g.speed}x</strong></span>
                                      <span>Start: <strong style={{ color: 'var(--text-primary)' }}>{g.start}s</strong></span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Frame Precision & Timing */}
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            flexWrap: 'wrap',
                            gap: '6px',
                            borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                            paddingTop: '6px'
                          }}>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                              Frames: <strong style={{ color: '#FFFFFF' }}>{startFrame} → {endFrame}f</strong> ({endFrame - startFrame} frames)
                            </span>
                            {gapAfter !== undefined && (
                              <span style={{
                                fontSize: '10.5px',
                                fontFamily: 'var(--font-mono)',
                                color: 'var(--accent-cyan)',
                                backgroundColor: 'rgba(0, 216, 245, 0.08)',
                                padding: '2px 6px',
                                borderRadius: '4px'
                              }}>
                                Gap Pause: {gapAfter}s
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Kinetic Elements & Resolved Presets */}
                      {elements.length > 0 && (
                        <div style={{
                          backgroundColor: 'var(--bg-card)',
                          border: '1px solid var(--border-card)',
                          borderRadius: '8px',
                          padding: '14px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '10px'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <Layers size={13} color="var(--accent-cyan)" />
                              <span style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                Kinetic Elements & Presets ({elements.length} Layers)
                              </span>
                            </div>
                            <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                              Resolved Registry Components
                            </span>
                          </div>

                          <div style={{
                            display: 'grid',
                            gridTemplateColumns: isFullPage ? 'repeat(auto-fit, minmax(260px, 1fr))' : '1fr',
                            gap: '10px'
                          }}>
                            {elements.map((el: any, elIdx: number) => (
                              <div
                                key={el.element_id || elIdx}
                                style={{
                                  backgroundColor: 'var(--bg-elevated)',
                                  border: el.semantic_role === 'primary' ? '1px solid rgba(0, 216, 245, 0.3)' : '1px solid rgba(255, 255, 255, 0.06)',
                                  borderRadius: '6px',
                                  padding: '10px 12px',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  gap: '6px'
                                }}
                              >
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                                    {el.element_id}
                                  </span>
                                  <div style={{ display: 'flex', gap: '4px' }}>
                                    <span style={{
                                      fontSize: '9.5px',
                                      fontWeight: 700,
                                      textTransform: 'uppercase',
                                      padding: '1px 6px',
                                      borderRadius: '3px',
                                      backgroundColor: el.semantic_role === 'primary' ? 'rgba(0, 216, 245, 0.2)' : 'rgba(255, 255, 255, 0.08)',
                                      color: el.semantic_role === 'primary' ? 'var(--accent-cyan)' : 'var(--text-muted)'
                                    }}>
                                      {el.semantic_role}
                                    </span>
                                    <span style={{
                                      fontSize: '9.5px',
                                      fontFamily: 'var(--font-mono)',
                                      padding: '1px 6px',
                                      borderRadius: '3px',
                                      backgroundColor: 'rgba(168, 85, 247, 0.15)',
                                      color: '#D8B4FE'
                                    }}>
                                      {el.type}
                                    </span>
                                  </div>
                                </div>

                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Preset:</span>
                                  <span style={{
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    fontFamily: 'var(--font-mono)',
                                    color: 'var(--accent-cyan)',
                                    backgroundColor: 'rgba(0, 216, 245, 0.1)',
                                    padding: '1px 6px',
                                    borderRadius: '3px'
                                  }}>
                                    {el.registry_id || 'default'}
                                  </span>
                                  <span style={{ fontSize: '10px', color: '#10B981', marginLeft: 'auto' }}>
                                    ✓ {el.status || 'resolved'}
                                  </span>
                                </div>

                                {el.note && (
                                  <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', lineHeight: 1.3 }}>
                                    {el.note}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Action Sequence Timeline */}
                      {sequence.length > 0 && (
                        <div style={{
                          backgroundColor: 'var(--bg-card)',
                          padding: '14px',
                          borderRadius: '8px',
                          border: '1px solid var(--border-card)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '10px'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <Film size={13} color="var(--accent-cyan)" />
                              <span style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                Kinetic Action Sequence ({sequence.length} Timed Events)
                              </span>
                            </div>
                            <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                              Chronological Animation Queue
                            </span>
                          </div>

                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {sequence.map((act: any, aIdx: number) => {
                              const phaseColors: Record<string, { bg: string; text: string }> = {
                                establish: { bg: 'rgba(59, 130, 246, 0.15)', text: '#60A5FA' },
                                enter: { bg: 'rgba(16, 185, 129, 0.15)', text: '#34D399' },
                                sustain: { bg: 'rgba(245, 158, 11, 0.15)', text: '#FBBF24' },
                                exit: { bg: 'rgba(239, 68, 68, 0.15)', text: '#F87171' }
                              };
                              const pColor = phaseColors[act.phase] || { bg: 'rgba(255, 255, 255, 0.08)', text: '#FFFFFF' };

                              return (
                                <div
                                  key={act.action_id || aIdx}
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    backgroundColor: 'var(--bg-elevated)',
                                    padding: '8px 12px',
                                    borderRadius: '4px',
                                    borderLeft: `3px solid ${pColor.text}`,
                                    flexWrap: 'wrap',
                                    gap: '8px'
                                  }}
                                >
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                                    <span style={{
                                      fontSize: '10px',
                                      fontWeight: 800,
                                      textTransform: 'uppercase',
                                      backgroundColor: pColor.bg,
                                      color: pColor.text,
                                      padding: '2px 6px',
                                      borderRadius: '3px'
                                    }}>
                                      {act.phase}
                                    </span>

                                    <span style={{
                                      fontSize: '11px',
                                      fontFamily: 'var(--font-mono)',
                                      color: 'var(--accent-cyan)',
                                      backgroundColor: 'rgba(0, 216, 245, 0.1)',
                                      padding: '2px 6px',
                                      borderRadius: '3px'
                                    }}>
                                      {act.start?.toFixed(2)}s - {act.end?.toFixed(2)}s ({act.start_frame}-{act.end_frame}f)
                                    </span>

                                    <span style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text-primary)' }}>
                                      {act.registry?.label || act.preset || act.action_id}
                                    </span>

                                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                                      ➔ Target: <strong style={{ color: 'var(--text-primary)' }}>{act.target}</strong>
                                    </span>
                                  </div>

                                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                                    {act.registry?.category && (
                                      <span style={{ fontSize: '10px', color: 'var(--text-muted)', backgroundColor: 'rgba(255, 255, 255, 0.05)', padding: '1px 5px', borderRadius: '3px' }}>
                                        {act.registry.category}
                                      </span>
                                    )}
                                    {act.depends_on && act.depends_on.length > 0 ? (
                                      <span style={{ fontSize: '10px', color: '#FBBF24', backgroundColor: 'rgba(245, 158, 11, 0.1)', padding: '1px 5px', borderRadius: '3px' }}>
                                        deps: {act.depends_on.join(', ')}
                                      </span>
                                    ) : (
                                      <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>independent</span>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Raw Scene JSON Box (Toggleable via JSON button) */}
                      {isRawJsonOpen && (
                        <div style={{
                          backgroundColor: 'var(--bg-card)',
                          border: '1px solid rgba(0, 216, 245, 0.3)',
                          borderRadius: '6px',
                          overflow: 'hidden'
                        }}>
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '8px 12px',
                            backgroundColor: 'var(--bg-elevated)',
                            borderBottom: '1px solid var(--border-card)'
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <Code size={13} color="var(--accent-cyan)" />
                              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                                Motion Scene {sceneNum} Raw JSON Data ({Object.keys(s).length} attributes)
                              </span>
                            </div>
                            <button
                              onClick={(e) => handleCopyMotionSceneJson(s, e)}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '3px 8px',
                                backgroundColor: isCopied ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.08)',
                                border: isCopied ? '1px solid #10B981' : '1px solid rgba(255, 255, 255, 0.15)',
                                borderRadius: '4px',
                                color: isCopied ? '#10B981' : '#FFFFFF',
                                fontSize: '10.5px',
                                cursor: 'pointer'
                              }}
                            >
                              {isCopied ? <Check size={11} color="#10B981" /> : <Copy size={11} />}
                              <span>{isCopied ? 'Copied!' : 'Copy'}</span>
                            </button>
                          </div>
                          <pre style={{
                            margin: 0,
                            padding: '12px 14px',
                            maxHeight: '340px',
                            overflowY: 'auto',
                            fontSize: '11.5px',
                            fontFamily: 'Consolas, monospace',
                            color: '#93C5FD',
                            lineHeight: 1.5,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-all'
                          }}>
                            {JSON.stringify(s, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                    </td></tr>
                  )}
                </React.Fragment>
              );
            })}
              </tbody>
            </table>
            )}
          </div>
        )}

        {/* Specialized: Frame-Accurate Visual Timeline (Stage 07: timeline) */}
        {activeTab === 'scenes' && config.id === 'timeline' && projectId && (
          <TimelineBuildVisualView
            projectId={projectId}
            onRetryTimeline={() => onRetryStage ? onRetryStage('timeline') : onRunStage?.('timeline')}
            isPipelineRunning={isPipelineRunning}
          />
        )}

        {activeTab === 'overview' && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: isFullPage ? 'minmax(0, 1.35fr) minmax(0, 1fr)' : '1fr',
            gap: '20px',
            alignItems: 'start'
          }}>
            {/* Left Column: Operational Status & Gates */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Operational State Card */}
              <div style={{
                backgroundColor: 'var(--bg-elevated)',
                padding: '16px 18px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-card)'
              }}>
                <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Operational State
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '6px' }}>
                  {isCompleted && <CheckCircle2 size={18} color="var(--status-completed)" />}
                  {isRunning && <Activity size={18} color="var(--accent-cyan)" className="animate-spin" />}
                  {isRetrying && <RotateCcw size={18} color="var(--status-retrying)" className="animate-spin" />}
                  {isFailed && <XCircle size={18} color="var(--status-failed)" />}
                  {isBlocked && <AlertTriangle size={18} color="var(--status-blocked)" />}
                  {!isCompleted && !isRunning && !isRetrying && !isFailed && !isBlocked && <Clock size={18} color="var(--text-muted)" />}
                  <span style={{ fontSize: '14.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {isCompleted 
                      ? 'Stage Finished & Verified' 
                      : isRunning 
                        ? 'Active Live Execution' 
                        : isRetrying
                          ? `Recovering Transient Failure (Attempt ${state?.attempt || 1})`
                          : isFailed
                            ? 'Stage Execution Failed'
                            : isBlocked
                              ? 'Blocked Awaiting Prerequisites'
                              : 'Waiting for Prerequisites'}
                  </span>
                </div>
              </div>

              {/* Warning: Long-running task without recent progress update */}
              {isStaleProgress && (
                <div 
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '12px 16px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'rgba(245, 158, 11, 0.12)',
                    border: '1px solid rgba(245, 158, 11, 0.35)',
                    color: '#FBBF24',
                    fontSize: '12.5px',
                    fontWeight: 600,
                    lineHeight: 1.4
                  }}
                >
                  <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                  <span>No recent progress update — checking current status.</span>
                </div>
              )}

              {/* Prominent Error Details Banner */}
              {isFailed && (
                <div style={{
                  backgroundColor: 'var(--status-failed-bg)',
                  padding: '16px 18px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--status-failed)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--status-failed)', fontWeight: 700, fontSize: '14px' }}>
                    <AlertCircle size={18} />
                    <span>
                      {state?.failingSubStage ? `Failed at ${state.failingSubStage}` : 'Execution Failed'}
                    </span>
                  </div>
                  <p style={{ fontSize: '13px', color: 'var(--text-primary)', marginTop: '8px', lineHeight: 1.4 }}>
                    {state?.errors?.[0] || 'Unknown transient error occurred during stage execution.'}
                  </p>
                  {state?.attempt && (
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '6px' }}>
                      Failure recorded after attempt {state.attempt}{state.maxAttempts ? ` of ${state.maxAttempts}` : ''}.
                    </div>
                  )}
                  {onRetryStage && (
                    <button
                      onClick={() => onRetryStage(config.id)}
                      style={{
                        marginTop: '12px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        backgroundColor: 'var(--status-failed)',
                        color: '#FFF',
                        border: 'none',
                        padding: '8px 14px',
                        borderRadius: 'var(--radius-sm)',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      <RotateCcw size={14} />
                      Retry Stage
                    </button>
                  )}
                </div>
              )}

              {/* Telugu Activity Message */}
              {state?.teluguMessage && (
                <div style={{
                  backgroundColor: 'rgba(0, 216, 245, 0.08)',
                  padding: '14px 16px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid rgba(0, 216, 245, 0.25)'
                }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase' }}>
                    Telugu Status Update
                  </span>
                  <p style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px' }}>
                    {state.teluguMessage}
                  </p>
                </div>
              )}

              {/* Specialized: Timeline Quality Gate Approval (Stage 08) */}
              {config.id === 'approval' && (
                <div style={{
                  backgroundColor: 'var(--bg-elevated)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-card)',
                  padding: '18px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <ShieldCheck size={18} color="var(--accent-cyan)" />
                    <span style={{ fontSize: '14.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                      Human Timeline Approval Gate
                    </span>
                  </div>
                  <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    Enforces mandatory LLM verification of scene durations, camera motions, and audio sync before Remotion rendering can begin.
                  </p>

                  <div style={{
                    backgroundColor: 'var(--bg-card)',
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '11.5px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-muted)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                  }}>
                    <div>Status: <span style={{ color: timelineApproval?.status === 'approved' ? 'var(--status-completed)' : 'var(--accent-cyan)', fontWeight: 700 }}>{timelineApproval?.status || 'Pending Producer Review'}</span></div>
                    <div>Contract: timeline.json & scenes.json verified</div>
                    {timelineApproval?.review_id && <div>Review ID: {timelineApproval.review_id}</div>}
                  </div>

                  {actionMessage && (
                    <div style={{
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '12px',
                      backgroundColor: actionMessage.startsWith('Error') ? 'var(--status-failed-bg)' : 'var(--status-completed-bg)',
                      color: actionMessage.startsWith('Error') ? 'var(--status-failed)' : 'var(--status-completed)',
                      fontWeight: 600
                    }}>
                      {actionMessage}
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                    <button
                      onClick={() => handleApproveTimeline('approved')}
                      disabled={actionLoading}
                      style={{
                        flex: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                        padding: '10px 16px',
                        backgroundColor: 'var(--status-completed)',
                        color: '#FFFFFF',
                        border: 'none',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '12.5px',
                        fontWeight: 700,
                        cursor: actionLoading ? 'not-allowed' : 'pointer',
                        opacity: actionLoading ? 0.7 : 1
                      }}
                    >
                      <Check size={14} />
                      Approve Timeline
                    </button>

                    <button
                      onClick={() => handleApproveTimeline('changes_requested')}
                      disabled={actionLoading}
                      style={{
                        padding: '10px 16px',
                        backgroundColor: 'transparent',
                        color: 'var(--text-secondary)',
                        border: '1px solid var(--border-card)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '12.5px',
                        fontWeight: 600,
                        cursor: actionLoading ? 'not-allowed' : 'pointer'
                      }}
                    >
                      Request Changes
                    </button>
                  </div>
                </div>
              )}

              {/* Specialized: Video Render Engine Details (Stage 09) */}
              {config.id === 'render' && (
                <div style={{
                  backgroundColor: 'var(--bg-elevated)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-card)',
                  padding: '18px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Video size={18} color="var(--accent-cyan)" />
                    <span style={{ fontSize: '14.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                      Remotion Video Render Engine
                    </span>
                  </div>
                  <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    Compiles Remotion motion components and mixes studio audio with FFmpeg to output 1080p Full HD MP4.
                  </p>

                  <div style={{
                    backgroundColor: 'var(--bg-card)',
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '11.5px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-muted)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                  }}>
                    <div>Target Resolution: 1080p (Full HD)</div>
                    <div>Video Codec: H.264 / AAC 320kbps</div>
                    <div>Output: projects/{projectId || 'active'}/final_video.mp4</div>
                    <div>Render Engine: {renderVideo?.engine || 'Remotion 4.x + FFmpeg'}</div>
                  </div>
                </div>
              )}
            </div>

            {/* Right Column: Metrics, Subtasks Progress, Agent Overview */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Timing & Metric Cards */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px'
              }}>
                <div style={{
                  backgroundColor: 'var(--bg-elevated)',
                  padding: '14px 16px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)'
                }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Elapsed Duration</span>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
                    {elapsedSec > 0 ? formatElapsedSeconds(elapsedSec) : '—'}
                  </div>
                </div>

                <div style={{
                  backgroundColor: 'var(--bg-elevated)',
                  padding: '14px 16px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)'
                }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Attempt Count</span>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
                    {state?.attempt || 1}
                  </div>
                </div>
              </div>

              {/* Subtasks Completion Summary */}
              <div style={{
                backgroundColor: 'var(--bg-elevated)',
                padding: '16px 18px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-card)',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '12.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    Subtasks Completion
                  </span>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                    {subSteps.length ? `${subDone} / ${subSteps.length} passed in the last report` : 'No step report'}
                  </span>
                </div>
                {/* Progress bar */}
                <div style={{
                  width: '100%',
                  height: '6px',
                  backgroundColor: 'var(--bg-card)',
                  borderRadius: '3px',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    width: `${subSteps.length > 0 ? (subDone / subSteps.length) * 100 : 0}%`,
                    height: '100%',
                    backgroundColor: isCompleted ? 'var(--status-completed)' : 'var(--accent-cyan)',
                    transition: 'width 0.3s ease'
                  }} />
                </div>
              </div>

              {/* Agent Preview Card */}
              <div style={{
                backgroundColor: 'var(--bg-elevated)',
                padding: '16px 18px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-card)',
                display: 'flex',
                alignItems: 'center',
                gap: '14px'
              }}>
                <div style={{
                  width: '42px',
                  height: '42px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'rgba(0, 216, 245, 0.12)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--accent-cyan)',
                  flexShrink: 0
                }}>
                  <Cpu size={20} />
                </div>
                <div>
                  <div style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {config.agentName}
                  </div>
                  <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                    ID: {config.agentId} • Category: {config.category.toUpperCase()}
                  </div>
                </div>
              </div>

              {/* Quick Action: Audio Analysis Drawer Link (for analyzer stage) */}
              {config.id === 'analyzer' && onOpenAudioAnalysis && (
                <button
                  onClick={onOpenAudioAnalysis}
                  data-testid="drawer-open-audio-analysis-btn"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    backgroundColor: 'rgba(24, 144, 255, 0.12)',
                    border: '1px solid rgba(24, 144, 255, 0.35)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '12px 16px',
                    color: '#FFFFFF',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'background-color 0.15s ease'
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(24, 144, 255, 0.22)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'rgba(24, 144, 255, 0.12)'; }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <FileAudio size={16} color="var(--accent-blue)" />
                    <span>Inspect Saved audio-analysis.json</span>
                  </div>
                  <span style={{ fontSize: '12px', color: 'var(--accent-cyan)', fontWeight: 700 }}>Open Results →</span>
                </button>
              )}
            </div>
          </div>
        )}

        {/* Subtasks Tab */}
        {activeTab === 'subtasks' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {/* LLM evidence for this stage: what the LLM really did (stored review + logged gateway calls) */}
            <div data-testid="subtasks-llm-evidence" style={{ padding: '12px 14px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '12.5px', fontWeight: 700, color: 'var(--text-primary)' }}>LLM</span>
                {realSub?.llm_review ? (
                  <span style={{
                    fontSize: '11px', fontWeight: 700, padding: '2px 8px', borderRadius: '9999px',
                    color: realSub.llm_review.status === 'passed' ? '#34D399' : (realSub.llm_review.status === 'blocked' ? '#FCA5A5' : '#FBBF24'),
                    backgroundColor: realSub.llm_review.status === 'passed' ? 'rgba(16, 185, 129, 0.12)' : (realSub.llm_review.status === 'blocked' ? 'rgba(239, 68, 68, 0.12)' : 'rgba(245, 158, 11, 0.12)')
                  }}>
                    review {realSub.llm_review.status}{realSub.llm_review.score != null ? ` · ${realSub.llm_review.score}` : ''}{realSub.llm_review.model ? ` · ${realSub.llm_review.model}` : ''}
                  </span>
                ) : (
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>no LLM review stored for this stage</span>
                )}
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  {Object.keys(realSub?.llm_calls || {}).length
                    ? `LLM calls logged: ${Object.entries(realSub!.llm_calls).map(([k, n]) => `${n} ${k}`).join(', ')}`
                    : 'no LLM calls logged for this stage'}
                </span>
              </div>
              <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                The steps below are deterministic checks the stage runs itself; the LLM works at stage level (generation and the review above).
              </span>
              {realSub?.llm_review?.summary && (
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>{realSub.llm_review.summary}</span>
              )}
            </div>

            <span style={{ fontSize: '12.5px', color: 'var(--text-muted)', fontWeight: 600 }}>
              {subSteps.length
                ? `Steps recorded in ${realSub?.report}${realSub?.written ? ` (written ${new Date(realSub.written * 1000).toLocaleString()})` : ''}`
                : 'This stage does not record step-by-step results; only its overall status and LLM review are available.'}
            </span>
            {subSteps.length > 0 && (() => {
              const checked = subSteps.filter((s) => s.llm_check?.current && s.llm_check.verdict !== 'error');
              const flagged = checked.filter((s) => s.llm_check!.verdict !== 'confirms').length;
              return (
                <div data-testid="subtasks-llm-step-summary" style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <span>
                    LLM step checks: <strong style={{ color: 'var(--text-primary)' }}>{checked.length} / {subSteps.length}</strong> checked
                    {flagged > 0 && <span style={{ color: '#FBBF24' }}> · {flagged} questioned or rejected</span>}
                    {realSub?.llm_checks_running && <span style={{ color: 'var(--accent-cyan)' }}> · checking now (one LLM call per step)…</span>}
                  </span>
                  {!realSub?.llm_checks_running && checked.length < subSteps.length && projectId && (
                    <button
                      onClick={() => runStageStepChecks(projectId, config.id).then(() => fetchStageSubtasks(projectId, config.id).then(setRealSub))}
                      data-testid="subtasks-llm-recheck-btn"
                      style={{ height: '26px', padding: '0 12px', borderRadius: '6px', fontSize: '11.5px', fontWeight: 600, cursor: 'pointer', color: '#38BDF8', backgroundColor: 'rgba(24, 144, 255, 0.12)', border: '1px solid rgba(24, 144, 255, 0.35)' }}
                    >
                      Check remaining steps with LLM
                    </button>
                  )}
                </div>
              );
            })()}
            {isRunning && subSteps.length > 0 && (
              <span style={{ fontSize: '12px', color: '#FBBF24' }}>
                The stage is running now: these are the results of its last finished run and refresh when the new report is written.
              </span>
            )}
            <div style={{
              display: 'grid',
              gridTemplateColumns: isFullPage ? 'repeat(auto-fill, minmax(460px, 1fr))' : '1fr',
              gap: '12px'
            }}>
              {subSteps.map((sub, i) => {
                const st = (sub.status || '').toLowerCase();
                const tone = st === 'completed' || st === 'passed' ? 'var(--status-completed)'
                  : (st === 'failed' || st === 'blocked' || st === 'error') ? 'var(--status-failed)'
                  : st === 'warning' ? '#FBBF24' : 'var(--text-muted)';
                return (
                <div
                  key={`${sub.n ?? i}-${sub.name}`}
                  data-testid={`real-subtask-${sub.n ?? i}`}
                  style={{
                    padding: '12px 14px',
                    backgroundColor: 'var(--bg-elevated)',
                    borderRadius: 'var(--radius-sm)',
                    border: `1px solid ${tone === 'var(--text-muted)' ? 'var(--border-subtle)' : tone}`,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--text-muted)',
                        backgroundColor: 'var(--bg-card)',
                        padding: '2px 6px',
                        borderRadius: '4px'
                      }}>
                        #{sub.n ?? i + 1}
                      </span>
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {sub.name}
                      </span>
                    </div>

                    <span style={{ fontSize: '11px', fontWeight: 700, color: tone, textTransform: 'uppercase' }}>
                      {sub.status.replace(/_/g, ' ')}
                      {sub.checks_total ? ` · ${sub.checks_passed ?? 0}/${sub.checks_total}` : ''}
                    </span>
                  </div>

                  {sub.detail && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.4, wordBreak: 'break-word' }}>
                      {sub.detail}
                    </div>
                  )}

                  {/* The LLM's own check of this step */}
                  {(() => {
                    const c = sub.llm_check;
                    if (!c || !c.current) {
                      return (
                        <div data-testid={`real-subtask-llm-${sub.n ?? i}`} style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {realSub?.llm_checks_running ? 'LLM check: in progress…' : 'LLM check: not checked yet'}
                          {c && !c.current ? ' (the last check was of an older result)' : ''}
                        </div>
                      );
                    }
                    const look = {
                      confirms: { label: '✓ LLM confirms', color: '#34D399', bg: 'rgba(16, 185, 129, 0.12)' },
                      questions: { label: '? LLM questions', color: '#FBBF24', bg: 'rgba(245, 158, 11, 0.12)' },
                      rejects: { label: '✗ LLM rejects', color: '#FCA5A5', bg: 'rgba(239, 68, 68, 0.12)' },
                      error: { label: '! LLM check failed', color: '#FCA5A5', bg: 'rgba(239, 68, 68, 0.12)' }
                    }[c.verdict];
                    return (
                      <div data-testid={`real-subtask-llm-${sub.n ?? i}`} style={{ display: 'flex', flexDirection: 'column', gap: '4px', padding: '8px 10px', borderRadius: '6px', backgroundColor: look.bg }}>
                        <span style={{ fontSize: '11px', fontWeight: 700, color: look.color }}>
                          {look.label}{c.model ? ` · ${c.model}` : ''}{c.latency_ms ? ` · ${(c.latency_ms / 1000).toFixed(1)}s` : ''}
                        </span>
                        {c.note && <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{c.note}</span>}
                      </div>
                    );
                  })()}
                </div>
                );
              })}
            </div>
          </div>
        )}

        {activeTab === 'agent' && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: isFullPage ? 'minmax(0, 1.4fr) minmax(0, 1fr)' : '1fr',
            gap: '20px',
            alignItems: 'start'
          }}>
            <div style={{
              backgroundColor: 'var(--bg-elevated)',
              padding: '20px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-card)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <div style={{
                  width: '46px',
                  height: '46px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'rgba(0, 216, 245, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--accent-cyan)'
                }}>
                  <Cpu size={24} />
                </div>
                <div>
                  <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                    {config.agentName}
                  </h3>
                  <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                    ID: {config.agentId}
                  </span>
                </div>
              </div>

              <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
                <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Assigned Responsibilities
                </span>
                <p style={{ fontSize: '13px', color: 'var(--text-primary)', marginTop: '4px', lineHeight: 1.5 }}>
                  {config.description}
                </p>
              </div>
            </div>

            <div style={{
              backgroundColor: 'var(--bg-elevated)',
              padding: '20px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-card)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px'
            }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Execution Metadata
              </span>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                Stage Order: <strong style={{ color: 'var(--text-primary)' }}>Stage {config.order}</strong>
              </div>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                Pipeline Category: <strong style={{ color: 'var(--accent-cyan)' }}>{config.category.toUpperCase()}</strong>
              </div>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                Weight in Video Composition: <strong style={{ color: 'var(--text-primary)' }}>{(config.weight * 100).toFixed(0)}%</strong>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'artifacts' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <span style={{ fontSize: '12.5px', color: 'var(--text-muted)', fontWeight: 600 }}>
              Produced Artifacts & Stage Outputs
            </span>
            {state?.artifacts && state.artifacts.length > 0 ? (
              <div style={{
                display: 'grid',
                gridTemplateColumns: isFullPage ? 'repeat(auto-fill, minmax(360px, 1fr))' : '1fr',
                gap: '12px'
              }}>
                {state.artifacts.map((art, idx) => (
                  <div
                    key={idx}
                    style={{
                      backgroundColor: 'var(--bg-elevated)',
                      padding: '14px 16px',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border-subtle)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <FileText size={18} color="var(--accent-cyan)" />
                      <div>
                        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {art.name}
                        </div>
                        <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                          {art.path}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{
                padding: '48px 16px',
                textAlign: 'center',
                backgroundColor: 'var(--bg-elevated)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-muted)',
                fontSize: '13px'
              }}>
                No artifacts recorded for this stage yet.
              </div>
            )}
          </div>
        )}

        {activeTab === 'logs' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <span style={{ fontSize: '12.5px', color: 'var(--text-muted)', fontWeight: 600 }}>
              Activity Stream & Technical Telemetry
            </span>
            <div style={{
              backgroundColor: 'var(--bg-app)',
              padding: '16px 20px',
              borderRadius: 'var(--radius-md)',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              minHeight: isFullPage ? '420px' : '220px',
              maxHeight: isFullPage ? '620px' : '360px',
              overflowY: 'auto',
              border: '1px solid var(--border-subtle)',
              lineHeight: 1.6
            }}>
              <div style={{ color: 'var(--accent-cyan)' }}>[INFO] Stage lifecycle bound: {config.id}</div>
              {state?.startedAt && <div>[START] Started at {new Date(state.startedAt).toLocaleTimeString()}</div>}
              {state?.currentActivity && <div>[ACTIVE] {state.currentActivity}</div>}
              {state?.teluguMessage && <div style={{ color: 'var(--status-completed)' }}>[TELUGU] {state.teluguMessage}</div>}
              {state?.errors?.[0] && <div style={{ color: 'var(--status-failed)' }}>[ERROR] {state.errors[0]}</div>}
              {state?.retryReason && <div style={{ color: 'var(--status-retrying)' }}>[RETRY] {state.retryReason}</div>}
              {isCompleted && <div style={{ color: 'var(--status-completed)' }}>[DONE] Completed successfully with verified hash.</div>}
            </div>
          </div>
        )}

        {/* About Stage & Agent Tab (Full Specification & Architectural Evidence) */}
        {activeTab === 'about' && (
          <AgentAboutTab
            stageId={config.id}
            agentId={config.agentId}
            isFullPage={isFullPage}
          />
        )}
      </div>
    </aside>
  );
};
