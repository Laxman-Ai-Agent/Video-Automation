import { useState, useEffect, useCallback, useRef } from 'react';
import { 
  fetchProjectPipeline, 
  fetchProjectStatus, 
  fetchProjectMonitor,
  fetchProjects,
  createProjectWithAudio,
  startProjectRun, 
  cancelProjectRun 
} from '../services/api';
import { subscribeToEvents, ConnectionStatus } from '../services/sse';
import { CANONICAL_12_STAGES, PipelineIssue, PipelineProjectState, StageState, StageStatus } from '../types/pipeline';
import { processPipelineData } from './pipelineStageMapper';
import { DEFAULT_MEDIA, type MediaMix } from '../services/mediaMix';

interface UseProjectPipelineProps {
  activeProjectId: string;
  setActiveProjectId: (id: string) => void;
  setProjects: React.Dispatch<React.SetStateAction<any[]>>;
  onAfterAnalyze?: () => void;
}

export function useProjectPipeline({
  activeProjectId,
  setActiveProjectId,
  setProjects,
  onAfterAnalyze
}: UseProjectPipelineProps) {
  const [projectState, setProjectState] = useState<PipelineProjectState>({
    projectId: 'sample-01',
    title: 'Telugu Audio-to-Video Production',
    aspectRatio: '16:9',
    overallProgress: 0,
    currentStageId: 'audio',
    status: 'idle',
    stages: CANONICAL_12_STAGES.reduce((acc, s) => {
      acc[s.id] = { id: s.id, status: 'waiting', percentage: null };
      return acc;
    }, {} as Record<string, StageState>),
    updatedAt: new Date().toISOString()
  });

  const [issues, setIssues] = useState<PipelineIssue[]>([]);
  const [sseStatus, setSseStatus] = useState<ConnectionStatus>('reconnecting');
  const loadStateInFlightRef = useRef<boolean>(false);

  // Parallel fetch pipeline view, job status, and monitor data
  const loadState = useCallback(async () => {
    if (!activeProjectId || loadStateInFlightRef.current) return;
    loadStateInFlightRef.current = true;

    try {
      function withTimeout<T>(p: Promise<T>, ms = 8000): Promise<T> {
        return Promise.race([p, new Promise<T>((_, reject) => setTimeout(() => reject(new Error('request timed out')), ms))]);
      }

      const [pipeData, statusData, monitorData] = await Promise.all([
        withTimeout(fetchProjectPipeline(activeProjectId), 120000),
        withTimeout(fetchProjectStatus(activeProjectId)).catch(() => null),
        withTimeout(fetchProjectMonitor(activeProjectId)).catch(() => null)
      ]);

      if (pipeData && pipeData.stages) {
        setProjectState((prev) => {
          const result = processPipelineData(pipeData, statusData, monitorData, prev, activeProjectId);
          setIssues((prevIssues) => (JSON.stringify(prevIssues) === JSON.stringify(result.issueList) ? prevIssues : result.issueList));
          return result.stateChanged ? result.nextState : prev;
        });
      }
    } catch (err) {
      console.error('Error fetching project pipeline state:', err);
    } finally {
      loadStateInFlightRef.current = false;
    }
  }, [activeProjectId]);

  // Periodic polling & focus/visibility sync
  useEffect(() => {
    loadState();
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

  // SSE Live Events Subscription
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

  const handleStartRun = async () => {
    try {
      await startProjectRun(activeProjectId);
      setProjectState((prev) => ({ ...prev, status: 'running' }));
      setTimeout(loadState, 600);
    } catch (e) {
      console.error('Failed to start project run:', e);
    }
  };

  const handleCancelRun = async () => {
    try {
      await cancelProjectRun(activeProjectId);
      setProjectState((prev) => ({ ...prev, status: 'paused' }));
      setTimeout(loadState, 600);
    } catch (e) {
      console.error('Failed to cancel project run:', e);
    }
  };

  const handleAnalyze = async (
    title: string, 
    audioFile: File, 
    aspect: string,
    reusableTemplates: boolean = false,
    media: MediaMix = DEFAULT_MEDIA,
    transcribeMode: 'colab' | 'local' = 'colab',
    imageMode: 'colab' | 'normal' = 'colab',
    videoMode: 'colab' | 'normal' = 'colab'
  ) => {
    const res = await createProjectWithAudio(title, audioFile, aspect, reusableTemplates, media, transcribeMode, imageMode, videoMode);
    const newId = res.id || res.project_id || res.name;
    
    const updatedList = await fetchProjects();
    setProjects(updatedList);
    
    setActiveProjectId(newId);
    if (onAfterAnalyze) onAfterAnalyze();

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

    try {
      await startProjectRun(newId);
    } catch (runErr) {
      console.warn('Pipeline run started with background monitoring:', runErr);
    }

    setTimeout(loadState, 800);
  };

  return {
    projectState,
    setProjectState,
    issues,
    setIssues,
    sseStatus,
    loadState,
    handleStartRun,
    handleCancelRun,
    handleAnalyze
  };
}
