import React, { useState, useEffect } from 'react';
import { 
  X, 
  MessageSquare, 
  ArrowRight, 
  Clock, 
  Users, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Bot,
  Activity,
  Layers,
  Cpu,
  ShieldAlert
} from 'lucide-react';
import { fetchAgentCommunications } from '../services/api';

interface AgentCommunicationPanelProps {
  projectId: string;
  agents: any[];
  isOpen?: boolean;
  onClose?: () => void;
  isPipelineRunning: boolean;
}

export const AgentCommunicationPanel: React.FC<AgentCommunicationPanelProps> = ({
  projectId,
  agents,
  isOpen = true,
  onClose,
  isPipelineRunning
}) => {
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'feed' | 'agents'>('feed');

  // Agent lookup map
  const agentMap = React.useMemo(() => {
    const map = new Map<string, any>();
    agents.forEach((a) => {
      if (a.agent_id) map.set(a.agent_id, a);
      if (a.name) map.set(a.name, a);
    });
    return map;
  }, [agents]);

  const loadCommunications = async () => {
    if (!projectId) return;
    try {
      const data = await fetchAgentCommunications(projectId, 100);
      if (data && data.messages) {
        setMessages(data.messages);
      }
    } catch (err) {
      console.error('Failed to load agent communications:', err);
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    loadCommunications().finally(() => setLoading(false));

    const interval = setInterval(loadCommunications, isPipelineRunning ? 2000 : 4000);
    return () => clearInterval(interval);
  }, [isOpen, projectId, isPipelineRunning]);

  if (!isOpen) return null;

  const getAgentLabel = (id: string) => {
    const found = agentMap.get(id);
    return found ? (found.name || found.agent_id) : id;
  };

  const getAgentRole = (id: string) => {
    const found = agentMap.get(id);
    return found?.role || found?.domain || 'Video Engine Subagent';
  };

  const formatTimestamp = (ts?: string) => {
    if (!ts) return '';
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return ts;
    }
  };

  return (
    <div 
      role="dialog"
      aria-label="Agent Communication"
      data-testid="agent-communication-panel"
      style={{
        width: '100%',
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        border: '1px solid var(--border-card)',
        minHeight: '600px'
      }}
    >
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 24px',
          backgroundColor: 'var(--sidebar-bg)',
          color: '#FFFFFF',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '6px',
              backgroundColor: 'var(--accent-blue)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <MessageSquare size={18} color="#FFFFFF" />
            </div>
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, letterSpacing: '-0.3px' }}>
                Agent Communication & Handoff Panel
              </h3>
              <p style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.65)', margin: 0 }}>
                Project: {projectId} • {messages.length} live logged communications
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {isPipelineRunning && (
              <span style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                fontSize: '11px',
                color: 'var(--status-completed)',
                backgroundColor: 'var(--status-completed-bg)',
                padding: '3px 8px',
                borderRadius: '4px',
                fontWeight: 600
              }}>
                <RefreshCw size={12} className="animate-spin" />
                Live Syncing
              </span>
            )}

            {onClose && (
              <button
                onClick={onClose}
                aria-label="Close"
                title="Return to Pipeline Execution Flow"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'rgba(255, 255, 255, 0.65)',
                  cursor: 'pointer',
                  padding: '6px',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'color 0.15s ease'
                }}
                onMouseEnter={(e) => { e.currentTarget.style.color = '#FFFFFF'; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(255, 255, 255, 0.65)'; }}
              >
                <X size={20} />
              </button>
            )}
          </div>
        </div>

        {/* Navigation Tabs */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '24px',
          padding: '0 24px',
          borderBottom: '1px solid var(--border-card)',
          backgroundColor: 'var(--bg-elevated)'
        }}>
          <button
            onClick={() => setActiveTab('feed')}
            style={{
              padding: '12px 4px',
              border: 'none',
              background: 'none',
              fontSize: '13px',
              fontWeight: activeTab === 'feed' ? 600 : 400,
              color: activeTab === 'feed' ? 'var(--accent-blue)' : 'var(--text-secondary)',
              borderBottom: activeTab === 'feed' ? '2px solid var(--accent-blue)' : '2px solid transparent',
              cursor: 'pointer'
            }}
          >
            Communication Log ({messages.length})
          </button>

          <button
            onClick={() => setActiveTab('agents')}
            data-testid="agent-registry-tab"
            style={{
              padding: '12px 4px',
              border: 'none',
              background: 'none',
              fontSize: '13px',
              fontWeight: activeTab === 'agents' ? 600 : 400,
              color: activeTab === 'agents' ? 'var(--accent-blue)' : 'var(--text-secondary)',
              borderBottom: activeTab === 'agents' ? '2px solid var(--accent-blue)' : '2px solid transparent',
              cursor: 'pointer'
            }}
          >
            Agent Registry ({agents.length})
          </button>
        </div>

        {/* Content Body */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px 24px'
        }}>
          {activeTab === 'feed' && (
            <div>
              {loading && messages.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 8px auto' }} />
                  <p>Loading agent communication log...</p>
                </div>
              ) : messages.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '48px 24px',
                  backgroundColor: 'var(--bg-elevated)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px dashed var(--border-card)'
                }}>
                  <Users size={32} style={{ color: 'var(--text-muted)', marginBottom: '10px' }} />
                  <h4 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    No Agent Communications Recorded Yet
                  </h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '440px', margin: '6px auto 0 auto' }}>
                    Authentic inter-agent handoffs, requests, and milestone events will appear here in real time as the pipeline processes audio and scenes.
                  </p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
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
              )}
            </div>
          )}

          {activeTab === 'agents' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '12px' }}>
              {agents.map((ag) => (
                <div
                  key={ag.agent_id || ag.name}
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
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 24px',
          borderTop: '1px solid var(--border-card)',
          backgroundColor: 'var(--bg-elevated)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Data source: Authoritative project communication log (communications.jsonl)
          </span>
          {onClose && (
            <button
              onClick={onClose}
              aria-label="Close"
              style={{
                padding: '6px 18px',
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-card)',
                borderRadius: '3px',
                fontSize: '13px',
                color: 'var(--text-primary)',
                cursor: 'pointer'
              }}
            >
              Close
            </button>
          )}
        </div>
    </div>
  );
};
