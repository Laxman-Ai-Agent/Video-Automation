import React from 'react';
import styles from './PipelinePillBar.module.css';
import { PipelineProjectState } from '../../types/pipeline';

export type PipelineTabType = 'flow' | 'approvals' | 'communication' | 'new-project' | 'projects';

interface PipelinePillBarProps {
  activeView: string;
  pipelineTab: PipelineTabType;
  projectState: PipelineProjectState;
  projectCount: number;
  onSelectTab: (tab: PipelineTabType) => void;
}

const TAB_CONFIG: Array<{ id: PipelineTabType; label: string }> = [
  { id: 'new-project', label: 'New Project' },
  { id: 'flow', label: 'Pipeline Execution Flow' },
  { id: 'approvals', label: 'Approvals & Blockers' },
  { id: 'communication', label: 'Agent Communication' },
  { id: 'projects', label: 'Previous Projects' }
];

export const PipelinePillBar: React.FC<PipelinePillBarProps> = ({
  activeView,
  pipelineTab,
  projectState,
  projectCount,
  onSelectTab
}) => {
  return (
    <div data-testid="pipeline-pill-bar" className={styles.pillBarContainer}>
      <div className={styles.pillGroup}>
        {TAB_CONFIG.map(({ id, label }) => {
          const active = (activeView === 'audio-input' ? 'new-project' : pipelineTab) === id;
          const badge = id === 'approvals'
            ? Object.values(projectState.stages).filter(
                (s) => s.status === 'blocked' || (s.blockers && s.blockers.length > 0)
              ).length
            : id === 'projects' ? projectCount : 0;

          const badgeClass = id === 'approvals' && badge > 0 ? 'issue-blink-amber' : undefined;

          return (
            <button
              key={id}
              data-testid={`pill-tab-${id}`}
              className={`${styles.pillButton} ${active ? styles.pillButtonActive : ''} ${badgeClass || ''}`}
              onClick={() => onSelectTab(id)}
            >
              {label}{badge > 0 ? ` ${badge}` : ''}
            </button>
          );
        })}
      </div>
    </div>
  );
};
