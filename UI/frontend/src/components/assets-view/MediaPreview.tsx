import React from 'react';
import { Layers, Image as ImageIcon } from 'lucide-react';
import { API_BASE } from '../../services/api';
import styles from './MediaPreview.module.css';

export interface MediaPreviewProps {
  item: any;
  /** The card's small preview: a clip shows no player controls there (the click opens the detail view, which has them) */
  compact?: boolean;
}

export const MediaPreview: React.FC<MediaPreviewProps> = ({ item, compact = false }) => {
  const a = item.asset;

  if (item.kind === 'icon') {
    return (
      <div className={`${styles.box} ${styles.placeholder} ${styles.iconBox}`}>
        <div className={styles.iconRing}>
          <Layers size={28} color="#60A5FA" />
        </div>
        <span className={styles.iconLabel}>Icon: {item.icon_name || item.query || 'Default'}</span>
      </div>
    );
  }

  if (a && a.kind === 'video') {
    return (
      <video
        data-testid="asset-video"
        className={`${styles.box} ${compact ? '' : styles.contain}`}
        src={`${API_BASE}${a.url}`}
        controls={!compact}
        muted
        preload="metadata"
      />
    );
  }
  if (a) {
    return (
      <img
        data-testid="asset-image"
        className={`${styles.box} ${compact ? '' : styles.contain}`}
        src={`${API_BASE}${a.url}`}
        alt={a.title || item.query}
      />
    );
  }

  return (
    <div className={`${styles.box} ${styles.placeholder} ${styles.missing}`}>
      <ImageIcon size={26} className={styles.missingIcon} />
      <span className={styles.missingTitle}>No external file collected</span>
      <span className={styles.missingText}>Auto-fallback: Remotion will render with 100% Motion Canvas graphics & kinetic typography.</span>
    </div>
  );
};
