import React from 'react';
import { Cpu, ShieldCheck } from 'lucide-react';

interface EngineReadinessCardProps {
  agents: any[];
  backendHealthy: boolean;
  activeLlmCount: number;
}

export const EngineReadinessCard: React.FC<EngineReadinessCardProps> = ({
  agents,
  backendHealthy,
  activeLlmCount,
}) => {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '16px'
    }}>
      {/* Swarm Status Card */}
      <div style={{
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-card)',
        boxShadow: 'var(--shadow-card)',
        padding: '20px 24px'
      }}>
        <h3 style={{
          fontSize: '15px',
          fontWeight: 700,
          color: 'var(--text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '12px'
        }}>
          <Cpu size={17} color="var(--accent-blue)" />
          21 Autonomous Agents Swarm
        </h3>

        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '10px',
          marginBottom: '16px'
        }}>
          <div style={{
            backgroundColor: 'var(--bg-elevated)',
            padding: '12px',
            borderRadius: '4px',
            border: '1px solid var(--border-subtle)'
          }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Pipeline Specialists</div>
            <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--accent-cyan)', marginTop: '2px' }}>
              12 Online
            </div>
          </div>

          <div style={{
            backgroundColor: 'var(--bg-elevated)',
            padding: '12px',
            borderRadius: '4px',
            border: '1px solid var(--border-subtle)'
          }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>System Agents</div>
            <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
              7 Active
            </div>
          </div>
        </div>

        <div style={{
          fontSize: '12px',
          color: 'var(--text-secondary)',
          lineHeight: 1.6,
          backgroundColor: 'var(--bg-elevated)',
          padding: '12px',
          borderRadius: '4px',
          border: '1px solid var(--border-subtle)'
        }}>
          <div>[API Backend] FastAPI :8000: <strong style={{ color: backendHealthy ? 'var(--status-completed)' : 'var(--status-failed)' }}>{backendHealthy ? 'HEALTHY' : 'OFFLINE'}</strong></div>
          <div>[LLM In-Flight] Dispatches: <strong style={{ color: 'var(--accent-cyan)' }}>{activeLlmCount} Active</strong></div>
          <div>[Remotion Engine] 1080p HD: <strong style={{ color: 'var(--status-completed)' }}>READY</strong></div>
        </div>
      </div>
    </div>
  );
};
