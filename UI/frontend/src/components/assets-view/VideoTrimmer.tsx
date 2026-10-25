import React, { useState } from 'react';
import { Scissors, Loader2, Check, Save } from 'lucide-react';
import { updateAsset } from '../../services/api';

export interface VideoTrimmerProps {
  item: any;
  projectId: string;
  onSaved: () => void;
}

export const VideoTrimmer: React.FC<VideoTrimmerProps> = ({ item, projectId, onSaved }) => {
  const a = item.asset;
  const totalDuration = a?.duration_s || 10.0;
  const defaultSceneDur = item.duration_s || 2.0;

  const [clipStart, setClipStart] = useState<number>(a?.clip_start ?? 0.0);
  const [clipEnd, setClipEnd] = useState<number>(
    a?.clip_end ?? Math.min(totalDuration, (a?.clip_start ?? 0.0) + (a?.clip_dur ?? defaultSceneDur))
  );
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const selectedDuration = Math.max(0.1, Number((clipEnd - clipStart).toFixed(2)));

  const handleSaveTrim = async () => {
    setSaving(true);
    setSavedSuccess(false);
    try {
      await updateAsset(projectId, {
        requirement_id: item.requirement_id,
        scene_id: item.scene_id,
        kind: 'video',
        clip_start: clipStart,
        clip_dur: selectedDuration,
        clip_end: clipEnd,
      });
      setSavedSuccess(true);
      onSaved();
      setTimeout(() => setSavedSuccess(false), 2000);
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
          <Scissors size={12} color="#60A5FA" /> Video Trimmer / Frame Range
        </span>
        <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
          Total File: <strong>{totalDuration.toFixed(1)}s</strong>
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          <label style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Start Time (sec):</label>
          <input
            type="number"
            min={0}
            max={Math.max(0, clipEnd - 0.1)}
            step={0.1}
            value={clipStart}
            onChange={(e) => {
              const val = Math.max(0, parseFloat(e.target.value) || 0);
              setClipStart(val);
              if (val >= clipEnd) setClipEnd(val + defaultSceneDur);
            }}
            style={{
              backgroundColor: 'var(--bg-input, rgba(255,255,255,0.06))',
              border: '1px solid var(--border-subtle)',
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '11px',
              color: 'var(--text-primary)',
            }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          <label style={{ fontSize: '10px', color: 'var(--text-muted)' }}>End Time (sec):</label>
          <input
            type="number"
            min={clipStart + 0.1}
            max={totalDuration}
            step={0.1}
            value={clipEnd}
            onChange={(e) => {
              const val = Math.min(totalDuration, Math.max(clipStart + 0.1, parseFloat(e.target.value) || 0));
              setClipEnd(val);
            }}
            style={{
              backgroundColor: 'var(--bg-input, rgba(255,255,255,0.06))',
              border: '1px solid var(--border-subtle)',
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '11px',
              color: 'var(--text-primary)',
            }}
          />
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '2px' }}>
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
          Selected Duration: <strong style={{ color: '#34D399' }}>{selectedDuration.toFixed(1)}s</strong>
        </span>
        <button
          type="button"
          onClick={handleSaveTrim}
          disabled={saving}
          style={{
            padding: '4px 10px',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: 600,
            cursor: saving ? 'not-allowed' : 'pointer',
            backgroundColor: savedSuccess ? '#059669' : 'rgba(59, 130, 246, 0.2)',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            color: savedSuccess ? '#fff' : '#93C5FD',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            transition: 'all 0.15s ease',
          }}
        >
          {saving ? <Loader2 size={11} className="animate-spin" /> : savedSuccess ? <Check size={11} /> : <Save size={11} />}
          <span>{saving ? 'Saving…' : savedSuccess ? 'Trim Saved!' : 'Save Range'}</span>
        </button>
      </div>
    </div>
  );
};
