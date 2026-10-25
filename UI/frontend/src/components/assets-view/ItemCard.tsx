import React, { useState, useRef } from 'react';
import {
  Film,
  Layers,
  Image as ImageIcon,
  Sparkles,
  CheckCircle2,
  Copy,
  Loader2,
  Upload,
  ExternalLink,
  AlertTriangle
} from 'lucide-react';
import { uploadAsset } from '../../services/api';
import { MediaPreview } from './MediaPreview';
import { VideoTrimmer } from './VideoTrimmer';
import { IconEditor } from './IconEditor';

const card: React.CSSProperties = {
  backgroundColor: 'var(--bg-elevated)',
  border: '1px solid var(--border-card)',
  borderRadius: '8px',
  padding: '14px 18px',
};

const muted: React.CSSProperties = { fontSize: '11px', color: 'var(--text-muted)' };

const STATUS_COLOR: Record<string, string> = {
  collected: 'var(--status-completed, #34d399)',
  fallback: 'var(--status-warning, #f59e0b)',
  pending: 'var(--text-muted)',
};

export interface ItemCardProps {
  item: any;
  projectId: string;
  onAssetUpdated: () => void;
}

export const ItemCard: React.FC<ItemCardProps> = ({
  item,
  projectId,
  onAssetUpdated,
}) => {
  const a = item.asset;
  const isVideo = item.kind === 'video' || item.media_type === 'video';
  const isIcon = item.kind === 'icon' || item.type === 'icon';

  const [copied, setCopied] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const copyPrompt = () => {
    try {
      navigator.clipboard.writeText(item.ai_prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be unavailable */
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !projectId) return;

    setUploading(true);
    setUploadError(null);
    try {
      await uploadAsset(projectId, item.requirement_id, item.scene_id || 1, file);
      onAssetUpdated();
    } catch (err: any) {
      setUploadError(err?.message || 'Failed to upload asset');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div style={{ ...card, display: 'grid', gap: '10px' }} data-testid={`asset-item-${item.requirement_id}`}>
      {/* Header with Kind & Status */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            fontWeight: 700,
            color: 'var(--text-primary)',
          }}
        >
          {isVideo ? (
            <Film size={13} color="#60A5FA" />
          ) : isIcon ? (
            <Layers size={13} color="#A78BFA" />
          ) : (
            <ImageIcon size={13} color="#34D399" />
          )}
          Scene {item.scene_id} · {isVideo ? 'Video Clip' : isIcon ? 'Icon' : 'Image Card'}
        </span>

        <span
          data-testid={`asset-status-${item.requirement_id}`}
          style={{
            fontSize: '11px',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: '12px',
            backgroundColor: item.status === 'collected' ? 'rgba(52, 211, 153, 0.15)' : 'rgba(245, 158, 11, 0.15)',
            color: STATUS_COLOR[item.status],
            border: `1px solid ${STATUS_COLOR[item.status]}33`,
          }}
        >
          {item.status === 'collected'
            ? a?.selected_by === 'manual_upload'
              ? 'custom upload'
              : 'collected'
            : 'auto-fallback to motion'}
        </span>
      </div>

      {/* Media Preview Box */}
      <MediaPreview item={item} />

      {/* Subject Description */}
      <div style={{ fontSize: '12px', color: 'var(--text-primary)' }}>
        <strong>Subject:</strong> {item.query || item.description || 'Scene Element'}
        {item.alt_queries && item.alt_queries.length > 0 && (
          <span style={muted}> (also: {item.alt_queries.join(', ')})</span>
        )}
      </div>

      {/* Suggested Prompt for Image Generator */}
      {item.ai_prompt && (
        <div
          style={{
            backgroundColor: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid rgba(59, 130, 246, 0.25)',
            borderRadius: '6px',
            padding: '8px 10px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span
              style={{
                fontSize: '10.5px',
                fontWeight: 700,
                color: '#60A5FA',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <Sparkles size={11} /> AI Prompt:
            </span>
            <button
              type="button"
              onClick={copyPrompt}
              title="Copy prompt for Midjourney / DALL-E / Gemini"
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: copied ? '#34D399' : 'var(--accent-blue)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px',
                fontSize: '11px',
                fontWeight: 600,
              }}
            >
              {copied ? <CheckCircle2 size={12} /> : <Copy size={12} />}
              <span>{copied ? 'Copied!' : 'Copy Prompt'}</span>
            </button>
          </div>
          <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
            {item.ai_prompt}
          </div>
        </div>
      )}

      {/* Video Trimmer (For Videos) */}
      {isVideo && a && (
        <VideoTrimmer item={item} projectId={projectId} onSaved={onAssetUpdated} />
      )}

      {/* Icon Editor (For Icons) */}
      {isIcon && (
        <IconEditor item={item} projectId={projectId} onSaved={onAssetUpdated} />
      )}

      {/* Upload & Replace Controls */}
      {!isIcon && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: '2px' }}>
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            accept={isVideo ? 'video/mp4,video/quicktime' : 'image/png,image/jpeg,image/webp'}
            onChange={handleFileChange}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              fontSize: '11.5px',
              fontWeight: 600,
              cursor: uploading ? 'not-allowed' : 'pointer',
              backgroundColor: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'background-color 0.15s ease',
            }}
          >
            {uploading ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
            <span>
              {uploading
                ? 'Uploading…'
                : a
                ? `Replace ${isVideo ? 'Video' : 'Image'}`
                : `Upload Custom ${isVideo ? 'Video' : 'Image'}`}
            </span>
          </button>
          {uploadError && (
            <span style={{ fontSize: '11px', color: 'var(--status-failed, #f87171)' }}>
              {uploadError}
            </span>
          )}
        </div>
      )}

      {/* File details if collected */}
      {a && (
        <div
          style={{
            ...muted,
            display: 'grid',
            gap: '2px',
            borderTop: '1px solid var(--border-card)',
            paddingTop: '6px',
          }}
        >
          <div>
            {a.title || 'Custom File'} · {a.author || 'User'} ·{' '}
            <strong>{a.license?.name || 'Personal'}</strong>
          </div>
          {a.source_url && (
            <a
              href={a.source_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: 'var(--accent-blue)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              source <ExternalLink size={11} />
            </a>
          )}
        </div>
      )}

      {/* Auto-Fallback Reassurance */}
      {item.status === 'fallback' && (
        <div
          style={{
            fontSize: '11px',
            backgroundColor: 'rgba(245, 158, 11, 0.08)',
            border: '1px solid rgba(245, 158, 11, 0.25)',
            borderRadius: '6px',
            padding: '8px 10px',
            color: 'var(--status-warning, #f59e0b)',
            display: 'flex',
            gap: '6px',
            alignItems: 'flex-start',
          }}
        >
          <AlertTriangle size={13} style={{ flexShrink: 0, marginTop: '1px' }} />
          <span>
            <strong>Auto-Fallback Active:</strong> No image file is required here. Remotion will automatically generate and render kinetic motion graphics so your video never has an empty slot.
          </span>
        </div>
      )}
    </div>
  );
};
