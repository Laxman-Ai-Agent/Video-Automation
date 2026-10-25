import React, { useState } from 'react';
import { Layers, Loader2, Check, Save } from 'lucide-react';
import { updateAsset } from '../../services/api';

export interface IconEditorProps {
  item: any;
  projectId: string;
  onSaved: () => void;
}

export const IconEditor: React.FC<IconEditorProps> = ({ item, projectId, onSaved }) => {
  const [iconName, setIconName] = useState(item.icon_name || 'HelpCircle');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSaveIcon = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await updateAsset(projectId, {
        requirement_id: item.requirement_id,
        scene_id: item.scene_id,
        kind: 'icon',
        icon_name: iconName.trim(),
      });
      setSaved(true);
      onSaved();
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        backgroundColor: 'rgba(0, 0, 0, 0.25)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '6px',
        padding: '10px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Layers size={12} color="#A78BFA" /> Lucide Icon Selector
        </span>
      </div>

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <input
          type="text"
          value={iconName}
          onChange={(e) => setIconName(e.target.value)}
          placeholder="e.g. Zap, Heart, Shield, Code, TrendingUp..."
          style={{
            flex: 1,
            backgroundColor: 'var(--bg-input, rgba(255,255,255,0.06))',
            border: '1px solid var(--border-subtle)',
            borderRadius: '4px',
            padding: '5px 8px',
            fontSize: '11.5px',
            color: 'var(--text-primary)',
          }}
        />
        <button
          type="button"
          onClick={handleSaveIcon}
          disabled={saving}
          style={{
            padding: '5px 12px',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: 600,
            cursor: saving ? 'not-allowed' : 'pointer',
            backgroundColor: saved ? '#059669' : 'rgba(167, 139, 250, 0.2)',
            border: '1px solid rgba(167, 139, 250, 0.4)',
            color: saved ? '#fff' : '#DDD6FE',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {saving ? <Loader2 size={11} className="animate-spin" /> : saved ? <Check size={11} /> : <Save size={11} />}
          <span>{saving ? 'Saving…' : saved ? 'Saved!' : 'Save Icon'}</span>
        </button>
      </div>
    </div>
  );
};
