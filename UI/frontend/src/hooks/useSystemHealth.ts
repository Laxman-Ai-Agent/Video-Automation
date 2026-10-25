import { useState, useEffect } from 'react';
import { 
  fetchHealth, 
  fetchLlmHealth, 
  fetchProjects, 
  fetchAgents, 
  fetchSkills, 
  fetchLlmActive,
  deleteProject
} from '../services/api';

export function useSystemHealth() {
  const [backendHealthy, setBackendHealthy] = useState<boolean>(true);
  const [llmHealthy, setLlmHealthy] = useState<boolean>(false);
  const [llmConnecting, setLlmConnecting] = useState<boolean>(false);
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

  // Persist active project ID whenever it changes
  useEffect(() => {
    if (activeProjectId) {
      localStorage.setItem('a2v_active_project', activeProjectId);
    }
  }, [activeProjectId]);

  // Initial data fetch & periodic health polling with hysteresis
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

  return {
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
  };
}
