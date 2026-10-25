import React from 'react';
import { ChevronRight } from 'lucide-react';

export interface AgentUpgradesViewProps {
  upgradesData: any[];
}

export const AgentUpgradesView: React.FC<AgentUpgradesViewProps> = ({ upgradesData }) => {
  if (upgradesData.length === 0) {
    return (
      <div data-testid="upgrades-content" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        <div style={{ padding: '36px', textAlign: 'center', backgroundColor: 'var(--bg-card)', borderRadius: 'var(--radius-xl)' }}>
          <p style={{ color: 'var(--text-muted)' }}>No historical upgrades recorded yet for this agent.</p>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="upgrades-content" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      {upgradesData.map((u: any, idx: number) => {
        const statusColor =
          u.verification_status === 'VERIFIED'
            ? '#10B981'
            : u.verification_status === 'PARTIALLY VERIFIED'
            ? '#F59E0B'
            : u.verification_status === 'VERIFICATION FAILED'
            ? '#EF4444'
            : 'var(--accent-cyan)';

        return (
          <div
            key={u.upgrade_id || idx}
            style={{
              backgroundColor: 'var(--bg-card)',
              borderRadius: 'var(--radius-xl)',
              border: '1px solid var(--border-card)',
              padding: '24px',
              boxShadow: 'var(--shadow-card)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '3px 10px',
                    borderRadius: 'var(--radius-full)',
                    backgroundColor: `${statusColor}20`,
                    color: statusColor,
                    border: `1px solid ${statusColor}40`
                  }}
                >
                  {u.verification_status}
                </span>
                <h4 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                  {u.upgrade_id}: {u.reason}
                </h4>
              </div>

              <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                {u.timestamp}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px', fontSize: '12.5px', color: 'var(--text-secondary)' }}>
              <span>Version transition:</span>
              <span style={{ fontFamily: 'var(--font-mono)', padding: '2px 6px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
                {u.before_version}
              </span>
              <ChevronRight size={14} />
              <span style={{ fontFamily: 'var(--font-mono)', padding: '2px 6px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', color: 'var(--accent-cyan)', fontWeight: 700 }}>
                {u.after_version}
              </span>
            </div>

            <div style={{ marginTop: '14px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              <strong style={{ color: 'var(--text-primary)' }}>Previous Limitation Resolved:</strong> {u.previous_limitation}
            </div>

            {u.capabilities_added && u.capabilities_added.length > 0 && (
              <div style={{ marginTop: '12px' }}>
                <span style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Capabilities Added:
                </span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                  {u.capabilities_added.map((c: string, ci: number) => (
                    <span
                      key={ci}
                      style={{
                        fontSize: '11.5px',
                        padding: '2px 8px',
                        backgroundColor: 'rgba(0, 216, 245, 0.08)',
                        color: 'var(--accent-cyan)',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid rgba(0, 216, 245, 0.2)'
                      }}
                    >
                      + {c}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {u.files_changed && u.files_changed.length > 0 && (
              <div style={{ marginTop: '12px' }}>
                <span style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Modified Files:
                </span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                  {u.files_changed.map((f: string, fi: number) => (
                    <span
                      key={fi}
                      style={{
                        fontSize: '11px',
                        fontFamily: 'var(--font-mono)',
                        padding: '2px 8px',
                        backgroundColor: 'var(--bg-elevated)',
                        color: 'var(--text-secondary)',
                        borderRadius: 'var(--radius-sm)'
                      }}
                    >
                      {f}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {u.evidence_refs && u.evidence_refs.length > 0 && (
              <div style={{ marginTop: '12px', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px', fontSize: '12px', color: 'var(--text-muted)' }}>
                <strong>Verification Evidence:</strong> {u.evidence_refs.join(', ')}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
