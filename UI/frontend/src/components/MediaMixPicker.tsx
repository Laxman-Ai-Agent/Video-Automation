import React from 'react';
import { DEFAULT_MEDIA, FAMILIES, FAMILY_LABEL, MediaFamily, MediaMix, rebalance, total } from '../services/mediaMix';

const COLOR: Record<MediaFamily, string> = { motion: 'var(--accent-blue)', image: 'var(--accent-cyan)', video: '#a78bfa' };
const HINT: Record<MediaFamily, string> = {
  motion: 'Text, icons, graphics and diagrams drawn by code. Always part of every scene.',
  image: 'Real photographs where the narration shows something a camera can take.',
  video: 'Real clips where the movement itself is the point.'
};

interface MediaMixPickerProps {
  value: MediaMix;
  onChange: (next: MediaMix) => void;
  disabled?: boolean;
}

/** The three shares of the video (motion graphics, images, videos) and the AI-pictures switch. Chosen at upload; the server locks them. */
export const MediaMixPicker: React.FC<MediaMixPickerProps> = ({ value, onChange, disabled }) => (
  <div data-testid="media-mix-picker" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span style={{ fontSize: '11.5px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
        Media mix (share of the video)
      </span>
      <button
        type="button"
        data-testid="media-mix-reset"
        disabled={disabled}
        onClick={() => onChange({ ...DEFAULT_MEDIA, ai_images: value.ai_images })}
        style={{ fontSize: '10.5px', background: 'none', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer' }}
      >
        Reset to {DEFAULT_MEDIA.motion}/{DEFAULT_MEDIA.image}/{DEFAULT_MEDIA.video}
      </button>
    </div>

    <div style={{ display: 'flex', height: '8px', borderRadius: '4px', overflow: 'hidden', backgroundColor: 'var(--bg-card)' }} aria-hidden>
      {FAMILIES.map((f) => (
        <div key={f} style={{ width: `${value[f]}%`, backgroundColor: COLOR[f], transition: 'width 0.15s' }} />
      ))}
    </div>

    {FAMILIES.map((f) => (
      <label key={f} style={{ display: 'grid', gridTemplateColumns: '120px 1fr 64px', alignItems: 'center', gap: '10px' }} title={HINT[f]}>
        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
          <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, backgroundColor: COLOR[f], marginRight: 6 }} />
          {FAMILY_LABEL[f]}
        </span>
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={value[f]}
          disabled={disabled}
          data-testid={`media-mix-range-${f}`}
          onChange={(e) => onChange(rebalance(value, f, Number(e.target.value)))}
          style={{ accentColor: COLOR[f] }}
        />
        <span style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
          <input
            type="number"
            min={0}
            max={100}
            value={value[f]}
            disabled={disabled}
            data-testid={`media-mix-${f}`}
            onChange={(e) => onChange(rebalance(value, f, Number(e.target.value)))}
            style={{ width: '44px', padding: '2px 4px', fontSize: '12px', borderRadius: '4px', border: '1px solid var(--border-card)', backgroundColor: 'var(--bg-card)', color: 'var(--text-primary)' }}
          />
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>%</span>
        </span>
      </label>
    ))}

    <div data-testid="media-mix-total" style={{ fontSize: '10.5px', color: total(value) === 100 ? 'var(--text-muted)' : 'var(--status-failed, #f87171)' }}>
      Total {total(value)}% — the shares are a target for the whole video: the planner picks the scenes that suit each one, and the plan shows what it reached. They cannot be changed after the upload.
    </div>

    <label style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', cursor: disabled ? 'default' : 'pointer' }}>
      <input
        type="checkbox"
        checked={value.ai_images}
        disabled={disabled}
        data-testid="media-mix-ai"
        onChange={(e) => onChange({ ...value, ai_images: e.target.checked })}
        style={{ marginTop: '2px', accentColor: 'var(--accent-blue)' }}
      />
      <div>
        <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>AI-made pictures</div>
        <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
          Writes a ready image-generator prompt for every image. Used when an image generator is connected; otherwise the real-photo search runs, and if that finds nothing the scene draws its motion graphic.
        </div>
      </div>
    </label>
  </div>
);
