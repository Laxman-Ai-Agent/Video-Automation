import React from 'react';
import styles from '../StageCard.module.css';
import { StageConfig, StageState } from '../../types/pipeline';

const RING_R = 19;
const RING_C = 2 * Math.PI * RING_R;

export interface StageProgressRingProps {
  config: StageConfig;
  state?: StageState;
  isRunning: boolean;
  isCompleted: boolean;
  isRetrying: boolean;
  isFailed: boolean;
  hasPct: boolean;
  percentage: string;
}

export const StageProgressRing: React.FC<StageProgressRingProps> = ({
  config,
  state,
  isRunning,
  isCompleted,
  isRetrying,
  isFailed,
  hasPct,
  percentage
}) => {
  if (isRunning) {
    return (
      <div data-testid={`stage-progress-ring-${config.id}`} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{ position: 'relative', width: '48px', height: '48px', flexShrink: 0 }}>
          <div className={hasPct ? undefined : 'animate-spin'} style={{ width: '48px', height: '48px' }}>
            <svg width="48" height="48" viewBox="0 0 48 48" style={{ transform: 'rotate(-90deg)', display: 'block' }}>
              <circle cx="24" cy="24" r={RING_R} fill="none" stroke="var(--border-card)" strokeWidth="4" />
              <circle
                cx="24" cy="24" r={RING_R} fill="none" stroke="var(--status-running)" strokeWidth="4" strokeLinecap="round"
                strokeDasharray={RING_C}
                strokeDashoffset={RING_C * (1 - (hasPct ? Math.min(100, Math.max(0, state!.percentage as number)) : 25) / 100)}
                style={{ transition: 'stroke-dashoffset 0.6s ease' }}
              />
            </svg>
          </div>
          <span
            className="animate-blink-text"
            style={{
              position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '11px', fontWeight: 700, color: 'var(--status-running)', fontFamily: 'var(--font-mono)'
            }}
          >
            {hasPct ? `${Math.round(state!.percentage as number)}%` : '…'}
          </span>
        </div>
        <span aria-hidden="true" style={{ display: 'inline-flex', color: 'var(--accent-cyan)', fontSize: '16px', fontWeight: 700 }}>
          <span className="animate-arrow-flow">›</span>
          <span className="animate-arrow-flow" style={{ animationDelay: '0.18s' }}>›</span>
          <span className="animate-arrow-flow" style={{ animationDelay: '0.36s' }}>›</span>
        </span>
      </div>
    );
  }

  return (
    <div 
      className={styles.percentageNumber}
      style={{
        color: isCompleted 
          ? 'var(--status-completed)' 
          : isRunning 
            ? 'var(--status-running)' 
            : isRetrying
              ? 'var(--status-retrying)'
              : isFailed
                ? 'var(--status-failed)'
                : 'var(--text-primary)'
      }}
    >
      {percentage}
    </div>
  );
};
