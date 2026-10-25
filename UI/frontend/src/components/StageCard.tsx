import React, { useState, useEffect } from 'react';
import styles from './StageCard.module.css';
import { 
  Clock, 
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
  AlertTriangle
} from 'lucide-react';
import { StageConfig, StageState, StageStatus } from '../types/pipeline';
import { StageActionButtons } from './stage-card/StageActionButtons';
import { StageProgressRing } from './stage-card/StageProgressRing';
import { StageCardSnippet } from './stage-card/StageCardSnippet';

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
  const isWaitingForPrevious = !!state?.waitingFor;
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
    if (isRunning || isRetrying) {
      if (!state?.startedAt) return 'Timing unavailable';
      const start = new Date(state.startedAt).getTime();
      if (isNaN(start) || start <= 0) return 'Timing unavailable';
      return formatDuration(elapsedSec);
    }

    if (isCompleted || isFailed) {
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

  const cardClassName = [
    styles.stageCard,
    isRunning ? 'stage-card-running' : '',
    isRetrying ? 'stage-card-retrying' : '',
    isFailed ? 'stage-card-failed' : '',
    (isBlocked || state?.stuck) ? 'stage-card-blocked' : ''
  ].filter(Boolean).join(' ');

  const getBorderColor = () => {
    if (isSelected) return 'var(--accent-blue)';
    if (isRunning) return 'var(--status-running)';
    if (isRetrying) return 'var(--status-retrying)';
    if (isFailed) return 'var(--status-failed)';
    return 'var(--border-card)';
  };

  const getBoxShadow = () => {
    if (isSelected) return '0 0 0 2px rgba(24, 144, 255, 0.3), var(--shadow-card)';
    if (isRunning || isRetrying) return 'none';
    return 'var(--shadow-card)';
  };

  return (
    <div
      onClick={isWaitingForPrevious ? undefined : onSelect}
      role="button"
      tabIndex={isWaitingForPrevious ? -1 : 0}
      aria-disabled={isWaitingForPrevious}
      title={isWaitingForPrevious ? `Inactive: waits for ${state?.waitingFor} to complete` : `Click to open full screen details for ${config.label}`}
      data-testid={`stage-card-${config.id}`}
      data-status={status}
      className={cardClassName}
      onKeyDown={(e) => { if (!isWaitingForPrevious && (e.key === 'Enter' || e.key === ' ')) onSelect(); }}
      style={{
        border: `1px solid ${getBorderColor()}`,
        boxShadow: getBoxShadow(),
        cursor: isWaitingForPrevious ? 'not-allowed' : 'pointer',
        opacity: isWaitingForPrevious ? 0.55 : 1
      }}
    >
      {/* Input Port Indicator (Left Edge) */}
      <div 
        className={`${styles.portIndicator} ${styles.portLeft}`}
        style={{
          backgroundColor: isCompleted 
            ? 'var(--status-completed)' 
            : ((isRunning || isRetrying) ? 'var(--accent-cyan)' : (isFailed ? 'var(--status-failed)' : 'var(--border-subtle)'))
        }} 
      />

      {/* Output Port Indicator (Right Edge) */}
      <div 
        className={`${styles.portIndicator} ${styles.portRight}`}
        style={{
          backgroundColor: isCompleted 
            ? 'var(--status-completed)' 
            : ((isRunning || isRetrying) ? 'var(--accent-cyan)' : (isFailed ? 'var(--status-failed)' : 'var(--border-subtle)'))
        }} 
      />

      {/* Top Row: Stage Order & Status Icon & Status Badge + Action Buttons */}
      <div className={styles.topRow}>
        <div className={styles.orderGroup}>
          <span className={styles.orderNumber}>
            {String(config.order).padStart(2, '0')}
          </span>
          <span className={styles.stageIcon} style={{ color: getStatusColor() }}>
            {STAGE_ICONS[config.id] || <Layers size={14} />}
          </span>
        </div>

        <StageActionButtons
          config={config}
          state={state}
          isRunning={isRunning}
          isRetrying={isRetrying}
          isFailed={isFailed}
          isCompleted={isCompleted}
          isBlocked={isBlocked}
          isWaitingForPrevious={isWaitingForPrevious}
          isPipelineRunning={isPipelineRunning}
          onRunStage={onRunStage}
          onStopStage={onStopStage}
          statusBadgeProps={{
            config,
            state,
            status,
            isCompleted,
            isRetrying,
            isRunning,
            isFailed,
            isBlocked,
            isCancelled
          }}
        />
      </div>

      {/* Middle: Prominent Large Numeric Percentage (No Progress Bar) & Duration/Error preview */}
      <div className={styles.middleSection}>
        <div className={styles.percentageRow} style={{ alignItems: isRunning ? 'center' : 'baseline' }}>
          <StageProgressRing
            config={config}
            state={state}
            isRunning={isRunning}
            isCompleted={isCompleted}
            isRetrying={isRetrying}
            isFailed={isFailed}
            hasPct={hasPct}
            percentage={percentage}
          />

          <span
            data-testid={`stage-timing-${config.id}`}
            title={`Execution timing: ${getTimingDisplay()}`}
            className={styles.timingLabel}
            style={{ color: isRunning ? 'var(--status-running)' : 'var(--text-muted)' }}
          >
            <Clock size={11} style={{ flexShrink: 0, opacity: 0.8 }} />
            {getTimingDisplay()}
          </span>
        </div>

        <StageCardSnippet
          config={config}
          state={state}
          isRunning={isRunning}
          isStaleProgress={isStaleProgress}
          isFailed={isFailed}
          isRetrying={isRetrying}
          isBlocked={isBlocked}
        />
      </div>

      {/* Bottom: Stage Label (Clean Single Title) */}
      <div className={styles.bottomRow}>
        <div
          title={config.label}
          className={styles.stageLabel}
        >
          {config.label}
        </div>
        {((state?.issueErrors || 0) + (state?.issueWarnings || 0)) > 0 && (
          <button
            onClick={(e) => { e.stopPropagation(); window.dispatchEvent(new CustomEvent('open-issues', { detail: config.id })); }}
            data-testid={`stage-issues-${config.id}`}
            title="Open this stage's errors and warnings"
            className={`${styles.issueButton} ${(state?.issueErrors || 0) > 0 ? 'issue-blink' : ''}`}
            style={{
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
            className={styles.llmBadge}
            style={{ color: state?.llmVerified ? '#34D399' : '#9CA3AF' }}
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
