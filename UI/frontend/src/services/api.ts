import { DEFAULT_MEDIA, MediaMix } from './mediaMix';

export const API_BASE = ''; // proxied via Vite to http://127.0.0.1:8000

export async function fetchHealth(): Promise<{ ok: boolean }> {
  const directUrl = 'http://127.0.0.1:8000/health';
  const proxyUrl = `${API_BASE}/health`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 4000);

  const probe = (url: string) =>
    fetch(url, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data?.ok) return true;
        throw new Error('Payload not ok');
      });

  try {
    const isOk = await Promise.any([probe(directUrl), probe(proxyUrl)]);
    clearTimeout(timeoutId);
    return { ok: isOk };
  } catch {
    clearTimeout(timeoutId);
    return { ok: false };
  }
}

export interface WorkLogEntry { id: number; time: string; status: 'doing' | 'done' | 'problem' | 'fixed'; title: string; detail: string }

/** The assistant's Work Log (null when the server cannot be reached). */
export async function fetchWorkLog(): Promise<WorkLogEntry[] | null> {
  try {
    const res = await fetch(`${API_BASE}/work-log`);
    return res.ok ? (await res.json()).entries : null;
  } catch {
    return null;
  }
}

export async function fetchLlmHealth(): Promise<{ ok: boolean; provider?: string; latency_ms?: number; message?: string }> {
  const directUrl = 'http://127.0.0.1:8000/llm/health';
  const proxyUrl = `${API_BASE}/llm/health`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);

  const probe = (url: string) =>
    fetch(url, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
      });

  try {
    const data = await Promise.any([probe(directUrl), probe(proxyUrl)]);
    clearTimeout(timeoutId);
    return {
      ok: Boolean(data?.ok),
      provider: data?.provider,
      latency_ms: data?.latency_ms,
      message: data?.message
    };
  } catch {
    clearTimeout(timeoutId);
    return { ok: false };
  }
}

// --- LLM connection page (UI/backend/routes/llm.py) ---
export interface LlmProviderInfo { id: string; name: string; default_model: string; needs_key: boolean; models?: { id: string; name: string }[] }
export interface LlmSettings {
  model_locked?: boolean;
  active_provider: string;
  active_provider_name: string;
  active_model: string;
  auth_method?: string;
  auth_method_name?: string;
  base_url: string;
  has_api_key: boolean;
  api_key_masked: string;
  configured_provider: string;
  available_providers: LlmProviderInfo[];
  claude_cli_installed: boolean;
  connection_status: 'active' | 'offline' | 'unknown';
  status_message: string;
  latency_ms: number | null;
  last_verified_at: number | null;
}
export interface LlmForm { provider?: string; model?: string; api_key?: string; base_url?: string }
export interface LlmTestResult { ok: boolean; provider: string; provider_name?: string; model: string; latency_ms: number; message: string }
export interface LlmDetected { id: string; name: string; model: string; source: string }
export interface LlmTryResult { id: string; name: string; source: string; ok: boolean; message: string; latency_ms: number }
export interface LlmAutoResult {
  connected: boolean;
  provider: string | null;
  provider_name: string | null;
  model: string | null;
  latency_ms: number | null;
  message: string;
  results: LlmTryResult[];
}

async function llmRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(typeof err.detail === 'string' ? err.detail : err.detail?.message || `Request failed (HTTP ${res.status})`);
  }
  return res.json();
}

const postJson = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const fetchLlmSettings = () => llmRequest<LlmSettings>('/llm/settings');
export const saveLlmSettings = (body: LlmForm) => llmRequest<LlmSettings>('/llm/settings', postJson(body));
export const testLlmConnection = (body: LlmForm = {}) => llmRequest<LlmTestResult>('/llm/test', postJson(body));
export const detectLlm = () => llmRequest<{ options: LlmDetected[] }>('/llm/detect');
export const autoConnectLlm = () => llmRequest<LlmAutoResult>('/llm/auto-connect', { method: 'POST' });

export async function fetchProjects(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/projects`);
    if (res.ok) {
      return await res.json();
    }
  } catch {}
  try {
    const fallbackRes = await fetch('http://127.0.0.1:8000/projects');
    if (fallbackRes.ok) {
      return await fallbackRes.json();
    }
  } catch {}
  return [];
}

export async function deleteProject(projectId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}?confirm=true`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const fallbackRes = await fetch(`http://127.0.0.1:8000/projects/${encodeURIComponent(projectId)}?confirm=true`, {
        method: 'DELETE'
      });
      return fallbackRes.ok;
    }
    return true;
  } catch {
    try {
      const fallbackRes = await fetch(`http://127.0.0.1:8000/projects/${encodeURIComponent(projectId)}?confirm=true`, {
        method: 'DELETE'
      });
      return fallbackRes.ok;
    } catch {
      return false;
    }
  }
}

export async function fetchProjectPipeline(projectId: string): Promise<any | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/pipeline`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchProjectStatus(projectId: string): Promise<any | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/status`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchProjectState(projectId: string): Promise<any | null> {
  try {
    const pipeRes = await fetch(`${API_BASE}/projects/${projectId}/pipeline`);
    if (pipeRes.ok) {
      return await pipeRes.json();
    }
    const orchRes = await fetch(`${API_BASE}/projects/${projectId}/orchestrator/status`);
    if (orchRes.ok) {
      return await orchRes.json();
    }
    return null;
  } catch {
    return null;
  }
}

export async function fetchAgents(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/agents?all=true`);
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchSkills(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/skills`);
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchSkillDetails(skillId: string): Promise<any | null> {
  try {
    const res = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillId)}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function deleteSkill(skillId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillId)}`, {
    method: 'DELETE'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || 'Failed to delete skill');
  }
  return await res.json();
}

export async function fetchLlmActive(): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/llm/active`);
    if (!res.ok) return { active_count: 0, requests: [] };
    return await res.json();
  } catch {
    return { active_count: 0, requests: [] };
  }
}

export async function createProjectWithAudio(
  name: string,
  audioFile: File,
  aspect: string = '16:9',
  reusableTemplates: boolean = false,
  media: MediaMix = DEFAULT_MEDIA
): Promise<any> {
  const formData = new FormData();
  formData.append('name', name);
  formData.append('audio', audioFile);
  formData.append('aspect', aspect);
  formData.append('reusable_motion_templates', reusableTemplates ? 'true' : 'false');
  formData.append('ai_images', media.ai_images ? 'true' : 'false');
  formData.append('motion_kit', media.motion_kit ? 'true' : 'false');

  const res = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    body: formData
  });
  if (!res.ok) {
    let msg = 'Failed to create project';
    try {
      const err = await res.json();
      msg = err.detail?.message || err.detail || err.message || msg;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  return await res.json();
}

/** Asset Collection: what the Visual Plan asked for and what was collected for each request (GET /projects/{id}/assets). null when the project has none. */
export async function fetchAssets(projectId: string): Promise<any | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/assets`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

/** Manual upload / override of an asset for a specific visual requirement */
export async function uploadAsset(
  projectId: string,
  requirementId: string,
  sceneId: number,
  file: File
): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('requirement_id', requirementId);
  formData.append('scene_id', String(sceneId));

  const res = await fetch(`${API_BASE}/projects/${projectId}/assets/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    let msg = 'Failed to upload custom asset';
    try {
      const err = await res.json();
      msg = err.detail || err.message || msg;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  return await res.json();
}

/** Update asset properties: video trim frame range (clip_start, clip_dur, clip_end) or icon name */
export async function updateAsset(
  projectId: string,
  payload: {
    requirement_id: string;
    scene_id?: number;
    kind?: string;
    clip_start?: number;
    clip_dur?: number;
    clip_end?: number;
    icon_name?: string;
  }
): Promise<any> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/assets/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let msg = 'Failed to update asset settings';
    try {
      const err = await res.json();
      msg = err.detail || err.message || msg;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  return await res.json();
}

export async function createProject(title: string, aspectRatio: string = '16:9'): Promise<any> {
  const res = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, aspect: aspectRatio })
  });
  if (!res.ok) throw new Error('Failed to create project');
  return await res.json();
}

// Starts the autonomous run: every stage from `fromStage` (or the first unfinished one) to the end, each starting by itself when the one before it completed with nothing unresolved.
export async function startProjectRun(projectId: string, fromStage?: string): Promise<any> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/orchestrator/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fromStage ? { from_stage: fromStage, resume: true } : { resume: true })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || err.message || `Failed to start the run (HTTP ${res.status})`);
  }
  return await res.json();
}

export async function cancelProjectRun(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/cancel`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to cancel run');
  return await res.json();
}

export async function fetchAgentCommunications(
  projectId: string,
  limit: number = 100
): Promise<{ project_id: string; count: number; messages: any[] }> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/agent-communications?limit=${limit}&reverse=true`);
    if (!res.ok) return { project_id: projectId, count: 0, messages: [] };
    return await res.json();
  } catch {
    return { project_id: projectId, count: 0, messages: [] };
  }
}

// Approvals & Timeline Decision APIs
export async function fetchApprovals(status: string = 'pending', projectId?: string): Promise<any[]> {
  try {
    let url = `${API_BASE}/approvals?status=${encodeURIComponent(status)}`;
    if (projectId) url += `&project_id=${encodeURIComponent(projectId)}`;
    const res = await fetch(url);
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function llmDecideApproval(approvalId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/approvals/${approvalId}/llm-decide`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || 'The LLM approval review could not decide');
  }
  return await res.json();
}

export async function fetchTimelineApprovalState(projectId: string): Promise<any | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/timeline-approval`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchRenderVideoState(projectId: string): Promise<any | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/render-video`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchProject(projectId: string): Promise<any | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export interface SubtaskStep {
  n: number | null;
  name: string;
  status: string;
  detail: string | null;
  checks_passed?: number | null;
  checks_total?: number | null;
  progress_percent?: number | null;
  completion_percent?: number;
  disabled?: boolean;
  // the LLM's check of this step: 'error' = the call failed (never shown as a pass); current = it checked exactly the result now recorded
  llm_check?: { verdict: 'confirms' | 'questions' | 'rejects' | 'error'; note: string; model: string | null; latency_ms: number; at: number; current: boolean } | null;
  llm_verification?: {
    state: 'verified' | 'in_progress' | 'pending' | 'rejected' | 'questioned' | 'failed' | 'unverified';
    model?: string | null;
    latency_ms?: number;
    note?: string;
    verdict?: string;
  };
}

// The steps a stage really recorded in its report, plus its stored LLM review and logged LLM calls (UI/backend/routes/pipeline.py)
export interface StageSubtasks {
  stage_id: string;
  report: string | null;
  written: number | null;
  steps: SubtaskStep[];
  llm_review: { status: string | null; score: number | null; model: string | null; summary: string | null; written: number } | null;
  llm_calls: Record<string, number>;
  llm_checks_running: boolean;
  active_step?: number | null;
  active_model?: string;
  overall_progress?: number;
}

export async function runStageStepChecks(projectId: string, stageId: string): Promise<{ started: boolean; pending: number; running: boolean } | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/stages/${stageId}/subtasks/llm-check`, { method: 'POST' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// Run only one step of a stage again (Visual Planning: its warnings are solved; any other step: its LLM check is asked again)
export async function retryStageSubtask(projectId: string, stageId: string, n: number): Promise<{ ok: boolean; kind?: string; message?: string }> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/stages/${stageId}/subtasks/${n}/retry`, { method: 'POST' });
    const body = await res.json().catch(() => null);
    if (!res.ok) return { ok: false, message: body?.message || body?.detail?.message || `HTTP ${res.status}` };
    return body?.started === false ? { ok: false, message: 'A check of this stage is already running: try again when it finishes' } : { ok: true, kind: body?.kind };
  } catch (e: any) {
    return { ok: false, message: String(e?.message || e) };
  }
}

export async function fetchStageSubtasks(projectId: string, stageId: string): Promise<StageSubtasks | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/stages/${stageId}/subtasks`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchProjectMonitor(projectId: string): Promise<any | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/monitor`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// RUN / Retry of a stage = the autonomous run from that stage: it works the stage (what is already current is reused) and every later stage starts by itself when the one before completed clean.
export async function runStage(projectId: string, stageId: string): Promise<any> {
  return await startProjectRun(projectId, stageId);
}

export async function stopStage(projectId: string, stageId?: string): Promise<any> {
  // If specific cancel endpoint exists for stage, call that in addition to global cancel
  if (stageId === 'render') {
    try {
      await fetch(`${API_BASE}/projects/${projectId}/render-video/cancel`, { method: 'POST' });
    } catch {
      // ignore and proceed to main cancel
    }
  } else if (stageId === 'qc') {
    try {
      await fetch(`${API_BASE}/projects/${projectId}/final-qc/cancel`, { method: 'POST' });
    } catch {
      // ignore and proceed to main cancel
    }
  }

  // Canonical cooperative cancellation through jobs and orchestrator
  const res = await fetch(`${API_BASE}/projects/${projectId}/cancel`, {
    method: 'POST'
  });

  if (!res.ok) {
    let errMsg = `Failed to stop stage (HTTP ${res.status})`;
    try {
      const err = await res.json();
      errMsg = err.detail?.message || err.message || err.detail || errMsg;
    } catch {
      // ignore
    }
    throw new Error(errMsg);
  }

  return await res.json();
}

export async function executeStageAction(
  projectId: string, 
  actionKind: string, 
  stageId?: string
): Promise<any> {
  if (actionKind === 'stop_stage' || actionKind === 'cancel_stage') {
    return await stopStage(projectId, stageId);
  }

  if (stageId && (actionKind.startsWith('run_') || actionKind.startsWith('retry_'))) {
    return await runStage(projectId, stageId);
  }

  let endpoint = '';
  let method = 'POST';
  let body: any = null;

  switch (actionKind) {
    case 'retry_transcribe':
      endpoint = `${API_BASE}/projects/${projectId}/transcribe`;
      break;
    case 'run_segmentation':
      endpoint = `${API_BASE}/projects/${projectId}/segmentation/run`;
      break;
    case 'retry_plan':
      endpoint = `${API_BASE}/projects/${projectId}/visual-planning/run`;
      break;
    case 'run_motion':
      endpoint = `${API_BASE}/projects/${projectId}/motion/run`;
      break;
    case 'retry_timeline':
      endpoint = `${API_BASE}/projects/${projectId}/timeline-build/run`;
      break;
    case 'open_timeline_approval':
    case 'open_render':
    case 'open_final_qc':
    case 'open_timeline_build':
    case 'open_qc':
      return { kind: 'drawer', stageId: stageId || actionKind.replace('open_', '') };
    default:
      endpoint = `${API_BASE}/projects/${projectId}/orchestrator/run`;
      body = JSON.stringify({ from_stage: stageId, resume: true, aspect: '16:9' });
      break;
  }

  const res = await fetch(endpoint, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.message || err.detail || `Action ${actionKind} failed`);
  }
  return await res.json();
}

export interface AudioAnalysisResult {
  ok: boolean;
  data?: any;
  error?: string;
  status?: number;
  filename?: string;
  artifactPath?: string;
}

export async function fetchAudioAnalysis(projectId: string): Promise<AudioAnalysisResult> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/analysis`);
    if (res.status === 404 || res.status === 409) {
      const errJson = await res.json().catch(() => ({}));
      const message = errJson?.error?.message || errJson?.detail || `Audio analysis artifact (audio-analysis.json) is unavailable for project '${projectId}'`;
      return {
        ok: false,
        status: res.status,
        error: message
      };
    }
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      const message = errJson?.error?.message || errJson?.detail || `HTTP ${res.status}: Failed to load audio analysis`;
      return {
        ok: false,
        status: res.status,
        error: message
      };
    }
    const data = await res.json();
    return {
      ok: true,
      status: 200,
      data,
      filename: data?._filename || 'audio_analysis.json',
      artifactPath: data?._artifact_path || `projects/${projectId}/audio_analysis.json`
    };
  } catch (err: any) {
    return {
      ok: false,
      status: 0,
      error: err?.message || 'Network error accessing audio analysis artifact'
    };
  }
}

export interface AnalysisSubtask {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  percent: number | null;
  llm: { status: 'none' | 'pending' | 'running' | 'completed' | 'failed'; detail: string };
  message: string;
}

export interface AnalysisSubtasks {
  running: boolean;
  percent: number;
  subtasks: AnalysisSubtask[];
}

export async function fetchAnalysisSubtasks(projectId: string): Promise<AnalysisSubtasks> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/analysis/subtasks`);
  if (!res.ok) throw new Error(`HTTP ${res.status}: could not read the Audio Analysis subtasks`);
  return res.json();
}

export interface SceneSegmentationResult {
  ok: boolean;
  data?: any;
  error?: string;
  status?: number;
}

export async function fetchSceneSegmentation(projectId: string): Promise<SceneSegmentationResult> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/segmentation`);
    if (res.status === 404 || res.status === 409) {
      const errJson = await res.json().catch(() => ({}));
      return {
        ok: false,
        status: res.status,
        error: errJson?.error?.message || errJson?.detail || 'Scene Segmentation has not been run yet for this project.'
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        status: res.status,
        error: `HTTP ${res.status}: Failed to load scene segmentation`
      };
    }
    const data = await res.json();
    return {
      ok: true,
      status: 200,
      data
    };
  } catch (err: any) {
    return {
      ok: false,
      status: 0,
      error: err?.message || 'Network error accessing scene segmentation artifact'
    };
  }
}

export interface TranscriptComparisonData {
  raw_file: string;
  final_file: string;
  verified: boolean;
  language: string;
  duration: number;
  llm: { status: string | null; model: string | null; segments_sent: number | null; error: string | null };
  alignment: string | null;
  stage_review: { status: string | null; score: number | null } | null;
  corrections_applied: number;
  corrections_rejected: number;
  corrections: any[];
  segments: {
    id: number;
    start: number;
    end: number;
    raw_text: string;
    final_text: string;
    changed: boolean;
    final_words?: { w: string; start: number; end: number; timing: string | null; edit: string | null }[];
  }[];
}

/** The raw Whisper transcript next to the final LLM-verified one (read-only); null when the audio has not been analyzed yet. */
export async function fetchTranscriptComparison(projectId: string): Promise<TranscriptComparisonData | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/transcript?view=compare`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

/** The final transcript the video is made from (segments with their text and times); null when the audio has not been analyzed yet. */
export async function fetchFinalTranscript(projectId: string): Promise<{ segments: { id: number; start: number; end: number; text: string }[] } | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/transcript`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function runLlmReview(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/llm-review/run`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || err.message || 'LLM Review execution failed');
  }
  return await res.json();
}

export interface VisualPlanningResult {
  ok: boolean;
  status: number;
  data?: any;
  error?: string;
}

export async function fetchVisualPlanning(projectId: string): Promise<VisualPlanningResult> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/visual-planning`);
    if (res.status === 404 || res.status === 409) {
      const errJson = await res.json().catch(() => ({}));
      return {
        ok: false,
        status: res.status,
        error: errJson?.error?.message || errJson?.detail || 'Visual Planning has not been run yet for this project.'
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        status: res.status,
        error: `HTTP ${res.status}: Failed to load visual planning`
      };
    }
    const data = await res.json();
    return {
      ok: true,
      status: 200,
      data
    };
  } catch (err: any) {
    return {
      ok: false,
      status: 0,
      error: err?.message || 'Network error accessing visual planning artifact'
    };
  }
}

export interface MotionPlanningResult {
  ok: boolean;
  status: number;
  data?: any;
  error?: string;
}

export async function fetchMotionPlanning(projectId: string): Promise<MotionPlanningResult> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/motion-planning`);
    if (res.status === 404 || res.status === 409) {
      const errJson = await res.json().catch(() => ({}));
      return {
        ok: false,
        status: res.status,
        error: errJson?.error?.message || errJson?.detail || 'Motion Planning has not been run yet for this project.'
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        status: res.status,
        error: `HTTP ${res.status}: Failed to load motion planning`
      };
    }
    const data = await res.json();
    return {
      ok: true,
      status: 200,
      data
    };
  } catch (err: any) {
    return {
      ok: false,
      status: 0,
      error: err?.message || 'Network error accessing motion planning artifact'
    };
  }
}

export interface TimelineBuildResult {
  ok: boolean;
  status: number;
  data?: any;
  error?: string;
}

export async function fetchTimelineBuildData(projectId: string): Promise<TimelineBuildResult> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/timeline-build`);
    if (res.status === 404 || res.status === 409) {
      const errJson = await res.json().catch(() => ({}));
      return {
        ok: false,
        status: res.status,
        error: errJson?.error?.message || errJson?.detail || 'Timeline Build has not been run yet for this project.'
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        status: res.status,
        error: `HTTP ${res.status}: Failed to load timeline build`
      };
    }
    const data = await res.json();
    return {
      ok: true,
      status: 200,
      data
    };
  } catch (err: any) {
    return {
      ok: false,
      status: 0,
      error: err?.message || 'Network error accessing timeline build artifact'
    };
  }
}

export async function fetchTimelineJson(projectId: string): Promise<TimelineBuildResult> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/timeline-build/timeline`);
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      return {
        ok: false,
        status: res.status,
        error: errJson?.error?.message || errJson?.detail || 'Timeline JSON is not available.'
      };
    }
    const data = await res.json();
    return {
      ok: true,
      status: 200,
      data
    };
  } catch (err: any) {
    return {
      ok: false,
      status: 0,
      error: err?.message || 'Network error accessing timeline.json'
    };
  }
}

export async function fetchTimelineStills(projectId: string): Promise<TimelineBuildResult> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/timeline-build/stills`);
    if (!res.ok) return { ok: false, status: res.status, error: 'Preview stills are not available.' };
    return { ok: true, status: 200, data: await res.json() };
  } catch (err: any) {
    return { ok: false, status: 0, error: err?.message || 'Network error accessing preview stills' };
  }
}

export async function fetchTimelineThumbnails(projectId: string): Promise<TimelineBuildResult> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/timeline-build/thumbnails`);
    if (!res.ok) return { ok: false, status: res.status, error: 'Thumbnails are not available.' };
    return { ok: true, status: 200, data: await res.json() };
  } catch (err: any) {
    return { ok: false, status: 0, error: err?.message || 'Network error accessing thumbnails' };
  }
}

export async function fetchTimelineWaveform(projectId: string): Promise<TimelineBuildResult> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/timeline-build/waveform`);
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      return {
        ok: false,
        status: res.status,
        error: errJson?.error?.message || errJson?.detail || 'Audio waveform is not available.'
      };
    }
    const data = await res.json();
    return {
      ok: true,
      status: 200,
      data
    };
  } catch (err: any) {
    return {
      ok: false,
      status: 0,
      error: err?.message || 'Network error accessing waveform data'
    };
  }
}

export async function fetchMotionData(projectId: string): Promise<TimelineBuildResult> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/motion`);
    if (!res.ok) {
      return {
        ok: false,
        status: res.status,
        error: `HTTP ${res.status}: Failed to load motion data`
      };
    }
    const data = await res.json();
    return {
      ok: true,
      status: 200,
      data
    };
  } catch (err: any) {
    return {
      ok: false,
      status: 0,
      error: err?.message || 'Network error accessing motion branch data'
    };
  }
}

export async function fetchAgentGrowth(agentId: string): Promise<any | null> {
  try {
    const res = await fetch(`${API_BASE}/agents/${agentId}/growth`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchAgentUpgrades(agentId: string): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/agents/${agentId}/upgrades`);
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchAgentIntelligence(agentId: string): Promise<any | null> {
  try {
    const res = await fetch(`${API_BASE}/agents/${agentId}/intelligence`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function generateChartAsset(
  projectId: string,
  params: {
    chart_type?: string;
    labels: string[];
    data: number[];
    title?: string;
    label?: string;
    dark_mode?: boolean;
  }
): Promise<{ ok: boolean; filename?: string; url?: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/assets/generate-chart`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    return await res.json();
  } catch (err: any) {
    return { ok: false, error: err?.message || 'Failed to generate chart' };
  }
}

export async function generateMapAsset(
  projectId: string,
  params: {
    place_name: string;
    width?: number;
    height?: number;
  }
): Promise<{ ok: boolean; filename?: string; url?: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/assets/generate-map`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    return await res.json();
  } catch (err: any) {
    return { ok: false, error: err?.message || 'Failed to generate map' };
  }
}

export async function fetchSfxCatalog(): Promise<{ ok: boolean; sfx: any[] }> {
  try {
    const res = await fetch(`${API_BASE}/projects/_/assets/sfx-catalog`);
    if (!res.ok) return { ok: false, sfx: [] };
    return await res.json();
  } catch {
    return { ok: false, sfx: [] };
  }
}






// Motion Generation scene by scene (GET /projects/{id}/motion-generation/scenes): the code written for each scene, its elements, its checks and how it was made
export interface MotionGenScene {
  scene_id: number; start: number | null; end: number | null; meaning: string | null; timing: { start: number; end: number; start_frame: number; end_frame: number } | null; duration_frames: number | null;
  code: string; lines: number; bytes: number; file: string; code_changed: boolean; source_sha256: string | null; input_fingerprint: string | null;
  required_elements: string[]; implemented_elements: string[]; missing_required_elements: string[];
  element_classifications: { element_id: string; requested_effect: string; is_supported: boolean; is_3d: boolean; fallback_strategy: string; capability_limitation: string | null }[];
  compile_status: string | null; security_audit: { passed: boolean; findings: any[] } | null;
  preview_result: { passed: boolean; score: number; safe_zone_passed: boolean; typography_passed: boolean; contrast_passed: boolean; findings: any[] } | null;
  generation: { provider?: string; model?: string; attempt_count?: number; latency_ms?: number } | null; repair_attempts: number | null; warnings: string[];
  descriptors: { element_id: string; element_type: string; component_id: string; preset_id: string; start: number; end: number }[]; validation_notes: any[];
}
export interface MotionGenScenes { mode: string | null; status: string | null; run_id: string | null; typecheck: { status: string } | null; diagnostics: Record<string, any> | null; warnings: string[]; scenes: MotionGenScene[] }

export async function fetchMotionGenerationScenes(projectId: string): Promise<MotionGenScenes | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${projectId}/motion-generation/scenes`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

// The rules of the stages and the user's switch for each one (SYSTEM/policies/rule_catalog.py, rule_switches.py): OFF = the rule is never evaluated, so it cannot block or warn
export interface RuleRow { stage: string; stage_label: string; rule: string; severity: string; says: string; calls: number; on: boolean; off_note?: string | null; off_at?: number | null }
export interface RuleStage { stage: string; label: string; total: number; off: number; rules: RuleRow[] }
export interface RulesView { total: number; off: number; stages: RuleStage[] }

export async function fetchRules(): Promise<RulesView | null> {
  try {
    const res = await fetch(`${API_BASE}/rules`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

/** Switch one rule (stage + rule), every rule of a stage (stage only) or every rule (neither) ON or OFF. Returns the new view. */
export async function switchRules(body: { on: boolean; stage?: string; rule?: string; note?: string }): Promise<RulesView | null> {
  try {
    const res = await fetch(`${API_BASE}/rules/switch`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}
