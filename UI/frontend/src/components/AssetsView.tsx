import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Copy, ExternalLink, Film, Image as ImageIcon } from 'lucide-react';
import { API_BASE, fetchAssets } from '../services/api';

// Asset Collection (Stage 5): every real photo or clip the Visual Plan asked for, with the file that was collected (or why nothing was) and where it comes from.
const card: React.CSSProperties = { backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border-card)', borderRadius: '8px', padding: '14px 18px' };
const muted: React.CSSProperties = { fontSize: '11px', color: 'var(--text-muted)' };
const STATUS_COLOR: Record<string, string> = { collected: 'var(--status-completed, #34d399)', fallback: 'var(--status-warning, #f59e0b)', pending: 'var(--text-muted)' };

interface AssetsViewProps {
  projectId?: string | null;
  /** change it to load again (the stage finished, the plan changed) */
  refreshKey?: unknown;
}

const Media: React.FC<{ item: any }> = ({ item }) => {
  const a = item.asset;
  const box: React.CSSProperties = { width: '100%', aspectRatio: '16 / 9', borderRadius: '6px', backgroundColor: 'var(--bg-card)', objectFit: 'cover', display: 'block' };
  if (a && a.kind === 'video') return <video data-testid="asset-video" src={`${API_BASE}${a.url}`} controls muted preload="metadata" style={box} />;
  if (a) return <img data-testid="asset-image" src={`${API_BASE}${a.url}`} alt={a.title || item.query} style={box} />;
  return (
    <div style={{ ...box, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '10px', fontSize: '11.5px', color: 'var(--text-muted)' }}>
      {item.status === 'fallback' ? 'No suitable real media was found.' : 'Not collected yet.'}
    </div>
  );
};

const Item: React.FC<{ item: any }> = ({ item }) => {
  const a = item.asset;
  const [copied, setCopied] = useState(false);
  const copyPrompt = () => {
    try {
      navigator.clipboard.writeText(item.ai_prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* the clipboard may be unavailable */
    }
  };
  return (
    <div style={{ ...card, display: 'grid', gap: '8px' }} data-testid={`asset-item-${item.requirement_id}`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
          {item.kind === 'video' ? <Film size={13} /> : <ImageIcon size={13} />} Scene {item.scene_id} · {item.kind === 'video' ? 'Clip' : item.kind === 'page' ? 'Reference page' : 'Photo'}
        </span>
        <span data-testid={`asset-status-${item.requirement_id}`} style={{ fontSize: '11px', fontWeight: 700, color: STATUS_COLOR[item.status] }}>{item.status}</span>
      </div>
      <Media item={item} />
      <div style={{ fontSize: '12px', color: 'var(--text-primary)' }}>
        <strong>Searched for:</strong> {item.query} <span style={muted}>(also: {(item.alt_queries || []).join(', ') || '—'})</span>
      </div>
      {a && (
        <div style={{ ...muted, display: 'grid', gap: '2px' }}>
          <div>
            {a.title || 'Untitled'} · {a.author || 'unknown author'} · <strong>{a.license?.name || 'no licence'}</strong> · rights class {a.rights_class}
            {a.needs_human_review ? ' (rights not established: listed in Final QC for review)' : ''}
          </div>
          {a.source_url && (
            <a href={a.source_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-blue)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              source <ExternalLink size={11} />
            </a>
          )}
        </div>
      )}
      {item.status === 'fallback' && (
        <div style={{ fontSize: '11.5px', color: 'var(--status-warning, #f59e0b)', display: 'flex', gap: '6px' }}>
          <AlertTriangle size={12} style={{ marginTop: 2, flexShrink: 0 }} />
          <span>{item.reason}. The scene draws instead: {item.fallback}</span>
        </div>
      )}
      {item.ai_prompt && (
        <div style={{ ...muted, display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
          <span style={{ flex: 1 }}>AI prompt (ready for an image generator): {item.ai_prompt}</span>
          <button type="button" onClick={copyPrompt} aria-label="Copy the AI prompt" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent-blue)' }}>
            {copied ? <CheckCircle2 size={13} /> : <Copy size={13} />}
          </button>
        </div>
      )}
    </div>
  );
};

export const AssetsView: React.FC<AssetsViewProps> = ({ projectId, refreshKey }) => {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    let alive = true;
    setLoading(true);
    fetchAssets(projectId).then((d) => {
      if (alive) {
        setData(d);
        setLoading(false);
      }
    });
    return () => {
      alive = false;
    };
  }, [projectId, refreshKey]);

  if (loading && !data) return <div style={{ ...card, ...muted }} data-testid="assets-loading">Loading the collected media…</div>;
  if (!data || data.items.length === 0) {
    return (
      <div style={{ ...card, ...muted, textAlign: 'center', padding: '40px 16px' }} data-testid="assets-empty">
        No real photo or clip was requested by the Visual Plan for this project (images and videos set to 0%, or nothing in the narration that a camera can show). Every scene is drawn by code.
      </div>
    );
  }
  const s = data.summary;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }} data-testid="assets-tab-content">
      <div style={{ ...card, display: 'flex', gap: '24px', flexWrap: 'wrap', alignItems: 'center' }} data-testid="assets-summary">
        <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>Collected media</span>
        <span style={muted}>{s.requirements} requested · <strong style={{ color: STATUS_COLOR.collected }}>{s.collected} collected</strong> · <strong style={{ color: STATUS_COLOR.fallback }}>{s.fallbacks} fell back to motion graphics</strong></span>
        {!data.manifest_current && <span style={{ ...muted, color: 'var(--status-warning, #f59e0b)' }}>Run Asset Collection to search for these.</span>}
      </div>
      {(data.findings || []).filter((f: any) => f.severity !== 'info').map((f: any, i: number) => (
        <div key={i} style={{ ...muted, color: f.severity === 'error' ? 'var(--status-failed, #f87171)' : 'var(--status-warning, #f59e0b)' }}>{f.message}</div>
      ))}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px' }}>
        {data.items.map((item: any) => <Item key={item.requirement_id} item={item} />)}
      </div>
    </div>
  );
};
