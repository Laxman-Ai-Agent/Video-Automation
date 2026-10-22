import React from 'react';
import { CANONICAL_12_STAGES, StageState } from '../types/pipeline';
import { CheckCircle, Clock, AlertCircle, RefreshCw } from 'lucide-react';

interface StageRankingListProps {
  stages: Record<string, StageState>;
  onSelectStage: (stageId: string) => void;
  selectedStageId?: string | null;
}

export const StageRankingList: React.FC<StageRankingListProps> = ({
  stages,
  onSelectStage,
  selectedStageId
}) => {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%'
    }}>
      <h3 style={{
        fontSize: '14px',
        fontWeight: 600,
        color: 'var(--text-primary)',
        marginBottom: '16px'
      }}>
        Stage Execution Ranking
      </h3>

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        {CANONICAL_12_STAGES.map((cfg, idx) => {
          const rank = idx + 1;
          const st = stages[cfg.id];
          const status = st?.status || 'waiting';
          const pct = st?.percentage !== null && st?.percentage !== undefined ? `${st.percentage}%` : '-';
          const isSelected = selectedStageId === cfg.id;
          const isTopThree = rank <= 3;

          return (
            <div
              key={cfg.id}
              onClick={() => onSelectStage(cfg.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 8px',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                backgroundColor: isSelected ? 'var(--status-running-bg)' : 'transparent',
                transition: 'background-color 0.15s ease'
              }}
              onMouseEnter={(e) => {
                if (!isSelected) e.currentTarget.style.backgroundColor = 'var(--bg-elevated)';
              }}
              onMouseLeave={(e) => {
                if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', overflow: 'hidden' }}>
                {/* Number Badge */}
                <div style={{
                  width: '20px',
                  height: '20px',
                  borderRadius: '50%',
                  backgroundColor: isTopThree ? 'var(--accent-blue)' : 'var(--bg-elevated)',
                  color: isTopThree ? '#FFFFFF' : 'var(--text-muted)',
                  fontSize: '12px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  {rank}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{
                    fontSize: '13px',
                    color: isSelected ? 'var(--accent-blue)' : 'var(--text-primary)',
                    fontWeight: isSelected ? 600 : 500,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}>
                    {cfg.label}
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    {cfg.agentName}
                  </span>
                </div>
              </div>

              {/* Status / Percentage */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                {status === 'completed' && (
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    color: 'var(--status-completed)',
                    backgroundColor: 'var(--status-completed-bg)',
                    padding: '2px 6px',
                    borderRadius: '3px',
                    border: '1px solid var(--status-completed-border)'
                  }}>
                    100%
                  </span>
                )}
                {status === 'running' && (
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    color: 'var(--status-running)',
                    backgroundColor: 'var(--status-running-bg)',
                    padding: '2px 6px',
                    borderRadius: '3px',
                    border: '1px solid var(--status-running-border)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '3px'
                  }}>
                    <RefreshCw size={10} className="animate-spin" />
                    {pct}
                  </span>
                )}
                {status === 'waiting' && (
                  <span style={{
                    fontSize: '11px',
                    color: 'var(--text-muted)',
                    fontFamily: 'var(--font-mono)'
                  }}>
                    Ready
                  </span>
                )}
                {status === 'failed' && (
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    color: 'var(--status-failed)',
                    backgroundColor: 'var(--status-failed-bg)',
                    padding: '2px 6px',
                    borderRadius: '3px',
                    border: '1px solid var(--status-failed-border)'
                  }}>
                    Error
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
