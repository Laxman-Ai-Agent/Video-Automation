import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { PipelineCanvas } from './components/PipelineCanvas';
import { ProjectsPage } from './pages/ProjectsPage';
import { AgentsCenterPage } from './pages/AgentsCenterPage';
import { SkillsPage } from './pages/SkillsPage';
import { LlmPage } from './pages/LlmPage';
import { WorkLogPage } from './pages/WorkLogPage';
import { AudioInputPage } from './pages/AudioInputPage';
import { DEFAULT_MEDIA, type MediaMix } from './services/mediaMix';
import { DashboardPage } from './pages/DashboardPage';
import { VisualAiEditorPage } from './components/visual-editor/VisualAiEditorPage';
import { 
  fetchHealth, 
  fetchLlmHealth,
  fetchProjects, 
  fetchProjectState, 
  fetchProjectPipeline,
  acceptStageWarnings,
  fetchProjectStatus,
  fetchProjectMonitor,
  fetchAgents, 
  fetchSkills,
  fetchLlmActive,
  createProjectWithAudio,
  createProject,
  startProjectRun,
  cancelProjectRun,
  deleteProject
} from './services/api';
import { subscribeToEvents, ConnectionStatus } from './services/sse';
import { CANONICAL_12_STAGES, PipelineIssue, PipelineProjectState, StageState, StageStatus } from './types/pipeline';
import { IssuesPanel } from './components/IssuesPanel';

const normalizeTimestamp = (ts: any): string | undefined => {
  if (ts === null || ts === undefined || ts === '') return undefined;
  if (typeof ts === 'number') {
    const ms = ts < 1e11 ? ts * 1000 : ts;
    return new Date(ms).toISOString();
  }
  if (typeof ts === 'string') {
    const num = Number(ts);
    if (!isNaN(num) && num > 0) {
      const ms = num < 1e11 ? num * 1000 : num;
      return new Date(ms).toISOString();
    }
    const d = new Date(ts);
    if (!isNaN(d.getTime())) return d.toISOString();
    return ts;
  }
  return undefined;
};

export const App: React.FC = () => {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem('a2v_theme');
    return (saved === 'light' || saved === 'dark') ? saved : 'dark';
  });
  const [activeView, setActiveView] = useState<'dashboard' | 'pipeline' | 'projects' | 'agents' | 'skills' | 'diagnostics' | 'audio-input' | 'visual-editor' | 'llm' | 'work-log'>('pipeline');
  const [pipelineTab, setPipelineTab] = useState<'flow' | 'approvals' | 'communication' | 'new-project' | 'projects'>('flow');
  const [pipelineFullPage, setPipelineFullPage] = useState<boolean>(false);
  const [issues, setIssues] = useState<PipelineIssue[]>([]);
  const [issuesOpen, setIssuesOpen] = useState<boolean>(false);
  const [issuesStage, setIssuesStage] = useState<string | null>(null);      // the stage a card's issue badge opened the panel for (null = all)
  useEffect(() => {
    const open = (e: Event) => { setIssuesStage((e as CustomEvent<string | null>).detail ?? null); setIssuesOpen(true); };
    window.addEventListener('open-issues', open);
    return () => window.removeEventListener('open-issues', open);
  }, []);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [backendHealthy, setBackendHealthy] = useState<boolean>(true);
  const [llmHealthy, setLlmHealthy] = useState<boolean>(false);
  const [sseStatus, setSseStatus] = useState<ConnectionStatus>('reconnecting');
  const [activeLlmCount, setActiveLlmCount] = useState<number>(0);
  const [projects, setProjects] = useState<any[]>([]);
  const [agents, setAgents] = useState<any[]>([]);
  const [skills, setSkills] = useState<any[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string>(() => {
    const params = new URLSearchParams(window.location.search);
    const urlProj = params.get('projectId') || params.get('project');
    if (urlProj) return urlProj;
    return localStorage.getItem('a2v_active_project') || 'sample-01';
  });

  // Theme synchronization with HTML attribute and localStorage
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('a2v_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  // Persist active project ID whenever it changes
  useEffect(() => {
    if (activeProjectId) {
      localStorage.setItem('a2v_active_project', activeProjectId);
    }
  }, [activeProjectId]);

  // Authoritative project pipeline state
  const [projectState, setProjectState] = useState<PipelineProjectState>({
    projectId: 'sample-01',
    title: 'Telugu Audio-to-Video Production',
    aspectRatio: '16:9',
    autoPilot: true,
    overallProgress: 0,
    currentStageId: 'audio',
    status: 'idle',
    stages: CANONICAL_12_STAGES.reduce((acc, s) => {
      acc[s.id] = { id: s.id, status: 'waiting', percentage: null };
      return acc;
    }, {} as Record<string, StageState>),
    updatedAt: new Date().toISOString()
  });

  // 1. Initial Data Fetch & Periodic Real-time Health Poll with Non-Flapping Hysteresis
  useEffect(() => {
    let healthInFlight = false;
    let consecutiveFailures = 0;

    async function checkSystemHealth() {
      if (healthInFlight) return;
      healthInFlight = true;
      try {
        const h = await fetchHealth();
        if (h.ok) {
          consecutiveFailures = 0;
          setBackendHealthy(true);
          const lh = await fetchLlmHealth();
          setLlmHealthy(lh.ok);
        } else {
          consecutiveFailures++;
          // Hysteresis: Require 2 consecutive failed health probes before marking the backend offline
          // This permanently eliminates transient single-probe flapping during heavy I/O or brief network delays
          if (consecutiveFailures >= 2) {
            setBackendHealthy(false);
            setLlmHealthy(false);
          }
        }
      } catch {
        consecutiveFailures++;
        if (consecutiveFailures >= 2) {
          setBackendHealthy(false);
          setLlmHealthy(false);
        }
      } finally {
        healthInFlight = false;
      }
    }

    async function loadInitial() {
      checkSystemHealth();

      const projs = await fetchProjects();
      setProjects(projs);
      const params = new URLSearchParams(window.location.search);
      const urlProj = params.get('projectId') || params.get('project');
      const savedId = urlProj || localStorage.getItem('a2v_active_project');
      if (savedId && projs.some((p: any) => (p.id || p.project_id) === savedId)) {
        setActiveProjectId(savedId);
      } else if (urlProj) {
        setActiveProjectId(urlProj);
      } else if (projs.length > 0 && (!activeProjectId || activeProjectId === 'sample-01')) {
        const firstId = projs[0].id || projs[0].project_id;
        if (firstId) setActiveProjectId(firstId);
      }

      const ags = await fetchAgents();
      setAgents(ags);

      const sks = await fetchSkills();
      setSkills(sks);

      const llm = await fetchLlmActive();
      setActiveLlmCount(llm.active_count || 0);
    }

    loadInitial();
    const interval = setInterval(async () => {
      await checkSystemHealth();
      const llm = await fetchLlmActive();
      setActiveLlmCount(llm.active_count || 0);
    }, 4000);

    return () => clearInterval(interval);
  }, []);

  const loadStateInFlightRef = useRef<boolean>(false);

  // 2. Fetch Project Pipeline State when activeProjectId changes or polling
  const loadState = useCallback(async () => {
    if (!activeProjectId || loadStateInFlightRef.current) return;
    loadStateInFlightRef.current = true;

    try {
      // Parallel fetch pipeline view, job status, and monitor data
      // A hung request must not block later polls, and a failing side call must not block the stage update
      function withTimeout<T>(p: Promise<T>, ms = 8000): Promise<T> {
        return Promise.race([p, new Promise<T>((_, reject) => setTimeout(() => reject(new Error('request timed out')), ms))]);
      }
      const [pipeData, statusData, monitorData] = await Promise.all([
        withTimeout(fetchProjectPipeline(activeProjectId), 120000),      // ponytail: this endpoint re-fingerprints every input (15-45 s on this CPU); speed it up on the backend, then lower this
        withTimeout(fetchProjectStatus(activeProjectId)).catch(() => null),
        withTimeout(fetchProjectMonitor(activeProjectId)).catch(() => null)
      ]);

      const isJobRunning = Boolean(pipeData?.running || statusData?.running || monitorData?.job?.state === 'running');
      const jobError = statusData?.error || monitorData?.job?.error || monitorData?.status?.error;
      const jobMsg = statusData?.message || monitorData?.job?.message || monitorData?.status?.message;
      const jobPct = statusData?.percent !== undefined && statusData?.percent !== null ? statusData.percent : monitorData?.status?.percent;

      if (pipeData && pipeData.stages) {
        const rawStages = pipeData.stages;
        const mappedStages: Record<string, StageState> = {};
        let completedCount = 0;
        let activeStageId = 'audio';

        // Check if rawStages is array or object
        const isArray = Array.isArray(rawStages);

        CANONICAL_12_STAGES.forEach((cfg, idx) => {
          let raw: any = null;
          if (isArray) {
            raw = rawStages.find((s: any) => s.id === cfg.id);
          } else {
            raw = rawStages[cfg.id];
          }

          let st = raw?.status || 'waiting';
          if (st === 'queued') st = 'waiting';

          let pct: number | null = raw?.percent !== undefined && raw?.percent !== null
            ? raw.percent
            : (raw?.percentage !== undefined ? raw.percentage : null);

          if (st === 'completed') {
            completedCount++;
            pct = 100;
          } else if (st === 'running') {
            activeStageId = cfg.id;
            if (pct === null && jobPct) {
              pct = jobPct;
            }
          }

          let durationMs: number | undefined = undefined;
          if (raw?.duration_ms !== undefined && raw?.duration_ms !== null) {
            durationMs = Number(raw.duration_ms);
          } else if (raw?.durationMs !== undefined && raw?.durationMs !== null) {
            durationMs = Number(raw.durationMs);
          } else if (raw?.completed_at && raw?.started_at) {
            const startNum = typeof raw.started_at === 'number' ? (raw.started_at < 1e11 ? raw.started_at * 1000 : raw.started_at) : new Date(raw.started_at).getTime();
            const endNum = typeof raw.completed_at === 'number' ? (raw.completed_at < 1e11 ? raw.completed_at * 1000 : raw.completed_at) : new Date(raw.completed_at).getTime();
            if (!isNaN(startNum) && !isNaN(endNum) && endNum >= startNum) {
              durationMs = Math.round(endNum - startNum);
            }
          }

          mappedStages[cfg.id] = {
            id: cfg.id,
            status: st,
            percentage: pct,
            currentActivity: raw?.detail || raw?.current_activity || jobMsg,
            teluguMessage: raw?.telugu_status || raw?.telugu_message,
            startedAt: normalizeTimestamp(raw?.started_at),
            completedAt: normalizeTimestamp(raw?.completed_at),
            durationMs: durationMs,
            llmVerified: !!raw?.llm_verified,
            blockers: st === 'blocked' && raw?.detail ? [raw.detail] : undefined,
            waitingFor: raw?.waiting_for || undefined,
            attempt: raw?.attempt || 1,
            artifacts: raw?.artifacts,
            errors: (st === 'failed' || (activeStageId === cfg.id && jobError)) ? [jobError || 'Stage failed during processing'] : undefined
          };
        });

        // Real problems reported by the backend (agent log, job, stage statuses): list them and mark the exact stage they belong to
        const issueList: PipelineIssue[] = (pipeData.issues || []).map((i: any) => ({
          id: i.id, severity: i.severity, stageId: i.stage_id ?? null, stageLabel: i.stage_label, source: i.source,
          component: i.component, message: i.message, code: i.code, attempts: i.attempts, retryLimit: i.retry_limit, at: i.at,
          subtask: i.subtask ?? null, stageStatus: i.stage_status ?? null
        }));
        issueList.forEach((i) => {
          const s = i.stageId ? mappedStages[i.stageId] : undefined;
          if (!s) return;
          if (i.severity === 'warning') s.issueWarnings = (s.issueWarnings || 0) + 1;
          else s.issueErrors = (s.issueErrors || 0) + 1;            // error or stuck
          if (s.status === 'completed') return;
          if (i.severity === 'error' && s.status !== 'running' && s.status !== 'retrying') {
            s.status = 'failed';
            s.errors = [i.message];
          }
          if (i.severity === 'stuck') s.stuck = true;
        });
        setIssues((prev) => (JSON.stringify(prev) === JSON.stringify(issueList) ? prev : issueList));

        // If a job is running but stages haven't transitioned yet, mark the first incomplete stage as running
        if (isJobRunning && !jobError && !Object.values(mappedStages).some(s => s.status === 'running')) {
          const firstIncomplete = CANONICAL_12_STAGES.find(c => mappedStages[c.id].status !== 'completed');
          if (firstIncomplete) {
            mappedStages[firstIncomplete.id].status = 'running';
            mappedStages[firstIncomplete.id].percentage = jobPct ?? null;
            activeStageId = firstIncomplete.id;
          }
        }

        // If backend reports an error, ensure active stage is marked as failed immediately
        if (jobError) {
          const targetFailedId = activeStageId || 'analyzer';
          if (mappedStages[targetFailedId]) {
            mappedStages[targetFailedId].status = 'failed';
            mappedStages[targetFailedId].errors = [jobError];
          }
        }

        const totalStages = CANONICAL_12_STAGES.length;
        const overall = Math.min(100, Math.round((completedCount / totalStages) * 100));

        setProjectState((prev) => {
          const nextTitle = monitorData?.name || pipeData.project || prev.title;
          const nextAspect = pipeData.aspect || prev.aspectRatio;
          const isAnyStageRunning = Object.values(mappedStages).some(s => s.status === 'running' || s.status === 'retrying');
        const nextStatus = jobError 
          ? 'failed' 
          : (isJobRunning || isAnyStageRunning 
              ? 'running' 
              : (completedCount === totalStages ? 'completed' : 'idle'));

          // Check if any state values actually changed before triggering a React update
          const isBasicSame = 
            prev.projectId === activeProjectId &&
            prev.title === nextTitle &&
            prev.aspectRatio === nextAspect &&
            prev.overallProgress === overall &&
            prev.currentStageId === activeStageId &&
            prev.status === nextStatus;

          if (isBasicSame) {
            let stagesChanged = false;
            for (const cfg of CANONICAL_12_STAGES) {
              const oldS = prev.stages[cfg.id];
              const newS = mappedStages[cfg.id];
              if (!oldS || !newS) {
                stagesChanged = true;
                break;
              }
              if (
                oldS.status !== newS.status ||
                oldS.percentage !== newS.percentage ||
                oldS.currentActivity !== newS.currentActivity ||
                oldS.teluguMessage !== newS.teluguMessage ||
                oldS.errors?.[0] !== newS.errors?.[0] ||
                oldS.durationMs !== newS.durationMs ||
                oldS.llmVerified !== newS.llmVerified ||
                oldS.stuck !== newS.stuck ||
                oldS.waitingFor !== newS.waitingFor ||
                oldS.issueErrors !== newS.issueErrors ||
                oldS.issueWarnings !== newS.issueWarnings ||
                oldS.startedAt !== newS.startedAt ||
                oldS.completedAt !== newS.completedAt
              ) {
                stagesChanged = true;
                break;
              }
            }

            if (!stagesChanged) {
              // Nothing changed: return prev to bail out of re-rendering completely
              return prev;
            }
          }

          return {
            ...prev,
            projectId: activeProjectId,
            title: nextTitle,
            aspectRatio: nextAspect,
            overallProgress: overall,
            currentStageId: activeStageId,
            status: nextStatus,
            stages: mappedStages,
            updatedAt: new Date().toISOString()
          };
        });
      }
    } catch (err) {
      console.error('Error fetching project pipeline state:', err);
    } finally {
      loadStateInFlightRef.current = false;
    }
  }, [activeProjectId]);

  useEffect(() => {
    loadState();
    // Poll every 1.5s if running, otherwise every 3s when idle (SSE handles live push); refresh at once when the tab comes back
    const pollInterval = setInterval(loadState, projectState.status === 'running' ? 1500 : 3000);
    const onVisible = () => { if (document.visibilityState === 'visible') loadState(); };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', loadState);
    return () => {
      clearInterval(pollInterval);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', loadState);
    };
  }, [activeProjectId, loadState, projectState.status]);

  // 3. SSE Live Events Subscription (stable: does not reconnect on every poll)
  useEffect(() => {
    if (!activeProjectId) return;
    const unsubscribe = subscribeToEvents(
      activeProjectId, 
      (event) => {
        if (!event.stageId) return;
        setProjectState((prev) => {
          const existing = prev.stages[event.stageId!];
          if (!existing) return prev;

          const newMsgTelugu = event.messageTelugu;
          const newMsgEng = event.messageEnglish;
          const anyEvent = event as any;
          const newPct = anyEvent.percentage !== undefined ? anyEvent.percentage : existing.percentage;
          
          const isError = event.level === 'error' || event.eventType.includes('error');
          const isRetry = event.eventType.includes('retry') || event.eventType.includes('recover');
          const isDone = newPct === 100 || event.eventType.includes('complete');
          
          let nextStatus: StageStatus = existing.status;
          if (isError) nextStatus = 'failed';
          else if (isRetry) nextStatus = 'retrying';
          else if (isDone) nextStatus = 'completed';
          else if (prev.status === 'running' && existing.status === 'waiting') nextStatus = 'running';

          const updatedStage: StageState = {
            ...existing,
            status: nextStatus,
            teluguMessage: newMsgTelugu || existing.teluguMessage,
            currentActivity: newMsgEng || existing.currentActivity,
            percentage: newPct,
            attempt: event.retryAttempt || existing.attempt,
            maxAttempts: event.retryMax || existing.maxAttempts,
            retryReason: isRetry ? (event.messageEnglish || 'Retrying transient failure') : existing.retryReason,
            failingSubStage: event.failingSubStage || existing.failingSubStage,
            errors: isError ? [event.errorMessage || event.messageEnglish || 'Processing error'] : existing.errors,
            lastActivityAt: event.timestamp || new Date().toISOString()
          };

          const nextProjectStatus = isError ? 'failed' : (prev.status === 'idle' ? 'running' : prev.status);

          return {
            ...prev,
            currentStageId: event.stageId!,
            status: nextProjectStatus,
            stages: { ...prev.stages, [event.stageId!]: updatedStage },
            updatedAt: new Date().toISOString()
          };
        });
      },
      (connStatus) => {
        setSseStatus(connStatus);
      }
    );

    return () => unsubscribe();
  }, [activeProjectId]);

  // 4. Action: Start Pipeline Run
  const handleStartRun = async () => {
    try {
      await startProjectRun(activeProjectId, true);
      setProjectState((prev) => ({ ...prev, status: 'running' }));
      // Quick immediate reload of state
      setTimeout(loadState, 600);
    } catch (e) {
      console.error(e);
    }
  };

  // 5. Action: Cancel Pipeline Run
  const handleCancelRun = async () => {
    try {
      await cancelProjectRun(activeProjectId);
      setProjectState((prev) => ({ ...prev, status: 'paused' }));
      setTimeout(loadState, 600);
    } catch (e) {
      console.error(e);
    }
  };

  // 6. Action: Full New Project Creation & Analysis Flow (Analyze Button)
  const handleAnalyze = async (
    title: string, 
    audioFile: File, 
    aspect: string,
    reusableTemplates: boolean = false,
    media: MediaMix = DEFAULT_MEDIA
  ) => {
    // 1. Create project with audio upload and visual settings (the media mix is set here and never changes afterwards)
    const res = await createProjectWithAudio(title, audioFile, aspect, reusableTemplates, media);
    const newId = res.id || res.project_id || res.name;
    
    // 2. Refresh projects list
    const updatedList = await fetchProjects();
    setProjects(updatedList);
    
    // 3. Set active project and switch to live pipeline view
    setActiveProjectId(newId);
    setActiveView('pipeline');
    setPipelineTab('flow');

    // 4. Set state to running
    setProjectState((prev) => ({
      ...prev,
      projectId: newId,
      title: title,
      aspectRatio: (aspect as '16:9' | '9:16') || '16:9',
      status: 'running',
      overallProgress: 0,
      currentStageId: 'audio',
      stages: CANONICAL_12_STAGES.reduce((acc, s, idx) => {
        acc[s.id] = {
          id: s.id,
          status: idx === 0 ? 'running' : 'waiting',
          percentage: idx === 0 ? 10 : null
        };
        return acc;
      }, {} as Record<string, StageState>)
    }));

    // 5. Trigger the backend pipeline execution
    try {
      await startProjectRun(newId, true);
    } catch (runErr) {
      console.warn('Pipeline run started with background monitoring:', runErr);
    }

    // 6. Poll immediately for live progress updates
    setTimeout(loadState, 800);
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
      console.error(e);
    }
  };

  const handleOpenNewProject = () => {
    setActiveView('pipeline');
    setPipelineTab('new-project');
  };

  const handleDeleteProject = async (projectId: string): Promise<boolean> => {
    try {
      const ok = await deleteProject(projectId);
      if (ok) {
        const updatedList = await fetchProjects();
        setProjects(updatedList);
        if (activeProjectId === projectId) {
          if (updatedList.length > 0) {
            const nextId = updatedList[0].id || updatedList[0].project_id;
            if (nextId) setActiveProjectId(nextId);
          }
        }
      }
      return ok;
    } catch (e) {
      console.error('Failed to delete project:', e);
      return false;
    }
  };

  const handleRefreshProjects = async () => {
    try {
      const updatedList = await fetchProjects();
      setProjects(updatedList);
    } catch (e) {
      console.error('Failed to refresh projects:', e);
    }
  };

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100vw',
      overflow: 'hidden',
      backgroundColor: 'var(--bg-app)',
      fontFamily: 'var(--font-sans)',
      color: 'var(--text-primary)',
      transition: 'background-color 0.2s ease, color 0.2s ease'
    }}>
      {/* 1. LEFT SIDEBAR: Deep Navy matching reference image */}
      <Sidebar
        activeView={activeView}
        pipelineTab={pipelineTab}
        setActiveView={setActiveView}
        onSelectNewProject={handleOpenNewProject}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* 2. MAIN APPLICATION CONTENT AREA */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        height: '100%',
        overflow: 'hidden'
      }}>
        {/* TOP HEADER: Theme toggle, Navigation tabs group, system counters */}
        <Header
          onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
          onNewProject={handleOpenNewProject}
          backendHealthy={backendHealthy}
          llmHealthy={llmHealthy}
          activeLlmCount={activeLlmCount}
          projectCount={projects.length}
          activeProjectId={activeProjectId}
          theme={theme}
          onToggleTheme={toggleTheme}
          issues={issues}
          onOpenIssues={() => { setIssuesStage(null); setIssuesOpen(true); }}
          onOpenLlm={() => setActiveView('llm')}
        />
        <IssuesPanel
          open={issuesOpen}
          issues={issues}
          stageFilter={issuesStage}
          onShowAll={() => setIssuesStage(null)}
          onAcceptWarnings={async (stageId, stageLabel) => {
            const note = window.prompt(`Accept the current warnings of "${stageLabel}" and let the next stage start?\n\nThis records your decision for exactly these warnings (errors cannot be accepted). Why are they acceptable?`);
            if (!note || !note.trim()) return;
            const r = await acceptStageWarnings(activeProjectId, stageId, note);
            if (!r.ok) window.alert(`Not recorded: ${r.message}`);
            loadState();
          }}
          onClose={() => setIssuesOpen(false)}
          onLocate={(stageId) => {
            setIssuesOpen(false);
            setActiveView('pipeline');
            setPipelineTab('flow');
            setTimeout(() => document.querySelector(`[data-testid="stage-card-${stageId}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 150);
          }}
        />

        {/* FIXED PIPELINE TAB PILLS: centered, stays put while the body scrolls */}
        {(activeView === 'pipeline' || activeView === 'audio-input') && !pipelineFullPage && (
          <div
            data-testid="pipeline-pill-bar"
            style={{ flexShrink: 0, display: 'flex', justifyContent: 'center', padding: '12px 24px 0' }}
          >
            <div style={{
              display: 'inline-flex', gap: '8px'
            }}>
              {([
                ['new-project', 'New Project'],
                ['flow', 'Pipeline Execution Flow'],
                ['approvals', 'Approvals & Blockers'],
                ['communication', 'Agent Communication'],
                ['projects', 'Previous Projects']
              ] as const).map(([tab, label]) => {
                const active = (activeView === 'audio-input' ? 'new-project' : pipelineTab) === tab;
                const badge = tab === 'approvals'
                  ? Object.values(projectState.stages).filter(
                      (s) => s.status === 'blocked' || (s.blockers && s.blockers.length > 0)
                    ).length
                  : tab === 'projects' ? projects.length : 0;
                return (
                  <button
                    key={tab}
                    data-testid={`pill-tab-${tab}`}
                    className={tab === 'approvals' && badge > 0 ? 'issue-blink-amber' : undefined}
                    onClick={() => { setActiveView('pipeline'); setPipelineTab(tab); }}
                    style={{
                      height: '30px', padding: '0 14px', fontSize: '12px', lineHeight: 1,
                      fontWeight: 600, borderRadius: '6px',
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      border: active ? '1px solid #1890FF' : '1px solid rgba(24, 144, 255, 0.35)',
                      cursor: 'pointer', whiteSpace: 'nowrap',
                      color: active ? '#FFFFFF' : '#38BDF8',
                      backgroundColor: active ? '#1890FF' : 'rgba(24, 144, 255, 0.12)'
                    }}
                  >
                    {label}{badge > 0 ? ` ${badge}` : ''}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* SCROLLABLE MAIN BODY: Independently scrollable */}
        <main 
          data-testid="main-content-scroll-area"
          style={{
            flex: 1,
            padding: (activeView === 'pipeline' || activeView === 'audio-input') && !pipelineFullPage ? '12px 24px 24px' : '24px',
            overflowY: 'auto',
            overflowX: 'hidden',
            minHeight: 0
          }}
        >
          {/* DASHBOARD PAGE — HOUSES THE 4 TOP METRIC CARDS */}
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

          {/* LIVE PIPELINE VIEW — CONNECTED STAGE CARDS & REAL-TIME SUB-STAGE TRACKING & INLINE TABS */}
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
            />
          )}

          {/* PROJECTS LIST PAGE */}
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
            />
          )}

          {/* AGENTS CENTER PAGE */}
          {activeView === 'agents' && (
            <AgentsCenterPage agents={agents} />
          )}

          {/* SKILLS PAGE */}
          {activeView === 'skills' && (
            <SkillsPage skills={skills} />
          )}

          {/* WORK LOG PAGE: what the assistant is doing, live */}
          {activeView === 'work-log' && <WorkLogPage />}

          {/* LLM CONNECTION PAGE (opened from the LLM pill in the header) */}
          {activeView === 'llm' && (
            <LlmPage onChanged={async () => { const lh = await fetchLlmHealth(); setLlmHealthy(lh.ok); }} />
          )}

          {/* VISUAL AI EDITOR PAGE */}
          {activeView === 'visual-editor' && (
            <VisualAiEditorPage activeProjectId={activeProjectId} />
          )}

          {/* DIAGNOSTICS PAGE */}
          {activeView === 'diagnostics' && (
            <div style={{
              backgroundColor: 'var(--bg-card)',
              borderRadius: '6px',
              border: '1px solid var(--border-card)',
              padding: '32px',
              maxWidth: '1200px',
              margin: '0 auto',
              boxShadow: 'var(--shadow-card)'
            }}>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px' }}>
                System Diagnostics & Infrastructure Health
              </h2>
              <div style={{
                backgroundColor: 'var(--bg-elevated)',
                padding: '24px',
                borderRadius: '4px',
                border: '1px solid var(--border-subtle)',
                fontFamily: 'var(--font-mono)',
                fontSize: '13px',
                lineHeight: 1.8,
                color: 'var(--text-secondary)'
              }}>
                <div>[STATUS] FastAPI Backend: {backendHealthy ? 'ONLINE (http://127.0.0.1:8000)' : 'UNREACHABLE'}</div>
                <div>[AGENTS] Canonical Agents: {agents.length} Registered (13 Video + 7 System)</div>
                <div>[PROJECTS] Total Workspaces: {projects.length}</div>
                <div>[LLM GATEWAY] Active In-Flight LLM Dispatches: {activeLlmCount}</div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
