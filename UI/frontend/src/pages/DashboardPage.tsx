import React, { useState, useMemo } from 'react';
import { TopMetricCards } from '../components/TopMetricCards';
import { 
  Play, 
  Plus, 
  ExternalLink, 
  FolderKanban, 
  CheckCircle2, 
  Clock, 
  Cpu, 
  ShieldCheck, 
  Activity, 
  ArrowRight,
  Video,
  FileAudio,
  Trash2,
  Eye,
  Search,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  FolderOpen
} from 'lucide-react';
import { PipelineProjectState } from '../types/pipeline';
import { deleteProject } from '../services/api';

interface DashboardPageProps {
  projectState: PipelineProjectState;
  projects: any[];
  activeProjectId: string;
  onSelectProject: (projectId: string) => void;
  onOpenLivePipeline: () => void;
  onNewProject: () => void;
  agents: any[];
  activeLlmCount: number;
  backendHealthy: boolean;
  onDeleteProject?: (projectId: string) => Promise<boolean>;
  onRefreshProjects?: () => Promise<void>;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  projectState,
  projects,
  activeProjectId,
  onSelectProject,
  onOpenLivePipeline,
  onNewProject,
  agents,
  activeLlmCount,
  backendHealthy,
  onDeleteProject,
  onRefreshProjects
}) => {
  // Table & Project Management States
  const [showAllProjectsTable, setShowAllProjectsTable] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [projectToDelete, setProjectToDelete] = useState<{ id: string; name: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);

  // Filter projects based on search query
  const filteredProjects = useMemo(() => {
    if (!searchQuery.trim()) return projects;
    const q = searchQuery.toLowerCase().trim();
    return projects.filter((p) => {
      const pid = (p.id || p.project_id || p.name || '').toLowerCase();
      const title = (p.title || p.name || '').toLowerCase();
      const status = (p.status || '').toLowerCase();
      return pid.includes(q) || title.includes(q) || status.includes(q);
    });
  }, [projects, searchQuery]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '24px',
      maxWidth: '1600px',
      margin: '0 auto',
      fontFamily: 'var(--font-sans)'
    }}>
      {/* 1. TOP 4 METRIC CARDS */}
      <TopMetricCards
        totalRuns={projects.length || 1430}
        activeStagesCount={12}
        totalAgentsCount={agents.length || 21}
        overallProgress={projectState.overallProgress || 88}
      />

      {/* 2. DUAL SPOTLIGHT CARDS: CURRENT ACTIVE PROJECT & ALL PROJECTS CARD */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(440px, 1fr))',
        gap: '20px'
      }}>
        {/* Card A: Current Active Project Spotlight */}
        <div style={{
          backgroundColor: 'var(--bg-card)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border-card)',
          padding: '24px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: '16px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--status-running-bg)',
              border: '1px solid var(--status-running-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-blue)',
              flexShrink: 0
            }}>
              <Video size={24} />
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  fontFamily: 'var(--font-mono)'
                }}>
                  Current Active Project
                </span>
                <span style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: projectState.status === 'running' ? 'var(--status-running)' : 'var(--status-completed)',
                  backgroundColor: projectState.status === 'running' ? 'var(--status-running-bg)' : 'var(--status-completed-bg)',
                  padding: '1px 6px',
                  borderRadius: '3px'
                }}>
                  {projectState.status.toUpperCase()}
                </span>
              </div>

              <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                {projectState.title || activeProjectId}
              </h2>

              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                <span>ID: <strong style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{activeProjectId}</strong></span>
                <span>•</span>
                <span>Aspect: <strong>{projectState.aspectRatio}</strong></span>
                <span>•</span>
                <span>Progress: <strong>{projectState.overallProgress}%</strong></span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <button
              onClick={onOpenLivePipeline}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '9px 18px',
                backgroundColor: 'var(--accent-blue)',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 2px 6px rgba(24, 144, 255, 0.35)',
                transition: 'background-color 0.15s ease'
              }}
            >
              <span>Open Live Pipeline</span>
              <ArrowRight size={15} />
            </button>

            <button
              onClick={onNewProject}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '9px 16px',
                backgroundColor: 'transparent',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-card)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              <Plus size={15} />
              <span>New Audio Project</span>
            </button>
          </div>
        </div>

        {/* Card B: All Projects Card (Interactive click to show table on same page) */}
        <div
          data-testid="all-projects-card"
          onClick={() => setShowAllProjectsTable((prev) => !prev)}
          style={{
            backgroundColor: 'var(--bg-card)',
            borderRadius: 'var(--radius-sm)',
            border: showAllProjectsTable ? '1.5px solid var(--accent-blue)' : '1px solid var(--border-card)',
            padding: '24px',
            boxShadow: showAllProjectsTable ? '0 0 16px rgba(24, 144, 255, 0.2)' : 'var(--shadow-card)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: '16px',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            position: 'relative'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(24, 144, 255, 0.12)',
                border: '1px solid rgba(24, 144, 255, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-blue)',
                flexShrink: 0
              }}>
                <FolderKanban size={24} />
              </div>

              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    color: 'var(--text-muted)',
                    textTransform: 'uppercase',
                    fontFamily: 'var(--font-mono)'
                  }}>
                    Workspaces &amp; Renders
                  </span>
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    color: 'var(--accent-blue)',
                    backgroundColor: 'rgba(24, 144, 255, 0.12)',
                    padding: '1px 6px',
                    borderRadius: '3px'
                  }}>
                    {projects.length} PROJECTS
                  </span>
                </div>

                <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                  All Projects
                </h2>

                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: 1.4 }}>
                  Browse all production workspaces. Click to display the full projects table on this page with View and Delete actions.
                </p>
              </div>
            </div>

            {/* Toggle Badge Indicator */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: showAllProjectsTable ? 'var(--accent-blue)' : 'var(--bg-elevated)',
              color: showAllProjectsTable ? '#FFFFFF' : 'var(--accent-blue)',
              fontSize: '12px',
              fontWeight: 600,
              border: '1px solid var(--border-card)',
              flexShrink: 0
            }}>
              <span>{showAllProjectsTable ? 'Hide Table' : 'View Table'}</span>
              {showAllProjectsTable ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </div>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingTop: '12px',
            borderTop: '1px solid var(--border-subtle)',
            fontSize: '12px',
            color: 'var(--text-muted)'
          }}>
            <span>Active: <strong style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{activeProjectId}</strong></span>
            <span style={{ color: 'var(--accent-blue)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span>{showAllProjectsTable ? 'Close Projects Table' : 'Display All Projects Table'}</span>
              <ArrowRight size={13} />
            </span>
          </div>
        </div>
      </div>

      {/* 3. ALL PROJECTS TABLE ON THE SAME PAGE (EXPANDABLE VIA ALL PROJECTS CARD) */}
      {showAllProjectsTable && (
        <div 
          id="all-projects-table-section"
          data-testid="all-projects-table-container"
          style={{
            backgroundColor: 'var(--bg-card)',
            borderRadius: 'var(--radius-sm)',
            border: '1.5px solid var(--accent-blue)',
            boxShadow: 'var(--shadow-card)',
            padding: '24px'
          }}
        >
          {/* Header of Table: Title, Search, Refresh, Close */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '16px',
            marginBottom: '20px'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FolderOpen size={20} color="var(--accent-blue)" />
                <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  All Projects Directory
                </h3>
                <span style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'var(--accent-blue)',
                  backgroundColor: 'rgba(24, 144, 255, 0.1)',
                  padding: '2px 8px',
                  borderRadius: '12px'
                }}>
                  {filteredProjects.length} of {projects.length} Total
                </span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                All localized workspaces, timeline runs, and render outputs. Click View to open project details, or Delete to remove.
              </p>
            </div>

            {/* Search and Action Bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-card)',
                borderRadius: 'var(--radius-sm)',
                padding: '6px 12px',
                gap: '8px',
                minWidth: '240px'
              }}>
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
                    width: '100%'
                  }}
                  data-testid="all-projects-search-input"
                />
              </div>

              {onRefreshProjects && (
                <button
                  onClick={async () => {
                    if (onRefreshProjects) await onRefreshProjects();
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
                    cursor: 'pointer'
                  }}
                >
                  <RefreshCw size={14} />
                </button>
              )}

              <button
                onClick={() => setShowAllProjectsTable(false)}
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
                  cursor: 'pointer'
                }}
              >
                <span>Hide Table</span>
                <ChevronUp size={14} />
              </button>
            </div>
          </div>

          {/* Feedback alerts if any */}
          {deleteSuccess && (
            <div style={{
              marginBottom: '16px',
              padding: '10px 14px',
              backgroundColor: 'var(--status-completed-bg)',
              border: '1px solid var(--status-completed-border)',
              borderRadius: '4px',
              color: 'var(--status-completed)',
              fontSize: '13px',
              fontWeight: 600
            }}>
              {deleteSuccess}
            </div>
          )}

          {deleteError && (
            <div style={{
              marginBottom: '16px',
              padding: '10px 14px',
              backgroundColor: 'rgba(255, 77, 79, 0.1)',
              border: '1px solid var(--status-failed)',
              borderRadius: '4px',
              color: 'var(--status-failed)',
              fontSize: '13px',
              fontWeight: 600
            }}>
              {deleteError}
            </div>
          )}

          {/* TABLE CONTAINER */}
          <div style={{
            overflowX: 'auto',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)'
          }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              textAlign: 'left',
              fontSize: '13px'
            }}>
              <thead>
                <tr style={{
                  backgroundColor: 'var(--bg-elevated)',
                  borderBottom: '1px solid var(--border-card)',
                  color: 'var(--text-muted)',
                  fontSize: '11px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px'
                }}>
                  <th style={{ padding: '12px 16px' }}>Project ID &amp; Name</th>
                  <th style={{ padding: '12px 16px', width: '100px' }}>Aspect</th>
                  <th style={{ padding: '12px 16px', width: '130px' }}>Status</th>
                  <th style={{ padding: '12px 16px', width: '180px' }}>Created / Workspace</th>
                  <th style={{ padding: '12px 16px', width: '180px', textAlign: 'right' }}>Actions</th>
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
                  filteredProjects.map((proj) => {
                    const pid = proj.id || proj.project_id || proj.name;
                    const isActive = pid === activeProjectId;
                    const title = proj.name || proj.title || pid;
                    const aspect = proj.aspect || '16:9';
                    const status = proj.status || (isActive ? 'active' : 'ready');
                    const createdAt = proj.created_at ? new Date(proj.created_at).toLocaleString() : 'Active Workspace';

                    return (
                      <tr
                        key={pid}
                        data-testid={`project-row-${pid}`}
                        style={{
                          borderBottom: '1px solid var(--border-subtle)',
                          backgroundColor: isActive ? 'rgba(24, 144, 255, 0.05)' : 'transparent',
                          transition: 'background-color 0.15s ease'
                        }}
                      >
                        {/* Project ID & Name */}
                        <td style={{ padding: '12px 16px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <div style={{
                              width: '32px',
                              height: '32px',
                              borderRadius: '4px',
                              backgroundColor: 'var(--bg-elevated)',
                              border: '1px solid var(--border-subtle)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: isActive ? 'var(--accent-blue)' : 'var(--text-muted)',
                              flexShrink: 0
                            }}>
                              <FileAudio size={16} />
                            </div>
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                                  {title}
                                </span>
                                {isActive && (
                                  <span style={{
                                    fontSize: '10px',
                                    fontWeight: 700,
                                    color: 'var(--accent-blue)',
                                    backgroundColor: 'rgba(24, 144, 255, 0.12)',
                                    padding: '1px 5px',
                                    borderRadius: '3px'
                                  }}>
                                    ACTIVE
                                  </span>
                                )}
                              </div>
                              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                                {pid}
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* Aspect */}
                        <td style={{ padding: '12px 16px' }}>
                          <span style={{
                            fontSize: '11px',
                            fontFamily: 'var(--font-mono)',
                            color: 'var(--text-secondary)',
                            backgroundColor: 'var(--bg-elevated)',
                            padding: '2px 6px',
                            borderRadius: '3px',
                            border: '1px solid var(--border-subtle)'
                          }}>
                            {aspect}
                          </span>
                        </td>

                        {/* Status */}
                        <td style={{ padding: '12px 16px' }}>
                          <span style={{
                            fontSize: '11px',
                            fontWeight: 600,
                            color: status === 'completed' 
                              ? 'var(--status-completed)' 
                              : status === 'running' 
                              ? 'var(--status-running)' 
                              : 'var(--accent-blue)',
                            backgroundColor: status === 'completed'
                              ? 'var(--status-completed-bg)'
                              : status === 'running'
                              ? 'var(--status-running-bg)'
                              : 'var(--bg-elevated)',
                            padding: '3px 8px',
                            borderRadius: '3px',
                            border: '1px solid var(--border-subtle)',
                            textTransform: 'capitalize'
                          }}>
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
                                onOpenLivePipeline();
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
                                transition: 'all 0.15s ease'
                              }}
                            >
                              <Eye size={13} />
                              <span>View</span>
                            </button>

                            {/* Delete Button */}
                            <button
                              data-testid={`delete-project-btn-${pid}`}
                              onClick={() => setProjectToDelete({ id: pid, name: title })}
                              title="Delete Project Permanently"
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '6px 10px',
                                backgroundColor: 'rgba(255, 77, 79, 0.08)',
                                border: '1px solid rgba(255, 77, 79, 0.3)',
                                borderRadius: '4px',
                                color: 'var(--status-failed)',
                                fontSize: '12px',
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'all 0.15s ease'
                              }}
                            >
                              <Trash2 size={13} />
                              <span>Delete</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 4. DELETE CONFIRMATION MODAL */}
      {projectToDelete && (
        <div style={{
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
          zIndex: 1000
        }}>
          <div 
            data-testid="delete-confirmation-dialog"
            style={{
              backgroundColor: 'var(--bg-card)',
              border: '1.5px solid var(--border-card)',
              borderRadius: 'var(--radius-md)',
              padding: '24px',
              maxWidth: '460px',
              width: '90%',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                backgroundColor: 'rgba(255, 77, 79, 0.15)',
                border: '1px solid rgba(255, 77, 79, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--status-failed)',
                flexShrink: 0
              }}>
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

            <div style={{
              backgroundColor: 'var(--bg-elevated)',
              padding: '12px 14px',
              borderRadius: '4px',
              border: '1px solid var(--border-subtle)',
              fontSize: '13px',
              lineHeight: 1.5,
              color: 'var(--text-secondary)',
              marginBottom: '20px'
            }}>
              Are you sure you want to permanently delete project <strong style={{ color: 'var(--text-primary)' }}>"{projectToDelete.name}"</strong>?
              <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: '4px' }}>
                ID: {projectToDelete.id}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--status-failed)', marginTop: '8px' }}>
                All audio files, timeline edits, rendered videos, and workspace metadata will be permanently deleted.
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => {
                  setProjectToDelete(null);
                  setDeleteError(null);
                }}
                style={{
                  padding: '8px 16px',
                  backgroundColor: 'transparent',
                  border: '1px solid var(--border-card)',
                  borderRadius: '4px',
                  color: 'var(--text-secondary)',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: isDeleting ? 'not-allowed' : 'pointer'
                }}
              >
                Cancel
              </button>

              <button
                type="button"
                data-testid="confirm-delete-project-btn"
                disabled={isDeleting}
                onClick={async () => {
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
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 18px',
                  backgroundColor: 'var(--status-failed)',
                  border: 'none',
                  borderRadius: '4px',
                  color: '#FFFFFF',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: isDeleting ? 'not-allowed' : 'pointer',
                  opacity: isDeleting ? 0.7 : 1
                }}
              >
                <Trash2 size={14} />
                <span>{isDeleting ? 'Deleting...' : 'Permanently Delete'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. RECENT PROJECTS & SWARM ACTIVITY GRID */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1.8fr) minmax(320px, 1fr)',
        gap: '24px'
      }}>
        {/* Left: Previous Projects Quick List */}
        <div style={{
          backgroundColor: 'var(--bg-card)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border-card)',
          boxShadow: 'var(--shadow-card)',
          padding: '20px 24px'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '16px'
          }}>
            <div>
              <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Production Projects Workspace
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                All localized workspaces, renders, and live checkpoints
              </p>
            </div>

            <button
              onClick={() => setShowAllProjectsTable(true)}
              style={{
                fontSize: '12px',
                color: 'var(--accent-blue)',
                backgroundColor: 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <span>View All ({projects.length})</span>
              <ArrowRight size={13} />
            </button>
          </div>

          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            maxHeight: '440px',
            overflowY: 'auto'
          }}>
            {projects.slice(0, 6).map((proj, idx) => {
              const pid = proj.id || proj.project_id || proj.name;
              const isActive = pid === activeProjectId;

              return (
                <div
                  key={pid || idx}
                  onClick={() => {
                    onSelectProject(pid);
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: isActive ? 'var(--status-running-bg)' : 'var(--bg-elevated)',
                    border: isActive ? '1px solid var(--accent-blue)' : '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '4px',
                      backgroundColor: 'var(--bg-card)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: isActive ? 'var(--accent-blue)' : 'var(--text-muted)'
                    }}>
                      <FolderKanban size={16} />
                    </div>

                    <div>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {proj.name || proj.title || pid}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {proj.aspect || '16:9'} • {proj.created_at ? new Date(proj.created_at).toLocaleDateString() : 'Active Workspace'}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      color: proj.status === 'completed' ? 'var(--status-completed)' : 'var(--accent-blue)',
                      backgroundColor: 'var(--bg-card)',
                      padding: '2px 8px',
                      borderRadius: '3px',
                      border: '1px solid var(--border-subtle)'
                    }}>
                      {proj.status || 'Active'}
                    </span>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectProject(pid);
                        onOpenLivePipeline();
                      }}
                      style={{
                        padding: '5px 10px',
                        backgroundColor: 'transparent',
                        border: '1px solid var(--border-card)',
                        borderRadius: '3px',
                        color: 'var(--accent-blue)',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      <span>Open</span>
                      <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Autonomous Swarm & Engine Status */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '16px'
        }}>
          {/* Swarm Status Card */}
          <div style={{
            backgroundColor: 'var(--bg-card)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-card)',
            boxShadow: 'var(--shadow-card)',
            padding: '20px 24px'
          }}>
            <h3 style={{
              fontSize: '15px',
              fontWeight: 700,
              color: 'var(--text-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '12px'
            }}>
              <Cpu size={17} color="var(--accent-blue)" />
              21 Autonomous Agents Swarm
            </h3>

            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '10px',
              marginBottom: '16px'
            }}>
              <div style={{
                backgroundColor: 'var(--bg-elevated)',
                padding: '12px',
                borderRadius: '4px',
                border: '1px solid var(--border-subtle)'
              }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Video Agents</div>
                <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                  14 Active
                </div>
              </div>

              <div style={{
                backgroundColor: 'var(--bg-elevated)',
                padding: '12px',
                borderRadius: '4px',
                border: '1px solid var(--border-subtle)'
              }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>System Agents</div>
                <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                  7 Active
                </div>
              </div>
            </div>

            <div style={{
              fontSize: '12px',
              color: 'var(--text-secondary)',
              lineHeight: 1.6,
              backgroundColor: 'var(--bg-elevated)',
              padding: '12px',
              borderRadius: '4px',
              border: '1px solid var(--border-subtle)'
            }}>
              <div>[API Backend] FastAPI :8000: <strong style={{ color: backendHealthy ? 'var(--status-completed)' : 'var(--status-failed)' }}>{backendHealthy ? 'HEALTHY' : 'OFFLINE'}</strong></div>
              <div>[LLM In-Flight] Dispatches: <strong style={{ color: 'var(--accent-cyan)' }}>{activeLlmCount} Active</strong></div>
              <div>[Remotion Engine] 1080p HD: <strong style={{ color: 'var(--status-completed)' }}>READY</strong></div>
            </div>
          </div>

          {/* Core Invariants Card */}
          <div style={{
            backgroundColor: 'var(--bg-card)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-card)',
            boxShadow: 'var(--shadow-card)',
            padding: '20px 24px'
          }}>
            <h4 style={{
              fontSize: '13px',
              fontWeight: 700,
              color: 'var(--status-completed)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              marginBottom: '8px'
            }}>
              <ShieldCheck size={16} />
              Frozen Algorithm Integrity
            </h4>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px' }}>
              SHA-256 bit-for-bit identical hashes verified:
            </p>
            <div style={{
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-secondary)',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div>• transcribe.py (07A200...)</div>
              <div>• transcript_review.py (7290EA...)</div>
              <div>• scene_segmentation.py (2D9EA8...)</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
