import React, { useState, useMemo } from 'react';
import { Search, ChevronDown, ChevronRight } from 'lucide-react';
import { TranscriptComparison } from '../TranscriptComparison';
import { TranscriptComparisonData } from '../../services/api';

export interface AudioTranscriptTabProps {
  data: any;
  comparison: TranscriptComparisonData | null;
  totalWords: number;
}

export const AudioTranscriptTab: React.FC<AudioTranscriptTabProps> = ({
  data,
  comparison,
  totalWords
}) => {
  const [wordSearch, setWordSearch] = useState<string>('');
  const utterances = data?.utterances || [];

  const [expandedUtterances, setExpandedUtterances] = useState<Record<string, boolean>>(() => {
    if (utterances.length > 0) {
      return {
        [utterances[0].utterance_id || '0']: true,
        ...(utterances[1] ? { [utterances[1].utterance_id || '1']: true } : {})
      };
    }
    return {};
  });

  const filteredUtterances = useMemo(() => {
    if (!wordSearch.trim()) return utterances;
    const q = wordSearch.toLowerCase().trim();
    return utterances.filter((u: any) =>
      (u.text && u.text.toLowerCase().includes(q)) ||
      (u.words && u.words.some((w: any) => w.text && w.text.toLowerCase().includes(q)))
    );
  }, [utterances, wordSearch]);

  const toggleUtterance = (id: string) => {
    setExpandedUtterances((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Complete text card */}
      {data.transcription?.full_text && (
        <div
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '16px 18px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)' }}>
              Full Telugu Transcript
            </span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              {totalWords} words · {data.transcription.full_text.length} chars
            </span>
          </div>
          <p
            style={{
              fontSize: '13.5px',
              lineHeight: 1.6,
              color: 'var(--text-primary)',
              margin: 0,
              backgroundColor: 'var(--bg-card)',
              padding: '12px 14px',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle)'
            }}
          >
            {data.transcription.full_text}
          </p>
        </div>
      )}

      {/* Transcript Comparison if available */}
      {comparison && <TranscriptComparison data={comparison} />}

      {/* Search bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Search
            size={14}
            style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
          />
          <input
            type="text"
            placeholder="Search Telugu words or utterances..."
            value={wordSearch}
            onChange={(e) => setWordSearch(e.target.value)}
            style={{
              width: '100%',
              padding: '7px 12px 7px 32px',
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              color: 'var(--text-primary)',
              fontSize: '12.5px',
              outline: 'none'
            }}
          />
        </div>
        {wordSearch && (
          <button
            onClick={() => setWordSearch('')}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Utterances list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {filteredUtterances.map((u: any, idx: number) => {
          const uId = u.utterance_id || String(u.id || idx);
          const isExpanded = !!expandedUtterances[uId];
          return (
            <div
              key={uId}
              data-testid={`utterance-card-${idx}`}
              style={{
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                overflow: 'hidden'
              }}
            >
              <div
                onClick={() => toggleUtterance(uId)}
                style={{
                  padding: '12px 16px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  cursor: 'pointer',
                  backgroundColor: isExpanded ? 'var(--bg-card)' : 'transparent',
                  borderBottom: isExpanded ? '1px solid var(--border-subtle)' : 'none',
                  userSelect: 'none',
                  gap: '12px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
                  <span style={{ color: 'var(--text-muted)', display: 'flex' }}>
                    {isExpanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                  </span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 700,
                      color: 'var(--accent-cyan)',
                      backgroundColor: 'rgba(0, 216, 245, 0.1)',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      flexShrink: 0
                    }}
                  >
                    #{String(u.id !== undefined ? u.id + 1 : idx + 1).padStart(2, '0')}
                  </span>
                  <span
                    style={{
                      fontSize: '13px',
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}
                  >
                    {u.text}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
                  <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    {u.start_seconds?.toFixed(2)}s – {u.end_seconds?.toFixed(2)}s
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                    {u.words?.length || 0} words
                  </span>
                </div>
              </div>

              {/* Expanded word badges */}
              {isExpanded && (
                <div style={{ padding: '12px 16px', backgroundColor: 'var(--bg-card)' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {u.words &&
                      u.words.map((w: any, wIdx: number) => (
                        <div
                          key={wIdx}
                          style={{
                            backgroundColor: 'var(--bg-elevated)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '6px',
                            padding: '6px 10px',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '2px',
                            minWidth: '70px'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
                              {w.text}
                            </span>
                            {w.edit && (
                              <span
                                style={{
                                  fontSize: '9px',
                                  fontWeight: 700,
                                  backgroundColor: 'rgba(24, 144, 255, 0.2)',
                                  color: 'var(--accent-cyan)',
                                  padding: '0 4px',
                                  borderRadius: '3px'
                                }}
                              >
                                {w.edit}
                              </span>
                            )}
                          </div>
                          <span style={{ fontSize: '10.5px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                            {w.start_seconds?.toFixed(2)}s – {w.end_seconds?.toFixed(2)}s
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
