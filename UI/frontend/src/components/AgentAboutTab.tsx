import React, { useState, useMemo } from 'react';
import { HelpCircle } from 'lucide-react';
import { getAgentAboutData, AgentAboutData } from '../data/agentAboutData';
import { AgentAboutHeader } from './agent-about/AgentAboutHeader';
import { AgentAboutCoreSpecs } from './agent-about/AgentAboutCoreSpecs';
import { AgentAboutAudits } from './agent-about/AgentAboutAudits';

interface AgentAboutTabProps {
  stageId: string;
  agentId?: string;
  isFullPage?: boolean;
}

export const AgentAboutTab: React.FC<AgentAboutTabProps> = ({
  stageId,
  agentId,
  isFullPage = false
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [activeSection, setActiveSection] = useState<string>('all');

  const data: AgentAboutData | null = useMemo(() => {
    return getAgentAboutData(stageId) || (agentId ? getAgentAboutData(agentId) : null);
  }, [stageId, agentId]);

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  if (!data) {
    return (
      <div
        data-testid="agent-about-empty"
        style={{
          padding: '40px 24px',
          textAlign: 'center',
          backgroundColor: 'var(--bg-card)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
          color: 'var(--text-secondary)'
        }}
      >
        <HelpCircle size={36} color="var(--accent-cyan)" style={{ margin: '0 auto 12px' }} />
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
          About Specification Not Found
        </h3>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '6px' }}>
          No registered evidence specification for stage: <code>{stageId}</code> / agent: <code>{agentId || 'none'}</code>.
        </p>
      </div>
    );
  }

  return (
    <div
      data-testid="agent-about-tab-container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '24px',
        color: 'var(--text-primary)',
        paddingBottom: '40px'
      }}
    >
      <AgentAboutHeader
        data={data}
        activeSection={activeSection}
        setActiveSection={setActiveSection}
        searchTerm={searchTerm}
        setSearchTerm={setSearchTerm}
        copiedKey={copiedKey}
        handleCopy={handleCopy}
      />

      <AgentAboutCoreSpecs
        data={data}
        activeSection={activeSection}
        isFullPage={isFullPage}
        copiedKey={copiedKey}
        handleCopy={handleCopy}
      />

      <AgentAboutAudits
        data={data}
        activeSection={activeSection}
        isFullPage={isFullPage}
        copiedKey={copiedKey}
        handleCopy={handleCopy}
      />
    </div>
  );
};
