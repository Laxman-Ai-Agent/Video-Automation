import React, { useEffect, useState } from 'react';
import { X, ChevronLeft, ChevronRight, Copy, Check } from 'lucide-react';
import type { MotionGenScene } from '../../../services/api';
import styles from './MotionGenScenes.module.css';

type Tab = 'code' | 'elements' | 'checks' | 'details';
const TABS: { id: Tab; label: string }[] = [
  { id: 'code', label: 'Code' },
  { id: 'elements', label: 'Elements' },
  { id: 'checks', label: 'Checks' },
  { id: 'details', label: 'Details' },
];

export interface MotionGenSceneModalProps {
  scene: MotionGenScene;
  idx: number;
  total: number;
  onClose: () => void;
  onStep: (delta: number) => void;
}

const tone = (ok: boolean | null | undefined) => (ok === null || ok === undefined ? styles.warn : ok ? styles.ok : styles.bad);

/** One scene of Motion Generation in full: the TSX that was written (with line numbers), the elements it draws, what was checked and how the code was made. */
export const MotionGenSceneModal: React.FC<MotionGenSceneModalProps> = ({ scene, idx, total, onClose, onStep }) => {
  const [tab, setTab] = useState<Tab>('code');
  const [copied, setCopied] = useState(false);
  useEffect(() => setTab('code'), [scene.scene_id]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' && e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.stopImmediatePropagation();                                   // the popup owns these keys: Esc must not also close the stage drawer behind it
      if (e.key === 'Escape') onClose();
      else onStep(e.key === 'ArrowLeft' ? -1 : 1);
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [onClose, onStep]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(scene.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard may be unavailable */ }
  };

  const gen = scene.generation || {};
  const classes = scene.element_classifications || [];
  const pr = scene.preview_result;

  return (
    <div className={styles.overlay} data-testid="motion-gen-scene-modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={styles.modal} role="dialog" aria-label={`Motion Generation scene ${scene.scene_id}`} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.headLeft}>
            <span className={styles.sceneBadge}>SCENE {String(scene.scene_id).padStart(2, '0')}</span>
            <div>
              <h3 className={styles.title}>{scene.meaning || `Scene ${scene.scene_id}`}</h3>
              <div className={styles.muted}>
                {scene.file} · {scene.lines} lines · {(scene.bytes / 1024).toFixed(1)} KB{scene.start !== null && scene.end !== null ? ` · ${scene.start.toFixed(1)}s - ${scene.end.toFixed(1)}s` : ''}
              </div>
            </div>
          </div>
          <div className={styles.headRight}>
            <button className={styles.iconBtn} disabled={idx === 0} onClick={() => onStep(-1)} title="Previous scene (←)" data-testid="motion-gen-modal-prev"><ChevronLeft size={16} /></button>
            <span className={styles.muted}>{idx + 1} / {total}</span>
            <button className={styles.iconBtn} disabled={idx >= total - 1} onClick={() => onStep(1)} title="Next scene (→)" data-testid="motion-gen-modal-next"><ChevronRight size={16} /></button>
            <button className={styles.iconBtn} onClick={onClose} title="Close (Esc)" data-testid="motion-gen-modal-close"><X size={16} /></button>
          </div>
        </div>
        <div className={styles.tabs}>
          {TABS.map((t) => (
            <button key={t.id} className={`${styles.tab} ${tab === t.id ? styles.tabActive : ''}`} onClick={() => setTab(t.id)} data-testid={`motion-gen-modal-tab-${t.id}`}>{t.label}</button>
          ))}
        </div>
        <div className={styles.body}>
          {tab === 'code' && (
            <div className={styles.codeBox}>
              <div className={styles.codeBar}>
                <span>{scene.file}</span>
                <button className={styles.footBtn} onClick={copy}>{copied ? <Check size={13} /> : <Copy size={13} />} {copied ? 'Copied!' : 'Copy code'}</button>
              </div>
              <pre className={styles.code} data-testid="motion-gen-code">
                {scene.code ? scene.code.replace(/\n$/, '').split('\n').map((line, i) => <span key={i} className={styles.codeLine}>{line || ' '}</span>) : 'The code file is missing.'}
              </pre>
            </div>
          )}

          {tab === 'elements' && (
            <>
              <div className={styles.card}>
                <div className={styles.cardTitle}>Drawn by this code ({scene.implemented_elements.length} of {scene.required_elements.length} required)</div>
                <div className={styles.chips}>
                  {scene.implemented_elements.map((id) => <span key={id} className={`${styles.chip} ${styles.ok}`}>✓ {id}</span>)}
                  {scene.missing_required_elements.map((id) => <span key={id} className={`${styles.chip} ${styles.bad}`}>✗ {id} (required, not drawn)</span>)}
                  {scene.implemented_elements.length === 0 && scene.missing_required_elements.length === 0 && <span className={styles.muted}>No element is listed for this scene.</span>}
                </div>
              </div>
              {classes.length > 0 && (
                <div className={styles.card}>
                  <div className={styles.cardTitle}>How each element is drawn</div>
                  {classes.map((c) => (
                    <div key={c.element_id} className={styles.listRow}>
                      <span className={`${styles.chip} ${styles.info}`}>{c.element_id}</span>
                      <span className={styles.muted}>{c.requested_effect}</span>
                      <span className={`${styles.chip} ${c.is_supported ? styles.ok : styles.warn}`}>{c.fallback_strategy}</span>
                      {c.capability_limitation && <span className={styles.muted}>{c.capability_limitation.replace(/_/g, ' ')}</span>}
                    </div>
                  ))}
                </div>
              )}
              {scene.descriptors.length > 0 && (
                <div className={styles.card}>
                  <div className={styles.cardTitle}>In the composition ({scene.descriptors.length} layers)</div>
                  {scene.descriptors.map((d, i) => (
                    <div key={`${d.element_id}-${i}`} className={styles.listRow}>
                      <span className={styles.chip}>{d.element_id}</span>
                      <span className={styles.muted}>{d.element_type} · {d.component_id} · {d.preset_id}</span>
                      <span className={styles.muted}>{Number(d.start).toFixed(2)}s - {Number(d.end).toFixed(2)}s</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {tab === 'checks' && (
            <div className={styles.card}>
              <div className={styles.cardTitle}>What was checked</div>
              <div className={styles.kv}>
                <span className={styles.k}>TypeScript compile</span>
                <span className={`${styles.chip} ${tone(scene.compile_status === 'passed' ? true : scene.compile_status === 'pending' ? null : false)}`}>{scene.compile_status || 'unknown'}</span>
                <span className={styles.k}>Security audit</span>
                <span className={`${styles.chip} ${tone(scene.security_audit?.passed)}`}>
                  {scene.security_audit ? `${scene.security_audit.passed ? 'passed' : 'failed'}, ${scene.security_audit.findings.length} findings` : 'not recorded'}
                </span>
                <span className={styles.k}>Preview verifier</span>
                <span className={`${styles.chip} ${tone(pr?.passed)}`}>{pr ? `${pr.passed ? 'passed' : 'failed'}, score ${pr.score}` : 'not recorded'}</span>
                <span className={styles.k}>Safe area / typography / contrast</span>
                <span className={styles.chips}>
                  <span className={`${styles.chip} ${tone(pr?.safe_zone_passed)}`}>safe area</span>
                  <span className={`${styles.chip} ${tone(pr?.typography_passed)}`}>typography</span>
                  <span className={`${styles.chip} ${tone(pr?.contrast_passed)}`}>contrast</span>
                </span>
              </div>
              {[...(pr?.findings || []), ...(scene.security_audit?.findings || [])].map((f, i) => <div key={i} className={styles.muted}>• {typeof f === 'string' ? f : JSON.stringify(f)}</div>)}
              {scene.warnings.map((w, i) => <div key={i} className={`${styles.chip} ${styles.warn}`}>{w}</div>)}
              {scene.validation_notes.map((n, i) => <div key={i} className={styles.muted}>• {n.message || JSON.stringify(n)}</div>)}
              {scene.code_changed && <div className={`${styles.chip} ${styles.warn}`}>The file was edited after it was generated (its hash differs from the manifest).</div>}
            </div>
          )}

          {tab === 'details' && (
            <div className={styles.card}>
              <div className={styles.cardTitle}>How this code was made</div>
              <div className={styles.kv}>
                <span className={styles.k}>Made by</span>
                <span className={styles.v}>{gen.provider === 'cache' ? 'reused from an earlier run (same inputs)' : `${gen.provider || '?'} / ${gen.model || '?'}`}</span>
                <span className={styles.k}>Attempts / repairs</span><span className={styles.v}>{gen.attempt_count ?? '-'} / {scene.repair_attempts ?? '-'}</span>
                <span className={styles.k}>Latency</span><span className={styles.v}>{gen.latency_ms ? `${(gen.latency_ms / 1000).toFixed(1)} s` : '-'}</span>
                <span className={styles.k}>Duration</span>
                <span className={styles.v}>{scene.duration_frames ?? '-'} frames (30 fps){scene.timing ? ` · frames ${scene.timing.start_frame}-${scene.timing.end_frame}` : ''}</span>
                <span className={styles.k}>Input fingerprint</span><span className={styles.v}>{scene.input_fingerprint || 'not recorded (the code is written again at the next run)'}</span>
                <span className={styles.k}>Code SHA-256</span><span className={styles.v}>{scene.source_sha256 || '-'}</span>
              </div>
            </div>
          )}
        </div>
        <div className={styles.footer}>
          <button className={styles.footBtn} onClick={copy}>{copied ? <Check size={13} /> : <Copy size={13} />} {copied ? 'Copied!' : 'Copy code'}</button>
          <button className={`${styles.footBtn} ${styles.footPrimary}`} onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
};
