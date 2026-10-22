import React, { useState, useEffect } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  CheckCircle2, 
  ShieldCheck, 
  Zap, 
  Tv, 
  ExternalLink,
  ChevronRight,
  FolderCheck,
  Video,
  Layers,
  Sparkles,
  Plus,
  MessageSquare,
  FolderKanban,
  AlertTriangle,
  Clock,
  ArrowRight,
  ShieldAlert,
  Check,
  X
} from 'lucide-react';
import { CANONICAL_12_STAGES, PipelineProjectState, StageConfig } from '../types/pipeline';
import { StageCard } from './StageCard';
import { StageDrawer } from './StageDrawer';
import { AudioAnalysisDrawer } from './AudioAnalysisDrawer';
import { AgentCommunicationPanel } from './AgentCommunicationPanel';
import { AudioInputPage } from '../pages/AudioInputPage';
import { fetchApprovals, llmDecideApproval, executeStageAction, runStage, stopStage } from '../services/api';

interface PipelineCanvasProps {
  projectState: PipelineProjectState;
  projects?: any[];
  activeProjectId: string;
  onSelectProject?: (projectId: string) => void;
  agents?: any[];
  activeLlmCount?: number;
  backendHealthy?: boolean;
  onReloadState?: () => void;
  onStartRun: () => void;
  onCancelRun: () => void;
  onNewProject: () => void;
  onAnalyze?: (
    title: string, 
    audioFile: File, 
    aspect: string, 
    reusableTemplates: boolean
  ) => Promise<void>;
  activeTab?: 'flow' | 'approvals' | 'communication' | 'new-project' | 'projects';
  onTabChange?: (tab: 'flow' | 'approvals' | 'communication' | 'new-project' | 'projects') => void;
  sseStatus?: 'connected' | 'reconnecting' | 'disconnected';
  onFullPageChange?: (open: boolean) => void;
}

export const PipelineCanvas: React.FC<PipelineCanvasProps> = ({
  projectState,
  projects = [],
  activeProjectId,
  onSelectProject,
  agents = [],
  activeLlmCount = 0,
  backendHealthy = true,
  onReloadState,
  onStartRun,
  onCancelRun,
  onNewProject,
  onAnalyze,
  activeTab: propActiveTab,
  onTabChange,
  sseStatus = 'connected',
  onFullPageChange
}) => {
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);
  const [drawerStageId, setDrawerStageId] = useState<string | null>(null);
  const [isAudioAnalysisDrawerOpen, setIsAudioAnalysisDrawerOpen] = useState<boolean>(false);
  const [internalTab, setInternalTab] = useState<'flow' | 'approvals' | 'communication' | 'new-project' | 'projects'>('flow');
  const [pendingApprovals, setPendingApprovals] = useState<any[]>([]);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  // An automatic start that the backend refused or that failed: the real reason, and the stage to run by hand (null = nothing failed)
  const [autoFailure, setAutoFailure] = useState<{ stageId: string; label: string; message: string } | null>(null);

  const activeTab = propActiveTab || internalTab;

  const handleTabChange = (tab: 'flow' | 'approvals' | 'communication' | 'new-project' | 'projects') => {
    setInternalTab(tab);
    if (tab !== 'flow') {
      setIsAudioAnalysisDrawerOpen(false);
      setDrawerStageId(null);
    }
    if (onTabChange) onTabChange(tab);
  };

  const drawerStageConfig = CANONICAL_12_STAGES.find((s) => s.id === drawerStageId);
  const drawerStageState = drawerStageId ? projectState.stages[drawerStageId] : undefined;

  const fullPageOpen = activeTab === 'flow' && (isAudioAnalysisDrawerOpen || !!drawerStageConfig);
  useEffect(() => {
    onFullPageChange?.(fullPageOpen);
    return () => onFullPageChange?.(false);
  }, [fullPageOpen, onFullPageChange]);

  const isFinalDelivered = projectState.stages['final']?.status === 'completed';
  const isAnyStageRunning = Object.values(projectState.stages).some(s => s.status === 'running' || s.status === 'retrying');
  const isRunning = projectState.status === 'running' && isAnyStageRunning;

  const failedStage = CANONICAL_12_STAGES.find(s => projectState.stages[s.id]?.status === 'failed');
  const failedStageState = failedStage ? projectState.stages[failedStage.id] : null;

  const isAudioMissing = projectState.stages['audio']?.status === 'waiting' && 
    (projectState.stages['audio']?.currentActivity?.toLowerCase().includes('no audio') || false);

  // Retry or execute backend stage action
  const handleRetryStage = async (stageId: string) => {
    try {
      setActionMessage(`Initiating ${stageId} execution...`);
      const actionMap: Record<string, string> = {
        audio: 'retry_transcribe',
        analyzer: 'retry_transcribe',
        segmentation: 'run_segmentation',
        planning: 'retry_plan',
        motion_plan: 'run_motion',
        motion_gen: 'run_motion',
        motion_validation: 'run_motion',
        timeline: 'retry_timeline'
      };
      const actionKind = actionMap[stageId] || 'start_run';
      const result = await executeStageAction(projectState.projectId || activeProjectId, actionKind, stageId);
      if (result?.kind === 'drawer') {
        setDrawerStageId(result.stageId);
      } else {
        setActionMessage(`Stage ${stageId} started successfully.`);
        if (onReloadState) onReloadState();
      }
      setTimeout(() => setActionMessage(null), 3500);
    } catch (err: any) {
      alert(`Stage execution failed: ${err.message}`);
    }
  };

  const handleRunStage = async (stageId: string) => {
    try {
      const pid = projectState.projectId || activeProjectId;
      if (!pid) return;
      setActionMessage(`Starting stage '${stageId}'...`);
      await runStage(pid, stageId);
      setActionMessage(`Stage '${stageId}' started successfully.`);
      if (onReloadState) onReloadState();
      setTimeout(() => setActionMessage(null), 3500);
    } catch (err: any) {
      setActionMessage(`Execution notice for '${stageId}': ${err.message}. Manual RUN is available.`);
      setTimeout(() => setActionMessage(null), 6000);
    }
  };

  const handleStopStage = async (stageId: string) => {
    try {
      const pid = projectState.projectId || activeProjectId;
      if (!pid) return;
      setActionMessage(`Stopping stage '${stageId}'...`);
      await stopStage(pid, stageId);
      setActionMessage(`Stop request sent for '${stageId}'.`);
      if (onReloadState) onReloadState();
      setTimeout(() => setActionMessage(null), 3500);
    } catch (err: any) {
      setActionMessage(`Stop request failed: ${err.message}`);
      setTimeout(() => setActionMessage(null), 5000);
    }
  };

  // Auto-advance to next downstream stage when previous stage completes
  const autoTriggeredStagesRef = React.useRef<Set<string>>(new Set());
  const isAutoAdvancingRef = React.useRef<boolean>(false);

  useEffect(() => {
    // If any stage is actively executing, wait for it to complete
    if (isAnyStageRunning || isAutoAdvancingRef.current) return;

    // If a stage failed, do not auto-advance past it
    if (failedStage) return;

    const pid = activeProjectId;
    if (!pid || pid === 'sample-01' || projectState.projectId !== activeProjectId) return;

    // Find first incomplete stage in sequence
    for (let i = 0; i < CANONICAL_12_STAGES.length; i++) {
      const stage = CANONICAL_12_STAGES[i];
      const stageState = projectState.stages[stage.id];
      const isCompleted = stageState?.status === 'completed';

      if (!isCompleted) {
        const prevStage = i > 0 ? CANONICAL_12_STAGES[i - 1] : null;
        const prevCompleted = prevStage ? projectState.stages[prevStage.id]?.status === 'completed' : !isAudioMissing;

        if (prevCompleted && (stageState?.status === 'waiting' || stageState?.status === 'queued' || stageState?.status === 'idle')) {
          // Do not automatically advance past motion_gen into motion_validation without generation completing
          if (stage.id === 'motion_validation') {
            break;
          }

          const autoKey = `${pid}:${stage.id}`;
          if (!autoTriggeredStagesRef.current.has(autoKey)) {
            autoTriggeredStagesRef.current.add(autoKey);
            isAutoAdvancingRef.current = true;
            setActionMessage(`Auto-starting Stage ${String(stage.order).padStart(2, '0')}: ${stage.label}...`);
            runStage(pid, stage.id)
              .then(() => {
                setAutoFailure(null);
                setActionMessage(`Stage ${stage.label} started automatically.`);
                if (onReloadState) onReloadState();
                setTimeout(() => setActionMessage(null), 3500);
              })
              .catch((err: any) => {
                console.warn(`Auto-advance for stage ${stage.id} failed:`, err);
                setActionMessage(null);
                setAutoFailure({ stageId: stage.id, label: stage.label, message: String(err?.message || err) });
              })
              .finally(() => {
                isAutoAdvancingRef.current = false;
              });
          }
        }
        break;
      }
    }
  }, [projectState.stages, isAnyStageRunning, failedStage, isAudioMissing, projectState.projectId, activeProjectId, onReloadState]);

  // Load pending approvals
  const loadApprovals = async () => {
    try {
      const data = await fetchApprovals('pending');
      setPendingApprovals(data);
    } catch {
      setPendingApprovals([]);
    }
  };

  useEffect(() => {
    loadApprovals();
    const interval = setInterval(loadApprovals, 5000);
    return () => clearInterval(interval);
  }, [projectState.projectId]);

  const handleLlmDecide = async (approvalId: string) => {
    try {
      const done = await llmDecideApproval(approvalId);
      setActionMessage(`The LLM review ${done.decision?.replace('_', ' ') ?? 'decided'}: ${(done.decision_reason || '').slice(0, 160)}`);
      setTimeout(() => setActionMessage(null), 6000);
      loadApprovals();
    } catch (err: any) {
      alert(`LLM approval review failed: ${err.message}`);
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '20px',
      maxWidth: '1600px',
      margin: '0 auto',
      position: 'relative'
    }}>
      {/* MAIN WORKSPACE CONTAINER (OUTER CARD REMOVED AS REQUESTED) */}
      <div style={{
        backgroundColor: 'transparent',
        borderRadius: 0,
        border: 'none',
        boxShadow: 'none',
        padding: '0 0 24px 0',
        transition: 'background-color 0.2s ease, border-color 0.2s ease'
      }}>


        {/* Action feedback message */}
        {autoFailure && projectState.stages[autoFailure.stageId]?.status !== 'running' && projectState.stages[autoFailure.stageId]?.status !== 'completed' && (
          <div data-testid="auto-advance-failure" style={{
            margin: '0 0 12px', padding: '10px 14px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap',
            backgroundColor: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.4)', color: '#FCA5A5', fontSize: '12.5px'
          }}>
            <AlertTriangle size={15} style={{ flexShrink: 0 }} />
            <span style={{ flex: 1, minWidth: '240px' }}>
              <strong>{autoFailure.label} did not start automatically.</strong> {autoFailure.message}
            </span>
            <button
              data-testid="auto-advance-manual-run"
              disabled={isAnyStageRunning}
              title={isAnyStageRunning ? 'Another stage is running' : `Run ${autoFailure.label} (the same dependency and issue checks apply)`}
              onClick={() => { const id = autoFailure.stageId; setAutoFailure(null); handleRunStage(id); }}
              style={{ height: '28px', padding: '0 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: isAnyStageRunning ? 'not-allowed' : 'pointer',
                       color: '#38BDF8', backgroundColor: 'rgba(24, 144, 255, 0.12)', border: '1px solid rgba(24, 144, 255, 0.35)', opacity: isAnyStageRunning ? 0.6 : 1 }}
            >
              Run {autoFailure.label}
            </button>
          </div>
        )}
        {actionMessage && (
          <div style={{
            margin: '16px 28px 0 28px',
            padding: '10px 16px',
            backgroundColor: 'var(--status-completed-bg)',
            border: '1px solid var(--status-completed-border)',
            borderRadius: '4px',
            color: 'var(--status-completed)',
            fontSize: '13px',
            fontWeight: 600
          }}>
            {actionMessage}
          </div>
        )}

        {/* Backend Connectivity Status Alert */}
        {!backendHealthy && (
          <div 
            data-testid="backend-disconnected-banner"
            style={{
              margin: '16px 28px 0 28px',
              padding: '12px 18px',
              backgroundColor: 'var(--status-failed-bg)',
              border: '1px solid var(--status-failed-border)',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              color: 'var(--status-failed)',
              fontSize: '13px',
              fontWeight: 600
            }}
          >
            <AlertTriangle size={16} />
            <span>FastAPI Backend Offline / Unreachable — Attempting automatic reconnection to http://127.0.0.1:8000...</span>
          </div>
        )}

        {/* TAB 1: PIPELINE EXECUTION FLOW */}
        {activeTab === 'flow' && (
          isAudioAnalysisDrawerOpen ? (
            <div 
              data-testid="pipeline-audio-analysis-fullpage-container"
              style={{
                padding: 0,
                minHeight: 'calc(100vh - 160px)',
                display: 'flex',
                flexDirection: 'column'
              }}
            >
              <AudioAnalysisDrawer
                projectId={projectState.projectId || activeProjectId}
                isOpen={true}
                isFullPage={true}
                onClose={() => setIsAudioAnalysisDrawerOpen(false)}
                onRunWorkflow={() => handleRunStage('analyzer')}
                onStopWorkflow={() => handleStopStage('analyzer')}
                isRunning={projectState.stages['analyzer']?.status === 'running'}
              />
            </div>
          ) : drawerStageConfig ? (
            <div 
              data-testid="pipeline-stage-fullpage-container"
              style={{
                padding: 0,
                minHeight: 'calc(100vh - 160px)',
                display: 'flex',
                flexDirection: 'column'
              }}
            >
              <StageDrawer
                config={drawerStageConfig}
                state={drawerStageState}
                projectId={projectState.projectId || activeProjectId}
                isFullPage={true}
                onClose={() => setDrawerStageId(null)}
                onRunStage={handleRunStage}
                onStopStage={handleStopStage}
                onRetryStage={(id) => handleRetryStage(id)}
                isPipelineRunning={isRunning}
                onOpenAudioAnalysis={() => {
                  setDrawerStageId(null);
                  setIsAudioAnalysisDrawerOpen(true);
                }}
              />
            </div>
          ) : (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              padding: '24px 28px',
              width: '100%',
              boxSizing: 'border-box'
            }}>
              <div>
                <h2 style={{
                  fontSize: '20px',
                  fontWeight: 800,
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-sans)',
                  letterSpacing: '-0.4px',
                  margin: 0
                }}>
                  {projectState.title || projectState.projectId || 'sample-01'}
                </h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Workspace: <strong>{projectState.projectId}</strong> | Aspect: <strong>{projectState.aspectRatio}</strong> | {CANONICAL_12_STAGES.length} Connected Stages
                  </span>
                  <span 
                    data-testid="live-connection-status-pill"
                    style={{
                      fontSize: '10px',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '10px',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      backgroundColor: sseStatus === 'connected' 
                        ? 'var(--status-completed-bg)' 
                        : (sseStatus === 'reconnecting' ? 'var(--status-retrying-bg)' : 'var(--status-failed-bg)'),
                      border: `1px solid ${
                        sseStatus === 'connected' 
                          ? 'var(--status-completed-border)' 
                          : (sseStatus === 'reconnecting' ? 'var(--status-retrying-border)' : 'var(--status-failed-border)')
                      }`,
                      color: sseStatus === 'connected' 
                        ? 'var(--status-completed)' 
                        : (sseStatus === 'reconnecting' ? 'var(--status-retrying)' : 'var(--status-failed)')
                    }}
                  >
                    <span 
                      className={sseStatus === 'connected' ? 'animate-pulse-dot' : ''} 
                      style={{ 
                        width: '5px', 
                        height: '5px', 
                        borderRadius: '50%', 
                        backgroundColor: 'currentColor' 
                      }} 
                    />
                    {sseStatus === 'connected' ? 'Live Connected' : (sseStatus === 'reconnecting' ? 'Reconnecting...' : 'Disconnected')}
                  </span>
                </div>
              </div>

              {/* Stage Failure Alert Banner with One-Click Retry */}
              {failedStage && (
                <div
                  data-testid="stage-error-banner"
                  style={{
                    backgroundColor: 'var(--status-failed-bg)',
                    border: '1px solid var(--status-failed-border)',
                    borderRadius: '4px',
                    padding: '12px 18px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '12px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <AlertTriangle size={18} color="var(--status-failed)" />
                    <div>
                      <h4 style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--status-failed)', margin: 0 }}>
                        {failedStage.label} Execution Failed
                      </h4>
                      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
                        {failedStageState?.errors?.[0] || failedStageState?.currentActivity || 'A step encountered an error. Retry to re-run from the last valid checkpoint.'}
                      </p>
                    </div>
                  </div>

                  <button
                    onClick={() => handleRetryStage(failedStage.id)}
                    data-testid="retry-failed-stage-btn"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 14px',
                      backgroundColor: 'var(--status-failed)',
                      color: '#FFFFFF',
                      border: 'none',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    <RotateCcw size={13} />
                    Retry {failedStage.label}
                  </button>
                </div>
              )}

              {/* Empty Audio Workspace Ingest Prompt */}
              {isAudioMissing && (
                <div
                  data-testid="empty-audio-prompt"
                  style={{
                    backgroundColor: 'var(--bg-elevated)',
                    border: '1px dashed var(--border-card)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '14px 20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '14px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Clock size={16} color="var(--accent-blue)" />
                    <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                      No narration audio uploaded for workspace <strong>{projectState.projectId}</strong>. Upload an audio file to begin video generation.
                    </span>
                  </div>

                  <button
                    onClick={() => handleTabChange('new-project')}
                    style={{
                      padding: '6px 14px',
                      backgroundColor: 'var(--accent-blue)',
                      color: '#FFFFFF',
                      border: 'none',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    Upload Audio
                  </button>
                </div>
              )}

              {/* Delivery Alert when Final Stage 12 is Completed */}
              {isFinalDelivered && (
                <div 
                  data-testid="delivery-success-banner"
                  style={{
                    backgroundColor: 'var(--status-completed-bg)',
                    border: '1px solid var(--status-completed-border)',
                    borderRadius: '4px',
                    padding: '16px 20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '12px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '50%',
                      backgroundColor: 'var(--status-completed)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#FFFFFF'
                    }}>
                      <Video size={18} />
                    </div>
                    <div>
                      <h4 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
                        Production Video Delivered to Desktop
                      </h4>
                      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        All 12 stages passed technical QC with zero manual intervention.
                      </p>
                    </div>
                  </div>

                  <div style={{
                    fontSize: '11px',
                    fontFamily: 'var(--font-mono)',
                    backgroundColor: 'var(--bg-card)',
                    padding: '6px 12px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-card)',
                    color: 'var(--accent-blue)'
                  }}>
                    Desktop/darkworld-renders/{projectState.projectId}
                  </div>
                </div>
              )}

              {/* 12 CANONICAL STAGE CARDS CONNECTED IN SEQUENCE */}
              <div 
                data-testid="stages-container"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px'
                }}
              >
                {[
                  CANONICAL_12_STAGES.slice(0, 4),   // Row 1: Audio Analysis & Planning (01 to 04)
                  CANONICAL_12_STAGES.slice(4, 8),   // Row 2: Motion Planning & Assembly (05 to 08)
                  CANONICAL_12_STAGES.slice(8)       // Row 3: Approval, Render, QC & Delivery (09 to the last stage)
                ].map((rowStages, rowIndex) => (
                  <div key={rowIndex} style={{ position: 'relative' }}>
                    {/* Row of Stage Cards */}
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                      gap: '24px',
                      position: 'relative'
                    }}>
                      {rowStages.map((stage, colIndex) => {
                        const isLastInRow = colIndex === rowStages.length - 1;
                        const isPassed = projectState.stages[stage.id]?.status === 'completed';
                        const isCurrentlyRunning = projectState.stages[stage.id]?.status === 'running';

                        return (
                          <div 
                            key={stage.id} 
                            style={{ 
                              position: 'relative',
                              display: 'flex',
                              flexDirection: 'column'
                            }}
                          >
                            <StageCard
                              config={stage}
                              state={projectState.stages[stage.id]}
                              isSelected={selectedStageId === stage.id}
                              onRunStage={handleRunStage}
                              onStopStage={handleStopStage}
                              isPipelineRunning={isRunning}
                              onSelect={() => {
                                setSelectedStageId(stage.id);
                                if (stage.id === 'analyzer') {
                                  setIsAudioAnalysisDrawerOpen(true);
                                  setDrawerStageId(null);
                                } else {
                                  setDrawerStageId(stage.id);
                                  setIsAudioAnalysisDrawerOpen(false);
                                }
                              }}
                            />

                            {/* Sequential Connector Arrow to Next Card in Row */}
                            {!isLastInRow && (
                              <div style={{
                                position: 'absolute',
                                right: '-20px',
                                top: '50%',
                                transform: 'translateY(-50%)',
                                zIndex: 10,
                                display: 'flex',
                                alignItems: 'center',
                                pointerEvents: 'none'
                              }}>
                                <div className={isCurrentlyRunning ? 'animate-arrow-flow' : undefined} style={{
                                  width: '16px',
                                  height: '2px',
                                  backgroundColor: isPassed 
                                    ? 'var(--status-completed)' 
                                    : (isCurrentlyRunning ? 'var(--accent-cyan)' : 'var(--border-card)'),
                                  boxShadow: isCurrentlyRunning ? '0 0 8px var(--accent-cyan)' : 'none',
                                  position: 'relative',
                                  transition: 'background-color 0.2s ease'
                                }}>
                                  {/* Directional Arrow Head */}
                                  <div style={{
                                    position: 'absolute',
                                    right: '-5px',
                                    top: '-4px',
                                    width: 0,
                                    height: 0,
                                    borderTop: '5px solid transparent',
                                    borderBottom: '5px solid transparent',
                                    borderLeft: `6px solid ${isPassed ? 'var(--status-completed)' : (isCurrentlyRunning ? 'var(--accent-cyan)' : 'var(--border-card)')}`,
                                    transition: 'border-left-color 0.2s ease'
                                  }} />
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>

                  </div>
                ))}
              </div>
            </div>
          )
        )}

        {/* TAB 2: PREVIOUS PROJECTS SECTION */}
        {activeTab === 'projects' && (
          <div style={{ padding: '24px 28px' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '20px'
            }}>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Previous Production Projects
                </h3>
                <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Select an existing workspace to review outputs, resume execution, or inspect pipeline state.
                </p>
              </div>

              <button
                onClick={onNewProject}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '7px 16px',
                  backgroundColor: 'var(--accent-blue)',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                <Plus size={14} />
                New Project
              </button>
            </div>

            {projects.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: '48px',
                backgroundColor: 'var(--bg-elevated)',
                borderRadius: 'var(--radius-sm)',
                border: '1px dashed var(--border-card)'
              }}>
                <FolderKanban size={32} style={{ color: 'var(--text-muted)', marginBottom: '10px' }} />
                <h4 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  No Previous Projects Found
                </h4>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Click "New Project" to ingest audio and begin your first automated video production.
                </p>
              </div>
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                gap: '16px'
              }}>
                {projects.map((proj) => {
                  const pid = proj.id || proj.project_id || proj.name;
                  const isCurrent = activeProjectId === pid;

                  return (
                    <div
                      key={pid}
                      style={{
                        backgroundColor: 'var(--bg-elevated)',
                        border: `1px solid ${isCurrent ? 'var(--accent-blue)' : 'var(--border-card)'}`,
                        borderRadius: 'var(--radius-sm)',
                        padding: '18px 20px',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        gap: '14px',
                        boxShadow: 'var(--shadow-card)',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{
                            fontSize: '15px',
                            fontWeight: 700,
                            color: 'var(--text-primary)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }}>
                            {proj.name || pid}
                          </span>
                          <span style={{
                            fontSize: '11px',
                            fontWeight: 600,
                            color: 'var(--accent-blue)',
                            backgroundColor: 'var(--status-running-bg)',
                            padding: '2px 8px',
                            borderRadius: '4px'
                          }}>
                            {proj.aspect || '16:9'}
                          </span>
                        </div>

                        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
                          ID: {pid}
                        </div>

                        {proj.created && (
                          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Clock size={12} />
                            <span>Created: {new Date(proj.created).toLocaleDateString()}</span>
                          </div>
                        )}
                      </div>

                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        borderTop: '1px solid var(--border-card)',
                        paddingTop: '12px'
                      }}>
                        <span style={{
                          fontSize: '12px',
                          fontWeight: 600,
                          color: isCurrent ? 'var(--status-completed)' : 'var(--text-muted)'
                        }}>
                          {isCurrent ? '● Active Workspace' : 'Available'}
                        </span>

                        <button
                          onClick={() => {
                            if (onSelectProject) onSelectProject(pid);
                            handleTabChange('flow');
                          }}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '6px 14px',
                            backgroundColor: isCurrent ? 'var(--status-running-bg)' : 'var(--bg-card)',
                            color: 'var(--accent-blue)',
                            border: '1px solid var(--border-card)',
                            borderRadius: '4px',
                            fontSize: '12.5px',
                            fontWeight: 600,
                            cursor: 'pointer'
                          }}
                        >
                          <span>{isCurrent ? 'View Flow' : 'Open / Resume'}</span>
                          <ArrowRight size={13} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: PENDING APPROVALS & BLOCKERS */}
        {activeTab === 'approvals' && (
          <div style={{ padding: '24px 28px' }}>
            <div style={{ marginBottom: '20px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Pending Approval Requests
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
                High-risk actions wait here until the LLM approval review decides them; no person approves.
              </p>
            </div>

            {pendingApprovals.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: '48px',
                backgroundColor: 'var(--bg-elevated)',
                borderRadius: 'var(--radius-sm)',
                border: '1px dashed var(--border-card)'
              }}>
                <ShieldCheck size={36} style={{ color: 'var(--status-completed)', marginBottom: '10px' }} />
                <h4 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  All Clear — No Pending Approvals
                </h4>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  No request is waiting for the LLM approval review.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {pendingApprovals.map((appr) => (
                  <div
                    key={appr.approval_id || appr.id}
                    style={{
                      backgroundColor: 'var(--bg-elevated)',
                      border: '1px solid var(--status-blocked-border)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '18px 22px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '16px'
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor: 'var(--status-blocked-bg)',
                          color: 'var(--status-blocked)',
                          padding: '2px 8px',
                          borderRadius: '4px'
                        }}>
                          {(appr.risk_level || 'MEDIUM').toUpperCase()} RISK
                        </span>
                        <h4 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
                          {appr.action_summary || appr.action_type || 'Approval Request'}
                        </h4>
                      </div>

                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        Requester Agent: <strong style={{ color: 'var(--accent-blue)' }}>{appr.requester_agent_id}</strong> • Project: {appr.project_id || activeProjectId}
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <button
                        onClick={() => handleLlmDecide(appr.approval_id || appr.id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '6px 16px',
                          backgroundColor: 'var(--status-completed)',
                          color: '#FFFFFF',
                          border: 'none',
                          borderRadius: '4px',
                          fontSize: '13px',
                          fontWeight: 600,
                          cursor: 'pointer',
                          boxShadow: '0 2px 4px rgba(16, 185, 129, 0.3)'
                        }}
                      >
                        <Check size={14} />
                        Let the LLM decide
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: AGENT COMMUNICATION (INLINE TAB — NOT A POPUP) */}
        {activeTab === 'communication' && (
          <div style={{ padding: '24px 28px' }}>
            <AgentCommunicationPanel
              projectId={projectState.projectId || activeProjectId}
              agents={agents}
              isOpen={true}
              onClose={() => handleTabChange('flow')}
              isPipelineRunning={isRunning}
            />
          </div>
        )}

        {/* TAB 5: NEW PROJECT (INLINE AUDIO INGEST IN LIVE PIPELINE SECTION) */}
        {activeTab === 'new-project' && (
          <div style={{ padding: '16px 20px' }}>
            <AudioInputPage
              onAnalyze={async (title, audioFile, aspect, reusableTemplates) => {
                if (onAnalyze) {
                  await onAnalyze(title, audioFile, aspect, reusableTemplates);
                }
                handleTabChange('flow');
              }}
              onCancel={() => handleTabChange('flow')}
            />
          </div>
        )}
      </div>

      {/* 3. SLIDE-OUT STAGE DETAIL DRAWER - only rendered in drawer mode when flow tab is not active */}
      {activeTab !== 'flow' && drawerStageConfig && (
        <StageDrawer
          config={drawerStageConfig}
          state={drawerStageState}
          projectId={projectState.projectId || activeProjectId}
          isFullPage={false}
          onClose={() => setDrawerStageId(null)}
          onRunStage={handleRunStage}
          onStopStage={handleStopStage}
          onRetryStage={(id) => handleRetryStage(id)}
          isPipelineRunning={isRunning}
          onOpenAudioAnalysis={() => {
            setDrawerStageId(null);
            setIsAudioAnalysisDrawerOpen(true);
          }}
        />
      )}

      {/* 4. DEDICATED AUDIO ANALYSIS RESULTS DRAWER (STAGE 01) - only rendered in drawer mode when flow tab is not active */}
      {activeTab !== 'flow' && isAudioAnalysisDrawerOpen && (
        <AudioAnalysisDrawer
          projectId={projectState.projectId || activeProjectId}
          isOpen={true}
          isFullPage={false}
          onClose={() => setIsAudioAnalysisDrawerOpen(false)}
          onRunWorkflow={() => handleRunStage('analyzer')}
          onStopWorkflow={() => handleStopStage('analyzer')}
          isRunning={projectState.stages['analyzer']?.status === 'running'}
        />
      )}
    </div>
  );
};
