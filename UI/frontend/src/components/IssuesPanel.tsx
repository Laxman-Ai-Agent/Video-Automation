import React from 'react';
import { AlertCircle, AlertTriangle, Clock, Crosshair, X } from 'lucide-react';
import { PipelineIssue } from '../types/pipeline';

interface IssuesPanelProps {
  open: boolean;
  issues: PipelineIssue[];
  stageFilter?: string | null; // show only this stage's issues (opened from its card)
  onShowAll?: () => void;
  onClose: () => void;
  onLocate: (stageId: string) => void;
}

const SEVERITY = {
  error: { label: 'ERROR', color: '#FCA5A5', bg: 'rgba(239, 68, 68, 0.14)', border: 'rgba(239, 68, 68, 0.45)', Icon: AlertCircle },
  stuck: { label: 'STUCK', color: '#FDBA74', bg: 'rgba(249, 115, 22, 0.14)', border: 'rgba(249, 115, 22, 0.45)', Icon: Clock },
  warning: { label: 'WARNING', color: '#FBBF24', bg: 'rgba(245, 158, 11, 0.14)', border: 'rgba(245, 158, 11, 0.45)', Icon: AlertTriangle }
} as const;

function ago(epochSeconds?: number | null): string {
  if (!epochSeconds) return '';
  const s = Math.max(0, Math.round(Date.now() / 1000 - epochSeconds));
  if (s < 90) return `${s}s ago`;
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  return `${Math.round(s / 3600)} h ago`;
}

export const IssuesPanel: React.FC<IssuesPanelProps> = ({ open, issues: allIssues, stageFilter, onShowAll, onClose, onLocate }) => {
  if (!open) return null;
  const issues = stageFilter ? allIssues.filter((i) => i.stageId === stageFilter) : allIssues;
  const order = { error: 0, stuck: 1, warning: 2 };
  const sorted = [...issues].sort((a, b) => order[a.severity] - order[b.severity]);

  return (
    <aside
      data-testid="issues-panel"
      style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: '480px', maxWidth: '100vw', zIndex: 130,
        backgroundColor: 'var(--bg-card)', borderLeft: '1px solid var(--border-card)', boxShadow: 'var(--shadow-drawer)',
        display: 'flex', flexDirection: 'column', animation: 'slideInRight 0.22s ease-out'
      }}
    >
      <div style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-card)', backgroundColor: 'var(--bg-elevated)' }}>
        <div>
          <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>Issues</div>
          <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
            {issues.length === 0 ? (stageFilter ? 'No issues for this stage.' : 'No issues detected in this project.')
              : `${issues.length} unresolved${stageFilter ? ` in ${issues[0].stageLabel}` : ''}: errors ${issues.filter((i) => i.severity !== 'warning').length}, warnings ${issues.filter((i) => i.severity === 'warning').length}. Live from the agent log, step reports, LLM step checks and stage status.`}
          </div>
          {stageFilter && onShowAll && (
            <button onClick={onShowAll} data-testid="issues-show-all" style={{ marginTop: '6px', height: '24px', padding: '0 10px', borderRadius: '6px', fontSize: '11px', fontWeight: 600, cursor: 'pointer', color: '#38BDF8', backgroundColor: 'rgba(24, 144, 255, 0.12)', border: '1px solid rgba(24, 144, 255, 0.35)' }}>
              Show all stages ({allIssues.length})
            </button>
          )}
        </div>
        <button onClick={onClose} title="Close" style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex' }}>
          <X size={18} />
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {sorted.map((i) => {
          const sev = SEVERITY[i.severity];
          const Icon = sev.Icon;
          return (
            <div key={i.id} data-testid={`issue-${i.id}`} style={{ border: `1px solid ${sev.border}`, backgroundColor: sev.bg, borderRadius: '8px', padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '11px', fontWeight: 800, color: sev.color }}>
                  <Icon size={13} /> {sev.label}
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{ago(i.at)}</span>
              </div>
              <div style={{ marginTop: '6px', fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                {i.stageLabel}{i.subtask ? <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}> › {i.subtask}</span> : null}
              </div>
              <div style={{ marginTop: '4px', fontSize: '12.5px', color: 'var(--text-secondary)', wordBreak: 'break-word' }}>{i.message}</div>
              <div style={{ marginTop: '8px', display: 'grid', gridTemplateColumns: 'auto 1fr', columnGap: '10px', rowGap: '2px', fontSize: '11.5px' }}>
                {i.stageStatus && (<><span style={{ color: 'var(--text-muted)' }}>Stage status</span><span style={{ color: 'var(--text-primary)' }}>{i.stageStatus.replace(/_/g, ' ')}</span></>)}
                <span style={{ color: 'var(--text-muted)' }}>Source</span><span style={{ color: 'var(--text-primary)' }}>{i.source}</span>
                <span style={{ color: 'var(--text-muted)' }}>Component</span><span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{i.component}</span>
                {i.code && (<><span style={{ color: 'var(--text-muted)' }}>Code</span><span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{i.code}</span></>)}
                {i.attempts ? (<><span style={{ color: 'var(--text-muted)' }}>Attempt</span><span style={{ color: 'var(--text-primary)' }}>{i.attempts}{i.retryLimit ? ` of ${i.retryLimit}` : ''}</span></>) : null}
              </div>
              {i.stageId && (
                <button
                  onClick={() => onLocate(i.stageId as string)}
                  style={{ marginTop: '10px', display: 'inline-flex', alignItems: 'center', gap: '6px', height: '28px', padding: '0 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer', color: '#38BDF8', backgroundColor: 'rgba(24, 144, 255, 0.12)', border: '1px solid rgba(24, 144, 255, 0.35)' }}
                >
                  <Crosshair size={13} /> Locate stage
                </button>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
};
