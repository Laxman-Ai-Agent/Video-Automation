import React from 'react';
import { Layers, Image as ImageIcon } from 'lucide-react';
import { API_BASE } from '../../services/api';

export interface MediaPreviewProps {
  item: any;
}

export const MediaPreview: React.FC<MediaPreviewProps> = ({ item }) => {
  const a = item.asset;
  const box: React.CSSProperties = {
    width: '100%',
    aspectRatio: '16 / 9',
    borderRadius: '6px',
    backgroundColor: 'var(--bg-card)',
    objectFit: 'cover',
    display: 'block',
  };

  if (item.kind === 'icon') {
    return (
      <div
        style={{
          ...box,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          background: 'linear-gradient(135deg, rgba(59,130,246,0.12) 0%, rgba(147,51,234,0.12) 100%)',
          border: '1px dashed var(--border-subtle)',
        }}
      >
        <div
          style={{
            padding: '12px',
            borderRadius: '50%',
            backgroundColor: 'rgba(255,255,255,0.08)',
            border: '1px solid rgba(255,255,255,0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Layers size={28} color="#60A5FA" />
        </div>
        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
          Icon: {item.icon_name || item.query || 'Default'}
        </span>
      </div>
    );
  }

  if (a && a.kind === 'video') {
    return (
      <video
        data-testid="asset-video"
        src={`${API_BASE}${a.url}`}
        controls
        muted
        preload="metadata"
        style={box}
      />
    );
  }
  if (a) {
    return (
      <img
        data-testid="asset-image"
        src={`${API_BASE}${a.url}`}
        alt={a.title || item.query}
        style={box}
      />
    );
  }

  return (
    <div
      style={{
        ...box,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: '16px',
        fontSize: '11.5px',
        color: 'var(--text-muted)',
        gap: '8px',
        background: 'linear-gradient(135deg, rgba(245,158,11,0.06) 0%, rgba(59,130,246,0.06) 100%)',
        border: '1px dashed rgba(245, 158, 11, 0.3)',
      }}
    >
      <ImageIcon size={26} style={{ color: '#F59E0B', opacity: 0.8 }} />
      <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
        No external file collected
      </span>
      <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', maxWidth: '240px' }}>
        Auto-fallback: Remotion will render with 100% Motion Canvas graphics & kinetic typography.
      </span>
    </div>
  );
};
