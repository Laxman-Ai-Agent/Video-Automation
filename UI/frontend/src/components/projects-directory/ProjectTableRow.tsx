import React from 'react';
import { FileAudio, Clock, Eye, Trash2 } from 'lucide-react';

export interface ProjectTableRowProps {
  proj: any;
  isActive: boolean;
  onSelectProject: (projectId: string) => void;
  onOpenLivePipeline?: () => void;
  setProjectToDelete: (proj: { id: string; name: string }) => void;
}

export const ProjectTableRow: React.FC<ProjectTableRowProps> = ({
  proj,
  isActive,
  onSelectProject,
  onOpenLivePipeline,
  setProjectToDelete
}) => {
  const pid = proj.id || proj.project_id || proj.name;
  const titleText = proj.name || proj.title || pid;
  const aspect = proj.aspect || '16:9';
  const status = proj.status || (isActive ? 'active' : 'ready');
  const createdAt = proj.created_at
    ? new Date(proj.created_at).toLocaleString()
    : 'Active Workspace';

  return (
    <tr
      key={pid}
      data-testid={`project-row-${pid}`}
      style={{
        borderBottom: '1px solid var(--border-subtle)',
        backgroundColor: isActive ? 'rgba(24, 144, 255, 0.05)' : 'transparent',
        transition: 'background-color 0.15s ease',
      }}
    >
      {/* Project ID & Name */}
      <td style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '4px',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: isActive ? 'var(--accent-blue)' : 'var(--text-muted)',
              flexShrink: 0,
            }}
          >
            <FileAudio size={16} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                {titleText}
              </span>
              {isActive && (
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    color: 'var(--accent-blue)',
                    backgroundColor: 'rgba(24, 144, 255, 0.12)',
                    padding: '1px 5px',
                    borderRadius: '3px',
                  }}
                >
                  ACTIVE
                </span>
              )}
            </div>
            <div
              style={{
                fontSize: '11px',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                marginTop: '2px',
              }}
            >
              {pid}
            </div>
          </div>
        </div>
      </td>

      {/* Aspect */}
      <td style={{ padding: '12px 16px' }}>
        <span
          style={{
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-secondary)',
            backgroundColor: 'var(--bg-elevated)',
            padding: '2px 6px',
            borderRadius: '3px',
            border: '1px solid var(--border-subtle)',
          }}
        >
          {aspect}
        </span>
      </td>

      {/* Status */}
      <td style={{ padding: '12px 16px' }}>
        <span
          style={{
            fontSize: '11px',
            fontWeight: 600,
            color:
              status === 'completed'
                ? 'var(--status-completed, #34d399)'
                : status === 'running'
                ? 'var(--status-running, #38bdf8)'
                : 'var(--accent-blue)',
            backgroundColor:
              status === 'completed'
                ? 'var(--status-completed-bg, rgba(52, 211, 153, 0.15))'
                : status === 'running'
                ? 'var(--status-running-bg, rgba(56, 189, 248, 0.15))'
                : 'var(--bg-elevated)',
            padding: '3px 8px',
            borderRadius: '3px',
            border: '1px solid var(--border-subtle)',
            textTransform: 'capitalize',
          }}
        >
          {status}
        </span>
      </td>

      {/* Created Date */}
      <td style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontSize: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Clock size={12} color="var(--text-muted)" />
          <span>{createdAt}</span>
        </div>
      </td>

      {/* Actions: View and Delete */}
      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          {/* View Button */}
          <button
            data-testid={`view-project-btn-${pid}`}
            onClick={() => {
              onSelectProject(pid);
              if (onOpenLivePipeline) {
                onOpenLivePipeline();
              }
            }}
            title="View Project Details and Pipeline"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              backgroundColor: 'rgba(24, 144, 255, 0.12)',
              border: '1px solid rgba(24, 144, 255, 0.35)',
              borderRadius: '4px',
              color: 'var(--accent-blue)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <Eye size={13} />
            <span>View</span>
          </button>

          {/* Delete Button */}
          <button
            data-testid={`delete-project-btn-${pid}`}
            onClick={() => setProjectToDelete({ id: pid, name: titleText })}
            title="Delete Project Permanently"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 10px',
              backgroundColor: 'rgba(255, 77, 79, 0.08)',
              border: '1px solid rgba(255, 77, 79, 0.3)',
              borderRadius: '4px',
              color: 'var(--status-failed, #f87171)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <Trash2 size={13} />
            <span>Delete</span>
          </button>
        </div>
      </td>
    </tr>
  );
};
