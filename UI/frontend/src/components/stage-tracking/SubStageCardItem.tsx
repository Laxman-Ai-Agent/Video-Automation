import React from 'react';
import { 
  CheckCircle2, 
  Activity, 
  RotateCcw, 
  AlertCircle, 
  AlertTriangle, 
  Clock 
} from 'lucide-react';
import { SubStageState } from '../../types/subStages';

export interface SubStageCardItemProps {
  sub: SubStageState;
  isLast: boolean;
}

export const SubStageCardItem: React.FC<SubStageCardItemProps> = ({ sub, isLast }) => {
  const isRunningSub = sub.status === 'running';
  const isCompletedSub = sub.status === 'completed';
  const isFailedSub = sub.status === 'failed';
  const isRetryingSub = sub.status === 'retrying' || sub.status === 'recovering';
  const isBlockedSub = sub.status === 'blocked';

  return (
    <div 
      style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'stretch' 
      }}
    >
      {/* Individual Sub-Stage Card */}
      <div
        data-testid={`sub-stage-card-${sub.id}`}
        style={{
          padding: '9px 12px',
          backgroundColor: isRunningSub 
            ? 'var(--status-running-bg)' 
            : (isRetryingSub ? 'var(--status-retrying-bg)' : (isFailedSub ? 'var(--status-failed-bg)' : 'var(--bg-card)')),
          border: isRunningSub 
            ? '1px solid var(--accent-cyan)' 
            : (isRetryingSub ? '1px solid var(--status-retrying)' : (isFailedSub ? '1px solid var(--status-failed)' : (isCompletedSub ? '1px solid var(--border-subtle)' : '1px solid var(--border-card)'))),
          borderRadius: 'var(--radius-sm)',
          boxShadow: isRunningSub 
            ? '0 0 10px rgba(0, 216, 245, 0.15)' 
            : (isRetryingSub ? '0 0 10px rgba(245, 158, 11, 0.15)' : 'none'),
          transition: 'border-color 0.2s ease, background-color 0.2s ease',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          opacity: sub.status === 'waiting' ? 0.75 : 1
        }}
      >
        {/* Top Row: Order Badge, Sub-stage Name, Status & Sub-stage Progress */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
            {/* Numbered Step Circle */}
            <span style={{
              width: '20px',
              height: '20px',
              borderRadius: '50%',
              backgroundColor: isCompletedSub 
                ? 'var(--status-completed-bg)' 
                : (isRunningSub ? 'var(--accent-cyan)' : (isFailedSub ? 'var(--status-failed-bg)' : 'var(--bg-elevated)')),
              color: isCompletedSub 
                ? 'var(--status-completed)' 
                : (isRunningSub ? '#001529' : (isFailedSub ? 'var(--status-failed)' : 'var(--text-muted)')),
              fontSize: '10px',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              border: isCompletedSub 
                ? '1px solid var(--status-completed)' 
                : (isRunningSub ? '1px solid var(--accent-cyan)' : (isFailedSub ? '1px solid var(--status-failed)' : '1px solid var(--border-card)'))
            }}>
              {sub.order}
            </span>

            {/* Sub-Stage Name */}
            <span 
              title={sub.label}
              style={{
                fontSize: '12px',
                fontWeight: isRunningSub ? 700 : (isCompletedSub ? 600 : 500),
                color: isRunningSub 
                  ? 'var(--accent-cyan)' 
                  : (isCompletedSub ? 'var(--text-primary)' : (isFailedSub ? 'var(--status-failed)' : 'var(--text-secondary)')),
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis'
              }}
            >
              {sub.label}
            </span>
          </div>

          {/* Status Indicator & Sub-stage Progress Label */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
            {isCompletedSub && (
              <span style={{
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                fontSize: '11px',
                fontWeight: 600,
                color: 'var(--status-completed)'
              }}>
                <CheckCircle2 size={13} color="var(--status-completed)" />
                100%
              </span>
            )}

            {isRunningSub && (
              <span style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '11px',
                fontWeight: 700,
                color: 'var(--accent-cyan)',
                fontFamily: 'var(--font-mono)'
              }}>
                <Activity size={12} className="animate-spin" color="var(--accent-cyan)" />
                <span>Sub: {sub.percentage}%</span>
              </span>
            )}

            {isRetryingSub && (
              <span style={{
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                fontSize: '11px',
                fontWeight: 700,
                color: 'var(--status-retrying)'
              }}>
                <RotateCcw size={12} className="animate-spin" color="var(--status-retrying)" />
                Retry
              </span>
            )}

            {isFailedSub && (
              <span style={{
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                fontSize: '11px',
                fontWeight: 700,
                color: 'var(--status-failed)'
              }}>
                <AlertCircle size={13} color="var(--status-failed)" />
                Failed
              </span>
            )}

            {isBlockedSub && (
              <span style={{
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                fontSize: '11px',
                fontWeight: 700,
                color: 'var(--status-blocked)'
              }}>
                <AlertTriangle size={13} color="var(--status-blocked)" />
                Blocked
              </span>
            )}

            {sub.status === 'waiting' && (
              <span style={{
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                fontSize: '11px',
                color: 'var(--text-muted)'
              }}>
                <Clock size={11} color="var(--text-muted)" />
                Pending
              </span>
            )}
          </div>
        </div>

        {/* Smooth Progress Bar for Running or Completed Sub-stages Only */}
        {(isRunningSub || isCompletedSub) && (
          <div style={{
            width: '100%',
            height: '3px',
            backgroundColor: 'var(--bg-elevated)',
            borderRadius: '2px',
            overflow: 'hidden'
          }}>
            <div style={{
              height: '100%',
              width: `${sub.percentage}%`,
              backgroundColor: isCompletedSub ? 'var(--status-completed)' : 'var(--accent-cyan)',
              transition: 'width 0.25s ease'
            }} />
          </div>
        )}

        {/* Real-time Sub-Stage Activity Telemetry */}
        {(isRunningSub || isRetryingSub || isFailedSub) && sub.description && (
          <div style={{
            fontSize: '10px',
            color: isFailedSub ? 'var(--status-failed)' : (isRetryingSub ? 'var(--status-retrying)' : 'var(--text-secondary)'),
            fontFamily: 'var(--font-mono)',
            lineHeight: 1.35,
            backgroundColor: isFailedSub ? 'rgba(239, 68, 68, 0.08)' : (isRetryingSub ? 'rgba(245, 158, 11, 0.08)' : 'rgba(0, 216, 245, 0.06)'),
            padding: '3px 6px',
            borderRadius: '3px',
            borderLeft: `2px solid ${isFailedSub ? 'var(--status-failed)' : (isRetryingSub ? 'var(--status-retrying)' : 'var(--accent-cyan)')}`
          }}>
            {sub.description}
          </div>
        )}
      </div>

      {/* Sequential Connector to Next Sub-Stage Card */}
      {!isLast && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          height: '14px',
          justifyContent: 'center',
          margin: '1px 0',
          position: 'relative'
        }}>
          <div style={{
            width: '2px',
            height: '100%',
            backgroundColor: isCompletedSub 
              ? 'var(--status-completed)' 
              : (isRunningSub ? 'var(--accent-cyan)' : 'var(--border-card)'),
            opacity: sub.status === 'waiting' ? 0.4 : 1,
            transition: 'background-color 0.2s ease, opacity 0.2s ease',
            position: 'relative'
          }}>
            {/* Small downward indicator chevron */}
            <div style={{
              position: 'absolute',
              bottom: '-2px',
              left: '50%',
              transform: 'translateX(-50%)',
              width: 0,
              height: 0,
              borderLeft: '3px solid transparent',
              borderRight: '3px solid transparent',
              borderTop: `4px solid ${isCompletedSub ? 'var(--status-completed)' : (isRunningSub ? 'var(--accent-cyan)' : 'var(--border-card)')}`
            }} />
          </div>
        </div>
      )}
    </div>
  );
};
