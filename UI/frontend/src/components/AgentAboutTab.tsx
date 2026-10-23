import React, { useState, useMemo } from 'react';
import {
  Cpu,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  FileText,
  Layers,
  ArrowRight,
  Code2,
  Terminal,
  Copy,
  Check,
  Search,
  ExternalLink,
  Zap,
  Sparkles,
  HelpCircle,
  Database,
  GitBranch,
  Wrench,
  Compass,
  Film,
  Scissors,
  CheckCheck,
  XCircle,
  Clock
} from 'lucide-react';
import { getAgentAboutData, AgentAboutData, CapabilityStatus } from '../data/agentAboutData';

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

  // Helper for status badge styling
  const renderStatusBadge = (status: CapabilityStatus) => {
    let bg = 'rgba(140, 140, 140, 0.15)';
    let text = '#8C8C8C';
    let border = 'rgba(140, 140, 140, 0.3)';

    if (status === 'VERIFIED WORKING') {
      bg = 'rgba(82, 196, 26, 0.15)';
      text = '#52C41A';
      border = 'rgba(82, 196, 26, 0.35)';
    } else if (status === 'PARTIALLY IMPLEMENTED') {
      bg = 'rgba(250, 173, 20, 0.15)';
      text = '#FAAD14';
      border = 'rgba(250, 173, 20, 0.35)';
    } else if (status === 'NOT IMPLEMENTED') {
      bg = 'rgba(24, 144, 255, 0.15)';
      text = '#1890FF';
      border = 'rgba(24, 144, 255, 0.35)';
    } else if (status === 'NOT SUPPORTED') {
      bg = 'rgba(255, 77, 79, 0.15)';
      text = '#FF4D4F';
      border = 'rgba(255, 77, 79, 0.35)';
    }

    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '2px 8px',
          borderRadius: '4px',
          fontSize: '10.5px',
          fontWeight: 700,
          fontFamily: 'var(--font-mono)',
          backgroundColor: bg,
          color: text,
          border: `1px solid ${border}`,
          letterSpacing: '0.3px',
          textTransform: 'uppercase'
        }}
      >
        {status === 'VERIFIED WORKING' && <CheckCircle2 size={11} />}
        {status === 'PARTIALLY IMPLEMENTED' && <Clock size={11} />}
        {status === 'NOT IMPLEMENTED' && <Layers size={11} />}
        {status === 'NOT SUPPORTED' && <XCircle size={11} />}
        {status}
      </span>
    );
  };

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
      {/* 1. HERO AGENT HEADER CARD */}
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

      {/* SECTION A: OVERVIEW & PURPOSE */}
      {(activeSection === 'all' || activeSection === 'overview') && (
        <section
          data-testid="agent-about-section-overview"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Compass size={18} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              A. Overview, Purpose & System Position
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr', gap: '16px' }}>
            <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.25)', padding: '14px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase' }}>
                Primary Purpose
              </span>
              <p style={{ fontSize: '13px', color: 'var(--text-primary)', marginTop: '6px', lineHeight: 1.5 }}>
                {data.overview.purpose}
              </p>
            </div>

            <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.25)', padding: '14px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-orange)', textTransform: 'uppercase' }}>
                Problem It Solves
              </span>
              <p style={{ fontSize: '13px', color: 'var(--text-primary)', marginTop: '6px', lineHeight: 1.5 }}>
                {data.overview.problemSolved}
              </p>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: isFullPage ? 'repeat(3, 1fr)' : '1fr',
              gap: '12px',
              marginTop: '4px'
            }}
          >
            <div style={{ padding: '12px', backgroundColor: 'rgba(255, 255, 255, 0.03)', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>PIPELINE POSITION</div>
              <div style={{ fontSize: '12.5px', color: 'var(--text-primary)', marginTop: '4px', fontWeight: 600 }}>
                {data.overview.position}
              </div>
            </div>

            <div style={{ padding: '12px', backgroundColor: 'rgba(255, 255, 255, 0.03)', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>UPSTREAM INPUT DEPENDENCY</div>
              <div style={{ fontSize: '12.5px', color: 'var(--accent-cyan)', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
                {data.overview.upstream}
              </div>
            </div>

            <div style={{ padding: '12px', backgroundColor: 'rgba(255, 255, 255, 0.03)', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>DOWNSTREAM CONSUMER STAGE</div>
              <div style={{ fontSize: '12.5px', color: '#52C41A', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
                {data.overview.downstream}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* SECTION B: WHAT IT DOES */}
      {(activeSection === 'all' || activeSection === 'responsibilities') && (
        <section
          data-testid="agent-about-section-responsibilities"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCheck size={18} color="#52C41A" />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              B. What It Does (Implemented Responsibilities)
            </h3>
          </div>

          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
            {data.whatItDoes.summary}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
            {data.whatItDoes.implementedResponsibilities.map((resp, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  padding: '8px 12px',
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                  borderRadius: '4px',
                  border: '1px solid rgba(255, 255, 255, 0.05)'
                }}
              >
                <div style={{ color: '#52C41A', marginTop: '2px', flexShrink: 0 }}>
                  <CheckCircle2 size={14} />
                </div>
                <span style={{ fontSize: '12.5px', color: 'var(--text-primary)', lineHeight: 1.4 }}>
                  {resp}
                </span>
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr', gap: '14px', marginTop: '8px' }}>
            <div style={{ padding: '12px 14px', backgroundColor: 'rgba(82, 196, 26, 0.06)', border: '1px solid rgba(82, 196, 26, 0.2)', borderRadius: '6px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#52C41A', textTransform: 'uppercase' }}>
                Production-Ready Capabilities
              </span>
              <ul style={{ margin: '8px 0 0', paddingLeft: '18px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {data.whatItDoes.productionReadyFeatures.map((f, i) => (
                  <li key={i} style={{ marginBottom: '4px' }}>{f}</li>
                ))}
              </ul>
            </div>

            {data.whatItDoes.experimentalFeatures && data.whatItDoes.experimentalFeatures.length > 0 && (
              <div style={{ padding: '12px 14px', backgroundColor: 'rgba(250, 173, 20, 0.06)', border: '1px solid rgba(250, 173, 20, 0.2)', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', fontWeight: 700, color: '#FAAD14', textTransform: 'uppercase' }}>
                  Experimental / Extended Logic
                </span>
                <ul style={{ margin: '8px 0 0', paddingLeft: '18px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  {data.whatItDoes.experimentalFeatures.map((f, i) => (
                    <li key={i} style={{ marginBottom: '4px' }}>{f}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}

      {/* SECTION C: HOW IT WORKS INTERNALLY */}
      {(activeSection === 'all' || activeSection === 'flow') && (
        <section
          data-testid="agent-about-section-internal-flow"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              C. How It Works Internally (Step-by-Step Flow)
            </h3>
          </div>

          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
            {data.howItWorks.summary}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '6px' }}>
            {data.howItWorks.stepByStepFlow.map((step) => {
              let tagBg = 'rgba(0, 216, 245, 0.12)';
              let tagColor = 'var(--accent-cyan)';
              let tagBorder = 'rgba(0, 216, 245, 0.3)';

              if (step.type === 'llm') {
                tagBg = 'rgba(168, 85, 247, 0.12)';
                tagColor = '#C084FC';
                tagBorder = 'rgba(168, 85, 247, 0.3)';
              } else if (step.type === 'external') {
                tagBg = 'rgba(255, 107, 74, 0.12)';
                tagColor = 'var(--accent-orange)';
                tagBorder = 'rgba(255, 107, 74, 0.3)';
              }

              return (
                <div
                  key={step.step}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '14px',
                    padding: '12px 14px',
                    backgroundColor: 'rgba(0, 0, 0, 0.25)',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle)'
                  }}
                >
                  <div
                    style={{
                      width: '28px',
                      height: '28px',
                      borderRadius: '50%',
                      backgroundColor: 'rgba(0, 216, 245, 0.15)',
                      color: 'var(--accent-cyan)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '12px',
                      fontWeight: 800,
                      flexShrink: 0
                    }}
                  >
                    {step.step}
                  </div>

                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                      <div style={{ fontSize: '13.5px', fontWeight: 700, color: '#FFFFFF' }}>
                        {step.title}
                      </div>
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          fontFamily: 'var(--font-mono)',
                          padding: '1px 6px',
                          borderRadius: '3px',
                          backgroundColor: tagBg,
                          color: tagColor,
                          border: `1px solid ${tagBorder}`,
                          textTransform: 'uppercase'
                        }}
                      >
                        {step.type}
                      </span>
                    </div>
                    <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: 1.45 }}>
                      {step.detail}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr', gap: '12px', marginTop: '6px' }}>
            <div style={{ padding: '10px 14px', backgroundColor: 'rgba(255, 255, 255, 0.03)', borderRadius: '4px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>CONCURRENCY & CACHING:</span>
              <p style={{ fontSize: '12px', color: 'var(--text-primary)', margin: '4px 0 0' }}>
                {data.howItWorks.concurrencyAndCaching}
              </p>
            </div>
            <div style={{ padding: '10px 14px', backgroundColor: 'rgba(255, 255, 255, 0.03)', borderRadius: '4px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>ERROR RETRY LOGIC:</span>
              <p style={{ fontSize: '12px', color: 'var(--text-primary)', margin: '4px 0 0' }}>
                {data.howItWorks.retryLogic}
              </p>
            </div>
          </div>
        </section>
      )}

      {/* SECTION D: INPUTS & DEPENDENCIES */}
      {(activeSection === 'all' || activeSection === 'inputs') && (
        <section
          data-testid="agent-about-section-inputs"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Database size={18} color="var(--accent-orange)" />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              D. Inputs & Dependencies
            </h3>
          </div>

          {data.inputsDependencies.inputs.some((i) => i.required) && (
            <div
              data-testid="required-inputs-note"
              style={{
                padding: '10px 14px', borderRadius: '6px', fontSize: '12.5px', fontWeight: 600,
                color: '#FCA5A5', backgroundColor: 'rgba(255, 77, 79, 0.07)', border: '1px solid rgba(255, 77, 79, 0.35)'
              }}
            >
              Required inputs (highlighted in red): {data.inputsDependencies.inputs.filter((i) => i.required).map((i) => i.name).join(', ')}.
              {' '}All of them must exist (100%) before this stage can run.
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {data.inputsDependencies.inputs.map((inp, idx) => (
              <div
                key={idx}
                title={inp.required ? 'Required input' : undefined}
                data-required={inp.required ? 'true' : 'false'}
                style={{
                  backgroundColor: inp.required ? 'rgba(255, 77, 79, 0.07)' : 'rgba(0, 0, 0, 0.25)',
                  border: inp.required ? '1px solid rgba(255, 77, 79, 0.45)' : '1px solid var(--border-subtle)',
                  borderLeft: inp.required ? '3px solid #FF4D4F' : '3px solid transparent',
                  borderRadius: '6px',
                  padding: '12px 14px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '13.5px', fontWeight: 700, color: '#FFFFFF' }}>{inp.name}</span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      [{inp.format}]
                    </span>
                  </div>

                  <button
                    onClick={() => handleCopy(inp.pathExample, `input-${idx}`)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      background: 'none',
                      border: 'none',
                      color: copiedKey === `input-${idx}` ? 'var(--status-completed)' : 'var(--text-muted)',
                      fontSize: '11px',
                      fontFamily: 'var(--font-mono)',
                      cursor: 'pointer'
                    }}
                  >
                    {copiedKey === `input-${idx}` ? <Check size={12} /> : <Copy size={12} />}
                    <span>{inp.pathExample}</span>
                  </button>
                </div>

                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '6px' }}>
                  {inp.description}
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr', gap: '12px', marginTop: '4px' }}>
            <div style={{ padding: '10px 14px', backgroundColor: 'rgba(255, 255, 255, 0.03)', borderRadius: '4px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>EXTERNAL TOOLS USED:</span>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '6px' }}>
                {data.inputsDependencies.externalTools.map((tool, i) => (
                  <span key={i} style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', backgroundColor: 'rgba(255, 255, 255, 0.08)', padding: '2px 6px', borderRadius: '3px' }}>
                    {tool}
                  </span>
                ))}
              </div>
            </div>

            <div style={{ padding: '10px 14px', backgroundColor: 'rgba(255, 255, 255, 0.03)', borderRadius: '4px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>SYSTEM DEPENDENCIES:</span>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '6px' }}>
                {data.inputsDependencies.systemDependencies.map((dep, i) => (
                  <span key={i} style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', backgroundColor: 'rgba(255, 255, 255, 0.08)', padding: '2px 6px', borderRadius: '3px' }}>
                    {dep}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* SECTION E: OUTPUTS & SIDE EFFECTS */}
      {(activeSection === 'all' || activeSection === 'outputs') && (
        <section
          data-testid="agent-about-section-outputs"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={18} color="#52C41A" />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              E. Outputs & Side Effects
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {data.outputsSideEffects.outputs.map((out, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: 'rgba(0, 0, 0, 0.25)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '6px',
                  padding: '12px 14px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--accent-cyan)' }}>{out.name}</span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      [{out.format}]
                    </span>
                  </div>

                  <button
                    onClick={() => handleCopy(out.pathExample, `output-${idx}`)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      background: 'none',
                      border: 'none',
                      color: copiedKey === `output-${idx}` ? 'var(--status-completed)' : 'var(--text-muted)',
                      fontSize: '11px',
                      fontFamily: 'var(--font-mono)',
                      cursor: 'pointer'
                    }}
                  >
                    {copiedKey === `output-${idx}` ? <Check size={12} /> : <Copy size={12} />}
                    <span>{out.pathExample}</span>
                  </button>
                </div>

                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '6px' }}>
                  {out.description}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontWeight: 600 }}>DOWNSTREAM CONSUMERS:</span>
                  {out.consumers.map((c, i) => (
                    <span key={i} style={{ fontSize: '10.5px', fontFamily: 'var(--font-mono)', backgroundColor: 'rgba(0, 216, 245, 0.1)', color: 'var(--accent-cyan)', padding: '1px 5px', borderRadius: '3px' }}>
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr', gap: '12px', marginTop: '4px' }}>
            <div style={{ padding: '10px 14px', backgroundColor: 'rgba(255, 255, 255, 0.03)', borderRadius: '4px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>SYSTEM SIDE EFFECTS:</span>
              <ul style={{ margin: '6px 0 0', paddingLeft: '16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {data.outputsSideEffects.sideEffects.map((se, i) => (
                  <li key={i}>{se}</li>
                ))}
              </ul>
            </div>

            <div style={{ padding: '10px 14px', backgroundColor: 'rgba(255, 77, 79, 0.05)', borderRadius: '4px', border: '1px solid rgba(255, 77, 79, 0.15)' }}>
              <span style={{ fontSize: '11px', color: '#FF4D4F', fontWeight: 600 }}>KNOWN ERROR STATES:</span>
              <ul style={{ margin: '6px 0 0', paddingLeft: '16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {data.outputsSideEffects.errorStates.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      )}

      {/* SECTION F: LLM USAGE & DECISION-MAKING */}
      {(activeSection === 'all' || activeSection === 'llm') && (
        <section
          data-testid="agent-about-section-llm"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={18} color="#C084FC" />
              <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
                F. LLM Usage, Decision-Making & Deterministic Guardrails
              </h3>
            </div>

            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
                padding: '2px 8px',
                borderRadius: '4px',
                backgroundColor: data.llmDecisionMaking.usesLlm ? 'rgba(168, 85, 247, 0.15)' : 'rgba(0, 216, 245, 0.15)',
                color: data.llmDecisionMaking.usesLlm ? '#C084FC' : 'var(--accent-cyan)',
                border: `1px solid ${data.llmDecisionMaking.usesLlm ? 'rgba(168, 85, 247, 0.3)' : 'rgba(0, 216, 245, 0.3)'}`
              }}
            >
              {data.llmDecisionMaking.usesLlm ? 'USES LLM DECISION-MAKING' : 'PURELY DETERMINISTIC (NO LLM)'}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr', gap: '14px' }}>
            <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.25)', padding: '12px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>MODEL / PROMPT PROFILE</div>
              <div style={{ fontSize: '13px', color: '#FFFFFF', fontWeight: 700, marginTop: '4px' }}>
                {data.llmDecisionMaking.modelOrProfile}
              </div>
              {data.llmDecisionMaking.temperature && (
                <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                  Temperature: {data.llmDecisionMaking.temperature}
                </div>
              )}
            </div>

            <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.25)', padding: '12px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>OFFLINE / ERROR FALLBACK</div>
              <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                {data.llmDecisionMaking.fallbackStrategy}
              </div>
            </div>
          </div>

          <div style={{ padding: '12px 14px', backgroundColor: 'rgba(255, 255, 255, 0.02)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase' }}>
              Prompting Strategy
            </span>
            <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: 1.5 }}>
              {data.llmDecisionMaking.promptStrategy}
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr', gap: '12px' }}>
            <div style={{ padding: '12px 14px', backgroundColor: 'rgba(82, 196, 26, 0.05)', borderRadius: '6px', border: '1px solid rgba(82, 196, 26, 0.2)' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#52C41A', textTransform: 'uppercase' }}>
                Deterministic Guardrails Around LLM
              </span>
              <ul style={{ margin: '8px 0 0', paddingLeft: '16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {data.llmDecisionMaking.deterministicGuardrails.map((g, i) => (
                  <li key={i} style={{ marginBottom: '3px' }}>{g}</li>
                ))}
              </ul>
            </div>

            <div style={{ padding: '12px 14px', backgroundColor: 'rgba(0, 216, 245, 0.05)', borderRadius: '6px', border: '1px solid rgba(0, 216, 245, 0.2)' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase' }}>
                Purely Deterministic Steps
              </span>
              <ul style={{ margin: '8px 0 0', paddingLeft: '16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {data.llmDecisionMaking.purelyDeterministicParts.map((p, i) => (
                  <li key={i} style={{ marginBottom: '3px' }}>{p}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      )}

      {/* SECTION G: VERIFIED CAPABILITIES */}
      {(activeSection === 'all' || activeSection === 'capabilities') && (
        <section
          data-testid="agent-about-section-capabilities"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={18} color="#52C41A" />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              G. Current Capabilities (Verified in Codebase)
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {data.currentCapabilities.map((cap, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: 'rgba(0, 0, 0, 0.25)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '6px',
                  padding: '12px 14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '13.5px', fontWeight: 700, color: '#FFFFFF' }}>{cap.name}</span>
                  {renderStatusBadge(cap.status)}
                </div>

                <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                  {cap.description}
                </div>

                <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                  Evidence: {cap.evidence}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* SECTION H: WHAT IT DOES NOT DO */}
      {(activeSection === 'all' || activeSection === 'boundaries') && (
        <section
          data-testid="agent-about-section-boundaries"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <XCircle size={18} color="#FF4D4F" />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              H. What It Does NOT Do (Explicit Non-Responsibilities)
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {data.whatItDoesNotDo.map((item, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  padding: '8px 12px',
                  backgroundColor: 'rgba(255, 77, 79, 0.04)',
                  borderRadius: '4px',
                  border: '1px solid rgba(255, 77, 79, 0.12)'
                }}
              >
                <span style={{ color: '#FF4D4F', fontWeight: 800, fontSize: '12px' }}>✕</span>
                <span style={{ fontSize: '12.5px', color: 'var(--text-primary)' }}>{item}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* SECTION I: MISSING CAPABILITIES & GAPS */}
      {(activeSection === 'all' || activeSection === 'gaps') && (
        <section
          data-testid="agent-about-section-gaps"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={18} color="var(--accent-orange)" />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              I. Missing Capabilities, Gaps & Architectural Limits
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {data.missingCapabilities.map((gap, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: 'rgba(0, 0, 0, 0.25)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '6px',
                  padding: '12px 14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '13.5px', fontWeight: 700, color: '#FFFFFF' }}>{gap.title}</span>
                  {renderStatusBadge(gap.status)}
                </div>

                <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                  <strong>Gap:</strong> {gap.gapDescription}
                </div>

                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  <strong>Impact:</strong> {gap.impact}
                </div>

                {gap.plannedResolution && (
                  <div style={{ fontSize: '11.5px', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                    Planned Resolution: {gap.plannedResolution}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* SECTION J: VALIDATION & TESTING */}
      {(activeSection === 'all' || activeSection === 'testing') && (
        <section
          data-testid="agent-about-section-testing"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={18} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              J. Validation & Testing Evidence
            </h3>
          </div>

          <div style={{ padding: '12px 14px', backgroundColor: 'rgba(0, 0, 0, 0.25)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase' }}>
              Automated Validation Logic
            </span>
            <ul style={{ margin: '6px 0 0', paddingLeft: '16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              {data.validationTesting.validationLogic.map((v, i) => (
                <li key={i} style={{ marginBottom: '3px' }}>{v}</li>
              ))}
            </ul>
          </div>

          <div style={{ padding: '12px 14px', backgroundColor: 'rgba(0, 0, 0, 0.25)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-orange)', textTransform: 'uppercase' }}>
              Failure Modes & Recovery Procedures
            </span>
            <ul style={{ margin: '6px 0 0', paddingLeft: '16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              {data.validationTesting.failureModesAndRecovery.map((f, i) => (
                <li key={i} style={{ marginBottom: '3px' }}>{f}</li>
              ))}
            </ul>
          </div>

          <div>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Automated Pytest & Playwright Test Suites
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '6px' }}>
              {data.validationTesting.testFiles.map((tf, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 10px',
                    backgroundColor: 'rgba(255, 255, 255, 0.03)',
                    borderRadius: '4px',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '11.5px',
                    color: 'var(--text-primary)'
                  }}
                >
                  <span>{tf}</span>
                  <button
                    onClick={() => handleCopy(tf, `test-${i}`)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: copiedKey === `test-${i}` ? 'var(--status-completed)' : 'var(--text-muted)',
                      cursor: 'pointer'
                    }}
                    title="Copy test file path"
                  >
                    {copiedKey === `test-${i}` ? <Check size={12} /> : <Copy size={12} />}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* SECTION K: IMPROVEMENT OPPORTUNITIES */}
      {(activeSection === 'all' || activeSection === 'improvements') && (
        <section
          data-testid="agent-about-section-improvements"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Wrench size={18} color="var(--accent-orange)" />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              K. Concrete Improvement Opportunities (Prioritized Backlog)
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {data.improvementOpportunities.map((imp, idx) => {
              let pColor = 'var(--accent-cyan)';
              if (imp.priority === 'HIGH') pColor = 'var(--accent-orange)';
              if (imp.priority === 'MEDIUM') pColor = '#FAAD14';

              return (
                <div
                  key={idx}
                  style={{
                    backgroundColor: 'rgba(0, 0, 0, 0.25)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '6px',
                    padding: '12px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '13.5px', fontWeight: 700, color: '#FFFFFF' }}>{imp.title}</span>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 700,
                        fontFamily: 'var(--font-mono)',
                        padding: '1px 6px',
                        borderRadius: '3px',
                        backgroundColor: 'rgba(255, 255, 255, 0.08)',
                        color: pColor,
                        border: `1px solid ${pColor}44`
                      }}
                    >
                      {imp.priority} PRIORITY
                    </span>
                  </div>

                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    <strong>Current Limitation:</strong> {imp.currentLimitation}
                  </div>

                  <div style={{ fontSize: '12px', color: 'var(--text-primary)' }}>
                    <strong>Desired Behavior:</strong> {imp.desiredBehavior}
                  </div>

                  <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    Implementation Gap: {imp.implementationGap} • Dependencies: {imp.dependencies}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* SECTION L: SOURCE CODE EVIDENCE & REFERENCES */}
      {(activeSection === 'all' || activeSection === 'source') && (
        <section
          data-testid="agent-about-section-source-code"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-card)',
            borderRadius: '8px',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Code2 size={18} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
              L. Source Code Evidence & References
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr', gap: '14px' }}>
            <div>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Primary Implementation Files
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '6px' }}>
                {data.sourceEvidence.primaryFiles.map((pf, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '6px 10px',
                      backgroundColor: 'rgba(0, 0, 0, 0.25)',
                      borderRadius: '4px',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '11px',
                      color: 'var(--accent-cyan)',
                      border: '1px solid var(--border-subtle)'
                    }}
                  >
                    <span>{pf}</span>
                    <button
                      onClick={() => handleCopy(pf, `primary-${i}`)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: copiedKey === `primary-${i}` ? 'var(--status-completed)' : 'var(--text-muted)',
                        cursor: 'pointer'
                      }}
                      title="Copy path"
                    >
                      {copiedKey === `primary-${i}` ? <Check size={12} /> : <Copy size={12} />}
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Key Classes & Functions
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '6px' }}>
                {data.sourceEvidence.classesAndFunctions.map((cf, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '6px 10px',
                      backgroundColor: 'rgba(0, 0, 0, 0.25)',
                      borderRadius: '4px',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '11px',
                      color: '#FFFFFF',
                      border: '1px solid var(--border-subtle)'
                    }}
                  >
                    <span>{cf}</span>
                    <button
                      onClick={() => handleCopy(cf, `cf-${i}`)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: copiedKey === `cf-${i}` ? 'var(--status-completed)' : 'var(--text-muted)',
                        cursor: 'pointer'
                      }}
                      title="Copy name"
                    >
                      {copiedKey === `cf-${i}` ? <Check size={12} /> : <Copy size={12} />}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};
