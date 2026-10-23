import React, { useState, useEffect } from 'react';
import { Users, Cpu, ShieldCheck, Video, CheckCircle2, Search, Filter, ArrowRight, Sparkles } from 'lucide-react';
import { AgentIntelligenceDetailView } from '../components/AgentIntelligenceDetailView';

interface AgentsCenterPageProps {
  agents: any[];
}

export const AgentsCenterPage: React.FC<AgentsCenterPageProps> = ({ agents }) => {
  const [filter, setFilter] = useState<'all' | 'video' | 'system'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('agentId') || params.get('agent') || null;
  });

  // Sync selectedAgentId with URL search params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlAgent = params.get('agentId') || params.get('agent');
    if (urlAgent && urlAgent !== selectedAgentId) {
      setSelectedAgentId(urlAgent);
    }
  }, []);

  const handleSelectAgent = (agentId: string) => {
    setSelectedAgentId(agentId);
    const url = new URL(window.location.href);
    url.searchParams.set('agentId', agentId);
    window.history.replaceState({}, '', url.toString());
  };

  const handleBackToGrid = () => {
    setSelectedAgentId(null);
    const url = new URL(window.location.href);
    url.searchParams.delete('agentId');
    url.searchParams.delete('agent');
    window.history.replaceState({}, '', url.toString());
  };

  // If an agent is selected, render the dedicated full-page Agent Intelligence Detail View
  if (selectedAgentId) {
    return (
      <AgentIntelligenceDetailView
        agentId={selectedAgentId}
        onBack={handleBackToGrid}
      />
    );
  }

  const filteredAgents = agents.filter((a) => {
    const isVideo = a.category === 'video_engine_agent' || a.category === 'video_agent' || a.category === 'audio' || a.category === 'visual' || a.category === 'motion';
    if (filter === 'video' && !isVideo) return false;
    if (filter === 'system' && isVideo) return false;
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      const matchName = a.name?.toLowerCase().includes(q);
      const matchId = a.agent_id?.toLowerCase().includes(q);
      const matchPurpose = a.purpose?.toLowerCase().includes(q);
      const matchCap = Array.isArray(a.capabilities) && a.capabilities.some((c: string) => c.toLowerCase().includes(q));
      return matchName || matchId || matchPurpose || matchCap;
    }
    return true;
  });

  const videoCount = agents.filter(a => a.category !== 'system_subagent' && a.agent_id !== 'main_architecture_agent').length || 13;
  const systemCount = agents.filter(a => a.category === 'system_subagent' || a.agent_id === 'main_architecture_agent').length || 7;

  return (
    <div data-testid="agents-center-page" style={{ padding: '32px', maxWidth: '1440px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
              Canonical Agent Swarm ({agents.length || 20} Registered)
            </h2>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '3px 10px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'rgba(0, 216, 245, 0.12)',
                color: 'var(--accent-cyan)'
              }}
            >
              INTELLIGENCE & GROWTH SYSTEM
            </span>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '6px' }}>
            Authoritative registry of {videoCount} specialized video pipeline agents and {systemCount} core system agents. Click any card to inspect its complete technical profile, growth scores, and verified upgrades.
          </p>
        </div>

        {/* Filter Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {[
            { id: 'all', label: `All (${agents.length || 20})` },
            { id: 'video', label: `Video Pipeline (${videoCount})` },
            { id: 'system', label: `System Subagents (${systemCount})` }
          ].map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id as any)}
              data-testid={`filter-${f.id}`}
              style={{
                padding: '7px 16px',
                borderRadius: 'var(--radius-full)',
                border: 'none',
                backgroundColor: filter === f.id ? 'var(--accent-cyan)' : 'var(--bg-elevated)',
                color: filter === f.id ? '#060D1A' : 'var(--text-secondary)',
                fontWeight: 700,
                fontSize: '12.5px',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Search Input Bar */}
      <div style={{ marginBottom: '24px', position: 'relative', maxWidth: '480px' }}>
        <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)' }} />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search agents by name, ID, or capability..."
          data-testid="agents-search-input"
          style={{
            width: '100%',
            padding: '10px 14px 10px 40px',
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-card)',
            borderRadius: 'var(--radius-lg)',
            color: 'var(--text-primary)',
            fontSize: '13px',
            outline: 'none'
          }}
        />
      </div>

      {/* Agents Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))', gap: '20px' }}>
        {filteredAgents.map((agent) => {
          const isVideo = agent.category === 'video_engine_agent' || agent.category === 'video_agent' || agent.category === 'audio' || agent.category === 'visual' || agent.category === 'motion';

          return (
            <div
              key={agent.agent_id}
              onClick={() => handleSelectAgent(agent.agent_id)}
              data-testid={`agent-card-${agent.agent_id}`}
              style={{
                backgroundColor: 'var(--bg-card)',
                borderRadius: 'var(--radius-xl)',
                border: '1px solid var(--border-card)',
                padding: '22px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                minHeight: '200px',
                boxShadow: 'var(--shadow-card)',
                cursor: 'pointer',
                transition: 'transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-3px)';
                e.currentTarget.style.borderColor = isVideo ? 'var(--accent-cyan)' : 'var(--accent-orange)';
                e.currentTarget.style.boxShadow = isVideo ? '0 8px 24px rgba(0, 216, 245, 0.15)' : '0 8px 24px rgba(255, 107, 74, 0.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.borderColor = 'var(--border-card)';
                e.currentTarget.style.boxShadow = 'var(--shadow-card)';
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: isVideo ? 'rgba(0, 216, 245, 0.12)' : 'rgba(255, 107, 74, 0.12)',
                      color: isVideo ? 'var(--accent-cyan)' : 'var(--accent-orange)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                  >
                    {isVideo ? <Video size={18} /> : <ShieldCheck size={18} />}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'var(--status-completed-bg)',
                        color: 'var(--status-completed)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      <CheckCircle2 size={11} />
                      READY
                    </span>
                  </div>
                </div>

                <h3 style={{ fontSize: '16.5px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '14px', marginBottom: '2px' }}>
                  {agent.name}
                </h3>
                <p style={{ fontSize: '11.5px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {agent.agent_id}
                </p>

                <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '10px', lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {agent.purpose}
                </p>
              </div>

              <div style={{ marginTop: '18px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    color: isVideo ? 'var(--accent-cyan)' : 'var(--accent-orange)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px'
                  }}
                >
                  {isVideo ? 'Video Generation Pipeline' : 'System Subagent'}
                </span>

                <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  View Profile <ArrowRight size={13} />
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
