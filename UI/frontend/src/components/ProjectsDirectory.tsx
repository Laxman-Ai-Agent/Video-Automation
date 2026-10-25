import React, { useMemo, useState } from 'react';
import styles from './ProjectsDirectory.module.css';
import {
  ChevronUp,
  FolderOpen,
  Plus,
  RefreshCw,
  Search,
} from 'lucide-react';
import { deleteProject } from '../services/api';
import { CreateProjectModal } from './projects-directory/CreateProjectModal';
import { DeleteProjectModal } from './projects-directory/DeleteProjectModal';
import { ProjectTableRow } from './projects-directory/ProjectTableRow';

export interface ProjectsDirectoryProps {
  projects: any[];
  activeProjectId?: string;
  onSelectProject: (projectId: string) => void;
  onOpenLivePipeline?: () => void;
  onRefreshProjects?: () => Promise<void> | void;
  onDeleteProject?: (projectId: string) => Promise<boolean>;
  onCreateProject?: (title: string, aspect: string) => void;
  onClose?: () => void;
  title?: string;
  subtitle?: string;
  showCloseButton?: boolean;
}

export const ProjectsDirectory: React.FC<ProjectsDirectoryProps> = ({
  projects,
  activeProjectId,
  onSelectProject,
  onOpenLivePipeline,
  onRefreshProjects,
  onDeleteProject,
  onCreateProject,
  onClose,
  title = 'All Projects Directory',
  subtitle = 'All localized workspaces, timeline runs, and render outputs. Click View to open project details, or Delete to remove.',
  showCloseButton = false,
}) => {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [projectToDelete, setProjectToDelete] = useState<{ id: string; name: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);

  // Modal for creating project if onCreateProject is provided
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newTitle, setNewTitle] = useState<string>('');
  const [newAspect, setNewAspect] = useState<'16:9' | '9:16'>('16:9');

  // Filter projects by query
  const filteredProjects = useMemo(() => {
    if (!searchQuery.trim()) return projects;
    const q = searchQuery.toLowerCase().trim();
    return projects.filter((p) => {
      const id = String(p.id || p.project_id || p.name || '').toLowerCase();
      const name = String(p.name || p.title || '').toLowerCase();
      const status = String(p.status || '').toLowerCase();
      const aspect = String(p.aspect || '').toLowerCase();
      return id.includes(q) || name.includes(q) || status.includes(q) || aspect.includes(q);
    });
  }, [projects, searchQuery]);

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !onCreateProject) return;
    onCreateProject(newTitle.trim(), newAspect);
    setNewTitle('');
    setShowCreateModal(false);
  };

  const handleConfirmDelete = async () => {
    if (!projectToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      let success = false;
      if (onDeleteProject) {
        success = await onDeleteProject(projectToDelete.id);
      } else {
        success = await deleteProject(projectToDelete.id);
        if (onRefreshProjects) await onRefreshProjects();
      }

      if (success) {
        setDeleteSuccess(`Project "${projectToDelete.name}" was permanently deleted.`);
        setTimeout(() => setDeleteSuccess(null), 4000);
        setProjectToDelete(null);
      } else {
        setDeleteError(`Could not delete "${projectToDelete.name}". It may be currently running or locked.`);
      }
    } catch (err: any) {
      setDeleteError(err?.message || 'Failed to delete project.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div
      id="all-projects-table-section"
      data-testid="all-projects-table-container"
      className={styles.container}
    >
      {/* Header of Table: Title, Search, Refresh, Close */}
      <div className={styles.header}>
        <div>
          <div className={styles.titleGroup}>
            <FolderOpen size={20} color="var(--accent-blue)" />
            <h3 className={styles.title}>
              {title}
            </h3>
            <span className={styles.countBadge}>
              {filteredProjects.length} of {projects.length} Total
            </span>
          </div>
          <p className={styles.subtitle}>
            {subtitle}
          </p>
        </div>

        {/* Search and Action Bar */}
        <div className={styles.searchBar}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-card)',
              borderRadius: 'var(--radius-sm)',
              padding: '6px 12px',
              gap: '8px',
              minWidth: '240px',
            }}
          >
            <Search size={14} color="var(--text-muted)" />
            <input
              type="text"
              placeholder="Search by name, ID, or status..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                backgroundColor: 'transparent',
                border: 'none',
                outline: 'none',
                color: 'var(--text-primary)',
                fontSize: '12px',
                width: '100%',
              }}
              data-testid="all-projects-search-input"
            />
          </div>

          {onRefreshProjects && (
            <button
              onClick={async () => {
                await onRefreshProjects();
              }}
              title="Refresh Projects List"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '8px',
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-card)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              <RefreshCw size={14} />
            </button>
          )}

          {onCreateProject && (
            <button
              onClick={() => setShowCreateModal(true)}
              title="Create New Project"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 14px',
                backgroundColor: 'var(--accent-blue)',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                color: '#FFFFFF',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <Plus size={14} />
              <span>New Project</span>
            </button>
          )}

          {showCloseButton && onClose && (
            <button
              onClick={onClose}
              title="Hide Table"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '7px 12px',
                backgroundColor: 'transparent',
                border: '1px solid var(--border-card)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-muted)',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              <span>Hide Table</span>
              <ChevronUp size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Feedback alerts if any */}
      {deleteSuccess && (
        <div
          style={{
            marginBottom: '16px',
            padding: '10px 14px',
            backgroundColor: 'var(--status-completed-bg, rgba(52, 211, 153, 0.15))',
            border: '1px solid var(--status-completed-border, rgba(52, 211, 153, 0.4))',
            borderRadius: '4px',
            color: 'var(--status-completed, #34d399)',
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          {deleteSuccess}
        </div>
      )}

      {deleteError && (
        <div
          style={{
            marginBottom: '16px',
            padding: '10px 14px',
            backgroundColor: 'rgba(255, 77, 79, 0.1)',
            border: '1px solid var(--status-failed, #f87171)',
            borderRadius: '4px',
            color: 'var(--status-failed, #f87171)',
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          {deleteError}
        </div>
      )}

      {/* TABLE CONTAINER */}
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.th}>Project ID &amp; Name</th>
              <th className={styles.th} style={{ width: '100px' }}>Aspect</th>
              <th className={styles.th} style={{ width: '130px' }}>Status</th>
              <th className={styles.th} style={{ width: '180px' }}>Created / Workspace</th>
              <th className={styles.th} style={{ width: '180px', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredProjects.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No projects found matching your search.
                </td>
              </tr>
            ) : (
              filteredProjects.map((proj) => (
                <ProjectTableRow
                  key={proj.id || proj.project_id || proj.name}
                  proj={proj}
                  isActive={(proj.id || proj.project_id || proj.name) === activeProjectId}
                  onSelectProject={onSelectProject}
                  onOpenLivePipeline={onOpenLivePipeline}
                  setProjectToDelete={setProjectToDelete}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* CREATE PROJECT MODAL */}
      <CreateProjectModal
        show={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        newTitle={newTitle}
        setNewTitle={setNewTitle}
        newAspect={newAspect}
        setNewAspect={setNewAspect}
        onSubmit={handleCreateSubmit}
      />

      {/* DELETE CONFIRMATION MODAL */}
      <DeleteProjectModal
        projectToDelete={projectToDelete}
        isDeleting={isDeleting}
        onCancel={() => {
          setProjectToDelete(null);
          setDeleteError(null);
        }}
        onConfirm={handleConfirmDelete}
      />
    </div>
  );
};

export default ProjectsDirectory;
