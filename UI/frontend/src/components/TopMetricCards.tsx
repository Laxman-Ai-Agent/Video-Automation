import React from 'react';
import { Info, ArrowUp, ArrowDown } from 'lucide-react';

interface TopMetricCardsProps {
  totalRuns?: number;
  activeStagesCount?: number;
  totalAgentsCount?: number;
  overallProgress?: number;
}

export const TopMetricCards: React.FC<TopMetricCardsProps> = ({
  totalRuns = 1430,
  activeStagesCount = 12,
  totalAgentsCount = 21,
  overallProgress = 88
}) => {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
      gap: '16px',
      marginBottom: '20px'
    }}>
      {/* CARD 1: Total Sales / Projects */}
      <div style={{
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-card)',
        padding: '20px 24px 16px 24px',
        boxShadow: 'var(--shadow-card)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'background-color 0.2s ease, border-color 0.2s ease'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: 'var(--text-muted)',
          fontSize: '14px',
          fontWeight: 400
        }}>
          <span>Total Pipeline Runs</span>
          <button style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}>
            <Info size={15} />
          </button>
        </div>

        <div style={{
          fontSize: '30px',
          fontWeight: 700,
          color: 'var(--text-primary)',
          marginTop: '8px',
          marginBottom: '10px',
          fontFamily: 'var(--font-sans)',
          letterSpacing: '-0.5px'
        }}>
          $ 154,430
        </div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          fontSize: '13px',
          color: 'var(--text-secondary)',
          marginTop: 'auto',
          paddingBottom: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span>Week ratio</span>
            <span style={{ fontWeight: 600 }}>13%</span>
            <span style={{ color: 'var(--status-failed)', display: 'flex', alignItems: 'center' }}>
              <ArrowUp size={13} strokeWidth={3} />
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span>Day ratio</span>
            <span style={{ fontWeight: 600 }}>10%</span>
            <span style={{ color: 'var(--status-completed)', display: 'flex', alignItems: 'center' }}>
              <ArrowDown size={13} strokeWidth={3} />
            </span>
          </div>
        </div>

        <div style={{
          borderTop: '1px solid var(--border-card)',
          paddingTop: '10px',
          fontSize: '13px',
          color: 'var(--text-secondary)'
        }}>
          Day Operations <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>15,443 ops</span>
        </div>
      </div>

      {/* CARD 2: Visits / Multi-wave Chart */}
      <div style={{
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-card)',
        padding: '20px 24px 16px 24px',
        boxShadow: 'var(--shadow-card)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'background-color 0.2s ease, border-color 0.2s ease'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: 'var(--text-muted)',
          fontSize: '14px',
          fontWeight: 400
        }}>
          <span>Active Stage Events</span>
          <button style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}>
            <Info size={15} />
          </button>
        </div>

        <div style={{
          fontSize: '30px',
          fontWeight: 700,
          color: 'var(--text-primary)',
          marginTop: '8px',
          marginBottom: '6px',
          fontFamily: 'var(--font-sans)',
          letterSpacing: '-0.5px'
        }}>
          6,480
        </div>

        {/* SVG Multi-Layer Wave matching reference image */}
        <div style={{ marginTop: 'auto', paddingBottom: '8px', height: '44px', width: '100%', overflow: 'hidden' }}>
          <svg viewBox="0 0 200 50" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
            <defs>
              <linearGradient id="waveCyan" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#13C2C2" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#13C2C2" stopOpacity="0.1" />
              </linearGradient>
              <linearGradient id="waveBlue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#1890FF" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#1890FF" stopOpacity="0.1" />
              </linearGradient>
              <linearGradient id="waveOrange" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#FA541C" stopOpacity="0.85" />
                <stop offset="100%" stopColor="#FA541C" stopOpacity="0.15" />
              </linearGradient>
            </defs>

            <path
              d="M0,50 L0,32 Q25,8 55,28 T110,18 T165,8 T200,32 L200,50 Z"
              fill="url(#waveBlue)"
            />
            <path
              d="M0,50 L0,38 Q30,15 65,34 T130,12 T180,6 T200,28 L200,50 Z"
              fill="url(#waveCyan)"
            />
            <path
              d="M0,50 L0,44 Q35,26 75,38 T140,24 T185,34 T200,42 L200,50 Z"
              fill="url(#waveOrange)"
            />
          </svg>
        </div>

        <div style={{
          borderTop: '1px solid var(--border-card)',
          paddingTop: '10px',
          fontSize: '13px',
          color: 'var(--text-secondary)'
        }}>
          Stage Ingest <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>4,280 ms</span>
        </div>
      </div>

      {/* CARD 3: Payments / Bar Sparkline */}
      <div style={{
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-card)',
        padding: '20px 24px 16px 24px',
        boxShadow: 'var(--shadow-card)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'background-color 0.2s ease, border-color 0.2s ease'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: 'var(--text-muted)',
          fontSize: '14px',
          fontWeight: 400
        }}>
          <span>Canonical Agents</span>
          <button style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}>
            <Info size={15} />
          </button>
        </div>

        <div style={{
          fontSize: '30px',
          fontWeight: 700,
          color: 'var(--text-primary)',
          marginTop: '8px',
          marginBottom: '6px',
          fontFamily: 'var(--font-sans)',
          letterSpacing: '-0.5px'
        }}>
          {totalAgentsCount} Active
        </div>

        {/* Vertical Blue Bars matching reference image */}
        <div style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: '8px',
          height: '44px',
          marginTop: 'auto',
          paddingBottom: '8px',
          paddingLeft: '4px'
        }}>
          <div style={{ flex: 1, height: '40%', backgroundColor: 'var(--accent-blue)', borderRadius: '1px' }} />
          <div style={{ flex: 1, height: '95%', backgroundColor: 'var(--accent-blue)', borderRadius: '1px' }} />
          <div style={{ flex: 1, height: '75%', backgroundColor: 'var(--accent-blue)', borderRadius: '1px' }} />
          <div style={{ flex: 1, height: '35%', backgroundColor: 'var(--accent-blue)', borderRadius: '1px' }} />
          <div style={{ flex: 1, height: '65%', backgroundColor: 'var(--accent-blue)', borderRadius: '1px' }} />
        </div>

        <div style={{
          borderTop: '1px solid var(--border-card)',
          paddingTop: '10px',
          fontSize: '13px',
          color: 'var(--text-secondary)'
        }}>
          Execution Success Rate <span style={{ fontWeight: 600, color: 'var(--status-completed)' }}>98.4%</span>
        </div>
      </div>

      {/* CARD 4: Operation Effect / Overall Progress */}
      <div style={{
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-card)',
        padding: '20px 24px 16px 24px',
        boxShadow: 'var(--shadow-card)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        transition: 'background-color 0.2s ease, border-color 0.2s ease'
      }}>
        <div style={{
          color: 'var(--text-muted)',
          fontSize: '14px',
          fontWeight: 400,
          marginBottom: '4px'
        }}>
          Operation Effect
        </div>

        <div style={{
          fontSize: '36px',
          fontWeight: 700,
          color: 'var(--text-primary)',
          marginTop: '4px',
          marginBottom: '4px',
          fontFamily: 'var(--font-sans)'
        }}>
          {overallProgress}%
        </div>

        <div style={{
          fontSize: '12px',
          color: 'var(--status-completed)',
          fontWeight: 600,
          backgroundColor: 'var(--status-completed-bg)',
          border: '1px solid var(--status-completed-border)',
          padding: '2px 10px',
          borderRadius: '10px',
          marginTop: '6px'
        }}>
          12 Stages Synchronized
        </div>
      </div>
    </div>
  );
};
