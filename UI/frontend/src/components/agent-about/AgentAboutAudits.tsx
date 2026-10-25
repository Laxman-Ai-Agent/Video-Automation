import React from 'react';
import {
  ShieldCheck,
  XCircle,
  AlertTriangle,
  Wrench,
  Code2,
  Check,
  Copy
} from 'lucide-react';
import { AgentAboutData } from '../../data/agentAboutData';
import { StatusBadge } from './StatusBadge';

export interface AgentAboutAuditsProps {
  data: AgentAboutData;
  activeSection: string;
  isFullPage?: boolean;
  copiedKey: string | null;
  handleCopy: (text: string, key: string) => void;
}

export const AgentAboutAudits: React.FC<AgentAboutAuditsProps> = ({
  data,
  activeSection,
  isFullPage = false,
  copiedKey,
  handleCopy
}) => {
  return (
    <>
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
                  <StatusBadge status={cap.status} />
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
                  <StatusBadge status={gap.status} />
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
    </>
  );
};
