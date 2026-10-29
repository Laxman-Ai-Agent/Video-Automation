import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Copy, ExternalLink, Film, Image as ImageIcon, Loader2, Sparkles, Upload, X } from 'lucide-react';
import { uploadAsset } from '../../services/api';
import { MediaPreview } from './MediaPreview';
import { VideoTrimmer } from './VideoTrimmer';
import styles from './AssetDetailModal.module.css';

export interface AssetDetailModalProps {
  item: any;
  projectId: string;
  onClose: () => void;
  /** a file was uploaded or the trim was saved: the page loads its data again and passes the new item */
  onAssetUpdated: () => void;
}

/** What opens when a collected (or missing) picture or clip is clicked: the file, its prompt to make or find another elsewhere, and the upload that replaces it by hand. */
export const AssetDetailModal: React.FC<AssetDetailModalProps> = ({ item, projectId, onClose, onAssetUpdated }) => {
  const a = item.asset;
  const isVideo = item.kind === 'video' || item.media_type === 'video';
  const what = isVideo ? 'video' : 'image';

  const [copied, setCopied] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // capture phase + stopPropagation: Escape closes only this view, not the stage page behind it (which listens for Escape too)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [onClose]);

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(item.ai_prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* the clipboard may be unavailable: the prompt is shown and can be selected */
    }
  };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !projectId) return;
    setUploading(true);
    setUploadError(null);
    setUploaded(null);
    try {
      await uploadAsset(projectId, item.requirement_id, item.scene_id || 1, file);
      setUploaded(file.name);
      onAssetUpdated();
    } catch (err: any) {
      setUploadError(err?.message || 'Failed to upload the file');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose} data-testid={`asset-modal-${item.requirement_id}`}>
      <div className={styles.modal} role="dialog" aria-modal="true" aria-label={`Scene ${item.scene_id} ${what}`} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title}>
            {isVideo ? <Film size={14} color="#60A5FA" /> : <ImageIcon size={14} color="#34D399" />}
            Scene {item.scene_id} · {isVideo ? 'Video Clip' : 'Image'}
            <span className={styles.status} data-status={item.status}>
              {item.status === 'collected' ? (a?.selected_by === 'manual_upload' ? 'custom upload' : 'collected') : 'auto-fallback to motion'}
            </span>
          </span>
          <button type="button" className={styles.close} onClick={onClose} aria-label="Close" data-testid="asset-modal-close">
            <X size={18} />
          </button>
        </div>

        <div className={styles.body}>
          <MediaPreview item={item} />

          <div className={styles.side}>
            <div className={styles.section}>
              <span className={styles.label}>Subject</span>
              <span className={styles.subject}>
                {item.query || item.description || 'Scene element'}
                {item.alt_queries?.length > 0 && <span className={styles.muted}> (also: {item.alt_queries.join(', ')})</span>}
              </span>
            </div>

            {item.ai_prompt && (
              <div className={styles.promptBox} data-testid="asset-modal-prompt">
                <div className={styles.promptHead}>
                  <span className={styles.promptTitle}>
                    <Sparkles size={11} /> {isVideo ? 'Prompt for a video generator (or words to search stock footage)' : 'AI prompt (Midjourney / DALL-E / Gemini)'}
                  </span>
                  <button type="button" className={styles.copy} data-copied={copied} onClick={copyPrompt} data-testid="asset-modal-copy">
                    {copied ? <CheckCircle2 size={12} /> : <Copy size={12} />}
                    <span>{copied ? 'Copied!' : 'Copy prompt'}</span>
                  </button>
                </div>
                <div className={styles.promptText}>{item.ai_prompt}</div>
              </div>
            )}

            <div className={styles.uploadBox}>
              <span className={styles.label}>{a ? `Not happy with this ${what}?` : `Add your own ${what}`}</span>
              <span className={styles.muted}>
                Make or find one with the prompt above, then upload it here. It {a ? 'replaces this one' : 'is used for this slot'} in Scene {item.scene_id}.
              </span>
              <input
                ref={fileInputRef}
                type="file"
                className={styles.hidden}
                accept={isVideo ? 'video/mp4,video/quicktime' : 'image/png,image/jpeg,image/webp'}
                onChange={onFile}
                data-testid="asset-modal-file"
              />
              <button type="button" className={styles.upload} disabled={uploading} onClick={() => fileInputRef.current?.click()} data-testid="asset-modal-upload">
                {uploading ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
                <span>{uploading ? 'Uploading…' : a ? `Replace ${what}` : `Upload ${what}`}</span>
              </button>
              {uploadError && <span className={styles.error}>{uploadError}</span>}
              {uploaded && <span className={styles.done}>Uploaded: {uploaded}</span>}
            </div>

            {isVideo && a && <VideoTrimmer item={item} projectId={projectId} onSaved={onAssetUpdated} />}

            {a && (
              <div className={styles.fileInfo}>
                <div>
                  {a.title || 'Custom file'} · {a.author || 'User'} · <strong>{a.license?.name || 'Personal'}</strong>
                </div>
                {a.source_url && !String(a.source_url).startsWith('user-upload://') && (
                  <a className={styles.source} href={a.source_url} target="_blank" rel="noopener noreferrer">
                    source <ExternalLink size={11} />
                  </a>
                )}
              </div>
            )}

            {item.status === 'fallback' && (
              <div className={styles.fallback}>
                <AlertTriangle size={13} />
                <span>
                  <strong>No file here:</strong> {item.reason || 'nothing suitable was found'}. Until you upload one, Remotion draws motion graphics in this slot, so the video is never empty.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
