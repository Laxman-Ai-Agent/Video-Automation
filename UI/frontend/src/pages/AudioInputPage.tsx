import React, { useState, useRef } from 'react';
import { DEFAULT_MEDIA, MediaMix, total } from '../services/mediaMix';
import { 
  Film, 
  AlertCircle, 
  Zap, 
  Sparkles 
} from 'lucide-react';
import { AudioUploadZone } from './audio-input/AudioUploadZone';
import { ProjectOptionsConfig } from './audio-input/ProjectOptionsConfig';
import styles from './AudioInputPage.module.css';

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
                className={styles.titleInput}
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
            {/* COLUMN 1: Audio Narration File Upload */}
            <AudioUploadZone
              audioFile={audioFile}
              setAudioFile={setAudioFile}
              submitting={submitting}
              fileInputRef={fileInputRef}
              dragOver={dragOver}
              setDragOver={setDragOver}
              handleFileChange={handleFileChange}
              handleDrop={handleDrop}
              formatFileSize={formatFileSize}
            />

            {/* COLUMN 2: Video Aspect Ratio & Visual Engine Options */}
            <ProjectOptionsConfig
              aspect={aspect}
              setAspect={setAspect}
              media={media}
              setMedia={setMedia}
              reusableTemplates={reusableTemplates}
              setReusableTemplates={setReusableTemplates}
              submitting={submitting}
            />
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
                className={styles.cancelBtn}
              >
                Cancel
              </button>

              <button
                type="submit"
                data-testid="analyze-button"
                disabled={submitting}
                className={styles.submitBtn}
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

export default AudioInputPage;
