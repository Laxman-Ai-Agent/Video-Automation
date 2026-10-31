import React, { useEffect, useState } from 'react';
import { Video, Zap, Check, Globe } from 'lucide-react';
import { fetchDriveStatus } from '../../services/api';
import styles from './VideoModeSelector.module.css';

export interface VideoModeSelectorProps {
  mode: 'colab' | 'normal';
  onChange: (mode: 'colab' | 'normal') => void;
  disabled?: boolean;
}

export const VideoModeSelector: React.FC<VideoModeSelectorProps> = ({
  mode,
  onChange,
  disabled = false,
}) => {
  const [driveConnected, setDriveConnected] = useState<boolean>(true);

  useEffect(() => {
    let mounted = true;
    fetchDriveStatus().then((res) => {
      if (mounted) {
        setDriveConnected(res.connected);
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className={styles.container} data-testid="video-mode-selector">
      <div className={styles.header}>
        <label className={styles.label}>
          <Video size={14} color="var(--accent-blue)" />
          <span>Scene Video Clip Engine <span style={{ color: 'var(--accent-red)' }}>*</span></span>
        </label>
        {driveConnected && (
          <span className={styles.statusPill} data-testid="drive-video-sync-pill">
            <span className={styles.statusDot} />
            <span>Drive Videos Auto-Sync</span>
          </span>
        )}
      </div>

      <div className={styles.grid}>
        {/* OPTION 1: GOOGLE COLAB (LIGHTNING AI VIDEO) - DEFAULT */}
        <div
          role="button"
          tabIndex={0}
          data-testid="video-mode-colab"
          className={`${styles.card} ${mode === 'colab' ? styles.cardActive : styles.cardIdle}`}
          onClick={() => !disabled && onChange('colab')}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === ' ') && !disabled) {
              onChange('colab');
            }
          }}
        >
          <div
            className={`${styles.iconWrapper} ${
              mode === 'colab' ? styles.iconWrapperActive : styles.iconWrapperIdle
            }`}
          >
            <Zap size={16} />
          </div>
          <div className={styles.content}>
            <div className={styles.titleRow}>
              <span
                className={`${styles.title} ${
                  mode === 'colab' ? styles.titleActive : ''
                }`}
              >
                Google Colab (Lightning AI Video)
              </span>
              <span className={`${styles.badge} ${styles.badgeColab}`}>Default</span>
            </div>
            <p className={styles.description}>
              Generates 15s ultra-fast AI video clips using ByteDance AnimateDiff-Lightning and auto-syncs via Drive.
            </p>
          </div>
          {mode === 'colab' && (
            <span className={styles.checkBadge}>
              <Check size={10} strokeWidth={3} />
            </span>
          )}
        </div>

        {/* OPTION 2: NORMAL / STOCK VIDEO CLIPS */}
        <div
          role="button"
          tabIndex={0}
          data-testid="video-mode-normal"
          className={`${styles.card} ${mode === 'normal' ? styles.cardActive : styles.cardIdle}`}
          onClick={() => !disabled && onChange('normal')}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === ' ') && !disabled) {
              onChange('normal');
            }
          }}
        >
          <div
            className={`${styles.iconWrapper} ${
              mode === 'normal' ? styles.iconWrapperActive : styles.iconWrapperIdle
            }`}
          >
            <Globe size={16} />
          </div>
          <div className={styles.content}>
            <div className={styles.titleRow}>
              <span
                className={`${styles.title} ${
                  mode === 'normal' ? styles.titleActive : ''
                }`}
              >
                Normal / Stock Video Clips
              </span>
              <span className={`${styles.badge} ${styles.badgeNormal}`}>Standard</span>
            </div>
            <p className={styles.description}>
              Fetches curated stock video clips (Pexels / Pixabay) and standard motion fallbacks.
            </p>
          </div>
          {mode === 'normal' && (
            <span className={styles.checkBadge}>
              <Check size={10} strokeWidth={3} />
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
