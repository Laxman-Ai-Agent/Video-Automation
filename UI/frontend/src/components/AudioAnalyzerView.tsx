import React, { useState, useEffect, useMemo } from 'react';
import {
  Volume2,
  FileText,
  Clock,
  Sliders,
  Code2,
  RefreshCw,
  AlertTriangle
} from 'lucide-react';
import {
  fetchAudioAnalysis,
  fetchTranscriptComparison,
  AudioAnalysisResult,
  TranscriptComparisonData
} from '../services/api';
import { AudioTranscriptTab } from './audio-analyzer/AudioTranscriptTab';
import { AudioQualityPausesTabs } from './audio-analyzer/AudioQualityPausesTabs';

export interface AudioAnalyzerViewProps {
  projectId?: string;
  refreshKey?: string | number;
  isFullPage?: boolean;
}

export const AudioAnalyzerView: React.FC<AudioAnalyzerViewProps> = ({
  projectId,
  refreshKey,
  isFullPage: _isFullPage = false
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'transcript' | 'pauses' | 'quality' | 'overview' | 'raw'>('transcript');
  const [loading, setLoading] = useState<boolean>(true);
  const [result, setResult] = useState<AudioAnalysisResult | null>(null);
  const [comparison, setComparison] = useState<TranscriptComparisonData | null>(null);

  const loadData = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [res, comp] = await Promise.all([
        fetchAudioAnalysis(projectId),
        fetchTranscriptComparison(projectId).catch(() => null)
      ]);
      setResult(res);
      setComparison(comp);
    } catch (err: any) {
      setResult({
        ok: false,
        error: err?.message || 'Failed to load audio analysis'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [projectId, refreshKey]);

  const data = result?.data;
  const isMissing = result?.status === 404 || (result?.error && result.error.includes('unavailable'));

  const utterances = data?.utterances || [];
  const totalWords = useMemo(() => {
    return utterances.reduce((acc: number, u: any) => acc + (u.words?.length || 0), 0);
  }, [utterances]);

  if (loading) {
    return (
      <div
        data-testid="audio-analyzer-loading"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 20px',
          color: 'var(--text-secondary)',
          gap: '12px'
        }}
      >
        <RefreshCw size={26} className="animate-spin" color="var(--accent-cyan)" />
        <span style={{ fontSize: '13px', fontWeight: 600 }}>Loading Audio Analysis Artifact...</span>
      </div>
    );
  }

  if (isMissing || !data) {
    return (
      <div
        data-testid="audio-analyzer-missing"
        style={{
          padding: '32px 24px',
          backgroundColor: 'var(--bg-elevated)',
          borderRadius: '8px',
          border: '1px solid var(--border-subtle)',
          textAlign: 'center',
          color: 'var(--text-secondary)'
        }}
      >
        <AlertTriangle size={32} color="#F59E0B" style={{ marginBottom: '10px' }} />
        <h4 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 6px 0' }}>
          Audio Analysis Not Generated Yet
        </h4>
        <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', margin: 0 }}>
          Click "Run Stage" or "Rerun Stage" above to transcribe and analyze the audio file.
        </p>
      </div>
    );
  }

  const subTabs = [
    { id: 'transcript', label: `Transcript (${utterances.length} utterances)`, icon: <FileText size={13} /> },
    { id: 'pauses', label: `Pauses & Rhythm (${data.pauses?.length || 0})`, icon: <Clock size={13} /> },
    { id: 'quality', label: 'Audio Quality', icon: <Sliders size={13} /> },
    { id: 'overview', label: 'Audio Metadata', icon: <Volume2 size={13} /> },
    { id: 'raw', label: 'Raw JSON', icon: <Code2 size={13} /> },
  ] as const;

  return (
    <div data-testid="audio-analyzer-view" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Sub-navigation Tabs */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          overflowX: 'auto',
          paddingBottom: '4px',
          borderBottom: '1px solid var(--border-subtle)'
        }}
      >
        {subTabs.map((tab) => {
          const active = activeSubTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id)}
              data-testid={`audio-subtab-${tab.id}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                height: '28px',
                padding: '0 12px',
                borderRadius: '6px',
                backgroundColor: active ? 'rgba(0, 216, 245, 0.15)' : 'transparent',
                border: active ? '1px solid rgba(0, 216, 245, 0.4)' : '1px solid transparent',
                color: active ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                fontSize: '12px',
                fontWeight: active ? 700 : 500,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease'
              }}
            >
              {tab.icon}
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* 1. TRANSCRIPT TAB */}
      {activeSubTab === 'transcript' && (
        <AudioTranscriptTab
          data={data}
          comparison={comparison}
          totalWords={totalWords}
        />
      )}

      {/* 2-5. OTHER TABS (PAUSES, QUALITY, OVERVIEW, RAW) */}
      {activeSubTab !== 'transcript' && (
        <AudioQualityPausesTabs
          activeSubTab={activeSubTab}
          data={data}
        />
      )}
    </div>
  );
};
