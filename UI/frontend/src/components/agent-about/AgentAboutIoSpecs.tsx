import React from 'react';
import { Database, FileText, Sparkles, Copy, Check } from 'lucide-react';
import { AgentAboutData } from '../../data/agentAboutData';

export interface AgentAboutIoSpecsProps {
  data: AgentAboutData;
  activeSection: string;
  isFullPage?: boolean;
  copiedKey: string | null;
  handleCopy: (text: string, key: string) => void;
}

export const AgentAboutIoSpecs: React.FC<AgentAboutIoSpecsProps> = ({
  data,
  activeSection,
  isFullPage = false,
  copiedKey,
  handleCopy
}) => {
  return (
    <>
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
    </>
  );
};
