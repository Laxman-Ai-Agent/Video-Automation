import React, { useState } from 'react';
import type { TranscriptComparisonData } from '../services/api';

interface Props {
  data: TranscriptComparisonData;
}

const chip = (ok: boolean | null): React.CSSProperties => ({
  fontSize: '11px',
  fontFamily: 'var(--font-mono)',
  padding: '2px 8px',
  borderRadius: '10px',
  border: '1px solid rgba(255, 255, 255, 0.12)',
  color: ok === null ? 'var(--text-muted)' : ok ? '#4ADE80' : '#FBBF24',
});

const box: React.CSSProperties = {
  backgroundColor: '#080E1A',
  border: '1px solid rgba(255, 255, 255, 0.06)',
  borderRadius: '6px',
  padding: '10px 12px',
  fontSize: '13px',
  lineHeight: 1.6,
  color: '#FFFFFF',
};

/** The raw Whisper output next to the final, LLM-verified transcript, segment by segment: the LLM's edits are highlighted (green = re-aligned against the audio, amber = estimated time). */
export const TranscriptComparison: React.FC<Props> = ({ data }) => {
  const [onlyChanged, setOnlyChanged] = useState<boolean>(false);
  const changed = data.segments.filter((s) => s.changed).length;
  const shown = onlyChanged ? data.segments.filter((s) => s.changed) : data.segments;
  const alignmentOk = data.alignment ? !['estimated_for_edits', 'partial'].includes(data.alignment) : null;

  return (
    <div data-testid="transcript-comparison" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '13px', fontWeight: 700, color: '#FFFFFF' }}>Raw Whisper vs LLM-corrected</span>
        <span style={chip(data.verified)}>{data.verified ? 'LLM verified' : 'not verified yet'}</span>
        <span style={chip(data.llm.status ? ['applied', 'cached'].includes(data.llm.status) : null)}>LLM: {data.llm.status || 'not run'}</span>
        <span style={chip(null)}>{data.corrections_applied} applied / {data.corrections_rejected} rejected</span>
        <span style={chip(alignmentOk)}>timestamps: {data.alignment || 'n/a'}</span>
        {data.stage_review && <span style={chip(data.stage_review.status === 'passed')}>stage review: {data.stage_review.status}{data.stage_review.score != null ? ` ${data.stage_review.score}` : ''}</span>}
        <span style={{ ...chip(null), marginLeft: 'auto' }}>{data.raw_file} → {data.final_file}</span>
      </div>
      <label style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', gap: '6px', alignItems: 'center' }}>
        <input type="checkbox" checked={onlyChanged} onChange={(e) => setOnlyChanged(e.target.checked)} />
        Show only the {changed} changed segment(s)
      </label>
      {shown.length === 0 && <div style={{ ...box, color: 'var(--text-muted)' }}>{changed === 0 ? 'The LLM checked every word and changed nothing: the final transcript has the same words as the original.' : 'No segments.'}</div>}
      {shown.map((s) => (
        <div key={s.id} data-testid={`comparison-segment-${s.id}`} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div style={box}>
            <div style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: '4px' }}>#{s.id + 1} · {s.start.toFixed(2)}–{s.end.toFixed(2)}s · WHISPER (original)</div>
            {s.raw_text}
          </div>
          <div style={{ ...box, borderColor: s.changed ? 'rgba(74, 222, 128, 0.35)' : 'rgba(255, 255, 255, 0.06)' }}>
            <div style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: '4px' }}>LLM-CORRECTED (final){s.changed ? '' : ' · unchanged'}</div>
            {s.final_words
              ? s.final_words.map((w, i) => (
                  <span key={i} title={w.edit ? `LLM edit, ${w.timing === 'aligned' ? 're-aligned against the audio' : 'estimated time'} (${w.start.toFixed(2)}–${w.end.toFixed(2)}s)` : undefined}
                        style={w.edit ? { color: w.timing === 'aligned' ? '#4ADE80' : '#FBBF24', fontWeight: 700 } : undefined}>
                    {w.w}{' '}
                  </span>
                ))
              : s.final_text}
          </div>
        </div>
      ))}
    </div>
  );
};
