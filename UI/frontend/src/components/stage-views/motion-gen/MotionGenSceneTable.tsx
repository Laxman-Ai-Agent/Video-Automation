import React, { useEffect, useState } from 'react';
import { Code, RefreshCw } from 'lucide-react';
import { fetchMotionGenerationScenes, type MotionGenScenes } from '../../../services/api';
import { MotionGenSceneModal } from './MotionGenSceneModal';
import styles from './MotionGenScenes.module.css';

export interface MotionGenSceneTableProps {
  projectId: string;
  refreshKey?: string;              // the stage status: the scenes are read again when it changes (a run finished)
  onRunStage?: (stageId: string) => void;
}

/** Motion Generation scene by scene: a table of the scenes with the code written for each; a click opens the scene in a popup (code, elements, checks, details). */
export const MotionGenSceneTable: React.FC<MotionGenSceneTableProps> = ({ projectId, refreshKey, onRunStage }) => {
  const [data, setData] = useState<MotionGenScenes | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<number | null>(null);          // index of the scene whose popup is open

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetchMotionGenerationScenes(projectId).then((d) => {
      if (!alive) return;
      setData(d);
      setLoading(false);
    });
    return () => { alive = false; };
  }, [projectId, refreshKey]);

  if (loading && !data) {
    return <div className={styles.empty}><RefreshCw size={20} className="animate-spin" /> Loading the generated scenes…</div>;
  }
  if (!data || data.scenes.length === 0) {
    return (
      <div className={styles.empty} data-testid="motion-gen-no-scenes">
        No scene code has been generated yet.
        {onRunStage && <div style={{ marginTop: 12 }}><button className={styles.viewBtn} onClick={() => onRunStage('motion_gen')}>Run Motion Generation</button></div>}
      </div>
    );
  }

  const scenes = data.scenes;
  const totalLines = scenes.reduce((n, s) => n + s.lines, 0);
  const diag = data.diagnostics || {};
  const step = (delta: number) => setOpen((i) => (i === null ? i : Math.min(scenes.length - 1, Math.max(0, i + delta))));

  return (
    <div className={styles.wrap} data-testid="motion-gen-scenes-tab">
      <div className={styles.summary}>
        <span className={styles.summaryTitle}>Generated scene code</span>
        <span className={styles.chip}>{data.mode || 'custom_code'}</span>
        <span className={`${styles.chip} ${data.typecheck?.status === 'passed' ? styles.ok : styles.warn}`}>TypeScript: {data.typecheck?.status || 'unknown'}</span>
        <span className={styles.chip}>{scenes.length} scenes · {totalLines} lines</span>
        {typeof diag.fallbacks_applied === 'number' && <span className={`${styles.chip} ${diag.fallbacks_applied ? styles.warn : styles.ok}`}>{diag.fallbacks_applied} fallbacks</span>}
        {typeof diag.warnings_count === 'number' && <span className={`${styles.chip} ${diag.warnings_count ? styles.warn : styles.ok}`}>{diag.warnings_count} warnings</span>}
        {data.run_id && <span className={styles.chip}>{data.run_id}</span>}
      </div>

      <table className={styles.table} data-testid="motion-gen-scenes-list">
        <thead>
          <tr>
            <th className={styles.th}>Scene</th><th className={styles.th}>Purpose</th><th className={styles.th}>Elements drawn</th>
            <th className={styles.th}>Code</th><th className={styles.th}>Checks</th><th className={styles.th}>Made by</th><th className={styles.th} />
          </tr>
        </thead>
        <tbody>
          {scenes.map((s, i) => {
            const cached = s.generation?.provider === 'cache';
            const missing = s.missing_required_elements.length;
            return (
              <tr key={s.scene_id} className={styles.row} onClick={() => setOpen(i)} data-testid={`motion-gen-scene-row-${s.scene_id}`}>
                <td className={styles.td}><span className={styles.sceneBadge}>SCENE {String(s.scene_id).padStart(2, '0')}</span></td>
                <td className={styles.td}>
                  <div className={styles.meaning}>{s.meaning || '—'}</div>
                  <div className={styles.muted}>{s.start !== null && s.end !== null ? `${s.start.toFixed(1)}s - ${s.end.toFixed(1)}s` : ''}{s.duration_frames ? ` · ${s.duration_frames} frames` : ''}</div>
                </td>
                <td className={styles.td}>
                  <span className={`${styles.chip} ${missing ? styles.bad : styles.ok}`}>{s.implemented_elements.length} / {s.required_elements.length}{missing ? ` · ${missing} missing` : ''}</span>
                </td>
                <td className={styles.td}><span className={styles.muted}>{s.lines} lines · {(s.bytes / 1024).toFixed(1)} KB</span></td>
                <td className={styles.td}>
                  <div className={styles.chips}>
                    <span className={`${styles.chip} ${s.compile_status === 'passed' ? styles.ok : styles.warn}`}>compile {s.compile_status || '?'}</span>
                    <span className={`${styles.chip} ${s.security_audit?.passed ? styles.ok : styles.bad}`}>security</span>
                    {s.preview_result && <span className={`${styles.chip} ${s.preview_result.passed ? styles.ok : styles.warn}`}>preview {s.preview_result.score}</span>}
                    {s.code_changed && <span className={`${styles.chip} ${styles.warn}`}>edited</span>}
                  </div>
                </td>
                <td className={styles.td}><span className={styles.muted}>{cached ? 'reused (same inputs)' : `${s.generation?.model || '?'} · ${s.generation?.attempt_count ?? '-'} attempt(s)`}</span></td>
                <td className={styles.td}><button className={styles.viewBtn} onClick={(e) => { e.stopPropagation(); setOpen(i); }} data-testid={`motion-gen-scene-open-${s.scene_id}`}><Code size={12} /> Code</button></td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {open !== null && scenes[open] && (
        <MotionGenSceneModal scene={scenes[open]} idx={open} total={scenes.length} onClose={() => setOpen(null)} onStep={step} />
      )}
    </div>
  );
};
