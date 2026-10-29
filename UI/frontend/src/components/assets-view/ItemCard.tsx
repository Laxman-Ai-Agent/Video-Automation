import React, { useState } from 'react';
import { Film, Layers, Image as ImageIcon, MousePointerClick } from 'lucide-react';
import { MediaPreview } from './MediaPreview';
import { IconEditor } from './IconEditor';
import { AssetDetailModal } from './AssetDetailModal';
import styles from './ItemCard.module.css';

export interface ItemCardProps {
  item: any;
  projectId: string;
  onAssetUpdated: () => void;
}

/** One requirement of the Visual Plan. A picture or a clip opens its detail view on click (prompt, upload your own, trim); an icon is edited on the card. */
export const ItemCard: React.FC<ItemCardProps> = ({ item, projectId, onAssetUpdated }) => {
  const a = item.asset;
  const isVideo = item.kind === 'video' || item.media_type === 'video';
  const isIcon = item.kind === 'icon' || item.type === 'icon';
  const [open, setOpen] = useState(false);

  const kindLabel = isVideo ? 'Video Clip' : isIcon ? 'Icon' : 'Image Card';

  return (
    <div className={styles.card} data-testid={`asset-item-${item.requirement_id}`}>
      <div className={styles.header}>
        <span className={styles.kind}>
          {isVideo ? <Film size={13} color="#60A5FA" /> : isIcon ? <Layers size={13} color="#A78BFA" /> : <ImageIcon size={13} color="#34D399" />}
          Scene {item.scene_id} · {kindLabel}
        </span>
        <span className={styles.status} data-status={item.status} data-testid={`asset-status-${item.requirement_id}`}>
          {item.status === 'collected' ? (a?.selected_by === 'manual_upload' ? 'custom upload' : 'collected') : 'auto-fallback to motion'}
        </span>
      </div>

      {isIcon ? (
        <MediaPreview item={item} />
      ) : (
        <button
          type="button"
          className={styles.previewButton}
          onClick={() => setOpen(true)}
          aria-label={`Open the ${isVideo ? 'video' : 'image'} of scene ${item.scene_id}: prompt and upload`}
          data-testid={`asset-open-${item.requirement_id}`}
        >
          <MediaPreview item={item} compact />
          <span className={styles.hint}>
            <MousePointerClick size={11} /> Prompt &amp; upload
          </span>
        </button>
      )}

      <div className={styles.subject}>
        <strong>Subject:</strong> {item.query || item.description || 'Scene element'}
        {item.alt_queries?.length > 0 && <span className={styles.muted}> (also: {item.alt_queries.join(', ')})</span>}
      </div>

      {isIcon && <IconEditor item={item} projectId={projectId} onSaved={onAssetUpdated} />}

      {a && !isIcon && (
        <div className={styles.fileInfo}>
          {a.title || 'Custom file'} · {a.author || 'User'} · <strong>{a.license?.name || 'Personal'}</strong>
        </div>
      )}

      {open && <AssetDetailModal item={item} projectId={projectId} onClose={() => setOpen(false)} onAssetUpdated={onAssetUpdated} />}
    </div>
  );
};
