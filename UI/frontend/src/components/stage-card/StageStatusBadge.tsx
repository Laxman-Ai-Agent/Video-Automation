import React from 'react';
import styles from '../StageCard.module.css';
import { 
  CheckCircle2, 
  Clock, 
  Loader2, 
  AlertTriangle, 
  XCircle, 
  RotateCcw
} from 'lucide-react';
import { StageConfig, StageState, StageStatus } from '../../types/pipeline';

export interface StageStatusBadgeProps {
  config: StageConfig;
  state?: StageState;
  status: StageStatus;
  isCompleted: boolean;
  isRetrying: boolean;
  isRunning: boolean;
  isFailed: boolean;
  isBlocked: boolean;
  isCancelled: boolean;
}

export const StageStatusBadge: React.FC<StageStatusBadgeProps> = ({
  config,
  state,
  status,
  isCompleted,
  isRetrying,
  isRunning,
  isFailed,
  isBlocked,
  isCancelled
}) => {
  if (state?.stuck && !isCompleted && !isFailed) {
    return (
      <span data-testid={`stage-status-${config.id}`} className={styles.badge} style={{
        color: '#FDBA74', backgroundColor: 'rgba(249, 115, 22, 0.14)',
        border: '1px solid rgba(249, 115, 22, 0.4)'
      }}>
        <Clock size={11} />
        STUCK
      </span>
    );
  }
  if (isCompleted) {
    return (
      <span className={styles.badge} style={{ 
        color: 'var(--status-completed)', 
        backgroundColor: 'var(--status-completed-bg)', 
        border: '1px solid var(--status-completed-border)'
      }}>
        <CheckCircle2 size={12} />
        {(state?.issueWarnings || 0) > 0 ? 'WARNING' : 'COMPLETED'}
      </span>
    );
  }
  if (isRetrying) {
    return (
      <span className={styles.badge} style={{ 
        color: 'var(--status-retrying)', 
        backgroundColor: 'var(--status-retrying-bg)', 
        border: '1px solid var(--status-retrying-border)'
      }}>
        <RotateCcw size={12} className="animate-spin" />
        {state?.attempt ? `RETRY (${state.attempt})` : 'RETRYING'}
      </span>
    );
  }
  if (isRunning) {
    return (
      <span className={styles.badge} style={{ 
        color: 'var(--status-running)', 
        backgroundColor: 'var(--status-running-bg)', 
        border: '1px solid var(--status-running-border)'
      }}>
        <span 
          className="animate-pulse-dot" 
          style={{ 
            width: '6px', 
            height: '6px', 
            borderRadius: '50%', 
            backgroundColor: 'var(--accent-cyan)' 
          }} 
        />
        <Loader2 size={12} className="animate-spin" />
        RUNNING
      </span>
    );
  }
  if (isFailed) {
    return (
      <span className={styles.badge} style={{ 
        color: 'var(--status-failed)', 
        backgroundColor: 'var(--status-failed-bg)', 
        border: '1px solid var(--status-failed-border)'
      }}>
        <XCircle size={12} />
        ERROR
      </span>
    );
  }
  if (isBlocked) {
    return (
      <span className={styles.badge} style={{ 
        color: 'var(--status-blocked)', 
        backgroundColor: 'var(--status-blocked-bg)', 
        border: '1px solid var(--status-blocked-border)'
      }}>
        <AlertTriangle size={12} />
        BLOCKED
      </span>
    );
  }
  if (isCancelled) {
    return (
      <span className={styles.badge} style={{ 
        color: 'var(--status-cancelled)', 
        backgroundColor: 'var(--status-cancelled-bg)', 
        border: '1px solid var(--status-cancelled-border)'
      }}>
        <XCircle size={12} />
        STOPPED
      </span>
    );
  }
  return (
    <span className={styles.badge} style={{ 
      color: 'var(--text-muted)', 
      backgroundColor: 'var(--status-waiting-bg)', 
      border: '1px solid var(--status-waiting-border)',
      fontWeight: 500
    }}>
      <Clock size={11} />
      {(status as string) === 'waiting_for_approval' ? 'NEEDS APPROVAL' : (state?.waitingFor ? 'WAITING' : 'READY')}
    </span>
  );
};
