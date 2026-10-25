import React from 'react';
import { AlertTriangle, Loader2, Trash2 } from 'lucide-react';

export interface DeleteProjectModalProps {
  projectToDelete: { id: string; name: string } | null;
  isDeleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export const DeleteProjectModal: React.FC<DeleteProjectModalProps> = ({
  projectToDelete,
  isDeleting,
  onCancel,
  onConfirm
}) => {
  if (!projectToDelete) return null;

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
        data-testid="delete-confirmation-dialog"
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              backgroundColor: 'rgba(255, 77, 79, 0.15)',
              border: '1px solid rgba(255, 77, 79, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--status-failed, #f87171)',
              flexShrink: 0,
            }}
          >
            <AlertTriangle size={22} />
          </div>

          <div>
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
              Confirm Permanent Deletion
            </h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              This action is irreversible
            </p>
          </div>
        </div>

        <div
          style={{
            backgroundColor: 'var(--bg-elevated)',
            padding: '12px 14px',
            borderRadius: '4px',
            border: '1px solid var(--border-subtle)',
            fontSize: '13px',
            lineHeight: 1.5,
            color: 'var(--text-secondary)',
            marginBottom: '20px',
          }}
        >
          Are you sure you want to permanently delete project{' '}
          <strong style={{ color: 'var(--text-primary)' }}>"{projectToDelete.name}"</strong>?
          <div
            style={{
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)',
              marginTop: '4px',
            }}
          >
            ID: {projectToDelete.id}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--status-failed, #f87171)', marginTop: '8px' }}>
            All audio files, timeline edits, rendered videos, and workspace metadata will be permanently deleted.
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button
            type="button"
            disabled={isDeleting}
            onClick={onCancel}
            style={{
              padding: '8px 16px',
              backgroundColor: 'transparent',
              border: '1px solid var(--border-card)',
              borderRadius: '4px',
              color: 'var(--text-secondary)',
              fontSize: '13px',
              fontWeight: 600,
              cursor: isDeleting ? 'not-allowed' : 'pointer',
            }}
          >
            Cancel
          </button>

          <button
            type="button"
            data-testid="confirm-delete-project-btn"
            disabled={isDeleting}
            onClick={onConfirm}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 18px',
              backgroundColor: 'var(--status-failed, #f87171)',
              border: 'none',
              borderRadius: '4px',
              color: '#FFFFFF',
              fontSize: '13px',
              fontWeight: 600,
              cursor: isDeleting ? 'not-allowed' : 'pointer',
            }}
          >
            {isDeleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
            <span>{isDeleting ? 'Deleting…' : 'Delete Permanently'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
