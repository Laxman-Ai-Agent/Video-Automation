import React from 'react';
import {
  CheckCircle2,
  Activity,
  RotateCcw,
  XCircle,
  AlertTriangle,
  Clock,
  AlertCircle,
  ShieldCheck,
  Check,
  Video,
  Cpu,
  FileAudio,
} from 'lucide-react';
import { StageConfig, StageState } from '../../types/pipeline';
import { SubtaskStep } from '../../services/api';
import { StageOverviewMetricsPanel } from './StageOverviewMetricsPanel';


export interface StageOverviewTabProps {
  config: StageConfig;
  state?: StageState;
  isCompleted: boolean;
  isRunning: boolean;
  isRetrying: boolean;
  isFailed: boolean;
  isBlocked: boolean;
  isStaleProgress: boolean;
  isFullPage: boolean;
  projectId?: string;
  elapsedSec: number;
  formatElapsedSeconds: (seconds: number) => string;
  subSteps: SubtaskStep[];
  subDone: number;
  timelineApproval?: any;
  actionMessage: string | null;
  actionLoading: boolean;
  renderVideo?: any;
  onRetryStage?: (id: string) => void;
  handleApproveTimeline: (decision: 'approved' | 'changes_requested') => void;
  setActiveTab: (tab: any) => void;
}

export const StageOverviewTab: React.FC<StageOverviewTabProps> = ({
  config,
  state,
  isCompleted,
  isRunning,
  isRetrying,
  isFailed,
  isBlocked,
  isStaleProgress,
  isFullPage,
  projectId,
  elapsedSec,
  formatElapsedSeconds,
  subSteps,
  subDone,
  timelineApproval,
  actionMessage,
  actionLoading,
  renderVideo,
  onRetryStage,
  handleApproveTimeline,
  setActiveTab,
}) => {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: isFullPage ? 'minmax(0, 1.35fr) minmax(0, 1fr)' : '1fr',
        gap: '20px',
        alignItems: 'start'
      }}
    >
      {/* Left Column: Operational Status & Gates */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Operational State Card */}
        <div style={{
          backgroundColor: 'var(--bg-elevated)',
          padding: '16px 18px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-card)'
        }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Operational State
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '6px' }}>
            {isCompleted && <CheckCircle2 size={18} color="var(--status-completed)" />}
            {isRunning && <Activity size={18} color="var(--accent-cyan)" className="animate-spin" />}
            {isRetrying && <RotateCcw size={18} color="var(--status-retrying)" className="animate-spin" />}
            {isFailed && <XCircle size={18} color="var(--status-failed)" />}
            {isBlocked && <AlertTriangle size={18} color="var(--status-blocked)" />}
            {!isCompleted && !isRunning && !isRetrying && !isFailed && !isBlocked && <Clock size={18} color="var(--text-muted)" />}
            <span style={{ fontSize: '14.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {isCompleted 
                ? 'Stage Finished & Verified' 
                : isRunning 
                  ? 'Active Live Execution' 
                  : isRetrying
                    ? `Recovering Transient Failure (Attempt ${state?.attempt || 1})`
                    : isFailed
                      ? 'Stage Execution Failed'
                      : isBlocked
                        ? 'Blocked Awaiting Prerequisites'
                        : 'Waiting for Prerequisites'}
            </span>
          </div>
        </div>

        {/* Warning: Long-running task without recent progress update */}
        {isStaleProgress && (
          <div 
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '12px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid rgba(245, 158, 11, 0.35)',
              color: '#FBBF24',
              fontSize: '12.5px',
              fontWeight: 600,
              lineHeight: 1.4
            }}
          >
            <AlertTriangle size={16} style={{ flexShrink: 0 }} />
            <span>No recent progress update — checking current status.</span>
          </div>
        )}

        {/* Prominent Error Details Banner */}
        {isFailed && (
          <div style={{
            backgroundColor: 'var(--status-failed-bg)',
            padding: '16px 18px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--status-failed)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--status-failed)', fontWeight: 700, fontSize: '14px' }}>
              <AlertCircle size={18} />
              <span>
                {state?.failingSubStage ? `Failed at ${state.failingSubStage}` : 'Execution Failed'}
              </span>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-primary)', marginTop: '8px', lineHeight: 1.4 }}>
              {state?.errors?.[0] || 'Unknown transient error occurred during stage execution.'}
            </p>
            {state?.attempt && (
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '6px' }}>
                Failure recorded after attempt {state.attempt}{state.maxAttempts ? ` of ${state.maxAttempts}` : ''}.
              </div>
            )}
            {onRetryStage && (
              <button
                onClick={() => onRetryStage(config.id)}
                style={{
                  marginTop: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  backgroundColor: 'var(--status-failed)',
                  color: '#FFF',
                  border: 'none',
                  padding: '8px 14px',
                  borderRadius: 'var(--radius-sm)',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                <RotateCcw size={14} />
                Retry Stage
              </button>
            )}
          </div>
        )}

        {/* Telugu Activity Message */}
        {state?.teluguMessage && (
          <div style={{
            backgroundColor: 'rgba(0, 216, 245, 0.08)',
            padding: '14px 16px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid rgba(0, 216, 245, 0.25)'
          }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase' }}>
              Telugu Status Update
            </span>
            <p style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px' }}>
              {state.teluguMessage}
            </p>
          </div>
        )}

        {/* Specialized: Timeline Quality Gate Approval (Stage 08) */}
        {config.id === 'approval' && (
          <div style={{
            backgroundColor: 'var(--bg-elevated)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-card)',
            padding: '18px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldCheck size={18} color="var(--accent-cyan)" />
              <span style={{ fontSize: '14.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Human Timeline Approval Gate
              </span>
            </div>
            <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Enforces mandatory LLM verification of scene durations, camera motions, and audio sync before Remotion rendering can begin.
            </p>

            <div style={{
              backgroundColor: 'var(--bg-card)',
              padding: '12px 14px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '11.5px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div>Status: <span style={{ color: timelineApproval?.status === 'approved' ? 'var(--status-completed)' : 'var(--accent-cyan)', fontWeight: 700 }}>{timelineApproval?.status || 'Pending Producer Review'}</span></div>
              <div>Contract: timeline.json & scenes.json verified</div>
              {timelineApproval?.review_id && <div>Review ID: {timelineApproval.review_id}</div>}
            </div>

            {actionMessage && (
              <div style={{
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '12px',
                backgroundColor: actionMessage.startsWith('Error') ? 'var(--status-failed-bg)' : 'var(--status-completed-bg)',
                color: actionMessage.startsWith('Error') ? 'var(--status-failed)' : 'var(--status-completed)',
                fontWeight: 600
              }}>
                {actionMessage}
              </div>
            )}

            <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
              <button
                onClick={() => handleApproveTimeline('approved')}
                disabled={actionLoading}
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  padding: '10px 16px',
                  backgroundColor: 'var(--status-completed)',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '12.5px',
                  fontWeight: 700,
                  cursor: actionLoading ? 'not-allowed' : 'pointer',
                  opacity: actionLoading ? 0.7 : 1
                }}
              >
                <Check size={14} />
                Approve Timeline
              </button>

              <button
                onClick={() => handleApproveTimeline('changes_requested')}
                disabled={actionLoading}
                style={{
                  padding: '10px 16px',
                  backgroundColor: 'transparent',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border-card)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '12.5px',
                  fontWeight: 600,
                  cursor: actionLoading ? 'not-allowed' : 'pointer'
                }}
              >
                Request Changes
              </button>
            </div>
          </div>
        )}

        {/* Specialized: Video Render Engine Details (Stage 09) */}
        {config.id === 'render' && (
          <div style={{
            backgroundColor: 'var(--bg-elevated)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-card)',
            padding: '18px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Video size={18} color="var(--accent-cyan)" />
              <span style={{ fontSize: '14.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Remotion Video Render Engine
              </span>
            </div>
            <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Compiles Remotion motion components and mixes studio audio with FFmpeg to output 1080p Full HD MP4.
            </p>

            <div style={{
              backgroundColor: 'var(--bg-card)',
              padding: '12px 14px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '11.5px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div>Target Resolution: 1080p (Full HD)</div>
              <div>Video Codec: H.264 / AAC 320kbps</div>
              <div>Output: projects/{projectId || 'active'}/final_video.mp4</div>
              <div>Render Engine: {renderVideo?.engine || 'Remotion 4.x + FFmpeg'}</div>
            </div>
          </div>
        )}
      </div>

      {/* Right Column: Metrics, Subtasks Progress, Agent Overview */}
      <StageOverviewMetricsPanel
        config={config}
        state={state}
        isCompleted={isCompleted}
        elapsedSec={elapsedSec}
        formatElapsedSeconds={formatElapsedSeconds}
        subSteps={subSteps}
        subDone={subDone}
        setActiveTab={setActiveTab}
      />
    </div>
  );
};
