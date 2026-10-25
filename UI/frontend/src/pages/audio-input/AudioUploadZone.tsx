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
          className={`${styles.dropzone} ${dragOver ? styles.dropzoneActive : styles.dropzoneIdle} ${submitting ? styles.dropzoneDisabled : ''}`}
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
