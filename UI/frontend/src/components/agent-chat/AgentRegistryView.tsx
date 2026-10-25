import React from 'react';

interface AgentRegistryViewProps {
  agents: any[];
}

export const AgentRegistryView: React.FC<AgentRegistryViewProps> = ({ agents }) => {
  return (
    <div 
      data-testid="agent-registry-grid"
      style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '12px' }}
    >
      {agents.map((ag) => (
        <div
          key={ag.agent_id || ag.name}
          data-testid={`agent-card-${ag.agent_id || ag.name}`}
          style={{
            border: '1px solid var(--border-card)',
            borderRadius: 'var(--radius-sm)',
            padding: '14px',
            backgroundColor: 'var(--bg-elevated)',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
              {ag.name}
            </span>
            <span style={{
              fontSize: '10px',
              fontWeight: 700,
              color: 'var(--status-completed)',
              backgroundColor: 'var(--status-completed-bg)',
              padding: '1px 5px',
              borderRadius: '3px'
            }}>
              ONLINE
            </span>
          </div>

          <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: 0 }}>
            {ag.description || ag.domain || 'Canonical Video/System Agent'}
          </p>

          <div style={{
            fontSize: '11px',
            color: 'var(--accent-blue)',
            fontFamily: 'var(--font-mono)',
            marginTop: 'auto',
            paddingTop: '6px'
          }}>
            ID: {ag.agent_id}
          </div>
        </div>
      ))}
    </div>
  );
};
