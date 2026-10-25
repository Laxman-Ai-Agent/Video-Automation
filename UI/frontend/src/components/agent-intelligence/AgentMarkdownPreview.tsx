import React from 'react';
import { Copy, Check } from 'lucide-react';
import { generateAgentMarkdownExport, AgentAboutData } from '../../data/agentAboutData';

export interface AgentMarkdownPreviewProps {
  aboutData: AgentAboutData;
  growthData: any | null;
  upgradesData: any[];
  copied: boolean;
  handleCopyAllDetails: () => void;
}

export const AgentMarkdownPreview: React.FC<AgentMarkdownPreviewProps> = ({
  aboutData,
  growthData,
  upgradesData,
  copied,
  handleCopyAllDetails
}) => {
  return (
    <div
      data-testid="markdown-preview-content"
      style={{
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-xl)',
        border: '1px solid var(--border-card)',
        padding: '24px',
        boxShadow: 'var(--shadow-card)'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
            Comprehensive Markdown Technical Profile (19 Specification Points)
          </h3>
          <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Formatted for direct sharing with Claude, GPT, or another LLM for architectural critique and upgrade planning.
          </p>
        </div>

        <button
          onClick={handleCopyAllDetails}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            backgroundColor: copied ? '#10B981' : 'var(--accent-cyan)',
            color: '#060D1A',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            cursor: 'pointer',
            fontWeight: 700,
            fontSize: '12.5px'
          }}
        >
          {copied ? <Check size={15} /> : <Copy size={15} />}
          {copied ? 'Copied!' : 'Copy Markdown'}
        </button>
      </div>

      <pre
        style={{
          padding: '20px',
          backgroundColor: 'var(--bg-elevated)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
          fontFamily: 'var(--font-mono)',
          fontSize: '12px',
          color: 'var(--text-primary)',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          maxHeight: '600px',
          overflowY: 'auto'
        }}
      >
        {generateAgentMarkdownExport(aboutData, growthData, upgradesData)}
      </pre>
    </div>
  );
};
