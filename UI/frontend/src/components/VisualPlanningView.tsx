import React, { useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Film, Image as ImageIcon, Sparkles } from 'lucide-react';
import { FAMILIES, FAMILY_LABEL, MediaFamily } from '../services/mediaMix';

// What Visual Planning (visual_planning.json, schema 2.0) shows: the chosen media mix against what the plan reached, the count of every kind of element, and one row per scene.
const COLOR: Record<MediaFamily, string> = { motion: 'var(--accent-blue)', image: 'var(--accent-cyan)', video: '#a78bfa' };
const COUNT_COLUMNS: { key: string; label: string }[] = [
  { key: 'text', label: 'Text' },
  { key: 'icon', label: 'Icons' },
  { key: 'graphic', label: 'Graphics' },
  { key: 'image', label: 'Images' },
  { key: 'video', label: 'Videos' },
  { key: 'page', label: 'Pages' }
];

interface VisualPlanningViewProps {
  data: any | null;
  loading: boolean;
}

const card: React.CSSProperties = { backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border-card)', borderRadius: '8px', padding: '14px 18px' };
const muted: React.CSSProperties = { fontSize: '11px', color: 'var(--text-muted)' };

export const HeroBadge: React.FC<{ family: MediaFamily }> = ({ family }) => (
  <span
    data-testid={`hero-${family}`}
    style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 700, color: COLOR[family], border: `1px solid ${COLOR[family]}`, whiteSpace: 'nowrap' }}
  >
    {family === 'image' ? <ImageIcon size={11} /> : family === 'video' ? <Film size={11} /> : <Sparkles size={11} />}
    {FAMILY_LABEL[family]}
  </span>
);

const MixBar: React.FC<{ mix: any }> = ({ mix }) => (
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
    {FAMILIES.map((f) => {
      const target = mix.target?.[f] ?? 0;
      const actual = mix.actual?.[f] ?? 0;
      const off = (mix.off_target || []).includes(f);
      return (
        <div key={f} data-testid={`mix-${f}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
            <span>{FAMILY_LABEL[f]}</span>
            <span style={{ color: off ? 'var(--status-warning, #f59e0b)' : 'var(--text-primary)' }}>
              {actual}% <span style={{ ...muted, fontWeight: 400 }}>of {target}% chosen</span>
            </span>
          </div>
          <div style={{ position: 'relative', height: '8px', borderRadius: '4px', backgroundColor: 'var(--bg-card)', marginTop: '4px' }}>
            <div style={{ width: `${actual}%`, height: '100%', borderRadius: '4px', backgroundColor: COLOR[f] }} />
            <div title={`chosen ${target}%`} style={{ position: 'absolute', left: `${target}%`, top: '-3px', width: '2px', height: '14px', backgroundColor: 'var(--text-primary)' }} />
          </div>
        </div>
      );
    })}
  </div>
);

const SceneDetails: React.FC<{ scene: any }> = ({ scene }) => {
  const notes = (scene.validation_notes || []).filter((n: any) => n.severity !== 'info');
  return (
    <div style={{ display: 'grid', gap: '10px', padding: '10px 4px' }}>
      <div style={{ fontSize: '12px', color: 'var(--text-primary)' }}>
        <strong>{scene.scene_objective?.core_meaning}</strong>
        <div style={muted}>{scene.narration?.text_en || scene.narration?.text}</div>
      </div>
      <div style={{ display: 'grid', gap: '4px' }}>
        {(scene.elements || []).map((e: any) => (
          <div key={e.element_id} style={{ display: 'grid', gridTemplateColumns: '90px 150px 1fr', gap: '8px', fontSize: '11.5px', alignItems: 'baseline' }}>
            <span style={{ fontWeight: 700, color: e.type === 'image' || e.type === 'reference' ? COLOR.image : e.type === 'video' ? COLOR.video : 'var(--text-secondary)' }}>{e.type}</span>
            <span style={{ ...muted, fontFamily: 'var(--font-mono)' }}>{e.element_id} · {e.role} · {e.placement?.region}</span>
            <span style={{ color: 'var(--text-primary)' }}>{e.content ? `"${e.content}"` : e.visual_description}</span>
          </div>
        ))}
      </div>
      {(scene.media_requirements || []).map((r: any) => (
        <div key={r.requirement_id} data-testid="media-requirement" style={{ border: '1px dashed var(--border-card)', borderRadius: '6px', padding: '8px 10px', fontSize: '11.5px', display: 'grid', gap: '2px' }}>
          <div><strong>{r.media_type === 'video' ? 'Clip' : r.media_type === 'reference' ? 'Reference page' : 'Photo'} {r.media_type === 'reference' ? `(${r.section})` : 'search'}:</strong> {r.query} <span style={muted}>(also: {(r.alt_queries || []).join(', ') || '—'})</span></div>
          <div style={muted}>If nothing suitable is found: {r.fallback}</div>
          {r.ai_prompt && <div style={muted}>AI prompt: {r.ai_prompt}</div>}
        </div>
      ))}
      {notes.length > 0 && (
        <div style={{ fontSize: '11px', color: 'var(--status-warning, #f59e0b)' }}>
          {notes.map((n: any, i: number) => (
            <div key={i} style={{ display: 'flex', gap: '6px', alignItems: 'flex-start' }}><AlertTriangle size={12} style={{ marginTop: 2, flexShrink: 0 }} />{n.message}</div>
          ))}
        </div>
      )}
    </div>
  );
};

export const VisualPlanningView: React.FC<VisualPlanningViewProps> = ({ data, loading }) => {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const scenes: any[] = data?.scenes || [];
  const totals = data?.totals || {};
  const errors: string[] = data?.validation?.errors || [];
  const warnings: string[] = data?.validation?.warnings || [];
  const mix = data?.media_mix;
  const first = useMemo(() => scenes[0]?.scene_id, [scenes]);

  if (loading) return <div style={{ ...card, ...muted }} data-testid="visual-planning-loading">Loading the visual plan…</div>;
  if (!data) {
    return (
      <div style={{ ...card, ...muted, textAlign: 'center', padding: '40px 16px' }} data-testid="visual-planning-empty">
        Visual Planning has not produced a plan for this project yet. Run the stage to plan what each scene shows.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }} data-testid="visual-planning-tab-content">
      <div style={{ ...card, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <div style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)' }}>Visual Planning</div>
          <div style={muted}>
            {scenes.length} scenes · {data.visual_style?.category || 'style not named'} · {data.project?.aspect_ratio}
            {data.stale ? ' · out of date (the scene plan or the media mix changed)' : ''}
          </div>
        </div>
        <span
          data-testid="visual-planning-validation"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '12px', fontWeight: 700, color: errors.length ? 'var(--status-failed, #f87171)' : warnings.length ? 'var(--status-warning, #f59e0b)' : 'var(--status-completed, #34d399)' }}
        >
          {errors.length ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
          {errors.length ? `${errors.length} blocking error(s)` : warnings.length ? `${warnings.length} warning(s)` : 'all checks passed'}
        </span>
      </div>

      {mix && (
        <div style={card}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: '8px' }}>
            Media mix — chosen at upload vs reached by the plan (share of the video's time)
          </div>
          <MixBar mix={mix} />
          <div style={{ ...muted, marginTop: '8px' }} data-testid="mix-note">
            {mix.off_target?.length ? mix.note : 'Within the tolerance of the chosen shares.'}{mix.ai_images ? ' · AI-picture prompts are written for every image.' : ''}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }} data-testid="visual-planning-totals">
        {COUNT_COLUMNS.map((c) => (
          <div key={c.key} style={{ ...card, padding: '10px 16px', minWidth: '96px' }}>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>{totals[c.key] ?? 0}</div>
            <div style={muted}>{c.label}</div>
          </div>
        ))}
      </div>

      <div style={{ ...card, padding: 0, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }} data-testid="visual-planning-table">
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-card)' }}>
              <th style={{ padding: '8px 12px' }}>Scene</th>
              <th style={{ padding: '8px 6px' }}>Primary</th>
              {COUNT_COLUMNS.map((c) => <th key={c.key} style={{ padding: '8px 6px', textAlign: 'center' }}>{c.label}</th>)}
              <th style={{ padding: '8px 12px' }}>Idea</th>
            </tr>
          </thead>
          <tbody>
            {scenes.map((s) => {
              const isOpen = open[s.scene_id] ?? s.scene_id === first;
              return (
                <React.Fragment key={s.scene_id}>
                  <tr
                    data-testid={`scene-row-${s.scene_id}`}
                    onClick={() => setOpen((o) => ({ ...o, [s.scene_id]: !isOpen }))}
                    style={{ cursor: 'pointer', borderBottom: '1px solid var(--border-card)' }}
                  >
                    <td style={{ padding: '8px 12px', whiteSpace: 'nowrap', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />} {s.scene_id}
                      <div style={muted}>{s.narration?.start_seconds?.toFixed?.(1)}–{s.narration?.end_seconds?.toFixed?.(1)} s</div>
                    </td>
                    <td style={{ padding: '8px 6px' }}><HeroBadge family={s.hero} /></td>
                    {COUNT_COLUMNS.map((c) => (
                      <td key={c.key} data-testid={`count-${s.scene_id}-${c.key}`} style={{ padding: '8px 6px', textAlign: 'center', color: s.counts?.[c.key] ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                        {s.counts?.[c.key] ?? 0}
                      </td>
                    ))}
                    <td style={{ padding: '8px 12px', color: 'var(--text-secondary)', minWidth: '220px' }}>{s.visual_concept?.description}</td>
                  </tr>
                  {isOpen && (
                    <tr>
                      <td colSpan={COUNT_COLUMNS.length + 3} style={{ padding: '4px 16px 12px', backgroundColor: 'var(--bg-card)' }}>
                        <SceneDetails scene={s} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {(errors.length > 0 || warnings.length > 0) && (
        <div style={card} data-testid="visual-planning-issues">
          {[...errors.map((m) => ({ m, error: true })), ...warnings.map((m) => ({ m, error: false }))].map((x, i) => (
            <div key={i} style={{ display: 'flex', gap: '6px', fontSize: '11.5px', color: x.error ? 'var(--status-failed, #f87171)' : 'var(--status-warning, #f59e0b)', padding: '2px 0' }}>
              <AlertTriangle size={12} style={{ marginTop: 2, flexShrink: 0 }} />{x.m}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
