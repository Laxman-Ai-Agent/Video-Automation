import React from 'react';
import { MediaMix } from '../services/mediaMix';
import styles from './AiPicturesOption.module.css';

interface MotionKitOptionProps {
  value: MediaMix;
  onChange: (next: MediaMix) => void;
  disabled?: boolean;
}

/** The optional motion kit, chosen once at upload (locked afterwards, like the AI-pictures choice). Off = every scene is written from scratch. */
export const MotionKitOption: React.FC<MotionKitOptionProps> = ({ value, onChange, disabled }) => (
  <label className={styles.option} data-disabled={disabled ? 'true' : 'false'}>
    <input
      type="checkbox"
      className={styles.checkbox}
      checked={value.motion_kit}
      disabled={disabled}
      data-testid="motion-kit-option"
      onChange={(e) => onChange({ ...value, motion_kit: e.target.checked })}
    />
    <div>
      <div className={styles.title}>Motion kit</div>
      <div className={styles.hint}>
        Scenes may use a vetted kit (camera moves, word-by-word kinetic text, art directions) in addition to code written from scratch. Off by default; cannot be changed after upload.
      </div>
    </div>
  </label>
);
