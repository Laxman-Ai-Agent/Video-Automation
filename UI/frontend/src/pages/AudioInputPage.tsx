import React, { useState, useRef } from 'react';
import { DEFAULT_MEDIA, MediaMix } from '../services/mediaMix';
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
    <div className={styles.pageContainer}>
      {/* Top Banner / Heading Area */}
      <div className={styles.headerArea}>
        <div className={styles.headerLeft}>
          <div className={styles.headerIconWrapper}>
            <Film size={16} />
          </div>
          <div className={styles.headerText}>
            <div className={styles.headerTitleRow}>
              <h2 className={styles.title}>New Motion Video Project</h2>
              <span className={styles.stageBadge}>STAGE 01 • INGESTION</span>
            </div>
            <p className={styles.subtitle}>
              Upload spoken audio narration to generate frame-accurate 30 FPS Remotion animated video.
            </p>
          </div>
        </div>
      </div>

      {/* Main Single Form Box */}
      <form onSubmit={handleSubmit} className={styles.formContainer}>
        {/* Error Alert Banner */}
        {error && (
          <div className={styles.errorBanner}>
            <AlertCircle size={15} className={styles.errorIcon} />
            <div className={styles.errorText}>{error}</div>
          </div>
        )}

        {/* 1. PROJECT TITLE INPUT */}
        <div className={styles.sectionBlock}>
          <label className={styles.label}>
            <span>Project Title <span className={styles.requiredAsterisk}>*</span></span>
            <span className={styles.labelHint}>Used for export file names and timeline scene title headers</span>
          </label>
          <input
            type="text"
            data-testid="project-title-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. History of Rome - Episode 1"
            className={styles.titleInput}
            disabled={submitting}
            autoFocus
          />
        </div>

        {/* 2. MIDDLE TWO-COLUMN STUDIO GRID */}
        <div className={styles.twoColGrid}>
          {/* LEFT SIDE: Audio Narration File Upload Zone */}
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

          {/* RIGHT SIDE: Video Options & Settings */}
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

        {/* 3. BOTTOM ACTION ROW: Summary & Primary Analyze Button */}
        <div className={styles.footerRow}>
          <div className={styles.footerWorkflow}>
            <Zap size={13} color="var(--accent-cyan)" />
            <span>Full automated workflow: Whisper ASR → Scene Segmentation → Motion Planning → Remotion 30 FPS Render</span>
          </div>

          <div className={styles.footerActions}>
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
                  <span className={styles.spinner} />
                  <span>Ingesting &amp; Analyzing...</span>
                </>
              ) : (
                <>
                  <Sparkles size={15} />
                  <span>Analyze Audio</span>
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};

export default AudioInputPage;
