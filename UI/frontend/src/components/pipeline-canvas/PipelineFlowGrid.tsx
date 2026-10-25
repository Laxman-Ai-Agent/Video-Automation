import React from 'react';
import styles from '../PipelineCanvas.module.css';
import { CANONICAL_12_STAGES, PipelineProjectState } from '../../types/pipeline';
import { StageCard } from '../StageCard';

export interface PipelineFlowGridProps {
  projectState: PipelineProjectState;
  selectedStageId: string | null;
  isRunning: boolean;
  handleRunStage: (stageId: string) => Promise<void>;
  handleStopStage: (stageId: string) => Promise<void>;
  onSelectStage: (stageId: string) => void;
}

export const PipelineFlowGrid: React.FC<PipelineFlowGridProps> = ({
  projectState,
  selectedStageId,
  isRunning,
  handleRunStage,
  handleStopStage,
  onSelectStage
}) => {
  return (
    <div 
      data-testid="stages-container"
      className={styles.stagesContainer}
    >
      {[
        CANONICAL_12_STAGES.slice(0, 4),   // Row 1: Audio Analysis & Planning (01 to 04)
        CANONICAL_12_STAGES.slice(4, 8),   // Row 2: Motion Planning & Assembly (05 to 08)
        CANONICAL_12_STAGES.slice(8)       // Row 3: Approval, Render, QC & Delivery (09 to the last stage)
      ].map((rowStages, rowIndex) => (
        <div key={rowIndex} style={{ position: 'relative' }}>
          {/* Row of Stage Cards */}
          <div className={styles.stagesGrid}>
            {rowStages.map((stage, colIndex) => {
              const isLastInRow = colIndex === rowStages.length - 1;
              const isPassed = projectState.stages[stage.id]?.status === 'completed';
              const isCurrentlyRunning = projectState.stages[stage.id]?.status === 'running';

              return (
                <div 
                  key={stage.id} 
                  className={styles.stageCardWrapper}
                >
                  <StageCard
                    config={stage}
                    state={projectState.stages[stage.id]}
                    isSelected={selectedStageId === stage.id}
                    onRunStage={handleRunStage}
                    onStopStage={handleStopStage}
                    isPipelineRunning={isRunning}
                    onSelect={() => onSelectStage(stage.id)}
                  />

                  {/* Sequential Connector Arrow to Next Card in Row */}
                  {!isLastInRow && (
                    <div className={styles.connectorWrapper}>
                      <div 
                        className={`${styles.connectorLine} ${isCurrentlyRunning ? 'animate-arrow-flow' : ''}`} 
                        style={{
                          backgroundColor: isPassed 
                            ? 'var(--status-completed)' 
                            : (isCurrentlyRunning ? 'var(--accent-cyan)' : 'var(--border-card)'),
                          boxShadow: isCurrentlyRunning ? '0 0 8px var(--accent-cyan)' : 'none'
                        }}
                      >
                        {/* Directional Arrow Head */}
                        <div 
                          className={styles.connectorArrow}
                          style={{
                            borderLeft: `6px solid ${isPassed ? 'var(--status-completed)' : (isCurrentlyRunning ? 'var(--accent-cyan)' : 'var(--border-card)')}`
                          }} 
                        />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};
