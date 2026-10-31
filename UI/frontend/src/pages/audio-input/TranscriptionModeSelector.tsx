import React, { useEffect, useState } from 'react';
import { Zap, Cpu, Check, HardDrive } from 'lucide-react';
import { fetchDriveStatus } from '../../services/api';
import styles from './TranscriptionModeSelector.module.css';

export interface TranscriptionModeSelectorProps {
  mode: 'colab' | 'local';
  onChange: (mode: 'colab' | 'local') => void;
  disabled?: boolean;
}

export const TranscriptionModeSelector: React.FC<TranscriptionModeSelectorProps> = ({
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
    <div className={styles.container} data-testid="transcription-mode-selector">
      <div className={styles.header}>
        <label className={styles.label}>
          <Zap size={14} color="var(--accent-cyan)" />
          <span>Transcription Engine <span style={{ color: 'var(--accent-red)' }}>*</span></span>
        </label>
        {driveConnected && (
          <span className={styles.statusPill} data-testid="drive-connected-pill">
            <span className={styles.statusDot} />
            <span>Google Drive Connected</span>
          </span>
        )}
      </div>

      <div className={styles.grid}>
        {/* OPTION 1: GOOGLE COLAB (DRIVE CLOUD GPU) - DEFAULT */}
        <div
          role="button"
          tabIndex={0}
          data-testid="transcription-mode-colab"
          onClick={() => !disabled && onChange('colab')}
          className={`${styles.card} ${mode === 'colab' ? styles.cardActive : styles.cardIdle}`}
        >
          <div className={`${styles.iconWrapper} ${mode === 'colab' ? styles.iconWrapperActive : styles.iconWrapperIdle}`}>
            <Zap size={18} />
          </div>

          <div className={styles.content}>
            <div className={styles.titleRow}>
              <span className={`${styles.title} ${mode === 'colab' ? styles.titleActive : ''}`}>
                Google Colab (Drive GPU)
              </span>
              <span className={`${styles.badge} ${styles.badgeColab}`}>
                Default • Fast GPU
              </span>
            </div>
            <p className={styles.description}>
              Auto-syncs narration with Google Drive (<code>AI_Video_Project/</code>). Uses Colab T4 GPU for ultra-fast Telugu Whisper v3. 0% PC load.
            </p>
          </div>

          {mode === 'colab' && (
            <span className={styles.checkBadge}>
              <Check size={10} strokeWidth={3} />
            </span>
          )}
        </div>

        {/* OPTION 2: LOCAL WHISPER (ON-DEVICE) */}
        <div
          role="button"
          tabIndex={0}
          data-testid="transcription-mode-local"
          onClick={() => !disabled && onChange('local')}
          className={`${styles.card} ${mode === 'local' ? styles.cardActive : styles.cardIdle}`}
        >
          <div className={`${styles.iconWrapper} ${mode === 'local' ? styles.iconWrapperActive : styles.iconWrapperIdle}`}>
            <Cpu size={18} />
          </div>

          <div className={styles.content}>
            <div className={styles.titleRow}>
              <span className={`${styles.title} ${mode === 'local' ? styles.titleActive : ''}`}>
                Local Whisper (On-Device)
              </span>
              <span className={`${styles.badge} ${styles.badgeLocal}`}>
                Local CPU/GPU
              </span>
            </div>
            <p className={styles.description}>
              Transcribes audio entirely on this machine. Suitable for offline usage or when Google Colab is not active.
            </p>
          </div>

          {mode === 'local' && (
            <span className={styles.checkBadge}>
              <Check size={10} strokeWidth={3} />
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
