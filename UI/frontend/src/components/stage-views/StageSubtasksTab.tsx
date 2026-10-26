import React from 'react';
import { Play } from 'lucide-react';
import { StageConfig } from '../../types/pipeline';
import { StageSubtasks, runStageStepChecks, fetchStageSubtasks } from '../../services/api';
import { SubtaskCard } from '../SubtaskCard';

export interface StageSubtasksTabProps {
  projectId?: string;
  config: StageConfig;
  isFullPage: boolean;
  subSteps: any[];
  realSub: StageSubtasks | null;
  setRealSub: React.Dispatch<React.SetStateAction<StageSubtasks | null>>;
  isRunning: boolean;
}

export const StageSubtasksTab: React.FC<StageSubtasksTabProps> = ({
  projectId,
  config,
  isFullPage,
  subSteps,
  realSub,
  setRealSub,
  isRunning
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* Embedded Video Player when video is available for Render / Final QC / Delivery */}
      {projectId && ['render', 'qc', 'final'].includes(config.id) && (
        <div style={{
          borderRadius: '10px',
          overflow: 'hidden',
          backgroundColor: '#0a0d14',
          border: '1px solid var(--border-card)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <div style={{
            padding: '8px 14px',
            backgroundColor: 'rgba(255,255,255,0.03)',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Play size={13} style={{ color: 'var(--accent-cyan)' }} />
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Rendered Video Preview (1080p · 30 FPS)
              </span>
            </div>
            <a
              href={`http://127.0.0.1:8000/projects/${projectId}/video?preview=false`}
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: '11px', color: 'var(--accent-cyan)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              Open in tab ↗
            </a>
          </div>
          <div style={{ position: 'relative', width: '100%', backgroundColor: '#000', display: 'flex', justifyContent: 'center' }}>
            <video
              controls
              preload="metadata"
              src={`http://127.0.0.1:8000/projects/${projectId}/video?preview=false`}
              style={{ width: '100%', maxHeight: '360px', objectFit: 'contain' }}
            />
          </div>
        </div>
      )}

      <span style={{ fontSize: '12.5px', color: 'var(--text-muted)', fontWeight: 600 }}>
        {subSteps.length
          ? (realSub?.report
              ? `Steps recorded in ${realSub.report}${realSub.written ? ` (written ${new Date(realSub.written * 1000).toLocaleString()})` : ''}`
              : 'Live progress: the step report is written when the stage finishes')
          : isRunning
            ? 'Stage is currently executing: subtasks will update live as steps complete...'
            : 'This stage does not record step-by-step results; only its overall status and LLM review are available.'}
      </span>
      {subSteps.length > 0 && (() => {
        const warnings = subSteps.filter(
          (s) => s.status === 'warning' || s.llm_check?.verdict === 'questions'
        ).length;
        const failures = subSteps.filter(
          (s) => s.status === 'failed' || s.status === 'error' || s.llm_check?.verdict === 'rejects'
        ).length;
        const verifiedClean = subSteps.filter(
          (s) => (s.status === 'completed' || s.status === 'passed') && s.llm_check?.current && s.llm_check.verdict === 'confirms'
        ).length;
        const activeMdl = realSub?.active_model || 'openai/gpt-oss-20b';

        return (
          <div data-testid="subtasks-llm-step-summary" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', fontSize: '12px', color: 'var(--text-secondary)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span>
                LLM Verification: <strong style={{ color: verifiedClean === subSteps.length ? '#10B981' : 'var(--text-primary)' }}>{verifiedClean} / {subSteps.length} verified</strong>
                {warnings > 0 && <span style={{ color: '#F59E0B', fontWeight: 600 }}> · {warnings} {warnings === 1 ? 'warning' : 'warnings'}</span>}
                {failures > 0 && <span style={{ color: '#EF4444', fontWeight: 600 }}> · {failures} failed</span>}
                {realSub?.llm_checks_running && <span style={{ color: 'var(--accent-cyan)' }}> · verification running…</span>}
              </span>
              <span
                style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                  backgroundColor: 'var(--bg-elevated)',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                Model: {activeMdl}
              </span>
            </div>

            {!realSub?.llm_checks_running && (verifiedClean + warnings + failures) < subSteps.length && projectId && (
              <button
                onClick={() => runStageStepChecks(projectId, config.id).then(() => fetchStageSubtasks(projectId, config.id).then(setRealSub))}
                data-testid="subtasks-llm-recheck-btn"
                style={{ height: '26px', padding: '0 12px', borderRadius: '6px', fontSize: '11.5px', fontWeight: 600, cursor: 'pointer', color: '#38BDF8', backgroundColor: 'rgba(24, 144, 255, 0.12)', border: '1px solid rgba(24, 144, 255, 0.35)' }}
              >
                Verify remaining with {activeMdl}
              </button>
            )}
          </div>
        );
      })()}
      {isRunning && subSteps.length > 0 && (
        <span style={{ fontSize: '12px', color: '#FBBF24' }}>
          The stage is running now: these are the results of its last finished run and refresh when the new report is written.
        </span>
      )}
      <div style={{
        display: 'grid',
        gridTemplateColumns: isFullPage ? 'repeat(auto-fill, minmax(135px, 1fr))' : 'repeat(auto-fill, minmax(120px, 1fr))',
        gap: '12px'
      }}>
        {subSteps.map((sub, i) => (
          <SubtaskCard
            key={`${sub.n ?? i}-${sub.name}`}
            subtask={sub}
            index={i}
            stageRunning={isRunning}
            llmChecksRunning={Boolean(realSub?.llm_checks_running)}
            activeModel={realSub?.active_model || 'openai/gpt-oss-20b'}
          />
        ))}
      </div>
    </div>
  );
};
