import React from 'react';
import { 
  Layers, 
  RefreshCw, 
  RotateCcw, 
  XCircle, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Cpu, 
  Square, 
  Play, 
  FileAudio 
} from 'lucide-react';
import { StageConfig, StageState } from '../../types/pipeline';
import styles from './ExecutionTrackingHeader.module.css';

export interface ExecutionTrackingHeaderProps {
  targetConfig: StageConfig;
  targetState?: StageState;
  activeTargetId: string;
  stageStatus: string;
  isRunning: boolean;
  isRetrying: boolean;
  isFailed: boolean;
  isBlocked: boolean;
  isCompleted: boolean;
  isStaleProgress: boolean;
  subStagesCount: number;
  completedCount: number;
  elapsedSec: number;
  formatElapsedSeconds: (s: number) => string;
  onRunStage?: (stageId: string) => void;
  onStopStage?: (stageId: string) => void;
  onOpenStageDetails?: (stageId: string) => void;
  onOpenAudioAnalysis?: () => void;
}

export const ExecutionTrackingHeader: React.FC<ExecutionTrackingHeaderProps> = ({
  targetConfig,
  targetState,
  activeTargetId,
  isRunning,
  isRetrying,
  isFailed,
  isBlocked,
  isCompleted,
  isStaleProgress,
  subStagesCount,
  completedCount,
  elapsedSec,
  formatElapsedSeconds,
  onRunStage,
  onStopStage,
  onOpenStageDetails,
  onOpenAudioAnalysis
}) => {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      marginBottom: '14px',
      paddingBottom: '12px',
      borderBottom: '1px solid var(--border-card)'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <h3 style={{
          fontSize: '14px',
          fontWeight: 700,
          color: 'var(--text-primary)',
          letterSpacing: '-0.2px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Layers size={16} color="var(--accent-cyan)" />
          Stage Execution Tracking
        </h3>

        {/* Authoritative Status Badge */}
        {isRunning ? (
          <span style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            fontSize: '10px',
            fontWeight: 700,
            color: 'var(--accent-cyan)',
            backgroundColor: 'var(--status-running-bg)',
            padding: '2px 8px',
            borderRadius: '4px',
            border: '1px solid var(--status-running-border)'
          }}>
            <span className="animate-pulse-dot" style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--accent-cyan)' }} />
            <RefreshCw size={10} className="animate-spin" />
            LIVE EXECUTION
          </span>
        ) : isRetrying ? (
          <span style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '10px',
            fontWeight: 700,
            color: 'var(--status-retrying)',
            backgroundColor: 'var(--status-retrying-bg)',
            padding: '2px 8px',
            borderRadius: '4px',
            border: '1px solid var(--status-retrying-border)'
          }}>
            <RotateCcw size={10} className="animate-spin" />
            RETRYING {targetState?.attempt ? `(${targetState.attempt})` : ''}
          </span>
        ) : isFailed ? (
          <span style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '10px',
            fontWeight: 700,
            color: 'var(--status-failed)',
            backgroundColor: 'var(--status-failed-bg)',
            padding: '2px 8px',
            borderRadius: '4px',
            border: '1px solid var(--status-failed-border)'
          }}>
            <XCircle size={10} />
            FAILED
          </span>
        ) : isBlocked ? (
          <span style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '10px',
            fontWeight: 700,
            color: 'var(--status-blocked)',
            backgroundColor: 'var(--status-blocked-bg)',
            padding: '2px 8px',
            borderRadius: '4px',
            border: '1px solid var(--status-blocked-border)'
          }}>
            <AlertTriangle size={10} />
            BLOCKED
          </span>
        ) : isCompleted ? (
          <span style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '10px',
            fontWeight: 700,
            color: 'var(--status-completed)',
            backgroundColor: 'var(--status-completed-bg)',
            padding: '2px 8px',
            borderRadius: '4px',
            border: '1px solid var(--status-completed-border)'
          }}>
            <CheckCircle2 size={10} />
            COMPLETED
          </span>
        ) : (
          <span style={{
            fontSize: '11px',
            fontWeight: 600,
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
            <Clock size={11} />
            READY
          </span>
        )}
      </div>

      {/* Executing Agent Identity Badge & Stage Progress Distinction */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        backgroundColor: 'var(--bg-elevated)',
        padding: '8px 10px',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-subtle)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Cpu size={13} color="var(--accent-blue)" />
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
              {targetConfig.agentName}
            </span>
          </div>

          <span style={{
            fontSize: '10px',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-secondary)'
          }}>
            Stage {String(targetConfig.order).padStart(2, '0')} ({completedCount}/{subStagesCount} Sub-stages)
          </span>
        </div>

        {/* Distinction: Stage Level Progress vs Sub-stage Progress */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '11px',
          color: 'var(--text-secondary)',
          borderTop: '1px dashed var(--border-card)',
          paddingTop: '6px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Stage Progress:</span>
            <span style={{ 
              fontFamily: 'var(--font-mono)', 
              fontWeight: 700, 
              color: isCompleted ? 'var(--status-completed)' : (isRunning ? 'var(--status-running)' : 'var(--text-primary)') 
            }}>
              {targetState?.percentage !== null && targetState?.percentage !== undefined ? `${targetState.percentage}%` : (isCompleted ? '100%' : '—')}
            </span>
          </div>

          {elapsedSec > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontFamily: 'var(--font-mono)', fontSize: '10px' }}>
              <Clock size={10} color="var(--text-muted)" />
              <span>Elapsed: {formatElapsedSeconds(elapsedSec)}</span>
            </div>
          )}
        </div>

        {/* Quick Action Control: Run / Stop / Retry */}
        {(onRunStage || onStopStage) && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderTop: '1px dashed var(--border-card)',
            paddingTop: '6px',
            marginTop: '2px'
          }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Stage Control:
            </span>

            {isRunning || isRetrying ? (
              <button
                onClick={() => onStopStage && onStopStage(activeTargetId)}
                data-testid="tracking-stop-btn"
                title={`Stop ${targetConfig.label}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '3px 8px',
                  backgroundColor: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  borderRadius: '4px',
                  color: '#EF4444',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                <Square size={10} fill="currentColor" />
                <span>Stop Stage</span>
              </button>
            ) : isFailed ? (
              <button
                onClick={() => onRunStage && onRunStage(activeTargetId)}
                data-testid="tracking-run-btn"
                title={`Retry ${targetConfig.label}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '3px 8px',
                  backgroundColor: 'rgba(255, 77, 79, 0.15)',
                  border: '1px solid rgba(255, 77, 79, 0.4)',
                  borderRadius: '4px',
                  color: 'var(--status-failed)',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                <RotateCcw size={10} />
                <span>Retry Stage</span>
              </button>
            ) : (
              <button
                onClick={() => onRunStage && !isBlocked && !isRunning && onRunStage(activeTargetId)}
                disabled={isBlocked || isRunning}
                data-testid="tracking-run-btn"
                title={isBlocked ? (targetState?.blockers?.[0] || 'Prerequisites required') : (isRunning ? 'Stage is running' : `Run ${targetConfig.label}`)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '4px 10px',
                  backgroundColor: isBlocked || isRunning ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 216, 245, 0.18)',
                  border: `1px solid ${isBlocked || isRunning ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 216, 245, 0.4)'}`,
                  borderRadius: '4px',
                  color: isBlocked || isRunning ? 'var(--text-muted)' : 'var(--accent-cyan)',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: isBlocked || isRunning ? 'not-allowed' : 'pointer',
                  opacity: isBlocked || isRunning ? 0.6 : 1,
                  boxShadow: (!isBlocked && !isRunning) ? '0 0 8px rgba(0, 216, 245, 0.25)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                {isCompleted ? <RotateCcw size={10} /> : <Play size={10} fill="currentColor" />}
                <span>{isCompleted ? 'Rerun Stage' : 'Run Stage'}</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Warning: Long-running task without recent progress update */}
      {isStaleProgress && (
        <div 
          data-testid="stale-progress-warning"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 10px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'rgba(245, 158, 11, 0.12)',
            border: '1px solid rgba(245, 158, 11, 0.35)',
            color: '#FBBF24',
            fontSize: '11px',
            fontWeight: 600,
            lineHeight: 1.3
          }}
        >
          <AlertTriangle size={13} style={{ flexShrink: 0 }} />
          <span>No recent progress update — checking current status.</span>
        </div>
      )}

      {/* Prominent Failure Error Banner */}
      {isFailed && (
        <div 
          data-testid="stage-error-banner"
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            padding: '8px 10px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--status-failed-bg)',
            border: '1px solid var(--status-failed-border)',
            color: 'var(--status-failed)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '11px' }}>
            <XCircle size={13} />
            <span>
              {targetState?.failingSubStage 
                ? `Failed at Sub-stage: ${targetState.failingSubStage}` 
                : 'Stage Execution Failed'}
            </span>
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-primary)', lineHeight: 1.35 }}>
            {targetState?.errors?.[0] || 'A processing error was reported by the stage agent.'}
          </div>
        </div>
      )}

      {/* Dedicated Audio Analysis Artifact Inspector Button */}
      {activeTargetId === 'analyzer' && (onOpenStageDetails || onOpenAudioAnalysis) && (
        <button
          onClick={() => onOpenStageDetails ? onOpenStageDetails('analyzer') : onOpenAudioAnalysis?.()}
          data-testid="tracking-open-audio-analysis-btn"
          className={styles.openAudioBtn}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <FileAudio size={14} color="var(--accent-blue)" />
            <span>Inspect audio-analysis.json</span>
          </div>
          <span style={{ fontSize: '11px', color: 'var(--accent-cyan)', fontWeight: 700 }}>Open →</span>
        </button>
      )}

      {/* General Stage Inspector Details Button */}
      {onOpenStageDetails && (
        <button
          onClick={() => onOpenStageDetails(activeTargetId)}
          data-testid="tracking-open-stage-details-btn"
          className={styles.openStageDetailsBtn}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={13} color="var(--text-muted)" />
            <span>View Full Stage Details & Logs</span>
          </div>
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Inspect →</span>
        </button>
      )}
    </div>
  );
};
