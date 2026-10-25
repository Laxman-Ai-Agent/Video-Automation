import React from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import {
  sceneTdStyle,
  sceneRowStyle
} from '../sceneTableStyles';
import { SegmentationSceneExpanded } from './SegmentationSceneExpanded';

export interface SegmentationSceneRowProps {
  scene: any;
  idx: number;
  isExpanded: boolean;
  isFullPage?: boolean;
  llmReviewLoading: boolean;
  toggleScene: (id: string) => void;
  handleRunLlmReview: () => void;
}

export const SegmentationSceneRow: React.FC<SegmentationSceneRowProps> = ({
  scene: s,
  idx,
  isExpanded,
  isFullPage = false,
  llmReviewLoading,
  toggleScene,
  handleRunLlmReview
}) => {
  const sceneId = s.scene_id || `scene_${idx + 1}`;
  const sceneNum = String(s.scene_index !== undefined ? s.scene_index : idx + 1).padStart(2, '0');
  const duration = (s.end_time !== undefined && s.start_time !== undefined)
    ? (Number(s.end_time) - Number(s.start_time)).toFixed(1)
    : null;

  return (
    <React.Fragment key={sceneId}>
      {/* Scene Table Row */}
      <tr
        onClick={() => toggleScene(sceneId)}
        data-testid={`scene-header-${idx}`}
        style={sceneRowStyle(isExpanded)}
      >
        <td style={{ ...sceneTdStyle, paddingRight: 0, color: 'var(--text-muted)', borderLeft: `3px solid ${s.llm_transcript ? '#10B981' : '#6B7280'}` }}>
          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </td>
        <td style={sceneTdStyle}>
          <span style={{
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            color: 'var(--accent-cyan)',
            backgroundColor: 'rgba(0, 216, 245, 0.1)',
            padding: '2px 7px',
            borderRadius: '4px',
            flexShrink: 0
          }}>
            #{sceneNum}
          </span>
        </td>
        <td style={sceneTdStyle}>
          {s.llm_transcript ? (
            <span 
              data-testid={`scene-${sceneNum}-badge-llm`}
              style={{
                fontSize: '10px',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                color: '#A7F3D0',
                backgroundColor: 'rgba(16, 185, 129, 0.16)',
                border: '1px solid rgba(16, 185, 129, 0.35)',
                padding: '1px 6px',
                borderRadius: '3px',
                flexShrink: 0
              }}
            >
              LLM FINAL
            </span>
          ) : (
            <span 
              data-testid={`scene-${sceneNum}-badge-raw`}
              style={{
                fontSize: '10px',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                color: '#9CA3AF',
                backgroundColor: 'rgba(107, 114, 128, 0.15)',
                border: '1px solid rgba(107, 114, 128, 0.35)',
                padding: '1px 6px',
                borderRadius: '3px',
                flexShrink: 0
              }}
            >
              NO LLM
            </span>
          )}
        </td>
        <td style={sceneTdStyle}>
          <span style={{
            display: 'block',
            fontSize: '13.5px',
            fontWeight: 600,
            color: 'var(--text-primary)', 
            whiteSpace: isExpanded ? 'normal' : 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            lineHeight: 1.4
          }}>
            {s.llm_transcript || s.transcript || s.semantic_beat || 'Scene Unit'}
          </span>
        </td>
        <td style={sceneTdStyle}>
          <span style={{
            fontSize: '11.5px',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
            whiteSpace: 'nowrap'
          }}>
            {s.start_time !== undefined ? `${Number(s.start_time).toFixed(2)}s` : '0.00s'} – {s.end_time !== undefined ? `${Number(s.end_time).toFixed(2)}s` : '—'}
          </span>
        </td>
        <td style={sceneTdStyle}>
          {duration && (
            <span style={{
              fontSize: '11px',
              color: 'var(--accent-blue)',
              fontWeight: 700,
              backgroundColor: 'rgba(24, 144, 255, 0.12)',
              padding: '2px 8px',
              borderRadius: '12px',
              fontFamily: 'var(--font-mono)'
            }}>
              {duration}s
            </span>
          )}
        </td>
      </tr>

      {/* Expanded Details Pane */}
      {isExpanded && (
        <tr>
          <td colSpan={6} style={{ padding: 0, borderBottom: '1px solid var(--border-subtle)' }}>
            <SegmentationSceneExpanded
              scene={s}
              sceneNum={sceneNum}
              duration={duration}
              isFullPage={isFullPage}
              llmReviewLoading={llmReviewLoading}
              handleRunLlmReview={handleRunLlmReview}
            />
          </td>
        </tr>
      )}
    </React.Fragment>
  );
};
