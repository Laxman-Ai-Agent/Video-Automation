import React, { useState, useRef } from 'react';
import { MediaMixPicker } from '../components/MediaMixPicker';
import { DEFAULT_MEDIA, MediaMix, total } from '../services/mediaMix';
import { 
  UploadCloud, 
  FileAudio, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle, 
  X, 
  FolderOpen,
  Film,
  Tv,
  Smartphone,
  Sliders,
  Check,
  Zap,
  Music
} from 'lucide-react';

interface AudioInputPageProps {
  onAnalyze: (
    title: string, 
    audioFile: File, 
    aspect: string,
    reusableTemplates: boolean,
    media: MediaMix
  ) => Promise<void>;
  onCancel: () => void;
}

const SUPPORTED_EXTS = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac'];

export const AudioInputPage: React.FC<AudioInputPageProps> = ({
  onAnalyze,
  onCancel
}) => {
  const [title, setTitle] = useState('');
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [aspect, setAspect] = useState<'16:9' | '9:16'>('16:9');
  const [reusableTemplates, setReusableTemplates] = useState(false);
  const [media, setMedia] = useState<MediaMix>(DEFAULT_MEDIA);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndSetFile = (file: File) => {
    setError(null);
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!SUPPORTED_EXTS.includes(ext)) {
      setError(`Unsupported audio format (${ext}). Supported formats: ${SUPPORTED_EXTS.join(', ')}`);
      return;
    }
    setAudioFile(file);
    if (!title.trim()) {
      const baseName = file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
      setTitle(baseName.charAt(0).toUpperCase() + baseName.slice(1));
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setError('Project Title is required. Please enter a title for your video project.');
      return;
    }

    if (!audioFile) {
      setError('Audio File is required. Please select or drop an audio file (.mp3, .wav, .m4a, etc.).');
      return;
    }

    if (total(media) !== 100) {
      setError(`The media mix must add up to 100% (it adds up to ${total(media)}%).`);
      return;
    }

    try {
      setSubmitting(true);
      await onAnalyze(trimmedTitle, audioFile, aspect, reusableTemplates, media);
    } catch (err: any) {
      setError(err?.message || 'Failed to initialize project and start analysis.');
      setSubmitting(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div style={{
      width: '100%',
      maxWidth: '1280px',
      margin: '0 auto',
      display: 'flex',
      flexDirection: 'column',
      gap: '14px',
      fontFamily: 'var(--font-sans)'
    }}>
      {/* Top Banner / Heading Area */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '8px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            backgroundColor: 'var(--status-running-bg)',
            border: '1px solid rgba(24, 144, 255, 0.25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent-blue)'
          }}>
            <Film size={16} />
          </div>
          <div>
            <h2 style={{
              fontSize: '16px',
              fontWeight: 700,
              color: 'var(--text-primary)',
              margin: 0,
              letterSpacing: '-0.3px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <span>Create New Video Project</span>
              <span style={{
                fontSize: '11px',
                fontWeight: 600,
                backgroundColor: 'rgba(0, 216, 245, 0.1)',
                color: 'var(--accent-cyan)',
                padding: '2px 8px',
                borderRadius: '12px',
                border: '1px solid rgba(0, 216, 245, 0.25)'
              }}>
                Automated Production
              </span>
            </h2>
            <p style={{
              fontSize: '12px',
              color: 'var(--text-muted)',
              margin: '2px 0 0 0'
            }}>
              Set project details, upload narration audio, and configure video dimensions for automated generation.
            </p>
          </div>
        </div>
      </div>

      {/* Main Form Container */}
      <div style={{
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-card)',
        boxShadow: 'var(--shadow-card)',
        overflow: 'hidden'
      }}>
        <form onSubmit={handleSubmit} style={{ padding: '18px 22px' }}>
          {/* Validation / API Error Banner */}
          {error && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: 'var(--status-failed-bg)',
              border: '1px solid var(--status-failed-border)',
              borderRadius: '4px',
              padding: '9px 14px',
              marginBottom: '14px',
              color: 'var(--status-failed)',
              fontSize: '12.5px',
              fontWeight: 500
            }}>
              <AlertCircle size={15} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {/* Top Section: Project Title Input */}
          <div style={{ marginBottom: '16px' }}>
            <label 
              htmlFor="project-title"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '12.5px',
                fontWeight: 600,
                color: 'var(--text-primary)',
                marginBottom: '6px'
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Film size={13} color="var(--accent-blue)" />
                Project Title <span style={{ color: 'var(--accent-red)' }}>*</span>
              </span>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 400 }}>
                Unique workspace name & video metadata
              </span>
            </label>

            <div style={{ position: 'relative' }}>
              <input
                id="project-title"
                data-testid="project-title-input"
                type="text"
                placeholder="e.g. Telugu Tech Insights — Episode 01"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={submitting}
                style={{
                  width: '100%',
                  height: '38px',
                  padding: '0 14px',
                  fontSize: '13.5px',
                  borderRadius: '4px',
                  border: '1px solid var(--border-card)',
                  outline: 'none',
                  transition: 'all 0.15s ease',
                  backgroundColor: 'var(--bg-app)',
                  color: 'var(--text-primary)',
                  boxSizing: 'border-box'
                }}
                onFocus={(e) => { 
                  e.currentTarget.style.borderColor = 'var(--accent-blue)'; 
                  e.currentTarget.style.boxShadow = '0 0 0 2px rgba(24, 144, 255, 0.2)'; 
                }}
                onBlur={(e) => { 
                  e.currentTarget.style.borderColor = 'var(--border-card)'; 
                  e.currentTarget.style.boxShadow = 'none'; 
                }}
              />
            </div>
          </div>

          {/* Middle Section: Side-by-Side 2-Column Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
            gap: '16px',
            alignItems: 'stretch'
          }}>
            {/* COLUMN 1: Prominent Audio Narration File Upload */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-card)',
              borderRadius: '6px',
              padding: '14px 16px'
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '10px'
              }}>
                <label 
                  htmlFor="audio-file"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '12.5px',
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    margin: 0
                  }}
                >
                  <Music size={14} color="var(--accent-cyan)" />
                  <span>Audio Narration File <span style={{ color: 'var(--accent-red)' }}>*</span></span>
                </label>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  MP3, WAV, M4A, FLAC, AAC (≤ 500MB)
                </span>
              </div>

              <input
                ref={fileInputRef}
                id="audio-file"
                data-testid="audio-file-input"
                type="file"
                accept=".mp3,.wav,.m4a,.flac,.ogg,.aac,audio/*"
                style={{ display: 'none' }}
                onChange={handleFileChange}
                disabled={submitting}
              />

              {!audioFile ? (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  style={{
                    flex: 1,
                    minHeight: '120px',
                    border: `1.5px dashed ${dragOver ? 'var(--accent-blue)' : 'var(--border-card)'}`,
                    borderRadius: '5px',
                    padding: '16px 14px',
                    textAlign: 'center',
                    backgroundColor: dragOver ? 'var(--status-running-bg)' : 'var(--bg-card)',
                    cursor: submitting ? 'not-allowed' : 'pointer',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px'
                  }}
                  onMouseEnter={(e) => { if (!dragOver) e.currentTarget.style.borderColor = 'var(--accent-blue)'; }}
                  onMouseLeave={(e) => { if (!dragOver) e.currentTarget.style.borderColor = 'var(--border-card)'; }}
                >
                  <div style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--status-running-bg)',
                    border: '1px solid rgba(24, 144, 255, 0.25)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--accent-blue)'
                  }}>
                    <UploadCloud size={20} />
                  </div>

                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    Drop narration audio here, or click to browse
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Telugu or English speech • Auto-detected by Whisper ASR
                  </div>

                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      marginTop: '4px',
                      padding: '4px 12px',
                      backgroundColor: 'var(--bg-elevated)',
                      border: '1px solid var(--border-card)',
                      borderRadius: '4px',
                      color: 'var(--accent-blue)',
                      fontSize: '11.5px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    <FolderOpen size={12} />
                    Browse Files
                  </button>
                </div>
              ) : (
                <div style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 16px',
                  backgroundColor: 'var(--status-completed-bg)',
                  border: '1px solid var(--status-completed-border)',
                  borderRadius: '5px',
                  gap: '12px',
                  boxShadow: '0 2px 8px rgba(16, 185, 129, 0.08)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0, flex: 1 }}>
                    <div style={{
                      width: '40px',
                      height: '40px',
                      borderRadius: '6px',
                      backgroundColor: 'var(--status-completed)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#FFFFFF',
                      flexShrink: 0
                    }}>
                      <FileAudio size={22} />
                    </div>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div 
                        title={audioFile.name}
                        style={{ 
                          fontSize: '13.5px', 
                          fontWeight: 600, 
                          color: 'var(--text-primary)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis'
                        }}
                      >
                        {audioFile.name}
                      </div>
                      <div style={{ 
                        fontSize: '11.5px', 
                        color: 'var(--text-secondary)', 
                        marginTop: '3px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}>
                        <span style={{ 
                          fontWeight: 700, 
                          color: 'var(--status-completed)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px'
                        }}>
                          <CheckCircle2 size={12} />
                          Audio Verified
                        </span>
                        <span>•</span>
                        <span>{formatFileSize(audioFile.size)}</span>
                      </div>
                    </div>
                  </div>

                  {!submitting && (
                    <button
                      type="button"
                      onClick={() => setAudioFile(null)}
                      style={{
                        background: 'none',
                        border: '1px solid var(--border-card)',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        padding: '6px',
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        backgroundColor: 'var(--bg-card)',
                        transition: 'all 0.15s ease'
                      }}
                      title="Remove file"
                      onMouseEnter={(e) => { 
                        e.currentTarget.style.color = 'var(--status-failed)'; 
                        e.currentTarget.style.borderColor = 'var(--status-failed-border)';
                      }}
                      onMouseLeave={(e) => { 
                        e.currentTarget.style.color = 'var(--text-muted)'; 
                        e.currentTarget.style.borderColor = 'var(--border-card)';
                      }}
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* COLUMN 2: Video Aspect Ratio & Visual Engine Options */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-card)',
              borderRadius: '6px',
              padding: '14px 16px',
              gap: '12px'
            }}>
              {/* Aspect Ratio Selection */}
              <div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '8px'
                }}>
                  <label style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '12.5px',
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    margin: 0
                  }}>
                    <Tv size={14} color="var(--accent-blue)" />
                    <span>Video Aspect Ratio <span style={{ color: 'var(--accent-red)' }}>*</span></span>
                  </label>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Output Dimensions
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  {/* 16:9 Landscape Card */}
                  <div
                    onClick={() => setAspect('16:9')}
                    role="button"
                    tabIndex={0}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '5px',
                      border: `1.5px solid ${aspect === '16:9' ? 'var(--accent-blue)' : 'var(--border-card)'}`,
                      backgroundColor: aspect === '16:9' ? 'var(--status-running-bg)' : 'var(--bg-card)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      transition: 'all 0.15s ease',
                      boxShadow: aspect === '16:9' ? '0 0 10px rgba(24, 144, 255, 0.15)' : 'none',
                      position: 'relative'
                    }}
                  >
                    <div style={{
                      width: '28px',
                      height: '18px',
                      border: `2px solid ${aspect === '16:9' ? 'var(--accent-blue)' : 'var(--text-muted)'}`,
                      borderRadius: '2px',
                      backgroundColor: aspect === '16:9' ? 'rgba(24, 144, 255, 0.25)' : 'transparent',
                      flexShrink: 0
                    }} />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ 
                        fontSize: '12.5px', 
                        fontWeight: 700, 
                        color: aspect === '16:9' ? 'var(--accent-blue)' : 'var(--text-primary)' 
                      }}>
                        16:9 Widescreen
                      </div>
                      <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                        YouTube & Desktop (1920×1080)
                      </div>
                    </div>
                    {aspect === '16:9' && (
                      <span style={{
                        width: '16px',
                        height: '16px',
                        borderRadius: '50%',
                        backgroundColor: 'var(--accent-blue)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#FFFFFF'
                      }}>
                        <Check size={10} strokeWidth={3} />
                      </span>
                    )}
                  </div>

                  {/* 9:16 Portrait Card */}
                  <div
                    onClick={() => setAspect('9:16')}
                    role="button"
                    tabIndex={0}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '5px',
                      border: `1.5px solid ${aspect === '9:16' ? 'var(--accent-blue)' : 'var(--border-card)'}`,
                      backgroundColor: aspect === '9:16' ? 'var(--status-running-bg)' : 'var(--bg-card)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      transition: 'all 0.15s ease',
                      boxShadow: aspect === '9:16' ? '0 0 10px rgba(24, 144, 255, 0.15)' : 'none',
                      position: 'relative'
                    }}
                  >
                    <div style={{
                      width: '18px',
                      height: '26px',
                      border: `2px solid ${aspect === '9:16' ? 'var(--accent-blue)' : 'var(--text-muted)'}`,
                      borderRadius: '2px',
                      backgroundColor: aspect === '9:16' ? 'rgba(24, 144, 255, 0.25)' : 'transparent',
                      flexShrink: 0
                    }} />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ 
                        fontSize: '12.5px', 
                        fontWeight: 700, 
                        color: aspect === '9:16' ? 'var(--accent-blue)' : 'var(--text-primary)' 
                      }}>
                        9:16 Vertical
                      </div>
                      <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                        Shorts & Reels (1080×1920)
                      </div>
                    </div>
                    {aspect === '9:16' && (
                      <span style={{
                        width: '16px',
                        height: '16px',
                        borderRadius: '50%',
                        backgroundColor: 'var(--accent-blue)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#FFFFFF'
                      }}>
                        <Check size={10} strokeWidth={3} />
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Visual Engine Options */}
              <div style={{
                borderTop: '1px solid var(--border-subtle)',
                paddingTop: '10px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ 
                    fontSize: '11.5px', 
                    fontWeight: 700, 
                    color: 'var(--text-secondary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px'
                  }}>
                    <Sliders size={12} color="var(--accent-blue)" />
                    Visual Engine Features
                  </span>
                  <span style={{ fontSize: '10.5px', color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)' }}>
                    Motion-Only Mode
                  </span>
                </div>

                <MediaMixPicker value={media} onChange={setMedia} disabled={submitting} />

                <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '6px' }}>
                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={reusableTemplates}
                      onChange={(e) => setReusableTemplates(e.target.checked)}
                      style={{ marginTop: '2px', accentColor: 'var(--accent-blue)' }}
                    />
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        Reusable Motion Templates Cache
                      </div>
                      <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                        Reuses cached Remotion template ASTs for accelerated timeline build & render.
                      </div>
                    </div>
                  </label>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Action Row: Summary and Primary Action Button */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderTop: '1px solid var(--border-card)',
            paddingTop: '14px',
            marginTop: '16px',
            flexWrap: 'wrap',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11.5px', color: 'var(--text-muted)' }}>
              <Zap size={14} color="var(--accent-cyan)" />
              <span>Full automated workflow: Whisper ASR → Scene Segmentation → Motion Planning → Remotion 30 FPS Render</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <button
                type="button"
                onClick={onCancel}
                disabled={submitting}
                style={{
                  padding: '8px 18px',
                  borderRadius: '4px',
                  border: '1px solid var(--border-card)',
                  backgroundColor: 'transparent',
                  color: 'var(--text-secondary)',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: submitting ? 'not-allowed' : 'pointer',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={(e) => { if (!submitting) e.currentTarget.style.color = 'var(--text-primary)'; }}
                onMouseLeave={(e) => { if (!submitting) e.currentTarget.style.color = 'var(--text-secondary)'; }}
              >
                Cancel
              </button>

              <button
                type="submit"
                data-testid="analyze-button"
                disabled={submitting}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 26px',
                  borderRadius: '4px',
                  border: 'none',
                  backgroundColor: 'var(--accent-blue)',
                  color: '#FFFFFF',
                  fontSize: '13.5px',
                  fontWeight: 600,
                  cursor: submitting ? 'not-allowed' : 'pointer',
                  boxShadow: '0 2px 10px rgba(24, 144, 255, 0.4)',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={(e) => { if (!submitting) e.currentTarget.style.backgroundColor = '#40A9FF'; }}
                onMouseLeave={(e) => { if (!submitting) e.currentTarget.style.backgroundColor = 'var(--accent-blue)'; }}
              >
                {submitting ? (
                  <>
                    <span className="animate-spin" style={{ display: 'inline-block', width: '14px', height: '14px', border: '2px solid #FFFFFF', borderTopColor: 'transparent', borderRadius: '50%' }} />
                    <span>Ingesting & Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    <span>Analyze Audio</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
