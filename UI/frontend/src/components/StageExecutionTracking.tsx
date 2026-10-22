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
import { 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  AlertTriangle,
  RefreshCw, 
  Cpu, 
  Layers, 
  FileAudio,
  RotateCcw,
  XCircle,
  Activity,
  Play,
  Square
} from 'lucide-react';

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
  onSelectStage,
  isPipelineRunning = false,
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
  const isExecutingCurrent = activeTargetId === currentStageId && isPipelineRunning;

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
      {/* 1. Header Section: Shows the executing Agent & Sub-stage Telemetry */}
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
              Stage {String(targetConfig.order).padStart(2, '0')} ({completedCount}/{subStages.length} Sub-stages)
            </span>
          </div>

          {/* Clear Distinction: Stage Level Progress vs Sub-stage Progress */}
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

          {/* Quick Action Control: Run / Stop / Retry for current/selected stage */}
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
        {activeTargetId === 'analyzer' && onOpenAudioAnalysis && (
          <button
            onClick={onOpenAudioAnalysis}
            data-testid="tracking-open-audio-analysis-btn"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: 'rgba(24, 144, 255, 0.12)',
              border: '1px solid rgba(24, 144, 255, 0.35)',
              borderRadius: 'var(--radius-sm)',
              padding: '7px 10px',
              color: '#FFFFFF',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background-color 0.15s ease'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(24, 144, 255, 0.22)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'rgba(24, 144, 255, 0.12)'; }}
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
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-card)',
              borderRadius: 'var(--radius-sm)',
              padding: '6px 10px',
              color: 'var(--text-secondary)',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
            onMouseEnter={(e) => { 
              e.currentTarget.style.borderColor = 'var(--accent-blue)'; 
              e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={(e) => { 
              e.currentTarget.style.borderColor = 'var(--border-card)'; 
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Layers size={13} color="var(--text-muted)" />
              <span>View Full Stage Details & Logs</span>
            </div>
            <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Inspect →</span>
          </button>
        )}
      </div>

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
        {subStages.map((sub, idx) => {
          const isRunningSub = sub.status === 'running';
          const isCompletedSub = sub.status === 'completed';
          const isFailedSub = sub.status === 'failed';
          const isRetryingSub = sub.status === 'retrying' || sub.status === 'recovering';
          const isBlockedSub = sub.status === 'blocked';
          const isLast = idx === subStages.length - 1;

          return (
            <div 
              key={sub.id} 
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
        })}
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
