import React, { useEffect, useState } from 'react';
import { Image as ImageIcon, Sparkles, Check, Globe } from 'lucide-react';
import { fetchDriveStatus } from '../../services/api';
import styles from './ImageModeSelector.module.css';

export interface ImageModeSelectorProps {
  mode: 'colab' | 'normal';
  onChange: (mode: 'colab' | 'normal') => void;
  disabled?: boolean;
}

export const ImageModeSelector: React.FC<ImageModeSelectorProps> = ({
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
    <div className={styles.container} data-testid="image-mode-selector">
      <div className={styles.header}>
        <label className={styles.label}>
          <ImageIcon size={14} color="var(--accent-blue)" />
          <span>Scene Image Generation Engine <span style={{ color: 'var(--accent-red)' }}>*</span></span>
        </label>
        {driveConnected && (
          <span className={styles.statusPill} data-testid="drive-image-sync-pill">
            <span className={styles.statusDot} />
            <span>Drive Images Auto-Sync</span>
          </span>
        )}
      </div>

      <div className={styles.grid}>
        {/* OPTION 1: GOOGLE COLAB (DRIVE ULTRA GPU) - DEFAULT */}
        <div
          role="button"
          tabIndex={0}
          data-testid="image-mode-colab"
          onClick={() => !disabled && onChange('colab')}
          className={`${styles.card} ${mode === 'colab' ? styles.cardActive : styles.cardIdle}`}
        >
          <div className={`${styles.iconWrapper} ${mode === 'colab' ? styles.iconWrapperActive : styles.iconWrapperIdle}`}>
            <Sparkles size={18} />
          </div>

          <div className={styles.content}>
            <div className={styles.titleRow}>
              <span className={`${styles.title} ${mode === 'colab' ? styles.titleActive : ''}`}>
                Google Colab (Ultra GPU)
              </span>
              <span className={`${styles.badge} ${styles.badgeColab}`}>
                Default • Photorealistic
              </span>
            </div>
            <p className={styles.description}>
              Uses Colab T4 GPU (RealVisXL / SDXL) for uncompressed 1080p DSLR cinema-quality scene photos via Google Drive (<code>AI_Video_Project/images/</code>).
            </p>
          </div>

          {mode === 'colab' && (
            <span className={styles.checkBadge}>
              <Check size={10} strokeWidth={3} />
            </span>
          )}
        </div>

        {/* OPTION 2: NORMAL / STANDARD ENGINE */}
        <div
          role="button"
          tabIndex={0}
          data-testid="image-mode-normal"
          onClick={() => !disabled && onChange('normal')}
          className={`${styles.card} ${mode === 'normal' ? styles.cardActive : styles.cardIdle}`}
        >
          <div className={`${styles.iconWrapper} ${mode === 'normal' ? styles.iconWrapperActive : styles.iconWrapperIdle}`}>
            <Globe size={18} />
          </div>

          <div className={styles.content}>
            <div className={styles.titleRow}>
              <span className={`${styles.title} ${mode === 'normal' ? styles.titleActive : ''}`}>
                Normal / Standard Engine
              </span>
              <span className={`${styles.badge} ${styles.badgeNormal}`}>
                Web API / Stock
              </span>
            </div>
            <p className={styles.description}>
              Standard web API / stock photography. Suitable when Google Colab is offline or for quick drafts without GPU generation.
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
