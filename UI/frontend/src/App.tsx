import React, { useState, useEffect, Suspense, lazy } from 'react';
import styles from './App.module.css';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { PipelineCanvas } from './components/PipelineCanvas';
import { IssuesPanel } from './components/IssuesPanel';
import { PipelinePillBar, PipelineTabType } from './components/layout/PipelinePillBar';
import { useSystemHealth } from './hooks/useSystemHealth';
import { useProjectPipeline } from './hooks/useProjectPipeline';
import { createProject, fetchProjects, fetchLlmHealth } from './services/api';

// Lazy-loaded secondary pages to minimize initial bundle size and speed up page load
const ProjectsPage = lazy(() => import('./pages/ProjectsPage').then(m => ({ default: m.ProjectsPage })));
const AgentsCenterPage = lazy(() => import('./pages/AgentsCenterPage').then(m => ({ default: m.AgentsCenterPage })));
const SkillsPage = lazy(() => import('./pages/SkillsPage').then(m => ({ default: m.SkillsPage })));
const LlmPage = lazy(() => import('./pages/LlmPage').then(m => ({ default: m.LlmPage })));
const RulesPage = lazy(() => import('./pages/RulesPage').then(m => ({ default: m.RulesPage })));
const WorkLogPage = lazy(() => import('./pages/WorkLogPage').then(m => ({ default: m.WorkLogPage })));
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })));

export const App: React.FC = () => {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem('a2v_theme');
    return (saved === 'light' || saved === 'dark') ? saved : 'dark';
  });
  const [activeView, setActiveView] = useState<'dashboard' | 'pipeline' | 'projects' | 'agents' | 'skills' | 'diagnostics' | 'audio-input' | 'llm' | 'work-log' | 'rules'>('pipeline');
  const [pipelineTab, setPipelineTab] = useState<PipelineTabType>('flow');
  const [pipelineFullPage, setPipelineFullPage] = useState<boolean>(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [issuesOpen, setIssuesOpen] = useState<boolean>(false);
  const [issuesStage, setIssuesStage] = useState<string | null>(null);

  // Synchronize theme with HTML root attribute and localStorage
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('a2v_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  // Custom event listener for stage card issues modal triggers
  useEffect(() => {
    const open = (e: Event) => {
      setIssuesStage((e as CustomEvent<string | null>).detail ?? null);
      setIssuesOpen(true);
    };
    window.addEventListener('open-issues', open);
    return () => window.removeEventListener('open-issues', open);
  }, []);

  // System Health & Infrastructure Hook
  const {
    backendHealthy,
    llmHealthy,
    setLlmHealthy,
    llmConnecting,
    setLlmConnecting,
    activeLlmCount,
    projects,
    setProjects,
    agents,
    skills,
    activeProjectId,
    setActiveProjectId,
    handleDeleteProject,
    handleRefreshProjects
  } = useSystemHealth();

  // Project Pipeline State & Subscription Hook
  const {
    projectState,
    issues,
    sseStatus,
    loadState,
    handleStartRun,
    handleCancelRun,
    handleAnalyze
  } = useProjectPipeline({
    activeProjectId,
    setActiveProjectId,
    setProjects,
    onAfterAnalyze: () => {
      setActiveView('pipeline');
      setPipelineTab('flow');
    }
  });

  const handleOpenNewProject = () => {
    setActiveView('pipeline');
    setPipelineTab('new-project');
  };

  const handleCreateLegacyProject = async (title: string, aspect: string) => {
    try {
      const res = await createProject(title, aspect);
      const newId = res.id || res.project_id || title.toLowerCase().replace(/\s+/g, '-');
      const updatedList = await fetchProjects();
      setProjects(updatedList);
      setActiveProjectId(newId);
      setActiveView('pipeline');
    } catch (e) {
      console.error('Failed to create legacy project:', e);
    }
  };

  const scrollAreaClass = `${styles.scrollArea} ${
    pipelineFullPage
      ? styles.scrollAreaFullPage
      : (activeView === 'pipeline' || activeView === 'audio-input')
        ? styles.scrollAreaPaddingPipeline
        : styles.scrollAreaPaddingStandard
  }`;

  return (
    <div className={styles.appRoot}>
      {/* 1. LEFT SIDEBAR */}
      <Sidebar
        activeView={activeView}
        pipelineTab={pipelineTab}
        setActiveView={setActiveView}
        onSelectNewProject={handleOpenNewProject}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        agentCount={agents.length}
      />

      {/* 2. MAIN APPLICATION CONTENT AREA */}
      <div className={styles.mainArea}>
        {/* TOP HEADER */}
        <Header
          onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
          onNewProject={handleOpenNewProject}
          backendHealthy={backendHealthy}
          llmHealthy={llmHealthy}
          llmConnecting={llmConnecting}
          activeLlmCount={activeLlmCount}
          projectCount={projects.length}
          activeProjectId={activeProjectId}
          theme={theme}
          onToggleTheme={toggleTheme}
          issues={issues}
          onOpenIssues={() => { setIssuesStage(null); setIssuesOpen(true); }}
          onOpenLlm={() => setActiveView('llm')}
        />

        {/* ISSUES MODAL PANEL */}
        <IssuesPanel
          open={issuesOpen}
          issues={issues}
          stageFilter={issuesStage}
          onShowAll={() => setIssuesStage(null)}
          onClose={() => setIssuesOpen(false)}
          onLocate={(stageId) => {
            setIssuesOpen(false);
            setActiveView('pipeline');
            setPipelineTab('flow');
            setTimeout(() => document.querySelector(`[data-testid="stage-card-${stageId}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 150);
          }}
        />

        {/* FIXED PIPELINE TAB PILLS */}
        {(activeView === 'pipeline' || activeView === 'audio-input') && !pipelineFullPage && (
          <PipelinePillBar
            activeView={activeView}
            pipelineTab={pipelineTab}
            projectState={projectState}
            projectCount={projects.length}
            onSelectTab={(tab) => {
              setActiveView('pipeline');
              setPipelineTab(tab);
            }}
          />
        )}

        {/* SCROLLABLE MAIN BODY */}
        <main data-testid="main-content-scroll-area" className={scrollAreaClass}>
          <Suspense fallback={<div className={styles.suspenseLoading}>Loading view...</div>}>
            {activeView === 'dashboard' && (
              <DashboardPage
                projectState={projectState}
                projects={projects}
                activeProjectId={activeProjectId}
                onSelectProject={(pid) => setActiveProjectId(pid)}
                onOpenLivePipeline={() => {
                  setActiveView('pipeline');
                  setPipelineTab('flow');
                }}
                onNewProject={handleOpenNewProject}
                agents={agents}
                activeLlmCount={activeLlmCount}
                backendHealthy={backendHealthy}
                onDeleteProject={handleDeleteProject}
                onRefreshProjects={handleRefreshProjects}
              />
            )}

            {(activeView === 'pipeline' || activeView === 'audio-input') && (
              <PipelineCanvas
                projectState={projectState}
                projects={projects}
                activeProjectId={activeProjectId}
                onSelectProject={(pid) => setActiveProjectId(pid)}
                agents={agents}
                activeLlmCount={activeLlmCount}
                backendHealthy={backendHealthy}
                onReloadState={loadState}
                onStartRun={handleStartRun}
                onCancelRun={handleCancelRun}
                onNewProject={handleOpenNewProject}
                onAnalyze={handleAnalyze}
                activeTab={activeView === 'audio-input' ? 'new-project' : pipelineTab}
                onTabChange={(tab) => {
                  setPipelineTab(tab);
                  if (activeView === 'audio-input') setActiveView('pipeline');
                }}
                sseStatus={sseStatus}
                onFullPageChange={setPipelineFullPage}
                onRefreshProjects={handleRefreshProjects}
                onDeleteProject={handleDeleteProject}
              />
            )}

            {activeView === 'projects' && (
              <ProjectsPage
                projects={projects}
                activeProjectId={activeProjectId}
                onSelectProject={(pid) => {
                  setActiveProjectId(pid);
                  setActiveView('pipeline');
                  setPipelineTab('flow');
                }}
                onCreateProject={handleCreateLegacyProject}
                onRefreshProjects={handleRefreshProjects}
              />
            )}

            {activeView === 'agents' && (
              <AgentsCenterPage agents={agents} />
            )}

            {activeView === 'skills' && (
              <SkillsPage skills={skills} />
            )}

            {activeView === 'rules' && (
              <RulesPage />
            )}

            {activeView === 'work-log' && (
              <WorkLogPage />
            )}

            {activeView === 'llm' && (
              <LlmPage
                onChanged={async () => {
                  const lh = await fetchLlmHealth();
                  setLlmHealthy(lh.ok);
                }}
                onBusyChange={setLlmConnecting}
              />
            )}

            {activeView === 'diagnostics' && (
              <div className={styles.diagnosticsCard}>
                <h2 className={styles.diagnosticsTitle}>
                  System Diagnostics & Infrastructure Health
                </h2>
                <div className={styles.diagnosticsConsole}>
                  <div>[STATUS] FastAPI Backend: {backendHealthy ? 'ONLINE (http://127.0.0.1:8000)' : 'UNREACHABLE'}</div>
                  <div>[AGENTS] Canonical Agents: {agents.length} Registered (15 Video + 7 System)</div>
                  <div>[PROJECTS] Total Workspaces: {projects.length}</div>
                  <div>[LLM GATEWAY] Active In-Flight LLM Dispatches: {activeLlmCount}</div>
                </div>
              </div>
            )}
          </Suspense>
        </main>
      </div>
    </div>
  );
};

export default App;
