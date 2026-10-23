import React, { useState, useEffect, useMemo } from 'react';
import { 
  X, 
  ArrowLeft,
  FileAudio, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  Activity, 
  Copy, 
  Check, 
  RefreshCw, 
  Volume2, 
  Layers, 
  Languages, 
  Mic, 
  Sliders, 
  ShieldCheck, 
  Code2, 
  Play, 
  Info, 
  Sparkles,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  RotateCcw,
  Square,
  HelpCircle
} from 'lucide-react';
import { fetchAudioAnalysis, fetchTranscriptComparison, AudioAnalysisResult, TranscriptComparisonData } from '../services/api';
import { AgentAboutTab } from './AgentAboutTab';
import { TranscriptComparison } from './TranscriptComparison';

interface AudioAnalysisDrawerProps {
  projectId: string;
  isOpen: boolean;
  isFullPage?: boolean;
  onClose: () => void;
  onRunWorkflow?: () => void;
  onStopWorkflow?: () => void;
  isRunning?: boolean;
}

export const AudioAnalysisDrawer: React.FC<AudioAnalysisDrawerProps> = ({
  projectId,
  isOpen,
  isFullPage = false,
  onClose,
  onRunWorkflow,
  onStopWorkflow,
  isRunning = false
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'transcript' | 'pauses' | 'quality' | 'stages' | 'raw' | 'about'>('overview');
  const [loading, setLoading] = useState<boolean>(true);
  const [result, setResult] = useState<AudioAnalysisResult | null>(null);
  const [copiedJson, setCopiedJson] = useState<boolean>(false);
  const [expandedUtterances, setExpandedUtterances] = useState<Record<string, boolean>>({});
  const [rawJsonExpanded, setRawJsonExpanded] = useState<boolean>(true);
  const [wordSearch, setWordSearch] = useState<string>('');
  const [comparison, setComparison] = useState<TranscriptComparisonData | null>(null);

  const loadAnalysisData = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const res = await fetchAudioAnalysis(projectId);
      setResult(res);
      setComparison(await fetchTranscriptComparison(projectId));
      // Default to expand first 2 utterances
      if (res.data?.utterances && res.data.utterances.length > 0) {
        setExpandedUtterances({
          [res.data.utterances[0].utterance_id || '0']: true,
          ...(res.data.utterances[1] ? { [res.data.utterances[1].utterance_id || '1']: true } : {})
        });
      }
    } catch (err: any) {
      setResult({
        ok: false,
        error: err?.message || 'Unexpected failure loading audio analysis artifact'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadAnalysisData();
    }
  }, [projectId, isOpen]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const data = result?.data;
  const isError = !result?.ok;
  const isMissing = result?.status === 404 || (result?.error && result.error.includes('unavailable'));

  const handleCopyJson = () => {
    if (!data) return;
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopiedJson(true);
    setTimeout(() => setCopiedJson(false), 2000);
  };

  const toggleUtterance = (id: string) => {
    setExpandedUtterances((prev) => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  // Filtered utterances or words
  const utterances = data?.utterances || [];
  const filteredUtterances = useMemo(() => {
    if (!wordSearch.trim()) return utterances;
    const q = wordSearch.toLowerCase().trim();
    return utterances.filter((u: any) => 
      u.text?.toLowerCase().includes(q) ||
      (u.words && u.words.some((w: any) => w.text?.toLowerCase().includes(q)))
    );
  }, [utterances, wordSearch]);

  const totalWords = useMemo(() => {
    return utterances.reduce((acc: number, u: any) => acc + (u.words?.length || 0), 0);
  }, [utterances]);

  if (!isOpen) return null;

  const content = (
    <div
      data-testid={isFullPage ? "audio-analysis-full-view" : "audio-analysis-drawer"}
      style={isFullPage ? {
        width: '100%',
        minHeight: 'calc(100vh - 180px)',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: 'var(--font-sans)',
        color: 'var(--text-primary)'
      } : {
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: '740px',
        maxWidth: '96vw',
        backgroundColor: 'var(--bg-card)',
        borderLeft: '1px solid var(--border-card)',
        boxShadow: '-8px 0 32px rgba(0, 0, 0, 0.65)',
        zIndex: 120,
        display: 'flex',
        flexDirection: 'column',
        fontFamily: 'var(--font-sans)',
        color: 'var(--text-primary)',
        animation: 'slideInRight 0.24s cubic-bezier(0.16, 1, 0.3, 1)'
      }}
    >
      {/* Header */}
      <div style={{
        padding: isFullPage ? '16px 24px' : '20px 24px',
        borderBottom: '1px solid var(--border-card)',
        backgroundColor: 'var(--bg-elevated)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
          {/* Prominent Back Button */}
          <button
            onClick={onClose}
            data-testid="audio-analysis-back-btn"
            title="Back to Pipeline Flow (Esc)"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              backgroundColor: 'rgba(24, 144, 255, 0.12)',
              border: '1px solid rgba(24, 144, 255, 0.35)',
              borderRadius: '6px',
              color: '#38BDF8',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              marginRight: '4px'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(24, 144, 255, 0.22)';
              e.currentTarget.style.borderColor = '#38BDF8';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(24, 144, 255, 0.12)';
              e.currentTarget.style.borderColor = 'rgba(24, 144, 255, 0.35)';
            }}
          >
            <ArrowLeft size={16} />
            <span>Back to Pipeline</span>
          </button>

          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '8px',
            backgroundColor: 'rgba(24, 144, 255, 0.15)',
            border: '1px solid rgba(24, 144, 255, 0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent-blue)',
            flexShrink: 0
          }}>
            <FileAudio size={20} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <h3 style={{
                fontSize: '17px',
                fontWeight: 800,
                color: '#FFFFFF',
                margin: 0,
                letterSpacing: '-0.3px'
              }}>
                Audio Analysis Results
              </h3>

                {data?.schema_version && (
                  <span style={{
                    fontSize: '10.5px',
                    fontFamily: 'var(--font-mono)',
                    backgroundColor: 'rgba(0, 216, 245, 0.12)',
                    color: 'var(--accent-cyan)',
                    padding: '1px 6px',
                    borderRadius: '4px',
                    fontWeight: 700,
                    border: '1px solid rgba(0, 216, 245, 0.25)'
                  }}>
                    {data.schema_version}
                  </span>
                )}

                {data?.validation?.status && (
                  <span style={{
                    fontSize: '10.5px',
                    padding: '1px 6px',
                    borderRadius: '4px',
                    fontWeight: 700,
                    backgroundColor: data.validation.status === 'ok' ? 'rgba(82, 196, 26, 0.15)' : 'rgba(250, 173, 20, 0.15)',
                    color: data.validation.status === 'ok' ? 'var(--status-completed)' : 'var(--status-waiting)',
                    border: `1px solid ${data.validation.status === 'ok' ? 'rgba(82, 196, 26, 0.3)' : 'rgba(250, 173, 20, 0.3)'}`
                  }}>
                    {data.validation.status.toUpperCase()}
                  </span>
                )}
              </div>

              <div style={{
                fontSize: '12px',
                color: 'var(--text-muted)',
                marginTop: '3px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontFamily: 'var(--font-mono)'
              }}>
                <span>Project: <strong style={{ color: 'var(--text-secondary)' }}>{projectId}</strong></span>
                {result?.filename && (
                  <>
                    <span>•</span>
                    <span style={{ color: 'var(--accent-cyan)' }}>{result.filename}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {/* Run / Stop / Rerun Controls */}
            {isRunning && onStopWorkflow && (
              <button
                onClick={onStopWorkflow}
                data-testid="audio-analysis-stop-btn"
                title="Stop Audio Analysis Execution"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  backgroundColor: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  borderRadius: '4px',
                  color: '#EF4444',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#EF4444';
                  e.currentTarget.style.color = '#FFFFFF';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.15)';
                  e.currentTarget.style.color = '#EF4444';
                }}
              >
                <Square size={13} fill="currentColor" />
                <span>Stop Analysis</span>
              </button>
            )}

            {!isRunning && onRunWorkflow && (
              <button
                onClick={onRunWorkflow}
                data-testid="audio-analysis-run-btn"
                title={data ? "Rerun Audio Analysis" : "Run Audio Analysis"}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  backgroundColor: 'rgba(0, 216, 245, 0.15)',
                  border: '1px solid rgba(0, 216, 245, 0.35)',
                  borderRadius: '4px',
                  color: 'var(--accent-cyan)',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--accent-cyan)';
                  e.currentTarget.style.color = '#000000';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(0, 216, 245, 0.15)';
                  e.currentTarget.style.color = 'var(--accent-cyan)';
                }}
              >
                {data ? <RotateCcw size={13} /> : <Play size={13} fill="currentColor" />}
                <span>{data ? 'Rerun Analysis' : 'Run Analysis'}</span>
              </button>
            )}

            {data && (
              <button
                onClick={handleCopyJson}
                data-testid="copy-audio-json-btn"
                title="Copy Full JSON to clipboard"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  backgroundColor: copiedJson ? 'var(--status-completed-bg)' : 'rgba(255, 255, 255, 0.06)',
                  color: copiedJson ? 'var(--status-completed)' : 'var(--text-secondary)',
                  border: `1px solid ${copiedJson ? 'var(--status-completed-border)' : 'rgba(255, 255, 255, 0.12)'}`,
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                {copiedJson ? <Check size={13} /> : <Copy size={13} />}
                <span>{copiedJson ? 'Copied' : 'Copy JSON'}</span>
              </button>
            )}

            <button
              onClick={loadAnalysisData}
              title="Refresh artifact data"
              disabled={loading}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                color: 'var(--text-secondary)',
                cursor: loading ? 'not-allowed' : 'pointer',
                padding: '7px',
                borderRadius: '4px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>

            <button
              onClick={onClose}
              data-testid="close-audio-analysis-btn"
              title="Close panel (Esc)"
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '7px',
                borderRadius: '4px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'background-color 0.15s ease, color 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255, 77, 79, 0.18)';
                e.currentTarget.style.color = 'var(--status-failed)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.06)';
                e.currentTarget.style.color = 'var(--text-muted)';
              }}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Navigation Tabs (visible when data is available or about tab inspected) */}
        {!loading && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            padding: '0 20px',
            backgroundColor: 'var(--bg-elevated)',
            borderBottom: '1px solid var(--border-card)',
            gap: '8px',
            overflowX: 'auto',
            flexShrink: 0
          }}>
            {[
              ...(data ? [
                { id: 'overview', label: 'Overview & Metadata', icon: <Info size={13} /> },
                { id: 'transcript', label: `Transcript & Words (${totalWords})`, icon: <Languages size={13} /> },
                { id: 'pauses', label: `Pauses (${data?.pauses?.length || 0})`, icon: <Volume2 size={13} /> },
                { id: 'quality', label: 'Quality & Validation', icon: <ShieldCheck size={13} /> },
                { id: 'stages', label: `14 Stages (${data?.stages?.length || 0})`, icon: <Layers size={13} /> },
                { id: 'raw', label: 'Raw JSON', icon: <Code2 size={13} /> }
              ] : []),
              { id: 'about', label: 'About Agent', icon: <HelpCircle size={13} /> }
            ].map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  data-testid={`audio-tab-${tab.id}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '12px 14px',
                    background: 'transparent',
                    border: 'none',
                    borderBottom: isActive ? '2px solid var(--accent-blue)' : '2px solid transparent',
                    color: isActive ? '#FFFFFF' : 'var(--text-muted)',
                    fontWeight: isActive ? 700 : 500,
                    fontSize: '12.5px',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <span style={{ color: isActive ? 'var(--accent-blue)' : 'var(--text-muted)' }}>
                    {tab.icon}
                  </span>
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Drawer Body Area */}
        <div 
          data-testid="audio-analysis-content-stream"
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
          }}
        >
          {/* ABOUT TAB VIEW */}
          {activeTab === 'about' && (
            <AgentAboutTab
              stageId="analyzer"
              agentId="audio_analyzer"
              isFullPage={isFullPage}
            />
          )}

          {/* 1. LOADING STATE */}
          {loading && activeTab !== 'about' && (
            <div 
              data-testid="audio-analysis-loading"
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '64px 20px',
                color: 'var(--text-secondary)',
                gap: '14px'
              }}
            >
              <RefreshCw size={28} className="animate-spin" color="var(--accent-blue)" />
              <div style={{ fontSize: '14px', fontWeight: 600 }}>
                Reading saved audio analysis artifact...
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                projects/{projectId}/audio-analysis.json
              </div>
            </div>
          )}

          {/* 2. MISSING ARTIFACT STATE */}
          {!loading && isMissing && activeTab !== 'about' && (
            <div 
              data-testid="audio-analysis-missing"
              style={{
                backgroundColor: 'rgba(250, 173, 20, 0.08)',
                border: '1px solid rgba(250, 173, 20, 0.25)',
                borderRadius: '8px',
                padding: '28px 24px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
                gap: '14px'
              }}
            >
              <div style={{
                width: '44px',
                height: '44px',
                borderRadius: '50%',
                backgroundColor: 'rgba(250, 173, 20, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--status-waiting)'
              }}>
                <AlertTriangle size={24} />
              </div>

              <div>
                <h4 style={{ fontSize: '16px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
                  Audio Analysis Artifact Unavailable
                </h4>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '6px', maxWidth: '480px', lineHeight: 1.5 }}>
                  The artifact <code style={{ color: 'var(--accent-cyan)', backgroundColor: 'rgba(0,0,0,0.3)', padding: '2px 5px', borderRadius: '3px' }}>audio-analysis.json</code> does not exist for project <strong style={{ color: '#FFFFFF' }}>{projectId}</strong>.
                </p>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                  The Audio Analysis workflow has not been executed yet. Existing data was not overwritten.
                </p>
              </div>

              {onRunWorkflow && (
                <button
                  onClick={onRunWorkflow}
                  data-testid="run-audio-analysis-workflow-btn"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '8px 18px',
                    backgroundColor: 'var(--accent-blue)',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '4px',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(24, 144, 255, 0.35)',
                    marginTop: '8px'
                  }}
                >
                  <Play size={14} fill="#FFFFFF" />
                  <span>Run Audio Analysis Workflow</span>
                </button>
              )}
            </div>
          )}

          {/* 3. ERROR / UNREADABLE STATE */}
          {!loading && isError && !isMissing && activeTab !== 'about' && (
            <div 
              data-testid="audio-analysis-error"
              style={{
                backgroundColor: 'rgba(255, 77, 79, 0.08)',
                border: '1px solid rgba(255, 77, 79, 0.25)',
                borderRadius: '8px',
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <AlertTriangle size={20} color="var(--status-failed)" />
                <h4 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--status-failed)', margin: 0 }}>
                  Failed to Load Audio Analysis Artifact
                </h4>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
                {result?.error || 'An unexpected error occurred while parsing the saved audio-analysis.json file.'}
              </p>
              <button
                onClick={loadAnalysisData}
                style={{
                  alignSelf: 'flex-start',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 14px',
                  backgroundColor: 'rgba(255, 255, 255, 0.08)',
                  color: '#FFFFFF',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: '4px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  marginTop: '4px'
                }}
              >
                <RefreshCw size={13} />
                <span>Retry Loading</span>
              </button>
            </div>
          )}

          {/* 4. SUCCESS STATE: STRUCTURED VIEWS */}
          {!loading && data && activeTab !== 'about' && (
            <>
              {/* TAB 1: OVERVIEW & AUDIO METADATA */}
              {activeTab === 'overview' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* File Metadata Grid */}
                  <div style={{
                    backgroundColor: '#0C1526',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: '8px',
                    padding: '18px 20px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                      <Volume2 size={16} color="var(--accent-blue)" />
                      <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
                        Audio Source Metadata
                      </h4>
                    </div>

                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                      gap: '14px'
                    }}>
                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>File Name</span>
                        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                          {data.source?.file || '—'}
                        </div>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Duration</span>
                        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent-cyan)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                          {data.source?.duration_seconds ? `${data.source.duration_seconds.toFixed(2)}s` : '—'}
                        </div>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Format / Codec</span>
                        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                          {data.source?.codec ? `${data.source.codec.toUpperCase()} (${data.source.container || 'audio'})` : '—'}
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
                          {data.source?.channels === 1 ? '1 (Mono)' : data.source?.channels === 2 ? '2 (Stereo)' : `${data.source?.channels || '—'} ch`}
                        </div>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>File Size</span>
                        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                          {data.source?.size_bytes ? `${(data.source.size_bytes / 1024).toFixed(1)} KB` : '—'}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Speech & Language Information */}
                  <div style={{
                    backgroundColor: '#0C1526',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: '8px',
                    padding: '18px 20px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                      <Languages size={16} color="var(--accent-cyan)" />
                      <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
                        Speech & Language Detection
                      </h4>
                    </div>

                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                      gap: '14px'
                    }}>
                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Detected Language</span>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: '#FFFFFF', marginTop: '2px' }}>
                          {data.transcription?.language?.code ? `${data.transcription.language.code.toUpperCase()} (Telugu)` : '—'}
                        </div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {data.transcription?.language?.source || 'Auto-detected / Config'}
                        </span>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>ASR Engine & Model</span>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: '#FFFFFF', marginTop: '2px' }}>
                          {data.transcription?.asr?.engine ? `${data.transcription.asr.engine} (${data.transcription.asr.model || 'model'})` : 'faster-whisper'}
                        </div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          compute: {data.transcription?.asr?.compute_type || 'int8'} • device: {data.transcription?.asr?.device || 'cpu'}
                        </span>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Word Alignment Method</span>
                        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent-blue)', marginTop: '2px' }}>
                          {data.processing?.alignment_status || 'word_timestamps'}
                        </div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {data.processing?.alignment_method?.slice(0, 50) || 'Model-inferred alignment'}...
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Summary Metric Counters */}
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, 1fr)',
                    gap: '12px'
                  }}>
                    <div style={{
                      backgroundColor: '#0C1526',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '8px',
                      padding: '14px'
                    }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Total Utterances</span>
                      <div style={{ fontSize: '20px', fontWeight: 800, color: '#FFFFFF', marginTop: '3px' }}>
                        {utterances.length}
                      </div>
                    </div>

                    <div style={{
                      backgroundColor: '#0C1526',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '8px',
                      padding: '14px'
                    }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Total Words</span>
                      <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--accent-blue)', marginTop: '3px' }}>
                        {totalWords}
                      </div>
                    </div>

                    <div style={{
                      backgroundColor: '#0C1526',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '8px',
                      padding: '14px'
                    }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Detected Silences</span>
                      <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--accent-cyan)', marginTop: '3px' }}>
                        {data.pauses?.length || 0}
                      </div>
                    </div>

                    <div style={{
                      backgroundColor: '#0C1526',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '8px',
                      padding: '14px'
                    }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Max Volume</span>
                      <div style={{ fontSize: '20px', fontWeight: 800, color: '#FFFFFF', marginTop: '3px', fontFamily: 'var(--font-mono)' }}>
                        {data.quality?.max_volume_db !== undefined ? `${data.quality.max_volume_db} dB` : '—'}
                      </div>
                    </div>
                  </div>

                  {/* Quick Transcript Preview */}
                  {data.transcription?.full_text && (
                    <div style={{
                      backgroundColor: '#0C1526',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '8px',
                      padding: '18px 20px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)' }}>
                          Transcript Preview (Telugu / English)
                        </span>
                        <button
                          onClick={() => setActiveTab('transcript')}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--accent-blue)',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer'
                          }}
                        >
                          View Word Timestamps →
                        </button>
                      </div>
                      <p style={{
                        fontSize: '13.5px',
                        color: 'var(--text-primary)',
                        lineHeight: 1.6,
                        margin: 0,
                        backgroundColor: '#080E1A',
                        padding: '12px 14px',
                        borderRadius: '6px',
                        border: '1px solid rgba(255, 255, 255, 0.05)'
                      }}>
                        {data.transcription.full_text}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: TRANSCRIPT & WORD-LEVEL TIMESTAMPS */}
              {activeTab === 'transcript' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {/* Full Text Box */}
                  {data.transcription?.full_text && (
                    <div style={{
                      backgroundColor: '#0C1526',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '8px',
                      padding: '16px 18px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)' }}>
                          Complete Transcript
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {totalWords} words • {data.transcription.full_text.length} chars
                        </span>
                      </div>
                      <div style={{
                        fontSize: '14px',
                        color: '#FFFFFF',
                        lineHeight: 1.6,
                        backgroundColor: '#080E1A',
                        padding: '12px 14px',
                        borderRadius: '6px',
                        border: '1px solid rgba(255, 255, 255, 0.05)'
                      }}>
                        {data.transcription.full_text}
                      </div>

                      {/* Associated Files */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        marginTop: '10px',
                        fontSize: '11px',
                        color: 'var(--text-muted)',
                        fontFamily: 'var(--font-mono)',
                        flexWrap: 'wrap'
                      }}>
                        {data.transcription.raw_file && (
                          <span>raw: <strong>{data.transcription.raw_file}</strong></span>
                        )}
                        {data.transcription.corrected_file && (
                          <span>corrected: <strong>{data.transcription.corrected_file}</strong></span>
                        )}
                        <span>edited_by_user: <strong>{String(data.transcription.edited_by_user || false)}</strong></span>
                      </div>
                    </div>
                  )}

                  {/* Raw Whisper output next to the final LLM-corrected transcript */}
                  {comparison && <TranscriptComparison data={comparison} />}

                  {/* Word Search Filter */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <input
                      type="text"
                      placeholder="Filter words or utterances..."
                      value={wordSearch}
                      onChange={(e) => setWordSearch(e.target.value)}
                      style={{
                        flex: 1,
                        padding: '8px 14px',
                        backgroundColor: '#0C1526',
                        border: '1px solid rgba(255, 255, 255, 0.12)',
                        borderRadius: '6px',
                        color: '#FFFFFF',
                        fontSize: '13px',
                        outline: 'none'
                      }}
                    />
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

                  {/* Utterance List with Word Badges */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {filteredUtterances.map((u: any, idx: number) => {
                      const uId = u.utterance_id || String(u.id || idx);
                      const isExpanded = !!expandedUtterances[uId];
                      return (
                        <div
                          key={uId}
                          data-testid={`utterance-card-${idx}`}
                          style={{
                            backgroundColor: '#0C1526',
                            border: '1px solid rgba(255, 255, 255, 0.08)',
                            borderRadius: '8px',
                            overflow: 'hidden'
                          }}
                        >
                          {/* Utterance Header */}
                          <div
                            onClick={() => toggleUtterance(uId)}
                            style={{
                              padding: '12px 16px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              cursor: 'pointer',
                              backgroundColor: isExpanded ? '#0E192E' : 'transparent',
                              borderBottom: isExpanded ? '1px solid rgba(255, 255, 255, 0.06)' : 'none',
                              userSelect: 'none'
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <span style={{ color: 'var(--text-muted)' }}>
                                {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                              </span>
                              <span style={{
                                fontSize: '11px',
                                fontFamily: 'var(--font-mono)',
                                fontWeight: 700,
                                color: 'var(--accent-cyan)',
                                backgroundColor: 'rgba(0, 216, 245, 0.1)',
                                padding: '1px 6px',
                                borderRadius: '4px'
                              }}>
                                #{String(u.id !== undefined ? u.id + 1 : idx + 1).padStart(2, '0')}
                              </span>
                              <span style={{
                                fontSize: '13px',
                                fontWeight: 600,
                                color: '#FFFFFF',
                                maxWidth: '420px',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis'
                              }}>
                                {u.text}
                              </span>
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                              <span style={{
                                fontSize: '11px',
                                fontFamily: 'var(--font-mono)',
                                color: 'var(--text-muted)'
                              }}>
                                {u.start_seconds?.toFixed(2)}s – {u.end_seconds?.toFixed(2)}s
                              </span>
                              <span style={{
                                fontSize: '11px',
                                color: 'var(--accent-blue)',
                                fontWeight: 600
                              }}>
                                {u.words?.length || 0} words
                              </span>
                            </div>
                          </div>

                          {/* Expanded Words Grid */}
                          {isExpanded && (
                            <div style={{ padding: '14px 16px', backgroundColor: '#09101C' }}>
                              <div style={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                gap: '8px'
                              }}>
                                {u.words && u.words.map((w: any, wIdx: number) => (
                                  <div
                                    key={wIdx}
                                    style={{
                                      backgroundColor: '#0D1628',
                                      border: '1px solid rgba(255, 255, 255, 0.1)',
                                      borderRadius: '6px',
                                      padding: '6px 10px',
                                      display: 'flex',
                                      flexDirection: 'column',
                                      gap: '2px',
                                      minWidth: '70px'
                                    }}
                                  >
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                                      <span style={{ fontSize: '13px', fontWeight: 700, color: '#FFFFFF' }}>
                                        {w.text}
                                      </span>
                                      {w.edit && (
                                        <span style={{
                                          fontSize: '9px',
                                          fontWeight: 700,
                                          backgroundColor: 'rgba(24, 144, 255, 0.2)',
                                          color: 'var(--accent-blue)',
                                          padding: '0 4px',
                                          borderRadius: '3px'
                                        }}>
                                          {w.edit}
                                        </span>
                                      )}
                                    </div>
                                    <div style={{
                                      fontSize: '10.5px',
                                      fontFamily: 'var(--font-mono)',
                                      color: 'var(--text-muted)'
                                    }}>
                                      {w.start_seconds?.toFixed(2)}s – {w.end_seconds?.toFixed(2)}s
                                    </div>
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
              )}

              {/* TAB 3: PAUSES & SPEECH RHYTHM */}
              {activeTab === 'pauses' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{
                    backgroundColor: '#0C1526',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: '8px',
                    padding: '16px 20px'
                  }}>
                    <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
                      Pause & Rhythm Detection Parameters
                    </h4>
                    <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Method: {data.processing?.pause_detection?.method || 'ffmpeg silencedetect'} • 
                      Min Duration: {data.processing?.pause_detection?.min_seconds || 0.35}s • 
                      Threshold: {data.processing?.pause_detection?.threshold_db || -35} dB
                    </p>
                  </div>

                  {/* Pauses List */}
                  {data.pauses && data.pauses.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {data.pauses.map((p: any, idx: number) => (
                        <div
                          key={idx}
                          style={{
                            backgroundColor: '#0C1526',
                            border: '1px solid rgba(255, 255, 255, 0.06)',
                            borderRadius: '6px',
                            padding: '12px 16px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{
                              fontSize: '11px',
                              fontFamily: 'var(--font-mono)',
                              color: 'var(--accent-cyan)',
                              backgroundColor: 'rgba(0, 216, 245, 0.1)',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontWeight: 700
                            }}>
                              P-{String(idx + 1).padStart(2, '0')}
                            </span>
                            <span style={{ fontSize: '13px', color: '#FFFFFF', fontWeight: 600 }}>
                              {p.kind || 'silence'} ({p.source || 'ffmpeg'})
                            </span>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                            <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                              {p.start_seconds?.toFixed(3)}s – {p.end_seconds?.toFixed(3)}s
                            </span>
                            <span style={{
                              fontSize: '12px',
                              fontFamily: 'var(--font-mono)',
                              fontWeight: 700,
                              color: 'var(--accent-blue)'
                            }}>
                              {p.duration_seconds?.toFixed(3)}s
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{
                      padding: '32px',
                      textAlign: 'center',
                      color: 'var(--text-muted)',
                      fontSize: '13px',
                      backgroundColor: '#0C1526',
                      borderRadius: '8px'
                    }}>
                      No pauses or silences recorded in this artifact.
                    </div>
                  )}
                </div>
              )}

              {/* TAB 4: QUALITY & VALIDATION */}
              {activeTab === 'quality' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                  {/* Quality Metrics */}
                  <div style={{
                    backgroundColor: '#0C1526',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: '8px',
                    padding: '18px 20px'
                  }}>
                    <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF', marginBottom: '14px' }}>
                      Audio Quality Validation
                    </h4>
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                      gap: '14px'
                    }}>
                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Quality Status</span>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--status-completed)', marginTop: '2px' }}>
                          {data.quality?.status || 'measured'}
                        </div>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Max Volume</span>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                          {data.quality?.max_volume_db !== undefined ? `${data.quality.max_volume_db} dB` : '—'}
                        </div>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Mean Volume</span>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                          {data.quality?.mean_volume_db !== undefined ? `${data.quality.mean_volume_db} dB` : '—'}
                        </div>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Uncertain Words</span>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--status-waiting)', marginTop: '2px' }}>
                          {data.quality?.uncertain_words ?? '0'}
                        </div>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Unresolved Words</span>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                          {data.quality?.unresolved_words ?? '0'}
                        </div>
                      </div>

                      <div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Uncertain Share</span>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                          {data.quality?.uncertain_share !== undefined ? `${(data.quality.uncertain_share * 100).toFixed(1)}%` : '—'}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Validation Notes & Warnings */}
                  <div style={{
                    backgroundColor: '#0C1526',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: '8px',
                    padding: '18px 20px'
                  }}>
                    <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF', marginBottom: '10px' }}>
                      Validation Diagnostics
                    </h4>
                    {data.validation?.notes && data.validation.notes.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {data.validation.notes.map((note: any, idx: number) => (
                          <div
                            key={idx}
                            style={{
                              backgroundColor: '#080E1A',
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
                      <div style={{ fontSize: '13px', color: 'var(--status-completed)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <CheckCircle2 size={16} />
                        <span>0 errors, 0 warnings. Analysis passed all validation checks.</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 5: 14 STAGES FLOW */}
              {activeTab === 'stages' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {data.stages && data.stages.map((st: any, idx: number) => (
                    <div
                      key={idx}
                      style={{
                        backgroundColor: '#0C1526',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: '6px',
                        padding: '12px 16px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '14px'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{
                          fontSize: '11px',
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          backgroundColor: 'rgba(24, 144, 255, 0.15)',
                          color: 'var(--accent-blue)',
                          padding: '2px 8px',
                          borderRadius: '4px'
                        }}>
                          {String(st.n || idx + 1).padStart(2, '0')}
                        </span>

                        <div>
                          <div style={{ fontSize: '13px', fontWeight: 700, color: '#FFFFFF' }}>
                            {st.name}
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                            {st.detail || '—'}
                          </div>
                        </div>
                      </div>

                      <span style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        backgroundColor: st.status === 'completed' ? 'rgba(82, 196, 26, 0.15)' : 'rgba(24, 144, 255, 0.15)',
                        color: st.status === 'completed' ? 'var(--status-completed)' : 'var(--accent-blue)'
                      }}>
                        {st.status || 'completed'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* TAB 6: RAW JSON VIEWER */}
              {activeTab === 'raw' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    backgroundColor: '#0C1526',
                    borderRadius: '6px',
                    border: '1px solid rgba(255, 255, 255, 0.08)'
                  }}>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      JSON Size: {JSON.stringify(data).length.toLocaleString()} bytes • Keys: {Object.keys(data).length}
                    </span>

                    <button
                      onClick={handleCopyJson}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 10px',
                        backgroundColor: 'var(--accent-blue)',
                        color: '#FFFFFF',
                        border: 'none',
                        borderRadius: '4px',
                        fontSize: '11.5px',
                        fontWeight: 600,
                        cursor: 'pointer'
                      }}
                    >
                      {copiedJson ? <Check size={12} /> : <Copy size={12} />}
                      <span>{copiedJson ? 'Copied' : 'Copy Full JSON'}</span>
                    </button>
                  </div>

                  <div style={{
                    backgroundColor: '#04070D',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '8px',
                    padding: '16px',
                    overflowX: 'auto',
                    maxHeight: '600px',
                    overflowY: 'auto'
                  }}>
                    <pre
                      data-testid="audio-analysis-raw-json"
                      style={{
                        margin: 0,
                        fontSize: '12px',
                        fontFamily: 'var(--font-mono)',
                        color: '#40A9FF',
                        lineHeight: 1.5,
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all'
                      }}
                    >
                      {JSON.stringify(data, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
    </div>
  );

  if (isFullPage) {
    return content;
  }

  return (
    <>
      <div 
        data-testid="audio-analysis-backdrop"
        onClick={onClose}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 5, 12, 0.65)',
          backdropFilter: 'blur(3px)',
          zIndex: 110,
          transition: 'opacity 0.2s ease'
        }}
      />
      {content}
    </>
  );
};
