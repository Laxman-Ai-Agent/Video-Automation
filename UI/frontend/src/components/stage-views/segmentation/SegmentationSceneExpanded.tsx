import React from 'react';
import { Mic, Sparkles, RefreshCw, Play, Scissors } from 'lucide-react';

export interface SegmentationSceneExpandedProps {
  scene: any;
  sceneNum: string;
  duration: string | null;
  isFullPage?: boolean;
  llmReviewLoading: boolean;
  handleRunLlmReview: () => void;
}

export const SegmentationSceneExpanded: React.FC<SegmentationSceneExpandedProps> = ({
  scene: s,
  sceneNum,
  duration,
  isFullPage = false,
  llmReviewLoading,
  handleRunLlmReview
}) => {
  return (
    <div style={{ padding: '16px 20px', backgroundColor: 'var(--bg-card)', display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* Dual Comparative Transcripts: Whisper Original ASR vs LLM-Processed Script */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Scene Transcripts: Whisper Original vs LLM-Processed Output
          </span>
          {s.llm_transcript && (
            <span style={{
              fontSize: '10.5px',
              color: '#A7F3D0',
              backgroundColor: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              padding: '1px 8px',
              borderRadius: '12px',
              fontWeight: 600
            }}>
              Telugu Script Preserved • English Technical Loanwords Standardized
            </span>
          )}
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr',
          gap: '14px'
        }}>
          {/* Panel 1: Whisper Original Output (Raw ASR) */}
          <div 
            data-testid={`scene-${sceneNum}-whisper-transcript`}
            style={{
              backgroundColor: 'var(--bg-elevated)',
              padding: '14px 16px',
              borderRadius: '8px',
              border: '1px solid rgba(0, 216, 245, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Mic size={14} color="var(--accent-cyan)" />
                <span style={{ fontSize: '11px', fontWeight: 800, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Whisper Original Output (ASR)
                </span>
              </div>
              <span style={{
                fontSize: '10px',
                fontWeight: 700,
                backgroundColor: 'rgba(0, 216, 245, 0.12)',
                color: 'var(--accent-cyan)',
                padding: '2px 8px',
                borderRadius: '12px',
                fontFamily: 'var(--font-mono)'
              }}>
                faster-whisper
              </span>
            </div>
            <div style={{
              fontSize: '14px',
              color: 'var(--text-primary)',
              lineHeight: 1.6,
              minHeight: '44px',
              fontFamily: 'system-ui, -apple-system, sans-serif'
            }}>
              {s.whisper_transcript || (s.isFallback ? 'Whisper original transcript preserved separately' : 'Whisper original transcript preserved separately')}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '6px', fontStyle: 'italic' }}>
              Raw speech-to-text transcript before LLM vocabulary & loanword processing
            </div>
          </div>

          {/* Panel 2: LLM-Processed Output (Telugu + Standard English Words) */}
          <div 
            data-testid={`scene-${sceneNum}-llm-transcript`}
            style={{
              backgroundColor: 'var(--bg-elevated)',
              padding: '14px 16px',
              borderRadius: '8px',
              border: (s.llm_transcript || s.transcript) ? '1px solid rgba(168, 85, 247, 0.35)' : '1px dashed rgba(255, 255, 255, 0.15)',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Sparkles size={14} color={(s.llm_transcript || s.transcript) ? '#C084FC' : 'var(--text-muted)'} />
                <span style={{
                  fontSize: '11px',
                  fontWeight: 800,
                  color: (s.llm_transcript || s.transcript) ? '#C084FC' : 'var(--text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em'
                }}>
                  LLM-Processed Output (Corrected)
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {(s.llm_transcript || s.transcript) ? (
                  <span style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    backgroundColor: 'rgba(168, 85, 247, 0.16)',
                    color: '#D8B4FE',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    fontFamily: 'var(--font-mono)'
                  }}>
                    Claude LLM Verified
                  </span>
                ) : (
                  <span style={{
                    fontSize: '10px',
                    fontWeight: 600,
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    color: '#F87171',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    border: '1px solid rgba(239, 68, 68, 0.3)'
                  }}>
                    Not Run Yet
                  </span>
                )}

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRunLlmReview();
                  }}
                  disabled={llmReviewLoading}
                  data-testid={`scene-${sceneNum}-run-llm-btn`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '5px',
                    padding: '3px 10px',
                    backgroundColor: (s.llm_transcript || s.transcript) ? 'rgba(168, 85, 247, 0.2)' : '#7C3AED',
                    border: (s.llm_transcript || s.transcript) ? '1px solid rgba(168, 85, 247, 0.4)' : '1px solid #A78BFA',
                    borderRadius: '4px',
                    color: (s.llm_transcript || s.transcript) ? '#7C3AED' : '#FFFFFF',
                    fontSize: '11px',
                    fontWeight: 600,
                    cursor: llmReviewLoading ? 'not-allowed' : 'pointer',
                    opacity: llmReviewLoading ? 0.7 : 1,
                    transition: 'all 0.15s ease'
                  }}
                >
                  {llmReviewLoading ? (
                    <RefreshCw size={11} className="animate-spin" />
                  ) : (
                    <Play size={10} fill="currentColor" />
                  )}
                  <span>
                    {llmReviewLoading ? 'Running...' : ((s.llm_transcript || s.transcript) ? 'Re-run LLM Review' : 'Run LLM Review')}
                  </span>
                </button>
              </div>
            </div>

            <div style={{
              fontSize: '14px',
              color: (s.llm_transcript || s.transcript) ? 'var(--text-primary)' : 'var(--text-muted)',
              lineHeight: 1.6,
              minHeight: '44px',
              fontFamily: 'system-ui, -apple-system, sans-serif'
            }}>
              {(s.llm_transcript || s.transcript) ? (
                (s.llm_transcript || s.transcript)
              ) : (
                <span style={{ fontStyle: 'italic', fontSize: '13px' }}>
                  LLM review not yet run for this project. Narration uses original Whisper transcript.
                </span>
              )}
            </div>
            <div style={{
              fontSize: '11px',
              color: s.llm_transcript ? '#6EE7B7' : '#FCA5A5',
              borderTop: '1px solid rgba(255, 255, 255, 0.05)',
              paddingTop: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '6px'
            }}>
              <span>
                {s.llm_transcript
                  ? '✓ Authoritative Final Narration for Visual Planning • Loanwords Standardized'
                  : '⚠️ LLM verification pending — next step is blocked until run'}
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: '10.5px', fontStyle: 'italic' }}>
                {s.llm_transcript ? 'Telugu script preserved' : 'Click Run LLM Review to verify'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Semantic Beat & Scene Objective */}
      <div style={{ display: 'grid', gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr', gap: '12px' }}>
        {s.semantic_beat && (
          <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '12px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase' }}>
              Semantic Beat (Story Point)
            </span>
            <p style={{ fontSize: '13px', color: 'var(--text-primary)', margin: '4px 0 0 0', lineHeight: 1.4 }}>
              {s.semantic_beat}
            </p>
          </div>
        )}
        {s.scene_objective && (
          <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '12px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-blue)', textTransform: 'uppercase' }}>
              Scene Objective
            </span>
            <p style={{ fontSize: '13px', color: 'var(--text-primary)', margin: '4px 0 0 0', lineHeight: 1.4 }}>
              {s.scene_objective}
            </p>
          </div>
        )}
      </div>

      {/* Cut Boundary Transition Details */}
      {s.boundary_after && (
        <div style={{ backgroundColor: 'var(--bg-elevated)', padding: '12px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <Scissors size={13} color="var(--accent-cyan)" />
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Cut Boundary Transition
            </span>
            {s.boundary_after.type && (
              <span style={{
                fontSize: '10px',
                fontFamily: 'var(--font-mono)',
                backgroundColor: 'rgba(0, 216, 245, 0.12)',
                color: 'var(--accent-cyan)',
                padding: '1px 6px',
                borderRadius: '3px',
                fontWeight: 700
              }}>
                {s.boundary_after.type}
              </span>
            )}
          </div>
          <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
            {s.boundary_after.reason || 'Semantic cut point transition.'}
          </div>
          {s.boundary_after.evidence && s.boundary_after.evidence.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>Evidence:</span>
              {s.boundary_after.evidence.map((ev: string, evIdx: number) => (
                <span key={evIdx} style={{
                  fontSize: '10.5px',
                  backgroundColor: 'rgba(255, 255, 255, 0.06)',
                  color: 'var(--text-secondary)',
                  padding: '1px 6px',
                  borderRadius: '3px',
                  fontFamily: 'var(--font-mono)'
                }}>
                  {ev}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Timing & Metric Details */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        fontSize: '11.5px',
        color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)',
        flexWrap: 'wrap',
        paddingTop: '4px'
      }}>
        <span>Start: <strong style={{ color: 'var(--text-primary)' }}>{s.start_time !== undefined ? Number(s.start_time).toFixed(2) : '0.00'}s</strong></span>
        <span>End: <strong style={{ color: 'var(--text-primary)' }}>{s.end_time !== undefined ? Number(s.end_time).toFixed(2) : '0.00'}s</strong></span>
        <span>Duration: <strong style={{ color: 'var(--accent-cyan)' }}>{duration}s</strong></span>
        {s.pause_after_seconds !== undefined && (
          <span>Pause After: <strong style={{ color: 'var(--accent-blue)' }}>{s.pause_after_seconds}s</strong></span>
        )}
        {s.source_word_ids && (
          <span>Words: <strong style={{ color: 'var(--text-primary)' }}>{s.source_word_ids.length}</strong></span>
        )}
        {s.timing_source && (
          <span>Source: <strong>{s.timing_source}</strong></span>
        )}
      </div>
    </div>
  );
};
