import React, { useState } from 'react';
import styles from './VisualPlanningView.module.css';
import { AlertTriangle, CheckCircle2, Film, Image as ImageIcon, Sparkles, Eye, Volume2 } from 'lucide-react';
import { MediaFamily } from '../services/mediaMix';
import { VisualSceneModal } from './VisualSceneModal';

const COLOR: Record<MediaFamily, string> = {
  motion: 'var(--accent-blue, #3b82f6)',
  image: 'var(--accent-cyan, #06b6d4)',
  video: '#a78bfa'
};

const COUNT_COLUMNS: { key: string; label: string }[] = [
  { key: 'text', label: 'Kinetic Text' },
  { key: 'icon', label: 'Icons' },
  { key: 'graphic', label: 'Cards & Graphics' },
  { key: 'image', label: 'Image Cards' },
  { key: 'video', label: 'Video Frames' }
];

interface VisualPlanningViewProps {
  data: any | null;
  loading: boolean;
}

export const HeroBadge: React.FC<{ family: MediaFamily }> = ({ family }) => {
  const isImage = family === 'image';
  const isVideo = family === 'video';
  const label = isImage ? 'Motion + Image Card' : isVideo ? 'Motion + Video Frame' : 'Motion Graphics';
  const color = isImage ? 'var(--accent-cyan, #06b6d4)' : isVideo ? '#c084fc' : 'var(--accent-blue, #3b82f6)';
  return (
    <span
      data-testid={`hero-${family}`}
      className={styles.heroBadge}
      style={{
        color: color,
        backgroundColor: isImage ? 'rgba(6, 182, 212, 0.12)' : isVideo ? 'rgba(192, 132, 252, 0.12)' : 'rgba(59, 130, 246, 0.12)',
        border: `1px solid ${isImage ? 'rgba(6, 182, 212, 0.35)' : isVideo ? 'rgba(192, 132, 252, 0.35)' : 'rgba(59, 130, 246, 0.35)'}`
      }}
    >
      {isImage ? <ImageIcon size={11} /> : isVideo ? <Film size={11} /> : <Sparkles size={11} />}
      {label}
    </span>
  );
};

export const VisualPlanningView: React.FC<VisualPlanningViewProps> = ({ data, loading }) => {
  const [selectedScene, setSelectedScene] = useState<any | null>(null);

  const scenes: any[] = data?.scenes || [];
  const totals = data?.totals || {};
  const errors: string[] = data?.validation?.errors || [];
  const warnings: string[] = data?.validation?.warnings || [];

  if (loading) {
    return (
      <div className={styles.loadingCard} data-testid="visual-planning-loading">
        Loading the visual plan…
      </div>
    );
  }

  if (!data) {
    return (
      <div className={styles.emptyCard} data-testid="visual-planning-empty">
        Visual Planning has not produced a plan for this project yet. Run the stage to plan what each scene shows.
      </div>
    );
  }

  return (
    <div className={styles.container} data-testid="visual-planning-tab-content">
      {/* Header Info */}
      <div className={styles.headerCard}>
        <div>
          <div className={styles.title}>Visual Planning</div>
          <div className={styles.subtitle}>
            {scenes.length} scenes · {data.visual_style?.category || 'Cinematic Motion Graphics'} · {data.project?.aspect_ratio}
            {data.stale ? ' · out of date (the scene plan changed)' : ''}
          </div>
        </div>
        <span
          data-testid="visual-planning-validation"
          className={`${styles.validationBadge} ${
            errors.length ? styles.badgeError : warnings.length ? styles.badgeWarn : styles.badgeOk
          }`}
        >
          {errors.length ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
          {errors.length ? `${errors.length} blocking error(s)` : warnings.length ? `${warnings.length} warning(s)` : 'all checks passed'}
        </span>
      </div>

      {/* 100% Motion Graphics Banner */}
      <div className={styles.motionBannerCard} data-testid="motion-format-banner">
        <div className={styles.motionBannerHeader}>
          <div className={styles.motionBadge}>
            <Sparkles size={14} />
            <span>100% Kinetic Motion Canvas</span>
          </div>
          <span className={styles.motionBannerSub} data-testid="mix-note">
            All scenes are rendered as animated motion graphics. Images and video clips are embedded inside interactive motion cards, card decks, and device frames synchronized with dialogue.
          </span>
        </div>
      </div>

      {/* Totals Summary */}
      <div className={styles.totalsGrid} data-testid="visual-planning-totals">
        {COUNT_COLUMNS.map((c) => (
          <div key={c.key} className={styles.totalCard}>
            <div className={styles.totalValue}>{totals[c.key] ?? 0}</div>
            <div className={styles.totalLabel}>{c.label}</div>
          </div>
        ))}
      </div>

      {/* Scenes Table */}
      <div className={styles.tableCard}>
        <table className={styles.table} data-testid="visual-planning-table">
          <thead>
            <tr>
              <th className={styles.th}>Scene</th>
              <th className={styles.th}>Format</th>
              {COUNT_COLUMNS.map((c) => (
                <th key={c.key} className={styles.thCenter}>
                  {c.label}
                </th>
              ))}
              <th className={styles.th}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                  <Volume2 size={13} color="var(--accent-cyan)" />
                  Original Narration
                </span>
              </th>
              <th className={`${styles.th} ${styles.actionsCol}`}>Action</th>
            </tr>
          </thead>
          <tbody>
            {scenes.map((s) => (
              <tr
                key={s.scene_id}
                data-testid={`scene-row-${s.scene_id}`}
                className={styles.tr}
                onClick={() => setSelectedScene(s)}
              >
                {/* Scene & Time */}
                <td className={styles.td}>
                  <div className={styles.sceneIdCol}>
                    <span className={styles.sceneIdText}>{s.scene_id}</span>
                    <span className={styles.timeMuted}>
                      {s.narration?.start_seconds?.toFixed?.(1)}–{s.narration?.end_seconds?.toFixed?.(1)} s
                    </span>
                  </div>
                </td>

                {/* Format: Motion / Motion + Card */}
                <td className={styles.td}>
                  <HeroBadge family={s.hero} />
                </td>

                {/* Element Counts */}
                {COUNT_COLUMNS.map((c) => (
                  <td
                    key={c.key}
                    data-testid={`count-${s.scene_id}-${c.key}`}
                    className={`${styles.tdCenter} ${styles.countCell}`}
                    style={{
                      color: s.counts?.[c.key] ? 'var(--text-primary)' : 'var(--text-muted)'
                    }}
                  >
                    {s.counts?.[c.key] ?? 0}
                  </td>
                ))}

                {/* Original Narration (Telugu & English) */}
                <td className={`${styles.td} ${styles.narrationCol}`}>
                  <div className={styles.narrationTelugu}>
                    {s.narration?.text || s.scene_objective?.core_meaning || 'Narration not available'}
                  </div>
                  {s.narration?.text_en && (
                    <div className={styles.narrationEnglish}>
                      {s.narration.text_en}
                    </div>
                  )}
                </td>

                {/* Action: View Modal Button */}
                <td className={`${styles.td} ${styles.actionsCol}`} onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className={styles.viewBtn}
                    onClick={() => setSelectedScene(s)}
                    data-testid={`scene-view-btn-${s.scene_id}`}
                    title="View Full Scene Details"
                  >
                    <Eye size={13} />
                    View Details
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Validation Issues / Notes */}
      {(errors.length > 0 || warnings.length > 0) && (
        <div className={styles.issuesCard} data-testid="visual-planning-issues">
          {[...errors.map((m) => ({ m, error: true })), ...warnings.map((m) => ({ m, error: false }))].map((x, i) => (
            <div
              key={i}
              className={styles.issueItem}
              style={{
                color: x.error ? 'var(--status-failed, #f87171)' : 'var(--status-warning, #f59e0b)'
              }}
            >
              <AlertTriangle size={12} style={{ marginTop: 2, flexShrink: 0 }} />
              <span>{x.m}</span>
            </div>
          ))}
        </div>
      )}

      {/* Full Detail Modal Popup */}
      {selectedScene && (
        <VisualSceneModal
          scene={selectedScene}
          onClose={() => setSelectedScene(null)}
        />
      )}
    </div>
  );
};
