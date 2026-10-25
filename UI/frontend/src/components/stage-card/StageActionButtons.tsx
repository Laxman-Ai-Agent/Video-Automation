import React from 'react';
import styles from '../StageCard.module.css';
import { Square, RotateCcw, Play } from 'lucide-react';
import { StageConfig, StageState } from '../../types/pipeline';
import { StageStatusBadge, StageStatusBadgeProps } from './StageStatusBadge';

export interface StageActionButtonsProps {
  config: StageConfig;
  state?: StageState;
  isRunning: boolean;
  isRetrying: boolean;
  isFailed: boolean;
  isCompleted: boolean;
  isBlocked: boolean;
  isWaitingForPrevious: boolean;
  isPipelineRunning: boolean;
  onRunStage?: (stageId: string) => void;
  onStopStage?: (stageId: string) => void;
  statusBadgeProps: StageStatusBadgeProps;
}

export const StageActionButtons: React.FC<StageActionButtonsProps> = ({
  config,
  state,
  isRunning,
  isRetrying,
  isFailed,
  isCompleted,
  isBlocked,
  isWaitingForPrevious,
  isPipelineRunning,
  onRunStage,
  onStopStage,
  statusBadgeProps
}) => {
  return (
    <div className={styles.actionGroup}>
      {/* Stop Button while Running */}
      {(isRunning || isRetrying) && onStopStage && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onStopStage(config.id);
          }}
          data-testid={`stage-stop-btn-${config.id}`}
          title={`Stop ${config.label}`}
          className={styles.stopButton}
        >
          <Square size={9} fill="currentColor" />
          <span>STOP</span>
        </button>
      )}

      {/* Retry Button on Failure */}
      {isFailed && onRunStage && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRunStage(config.id);
          }}
          data-testid={`stage-run-btn-${config.id}`}
          title={`Retry ${config.label}`}
          className={`${styles.retryButton} issue-blink`}
        >
          <RotateCcw size={9} />
          <span>RETRY</span>
        </button>
      )}

      {/* Run Button when Ready / Waiting / Cancelled */}
      {!isRunning && !isRetrying && !isFailed && !isCompleted && onRunStage && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (!isBlocked && !isRunning && !isWaitingForPrevious) onRunStage(config.id);
          }}
          disabled={isBlocked || isRunning || isWaitingForPrevious}
          data-testid={`stage-run-btn-${config.id}`}
          title={state?.waitingFor ? `Waits for ${state.waitingFor} to complete` : isBlocked ? (state?.blockers?.[0] || 'Prerequisites required') : (isRunning ? 'Stage is running' : `Run ${config.label}`)}
          className={`${styles.runButton} ${isBlocked || isRunning || isWaitingForPrevious ? styles.runButtonDisabled : styles.runButtonActive}`}
        >
          <Play size={9} fill="currentColor" />
          <span>RUN</span>
        </button>
      )}

      {/* Rerun Button when Completed */}
      {isCompleted && onRunStage && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (!isPipelineRunning) onRunStage(config.id);
          }}
          disabled={isPipelineRunning}
          data-testid={`stage-rerun-btn-${config.id}`}
          title={`Rerun ${config.label}`}
          className={styles.rerunButton}
          style={{ cursor: isPipelineRunning ? 'not-allowed' : 'pointer' }}
        >
          <RotateCcw size={8} />
          <span>RERUN</span>
        </button>
      )}

      <StageStatusBadge {...statusBadgeProps} />
    </div>
  );
};
