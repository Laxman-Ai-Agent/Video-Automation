import React from 'react';
import { Scissors, RefreshCw, Search } from 'lucide-react';
import { StageConfig } from '../../types/pipeline';
import {
  sceneTableStyle,
  sceneThStyle
} from './sceneTableStyles';
import { SegmentationSummaryBar } from './segmentation/SegmentationSummaryBar';
import { SegmentationSceneRow } from './segmentation/SegmentationSceneRow';

export interface SegmentationSceneTableProps {
  config: StageConfig;
  sceneData: any;
  scenesList: any[];
  filteredScenes: any[];
  sceneSearch: string;
  setSceneSearch: (val: string) => void;
  sceneLoading: boolean;
  expandedScenes: Record<string, boolean>;
  toggleScene: (id: string) => void;
  llmReviewLoading: boolean;
  llmReviewMessage: string | null;
  hasAnyMissingLlm: boolean;
  handleRunLlmReview: () => void;
  onRetryStage?: (stageId: string) => void;
  isFullPage?: boolean;
}

export const SegmentationSceneTable: React.FC<SegmentationSceneTableProps> = ({
  config,
  sceneData,
  scenesList,
  filteredScenes,
  sceneSearch,
  setSceneSearch,
  sceneLoading,
  expandedScenes,
  toggleScene,
  llmReviewLoading,
  llmReviewMessage,
  hasAnyMissingLlm,
  handleRunLlmReview,
  onRetryStage,
  isFullPage = false
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }} data-testid="scene-segmentation-tab-content">
      {/* Summary Metadata & LLM Status Bar */}
      <SegmentationSummaryBar
        config={config}
        sceneData={sceneData}
        scenesList={scenesList}
        llmReviewLoading={llmReviewLoading}
        llmReviewMessage={llmReviewMessage}
        hasAnyMissingLlm={hasAnyMissingLlm}
        handleRunLlmReview={handleRunLlmReview}
        onRetryStage={onRetryStage}
      />

      {/* Search Filter Input (matching reference screenshot) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <input
            type="text"
            placeholder="Filter words or utterances..."
            value={sceneSearch}
            onChange={(e) => setSceneSearch(e.target.value)}
            data-testid="scenes-filter-input"
            style={{
              width: '100%',
              padding: '9px 14px 9px 36px',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              color: 'var(--text-primary)', 
              fontSize: '13px',
              outline: 'none',
              boxSizing: 'border-box'
            }}
          />
          <Search size={15} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
        </div>
        {sceneSearch && (
          <button
            onClick={() => setSceneSearch('')}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '12px',
              padding: '6px 10px'
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Loading State */}
      {sceneLoading && (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          backgroundColor: 'var(--bg-elevated)',
          borderRadius: '8px',
          color: 'var(--text-muted)',
          fontSize: '13px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '10px'
        }}>
          <RefreshCw size={16} className="animate-spin" color="var(--accent-cyan)" />
          <span>Loading scene segmentation details...</span>
        </div>
      )}

      {/* Scene List Cards */}
      {!sceneLoading && filteredScenes.length > 0 && (
        <table data-testid="segmentation-scenes-list" style={sceneTableStyle}>
          <colgroup>
            <col style={{ width: '44px' }} /><col style={{ width: '72px' }} /><col style={{ width: '120px' }} />
            <col /><col style={{ width: '170px' }} /><col style={{ width: '90px' }} />
          </colgroup>
          <thead>
            <tr>
              <th style={sceneThStyle}></th><th style={sceneThStyle}>#</th><th style={sceneThStyle}>Source</th>
              <th style={sceneThStyle}>Narration</th><th style={sceneThStyle}>Time</th><th style={sceneThStyle}>Duration</th>
            </tr>
          </thead>
          <tbody>
            {filteredScenes.map((s: any, idx: number) => {
              const sceneId = s.scene_id || `scene_${idx + 1}`;
              return (
                <SegmentationSceneRow
                  key={sceneId}
                  scene={s}
                  idx={idx}
                  isExpanded={!!expandedScenes[sceneId]}
                  isFullPage={isFullPage}
                  llmReviewLoading={llmReviewLoading}
                  toggleScene={toggleScene}
                  handleRunLlmReview={handleRunLlmReview}
                />
              );
            })}
          </tbody>
        </table>
      )}

      {/* Empty State */}
      {!sceneLoading && filteredScenes.length === 0 && (
        <div style={{
          padding: '48px 16px',
          textAlign: 'center',
          backgroundColor: 'var(--bg-elevated)',
          borderRadius: '8px',
          border: '1px dashed rgba(255, 255, 255, 0.1)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '12px'
        }}>
          <Scissors size={28} color="var(--text-muted)" />
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
            {sceneSearch ? 'No matching scenes found' : 'No scenes available'}
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0, maxWidth: '360px' }}>
            {sceneSearch ? `Try adjusting your search query "${sceneSearch}"` : 'Run the Scene Segmentation stage to generate semantic scenes and cuts.'}
          </p>
          {sceneSearch && (
            <button
              onClick={() => setSceneSearch('')}
              style={{
                padding: '6px 14px',
                backgroundColor: 'var(--bg-elevated)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '4px',
                fontSize: '12px',
                cursor: 'pointer'
              }}
            >
              Clear Filter
            </button>
          )}
        </div>
      )}
    </div>
  );
};
