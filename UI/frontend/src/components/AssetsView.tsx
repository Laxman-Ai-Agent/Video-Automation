import React, { useEffect, useMemo, useState } from 'react';
import { Info } from 'lucide-react';
import { fetchAssets } from '../services/api';
import { ItemCard } from './assets-view/ItemCard';

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

interface AssetsViewProps {
  projectId?: string | null;
  /** change it to load again (the stage finished, the plan changed) */
  refreshKey?: unknown;
}

export const AssetsView: React.FC<AssetsViewProps> = ({ projectId, refreshKey }) => {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [localRefresh, setLocalRefresh] = useState(0);
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'photo' | 'video' | 'icon'>('all');

  const load = () => {
    if (!projectId) return;
    setLoading(true);
    fetchAssets(projectId).then((d) => {
      setData(d);
      setLoading(false);
    });
  };

  useEffect(() => {
    load();
  }, [projectId, refreshKey, localRefresh]);

  const items = data?.items || [];

  // Filter items by category
  const filteredItems = useMemo(() => {
    if (selectedCategory === 'all') return items;
    if (selectedCategory === 'photo') {
      return items.filter(
        (i: any) => i.kind === 'photo' || i.kind === 'image' || i.media_type === 'image'
      );
    }
    if (selectedCategory === 'video') {
      return items.filter((i: any) => i.kind === 'video' || i.media_type === 'video');
    }
    if (selectedCategory === 'icon') {
      return items.filter((i: any) => i.kind === 'icon' || i.type === 'icon');
    }
    return items;
  }, [items, selectedCategory]);

  const counts = useMemo(() => {
    const total = items.length;
    const images = items.filter(
      (i: any) => i.kind === 'photo' || i.kind === 'image' || i.media_type === 'image'
    ).length;
    const videos = items.filter(
      (i: any) => i.kind === 'video' || i.media_type === 'video'
    ).length;
    const icons = items.filter((i: any) => i.kind === 'icon' || i.type === 'icon').length;
    return { all: total, photo: images, video: videos, icon: icons };
  }, [items]);

  if (loading && !data) {
    return (
      <div style={{ ...card, ...muted }} data-testid="assets-loading">
        Loading the collected media…
      </div>
    );
  }

  if (!data || items.length === 0) {
    return (
      <div
        style={{ ...card, ...muted, textAlign: 'center', padding: '40px 16px' }}
        data-testid="assets-empty"
      >
        No real photo or clip was requested by the Visual Plan for this project (or images and videos were turned off). Every scene is drawn by 100% Motion Canvas graphics & typography.
      </div>
    );
  }

  const s = data.summary;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }} data-testid="assets-tab-content">
      {/* Summary Banner with Totals */}
      <div
        style={{
          ...card,
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
        data-testid="assets-summary"
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
              Asset Collection & Frame Editor
            </span>
            <span style={muted}>
              {s.requirements} total requested ·{' '}
              <strong style={{ color: STATUS_COLOR.collected }}>{s.collected} collected</strong> ·{' '}
              <strong style={{ color: STATUS_COLOR.fallback }}>{s.fallbacks} motion graphics fallback</strong>
            </span>
          </div>

          {!data.manifest_current && (
            <span style={{ ...muted, color: 'var(--status-warning, #f59e0b)' }}>
              Run Asset Collection to search for these.
            </span>
          )}
        </div>

        {/* 100% Motion Canvas Guarantee Callout */}
        <div
          style={{
            backgroundColor: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid rgba(59, 130, 246, 0.2)',
            borderRadius: '6px',
            padding: '8px 12px',
            fontSize: '11.5px',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Info size={14} color="#60A5FA" style={{ flexShrink: 0 }} />
          <span>
            <strong>100% Motion Canvas Guarantee:</strong> If any image or video is missing or not uploaded, Remotion automatically renders rich motion graphics in its place. Your final video is always complete and engaging.
          </span>
        </div>
      </div>

      {/* Category Tabs: All, Images, Icons, Videos */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {[
          { key: 'all', label: 'All Assets', count: counts.all },
          { key: 'photo', label: 'Images', count: counts.photo },
          { key: 'icon', label: 'Icons', count: counts.icon },
          { key: 'video', label: 'Videos', count: counts.video },
        ].map((tab) => {
          const active = selectedCategory === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setSelectedCategory(tab.key as any)}
              style={{
                padding: '6px 14px',
                borderRadius: '20px',
                fontSize: '11.5px',
                fontWeight: active ? 700 : 500,
                cursor: 'pointer',
                backgroundColor: active ? 'var(--accent-blue, #3B82F6)' : 'var(--bg-elevated)',
                border: active ? '1px solid transparent' : '1px solid var(--border-card)',
                color: active ? '#ffffff' : 'var(--text-secondary)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.15s ease',
              }}
            >
              <span>{tab.label}</span>
              <span
                style={{
                  fontSize: '10px',
                  padding: '1px 6px',
                  borderRadius: '10px',
                  backgroundColor: active ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.08)',
                  color: active ? '#ffffff' : 'var(--text-muted)',
                }}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Findings / Warnings */}
      {(data.findings || [])
        .filter((f: any) => f.severity !== 'info')
        .map((f: any, i: number) => (
          <div
            key={i}
            style={{
              ...muted,
              color: f.severity === 'error' ? 'var(--status-failed, #f87171)' : 'var(--status-warning, #f59e0b)',
            }}
          >
            {f.message}
          </div>
        ))}

      {/* Filtered Asset Items Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '12px',
        }}
      >
        {filteredItems.map((item: any) => (
          <ItemCard
            key={item.requirement_id}
            item={item}
            projectId={projectId || ''}
            onAssetUpdated={() => setLocalRefresh((n) => n + 1)}
          />
        ))}
      </div>
    </div>
  );
};

export default AssetsView;
