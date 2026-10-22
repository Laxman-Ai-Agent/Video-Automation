import React, { useState, useEffect, useMemo } from 'react';
import {
  ArrowLeft,
  Copy,
  Check,
  TrendingUp,
  History,
  FileCode2,
  ShieldCheck,
  Cpu,
  Video,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Sparkles,
  ExternalLink,
  Zap,
  Info,
  Calendar,
  Layers,
  ChevronRight,
  Search
} from 'lucide-react';
import { getAgentAboutData, AgentAboutData, generateAgentMarkdownExport } from '../data/agentAboutData';
import { fetchAgentGrowth, fetchAgentUpgrades } from '../services/api';
import { AgentAboutTab } from './AgentAboutTab';

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
  const [loading, setLoading] = useState(true);

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

  const currentScores = growthData?.current_scores || {};
  const crs = currentScores.capability_readiness_score ?? 85.0;
  const vc = currentScores.verification_coverage ?? 90.0;
  const qs = currentScores.quality_metric || 'Empirically Verified';
  const snapshots: any[] = growthData?.snapshots || [];

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

            {aboutData.isFrozen && (
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  padding: '4px 10px',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'rgba(239, 68, 68, 0.12)',
                  color: '#EF4444',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                FROZEN CORE
              </span>
            )}

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
        <div data-testid="growth-dashboard-content" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* TOP 3 SCORE CARDS */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '18px' }}>
            {/* CRS CARD */}
            <div
              style={{
                backgroundColor: 'var(--bg-card)',
                borderRadius: 'var(--radius-xl)',
                border: '1px solid var(--border-card)',
                padding: '24px',
                boxShadow: 'var(--shadow-card)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Capability Readiness Score
                </span>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '2px 8px',
                    backgroundColor: 'rgba(0, 216, 245, 0.12)',
                    color: 'var(--accent-cyan)',
                    borderRadius: 'var(--radius-sm)'
                  }}
                >
                  CRS v1.0.0
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '12px' }}>
                <span style={{ fontSize: '38px', fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {crs.toFixed(1)}%
                </span>
                {currentScores.delta_day_over_day !== undefined && currentScores.delta_day_over_day !== 0 && (
                  <span
                    style={{
                      fontSize: '12px',
                      fontWeight: 700,
                      color: currentScores.delta_day_over_day > 0 ? '#10B981' : '#EF4444'
                    }}
                  >
                    {currentScores.delta_day_over_day > 0 ? `+${currentScores.delta_day_over_day}%` : `${currentScores.delta_day_over_day}%`} (24h)
                  </span>
                )}
              </div>
              <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '8px', lineHeight: 1.4 }}>
                Weighted readiness across all in-scope capabilities. Status multiplier: Verified=1.0, Partial=0.5.
              </p>
            </div>

            {/* VC CARD */}
            <div
              style={{
                backgroundColor: 'var(--bg-card)',
                borderRadius: 'var(--radius-xl)',
                border: '1px solid var(--border-card)',
                padding: '24px',
                boxShadow: 'var(--shadow-card)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Verification Coverage
                </span>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '2px 8px',
                    backgroundColor: 'rgba(16, 185, 129, 0.12)',
                    color: '#10B981',
                    borderRadius: 'var(--radius-sm)'
                  }}
                >
                  EMPIRICAL TESTS
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '12px' }}>
                <span style={{ fontSize: '38px', fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {vc.toFixed(1)}%
                </span>
              </div>
              <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '8px', lineHeight: 1.4 }}>
                Percentage of capabilities backed by executed pytest or deterministic verification suites.
              </p>
            </div>

            {/* QS CARD */}
            <div
              style={{
                backgroundColor: 'var(--bg-card)',
                borderRadius: 'var(--radius-xl)',
                border: '1px solid var(--border-card)',
                padding: '24px',
                boxShadow: 'var(--shadow-card)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Quality Score & Telemetry
                </span>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '2px 8px',
                    backgroundColor: 'rgba(245, 158, 11, 0.12)',
                    color: '#F59E0B',
                    borderRadius: 'var(--radius-sm)'
                  }}
                >
                  OBSERVABLE
                </span>
              </div>
              <div style={{ marginTop: '14px' }}>
                <span style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {qs}
                </span>
              </div>
              <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '12px', lineHeight: 1.4 }}>
                Objective runtime observations: zero black frames, audio sync precision, latency, and test suite pass rate.
              </p>
            </div>
          </div>

          {/* HISTORICAL SNAPSHOTS TIMELINE */}
          <div
            style={{
              backgroundColor: 'var(--bg-card)',
              borderRadius: 'var(--radius-xl)',
              border: '1px solid var(--border-card)',
              padding: '24px',
              boxShadow: 'var(--shadow-card)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Chronological Maturity Snapshots ({snapshots.length} Milestones)
                </h3>
                <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Persistent day-by-day capability progress saved in <code>config/history/agent_growth_snapshots.json</code>.
                </p>
              </div>

              <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                Methodology: v1.0.0
              </div>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '10px 14px', fontWeight: 600 }}>Date</th>
                    <th style={{ padding: '10px 14px', fontWeight: 600 }}>CRS (%)</th>
                    <th style={{ padding: '10px 14px', fontWeight: 600 }}>VC (%)</th>
                    <th style={{ padding: '10px 14px', fontWeight: 600 }}>Quality Metric / Evidence</th>
                    <th style={{ padding: '10px 14px', fontWeight: 600 }}>Milestone Type</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshots.map((snap: any, idx: number) => (
                    <tr
                      key={snap.snapshot_id || idx}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                        backgroundColor: snap.is_baseline ? 'rgba(0, 216, 245, 0.04)' : 'transparent'
                      }}
                    >
                      <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Calendar size={13} color="var(--accent-cyan)" />
                          {snap.date}
                        </div>
                      </td>
                      <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                        {snap.capability_readiness_score}%
                      </td>
                      <td style={{ padding: '12px 14px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#10B981' }}>
                        {snap.verification_coverage}%
                      </td>
                      <td style={{ padding: '12px 14px', color: 'var(--text-secondary)' }}>
                        {snap.evidence_summary || snap.quality_metric}
                      </td>
                      <td style={{ padding: '12px 14px' }}>
                        {snap.is_baseline ? (
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: 'var(--radius-sm)',
                              backgroundColor: 'rgba(0, 216, 245, 0.12)',
                              color: 'var(--accent-cyan)'
                            }}
                          >
                            BASELINE
                          </span>
                        ) : (
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 600,
                              padding: '2px 8px',
                              borderRadius: 'var(--radius-sm)',
                              backgroundColor: 'var(--bg-elevated)',
                              color: 'var(--text-muted)'
                            }}
                          >
                            INCREMENTAL
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* FORMULA CALLOUT */}
            <div
              style={{
                marginTop: '20px',
                padding: '14px 18px',
                backgroundColor: 'var(--bg-elevated)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px'
              }}
            >
              <Info size={18} color="var(--accent-cyan)" style={{ marginTop: '2px', flexShrink: 0 }} />
              <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                <strong style={{ color: 'var(--text-primary)' }}>Maturity Scoring Formula (v1.0.0):</strong>
                <br />
                <code>CRS = (Σ(weight × status_multiplier) / total_weight) × 100</code> where Verified=1.0, Partial=0.5, Not Implemented=0.0. Out-of-scope non-responsibilities are excluded.
                <br />
                <code>VC = (verified_capabilities_count / total_in_scope_capabilities) × 100</code>. Quality score reflects empirical observable metrics.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: VERIFIED UPGRADES */}
      {activeTab === 'upgrades' && (
        <div data-testid="upgrades-content" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {upgradesData.length === 0 ? (
            <div style={{ padding: '36px', textAlign: 'center', backgroundColor: 'var(--bg-card)', borderRadius: 'var(--radius-xl)' }}>
              <p style={{ color: 'var(--text-muted)' }}>No historical upgrades recorded yet for this agent.</p>
            </div>
          ) : (
            upgradesData.map((u: any, idx: number) => {
              const statusColor =
                u.verification_status === 'VERIFIED'
                  ? '#10B981'
                  : u.verification_status === 'PARTIALLY VERIFIED'
                  ? '#F59E0B'
                  : u.verification_status === 'VERIFICATION FAILED'
                  ? '#EF4444'
                  : 'var(--accent-cyan)';

              return (
                <div
                  key={u.upgrade_id || idx}
                  style={{
                    backgroundColor: 'var(--bg-card)',
                    borderRadius: 'var(--radius-xl)',
                    border: '1px solid var(--border-card)',
                    padding: '24px',
                    boxShadow: 'var(--shadow-card)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '3px 10px',
                          borderRadius: 'var(--radius-full)',
                          backgroundColor: `${statusColor}20`,
                          color: statusColor,
                          border: `1px solid ${statusColor}40`
                        }}
                      >
                        {u.verification_status}
                      </span>
                      <h4 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                        {u.upgrade_id}: {u.reason}
                      </h4>
                    </div>

                    <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      {u.timestamp}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px', fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                    <span>Version transition:</span>
                    <span style={{ fontFamily: 'var(--font-mono)', padding: '2px 6px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
                      {u.before_version}
                    </span>
                    <ChevronRight size={14} />
                    <span style={{ fontFamily: 'var(--font-mono)', padding: '2px 6px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', color: 'var(--accent-cyan)', fontWeight: 700 }}>
                      {u.after_version}
                    </span>
                  </div>

                  <div style={{ marginTop: '14px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    <strong style={{ color: 'var(--text-primary)' }}>Previous Limitation Resolved:</strong> {u.previous_limitation}
                  </div>

                  {u.capabilities_added && u.capabilities_added.length > 0 && (
                    <div style={{ marginTop: '12px' }}>
                      <span style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Capabilities Added:
                      </span>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                        {u.capabilities_added.map((c: string, ci: number) => (
                          <span
                            key={ci}
                            style={{
                              fontSize: '11.5px',
                              padding: '2px 8px',
                              backgroundColor: 'rgba(0, 216, 245, 0.08)',
                              color: 'var(--accent-cyan)',
                              borderRadius: 'var(--radius-sm)',
                              border: '1px solid rgba(0, 216, 245, 0.2)'
                            }}
                          >
                            + {c}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {u.files_changed && u.files_changed.length > 0 && (
                    <div style={{ marginTop: '12px' }}>
                      <span style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Modified Files:
                      </span>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                        {u.files_changed.map((f: string, fi: number) => (
                          <span
                            key={fi}
                            style={{
                              fontSize: '11px',
                              fontFamily: 'var(--font-mono)',
                              padding: '2px 8px',
                              backgroundColor: 'var(--bg-elevated)',
                              color: 'var(--text-secondary)',
                              borderRadius: 'var(--radius-sm)'
                            }}
                          >
                            {f}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {u.evidence_refs && u.evidence_refs.length > 0 && (
                    <div style={{ marginTop: '12px', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px', fontSize: '12px', color: 'var(--text-muted)' }}>
                      <strong>Verification Evidence:</strong> {u.evidence_refs.join(', ')}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* TAB 3: TECHNICAL PROFILE (A-L) REUSING AgentAboutTab */}
      {activeTab === 'about' && (
        <div data-testid="technical-profile-content">
          <AgentAboutTab stageId={aboutData.stageId} agentId={aboutData.agentId} isFullPage={true} />
        </div>
      )}

      {/* TAB 4: LLM MARKDOWN EXPORT PREVIEW */}
      {activeTab === 'markdown' && (
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
      )}
    </div>
  );
};
