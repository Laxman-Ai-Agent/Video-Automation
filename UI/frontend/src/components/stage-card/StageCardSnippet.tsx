import React from 'react';
import styles from '../StageCard.module.css';
import { AlertTriangle, AlertCircle, RotateCcw, Clock } from 'lucide-react';
import { StageConfig, StageState } from '../../types/pipeline';

export interface StageCardSnippetProps {
  config: StageConfig;
  state?: StageState;
  isRunning: boolean;
  isStaleProgress: boolean;
  isFailed: boolean;
  isRetrying: boolean;
  isBlocked: boolean;
}

export const StageCardSnippet: React.FC<StageCardSnippetProps> = ({
  config,
  state,
  isRunning,
  isStaleProgress,
  isFailed,
  isRetrying,
  isBlocked
}) => {
  return (
    <>
      {/* Warning banner for long-running operation without recent progress update */}
      {isStaleProgress && (
        <div 
          title="No recent progress update — checking current status."
          className={styles.statusSnippet}
          style={{
            backgroundColor: 'rgba(245, 158, 11, 0.12)',
            border: '1px solid rgba(245, 158, 11, 0.3)',
            color: '#FBBF24'
          }}
        >
          <AlertTriangle size={10} style={{ flexShrink: 0 }} />
          <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            No recent progress update — checking current status.
          </span>
        </div>
      )}

      {/* Error Preview Snippet */}
      {isFailed && (
        <div 
          title={state?.errors?.[0] || 'Stage execution failed'}
          className={styles.statusSnippet}
          style={{
            backgroundColor: 'var(--status-failed-bg)',
            border: '1px solid var(--status-failed-border)',
            color: 'var(--status-failed)'
          }}
        >
          <AlertCircle size={10} style={{ flexShrink: 0 }} />
          <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {state?.errors?.[0] || (state?.failingSubStage ? `Failed at ${state.failingSubStage}` : 'Execution failed')}
          </span>
        </div>
      )}

      {/* Retrying Status Snippet */}
      {isRetrying && (
        <div 
          title={state?.retryReason || 'Transient failure recovery in progress'}
          className={styles.statusSnippet}
          style={{
            backgroundColor: 'var(--status-retrying-bg)',
            border: '1px solid var(--status-retrying-border)',
            color: 'var(--status-retrying)'
          }}
        >
          <RotateCcw size={10} className="animate-spin" style={{ flexShrink: 0 }} />
          <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {state?.retryReason || (state?.attempt ? `Attempt ${state.attempt} recovery` : 'Recovering...')}
          </span>
        </div>
      )}

      {/* Waiting: its prerequisite stage has not completed */}
      {state?.waitingFor && !isRunning && (
        <div 
          data-testid={`stage-waiting-${config.id}`} 
          title={`Starts after ${state.waitingFor} completes`}
          className={styles.statusSnippet}
          style={{ color: 'var(--text-muted)' }}
        >
          <Clock size={10} style={{ flexShrink: 0 }} />
          <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Waiting for {state.waitingFor}</span>
        </div>
      )}

      {/* Stuck: started but no progress beyond the stage's expected time */}
      {state?.stuck && !isFailed && (
        <div
          data-testid={`stage-stuck-${config.id}`}
          title="No progress beyond the expected time. Open Issues for details."
          className={styles.statusSnippet}
          style={{
            backgroundColor: 'rgba(249, 115, 22, 0.14)', border: '1px solid rgba(249, 115, 22, 0.4)',
            color: '#FDBA74', fontWeight: 700
          }}
        >
          <Clock size={10} style={{ flexShrink: 0 }} />
          <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>STUCK: no progress, see Issues</span>
        </div>
      )}

      {/* Blocked Reason Snippet */}
      {isBlocked && (
        <div 
          title={state?.blockers?.[0] || 'Blocked awaiting prerequisites'}
          className={styles.statusSnippet}
          style={{
            backgroundColor: 'var(--status-blocked-bg)',
            border: '1px solid var(--status-blocked-border)',
            color: 'var(--status-blocked)'
          }}
        >
          <AlertTriangle size={10} style={{ flexShrink: 0 }} />
          <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {state?.blockers?.[0] || 'Awaiting prerequisites'}
          </span>
        </div>
      )}
    </>
  );
};
