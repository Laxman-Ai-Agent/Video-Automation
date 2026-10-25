import React from 'react';
import styles from '../PipelineCanvas.module.css';
import { ShieldCheck, Check } from 'lucide-react';

export interface PipelineApprovalsTabProps {
  pendingApprovals: any[];
  activeProjectId: string;
  handleLlmDecide: (approvalId: string) => Promise<void>;
}

export const PipelineApprovalsTab: React.FC<PipelineApprovalsTabProps> = ({
  pendingApprovals,
  activeProjectId,
  handleLlmDecide
}) => {
  return (
    <div className={styles.tabContent}>
      <div style={{ marginBottom: '20px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
          Pending Approval Requests
        </h3>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
          High-risk actions wait here until the LLM approval review decides them; no person approves.
        </p>
      </div>

      {pendingApprovals.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '48px',
          backgroundColor: 'var(--bg-elevated)',
          borderRadius: 'var(--radius-sm)',
          border: '1px dashed var(--border-card)'
        }}>
          <ShieldCheck size={36} style={{ color: 'var(--status-completed)', marginBottom: '10px' }} />
          <h4 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
            All Clear — No Pending Approvals
          </h4>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            No request is waiting for the LLM approval review.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {pendingApprovals.map((appr) => (
            <div
              key={appr.approval_id || appr.id}
              style={{
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--status-blocked-border)',
                borderRadius: 'var(--radius-sm)',
                padding: '18px 22px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '16px'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    backgroundColor: 'var(--status-blocked-bg)',
                    color: 'var(--status-blocked)',
                    padding: '2px 8px',
                    borderRadius: '4px'
                  }}>
                    {(appr.risk_level || 'MEDIUM').toUpperCase()} RISK
                  </span>
                  <h4 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {appr.action_summary || appr.action_type || 'Approval Request'}
                  </h4>
                </div>

                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Requester Agent: <strong style={{ color: 'var(--accent-blue)' }}>{appr.requester_agent_id}</strong> • Project: {appr.project_id || activeProjectId}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <button
                  onClick={() => handleLlmDecide(appr.approval_id || appr.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '6px 16px',
                    backgroundColor: 'var(--status-completed)',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '4px',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    boxShadow: '0 2px 4px rgba(16, 185, 129, 0.3)'
                  }}
                >
                  <Check size={14} />
                  Let the LLM decide
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
