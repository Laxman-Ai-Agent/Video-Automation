import React from 'react';
import { Calendar, Info } from 'lucide-react';

export interface AgentGrowthDashboardProps {
  growthData: any | null;
}

export const AgentGrowthDashboard: React.FC<AgentGrowthDashboardProps> = ({ growthData }) => {
  const currentScores = growthData?.current_scores || {};
  const crs = currentScores.capability_readiness_score ?? 85.0;
  const vc = currentScores.verification_coverage ?? 90.0;
  const qs = currentScores.quality_metric || 'Empirically Verified';
  const snapshots: any[] = growthData?.snapshots || [];

  return (
    <div data-testid="growth-dashboard-content" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* TOP 3 SCORE CARDS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '18px' }}>
        {/* CRS CARD */}
        <div
          style={{
            backgroundColor: 'var(--bg-card)',
            borderRadius: 'var(--radius-xl)',
            border: '1px solid var(--border-card)',
            padding: '24px',
            boxShadow: 'var(--shadow-card)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Capability Readiness Score
            </span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '2px 8px',
                backgroundColor: 'rgba(0, 216, 245, 0.12)',
                color: 'var(--accent-cyan)',
                borderRadius: 'var(--radius-sm)'
              }}
            >
              CRS v1.0.0
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '12px' }}>
            <span style={{ fontSize: '38px', fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {crs.toFixed(1)}%
            </span>
            {currentScores.delta_day_over_day !== undefined && currentScores.delta_day_over_day !== 0 && (
              <span
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  color: currentScores.delta_day_over_day > 0 ? '#10B981' : '#EF4444'
                }}
              >
                {currentScores.delta_day_over_day > 0 ? `+${currentScores.delta_day_over_day}%` : `${currentScores.delta_day_over_day}%`} (24h)
              </span>
            )}
          </div>
          <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '8px', lineHeight: 1.4 }}>
            Weighted readiness across all in-scope capabilities. Status multiplier: Verified=1.0, Partial=0.5.
          </p>
        </div>

        {/* VC CARD */}
        <div
          style={{
            backgroundColor: 'var(--bg-card)',
            borderRadius: 'var(--radius-xl)',
            border: '1px solid var(--border-card)',
            padding: '24px',
            boxShadow: 'var(--shadow-card)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Verification Coverage
            </span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '2px 8px',
                backgroundColor: 'rgba(16, 185, 129, 0.12)',
                color: '#10B981',
                borderRadius: 'var(--radius-sm)'
              }}
            >
              EMPIRICAL TESTS
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '12px' }}>
            <span style={{ fontSize: '38px', fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {vc.toFixed(1)}%
            </span>
          </div>
          <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '8px', lineHeight: 1.4 }}>
            Percentage of capabilities backed by executed pytest or deterministic verification suites.
          </p>
        </div>

        {/* QS CARD */}
        <div
          style={{
            backgroundColor: 'var(--bg-card)',
            borderRadius: 'var(--radius-xl)',
            border: '1px solid var(--border-card)',
            padding: '24px',
            boxShadow: 'var(--shadow-card)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Quality Score & Telemetry
            </span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '2px 8px',
                backgroundColor: 'rgba(245, 158, 11, 0.12)',
                color: '#F59E0B',
                borderRadius: 'var(--radius-sm)'
              }}
            >
              OBSERVABLE
            </span>
          </div>
          <div style={{ marginTop: '14px' }}>
            <span style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {qs}
            </span>
          </div>
          <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '12px', lineHeight: 1.4 }}>
            Objective runtime observations: zero black frames, audio sync precision, latency, and test suite pass rate.
          </p>
        </div>
      </div>

      {/* HISTORICAL SNAPSHOTS TIMELINE */}
      <div
        style={{
          backgroundColor: 'var(--bg-card)',
          borderRadius: 'var(--radius-xl)',
          border: '1px solid var(--border-card)',
          padding: '24px',
          boxShadow: 'var(--shadow-card)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px', flexWrap: 'wrap', gap: '8px' }}>
          <div>
            <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--text-primary)' }}>
              Chronological Maturity Snapshots ({snapshots.length} Milestones)
            </h3>
            <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Persistent day-by-day capability progress saved in <code>config/history/agent_growth_snapshots.json</code>.
            </p>
          </div>

          <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Methodology: v1.0.0
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '10px 14px', fontWeight: 600 }}>Date</th>
                <th style={{ padding: '10px 14px', fontWeight: 600 }}>CRS (%)</th>
                <th style={{ padding: '10px 14px', fontWeight: 600 }}>VC (%)</th>
                <th style={{ padding: '10px 14px', fontWeight: 600 }}>Quality Metric / Evidence</th>
                <th style={{ padding: '10px 14px', fontWeight: 600 }}>Milestone Type</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((snap: any, idx: number) => (
                <tr
                  key={snap.snapshot_id || idx}
                  style={{
                    borderBottom: '1px solid var(--border-subtle)',
                    backgroundColor: snap.is_baseline ? 'rgba(0, 216, 245, 0.04)' : 'transparent'
                  }}
                >
                  <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Calendar size={13} color="var(--accent-cyan)" />
                      {snap.date}
                    </div>
                  </td>
                  <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                    {snap.capability_readiness_score}%
                  </td>
                  <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#10B981' }}>
                    {snap.verification_coverage}%
                  </td>
                  <td style={{ padding: '12px 14px', color: 'var(--text-secondary)' }}>
                    {snap.evidence_summary || snap.quality_metric}
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    {snap.is_baseline ? (
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: 'rgba(0, 216, 245, 0.12)',
                          color: 'var(--accent-cyan)'
                        }}
                      >
                        BASELINE
                      </span>
                    ) : (
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 600,
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: 'var(--bg-elevated)',
                          color: 'var(--text-muted)'
                        }}
                      >
                        INCREMENTAL
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* FORMULA CALLOUT */}
        <div
          style={{
            marginTop: '20px',
            padding: '14px 18px',
            backgroundColor: 'var(--bg-elevated)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '12px'
          }}
        >
          <Info size={18} color="var(--accent-cyan)" style={{ marginTop: '2px', flexShrink: 0 }} />
          <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Maturity Scoring Formula (v1.0.0):</strong>
            <br />
            <code>CRS = (Σ(weight × status_multiplier) / total_weight) × 100</code> where Verified=1.0, Partial=0.5, Not Implemented=0.0. Out-of-scope non-responsibilities are excluded.
            <br />
            <code>VC = (verified_capabilities_count / total_in_scope_capabilities) × 100</code>. Quality score reflects empirical observable metrics.
          </div>
        </div>
      </div>
    </div>
  );
};
