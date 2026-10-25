import React from 'react';
import {
  Compass,
  CheckCheck,
  CheckCircle2,
  Layers
} from 'lucide-react';
import { AgentAboutData } from '../../data/agentAboutData';
import { AgentAboutIoSpecs } from './AgentAboutIoSpecs';

export interface AgentAboutCoreSpecsProps {
  data: AgentAboutData;
  activeSection: string;
  isFullPage?: boolean;
  copiedKey: string | null;
  handleCopy: (text: string, key: string) => void;
}

export const AgentAboutCoreSpecs: React.FC<AgentAboutCoreSpecsProps> = ({
  data,
  activeSection,
  isFullPage = false,
  copiedKey,
  handleCopy
}) => {
  return (
    <>
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
                <span style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.45 }}>
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
          data-testid="agent-about-section-flow"
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

      {/* SECTIONS D, E, F: INPUTS, OUTPUTS, LLM DECISION MAKING */}
      <AgentAboutIoSpecs
        data={data}
        activeSection={activeSection}
        isFullPage={isFullPage}
        copiedKey={copiedKey}
        handleCopy={handleCopy}
      />
    </>
  );
};
