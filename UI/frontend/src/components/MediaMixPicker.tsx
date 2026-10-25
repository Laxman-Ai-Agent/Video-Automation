import React from 'react';
import { Sparkles, Image as ImageIcon, Film } from 'lucide-react';
import { MediaMix } from '../services/mediaMix';

interface MediaMixPickerProps {
  value: MediaMix;
  onChange: (next: MediaMix) => void;
  disabled?: boolean;
}

/** Modern Visual Asset Options: 100% Motion Design Canvas with optional Image and Video card layers. */
export const MediaMixPicker: React.FC<MediaMixPickerProps> = ({ value, onChange, disabled }) => {
  const imagesEnabled = value.image > 0;
  const videosEnabled = value.video > 0;

  const toggleImages = (checked: boolean) => {
    const imgShare = checked ? 30 : 0;
    const vidShare = videosEnabled ? 10 : 0;
    const motShare = 100 - imgShare - vidShare;
    onChange({
      ...value,
      image: imgShare,
      video: vidShare,
      motion: motShare,
    });
  };

  const toggleVideos = (checked: boolean) => {
    const imgShare = imagesEnabled ? 30 : 0;
    const vidShare = checked ? 10 : 0;
    const motShare = 100 - imgShare - vidShare;
    onChange({
      ...value,
      image: imgShare,
      video: vidShare,
      motion: motShare,
    });
  };

  return (
    <div data-testid="media-mix-picker" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {/* 100% Motion Canvas Indicator */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 12px',
        borderRadius: '6px',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        border: '1px solid rgba(59, 130, 246, 0.25)'
      }}>
        <Sparkles size={14} color="#60A5FA" />
        <span style={{ fontSize: '11.5px', fontWeight: 600, color: '#93C5FD' }}>
          100% Motion Canvas: Every scene is driven by dynamic typography & layout animations.
        </span>
      </div>

      {/* Two Essential Visual Layer Controls */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '8px' }}>
        {/* Images Toggle */}
        <label style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '10px',
          padding: '10px 12px',
          borderRadius: '6px',
          backgroundColor: imagesEnabled ? 'rgba(6, 182, 212, 0.08)' : 'var(--bg-elevated)',
          border: `1px solid ${imagesEnabled ? 'rgba(6, 182, 212, 0.35)' : 'var(--border-subtle)'}`,
          cursor: disabled ? 'default' : 'pointer',
          transition: 'all 0.15s ease'
        }}>
          <input
            type="checkbox"
            checked={imagesEnabled}
            disabled={disabled}
            data-testid="media-toggle-images"
            onChange={(e) => toggleImages(e.target.checked)}
            style={{ marginTop: '3px', accentColor: 'var(--accent-cyan)' }}
          />
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
              <ImageIcon size={13} color="var(--accent-cyan)" />
              <span>Images (Photo Cards & Cutouts)</span>
              <span style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '4px', backgroundColor: imagesEnabled ? 'rgba(6, 182, 212, 0.2)' : 'var(--bg-card)', color: imagesEnabled ? '#22D3EE' : 'var(--text-muted)' }}>
                {imagesEnabled ? 'Active' : 'Off'}
              </span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px', lineHeight: 1.4 }}>
              When objects, people, or entities are mentioned in the narration, animated photo cards pop up within the motion scene.
            </div>
          </div>
        </label>

        {/* Videos Toggle */}
        <label style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '10px',
          padding: '10px 12px',
          borderRadius: '6px',
          backgroundColor: videosEnabled ? 'rgba(167, 139, 250, 0.08)' : 'var(--bg-elevated)',
          border: `1px solid ${videosEnabled ? 'rgba(167, 139, 250, 0.35)' : 'var(--border-subtle)'}`,
          cursor: disabled ? 'default' : 'pointer',
          transition: 'all 0.15s ease'
        }}>
          <input
            type="checkbox"
            checked={videosEnabled}
            disabled={disabled}
            data-testid="media-toggle-videos"
            onChange={(e) => toggleVideos(e.target.checked)}
            style={{ marginTop: '3px', accentColor: '#A78BFA' }}
          />
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
              <Film size={13} color="#A78BFA" />
              <span>Videos (Cinematic B-Roll Mockups)</span>
              <span style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '4px', backgroundColor: videosEnabled ? 'rgba(167, 139, 250, 0.2)' : 'var(--bg-card)', color: videosEnabled ? '#C4B5FD' : 'var(--text-muted)' }}>
                {videosEnabled ? 'Active' : 'Off'}
              </span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px', lineHeight: 1.4 }}>
              Framed b-roll clips appear inside animated motion mockups during action or cinematic scenes.
            </div>
          </div>
        </label>
      </div>

      {/* AI Images option */}
      {imagesEnabled && (
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', cursor: disabled ? 'default' : 'pointer', marginTop: '2px' }}>
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
              Prepares AI image generation prompts for every visual concept. If an image is missing, the prompt is shown so you can view it or manually upload your own asset.
            </div>
          </div>
        </label>
      )}
    </div>
  );
};
