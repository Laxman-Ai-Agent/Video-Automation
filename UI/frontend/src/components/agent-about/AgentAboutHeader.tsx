import React from 'react';
import { Cpu, Check, Copy, Search } from 'lucide-react';
import { AgentAboutData } from '../../data/agentAboutData';

export interface AgentAboutHeaderProps {
  data: AgentAboutData;
  activeSection: string;
  setActiveSection: (sec: string) => void;
  searchTerm: string;
  setSearchTerm: (val: string) => void;
  copiedKey: string | null;
  handleCopy: (text: string, key: string) => void;
}

const sectionsList = [
  { id: 'all', label: 'All Details' },
  { id: 'overview', label: 'A. Overview' },
  { id: 'responsibilities', label: 'B. What It Does' },
  { id: 'flow', label: 'C. Internal Flow' },
  { id: 'inputs', label: 'D. Inputs & Tools' },
  { id: 'outputs', label: 'E. Outputs' },
  { id: 'llm', label: 'F. LLM Usage' },
  { id: 'capabilities', label: 'G. Capabilities' },
  { id: 'boundaries', label: 'H. Boundaries' },
  { id: 'gaps', label: 'I. Gaps' },
  { id: 'testing', label: 'J. Testing' },
  { id: 'improvements', label: 'K. Improvements' },
  { id: 'source', label: 'L. Source Code' }
];

export const AgentAboutHeader: React.FC<AgentAboutHeaderProps> = ({
  data,
  activeSection,
  setActiveSection,
  searchTerm,
  setSearchTerm,
  copiedKey,
  handleCopy
}) => {
  return (
    <div
      style={{
        backgroundColor: '#0C1526',
        border: '1px solid rgba(0, 216, 245, 0.25)',
        borderRadius: '10px',
        padding: '24px',
        position: 'relative',
        overflow: 'hidden',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '10px',
              backgroundColor: 'rgba(0, 216, 245, 0.12)',
              border: '1px solid rgba(0, 216, 245, 0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-cyan)',
              flexShrink: 0
            }}
          >
            <Cpu size={30} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 800, color: '#FFFFFF', margin: 0, letterSpacing: '-0.3px' }}>
                {data.name}
              </h2>
              {data.badge && (
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    fontFamily: 'var(--font-mono)',
                    backgroundColor: 'rgba(0, 216, 245, 0.15)',
                    color: 'var(--accent-cyan)',
                    border: '1px solid rgba(0, 216, 245, 0.35)',
                    padding: '2px 8px',
                    borderRadius: '4px'
                  }}
                >
                  {data.badge}
                </span>
              )}
            </div>

            <div
              style={{
                fontSize: '12px',
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-secondary)',
                marginTop: '5px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                flexWrap: 'wrap'
              }}
            >
              <span>Agent ID: <strong style={{ color: 'var(--accent-cyan)' }}>{data.agentId}</strong></span>
              <span>•</span>
              <span>Stage ID: <strong style={{ color: '#FFFFFF' }}>{data.stageId}</strong></span>
              <span>•</span>
              <span>Category: <strong style={{ textTransform: 'uppercase', color: 'var(--accent-orange)' }}>{data.category}</strong></span>
              <span>•</span>
              <span>Version: <strong style={{ color: '#52C41A' }}>{data.version}</strong></span>
            </div>

            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '8px', lineHeight: 1.4 }}>
              {data.role}
            </div>
          </div>
        </div>

        {/* Quick Copy Badge */}
        <button
          onClick={() => handleCopy(`SYSTEM/agents/video_generation_agents/${data.agentId}/agent.py`, 'hero-agent-path')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            backgroundColor: 'rgba(255, 255, 255, 0.06)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '4px',
            color: copiedKey === 'hero-agent-path' ? 'var(--status-completed)' : 'var(--text-secondary)',
            fontSize: '11.5px',
            fontFamily: 'var(--font-mono)',
            cursor: 'pointer',
            transition: 'all 0.15s ease'
          }}
          title="Copy path to agent implementation"
        >
          {copiedKey === 'hero-agent-path' ? <Check size={13} /> : <Copy size={13} />}
          <span>agent.py path</span>
        </button>
      </div>

      {/* Quick Filter Navigation Bar */}
      <div
        style={{
          marginTop: '20px',
          paddingTop: '16px',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
          flexWrap: 'wrap'
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            overflowX: 'auto',
            paddingBottom: '4px'
          }}
        >
          {sectionsList.map((sec) => (
            <button
              key={sec.id}
              onClick={() => setActiveSection(sec.id)}
              style={{
                padding: '5px 10px',
                borderRadius: '4px',
                border: 'none',
                backgroundColor: activeSection === sec.id ? 'var(--accent-cyan)' : 'rgba(255, 255, 255, 0.05)',
                color: activeSection === sec.id ? '#060D1A' : 'var(--text-secondary)',
                fontSize: '11.5px',
                fontWeight: 700,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease'
              }}
            >
              {sec.label}
            </button>
          ))}
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: 'rgba(255, 255, 255, 0.06)',
            borderRadius: '4px',
            padding: '4px 10px',
            gap: '6px',
            border: '1px solid rgba(255, 255, 255, 0.1)'
          }}
        >
          <Search size={13} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search in agent spec..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              background: 'none',
              border: 'none',
              outline: 'none',
              color: '#FFFFFF',
              fontSize: '12px',
              width: '150px'
            }}
          />
        </div>
      </div>
    </div>
  );
};
