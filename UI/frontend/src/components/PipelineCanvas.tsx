import React, { useState, useEffect } from 'react';
import styles from './PipelineCanvas.module.css';
import type { MediaMix } from '../services/mediaMix';
import { CANONICAL_12_STAGES, PipelineProjectState } from '../types/pipeline';
import { StageDrawer } from './StageDrawer';
import { AgentCommunicationPanel } from './AgentCommunicationPanel';
import { AudioInputPage } from '../pages/AudioInputPage';
import { ProjectsDirectory } from './ProjectsDirectory';
import { fetchApprovals, llmDecideApproval, executeStageAction, runStage, stopStage } from '../services/api';
import { PipelineFlowGrid } from './pipeline-canvas/PipelineFlowGrid';
import { PipelineApprovalsTab } from './pipeline-canvas/PipelineApprovalsTab';
import { PipelineAlertBanners } from './pipeline-canvas/PipelineAlertBanners';

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
    reusableTemplates: boolean,
    media: MediaMix
  ) => Promise<void>;
  activeTab?: 'flow' | 'approvals' | 'communication' | 'new-project' | 'projects';
  onTabChange?: (tab: 'flow' | 'approvals' | 'communication' | 'new-project' | 'projects') => void;
  sseStatus?: 'connected' | 'reconnecting' | 'disconnected';
  onFullPageChange?: (open: boolean) => void;
  onRefreshProjects?: () => Promise<void> | void;
  onDeleteProject?: (projectId: string) => Promise<boolean>;
}

export const PipelineCanvas: React.FC<PipelineCanvasProps> = ({
  projectState,
  projects = [],
  activeProjectId,
  onSelectProject,
  agents = [],
  activeLlmCount: _activeLlmCount = 0,
  backendHealthy = true,
  onReloadState,
  onStartRun,
  onCancelRun: _onCancelRun,
  onNewProject,
  onAnalyze,
  activeTab: propActiveTab,
  onTabChange,
  sseStatus = 'connected',
  onFullPageChange,
  onRefreshProjects,
  onDeleteProject,
}) => {
  const [selectedStageId, setSelectedStageId] = useState<string | null>(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('stage') || null;
  });
  const [drawerStageId, setDrawerStageId] = useState<string | null>(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('stage') || null;
  });
  const [internalTab, setInternalTab] = useState<'flow' | 'approvals' | 'communication' | 'new-project' | 'projects'>('flow');
  const [pendingApprovals, setPendingApprovals] = useState<any[]>([]);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [autoFailure, setAutoFailure] = useState<{ stageId: string; label: string; message: string } | null>(null);

  const activeTab = propActiveTab || internalTab;

  const handleTabChange = (tab: 'flow' | 'approvals' | 'communication' | 'new-project' | 'projects') => {
    setInternalTab(tab);
    if (tab !== 'flow') {
      setDrawerStageId(null);
    }
    if (onTabChange) onTabChange(tab);
  };

  const drawerStageConfig = CANONICAL_12_STAGES.find((s) => s.id === drawerStageId);
  const drawerStageState = drawerStageId ? projectState.stages[drawerStageId] : undefined;

  const fullPageOpen = activeTab === 'flow' && !!drawerStageConfig;
  useEffect(() => {
    onFullPageChange?.(fullPageOpen);
    return () => onFullPageChange?.(false);
  }, [fullPageOpen, onFullPageChange]);

  const isFinalDelivered = projectState.stages['final']?.status === 'completed';
  const isAnyStageRunning = Object.values(projectState.stages).some(s => s.status === 'running' || s.status === 'retrying');
  const isRunning = projectState.status === 'running' && isAnyStageRunning;
  const failedStage = CANONICAL_12_STAGES.find(s => projectState.stages[s.id]?.status === 'failed');

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
    <div className={`${styles.canvasContainer} ${drawerStageConfig ? styles.canvasContainerFullPage : ''}`}>
      {/* MAIN WORKSPACE CONTAINER */}
      <div className={`${styles.mainWorkspace} ${drawerStageConfig ? styles.mainWorkspaceFullPage : ''}`}>
        <PipelineAlertBanners
          autoFailure={autoFailure}
          setAutoFailure={setAutoFailure}
          projectState={projectState}
          isAnyStageRunning={isAnyStageRunning}
          handleRunStage={handleRunStage}
          actionMessage={actionMessage}
          backendHealthy={backendHealthy}
          failedStage={failedStage}
          handleRetryStage={handleRetryStage}
          isAudioMissing={isAudioMissing}
          onUploadAudio={() => handleTabChange('new-project')}
        />

        {/* TAB 1: PIPELINE EXECUTION FLOW */}
        {activeTab === 'flow' && (
          drawerStageConfig ? (
            <div 
              data-testid="pipeline-stage-fullpage-container"
              className={styles.flowFullPage}
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
              />
            </div>
          ) : (
            <div className={styles.flowContent}>
              <div>
                <h2 className={styles.flowHeader}>
                  {projectState.title || projectState.projectId || 'sample-01'}
                </h2>
                <div className={styles.flowSubheader}>
                  <span className={styles.flowMetaText}>
                    Workspace: <strong>{projectState.projectId}</strong> | Aspect: <strong>{projectState.aspectRatio}</strong> | {CANONICAL_12_STAGES.length} Connected Stages
                  </span>
                  <span 
                    data-testid="live-connection-status-pill"
                    className={styles.connectionStatusPill}
                    style={{
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
                      className={`${styles.pulseDot} ${sseStatus === 'connected' ? 'animate-pulse-dot' : ''}`} 
                    />
                    {sseStatus === 'connected' ? 'Live Connected' : (sseStatus === 'reconnecting' ? 'Reconnecting...' : 'Disconnected')}
                  </span>
                </div>
              </div>

              <div className={styles.runRow}>
                <button
                  type="button"
                  className={styles.runVideoBtn}
                  data-testid="run-video"
                  disabled={isRunning || isAudioMissing}
                  onClick={onStartRun}
                  title="Runs every unfinished stage in order: each starts by itself when the one before it completed with nothing unresolved, and a stage with an issue stops the run there."
                >
                  {isRunning ? 'Running…' : (isFinalDelivered ? 'Run again (changed stages only)' : 'Run Video')}
                </button>
                <span className={styles.runHint}>Fully automatic: the LLM reviews decide, nobody approves anything.</span>
              </div>

              {/* 12 CANONICAL STAGE CARDS CONNECTED IN SEQUENCE */}
              <PipelineFlowGrid
                projectState={projectState}
                selectedStageId={selectedStageId}
                isRunning={isRunning}
                handleRunStage={handleRunStage}
                handleStopStage={handleStopStage}
                onSelectStage={(stageId) => {
                  setSelectedStageId(stageId);
                  setDrawerStageId(stageId);
                }}
              />
            </div>
          )
        )}

        {/* TAB 2: PREVIOUS PROJECTS SECTION */}
        {activeTab === 'projects' && (
          <div className={styles.tabContent}>
            <ProjectsDirectory
              projects={projects}
              activeProjectId={activeProjectId}
              onSelectProject={(pid) => {
                if (onSelectProject) onSelectProject(pid);
                handleTabChange('flow');
              }}
              onOpenLivePipeline={() => handleTabChange('flow')}
              onRefreshProjects={onRefreshProjects || onReloadState}
              onDeleteProject={onDeleteProject}
              onCreateProject={onNewProject ? (_title, _aspect) => onNewProject() : undefined}
              showCloseButton={false}
              title="All Projects Directory"
              subtitle="All localized workspaces, timeline runs, and render outputs. Click View to open project details, or Delete to remove."
            />
          </div>
        )}

        {/* TAB 3: PENDING APPROVALS & BLOCKERS */}
        {activeTab === 'approvals' && (
          <PipelineApprovalsTab
            pendingApprovals={pendingApprovals}
            activeProjectId={activeProjectId}
            handleLlmDecide={handleLlmDecide}
          />
        )}

        {/* TAB 4: AGENT COMMUNICATION (INLINE TAB — NOT A POPUP) */}
        {activeTab === 'communication' && (
          <div className={styles.tabContent}>
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
              onAnalyze={async (title, audioFile, aspect, reusableTemplates, media) => {
                if (onAnalyze) {
                  await onAnalyze(title, audioFile, aspect, reusableTemplates, media);
                }
                handleTabChange('flow');
              }}
              onCancel={() => handleTabChange('flow')}
            />
          </div>
        )}
      </div>

      {/* 3. SLIDE-OUT STAGE DETAIL DRAWER */}
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
        />
      )}
    </div>
  );
};
