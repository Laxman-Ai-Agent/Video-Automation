import React from 'react';
import { ProjectsDirectory } from '../components/ProjectsDirectory';

interface ProjectsPageProps {
  projects: any[];
  activeProjectId: string;
  onSelectProject: (projectId: string) => void;
  onCreateProject?: (title: string, aspect: string) => void;
  onRefreshProjects?: () => Promise<void> | void;
  onDeleteProject?: (projectId: string) => Promise<boolean>;
}

export const ProjectsPage: React.FC<ProjectsPageProps> = ({
  projects,
  activeProjectId,
  onSelectProject,
  onCreateProject,
  onRefreshProjects,
  onDeleteProject,
}) => {
  return (
    <div style={{ padding: '32px', maxWidth: '1280px', margin: '0 auto' }}>
      <ProjectsDirectory
        projects={projects}
        activeProjectId={activeProjectId}
        onSelectProject={onSelectProject}
        onRefreshProjects={onRefreshProjects}
        onDeleteProject={onDeleteProject}
        onCreateProject={onCreateProject}
        showCloseButton={false}
        title="All Projects Directory"
        subtitle="All localized workspaces, timeline runs, and render outputs. Click View to open project details, or Delete to remove."
      />
    </div>
  );
};
