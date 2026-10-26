import React from 'react';
import { MediaMix } from '../services/mediaMix';
import styles from './AiPicturesOption.module.css';

interface AiPicturesOptionProps {
  value: MediaMix;
  onChange: (next: MediaMix) => void;
  disabled?: boolean;
}

/** The one media choice at upload: AI-made pictures yes / no. Every video is 100% motion graphics; real photos and clips are drawn inside it in any amount. */
export const AiPicturesOption: React.FC<AiPicturesOptionProps> = ({ value, onChange, disabled }) => (
  <div data-testid="media-mix-picker">
    <div className={styles.note}>
      100% motion graphics. Real photos and video clips are placed inside the animated scenes wherever the narration needs them, in any amount.
    </div>
    <label className={styles.option} data-disabled={disabled ? 'true' : 'false'}>
      <input
        type="checkbox"
        className={styles.checkbox}
        checked={value.ai_images}
        disabled={disabled}
        data-testid="media-mix-ai"
        onChange={(e) => onChange({ ...value, ai_images: e.target.checked })}
      />
      <div>
        <div className={styles.title}>AI-made pictures</div>
        <div className={styles.hint}>
          Prepares AI image generation prompts for every picture. If an image is missing, the prompt is shown so you can view it or manually upload your own asset.
        </div>
      </div>
    </label>
  </div>
);
