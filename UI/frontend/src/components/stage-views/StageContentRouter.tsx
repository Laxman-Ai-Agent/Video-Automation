import React from 'react';
import { StageConfig, StageState } from '../../types/pipeline';
import { StageSubtasks } from '../../services/api';
import { VisualPlanningView } from '../VisualPlanningView';
import { AssetsView } from '../AssetsView';
import { TimelineBuildVisualView } from '../TimelineBuildVisualView';
import { AgentAboutTab } from '../AgentAboutTab';
import { AudioAnalyzerView } from '../AudioAnalyzerView';
import { StageOverviewTab } from './StageOverviewTab';
import { SegmentationSceneTable } from './SegmentationSceneTable';
import { MotionPlanSceneTable } from './MotionPlanSceneTable';
import { StageSubtasksTab } from './StageSubtasksTab';
import { StageAgentTab, StageArtifactsTab, StageLogsTab } from './StageMetaTabs';

function formatElapsedSeconds(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

export interface StageContentRouterProps {
  activeTab: 'overview' | 'scenes' | 'subtasks' | 'agent' | 'artifacts' | 'logs' | 'about';
  config: StageConfig;
  state?: StageState;
  projectId?: string;
  isFullPage: boolean;
  isPipelineRunning: boolean;
  isRunning: boolean;
  isRetrying: boolean;
  isCompleted: boolean;
  isFailed: boolean;
  isBlocked: boolean;
  isStaleProgress: boolean;
  elapsedSec: number;
  subSteps: any[];
  subDone: number;
  realSub: StageSubtasks | null;
  setRealSub: React.Dispatch<React.SetStateAction<StageSubtasks | null>>;
  sceneData: any;
  scenesList: any[];
  filteredScenes: any[];
  sceneSearch: string;
  setSceneSearch: (s: string) => void;
  sceneLoading: boolean;
  expandedScenes: Record<string, boolean>;
  toggleScene: (id: string) => void;
  llmReviewLoading: boolean;
  llmReviewMessage: string | null;
  hasAnyMissingLlm: boolean;
  handleRunLlmReview: () => Promise<void>;
  visualPlanData: any;
  visualPlanLoading: boolean;
  motionPlanData: any;
  motionScenesList: any[];
  filteredMotionScenes: any[];
  motionPlanLoading: boolean;
  copiedMotionSceneId: string | null;
  copiedAllMotion: boolean;
  handleCopyMotionSceneJson: (scene: any, e?: React.MouseEvent) => void;
  handleCopyAllMotionPlanJson: (e?: React.MouseEvent) => void;
  timelineApproval: any;
  actionMessage: string | null;
  actionLoading: boolean;
  renderVideo: any;
  onRunStage?: (stageId: string) => void;
  onRetryStage?: (stageId: string) => void;
  handleApproveTimeline: (decision: 'approved' | 'changes_requested') => Promise<void>;
  setActiveTab: (t: 'overview' | 'scenes' | 'subtasks' | 'agent' | 'artifacts' | 'logs' | 'about') => void;
}

export const StageContentRouter: React.FC<StageContentRouterProps> = ({
  activeTab,
  config,
  state,
  projectId,
  isFullPage,
  isPipelineRunning,
  isRunning,
  isRetrying,
  isCompleted,
  isFailed,
  isBlocked,
  isStaleProgress,
  elapsedSec,
  subSteps,
  subDone,
  realSub,
  setRealSub,
  sceneData,
  scenesList,
  filteredScenes,
  sceneSearch,
  setSceneSearch,
  sceneLoading,
  expandedScenes,
  toggleScene,
  llmReviewLoading,
  llmReviewMessage,
  hasAnyMissingLlm,
  handleRunLlmReview,
  visualPlanData,
  visualPlanLoading,
  motionPlanData,
  motionScenesList,
  filteredMotionScenes,
  motionPlanLoading,
  copiedMotionSceneId,
  copiedAllMotion,
  handleCopyMotionSceneJson,
  handleCopyAllMotionPlanJson,
  timelineApproval,
  actionMessage,
  actionLoading,
  renderVideo,
  onRunStage,
  onRetryStage,
  handleApproveTimeline,
  setActiveTab
}) => {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
      minWidth: 0,
      flex: 1,
    }}>
      {/* Audio & Transcript Tab */}
      {activeTab === 'scenes' && config.id === 'analyzer' && projectId && (
        <AudioAnalyzerView projectId={projectId} refreshKey={state?.status} isFullPage={isFullPage} />
      )}

      {/* Scenes & Script Tab */}
      {activeTab === 'scenes' && config.id === 'segmentation' && (
        <SegmentationSceneTable
          config={config}
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
          onRetryStage={onRetryStage}
          isFullPage={isFullPage}
        />
      )}

      {/* Collected Media */}
      {activeTab === 'scenes' && config.id === 'assets' && (
        <AssetsView projectId={projectId} refreshKey={state?.status} />
      )}

      {/* Visual Planning */}
      {activeTab === 'scenes' && config.id === 'planning' && (
        <VisualPlanningView data={visualPlanData} loading={visualPlanLoading} />
      )}

      {/* Motion Scenes & Planning Tab */}
      {activeTab === 'scenes' && config.id === 'motion_plan' && (
        <MotionPlanSceneTable
          motionPlanData={motionPlanData}
          motionScenesList={motionScenesList}
          filteredMotionScenes={filteredMotionScenes}
          sceneSearch={sceneSearch}
          setSceneSearch={setSceneSearch}
          motionPlanLoading={motionPlanLoading}
          copiedMotionSceneId={copiedMotionSceneId}
          copiedAllMotion={copiedAllMotion}
          handleCopyMotionSceneJson={handleCopyMotionSceneJson}
          handleCopyAllMotionPlanJson={handleCopyAllMotionPlanJson}
          onRunStage={onRunStage}
        />
      )}

      {/* Specialized: Frame-Accurate Visual Timeline */}
      {activeTab === 'scenes' && config.id === 'timeline' && projectId && (
        <TimelineBuildVisualView
          projectId={projectId}
          onRetryTimeline={() => onRetryStage ? onRetryStage('timeline') : onRunStage?.('timeline')}
          isPipelineRunning={isPipelineRunning}
        />
      )}

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <StageOverviewTab
          config={config}
          state={state}
          isCompleted={isCompleted}
          isRunning={isRunning}
          isRetrying={isRetrying}
          isFailed={isFailed}
          isBlocked={isBlocked}
          isStaleProgress={isStaleProgress}
          isFullPage={isFullPage}
          projectId={projectId}
          elapsedSec={elapsedSec}
          formatElapsedSeconds={formatElapsedSeconds}
          subSteps={subSteps}
          subDone={subDone}
          timelineApproval={timelineApproval}
          actionMessage={actionMessage}
          actionLoading={actionLoading}
          renderVideo={renderVideo}
          onRetryStage={onRetryStage}
          handleApproveTimeline={handleApproveTimeline}
          setActiveTab={setActiveTab}
        />
      )}

      {/* Subtasks Tab */}
      {activeTab === 'subtasks' && (
        <StageSubtasksTab
          projectId={projectId}
          config={config}
          isFullPage={isFullPage}
          subSteps={subSteps}
          realSub={realSub}
          setRealSub={setRealSub}
          isRunning={isRunning}
        />
      )}

      {/* Agent Tab */}
      {activeTab === 'agent' && (
        <StageAgentTab config={config} isFullPage={isFullPage} />
      )}

      {/* Artifacts Tab */}
      {activeTab === 'artifacts' && (
        <StageArtifactsTab state={state} isFullPage={isFullPage} />
      )}

      {/* Live Logs Tab */}
      {activeTab === 'logs' && (
        <StageLogsTab config={config} state={state} isFullPage={isFullPage} isCompleted={isCompleted} />
      )}

      {/* About Tab */}
      {activeTab === 'about' && (
        <AgentAboutTab
          stageId={config.id}
          agentId={config.agentId}
          isFullPage={isFullPage}
        />
      )}
    </div>
  );
};
