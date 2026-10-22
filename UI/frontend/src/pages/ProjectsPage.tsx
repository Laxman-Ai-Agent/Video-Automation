import React, { useState } from 'react';
import { FolderKanban, Plus, Play, ExternalLink, Clock, CheckCircle2 } from 'lucide-react';

interface ProjectsPageProps {
  projects: any[];
  activeProjectId: string;
  onSelectProject: (projectId: string) => void;
  onCreateProject: (title: string, aspect: string) => void;
}

export const ProjectsPage: React.FC<ProjectsPageProps> = ({
  projects,
  activeProjectId,
  onSelectProject,
  onCreateProject
}) => {
  const [showModal, setShowModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newAspect, setNewAspect] = useState<'16:9' | '9:16'>('16:9');

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    onCreateProject(newTitle.trim(), newAspect);
    setNewTitle('');
    setShowModal(false);
  };

  return (
    <div style={{ padding: '32px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '28px' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-primary)' }}>
            Production Projects
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Select an active video production workspace or create a new automated run.
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 20px',
            backgroundColor: 'var(--accent-cyan)',
            color: '#060D1A',
            border: 'none',
            borderRadius: 'var(--radius-full)',
            fontWeight: 800,
            fontSize: '13px',
            cursor: 'pointer'
          }}
        >
          <Plus size={16} />
          New Project
        </button>
      </div>

      {/* Projects Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
        {projects.map((proj) => {
          const pid = proj.id || proj.project_id || proj.name || 'unnamed';
          const isActive = pid === activeProjectId;

          return (
            <div
              key={pid}
              onClick={() => onSelectProject(pid)}
              style={{
                backgroundColor: isActive ? 'var(--bg-elevated)' : 'var(--bg-card)',
                borderRadius: 'var(--radius-xl)',
                border: `1.5px solid ${isActive ? 'var(--accent-cyan)' : 'var(--border-card)'}`,
                padding: '22px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                minHeight: '160px',
                transition: 'all 0.2s ease',
                boxShadow: isActive ? 'var(--shadow-active)' : 'var(--shadow-card)'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{
                    fontSize: '11px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--accent-cyan)',
                    backgroundColor: 'var(--status-running-bg)',
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-sm)'
                  }}>
                    {proj.aspect || '16:9'}
                  </span>

                  {isActive && (
                    <span style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      color: 'var(--accent-cyan)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      <CheckCircle2 size={13} />
                      ACTIVE
                    </span>
                  )}
                </div>

                <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '12px' }}>
                  {proj.title || pid}
                </h3>
                <p style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: '3px' }}>
                  {pid}
                </p>
              </div>

              <div style={{
                marginTop: '16px',
                borderTop: '1px solid var(--border-subtle)',
                paddingTop: '12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '12px',
                color: 'var(--text-secondary)'
              }}>
                <span>Status: {proj.status || 'Ready'}</span>
                <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>Open Workspace &rarr;</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* New Project Modal */}
      {showModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'var(--bg-card)',
            padding: '28px',
            borderRadius: 'var(--radius-xl)',
            border: '1px solid var(--border-card)',
            width: '440px',
            maxWidth: '90vw'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '16px' }}>
              Create New Production Project
            </h3>

            <form onSubmit={handleCreate}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Project Title
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Telugu Tech Explainer 01"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    backgroundColor: 'var(--bg-app)',
                    border: '1px solid var(--border-card)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-primary)',
                    fontSize: '14px',
                    outline: 'none'
                  }}
                />
              </div>

              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Aspect Ratio
                </label>
                <div style={{ display: 'flex', gap: '10px' }}>
                  {['16:9', '9:16'].map((aspect) => (
                    <button
                      key={aspect}
                      type="button"
                      onClick={() => setNewAspect(aspect as any)}
                      style={{
                        flex: 1,
                        padding: '10px',
                        borderRadius: 'var(--radius-md)',
                        border: `1.5px solid ${newAspect === aspect ? 'var(--accent-cyan)' : 'var(--border-card)'}`,
                        backgroundColor: newAspect === aspect ? 'var(--bg-elevated)' : 'transparent',
                        color: newAspect === aspect ? 'var(--accent-cyan)' : 'var(--text-muted)',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      {aspect === '16:9' ? '16:9 Landscape' : '9:16 Portrait (Shorts)'}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  style={{
                    padding: '9px 16px',
                    backgroundColor: 'transparent',
                    color: 'var(--text-muted)',
                    border: 'none',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  style={{
                    padding: '9px 20px',
                    backgroundColor: 'var(--accent-cyan)',
                    color: '#060D1A',
                    border: 'none',
                    borderRadius: 'var(--radius-full)',
                    fontWeight: 800,
                    cursor: 'pointer'
                  }}
                >
                  Create & Open
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
