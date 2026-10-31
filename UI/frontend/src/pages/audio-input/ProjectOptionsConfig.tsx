import React from 'react';
import { Tv, Check, Sliders } from 'lucide-react';
import { MediaMix } from '../../services/mediaMix';
import { AiPicturesOption } from '../../components/AiPicturesOption';
import { MotionKitOption } from '../../components/MotionKitOption';
import { CaptionsOption } from '../../components/CaptionsOption';
import styles from './ProjectOptionsConfig.module.css';

export interface ProjectOptionsConfigProps {
  aspect: '16:9' | '9:16';
  setAspect: (val: '16:9' | '9:16') => void;
  media: MediaMix;
  setMedia: (val: MediaMix) => void;
  reusableTemplates: boolean;
  setReusableTemplates: (val: boolean) => void;
  submitting: boolean;
}

export const ProjectOptionsConfig: React.FC<ProjectOptionsConfigProps> = ({
  aspect,
  setAspect,
  media,
  setMedia,
  reusableTemplates,
  setReusableTemplates,
  submitting
}) => {
  return (
    <div className={styles.container}>
      {/* Aspect Ratio Selection */}
      <div>
        <div className={styles.sectionHeader}>
          <label className={styles.label}>
            <Tv size={14} color="var(--accent-blue)" />
            <span>Video Aspect Ratio <span className={styles.requiredAsterisk}>*</span></span>
          </label>
          <span className={styles.headerHint}>
            Output Dimensions
          </span>
        </div>

        <div className={styles.aspectGrid}>
          {/* 16:9 Landscape Card */}
          <div
            onClick={() => setAspect('16:9')}
            role="button"
            tabIndex={0}
            data-testid="aspect-16-9-card"
            className={`${styles.aspectCard} ${aspect === '16:9' ? styles.aspectCardActive : styles.aspectCardIdle}`}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') setAspect('16:9');
            }}
          >
            <div
              className={`${styles.aspectPreview169} ${aspect === '16:9' ? styles.previewActive : styles.previewIdle}`}
            />
            <div className={styles.aspectInfo}>
              <div className={`${styles.aspectTitle} ${aspect === '16:9' ? styles.aspectTitleActive : ''}`}>
                16:9 Widescreen
              </div>
              <div className={styles.aspectSubtitle}>
                YouTube & Desktop (1920×1080)
              </div>
            </div>
            {aspect === '16:9' && (
              <span className={styles.checkCircle}>
                <Check size={11} strokeWidth={3} />
              </span>
            )}
          </div>

          {/* 9:16 Portrait Card */}
          <div
            onClick={() => setAspect('9:16')}
            role="button"
            tabIndex={0}
            data-testid="aspect-9-16-card"
            className={`${styles.aspectCard} ${aspect === '9:16' ? styles.aspectCardActive : styles.aspectCardIdle}`}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') setAspect('9:16');
            }}
          >
            <div
              className={`${styles.aspectPreview916} ${aspect === '9:16' ? styles.previewActive : styles.previewIdle}`}
            />
            <div className={styles.aspectInfo}>
              <div className={`${styles.aspectTitle} ${aspect === '9:16' ? styles.aspectTitleActive : ''}`}>
                9:16 Vertical
              </div>
              <div className={styles.aspectSubtitle}>
                Shorts & Reels (1080×1920)
              </div>
            </div>
            {aspect === '9:16' && (
              <span className={styles.checkCircle}>
                <Check size={11} strokeWidth={3} />
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Visual Engine Features */}
      <div className={styles.featuresSection}>
        <div className={styles.featuresHeader}>
          <span className={styles.featuresTitle}>
            <Sliders size={13} color="var(--accent-blue)" />
            Visual Engine Features
          </span>
          <span className={styles.featuresTag}>
            Kinetic Motion Mode
          </span>
        </div>

        <AiPicturesOption value={media} onChange={setMedia} disabled={submitting} />
        <MotionKitOption value={media} onChange={setMedia} disabled={submitting} />
        <CaptionsOption value={media} onChange={setMedia} disabled={submitting} />

        <label className={styles.reusableTemplatesCard}>
          <input
            type="checkbox"
            checked={reusableTemplates}
            onChange={(e) => setReusableTemplates(e.target.checked)}
            disabled={submitting}
            className={styles.reusableTemplatesCheckbox}
          />
          <div>
            <div className={styles.reusableTemplatesTitle}>
              Reusable Motion Templates Cache
            </div>
            <div className={styles.reusableTemplatesHint}>
              Reuses cached Remotion template ASTs for accelerated timeline build & render.
            </div>
          </div>
        </label>
      </div>
    </div>
  );
};
