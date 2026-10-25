import React from 'react';

export interface CreateProjectModalProps {
  show: boolean;
  onClose: () => void;
  newTitle: string;
  setNewTitle: (val: string) => void;
  newAspect: '16:9' | '9:16';
  setNewAspect: (val: '16:9' | '9:16') => void;
  onSubmit: (e: React.FormEvent) => void;
}

export const CreateProjectModal: React.FC<CreateProjectModalProps> = ({
  show,
  onClose,
  newTitle,
  setNewTitle,
  newAspect,
  setNewAspect,
  onSubmit
}) => {
  if (!show) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        style={{
          backgroundColor: 'var(--bg-card)',
          border: '1.5px solid var(--border-card)',
          borderRadius: 'var(--radius-md)',
          padding: '24px',
          maxWidth: '460px',
          width: '90%',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
        }}
      >
        <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px' }}>
          Create New Production Project
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '20px' }}>
          Initialize a clean workspace for audio-to-video automated rendering.
        </p>

        <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Project Title / Name
            </label>
            <input
              type="text"
              required
              placeholder="e.g. tech_trends_explained"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              style={{
                width: '100%',
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '4px',
                padding: '8px 12px',
                color: 'var(--text-primary)',
                fontSize: '13px',
                outline: 'none',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Aspect Ratio
            </label>
            <div style={{ display: 'flex', gap: '10px' }}>
              <label
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '8px',
                  backgroundColor: newAspect === '16:9' ? 'rgba(24, 144, 255, 0.15)' : 'var(--bg-elevated)',
                  border: `1px solid ${newAspect === '16:9' ? 'var(--accent-blue)' : 'var(--border-subtle)'}`,
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  color: newAspect === '16:9' ? 'var(--accent-blue)' : 'var(--text-secondary)',
                  fontWeight: newAspect === '16:9' ? 600 : 400,
                }}
              >
                <input
                  type="radio"
                  name="aspect"
                  checked={newAspect === '16:9'}
                  onChange={() => setNewAspect('16:9')}
                  style={{ display: 'none' }}
                />
                <span>16:9 Landscape</span>
              </label>

              <label
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '8px',
                  backgroundColor: newAspect === '9:16' ? 'rgba(24, 144, 255, 0.15)' : 'var(--bg-elevated)',
                  border: `1px solid ${newAspect === '9:16' ? 'var(--accent-blue)' : 'var(--border-subtle)'}`,
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  color: newAspect === '9:16' ? 'var(--accent-blue)' : 'var(--text-secondary)',
                  fontWeight: newAspect === '9:16' ? 600 : 400,
                }}
              >
                <input
                  type="radio"
                  name="aspect"
                  checked={newAspect === '9:16'}
                  onChange={() => setNewAspect('9:16')}
                  style={{ display: 'none' }}
                />
                <span>9:16 Shorts / Reel</span>
              </label>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 16px',
                backgroundColor: 'transparent',
                border: '1px solid var(--border-card)',
                borderRadius: '4px',
                color: 'var(--text-secondary)',
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              style={{
                padding: '8px 18px',
                backgroundColor: 'var(--accent-blue)',
                border: 'none',
                borderRadius: '4px',
                color: '#FFFFFF',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Create Project
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
