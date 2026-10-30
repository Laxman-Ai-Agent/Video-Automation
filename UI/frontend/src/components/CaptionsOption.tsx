import React from 'react';
import { MediaMix } from '../services/mediaMix';
import styles from './AiPicturesOption.module.css';

interface CaptionsOptionProps {
  value: MediaMix;
  onChange: (next: MediaMix) => void;
  disabled?: boolean;
}

/** Word-timed captions over the scenes, chosen once at upload (locked afterwards, like the AI-pictures and motion-kit choices). On by default. */
export const CaptionsOption: React.FC<CaptionsOptionProps> = ({ value, onChange, disabled }) => (
  <label className={styles.option} data-disabled={disabled ? 'true' : 'false'}>
    <input
      type="checkbox"
      className={styles.checkbox}
      checked={value.captions}
      disabled={disabled}
      data-testid="captions-option"
      onChange={(e) => onChange({ ...value, captions: e.target.checked })}
    />
    <div>
      <div className={styles.title}>Captions</div>
      <div className={styles.hint}>
        Word-timed captions in the language spoken: the word being said is highlighted, numbers and on-screen terms are stressed, and the first line is a large hook. On by default; cannot be changed after upload.
      </div>
    </div>
  </label>
);
