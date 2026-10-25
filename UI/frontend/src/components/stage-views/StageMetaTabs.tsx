import React from 'react';
import { Cpu, FileText } from 'lucide-react';
import { StageConfig, StageState } from '../../types/pipeline';

export interface StageAgentTabProps {
  config: StageConfig;
  isFullPage: boolean;
}

export const StageAgentTab: React.FC<StageAgentTabProps> = ({ config, isFullPage }) => {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: isFullPage ? 'minmax(0, 1.4fr) minmax(0, 1fr)' : '1fr',
      gap: '20px',
      alignItems: 'start'
    }}>
      <div style={{
        backgroundColor: 'var(--bg-elevated)',
        padding: '20px',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-card)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '46px',
            height: '46px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'rgba(0, 216, 245, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent-cyan)'
          }}>
            <Cpu size={24} />
          </div>
          <div>
            <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              {config.agentName}
            </h3>
            <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              ID: {config.agentId}
            </span>
          </div>
        </div>

        <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Assigned Responsibilities
          </span>
          <p style={{ fontSize: '13px', color: 'var(--text-primary)', marginTop: '4px', lineHeight: 1.5 }}>
            {config.description}
          </p>
        </div>
      </div>

      <div style={{
        backgroundColor: 'var(--bg-elevated)',
        padding: '20px',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-card)',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
          Execution Metadata
        </span>
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          Stage Order: <strong style={{ color: 'var(--text-primary)' }}>Stage {config.order}</strong>
        </div>
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          Pipeline Category: <strong style={{ color: 'var(--accent-cyan)' }}>{config.category.toUpperCase()}</strong>
        </div>
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          Weight in Video Composition: <strong style={{ color: 'var(--text-primary)' }}>{(config.weight * 100).toFixed(0)}%</strong>
        </div>
      </div>
    </div>
  );
};

export interface StageArtifactsTabProps {
  state?: StageState;
  isFullPage: boolean;
}

export const StageArtifactsTab: React.FC<StageArtifactsTabProps> = ({ state, isFullPage }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <span style={{ fontSize: '12.5px', color: 'var(--text-muted)', fontWeight: 600 }}>
        Produced Artifacts & Stage Outputs
      </span>
      {state?.artifacts && state.artifacts.length > 0 ? (
        <div style={{
          display: 'grid',
          gridTemplateColumns: isFullPage ? 'repeat(auto-fill, minmax(360px, 1fr))' : '1fr',
          gap: '12px'
        }}>
          {state.artifacts.map((art, idx) => (
            <div
              key={idx}
              style={{
                backgroundColor: 'var(--bg-elevated)',
                padding: '14px 16px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <FileText size={18} color="var(--accent-cyan)" />
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {art.name}
                  </div>
                  <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    {art.path}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{
          padding: '48px 16px',
          textAlign: 'center',
          backgroundColor: 'var(--bg-elevated)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--text-muted)',
          fontSize: '13px'
        }}>
          No artifacts recorded for this stage yet.
        </div>
      )}
    </div>
  );
};

export interface StageLogsTabProps {
  config: StageConfig;
  state?: StageState;
  isFullPage: boolean;
  isCompleted: boolean;
}

export const StageLogsTab: React.FC<StageLogsTabProps> = ({ config, state, isFullPage, isCompleted }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <span style={{ fontSize: '12.5px', color: 'var(--text-muted)', fontWeight: 600 }}>
        Activity Stream & Technical Telemetry
      </span>
      <div style={{
        backgroundColor: 'var(--bg-app)',
        padding: '16px 20px',
        borderRadius: 'var(--radius-md)',
        fontFamily: 'var(--font-mono)',
        fontSize: '12px',
        color: 'var(--text-secondary)',
        minHeight: isFullPage ? '420px' : '220px',
        maxHeight: isFullPage ? '620px' : '360px',
        overflowY: 'auto',
        border: '1px solid var(--border-subtle)',
        lineHeight: 1.6
      }}>
        <div style={{ color: 'var(--accent-cyan)' }}>[INFO] Stage lifecycle bound: {config.id}</div>
        {state?.startedAt && <div>[START] Started at {new Date(state.startedAt).toLocaleTimeString()}</div>}
        {state?.currentActivity && <div>[ACTIVE] {state.currentActivity}</div>}
        {state?.teluguMessage && <div style={{ color: 'var(--status-completed)' }}>[TELUGU] {state.teluguMessage}</div>}
        {state?.errors?.[0] && <div style={{ color: 'var(--status-failed)' }}>[ERROR] {state.errors[0]}</div>}
        {state?.retryReason && <div style={{ color: 'var(--status-retrying)' }}>[RETRY] {state.retryReason}</div>}
        {isCompleted && <div style={{ color: 'var(--status-completed)' }}>[DONE] Completed successfully with verified hash.</div>}
      </div>
    </div>
  );
};
