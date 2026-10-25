import React, { useState, useEffect, useMemo } from 'react';
import { 
  X, 
  MessageSquare, 
  RefreshCw 
} from 'lucide-react';
import { fetchAgentCommunications } from '../services/api';
import { AgentMessageFeed } from './agent-chat/AgentMessageFeed';
import { AgentRegistryView } from './agent-chat/AgentRegistryView';

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
  const agentMap = useMemo(() => {
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
          <AgentMessageFeed
            messages={messages}
            loading={loading}
            agentMap={agentMap}
            formatTimestamp={formatTimestamp}
          />
        )}

        {activeTab === 'agents' && (
          <AgentRegistryView agents={agents} />
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
