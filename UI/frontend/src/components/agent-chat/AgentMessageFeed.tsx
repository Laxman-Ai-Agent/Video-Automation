import React from 'react';
import { 
  ArrowRight, 
  Clock, 
  Users, 
  RefreshCw, 
  Cpu,
  ShieldAlert 
} from 'lucide-react';

interface AgentMessageFeedProps {
  messages: any[];
  loading: boolean;
  agentMap: Map<string, any>;
  formatTimestamp: (ts?: string) => string;
}

export const AgentMessageFeed: React.FC<AgentMessageFeedProps> = ({
  messages,
  loading,
  agentMap,
  formatTimestamp,
}) => {
  const getAgentLabel = (id: string) => {
    const found = agentMap.get(id);
    return found ? (found.name || found.agent_id) : id;
  };

  if (loading && messages.length === 0) {
    return (
      <div 
        data-testid="agent-feed-loading"
        style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}
      >
        <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 8px auto' }} />
        <p>Loading agent communication log...</p>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div 
        data-testid="agent-feed-empty"
        style={{
          textAlign: 'center',
          padding: '48px 24px',
          backgroundColor: 'var(--bg-elevated)',
          borderRadius: 'var(--radius-sm)',
          border: '1px dashed var(--border-card)'
        }}
      >
        <Users size={32} style={{ color: 'var(--text-muted)', marginBottom: '10px' }} />
        <h4 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
          No Agent Communications Recorded Yet
        </h4>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '440px', margin: '6px auto 0 auto' }}>
          Authentic inter-agent handoffs, requests, and milestone events will appear here in real time as the pipeline processes audio and scenes.
        </p>
      </div>
    );
  }

  return (
    <div 
      data-testid="agent-feed-list"
      style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}
    >
      {messages.map((m, idx) => {
        const sender = m.sender_agent_id || m.source_agent_id || 'System';
        const target = (m.recipient_agent_ids && m.recipient_agent_ids[0]) || m.target_agent_id;
        const stage = m.stage_id;
        const status = m.status || 'completed';
        const isFailed = status === 'failed' || m.metadata?.error;
        const isBlocked = status === 'blocked' || m.metadata?.blocker;
        const model = m.metadata?.model || m.details?.model || m.metadata?.llm;
        const blockerReason = m.metadata?.blocker || m.details?.waiting_for;

        return (
          <div
            key={m.message_id || idx}
            data-testid={`agent-msg-${idx}`}
            style={{
              backgroundColor: 'var(--bg-elevated)',
              border: `1px solid ${isFailed ? 'var(--status-failed-border)' : isBlocked ? 'var(--status-blocked-border)' : 'var(--border-card)'}`,
              borderRadius: 'var(--radius-sm)',
              padding: '14px 18px',
              boxShadow: 'var(--shadow-card)',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px'
            }}
          >
            {/* Top row: Agents & Timestamp */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12.5px' }}>
                <span style={{
                  fontWeight: 600,
                  color: 'var(--accent-blue)',
                  backgroundColor: 'var(--status-running-bg)',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontFamily: 'var(--font-mono)'
                }}>
                  {getAgentLabel(sender)}
                </span>

                {target && (
                  <>
                    <ArrowRight size={13} style={{ color: 'var(--text-muted)' }} />
                    <span style={{
                      fontWeight: 600,
                      color: '#A855F7',
                      backgroundColor: 'rgba(168, 85, 247, 0.15)',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontFamily: 'var(--font-mono)'
                    }}>
                      {getAgentLabel(target)}
                    </span>
                  </>
                )}

                {stage && (
                  <span style={{
                    fontSize: '11px',
                    color: 'var(--text-secondary)',
                    backgroundColor: 'var(--bg-card)',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-card)'
                  }}>
                    Stage: {stage}
                  </span>
                )}

                {model && (
                  <span style={{
                    fontSize: '11px',
                    color: 'var(--accent-cyan)',
                    backgroundColor: 'rgba(0, 216, 245, 0.12)',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '3px'
                  }}>
                    <Cpu size={11} />
                    {model}
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: isFailed ? 'var(--status-failed)' : isBlocked ? 'var(--status-blocked)' : 'var(--status-completed)',
                  backgroundColor: isFailed ? 'var(--status-failed-bg)' : isBlocked ? 'var(--status-blocked-bg)' : 'var(--status-completed-bg)',
                  padding: '1px 6px',
                  borderRadius: '3px',
                  border: `1px solid ${isFailed ? 'var(--status-failed-border)' : isBlocked ? 'var(--status-blocked-border)' : 'var(--status-completed-border)'}`
                }}>
                  {isFailed ? 'FAILED' : isBlocked ? 'BLOCKED' : status.toUpperCase()}
                </span>

                <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={11} />
                  {formatTimestamp(m.timestamp)}
                </span>
              </div>
            </div>

            {/* Content text */}
            <div style={{
              fontSize: '13px',
              color: 'var(--text-primary)',
              lineHeight: 1.5,
              backgroundColor: 'var(--bg-card)',
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid var(--border-card)',
              fontFamily: 'var(--font-mono)'
            }}>
              {m.content || m.technical_message || JSON.stringify(m.metadata || {})}
            </div>

            {/* Blockers details if blocked */}
            {blockerReason && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '12px',
                color: 'var(--status-blocked)',
                backgroundColor: 'var(--status-blocked-bg)',
                padding: '4px 8px',
                borderRadius: '4px'
              }}>
                <ShieldAlert size={13} />
                <span>Waiting for: {blockerReason}</span>
              </div>
            )}

            {/* Telugu line if available */}
            {m.telugu_activity && (
              <div style={{
                fontSize: '12px',
                color: 'var(--accent-cyan)',
                fontWeight: 500,
                paddingLeft: '4px'
              }}>
                {m.telugu_activity}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
