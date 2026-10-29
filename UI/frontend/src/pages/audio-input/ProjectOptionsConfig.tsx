import React from 'react';
import { Tv, Check, Sliders } from 'lucide-react';
import { MediaMix } from '../../services/mediaMix';
import { AiPicturesOption } from '../../components/AiPicturesOption';
import { MotionKitOption } from '../../components/MotionKitOption';

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
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: 'var(--bg-elevated)',
      border: '1px solid var(--border-card)',
      borderRadius: '6px',
      padding: '14px 16px',
      gap: '12px'
    }}>
      {/* Aspect Ratio Selection */}
      <div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '8px'
        }}>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12.5px',
            fontWeight: 600,
            color: 'var(--text-primary)',
            margin: 0
          }}>
            <Tv size={14} color="var(--accent-blue)" />
            <span>Video Aspect Ratio <span style={{ color: 'var(--accent-red)' }}>*</span></span>
          </label>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Output Dimensions
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          {/* 16:9 Landscape Card */}
          <div
            onClick={() => setAspect('16:9')}
            role="button"
            tabIndex={0}
            style={{
              padding: '10px 12px',
              borderRadius: '5px',
              border: `1.5px solid ${aspect === '16:9' ? 'var(--accent-blue)' : 'var(--border-card)'}`,
              backgroundColor: aspect === '16:9' ? 'var(--status-running-bg)' : 'var(--bg-card)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              transition: 'all 0.15s ease',
              boxShadow: aspect === '16:9' ? '0 0 10px rgba(24, 144, 255, 0.15)' : 'none',
              position: 'relative'
            }}
          >
            <div style={{
              width: '28px',
              height: '18px',
              border: `2px solid ${aspect === '16:9' ? 'var(--accent-blue)' : 'var(--text-muted)'}`,
              borderRadius: '2px',
              backgroundColor: aspect === '16:9' ? 'rgba(24, 144, 255, 0.25)' : 'transparent',
              flexShrink: 0
            }} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ 
                fontSize: '12.5px', 
                fontWeight: 700, 
                color: aspect === '16:9' ? 'var(--accent-blue)' : 'var(--text-primary)' 
              }}>
                16:9 Widescreen
              </div>
              <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                YouTube & Desktop (1920×1080)
              </div>
            </div>
            {aspect === '16:9' && (
              <span style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                backgroundColor: 'var(--accent-blue)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#FFFFFF'
              }}>
                <Check size={10} strokeWidth={3} />
              </span>
            )}
          </div>

          {/* 9:16 Portrait Card */}
          <div
            onClick={() => setAspect('9:16')}
            role="button"
            tabIndex={0}
            style={{
              padding: '10px 12px',
              borderRadius: '5px',
              border: `1.5px solid ${aspect === '9:16' ? 'var(--accent-blue)' : 'var(--border-card)'}`,
              backgroundColor: aspect === '9:16' ? 'var(--status-running-bg)' : 'var(--bg-card)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              transition: 'all 0.15s ease',
              boxShadow: aspect === '9:16' ? '0 0 10px rgba(24, 144, 255, 0.15)' : 'none',
              position: 'relative'
            }}
          >
            <div style={{
              width: '18px',
              height: '26px',
              border: `2px solid ${aspect === '9:16' ? 'var(--accent-blue)' : 'var(--text-muted)'}`,
              borderRadius: '2px',
              backgroundColor: aspect === '9:16' ? 'rgba(24, 144, 255, 0.25)' : 'transparent',
              flexShrink: 0
            }} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ 
                fontSize: '12.5px', 
                fontWeight: 700, 
                color: aspect === '9:16' ? 'var(--accent-blue)' : 'var(--text-primary)' 
              }}>
                9:16 Vertical
              </div>
              <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                Shorts & Reels (1080×1920)
              </div>
            </div>
            {aspect === '9:16' && (
              <span style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                backgroundColor: 'var(--accent-blue)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#FFFFFF'
              }}>
                <Check size={10} strokeWidth={3} />
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Visual Engine Options */}
      <div style={{
        borderTop: '1px solid var(--border-subtle)',
        paddingTop: '10px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ 
            fontSize: '11.5px', 
            fontWeight: 700, 
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.4px',
            display: 'flex',
            alignItems: 'center',
            gap: '5px'
          }}>
            <Sliders size={12} color="var(--accent-blue)" />
            Visual Engine Features
          </span>
          <span style={{ fontSize: '10.5px', color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)' }}>
            Motion-Only Mode
          </span>
        </div>

        <AiPicturesOption value={media} onChange={setMedia} disabled={submitting} />
        <MotionKitOption value={media} onChange={setMedia} disabled={submitting} />

        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '6px' }}>
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={reusableTemplates}
              onChange={(e) => setReusableTemplates(e.target.checked)}
              style={{ marginTop: '2px', accentColor: 'var(--accent-blue)' }}
            />
            <div>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                Reusable Motion Templates Cache
              </div>
              <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                Reuses cached Remotion template ASTs for accelerated timeline build & render.
              </div>
            </div>
          </label>
        </div>
      </div>
    </div>
  );
};
