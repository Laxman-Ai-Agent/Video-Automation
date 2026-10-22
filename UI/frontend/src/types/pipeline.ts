export type StageStatus =
  | 'idle'
  | 'waiting'
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'blocked'
  | 'retrying'
  | 'recovering'
  | 'cancelled';

export interface StageConfig {
  id: string;
  order: number;
  label: string;
  category: 'audio' | 'visual' | 'motion' | 'assembly' | 'delivery';
  description: string;
  agentId: string;
  agentName: string;
  weight: number;
}

export const CANONICAL_11_STAGES: StageConfig[] = [
  { id: 'analyzer', order: 1, label: 'Audio Analysis', category: 'audio', description: 'Transcription, speech cadence & sound analysis', agentId: 'audio_analyzer', agentName: 'Audio Analyzer Agent', weight: 0.15 },
  { id: 'segmentation', order: 2, label: 'Scene Segmentation', category: 'visual', description: 'Semantic narrative cut & slot mapping', agentId: 'scene_segmentation', agentName: 'Scene Segmentation Agent', weight: 0.10 },
  { id: 'planning', order: 3, label: 'Visual Planning', category: 'visual', description: 'Visual concept framing & prompt generation', agentId: 'visual_planning', agentName: 'Visual Planning Agent', weight: 0.10 },
  { id: 'assets', order: 4, label: 'Asset Collection', category: 'visual', description: 'Optional licensed real photos & clips with provenance', agentId: 'asset_collection', agentName: 'Asset Collection Agent', weight: 0.04 },
  { id: 'motion_plan', order: 5, label: 'Motion Planning', category: 'motion', description: 'Camera paths, motion templates & transitions', agentId: 'motion_planning', agentName: 'Motion Planning Agent', weight: 0.10 },
  { id: 'motion_gen', order: 6, label: 'Motion Generation', category: 'motion', description: 'Dynamic React/Remotion component synthesis', agentId: 'motion_animation', agentName: 'Motion Animation Agent', weight: 0.13 },
  { id: 'motion_validation', order: 7, label: 'Motion Validation', category: 'motion', description: 'AST security, TypeScript & layout validation', agentId: 'motion_validation', agentName: 'Motion Validation Agent', weight: 0.05 },
  { id: 'timeline', order: 8, label: 'Timeline Build', category: 'assembly', description: 'Multi-track composition & asset binding', agentId: 'timeline_build', agentName: 'Timeline Build Agent', weight: 0.10 },
  { id: 'approval', order: 9, label: 'Timeline Approval', category: 'assembly', description: 'Automated rubric gates & operator signoff', agentId: 'timeline_approval', agentName: 'Timeline Approval Agent', weight: 0.05 },
  { id: 'render', order: 10, label: 'Render Video', category: 'assembly', description: 'Headless Chrome & FFmpeg frame compilation', agentId: 'render_video', agentName: 'Render Video Agent', weight: 0.08 },
  { id: 'qc', order: 11, label: 'Final QC', category: 'delivery', description: 'Strict A/V sync, bitrate, loudness & probe verification', agentId: 'final_qc', agentName: 'Final QC Agent', weight: 0.05 },
  { id: 'final', order: 12, label: 'Final Delivery', category: 'delivery', description: 'Desktop delivery folder publication & manifest hashing', agentId: 'final_video_delivery', agentName: 'Final Delivery Agent', weight: 0.05 }
];

export const CANONICAL_12_STAGES = CANONICAL_11_STAGES;

export interface StageState {
  id: string;
  status: StageStatus;
  percentage: number | null; // null if not reported
  currentActivity?: string;
  teluguMessage?: string;
  startedAt?: string;
  completedAt?: string;
  lastActivityAt?: string; // timestamp of latest activity or progress event
  durationMs?: number;
  llmVerified?: boolean; // the stage's stored LLM review passed
  waitingFor?: string; // the prerequisite stage this one waits for (not completed yet); the stage cannot run until it completes
  stuck?: boolean; // started, then no progress beyond the stage's expected time (from the backend issue list)
  issueErrors?: number; // real errors (stage or its subtasks) from the backend issue list
  issueWarnings?: number; // real warnings (stage, its subtasks, LLM step rejections)
  attempt?: number;
  maxAttempts?: number;
  retryReason?: string;
  failingSubStage?: string;
  artifacts?: { name: string; path: string; size?: number }[];
  errors?: string[];
  blockers?: string[];
}

// A real problem reported by the backend (UI/backend/pipeline_issues.py): read from the agent log, the job and the stage statuses
export interface PipelineIssue {
  id: string;
  severity: 'error' | 'warning' | 'stuck';
  stageId: string | null;
  stageLabel: string;
  source: string;
  component: string;
  message: string;
  code?: string | null;
  attempts?: number | null;
  retryLimit?: number | null;
  at?: number | null; // epoch seconds, when the log recorded it
  subtask?: string | null; // the step of the stage it belongs to (null = the stage itself)
  stageStatus?: string | null; // the stage's current status when the issue was read
}

export interface PipelineProjectState {
  projectId: string;
  title: string;
  aspectRatio: '16:9' | '9:16';
  autoPilot: boolean;
  overallProgress: number;
  currentStageId: string;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'paused';
  stages: Record<string, StageState>;
  updatedAt: string;
}

export interface AgentInfo {
  agentId: string;
  name: string;
  category: string;
  status: 'idle' | 'running' | 'ready' | 'error';
  currentTask?: string;
  capabilities: string[];
}
