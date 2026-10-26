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
  Terminal,
  Code
} from 'lucide-react';
import { StageConfig, StageState } from '../types/pipeline';
import { StageDrawerHeader } from './stage-views/StageDrawerHeader';
import { StageRightNavBar } from './stage-views/StageRightNavBar';
import { StageContentRouter } from './stage-views/StageContentRouter';
import { useStageDrawerData } from './stage-views/useStageDrawerData';
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
  const [rightNavCollapsed, setRightNavCollapsed] = useState<boolean>(false);

  useEffect(() => {
    setActiveTab('subtasks');
  }, [config.id]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Use custom hook for all drawer data fetching and scene state operations
  const drawerData = useStageDrawerData({
    config,
    state,
    projectId,
    onRunStage
  });

  const {
    isRunning,
    isRetrying,
    isCompleted,
    isFailed,
    isBlocked,
    isCancelled,
    percentage,
    scenesList,
    visualScenesList,
    motionScenesList,
    subSteps,
    hasAnyMissingLlm,
    handleRunLlmReview,
    llmReviewLoading,
    actionMessage
  } = drawerData;

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
    ...(config.id === 'motion_gen' ? [{
      id: 'scenes',
      label: 'Generated Scenes',
      icon: <Code size={18} strokeWidth={activeTab === 'scenes' ? 2.3 : 1.8} />
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
          isStaleProgress={drawerData.isStaleProgress}
          elapsedSec={drawerData.elapsedSec}
          subSteps={subSteps}
          subDone={drawerData.subDone}
          realSub={drawerData.realSub}
          setRealSub={drawerData.setRealSub}
          sceneData={drawerData.sceneData}
          scenesList={scenesList}
          filteredScenes={drawerData.filteredScenes}
          sceneSearch={drawerData.sceneSearch}
          setSceneSearch={drawerData.setSceneSearch}
          sceneLoading={drawerData.sceneLoading}
          expandedScenes={drawerData.expandedScenes}
          toggleScene={drawerData.toggleScene}
          llmReviewLoading={llmReviewLoading}
          llmReviewMessage={drawerData.llmReviewMessage}
          hasAnyMissingLlm={hasAnyMissingLlm}
          handleRunLlmReview={handleRunLlmReview}
          visualPlanData={drawerData.visualPlanData}
          visualPlanLoading={drawerData.visualPlanLoading}
          motionPlanData={drawerData.motionPlanData}
          motionScenesList={motionScenesList}
          filteredMotionScenes={drawerData.filteredMotionScenes}
          motionPlanLoading={drawerData.motionPlanLoading}
          copiedMotionSceneId={drawerData.copiedMotionSceneId}
          copiedAllMotion={drawerData.copiedAllMotion}
          handleCopyMotionSceneJson={drawerData.handleCopyMotionSceneJson}
          handleCopyAllMotionPlanJson={drawerData.handleCopyAllMotionPlanJson}
          timelineApproval={drawerData.timelineApproval}
          actionMessage={actionMessage}
          actionLoading={drawerData.actionLoading}
          renderVideo={drawerData.renderVideo}
          onRunStage={onRunStage}
          onRetryStage={onRetryStage}
          handleApproveTimeline={drawerData.handleApproveTimeline}
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
