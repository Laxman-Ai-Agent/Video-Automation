import React, { useState, useEffect } from 'react';
import { 
  CANONICAL_12_STAGES, 
  StageState, 
  StageConfig 
} from '../types/pipeline';
import { 
  computeSubStagesState, 
  SubStageState 
} from '../types/subStages';
import { ExecutionTrackingHeader } from './stage-tracking/ExecutionTrackingHeader';
import { SubStageCardItem } from './stage-tracking/SubStageCardItem';

interface StageExecutionTrackingProps {
  stages: Record<string, StageState>;
  currentStageId: string;
  selectedStageId?: string | null;
  onSelectStage?: (stageId: string) => void;
  isPipelineRunning?: boolean;
  onOpenAudioAnalysis?: () => void;
  onOpenStageDetails?: (stageId: string) => void;
  onRunStage?: (stageId: string) => void;
  onStopStage?: (stageId: string) => void;
}

function formatElapsedSeconds(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

export const StageExecutionTracking: React.FC<StageExecutionTrackingProps> = React.memo(({
  stages,
  currentStageId,
  selectedStageId,
  onSelectStage: _onSelectStage,
  isPipelineRunning: _isPipelineRunning = false,
  onOpenAudioAnalysis,
  onOpenStageDetails,
  onRunStage,
  onStopStage
}) => {
  // Prioritize explicitly selected stage card if clicked, otherwise follow the currently executing pipeline stage
  const activeTargetId = selectedStageId || currentStageId || 'analyzer';

  const targetConfig: StageConfig = CANONICAL_12_STAGES.find((s) => s.id === activeTargetId) || CANONICAL_12_STAGES[0];
  const targetState: StageState | undefined = stages[activeTargetId];

  const stageStatus = targetState?.status || 'waiting';
  const stagePercentage = targetState?.percentage !== null && targetState?.percentage !== undefined
    ? targetState.percentage
    : (stageStatus === 'completed' ? 100 : 0);

  const isRunning = stageStatus === 'running';
  const isRetrying = stageStatus === 'retrying' || stageStatus === 'recovering';
  const isFailed = stageStatus === 'failed';
  const isBlocked = stageStatus === 'blocked';
  const isCompleted = stageStatus === 'completed';

  // Live timer for elapsed duration
  const [elapsedSec, setElapsedSec] = useState<number>(0);
  const [nowTs, setNowTs] = useState<number>(Date.now());

  useEffect(() => {
    if (!isRunning && !isRetrying) {
      if (targetState?.durationMs) {
        setElapsedSec(targetState.durationMs / 1000);
      }
      return;
    }

    const start = targetState?.startedAt ? new Date(targetState.startedAt).getTime() : Date.now();
    const tick = () => {
      const current = Date.now();
      setNowTs(current);
      setElapsedSec(Math.max(0, (current - start) / 1000));
    };

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [isRunning, isRetrying, targetState?.startedAt, targetState?.durationMs]);

  // Stale progress detection (>30s without update while running)
  const lastActiveTs = targetState?.lastActivityAt 
    ? new Date(targetState.lastActivityAt).getTime() 
    : (targetState?.startedAt ? new Date(targetState.startedAt).getTime() : null);
  const isStaleProgress = isRunning && lastActiveTs !== null && (nowTs - lastActiveTs > 30000);

  // Compute sub-stages dynamically in authoritative execution order
  const subStages: SubStageState[] = computeSubStagesState(activeTargetId, targetState);
  const completedCount = subStages.filter((s) => s.status === 'completed').length;

  return (
    <div 
      data-testid="stage-execution-tracking"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        fontFamily: 'var(--font-sans)'
      }}
    >
      {/* 1. Header Section */}
      <ExecutionTrackingHeader
        targetConfig={targetConfig}
        targetState={targetState}
        activeTargetId={activeTargetId}
        stageStatus={stageStatus}
        isRunning={isRunning}
        isRetrying={isRetrying}
        isFailed={isFailed}
        isBlocked={isBlocked}
        isCompleted={isCompleted}
        isStaleProgress={isStaleProgress}
        subStagesCount={subStages.length}
        completedCount={completedCount}
        elapsedSec={elapsedSec}
        formatElapsedSeconds={formatElapsedSeconds}
        onRunStage={onRunStage}
        onStopStage={onStopStage}
        onOpenStageDetails={onOpenStageDetails}
        onOpenAudioAnalysis={onOpenAudioAnalysis}
      />

      {/* 2. Sequential Sub-Stage Cards in Authoritative Execution Order */}
      <div 
        data-testid="sub-stages-list"
        style={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          paddingRight: '4px'
        }}
      >
        {subStages.map((sub, idx) => (
          <SubStageCardItem
            key={sub.id}
            sub={sub}
            isLast={idx === subStages.length - 1}
          />
        ))}
      </div>
    </div>
  );
}, (prevProps, nextProps) => {
  const prevTarget = prevProps.selectedStageId || prevProps.currentStageId || 'analyzer';
  const nextTarget = nextProps.selectedStageId || nextProps.currentStageId || 'analyzer';
  if (prevTarget !== nextTarget) return false;
  if (prevProps.isPipelineRunning !== nextProps.isPipelineRunning) return false;

  const prevState = prevProps.stages[prevTarget];
  const nextState = nextProps.stages[nextTarget];
  return (
    prevState?.status === nextState?.status &&
    prevState?.percentage === nextState?.percentage &&
    prevState?.currentActivity === nextState?.currentActivity &&
    prevState?.teluguMessage === nextState?.teluguMessage &&
    prevState?.attempt === nextState?.attempt &&
    prevState?.retryReason === nextState?.retryReason &&
    prevState?.failingSubStage === nextState?.failingSubStage &&
    prevState?.errors?.[0] === nextState?.errors?.[0] &&
    prevState?.blockers?.[0] === nextState?.blockers?.[0] &&
    prevState?.lastActivityAt === nextState?.lastActivityAt
  );
});

export default StageExecutionTracking;
