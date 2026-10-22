import React, { useState, useEffect } from 'react';
import { 
  CheckCircle2, 
  Clock, 
  Loader2, 
  AlertTriangle, 
  XCircle, 
  RotateCcw,
  Mic, 
  FileAudio, 
  Scissors, 
  Compass,
  Images,
  Film,
  Sparkles, 
  ShieldCheck, 
  Layers, 
  ThumbsUp, 
  Tv, 
  CheckSquare, 
  FolderCheck,
  AlertCircle,
  Play,
  Square
} from 'lucide-react';
import { StageConfig, StageState, StageStatus } from '../types/pipeline';

interface StageCardProps {
  config: StageConfig;
  state?: StageState;
  isSelected: boolean;
  onSelect: () => void;
  onRunStage?: (stageId: string) => void;
  onStopStage?: (stageId: string) => void;
  isPipelineRunning?: boolean;
}

const STAGE_ICONS: Record<string, React.ReactNode> = {
  audio: <Mic size={15} />,
  analyzer: <FileAudio size={15} />,
  segmentation: <Scissors size={15} />,
  planning: <Compass size={15} />,
  assets: <Images size={15} />,
  motion_plan: <Film size={15} />,
  motion_gen: <Sparkles size={15} />,
  motion_validation: <ShieldCheck size={15} />,
  timeline: <Layers size={15} />,
  approval: <ThumbsUp size={15} />,
  render: <Tv size={15} />,
  qc: <CheckSquare size={15} />,
  final: <FolderCheck size={15} />
};

export function formatDuration(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '00:00';
  const totalSec = Math.floor(seconds);
  const hrs = Math.floor(totalSec / 3600);
  const mins = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;
  if (hrs > 0) {
    return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

const RING_R = 19;
const RING_C = 2 * Math.PI * RING_R;

export const StageCard: React.FC<StageCardProps> = React.memo(({
  config,
  state,
  isSelected,
  onSelect,
  onRunStage,
  onStopStage,
  isPipelineRunning = false
}) => {
  const status: StageStatus = state?.status || 'waiting';
  const percentage = state?.percentage !== undefined && state?.percentage !== null 
    ? `${state.percentage}%` 
    : (status === 'completed' ? '100%' : '—');

  const isRunning = status === 'running';
  const hasPct = state?.percentage !== undefined && state?.percentage !== null;
  const isRetrying = status === 'retrying' || status === 'recovering';
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';
  const isBlocked = status === 'blocked';
  const isCancelled = status === 'cancelled';

  // Live timer for elapsed duration while running / retrying
  const [elapsedSec, setElapsedSec] = useState<number>(0);
  const [nowTs, setNowTs] = useState<number>(Date.now());

  useEffect(() => {
    if (!isRunning && !isRetrying) {
      if (state?.durationMs !== undefined && state?.durationMs !== null) {
        setElapsedSec(state.durationMs / 1000);
      } else if (state?.completedAt && state?.startedAt) {
        const start = new Date(state.startedAt).getTime();
        const end = new Date(state.completedAt).getTime();
        if (!isNaN(start) && !isNaN(end) && end >= start) {
          setElapsedSec((end - start) / 1000);
        }
      }
      return;
    }

    const start = state?.startedAt ? new Date(state.startedAt).getTime() : Date.now();
    const tick = () => {
      const current = Date.now();
      setNowTs(current);
      setElapsedSec(Math.max(0, (current - start) / 1000));
    };

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [isRunning, isRetrying, state?.startedAt, state?.completedAt, state?.durationMs]);

  const getTimingDisplay = (): string => {
    // 1. While running, retrying, or recovering: show live elapsed timer
    if (isRunning || isRetrying) {
      if (!state?.startedAt) return 'Timing unavailable';
      const start = new Date(state.startedAt).getTime();
      if (isNaN(start) || start <= 0) return 'Timing unavailable';
      return formatDuration(elapsedSec);
    }

    // 2. Completed: show total execution duration
    if (isCompleted) {
      if (state?.durationMs !== undefined && state?.durationMs !== null) {
        return formatDuration(state.durationMs / 1000);
      }
      if (state?.completedAt && state?.startedAt) {
        const start = new Date(state.startedAt).getTime();
        const end = new Date(state.completedAt).getTime();
        if (!isNaN(start) && !isNaN(end) && end >= start) {
          return formatDuration((end - start) / 1000);
        }
      }
      return 'Timing unavailable';
    }

    // 3. Failed: show execution duration up to failure
    if (isFailed) {
      if (state?.durationMs !== undefined && state?.durationMs !== null) {
        return formatDuration(state.durationMs / 1000);
      }
      if (state?.completedAt && state?.startedAt) {
        const start = new Date(state.startedAt).getTime();
        const end = new Date(state.completedAt).getTime();
        if (!isNaN(start) && !isNaN(end) && end >= start) {
          return formatDuration((end - start) / 1000);
        }
      }
      return 'Timing unavailable';
    }

    // 4. Queued / Waiting / Blocked / Cancelled (persisted previous execution data if available)
    if (state?.durationMs !== undefined && state?.durationMs !== null) {
      return formatDuration(state.durationMs / 1000);
    }
    if (state?.completedAt && state?.startedAt) {
      const start = new Date(state.startedAt).getTime();
      const end = new Date(state.completedAt).getTime();
      if (!isNaN(start) && !isNaN(end) && end >= start) {
        return formatDuration((end - start) / 1000);
      }
    }

    return 'Timing unavailable';
  };

  // Stale progress detection (>30s without progress/activity update while running)
  const lastActiveTs = state?.lastActivityAt 
    ? new Date(state.lastActivityAt).getTime() 
    : (state?.startedAt ? new Date(state.startedAt).getTime() : null);
  const isStaleProgress = isRunning && lastActiveTs !== null && (nowTs - lastActiveTs > 30000);

  const getStatusColor = () => {
    if (isCompleted) return 'var(--status-completed)';
    if (isRunning) return 'var(--status-running)';
    if (isRetrying) return 'var(--status-retrying)';
    if (isFailed) return 'var(--status-failed)';
    if (isBlocked) return 'var(--status-blocked)';
    if (isCancelled) return 'var(--status-cancelled)';
    return 'var(--status-waiting)';
  };

  const getStatusBadge = () => {
    if (state?.stuck && !isCompleted && !isFailed) {                      // started, then no progress beyond the expected time (backend issue list)
      return (
        <span data-testid={`stage-status-${config.id}`} style={{
          display: 'flex', alignItems: 'center', gap: '3px', color: '#FDBA74', backgroundColor: 'rgba(249, 115, 22, 0.14)',
          border: '1px solid rgba(249, 115, 22, 0.4)', padding: '2px 6px', borderRadius: '3px', fontSize: '11px', fontWeight: 700
        }}>
          <Clock size={11} />
          STUCK
        </span>
      );
    }
    if (isCompleted) {
      return (
        <span style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '3px', 
          color: 'var(--status-completed)', 
          backgroundColor: 'var(--status-completed-bg)', 
          border: '1px solid var(--status-completed-border)',
          padding: '2px 6px',
          borderRadius: '3px',
          fontSize: '11px', 
          fontWeight: 600 
        }}>
          <CheckCircle2 size={12} />
          {(state?.issueWarnings || 0) > 0 ? 'WARNING' : 'COMPLETED'}
        </span>
      );
    }
    if (isRetrying) {
      return (
        <span style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '3px', 
          color: 'var(--status-retrying)', 
          backgroundColor: 'var(--status-retrying-bg)', 
          border: '1px solid var(--status-retrying-border)',
          padding: '2px 6px',
          borderRadius: '3px',
          fontSize: '11px', 
          fontWeight: 600 
        }}>
          <RotateCcw size={12} className="animate-spin" />
          {state?.attempt ? `RETRY (${state.attempt})` : 'RETRYING'}
        </span>
      );
    }
    if (isRunning) {
      return (
        <span style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '4px', 
          color: 'var(--status-running)', 
          backgroundColor: 'var(--status-running-bg)', 
          border: '1px solid var(--status-running-border)',
          padding: '2px 6px',
          borderRadius: '3px',
          fontSize: '11px', 
          fontWeight: 600 
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
        <span style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '3px', 
          color: 'var(--status-failed)', 
          backgroundColor: 'var(--status-failed-bg)', 
          border: '1px solid var(--status-failed-border)',
          padding: '2px 6px',
          borderRadius: '3px',
          fontSize: '11px', 
          fontWeight: 600 
        }}>
          <XCircle size={12} />
          ERROR
        </span>
      );
    }
    if (isBlocked) {
      return (
        <span style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '3px', 
          color: 'var(--status-blocked)', 
          backgroundColor: 'var(--status-blocked-bg)', 
          border: '1px solid var(--status-blocked-border)',
          padding: '2px 6px',
          borderRadius: '3px',
          fontSize: '11px', 
          fontWeight: 600 
        }}>
          <AlertTriangle size={12} />
          BLOCKED
        </span>
      );
    }
    if (isCancelled) {
      return (
        <span style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '3px', 
          color: 'var(--status-cancelled)', 
          backgroundColor: 'var(--status-cancelled-bg)', 
          border: '1px solid var(--status-cancelled-border)',
          padding: '2px 6px',
          borderRadius: '3px',
          fontSize: '11px', 
          fontWeight: 600 
        }}>
          <XCircle size={12} />
          STOPPED
        </span>
      );
    }
    return (
      <span style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '3px', 
        color: 'var(--text-muted)', 
        backgroundColor: 'var(--status-waiting-bg)', 
        border: '1px solid var(--status-waiting-border)',
        padding: '2px 6px',
        borderRadius: '3px',
        fontSize: '11px', 
        fontWeight: 500 
      }}>
        <Clock size={11} />
        {(status as string) === 'waiting_for_approval' ? 'NEEDS APPROVAL' : (state?.waitingFor ? 'WAITING' : 'READY')}
      </span>
    );
  };

  const cardClassName = isRunning 
    ? 'stage-card-running' 
    : (isRetrying ? 'stage-card-retrying' : (isFailed ? 'stage-card-failed' : ((isBlocked || state?.stuck) ? 'stage-card-blocked' : '')));

  return (
    <div
      onClick={onSelect}
      role="button"
      tabIndex={0}
      title={`Click to open full screen details for ${config.label}`}
      data-testid={`stage-card-${config.id}`}
      data-status={status}
      className={cardClassName}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect(); }}
      style={{
        width: '100%',
        minHeight: '118px',
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)',
        border: `1px solid ${
          isSelected 
            ? 'var(--accent-blue)' 
            : isRunning 
              ? 'var(--status-running)' 
              : isRetrying
                ? 'var(--status-retrying)'
                : isFailed
                  ? 'var(--status-failed)'
                  : 'var(--border-card)'
        }`,
        boxShadow: isSelected 
          ? '0 0 0 2px rgba(24, 144, 255, 0.3), var(--shadow-card)' 
          : (isRunning || isRetrying) 
            ? 'none' 
            : 'var(--shadow-card)',
        padding: '10px 14px',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        transition: 'border-color 0.18s ease, background-color 0.18s ease, transform 0.18s ease',
        position: 'relative',
        overflow: 'hidden'
      }}
      onMouseEnter={(e) => {
        if (!isSelected && !isRunning && !isRetrying) {
          e.currentTarget.style.borderColor = isFailed ? 'var(--status-failed)' : 'var(--accent-blue)';
          e.currentTarget.style.boxShadow = 'var(--shadow-hover)';
        }
      }}
      onMouseLeave={(e) => {
        if (!isSelected && !isRunning && !isRetrying) {
          e.currentTarget.style.borderColor = isFailed ? 'var(--status-failed)' : 'var(--border-card)';
          e.currentTarget.style.boxShadow = 'var(--shadow-card)';
        }
      }}
    >
      {/* Input Port Indicator (Left Edge) */}
      <div style={{
        position: 'absolute',
        left: 0,
        top: '50%',
        transform: 'translateY(-50%)',
        width: '3px',
        height: '16px',
        borderTopRightRadius: '3px',
        borderBottomRightRadius: '3px',
        backgroundColor: isCompleted 
          ? 'var(--status-completed)' 
          : ((isRunning || isRetrying) ? 'var(--accent-cyan)' : (isFailed ? 'var(--status-failed)' : 'var(--border-subtle)')),
        transition: 'background-color 0.2s ease'
      }} />

      {/* Output Port Indicator (Right Edge) */}
      <div style={{
        position: 'absolute',
        right: 0,
        top: '50%',
        transform: 'translateY(-50%)',
        width: '3px',
        height: '16px',
        borderTopLeftRadius: '3px',
        borderBottomLeftRadius: '3px',
        backgroundColor: isCompleted 
          ? 'var(--status-completed)' 
          : ((isRunning || isRetrying) ? 'var(--accent-cyan)' : (isFailed ? 'var(--status-failed)' : 'var(--border-subtle)')),
        transition: 'background-color 0.2s ease'
      }} />

      {/* Top Row: Stage Order & Status Icon & Status Badge + Action Buttons */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
          <span style={{
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            color: 'var(--text-muted)',
            letterSpacing: '0.5px'
          }}>
            {String(config.order).padStart(2, '0')}
          </span>
          <span style={{ color: getStatusColor(), display: 'flex', alignItems: 'center' }}>
            {STAGE_ICONS[config.id] || <Layers size={14} />}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {/* Stop Button while Running */}
          {(isRunning || isRetrying) && onStopStage && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onStopStage(config.id);
              }}
              data-testid={`stage-stop-btn-${config.id}`}
              title={`Stop ${config.label}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                borderRadius: '3px',
                padding: '2px 6px',
                color: '#EF4444',
                fontSize: '10px',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#EF4444';
                e.currentTarget.style.color = '#FFFFFF';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.15)';
                e.currentTarget.style.color = '#EF4444';
              }}
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
              className="issue-blink"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                backgroundColor: 'rgba(255, 77, 79, 0.15)',
                border: '1px solid rgba(255, 77, 79, 0.4)',
                borderRadius: '3px',
                padding: '2px 6px',
                color: 'var(--status-failed)',
                fontSize: '10px',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--status-failed)';
                e.currentTarget.style.color = '#FFFFFF';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255, 77, 79, 0.15)';
                e.currentTarget.style.color = 'var(--status-failed)';
              }}
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
                if (!isBlocked && !isRunning) onRunStage(config.id);
              }}
              disabled={isBlocked || isRunning || !!state?.waitingFor}
              data-testid={`stage-run-btn-${config.id}`}
              title={state?.waitingFor ? `Waits for ${state.waitingFor} to complete` : isBlocked ? (state?.blockers?.[0] || 'Prerequisites required') : (isRunning ? 'Stage is running' : `Run ${config.label}`)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
                backgroundColor: isBlocked || isRunning ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 216, 245, 0.15)',
                border: `1px solid ${isBlocked || isRunning ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 216, 245, 0.4)'}`,
                borderRadius: '3px',
                padding: '2px 6px',
                color: isBlocked || isRunning ? 'var(--text-muted)' : 'var(--accent-cyan)',
                fontSize: '10px',
                fontWeight: 700,
                cursor: isBlocked || isRunning ? 'not-allowed' : 'pointer',
                opacity: isBlocked || isRunning ? 0.6 : 1,
                boxShadow: (!isBlocked && !isRunning) ? '0 0 6px rgba(0, 216, 245, 0.25)' : 'none',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                if (!isBlocked && !isRunning) {
                  e.currentTarget.style.backgroundColor = 'var(--accent-cyan)';
                  e.currentTarget.style.color = '#000000';
                }
              }}
              onMouseLeave={(e) => {
                if (!isBlocked && !isRunning) {
                  e.currentTarget.style.backgroundColor = 'rgba(0, 216, 245, 0.15)';
                  e.currentTarget.style.color = 'var(--accent-cyan)';
                }
              }}
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
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '2px',
                backgroundColor: 'transparent',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '3px',
                padding: '1px 5px',
                color: 'var(--text-muted)',
                fontSize: '9.5px',
                fontWeight: 600,
                cursor: isPipelineRunning ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                if (!isPipelineRunning) {
                  e.currentTarget.style.borderColor = 'var(--accent-cyan)';
                  e.currentTarget.style.color = 'var(--accent-cyan)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isPipelineRunning) {
                  e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)';
                  e.currentTarget.style.color = 'var(--text-muted)';
                }
              }}
            >
              <RotateCcw size={8} />
              <span>RERUN</span>
            </button>
          )}

          {getStatusBadge()}
        </div>
      </div>

      {/* Middle: Prominent Large Numeric Percentage (No Progress Bar) & Duration/Error preview */}
      <div style={{ margin: '4px 0 2px 0' }}>
        <div style={{ display: 'flex', alignItems: isRunning ? 'center' : 'baseline', justifyContent: 'space-between', gap: '8px' }}>
          {isRunning ? (
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
          ) : (
          <div style={{
            fontSize: '26px',
            fontWeight: 700,
            fontFamily: 'var(--font-sans)',
            letterSpacing: '-1px',
            color: isCompleted 
              ? 'var(--status-completed)' 
              : isRunning 
                ? 'var(--status-running)' 
                : isRetrying
                  ? 'var(--status-retrying)'
                  : isFailed
                    ? 'var(--status-failed)'
                    : 'var(--text-primary)',
            lineHeight: 1
          }}>
            {percentage}
          </div>
          )}

          <span
            data-testid={`stage-timing-${config.id}`}
            title={`Execution timing: ${getTimingDisplay()}`}
            style={{
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              color: isRunning ? 'var(--status-running)' : 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              flexShrink: 0,
              whiteSpace: 'nowrap'
            }}
          >
            <Clock size={11} style={{ flexShrink: 0, opacity: 0.8 }} />
            {getTimingDisplay()}
          </span>
        </div>

        {/* Warning banner for long-running operation without recent progress update */}
        {isStaleProgress && (
          <div 
            title="No recent progress update — checking current status."
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginTop: '4px',
              padding: '2px 5px',
              borderRadius: '3px',
              backgroundColor: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              color: '#FBBF24',
              fontSize: '10px',
              fontWeight: 600,
              lineHeight: 1.2
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
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginTop: '4px',
              padding: '2px 5px',
              borderRadius: '3px',
              backgroundColor: 'var(--status-failed-bg)',
              border: '1px solid var(--status-failed-border)',
              color: 'var(--status-failed)',
              fontSize: '10px',
              fontWeight: 600,
              lineHeight: 1.2
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
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginTop: '4px',
              padding: '2px 5px',
              borderRadius: '3px',
              backgroundColor: 'var(--status-retrying-bg)',
              border: '1px solid var(--status-retrying-border)',
              color: 'var(--status-retrying)',
              fontSize: '10px',
              fontWeight: 600,
              lineHeight: 1.2
            }}
          >
            <RotateCcw size={10} className="animate-spin" style={{ flexShrink: 0 }} />
            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {state?.retryReason || (state?.attempt ? `Attempt ${state.attempt} recovery` : 'Recovering...')}
            </span>
          </div>
        )}

        {/* Waiting: its prerequisite stage has not completed, so it cannot run yet */}
        {state?.waitingFor && !isRunning && (
          <div data-testid={`stage-waiting-${config.id}`} title={`Starts after ${state.waitingFor} completes`}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px', fontSize: '10px', fontWeight: 600, color: 'var(--text-muted)', lineHeight: 1.2 }}>
            <Clock size={10} style={{ flexShrink: 0 }} />
            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Waiting for {state.waitingFor}</span>
          </div>
        )}

        {/* Stuck: started but no progress beyond the stage's expected time (real timing from the agent log) */}
        {state?.stuck && !isFailed && (
          <div
            data-testid={`stage-stuck-${config.id}`}
            title="No progress beyond the expected time. Open Issues for details."
            style={{
              display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px', padding: '2px 5px', borderRadius: '3px',
              backgroundColor: 'rgba(249, 115, 22, 0.14)', border: '1px solid rgba(249, 115, 22, 0.4)',
              color: '#FDBA74', fontSize: '10px', fontWeight: 700, lineHeight: 1.2
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
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginTop: '4px',
              padding: '2px 5px',
              borderRadius: '3px',
              backgroundColor: 'var(--status-blocked-bg)',
              border: '1px solid var(--status-blocked-border)',
              color: 'var(--status-blocked)',
              fontSize: '10px',
              fontWeight: 600,
              lineHeight: 1.2
            }}
          >
            <AlertTriangle size={10} style={{ flexShrink: 0 }} />
            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {state?.blockers?.[0] || 'Awaiting prerequisites'}
            </span>
          </div>
        )}
      </div>

      {/* Bottom: Stage Label (Clean Single Title) */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '8px' }}>
        <div
          title={config.label}
          style={{
            fontSize: '12.5px',
            fontWeight: 600,
            color: 'var(--text-primary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            minWidth: 0
          }}
        >
          {config.label}
        </div>
        {((state?.issueErrors || 0) + (state?.issueWarnings || 0)) > 0 && (
          <button
            onClick={(e) => { e.stopPropagation(); window.dispatchEvent(new CustomEvent('open-issues', { detail: config.id })); }}
            data-testid={`stage-issues-${config.id}`}
            title="Open this stage's errors and warnings"
            className={(state?.issueErrors || 0) > 0 ? 'issue-blink' : undefined}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '4px', flexShrink: 0, height: '20px', padding: '0 7px', borderRadius: '9999px',
              fontSize: '10.5px', fontWeight: 700, cursor: 'pointer',
              color: (state?.issueErrors || 0) > 0 ? '#FCA5A5' : '#FBBF24',
              backgroundColor: (state?.issueErrors || 0) > 0 ? 'rgba(239, 68, 68, 0.14)' : 'rgba(245, 158, 11, 0.14)',
              border: `1px solid ${(state?.issueErrors || 0) > 0 ? 'rgba(239, 68, 68, 0.45)' : 'rgba(245, 158, 11, 0.45)'}`
            }}
          >
            <AlertTriangle size={10} />
            {(state?.issueErrors || 0) > 0 ? `${state!.issueErrors}E` : ''}
            {(state?.issueErrors || 0) > 0 && (state?.issueWarnings || 0) > 0 ? ' · ' : ''}
            {(state?.issueWarnings || 0) > 0 ? `${state!.issueWarnings}W` : ''}
          </button>
        )}
        {status === 'completed' && (
          <div
            data-testid={`stage-llm-badge-${config.id}`}
            style={{
              fontSize: '10.5px', fontWeight: 600, whiteSpace: 'nowrap', flexShrink: 0,
              color: state?.llmVerified ? '#34D399' : '#9CA3AF'
            }}
          >
            {state?.llmVerified ? '✓ LLM Verified' : 'Not verified with LLM'}
          </div>
        )}
      </div>
    </div>
  );
}, (prevProps, nextProps) => {
  return (
    prevProps.isSelected === nextProps.isSelected &&
    prevProps.config.id === nextProps.config.id &&
    prevProps.state?.status === nextProps.state?.status &&
    prevProps.state?.percentage === nextProps.state?.percentage &&
    prevProps.state?.currentActivity === nextProps.state?.currentActivity &&
    prevProps.state?.teluguMessage === nextProps.state?.teluguMessage &&
    prevProps.state?.attempt === nextProps.state?.attempt &&
    prevProps.state?.retryReason === nextProps.state?.retryReason &&
    prevProps.state?.failingSubStage === nextProps.state?.failingSubStage &&
    prevProps.state?.lastActivityAt === nextProps.state?.lastActivityAt &&
    prevProps.state?.startedAt === nextProps.state?.startedAt &&
    prevProps.state?.llmVerified === nextProps.state?.llmVerified &&
    prevProps.state?.stuck === nextProps.state?.stuck &&
    prevProps.state?.waitingFor === nextProps.state?.waitingFor &&
    prevProps.state?.issueErrors === nextProps.state?.issueErrors &&
    prevProps.state?.issueWarnings === nextProps.state?.issueWarnings &&
    prevProps.state?.errors?.[0] === nextProps.state?.errors?.[0] &&
    prevProps.state?.blockers?.[0] === nextProps.state?.blockers?.[0] &&
    prevProps.isPipelineRunning === nextProps.isPipelineRunning
  );
});
