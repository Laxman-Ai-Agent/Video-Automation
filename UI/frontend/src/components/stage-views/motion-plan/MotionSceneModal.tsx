import React, { useEffect, useState } from 'react';
import { X, ChevronLeft, ChevronRight, Code, Copy, Check } from 'lucide-react';
import { MotionPlanSceneExpanded } from './MotionPlanSceneExpanded';
import styles from './MotionSceneModal.module.css';

export interface MotionSceneModalProps {
  scene: any;
  idx: number;
  total: number;
  startWithJson: boolean;
  isCopied: boolean;
  handleCopyMotionSceneJson: (scene: any, e?: React.MouseEvent) => void;
  onClose: () => void;
  onStep: (delta: number) => void;
}

/** One motion scene in full: its purpose, timing, narration, the before/after of the plan, every element with its preset, the whole action sequence and (on request) its raw JSON. */
export const MotionSceneModal: React.FC<MotionSceneModalProps> = ({ scene, idx, total, startWithJson, isCopied, handleCopyMotionSceneJson, onClose, onStep }) => {
  const [showJson, setShowJson] = useState(startWithJson);
  useEffect(() => setShowJson(startWithJson), [startWithJson, scene]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' && e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.stopImmediatePropagation();                                   // the popup owns these keys: Esc must not also close the stage drawer behind it
      if (e.key === 'Escape') onClose();
      else onStep(e.key === 'ArrowLeft' ? -1 : 1);
    };
    window.addEventListener('keydown', onKey, true);                 // capture: runs before the drawer's own listener
    return () => window.removeEventListener('keydown', onKey, true);
  }, [onClose, onStep]);

  const sceneNum = String(idx + 1).padStart(2, '0');
  const intent = scene.motion_intent || {};
  const pattern = scene.motion_plan_scene?.pattern || 'hero_text';
  const sequence: any[] = scene.sequence || [];
  const t0 = scene.timing?.start ?? 0;
  const t1 = scene.timing?.end ?? 0;
  const narration = scene.visual_scene_data?.narration?.text || scene.segmentation_data?.llm_transcript || scene.segmentation_data?.transcript || '';

  return (
    <div className={styles.overlay} data-testid="motion-scene-modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={styles.modal} role="dialog" aria-label={`Motion scene ${sceneNum}`} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.headLeft}>
            <span className={styles.badge}>SCENE {sceneNum}</span>
            <div>
              <h3 className={styles.title}>{(intent.purpose || 'Motion Beat')}: {intent.attention_goal || intent.takeaway || 'Kinetic animation focus'}</h3>
              {intent.mood && <div className={styles.subtitle}>Mood: {intent.mood}</div>}
            </div>
          </div>
          <div className={styles.headRight}>
            <button className={styles.iconBtn} disabled={idx === 0} onClick={() => onStep(-1)} title="Previous scene (←)" data-testid="motion-scene-modal-prev"><ChevronLeft size={16} /></button>
            <span className={styles.subtitle}>{idx + 1} / {total}</span>
            <button className={styles.iconBtn} disabled={idx >= total - 1} onClick={() => onStep(1)} title="Next scene (→)" data-testid="motion-scene-modal-next"><ChevronRight size={16} /></button>
            <button className={styles.iconBtn} onClick={onClose} title="Close (Esc)" data-testid="motion-scene-modal-close"><X size={16} /></button>
          </div>
        </div>
        <div className={styles.chips}>
          <span className={`${styles.chip} ${styles.chipTime}`}>⏱ {t0.toFixed(1)}s - {t1.toFixed(1)}s ({Math.max(0, t1 - t0).toFixed(1)}s)</span>
          <span className={`${styles.chip} ${styles.chipFrames}`}>🎞 {scene.timing?.start_frame ?? 0} - {scene.timing?.end_frame ?? 0}f</span>
          <span className={`${styles.chip} ${styles.chipPattern}`}>{pattern}</span>
          {intent.intensity && <span className={`${styles.chip} ${styles.chipIntensity}`}>⚡ {intent.intensity}</span>}
          <span className={`${styles.chip} ${styles.chipActions}`}>✨ {sequence.length} actions</span>
          <span className={styles.chip}>{(scene.elements || []).length} elements</span>
        </div>
        <div className={styles.body}>
          {narration && (
            <div className={styles.narration}>
              <div className={styles.narrationLabel}>Narration</div>
              <div className={styles.narrationText}>{narration}</div>
            </div>
          )}
          <MotionPlanSceneExpanded
            scene={scene}
            sceneNum={sceneNum}
            sceneKey={scene.scene_id || scene.plan_scene_id || String(idx + 1)}
            isFullPage
            isRawJsonOpen={showJson}
            isCopied={isCopied}
            handleCopyMotionSceneJson={handleCopyMotionSceneJson}
          />
        </div>
        <div className={styles.footer}>
          <button className={`${styles.footBtn} ${showJson ? styles.footBtnActive : ''}`} onClick={() => setShowJson(!showJson)} data-testid="motion-scene-modal-json"><Code size={13} /> Raw JSON</button>
          <button className={styles.footBtn} onClick={(e) => handleCopyMotionSceneJson(scene, e)}>{isCopied ? <Check size={13} /> : <Copy size={13} />} {isCopied ? 'Copied!' : 'Copy JSON'}</button>
          <button className={`${styles.footBtn} ${styles.footBtnPrimary}`} onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
};
