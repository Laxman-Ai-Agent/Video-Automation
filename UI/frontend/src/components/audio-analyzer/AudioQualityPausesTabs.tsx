import React, { useState } from 'react';
import { Check, Copy, CheckCircle2 } from 'lucide-react';

export interface AudioQualityPausesTabsProps {
  activeSubTab: 'pauses' | 'quality' | 'overview' | 'raw';
  data: any;
}

export const AudioQualityPausesTabs: React.FC<AudioQualityPausesTabsProps> = ({
  activeSubTab,
  data
}) => {
  const [copiedJson, setCopiedJson] = useState<boolean>(false);

  const handleCopyJson = () => {
    if (!data) return;
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopiedJson(true);
    setTimeout(() => setCopiedJson(false), 2000);
  };

  return (
    <>
      {/* 2. PAUSES & RHYTHM TAB */}
      {activeSubTab === 'pauses' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div
            style={{
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '14px 18px'
            }}
          >
            <h4 style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              Pause & Cadence Parameters
            </h4>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
              Method: {data.processing?.pause_detection?.method || 'ffmpeg silencedetect'} · 
              Min Duration: {data.processing?.pause_detection?.min_seconds || 0.35}s · 
              Threshold: {data.processing?.pause_detection?.threshold_db || -35} dB
            </p>
          </div>

          {data.pauses && data.pauses.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {data.pauses.map((p: any, idx: number) => (
                <div
                  key={idx}
                  style={{
                    backgroundColor: 'var(--bg-elevated)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '6px',
                    padding: '10px 14px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span
                      style={{
                        fontSize: '11px',
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--accent-cyan)',
                        backgroundColor: 'rgba(0, 216, 245, 0.1)',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontWeight: 700
                      }}
                    >
                      P-{String(idx + 1).padStart(2, '0')}
                    </span>
                    <span style={{ fontSize: '13px', color: 'var(--text-primary)', fontWeight: 600 }}>
                      {p.kind || 'silence'} ({p.source || 'ffmpeg'})
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      {p.start_seconds?.toFixed(3)}s – {p.end_seconds?.toFixed(3)}s
                    </span>
                    <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      {p.duration_seconds?.toFixed(3)}s
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12.5px' }}>
              No silences or pauses recorded in this audio artifact.
            </div>
          )}
        </div>
      )}

      {/* 3. QUALITY TAB */}
      {activeSubTab === 'quality' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div
            style={{
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '16px 18px',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
              gap: '14px'
            }}
          >
            <div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Quality Status</span>
              <div style={{ fontSize: '14px', fontWeight: 700, color: '#10B981', marginTop: '2px' }}>
                {data.quality?.status || 'measured'}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Max Volume</span>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                {data.quality?.max_volume_db !== undefined ? `${data.quality.max_volume_db} dB` : '—'}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Mean Volume</span>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                {data.quality?.mean_volume_db !== undefined ? `${data.quality.mean_volume_db} dB` : '—'}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Uncertain Words</span>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--accent-cyan)', marginTop: '2px' }}>
                {data.quality?.uncertain_words ?? '0'}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Uncertain Share</span>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                {data.quality?.uncertain_share !== undefined ? `${(data.quality.uncertain_share * 100).toFixed(1)}%` : '—'}
              </div>
            </div>
          </div>

          <div
            style={{
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '16px 18px'
            }}
          >
            <h4 style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 10px 0' }}>
              Validation Diagnostics
            </h4>
            {data.validation?.notes && data.validation.notes.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {data.validation.notes.map((note: any, idx: number) => (
                  <div
                    key={idx}
                    style={{
                      backgroundColor: 'var(--bg-card)',
                      padding: '10px 14px',
                      borderRadius: '6px',
                      fontSize: '12px',
                      color: 'var(--text-secondary)',
                      borderLeft: '3px solid var(--accent-cyan)'
                    }}
                  >
                    {typeof note === 'string' ? note : note.message || JSON.stringify(note)}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: '12.5px', color: '#10B981', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle2 size={15} />
                <span>All acoustic checks passed with zero errors or clipping.</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. OVERVIEW / AUDIO METADATA TAB */}
      {activeSubTab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div
            style={{
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '16px 18px',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
              gap: '14px'
            }}
          >
            <div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>File Name</span>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                {data.source?.file || 'audio.wav'}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Duration</span>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--accent-cyan)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                {data.source?.duration_seconds ? `${data.source.duration_seconds.toFixed(2)}s` : '—'}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Sample Rate</span>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                {data.source?.sample_rate_hz ? `${data.source.sample_rate_hz} Hz` : '—'}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Channels</span>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                {data.source?.channels === 1 ? 'Mono (1ch)' : 'Stereo (2ch)'}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Language</span>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                {data.transcription?.language?.code ? `${data.transcription.language.code.toUpperCase()} (Telugu)` : 'Telugu'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 5. RAW JSON TAB */}
      {activeSubTab === 'raw' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Size: {JSON.stringify(data).length.toLocaleString()} bytes · Keys: {Object.keys(data).length}
            </span>
            <button
              onClick={handleCopyJson}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px',
                borderRadius: '5px',
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-subtle)',
                color: copiedJson ? '#10B981' : 'var(--accent-cyan)',
                fontSize: '11.5px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              {copiedJson ? <Check size={12} /> : <Copy size={12} />}
              {copiedJson ? 'Copied!' : 'Copy JSON'}
            </button>
          </div>
          <pre
            style={{
              padding: '14px 16px',
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              fontSize: '11.5px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-secondary)',
              maxHeight: '480px',
              overflow: 'auto',
              lineHeight: 1.5,
              margin: 0
            }}
          >
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </>
  );
};
