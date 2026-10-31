import React from 'react';
import { Music, UploadCloud, FolderOpen, FileAudio, CheckCircle2, X } from 'lucide-react';
import styles from './AudioUploadZone.module.css';

export interface AudioUploadZoneProps {
  audioFile: File | null;
  setAudioFile: React.Dispatch<React.SetStateAction<File | null>>;
  submitting: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  dragOver: boolean;
  setDragOver: React.Dispatch<React.SetStateAction<boolean>>;
  handleFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleDrop: (e: React.DragEvent) => void;
  formatFileSize: (bytes: number) => string;
}

export const AudioUploadZone: React.FC<AudioUploadZoneProps> = ({
  audioFile,
  setAudioFile,
  submitting,
  fileInputRef,
  dragOver,
  setDragOver,
  handleFileChange,
  handleDrop,
  formatFileSize
}) => {
  return (
    <div className={styles.container}>
      <div className={styles.headerRow}>
        <label htmlFor="audio-file" className={styles.label}>
          <Music size={14} color="var(--accent-cyan)" />
          <span>Audio Narration File <span className={styles.requiredAsterisk}>*</span></span>
        </label>
        <span className={styles.headerHint}>
          MP3, WAV, M4A, FLAC, AAC (≤ 500MB)
        </span>
      </div>

      <input
        ref={fileInputRef}
        id="audio-file"
        data-testid="audio-file-input"
        type="file"
        accept=".mp3,.wav,.m4a,.flac,.ogg,.aac,audio/*"
        className={styles.hiddenInput}
        onChange={handleFileChange}
        disabled={submitting}
      />

      {!audioFile ? (
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`${styles.dropzone} ${dragOver ? styles.dropzoneActive : styles.dropzoneIdle} ${submitting ? styles.dropzoneDisabled : ''}`}
        >
          <div className={styles.uploadIconCircle}>
            <UploadCloud size={22} />
          </div>

          <div className={styles.dropTitle}>
            Drop narration audio here, or click to browse
          </div>
          <div className={styles.dropSubtitle}>
            Telugu or English speech • Auto-detected by Whisper ASR
          </div>

          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
            className={styles.browseBtn}
          >
            <FolderOpen size={13} />
            Browse Files
          </button>
        </div>
      ) : (
        <div className={styles.fileCard}>
          <div className={styles.fileInfoLeft}>
            <div className={styles.fileIconCircle}>
              <FileAudio size={22} />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div title={audioFile.name} className={styles.fileName}>
                {audioFile.name}
              </div>
              <div className={styles.fileMetaRow}>
                <span className={styles.verifiedBadge}>
                  <CheckCircle2 size={13} />
                  Audio Verified
                </span>
                <span className={styles.metaDot}>•</span>
                <span>{formatFileSize(audioFile.size)}</span>
              </div>
            </div>
          </div>

          {!submitting && (
            <button
              type="button"
              onClick={() => setAudioFile(null)}
              className={styles.removeBtn}
              title="Remove file"
            >
              <X size={16} />
            </button>
          )}
        </div>
      )}
    </div>
  );
};
