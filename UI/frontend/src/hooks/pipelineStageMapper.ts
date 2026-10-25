import { CANONICAL_12_STAGES, PipelineIssue, PipelineProjectState, StageState } from '../types/pipeline';

export const normalizeTimestamp = (ts: any): string | undefined => {
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

export interface ProcessPipelineDataResult {
  nextState: PipelineProjectState;
  issueList: PipelineIssue[];
  stateChanged: boolean;
}

export function processPipelineData(
  pipeData: any,
  statusData: any,
  monitorData: any,
  prev: PipelineProjectState,
  activeProjectId: string
): ProcessPipelineDataResult {
  const isJobRunning = Boolean(pipeData?.running || statusData?.running || monitorData?.job?.state === 'running');
  const jobError = statusData?.error || monitorData?.job?.error || monitorData?.status?.error;
  const jobMsg = statusData?.message || monitorData?.job?.message || monitorData?.status?.message;
  const jobPct = statusData?.percent !== undefined && statusData?.percent !== null ? statusData.percent : monitorData?.status?.percent;

  const rawStages = pipeData?.stages || {};
  const mappedStages: Record<string, StageState> = {};
  let completedCount = 0;
  let activeStageId = 'audio';

  const isArray = Array.isArray(rawStages);

  CANONICAL_12_STAGES.forEach((cfg) => {
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

  const issueList: PipelineIssue[] = (pipeData?.issues || []).map((i: any) => ({
    id: i.id, severity: i.severity, stageId: i.stage_id ?? null, stageLabel: i.stage_label, source: i.source,
    component: i.component, message: i.message, code: i.code, attempts: i.attempts, retryLimit: i.retry_limit, at: i.at,
    subtask: i.subtask ?? null, stageStatus: i.stage_status ?? null
  }));

  issueList.forEach((i) => {
    const s = i.stageId ? mappedStages[i.stageId] : undefined;
    if (!s) return;
    if (i.severity === 'warning') s.issueWarnings = (s.issueWarnings || 0) + 1;
    else s.issueErrors = (s.issueErrors || 0) + 1;
    if (s.status === 'completed') return;
    if (i.severity === 'error' && s.status !== 'running' && s.status !== 'retrying') {
      s.status = 'failed';
      s.errors = [i.message];
    }
    if (i.severity === 'stuck') s.stuck = true;
  });

  if (isJobRunning && !jobError && !Object.values(mappedStages).some(s => s.status === 'running')) {
    const firstIncomplete = CANONICAL_12_STAGES.find(c => mappedStages[c.id].status !== 'completed');
    if (firstIncomplete) {
      mappedStages[firstIncomplete.id].status = 'running';
      mappedStages[firstIncomplete.id].percentage = jobPct ?? null;
      activeStageId = firstIncomplete.id;
    }
  }

  if (jobError) {
    const targetFailedId = activeStageId || 'analyzer';
    if (mappedStages[targetFailedId]) {
      mappedStages[targetFailedId].status = 'failed';
      mappedStages[targetFailedId].errors = [jobError];
    }
  }

  const totalStages = CANONICAL_12_STAGES.length;
  const overall = Math.min(100, Math.round((completedCount / totalStages) * 100));

  const nextTitle = monitorData?.name || pipeData?.project || prev.title;
  const nextAspect = pipeData?.aspect || prev.aspectRatio;
  const isAnyStageRunning = Object.values(mappedStages).some(s => s.status === 'running' || s.status === 'retrying');
  const nextStatus = jobError 
    ? 'failed' 
    : (isJobRunning || isAnyStageRunning 
        ? 'running' 
        : (completedCount === totalStages ? 'completed' : 'idle'));

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
      return {
        nextState: prev,
        issueList,
        stateChanged: false
      };
    }
  }

  return {
    nextState: {
      ...prev,
      projectId: activeProjectId,
      title: nextTitle,
      aspectRatio: nextAspect,
      overallProgress: overall,
      currentStageId: activeStageId,
      status: nextStatus,
      stages: mappedStages,
      updatedAt: new Date().toISOString()
    },
    issueList,
    stateChanged: true
  };
}
