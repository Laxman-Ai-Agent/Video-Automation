import React from 'react';
import { 
  ArrowLeft, 
  Activity, 
  RotateCcw, 
  XCircle, 
  AlertTriangle, 
  CheckCircle2, 
  RefreshCw, 
  Sparkles, 
  Square, 
  Play, 
  X 
} from 'lucide-react';
import { StageConfig, StageState } from '../../types/pipeline';
import styles from './StageDrawerHeader.module.css';

export interface StageDrawerHeaderProps {
  config: StageConfig;
  state?: StageState;
  isFullPage: boolean;
  onClose: () => void;
  onRunStage?: (stageId: string) => void;
  onStopStage?: (stageId: string) => void;
  onRetryStage?: (stageId: string) => void;
  isPipelineRunning: boolean;
  isRunning: boolean;
  isRetrying: boolean;
  isFailed: boolean;
  isBlocked: boolean;
  isCancelled: boolean;
  isCompleted: boolean;
  scenesList: any[];
  hasAnyMissingLlm: boolean;
  handleRunLlmReview: () => void;
  llmReviewLoading: boolean;
  actionMessage: string | null;
  percentage: string;
}

export const StageDrawerHeader: React.FC<StageDrawerHeaderProps> = ({
  config,
  state,
  isFullPage,
  onClose,
  onRunStage,
  onStopStage,
  onRetryStage,
  isPipelineRunning,
  isRunning,
  isRetrying,
  isFailed,
  isBlocked,
  isCancelled,
  isCompleted,
  scenesList,
  hasAnyMissingLlm,
  handleRunLlmReview,
  llmReviewLoading,
  actionMessage,
  percentage
}) => {
  return (
    <div
      style={{
        padding: isFullPage ? '14px 20px' : '16px 20px',
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
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
        {/* Left: Back to Pipeline */}
        <button
          onClick={onClose}
          data-testid="stage-drawer-back-btn"
          title="Back to Pipeline Flow (Esc)"
          className={styles.backBtn}
        >
          <ArrowLeft size={13} />
          <span>Back to Pipeline</span>
        </button>

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
        {/* Optional LLM Banner (if applicable for segmentation) */}
        {config.id === 'segmentation' && !hasAnyMissingLlm && scenesList.length > 0 && (
          <div
            data-testid="llm-verification-passed-banner"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <span className={styles.llmBanner}>
              <CheckCircle2 size={13} /> Verified with LLM
            </span>
            <button
              onClick={handleRunLlmReview}
              disabled={llmReviewLoading}
              data-testid="rerun-llm-verification-btn"
              title="Re-run LLM Review"
              className={styles.llmRefreshBtn}
            >
              {llmReviewLoading ? <RefreshCw size={12} className="animate-spin" /> : <Sparkles size={12} />}
            </button>
          </div>
        )}

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
            className={styles.stopBtn}
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
            className={styles.retryBtn}
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
            className={`${styles.runBtn} ${isBlocked || isRunning ? styles.runBtnDisabled : styles.runBtnActive}`}
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
            className={styles.rerunBtn}
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
          className={styles.closeBtn}
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );
};
