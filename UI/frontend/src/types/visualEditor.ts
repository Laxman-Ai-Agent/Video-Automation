export type FeedbackStatus = 'pending' | 'in_review' | 'approved_for_plan' | 'implemented' | 'resolved';

export type FeedbackCategory = 'layout' | 'spacing' | 'alignment' | 'style' | 'logic' | 'bug' | 'general';

export interface VisualFeedbackItem {
  id: string;
  projectId: string;
  page: string;
  route: string;
  elementSelector: string;
  elementName: string;
  componentRef?: string;
  sourceFile?: string;
  isSourceMapped: boolean;
  category: FeedbackCategory;
  feedback: string;
  status: FeedbackStatus;
  createdAt: string;
  updatedAt?: string;
  tags?: string[];
  visualRef?: string;
}

export interface ComponentCatalogItem {
  id: string;
  name: string;
  component: string;
  source_file: string;
  page: string;
  route: string;
  selector: string;
  description: string;
}

export interface AffectedComponent {
  name: string;
  sourceFile: string;
  description: string;
}

export interface ImplementationPlan {
  id: string;
  projectId: string;
  feedbackIds: string[];
  generatedAt: string;
  generatedByAgent: string;
  llmProvider: string;
  llmModel: string;
  understanding: string;
  proposedModifications: string[];
  affectedComponents: AffectedComponent[];
  risksAndDependencies: string[];
  validationAndTestingSteps: string[];
  planApproved: boolean;
  planApprovedAt?: string | null;
  planApprovedBy?: string | null;
  rejectionNotes?: string | null;
  implementationAuthorized: boolean;
  implementationAuthorizedAt?: string | null;
}

export interface TestResult {
  passed: boolean;
  suiteName: string;
  durationMs: number;
  returnCode: number;
  output: string;
  timestamp: string;
}

export interface VisualChatMessage {
  id: string;
  sender: 'user' | 'agent';
  agentId?: string;
  agentName?: string;
  content: string;
  timestamp: string;
  provider?: string;
  model?: string;
  status?: 'delivered' | 'sending' | 'error';
  errorDetails?: string;
  attachedFeedbackIds?: string[];
}

export interface VisualEditorSession {
  projectId: string;
  currentStep: number; // 1 to 6
  selectedFeedbackIds: string[];
  plan?: ImplementationPlan | null;
  planApproved: boolean;
  implementationAuthorized: boolean;
  implementationStatus: 'idle' | 'ready_to_execute' | 'running' | 'completed' | 'failed';
  testResults?: TestResult | null;
  finalUiStatus: 'pending_review' | 'approved' | 'changes_requested';
  finalUiDecidedAt?: string | null;
  changeRequestReason?: string | null;
  chatMessages: VisualChatMessage[];
  updatedAt?: string;
}
