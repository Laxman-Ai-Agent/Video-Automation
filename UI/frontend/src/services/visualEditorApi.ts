import {
  VisualFeedbackItem,
  ComponentCatalogItem,
  VisualEditorSession,
  ImplementationPlan,
  TestResult
} from '../types/visualEditor';

const API_BASE = ''; // proxied to http://127.0.0.1:8000

export async function fetchComponentCatalog(): Promise<ComponentCatalogItem[]> {
  try {
    const res = await fetch(`${API_BASE}/visual-editor/component-catalog`);
    if (!res.ok) return [];
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch component catalog:', err);
    return [];
  }
}

export async function fetchVisualFeedback(projectId?: string): Promise<VisualFeedbackItem[]> {
  try {
    const url = projectId 
      ? `${API_BASE}/visual-editor/feedback?project_id=${encodeURIComponent(projectId)}`
      : `${API_BASE}/visual-editor/feedback`;
    const res = await fetch(url);
    if (!res.ok) return [];
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch visual feedback:', err);
    return [];
  }
}

export async function createVisualFeedback(payload: {
  projectId: string;
  page: string;
  route: string;
  elementSelector: string;
  elementName: string;
  componentRef?: string;
  sourceFile?: string;
  isSourceMapped: boolean;
  category: string;
  feedback: string;
  tags?: string[];
  visualRef?: string;
}): Promise<VisualFeedbackItem> {
  const res = await fetch(`${API_BASE}/visual-editor/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || 'Failed to create feedback sticky note');
  }
  return await res.json();
}

export async function updateVisualFeedback(
  feedbackId: string, 
  payload: { feedback?: string; status?: string; category?: string; tags?: string[] }
): Promise<VisualFeedbackItem> {
  const res = await fetch(`${API_BASE}/visual-editor/feedback/${feedbackId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    throw new Error('Failed to update feedback');
  }
  return await res.json();
}

export async function deleteVisualFeedback(feedbackId: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/visual-editor/feedback/${feedbackId}`, {
    method: 'DELETE'
  });
  return res.ok;
}

export async function fetchVisualEditorSession(projectId: string): Promise<VisualEditorSession> {
  const res = await fetch(`${API_BASE}/visual-editor/sessions/${encodeURIComponent(projectId)}`);
  if (!res.ok) {
    throw new Error('Failed to load visual editor session');
  }
  return await res.json();
}

export async function sendAgentChatMessage(
  projectId: string,
  message: string,
  selectedFeedbackIds: string[] = []
): Promise<any> {
  const res = await fetch(`${API_BASE}/visual-editor/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      projectId,
      message,
      selectedFeedbackIds
    })
  });
  return await res.json();
}

export async function generateImplementationPlan(
  projectId: string,
  feedbackIds: string[]
): Promise<ImplementationPlan> {
  const res = await fetch(`${API_BASE}/visual-editor/generate-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      projectId,
      feedbackIds
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || 'Failed to generate plan');
  }
  return await res.json();
}

export async function decideImplementationPlan(
  projectId: string,
  planId: string,
  decision: 'approved' | 'rejected',
  notes?: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/visual-editor/decide-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      projectId,
      planId,
      decision,
      notes
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || 'Plan approval decision failed');
  }
  return await res.json();
}

export async function authorizeImplementation(
  projectId: string,
  planId: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/visual-editor/authorize-implementation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      projectId,
      planId
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || 'Implementation authorization failed');
  }
  return await res.json();
}

export async function executeImplementationTests(projectId: string): Promise<{
  ok: boolean;
  implementationStatus: string;
  testResults: TestResult;
  currentStep: number;
}> {
  const res = await fetch(`${API_BASE}/visual-editor/run-implementation-tests?project_id=${encodeURIComponent(projectId)}`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || 'Implementation testing failed');
  }
  return await res.json();
}

export async function decideFinalUi(
  projectId: string,
  decision: 'approved' | 'changes_requested',
  reason?: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/visual-editor/decide-final-ui`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      projectId,
      decision,
      reason
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || 'Final UI decision failed');
  }
  return await res.json();
}
