import React from 'react';
import styles from '../PipelineCanvas.module.css';
import { AlertTriangle, RotateCcw, Clock } from 'lucide-react';
import { PipelineProjectState, StageConfig } from '../../types/pipeline';

export interface PipelineAlertBannersProps {
  autoFailure: { stageId: string; label: string; message: string } | null;
  setAutoFailure: (val: { stageId: string; label: string; message: string } | null) => void;
  projectState: PipelineProjectState;
  isAnyStageRunning: boolean;
  handleRunStage: (stageId: string) => Promise<void>;
  actionMessage: string | null;
  backendHealthy: boolean;
  failedStage?: StageConfig;
  handleRetryStage: (stageId: string) => Promise<void>;
  isAudioMissing: boolean;
  onUploadAudio: () => void;
}

export const PipelineAlertBanners: React.FC<PipelineAlertBannersProps> = ({
  autoFailure,
  setAutoFailure,
  projectState,
  isAnyStageRunning,
  handleRunStage,
  actionMessage,
  backendHealthy,
  failedStage,
  handleRetryStage,
  isAudioMissing,
  onUploadAudio
}) => {
  const failedStageState = failedStage ? projectState.stages[failedStage.id] : null;

  return (
    <>
      {/* Action feedback message */}
      {autoFailure && projectState.stages[autoFailure.stageId]?.status !== 'running' && projectState.stages[autoFailure.stageId]?.status !== 'completed' && (
        <div data-testid="auto-advance-failure" className={styles.autoFailureBanner}>
          <AlertTriangle size={15} style={{ flexShrink: 0 }} />
          <span style={{ flex: 1, minWidth: '240px' }}>
            <strong>{autoFailure.label} did not start automatically.</strong> {autoFailure.message}
          </span>
          <button
            data-testid="auto-advance-manual-run"
            disabled={isAnyStageRunning}
            title={isAnyStageRunning ? 'Another stage is running' : `Run ${autoFailure.label} (the same dependency and issue checks apply)`}
            onClick={() => { const id = autoFailure.stageId; setAutoFailure(null); handleRunStage(id); }}
            className={styles.autoFailureButton}
            style={{
              cursor: isAnyStageRunning ? 'not-allowed' : 'pointer',
              opacity: isAnyStageRunning ? 0.6 : 1
            }}
          >
            Run {autoFailure.label}
          </button>
        </div>
      )}

      {actionMessage && (
        <div className={styles.actionMessage}>
          {actionMessage}
        </div>
      )}

      {/* Backend Connectivity Status Alert */}
      {!backendHealthy && (
        <div 
          data-testid="backend-disconnected-banner"
          className={styles.backendAlert}
        >
          <AlertTriangle size={16} />
          <span>FastAPI Backend Offline / Unreachable — Attempting automatic reconnection to http://127.0.0.1:8000...</span>
        </div>
      )}

      {/* Stage Failure Alert Banner with One-Click Retry */}
      {failedStage && (
        <div
          data-testid="stage-error-banner"
          style={{
            backgroundColor: 'var(--status-failed-bg)',
            border: '1px solid var(--status-failed-border)',
            borderRadius: '4px',
            padding: '12px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <AlertTriangle size={18} color="var(--status-failed)" />
            <div>
              <h4 style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--status-failed)', margin: 0 }}>
                {failedStage.label} Execution Failed
              </h4>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
                {failedStageState?.errors?.[0] || failedStageState?.currentActivity || 'A step encountered an error. Retry to re-run from the last valid checkpoint.'}
              </p>
            </div>
          </div>

          <button
            onClick={() => handleRetryStage(failedStage.id)}
            data-testid="retry-failed-stage-btn"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              backgroundColor: 'var(--status-failed)',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            <RotateCcw size={13} />
            Retry {failedStage.label}
          </button>
        </div>
      )}

      {/* Empty Audio Workspace Ingest Prompt */}
      {isAudioMissing && (
        <div
          data-testid="empty-audio-prompt"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px dashed var(--border-card)',
            borderRadius: 'var(--radius-sm)',
            padding: '14px 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Clock size={16} color="var(--accent-blue)" />
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              No narration audio uploaded for workspace <strong>{projectState.projectId}</strong>. Upload an audio file to begin video generation.
            </span>
          </div>

          <button
            onClick={onUploadAudio}
            style={{
              padding: '6px 14px',
              backgroundColor: 'var(--accent-blue)',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Upload Audio
          </button>
        </div>
      )}
    </>
  );
};
