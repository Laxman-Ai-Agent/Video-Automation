import React from 'react';
import { Scissors, Play, RefreshCw, CheckCircle2, AlertCircle, AlertTriangle, Sparkles } from 'lucide-react';
import { StageConfig } from '../../../types/pipeline';

export interface SegmentationSummaryBarProps {
  config: StageConfig;
  sceneData: any;
  scenesList: any[];
  llmReviewLoading: boolean;
  llmReviewMessage: string | null;
  hasAnyMissingLlm: boolean;
  handleRunLlmReview: () => void;
  onRetryStage?: (stageId: string) => void;
}

export const SegmentationSummaryBar: React.FC<SegmentationSummaryBarProps> = ({
  config,
  sceneData,
  scenesList,
  llmReviewLoading,
  llmReviewMessage,
  hasAnyMissingLlm,
  handleRunLlmReview,
  onRetryStage
}) => {
  return (
    <>
      {/* Summary Metadata Bar */}
      <div style={{
        backgroundColor: 'var(--bg-elevated)',
        border: '1px solid var(--border-card)',
        borderRadius: '8px',
        padding: '14px 18px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            backgroundColor: 'rgba(0, 216, 245, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent-cyan)'
          }}>
            <Scissors size={16} />
          </div>
          <div>
            <div style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
              Scene Segmentation & Script Breakdown
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Method: <strong style={{ color: 'var(--accent-cyan)' }}>{sceneData?.raw?.segmentation_method || (sceneData?.isFallback ? 'source_utterances_preview' : 'llm_semantic_grouping')}</strong>
              {sceneData?.raw?.language && <> • Language: <strong>{sceneData.raw.language.toUpperCase()}</strong></>}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Total Scenes</span>
            <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
              {scenesList.length}
            </div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Duration</span>
            <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {sceneData?.raw?.audio_duration_seconds 
                ? `${sceneData.raw.audio_duration_seconds.toFixed(1)}s` 
                : (scenesList.length > 0 && scenesList[scenesList.length - 1].end_time 
                    ? `${Number(scenesList[scenesList.length - 1].end_time).toFixed(1)}s` 
                    : '—')}
            </div>
          </div>

          <span style={{
            fontSize: '10.5px',
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            backgroundColor: sceneData?.isFallback ? 'rgba(245, 158, 11, 0.15)' : 'rgba(0, 216, 245, 0.12)',
            color: sceneData?.isFallback ? '#FBBF24' : 'var(--accent-cyan)',
            padding: '3px 8px',
            borderRadius: '4px',
            border: sceneData?.isFallback ? '1px solid rgba(245, 158, 11, 0.3)' : '1px solid rgba(0, 216, 245, 0.25)'
          }}>
            {sceneData?.source || 'scene_segmentation.json'}
          </span>
        </div>
      </div>

      {/* Fallback Notice if using audio_analysis.json utterances */}
      {sceneData?.isFallback && (
        <div style={{
          backgroundColor: 'rgba(245, 158, 11, 0.08)',
          border: '1px solid rgba(245, 158, 11, 0.25)',
          borderRadius: '8px',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#FBBF24', fontSize: '12.5px' }}>
            <AlertTriangle size={16} style={{ flexShrink: 0 }} />
            <span>
              Displaying audio speech utterances as preview. The Scene Segmentation stage can be triggered to generate LLM semantic cut boundaries.
            </span>
          </div>
          {onRetryStage && (
            <button
              onClick={() => onRetryStage(config.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                backgroundColor: 'rgba(0, 216, 245, 0.15)',
                border: '1px solid rgba(0, 216, 245, 0.35)',
                borderRadius: '4px',
                color: 'var(--accent-cyan)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                flexShrink: 0
              }}
            >
              <Play size={12} fill="currentColor" />
              <span>Run Scene Segmentation</span>
            </button>
          )}
        </div>
      )}

      {/* LLM Review In-Flight / Success Message Toast */}
      {llmReviewMessage && (
        <div
          data-testid="llm-review-status-toast"
          style={{
            backgroundColor: 'rgba(124, 58, 237, 0.15)',
            border: '1px solid rgba(168, 85, 247, 0.4)',
            borderRadius: '8px',
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            color: '#D8B4FE',
            fontSize: '13px',
            fontWeight: 600
          }}
        >
          {llmReviewLoading ? (
            <RefreshCw size={16} className="animate-spin" color="#C084FC" />
          ) : (
            <CheckCircle2 size={16} color="#34D399" />
          )}
          <span>{llmReviewMessage}</span>
        </div>
      )}

      {/* Mandatory LLM Verification Gate Banner */}
      {hasAnyMissingLlm && (
        <div 
          data-testid="llm-verification-gate-banner"
          style={{
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            borderRadius: '8px',
            padding: '14px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
            <AlertCircle size={20} color="#EF4444" style={{ flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#FCA5A5' }}>
                ⚠️ LLM Verification Required Before Next Step
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                Narration must be verified by LLM before Visual Planning and image generation can proceed. English technical terms must be standardized in English script and Telugu grammar verified.
              </div>
            </div>
          </div>

          <button
            onClick={handleRunLlmReview}
            disabled={llmReviewLoading}
            data-testid="run-all-llm-verification-btn"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              backgroundColor: '#7C3AED',
              border: '1px solid #A78BFA',
              borderRadius: '6px',
              color: '#FFFFFF',
              fontSize: '12.5px',
              fontWeight: 700,
              cursor: llmReviewLoading ? 'not-allowed' : 'pointer',
              opacity: llmReviewLoading ? 0.7 : 1,
              flexShrink: 0,
              boxShadow: '0 2px 8px rgba(124, 58, 237, 0.4)'
            }}
          >
            {llmReviewLoading ? <RefreshCw size={13} className="animate-spin" /> : <Sparkles size={13} />}
            <span>{llmReviewLoading ? 'Verifying with LLM...' : 'Run LLM Verification'}</span>
          </button>
        </div>
      )}
    </>
  );
};
