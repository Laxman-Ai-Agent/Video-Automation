import React, { useState, useEffect, useMemo } from 'react';
import {
  ArrowLeft,
  Copy,
  Check,
  TrendingUp,
  History,
  FileCode2,
  ShieldCheck,
  Video,
  CheckCircle2,
  AlertTriangle,
  Layers
} from 'lucide-react';
import { getAgentAboutData, AgentAboutData, generateAgentMarkdownExport } from '../data/agentAboutData';
import { fetchAgentGrowth, fetchAgentUpgrades } from '../services/api';
import { AgentAboutTab } from './AgentAboutTab';
import { AgentGrowthDashboard } from './agent-intelligence/AgentGrowthDashboard';
import { AgentUpgradesView } from './agent-intelligence/AgentUpgradesView';
import { AgentMarkdownPreview } from './agent-intelligence/AgentMarkdownPreview';

interface AgentIntelligenceDetailViewProps {
  agentId: string;
  onBack: () => void;
}

export const AgentIntelligenceDetailView: React.FC<AgentIntelligenceDetailViewProps> = ({
  agentId,
  onBack
}) => {
  const [activeTab, setActiveTab] = useState<'growth' | 'upgrades' | 'about' | 'markdown'>('growth');
  const [copied, setCopied] = useState(false);
  const [growthData, setGrowthData] = useState<any | null>(null);
  const [upgradesData, setUpgradesData] = useState<any[]>([]);
  const [_loading, setLoading] = useState(true);

  // Retrieve static metadata & profile data
  const aboutData: AgentAboutData | null = useMemo(() => {
    return getAgentAboutData(agentId);
  }, [agentId]);

  // Fetch dynamic growth & upgrade history from backend
  useEffect(() => {
    let isMounted = true;
    async function loadIntelligence() {
      setLoading(true);
      try {
        const [growth, upgrades] = await Promise.all([
          fetchAgentGrowth(agentId),
          fetchAgentUpgrades(agentId)
        ]);
        if (isMounted) {
          if (growth) setGrowthData(growth);
          if (upgrades) setUpgradesData(upgrades);
        }
      } catch (err) {
        console.warn('Failed to load agent growth data:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadIntelligence();
    return () => {
      isMounted = false;
    };
  }, [agentId]);

  const handleCopyAllDetails = async () => {
    if (!aboutData) return;
    try {
      const markdown = generateAgentMarkdownExport(aboutData, growthData, upgradesData);
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  if (!aboutData) {
    return (
      <div style={{ padding: '32px', maxWidth: '1200px', margin: '0 auto', textAlign: 'center' }}>
        <button
          onClick={onBack}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            backgroundColor: 'var(--bg-elevated)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            cursor: 'pointer',
            marginBottom: '24px'
          }}
        >
          <ArrowLeft size={16} /> Back to Agents Swarm
        </button>
        <div style={{ padding: '48px', backgroundColor: 'var(--bg-card)', borderRadius: 'var(--radius-xl)' }}>
          <AlertTriangle size={36} color="var(--accent-orange)" style={{ margin: '0 auto 16px' }} />
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
            Agent Profile Not Found: {agentId}
          </h2>
          <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
            The requested agent is not recognized by the canonical registry.
          </p>
        </div>
      </div>
    );
  }

  const isVideo =
    aboutData.category === 'video_engine_agent' ||
    aboutData.category === 'video_agent' ||
    aboutData.category === 'audio' ||
    aboutData.category === 'visual' ||
    aboutData.category === 'motion';

  return (
    <div
      data-testid="agent-intelligence-detail-view"
      style={{
        padding: '24px 32px 48px',
        maxWidth: '1440px',
        margin: '0 auto',
        minHeight: '100%'
      }}
    >
      {/* 1. TOP HEADER & BREADCRUMB */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
          marginBottom: '24px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            onClick={onBack}
            data-testid="back-to-agents-swarm-btn"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              backgroundColor: 'var(--bg-elevated)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-full)',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '13px',
              transition: 'all 0.15s ease'
            }}
          >
            <ArrowLeft size={16} /> Back to All Agents
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: isVideo ? 'rgba(0, 216, 245, 0.12)' : 'rgba(255, 107, 74, 0.12)',
                color: isVideo ? 'var(--accent-cyan)' : 'var(--accent-orange)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              {isVideo ? <Video size={12} /> : <ShieldCheck size={12} />}
              {isVideo ? 'VIDEO PIPELINE' : 'SYSTEM SUBAGENT'}
            </span>

            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--status-completed-bg)',
                color: 'var(--status-completed)',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <CheckCircle2 size={12} />
              {aboutData.badge || 'READY'}
            </span>
          </div>
        </div>

        {/* PROMINENT "COPY ALL AGENT DETAILS" BUTTON */}
        <button
          onClick={handleCopyAllDetails}
          data-testid="copy-all-agent-details-btn"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 20px',
            backgroundColor: copied ? '#10B981' : 'var(--accent-cyan)',
            color: '#060D1A',
            border: 'none',
            borderRadius: 'var(--radius-lg)',
            cursor: 'pointer',
            fontWeight: 800,
            fontSize: '13.5px',
            letterSpacing: '0.2px',
            boxShadow: copied ? '0 0 16px rgba(16, 185, 129, 0.4)' : '0 0 16px rgba(0, 216, 245, 0.3)',
            transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)'
          }}
        >
          {copied ? <Check size={17} strokeWidth={3} /> : <Copy size={17} />}
          {copied ? 'Copied 19-Point Profile to Clipboard!' : 'Copy All Agent Details'}
        </button>
      </div>

      {/* 2. AGENT TITLE & IDENTITY HERO CARD */}
      <div
        style={{
          backgroundColor: 'var(--bg-card)',
          borderRadius: 'var(--radius-xl)',
          border: '1px solid var(--border-card)',
          padding: '24px 28px',
          marginBottom: '24px',
          boxShadow: 'var(--shadow-card)',
          position: 'relative',
          overflow: 'hidden'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '20px', flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h1 style={{ fontSize: '26px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                {aboutData.name}
              </h1>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '12px',
                  padding: '3px 8px',
                  backgroundColor: 'var(--bg-elevated)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-secondary)'
                }}
              >
                v{aboutData.version}
              </span>
            </div>

            <p style={{ fontSize: '14.5px', color: 'var(--accent-cyan)', fontWeight: 600, marginTop: '6px' }}>
              {aboutData.role}
            </p>

            <p style={{ fontSize: '13.5px', color: 'var(--text-secondary)', marginTop: '8px', maxWidth: '880px', lineHeight: 1.5 }}>
              {aboutData.overview.purpose}
            </p>
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              color: 'var(--text-muted)',
              backgroundColor: 'var(--bg-elevated)',
              padding: '12px 18px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)'
            }}
          >
            <div><strong>Agent ID:</strong> <span style={{ color: 'var(--text-primary)' }}>{aboutData.agentId}</span></div>
            <div><strong>Stage ID:</strong> <span style={{ color: 'var(--text-primary)' }}>{aboutData.stageId}</span></div>
            <div><strong>Owner:</strong> <span style={{ color: 'var(--text-primary)' }}>{aboutData.owner}</span></div>
            <div><strong>Category:</strong> <span style={{ color: 'var(--text-primary)' }}>{aboutData.category}</span></div>
          </div>
        </div>

        {/* TAB BUTTONS */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginTop: '24px',
            borderTop: '1px solid var(--border-subtle)',
            paddingTop: '16px'
          }}
        >
          {[
            { id: 'growth', label: 'Growth & Maturity Dashboard', icon: <TrendingUp size={16} /> },
            { id: 'upgrades', label: `Verified Upgrades (${upgradesData.length || 1})`, icon: <History size={16} /> },
            { id: 'about', label: 'Technical Profile (A–L)', icon: <Layers size={16} /> },
            { id: 'markdown', label: 'LLM Markdown Export Preview', icon: <FileCode2 size={16} /> }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              data-testid={`tab-${tab.id}`}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 18px',
                borderRadius: 'var(--radius-full)',
                border: 'none',
                backgroundColor: activeTab === tab.id ? 'var(--accent-cyan)' : 'var(--bg-elevated)',
                color: activeTab === tab.id ? '#060D1A' : 'var(--text-secondary)',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 3. TAB CONTENT */}
      {/* TAB 1: GROWTH & MATURITY TRACKING DASHBOARD */}
      {activeTab === 'growth' && (
        <AgentGrowthDashboard growthData={growthData} />
      )}

      {/* TAB 2: VERIFIED UPGRADES */}
      {activeTab === 'upgrades' && (
        <AgentUpgradesView upgradesData={upgradesData} />
      )}

      {/* TAB 3: TECHNICAL PROFILE (A-L) REUSING AgentAboutTab */}
      {activeTab === 'about' && (
        <div data-testid="technical-profile-content">
          <AgentAboutTab stageId={aboutData.stageId} agentId={aboutData.agentId} isFullPage={true} />
        </div>
      )}

      {/* TAB 4: LLM MARKDOWN EXPORT PREVIEW */}
      {activeTab === 'markdown' && (
        <AgentMarkdownPreview
          aboutData={aboutData}
          growthData={growthData}
          upgradesData={upgradesData}
          copied={copied}
          handleCopyAllDetails={handleCopyAllDetails}
        />
      )}
    </div>
  );
};

export default AgentIntelligenceDetailView;
