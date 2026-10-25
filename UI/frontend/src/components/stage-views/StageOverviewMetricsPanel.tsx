import React from 'react';
import { Cpu, FileAudio } from 'lucide-react';
import { StageConfig, StageState } from '../../types/pipeline';
import { SubtaskStep } from '../../services/api';

interface StageOverviewMetricsPanelProps {
  config: StageConfig;
  state?: StageState;
  isCompleted: boolean;
  elapsedSec: number;
  formatElapsedSeconds: (seconds: number) => string;
  subSteps: SubtaskStep[];
  subDone: number;
  setActiveTab: (tab: any) => void;
}

export const StageOverviewMetricsPanel: React.FC<StageOverviewMetricsPanelProps> = ({
  config,
  state,
  isCompleted,
  elapsedSec,
  formatElapsedSeconds,
  subSteps,
  subDone,
  setActiveTab,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Timing & Metric Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '12px'
      }}>
        <div style={{
          backgroundColor: 'var(--bg-elevated)',
          padding: '14px 16px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)'
        }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Elapsed Duration</span>
          <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
            {elapsedSec > 0 ? formatElapsedSeconds(elapsedSec) : '—'}
          </div>
        </div>

        <div style={{
          backgroundColor: 'var(--bg-elevated)',
          padding: '14px 16px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)'
        }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Attempt Count</span>
          <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
            {state?.attempt || 1}
          </div>
        </div>
      </div>

      {/* Subtasks Completion Summary */}
      <div style={{
        backgroundColor: 'var(--bg-elevated)',
        padding: '16px 18px',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-card)',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '12.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
            Subtasks Completion
          </span>
          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
            {subSteps.length ? `${subDone} / ${subSteps.length} passed in the last report` : 'No step report'}
          </span>
        </div>
        {/* Progress bar */}
        <div style={{
          width: '100%',
          height: '6px',
          backgroundColor: 'var(--bg-card)',
          borderRadius: '3px',
          overflow: 'hidden'
        }}>
          <div style={{
            width: `${subSteps.length > 0 ? (subDone / subSteps.length) * 100 : 0}%`,
            height: '100%',
            backgroundColor: isCompleted ? 'var(--status-completed)' : 'var(--accent-cyan)',
            transition: 'width 0.3s ease'
          }} />
        </div>
      </div>

      {/* Agent Preview Card */}
      <div style={{
        backgroundColor: 'var(--bg-elevated)',
        padding: '16px 18px',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-card)',
        display: 'flex',
        alignItems: 'center',
        gap: '14px'
      }}>
        <div style={{
          width: '42px',
          height: '42px',
          borderRadius: 'var(--radius-sm)',
          backgroundColor: 'rgba(0, 216, 245, 0.12)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--accent-cyan)',
          flexShrink: 0
        }}>
          <Cpu size={20} />
        </div>
        <div>
          <div style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {config.agentName}
          </div>
          <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
            ID: {config.agentId} • Category: {config.category.toUpperCase()}
          </div>
        </div>
      </div>

      {/* Quick Action: Switch to Audio & Transcript tab (for analyzer stage) */}
      {config.id === 'analyzer' && (
        <button
          onClick={() => setActiveTab('scenes')}
          data-testid="drawer-open-audio-analysis-btn"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: 'rgba(24, 144, 255, 0.12)',
            border: '1px solid rgba(24, 144, 255, 0.35)',
            borderRadius: 'var(--radius-sm)',
            padding: '12px 16px',
            color: '#FFFFFF',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'background-color 0.15s ease'
          }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(24, 144, 255, 0.22)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'rgba(24, 144, 255, 0.12)'; }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileAudio size={16} color="var(--accent-blue)" />
            <span>Inspect Audio & Telugu Transcript</span>
          </div>
          <span style={{ fontSize: '12px', color: 'var(--accent-cyan)', fontWeight: 700 }}>Open Transcript →</span>
        </button>
      )}
    </div>
  );
};
