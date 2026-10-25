import React, { useState } from 'react';
import styles from './DashboardPage.module.css';
import { TopMetricCards } from '../components/TopMetricCards';
import { ProjectsDirectory } from '../components/ProjectsDirectory';
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
  // Table Toggle State
  const [showAllProjectsTable, setShowAllProjectsTable] = useState<boolean>(false);

  return (
    <div className={styles.dashboardContainer}>
      {/* 1. TOP 4 METRIC CARDS */}
      <TopMetricCards
        totalRuns={projects.length || 1430}
        activeStagesCount={12}
        totalAgentsCount={agents.length || 21}
        overallProgress={projectState.overallProgress || 88}
      />

      {/* 2. DUAL SPOTLIGHT CARDS: CURRENT ACTIVE PROJECT & ALL PROJECTS CARD */}
      <div className={styles.dualSpotlightGrid}>
        {/* Card A: Current Active Project Spotlight */}
        <div className={styles.spotlightCard}>
          <div className={styles.cardTopRow}>
            <div 
              className={styles.iconSquare}
              style={{
                backgroundColor: 'var(--status-running-bg)',
                border: '1px solid var(--status-running-border)',
                color: 'var(--accent-blue)'
              }}
            >
              <Video size={24} />
            </div>

            <div className={styles.cardHeaderInfo}>
              <div className={styles.cardBadgeGroup}>
                <span className={styles.cardSubTitle}>
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

              <h2 className={styles.cardMainTitle}>
                {projectState.title || activeProjectId}
              </h2>

              <div className={styles.cardMetaRow}>
                <span>ID: <strong style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{activeProjectId}</strong></span>
                <span>•</span>
                <span>Aspect: <strong>{projectState.aspectRatio}</strong></span>
                <span>•</span>
                <span>Progress: <strong>{projectState.overallProgress}%</strong></span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className={styles.actionRow}>
            <button
              onClick={onOpenLivePipeline}
              className={styles.primaryActionButton}
            >
              <span>Open Live Pipeline</span>
              <ArrowRight size={15} />
            </button>

            <button
              onClick={onNewProject}
              className={styles.secondaryActionButton}
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
          className={`${styles.spotlightCard} ${styles.interactiveSpotlightCard}`}
          style={{
            border: showAllProjectsTable ? '1.5px solid var(--accent-blue)' : '1px solid var(--border-card)',
            boxShadow: showAllProjectsTable ? '0 0 16px rgba(24, 144, 255, 0.2)' : 'var(--shadow-card)',
            position: 'relative'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
            <div className={styles.cardTopRow}>
              <div 
                className={styles.iconSquare}
                style={{
                  backgroundColor: 'rgba(24, 144, 255, 0.12)',
                  border: '1px solid rgba(24, 144, 255, 0.3)',
                  color: 'var(--accent-blue)'
                }}
              >
                <FolderKanban size={24} />
              </div>

              <div className={styles.cardHeaderInfo}>
                <div className={styles.cardBadgeGroup}>
                  <span className={styles.cardSubTitle}>
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

                <h2 className={styles.cardMainTitle}>
                  All Projects
                </h2>

                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: 1.4 }}>
                  Browse all production workspaces. Click to display the full projects table on this page with View and Delete actions.
                </p>
              </div>
            </div>

            {/* Toggle Badge Indicator */}
            <div 
              className={styles.toggleBadge}
              style={{
                backgroundColor: showAllProjectsTable ? 'var(--accent-blue)' : 'var(--bg-elevated)',
                color: showAllProjectsTable ? '#FFFFFF' : 'var(--accent-blue)'
              }}
            >
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
        <ProjectsDirectory
          projects={projects}
          activeProjectId={activeProjectId}
          onSelectProject={onSelectProject}
          onOpenLivePipeline={onOpenLivePipeline}
          onRefreshProjects={onRefreshProjects}
          onDeleteProject={onDeleteProject}
          onClose={() => setShowAllProjectsTable(false)}
          showCloseButton={true}
        />
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
        </div>
      </div>
    </div>
  );
};
