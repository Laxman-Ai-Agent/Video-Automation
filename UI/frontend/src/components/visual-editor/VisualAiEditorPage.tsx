import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Plus, 
  Search, 
  Filter, 
  Trash2, 
  CheckCircle2, 
  Clock, 
  AlertTriangle, 
  Send, 
  Sparkles, 
  ShieldCheck, 
  Cpu, 
  FileCode, 
  ArrowRight, 
  Play, 
  RotateCcw, 
  Check, 
  X, 
  ExternalLink,
  ChevronRight,
  Layers,
  HelpCircle,
  Terminal,
  Activity,
  ThumbsUp,
  AlertCircle,
  Eye,
  MessageSquare,
  Sliders,
  CheckCircle,
  FileText,
  Copy,
  ArrowDown,
  Bot,
  User
} from 'lucide-react';
import { 
  VisualFeedbackItem, 
  ComponentCatalogItem, 
  VisualEditorSession, 
  ImplementationPlan, 
  VisualChatMessage,
  FeedbackStatus
} from '../../types/visualEditor';
import { 
  fetchComponentCatalog, 
  fetchVisualFeedback, 
  createVisualFeedback, 
  deleteVisualFeedback, 
  updateVisualFeedback,
  fetchVisualEditorSession, 
  sendAgentChatMessage, 
  generateImplementationPlan, 
  decideImplementationPlan, 
  authorizeImplementation, 
  executeImplementationTests, 
  decideFinalUi 
} from '../../services/visualEditorApi';
import { AddFeedbackModal } from './AddFeedbackModal';

type EditorTab = 'feedback' | 'chat' | 'plan' | 'implementation' | 'preview';

interface VisualAiEditorPageProps {
  activeProjectId?: string;
}

const CodeBlock: React.FC<{ language: string; code: string }> = ({ language, code }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{
      margin: '10px 0',
      borderRadius: '8px',
      overflow: 'hidden',
      border: '1px solid var(--border-subtle)',
      backgroundColor: '#070B12',
      maxWidth: '100%'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 12px',
        backgroundColor: 'rgba(255, 255, 255, 0.03)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
        fontSize: '11px',
        color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)'
      }}>
        <span style={{ textTransform: 'lowercase' }}>{language || 'code'}</span>
        <button
          onClick={handleCopy}
          type="button"
          style={{
            background: 'none',
            border: 'none',
            color: copied ? 'var(--status-completed)' : 'var(--text-secondary)',
            fontSize: '11px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '2px 6px',
            borderRadius: '4px'
          }}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          <span>{copied ? 'Copied' : 'Copy code'}</span>
        </button>
      </div>
      <pre style={{
        margin: 0,
        padding: '12px 14px',
        overflowX: 'auto',
        fontSize: '12px',
        fontFamily: 'var(--font-mono)',
        lineHeight: 1.5,
        color: '#E2E8F0',
        whiteSpace: 'pre'
      }}>
        <code>{code}</code>
      </pre>
    </div>
  );
};

const renderMessageContent = (content: string) => {
  if (!content) return null;

  // Split content by triple-backtick code fences
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    const textBefore = content.substring(lastIndex, match.index);
    if (textBefore) {
      parts.push(
        <div key={`text-${lastIndex}`} style={{ whiteSpace: 'pre-wrap' }}>
          {textBefore}
        </div>
      );
    }

    const language = match[1] || 'code';
    const code = match[2];
    parts.push(
      <CodeBlock key={`code-${match.index}`} language={language} code={code} />
    );

    lastIndex = match.index + match[0].length;
  }

  const remainingText = content.substring(lastIndex);
  if (remainingText) {
    parts.push(
      <div key={`text-${lastIndex}`} style={{ whiteSpace: 'pre-wrap' }}>
        {remainingText}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {parts}
    </div>
  );
};

export const VisualAiEditorPage: React.FC<VisualAiEditorPageProps> = ({
  activeProjectId = 'sample-01'
}) => {
  // 1. Navigation & Tab State
  const [activeTab, setActiveTab] = useState<EditorTab>('feedback');

  // 2. Data States
  const [feedbackList, setFeedbackList] = useState<VisualFeedbackItem[]>([]);
  const [catalog, setCatalog] = useState<ComponentCatalogItem[]>([]);
  const [session, setSession] = useState<VisualEditorSession | null>(null);
  const [selectedFeedbackIds, setSelectedFeedbackIds] = useState<string[]>([]);
  const [primarySelectedId, setPrimarySelectedId] = useState<string | null>(null);

  // 3. UI Filtering & Modal State
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [pageFilter, setPageFilter] = useState<string>('all');
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);

  // 4. Chat & Execution States
  const [chatInput, setChatInput] = useState<string>('');
  const [isSendingChat, setIsSendingChat] = useState<boolean>(false);
  const [isGeneratingPlan, setIsGeneratingPlan] = useState<boolean>(false);
  const [isRunningTests, setIsRunningTests] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const isUserNearBottomRef = useRef<boolean>(true);
  const [showScrollBottomBtn, setShowScrollBottomBtn] = useState<boolean>(false);

  // Auto-scroll handler
  const scrollToBottom = useCallback((behavior: 'auto' | 'smooth' = 'smooth') => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior
      });
      isUserNearBottomRef.current = true;
      setShowScrollBottomBtn(false);
    } else {
      chatEndRef.current?.scrollIntoView({ behavior });
    }
  }, []);

  const handleMessagesScroll = () => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const { scrollTop, scrollHeight, clientHeight } = container;
    const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);
    const isNear = distanceFromBottom < 80;
    isUserNearBottomRef.current = isNear;
    setShowScrollBottomBtn(!isNear && scrollHeight > clientHeight + 100);
  };

  // Load Initial Data
  const loadData = async () => {
    try {
      const [fbs, cats, sess] = await Promise.all([
        fetchVisualFeedback(activeProjectId),
        fetchComponentCatalog(),
        fetchVisualEditorSession(activeProjectId)
      ]);
      setFeedbackList(fbs);
      setCatalog(cats);
      setSession(sess);

      // Pre-select first item if available
      if (fbs.length > 0 && !primarySelectedId) {
        setPrimarySelectedId(fbs[0].id);
        setSelectedFeedbackIds([fbs[0].id]);
      }
    } catch (err: any) {
      setActionError(`Failed to load editor data: ${err.message}`);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeProjectId]);

  // Scroll chat to bottom when opening chat tab
  useEffect(() => {
    if (activeTab === 'chat') {
      const timer = setTimeout(() => {
        scrollToBottom('auto');
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [activeTab, scrollToBottom]);

  // Scroll chat to bottom when new messages arrive (only if already near bottom)
  useEffect(() => {
    if (activeTab === 'chat' && isUserNearBottomRef.current) {
      scrollToBottom('smooth');
    }
  }, [session?.chatMessages, isSendingChat, activeTab, scrollToBottom]);

  // Add Feedback Sticky Note
  const handleAddFeedback = async (data: {
    page: string;
    route: string;
    elementSelector: string;
    elementName: string;
    componentRef?: string;
    sourceFile?: string;
    isSourceMapped: boolean;
    category: any;
    feedback: string;
    tags: string[];
  }) => {
    try {
      const newItem = await createVisualFeedback({
        projectId: activeProjectId,
        ...data
      });
      setFeedbackList((prev) => [newItem, ...prev]);
      setPrimarySelectedId(newItem.id);
      setSelectedFeedbackIds([newItem.id]);
      setIsAddModalOpen(false);
      setActionNotice('Visual sticky note saved and persisted!');
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      setActionError(err.message);
    }
  };

  // Delete Feedback Sticky Note
  const handleDeleteFeedback = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteVisualFeedback(id);
      setFeedbackList((prev) => prev.filter((item) => item.id !== id));
      setSelectedFeedbackIds((prev) => prev.filter((item) => item !== id));
      if (primarySelectedId === id) {
        setPrimarySelectedId(null);
      }
      setActionNotice('Sticky note deleted.');
      setTimeout(() => setActionNotice(null), 2500);
    } catch (err: any) {
      setActionError(err.message);
    }
  };

  // Toggle selection for multi-item plan grouping
  const handleToggleSelect = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedFeedbackIds((prev) => 
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleChatKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isSendingChat && chatInput.trim()) {
        handleSendMessage();
      }
    }
  };

  // Send message to actual configured LLM agent
  const handleSendMessage = async (customPrompt?: string) => {
    const textToSend = customPrompt || chatInput;
    if (!textToSend.trim() || isSendingChat) return;

    // Force scroll to bottom on user send
    isUserNearBottomRef.current = true;
    setTimeout(() => scrollToBottom('smooth'), 20);

    const optimisticMsg: VisualChatMessage = {
      id: `msg-opt-${Date.now()}`,
      sender: 'user',
      content: textToSend.trim(),
      timestamp: new Date().toISOString()
    };

    try {
      setIsSendingChat(true);
      setActionError(null);
      setChatInput('');

      // Optimistically show user prompt in stream immediately
      setSession((prev) => prev ? {
        ...prev,
        chatMessages: [...(prev.chatMessages || []), optimisticMsg]
      } : prev);

      const res = await sendAgentChatMessage(
        activeProjectId,
        textToSend.trim(),
        selectedFeedbackIds
      );

      // Reload session to reflect updated conversation
      const updatedSess = await fetchVisualEditorSession(activeProjectId);
      setSession(updatedSess);

      if (!res.success) {
        setActionError(`Agent Warning: ${res.error || 'LLM communication problem'}`);
      }
    } catch (err: any) {
      setActionError(`Chat failed: ${err.message}`);
    } finally {
      setIsSendingChat(false);
    }
  };

  // Step 3: Trigger implementation plan generation
  const handleGeneratePlan = async () => {
    const targetIds = selectedFeedbackIds.length > 0 
      ? selectedFeedbackIds 
      : (primarySelectedId ? [primarySelectedId] : []);

    if (targetIds.length === 0) {
      setActionError('Please select at least one feedback sticky note to generate an implementation plan.');
      return;
    }

    try {
      setIsGeneratingPlan(true);
      setActionError(null);
      await generateImplementationPlan(activeProjectId, targetIds);
      const updatedSess = await fetchVisualEditorSession(activeProjectId);
      setSession(updatedSess);
      setActionNotice('Implementation Plan generated by Main Architecture Agent!');
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err: any) {
      setActionError(`Plan generation failed: ${err.message}`);
    } finally {
      setIsGeneratingPlan(false);
    }
  };

  // Gate 1: Approve Plan
  const handleApprovePlan = async () => {
    const planId = plan?.id || 'active-plan';
    try {
      setActionError(null);
      await decideImplementationPlan(activeProjectId, planId, 'approved');
      const updatedSess = await fetchVisualEditorSession(activeProjectId);
      setSession(updatedSess);
      setActionNotice('Plan Approved (Gate 1 Passed)! Implementation may now be authorized.');
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err: any) {
      setActionError(`Plan approval failed: ${err.message}`);
    }
  };

  // Gate 2: Authorize Implementation
  const handleAuthorizeImplementation = async () => {
    const planId = plan?.id || 'active-plan';
    try {
      setActionError(null);
      await authorizeImplementation(activeProjectId, planId);
      const updatedSess = await fetchVisualEditorSession(activeProjectId);
      setSession(updatedSess);
      setActionNotice('Implementation Authorized (Gate 2 Passed)! Acceptance tests unlocked.');
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err: any) {
      setActionError(`Implementation authorization failed: ${err.message}`);
    }
  };

  // Step 5: Execute Implementation & Acceptance Tests
  const handleRunTests = async () => {
    try {
      setIsRunningTests(true);
      setActionError(null);
      const res = await executeImplementationTests(activeProjectId);
      const updatedSess = await fetchVisualEditorSession(activeProjectId);
      setSession(updatedSess);
      if (res.testResults?.passed) {
        setActionNotice('Acceptance Tests PASSED! Final UI review unlocked.');
      } else {
        setActionError('Acceptance Tests failed. Check build and TypeScript output.');
      }
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err: any) {
      setActionError(`Test execution error: ${err.message}`);
    } finally {
      setIsRunningTests(false);
    }
  };

  // Gate 3: Final UI Decision (Approve vs Request Changes)
  const handleFinalUiDecision = async (decision: 'approved' | 'changes_requested') => {
    try {
      setActionError(null);
      await decideFinalUi(activeProjectId, decision);
      const [updatedFbs, updatedSess] = await Promise.all([
        fetchVisualFeedback(activeProjectId),
        fetchVisualEditorSession(activeProjectId)
      ]);
      setFeedbackList(updatedFbs);
      setSession(updatedSess);

      if (decision === 'approved') {
        setActionNotice('Final UI Approved! All feedback sticky notes marked as RESOLVED.');
      } else {
        setActionNotice('Changes requested: returned to Discussion step while preserving all plan history.');
      }
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err: any) {
      setActionError(`Final UI decision failed: ${err.message}`);
    }
  };

  // Filter feedback
  const filteredFeedback = feedbackList.filter((fb) => {
    if (statusFilter !== 'all' && fb.status !== statusFilter) return false;
    if (pageFilter !== 'all' && fb.page !== pageFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchText = fb.feedback.toLowerCase().includes(q);
      const matchEl = fb.elementName.toLowerCase().includes(q);
      const matchPage = fb.page.toLowerCase().includes(q);
      const matchComp = (fb.componentRef || '').toLowerCase().includes(q);
      if (!matchText && !matchEl && !matchPage && !matchComp) return false;
    }
    return true;
  });

  const primaryFeedback = feedbackList.find((f) => f.id === primarySelectedId);
  const plan = session?.plan;

  const getStatusBadge = (status: FeedbackStatus) => {
    switch (status) {
      case 'pending':
        return <span style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 600, backgroundColor: 'rgba(140, 140, 140, 0.15)', color: 'var(--text-muted)', border: '1px solid rgba(140, 140, 140, 0.3)' }}>PENDING</span>;
      case 'in_review':
        return <span style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 600, backgroundColor: 'rgba(24, 144, 255, 0.15)', color: 'var(--accent-blue)', border: '1px solid rgba(24, 144, 255, 0.3)' }}>IN REVIEW</span>;
      case 'approved_for_plan':
        return <span style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 600, backgroundColor: 'rgba(250, 140, 22, 0.15)', color: '#FA8C16', border: '1px solid rgba(250, 140, 22, 0.3)' }}>PLAN APPROVED</span>;
      case 'implemented':
        return <span style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 600, backgroundColor: 'rgba(0, 216, 245, 0.15)', color: 'var(--accent-cyan)', border: '1px solid rgba(0, 216, 245, 0.25)' }}>IMPLEMENTED</span>;
      case 'resolved':
        return <span style={{ padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 600, backgroundColor: 'rgba(82, 196, 26, 0.15)', color: 'var(--status-completed)', border: '1px solid rgba(82, 196, 26, 0.3)' }}>RESOLVED</span>;
    }
  };

  return (
    <div style={{
      width: '100%',
      maxWidth: '100%',
      margin: '0 auto',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      fontFamily: 'var(--font-sans)',
      height: 'calc(100vh - 112px)',
      boxSizing: 'border-box'
    }}>

      {/* Toast feedback alerts */}
      {actionNotice && (
        <div style={{
          padding: '8px 14px',
          backgroundColor: 'var(--status-completed-bg)',
          border: '1px solid var(--status-completed-border)',
          borderRadius: '4px',
          color: 'var(--status-completed)',
          fontSize: '12.5px',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          flexShrink: 0
        }}>
          <CheckCircle2 size={15} />
          <span>{actionNotice}</span>
        </div>
      )}

      {actionError && (
        <div style={{
          padding: '8px 14px',
          backgroundColor: 'var(--status-failed-bg)',
          border: '1px solid var(--status-failed-border)',
          borderRadius: '4px',
          color: 'var(--status-failed)',
          fontSize: '12.5px',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          flexShrink: 0
        }}>
          <AlertCircle size={15} />
          <span>{actionError}</span>
        </div>
      )}

      {/* 2. MAIN WORKSPACE CARD CONTAINER WITH RIGHT-SIDE MENU BAR */}
      <div style={{
        backgroundColor: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-card)',
        boxShadow: 'var(--shadow-card)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'row',
        flex: 1,
        height: '100%',
        minHeight: 0,
        boxSizing: 'border-box'
      }}>
        {/* LEFT COLUMN: ACTIVE WORKSPACE CONTENT */}
        <div style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflowY: activeTab === 'chat' ? 'hidden' : 'auto',
          boxSizing: 'border-box'
        }}>

        {/* ============================================================== */}
        {/* TAB 1 CONTENT: FEEDBACK STICKY NOTES STREAM */}
        {/* ============================================================== */}
        {activeTab === 'feedback' && (
          <div 
            data-testid="feedback-panel"
            style={{
              padding: '20px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              flex: 1
            }}
          >
            {/* Search, Filter Pills & Add Button Bar */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: '280px' }}>
                <div style={{
                  position: 'relative',
                  flex: 1,
                  maxWidth: '340px'
                }}>
                  <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }} />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search notes, elements, files..."
                    data-testid="feedback-search-input"
                    style={{
                      width: '100%',
                      padding: '7px 10px 7px 32px',
                      fontSize: '12.5px',
                      backgroundColor: 'var(--bg-app)',
                      border: '1px solid var(--border-card)',
                      borderRadius: '4px',
                      color: 'var(--text-primary)',
                      outline: 'none'
                    }}
                  />
                </div>

                {/* Status Filter Pills */}
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {['all', 'pending', 'in_review', 'approved_for_plan', 'resolved'].map((st) => (
                    <button
                      key={st}
                      onClick={() => setStatusFilter(st)}
                      style={{
                        padding: '4px 9px',
                        fontSize: '11px',
                        borderRadius: '4px',
                        border: '1px solid',
                        borderColor: statusFilter === st ? 'var(--accent-blue)' : 'var(--border-subtle)',
                        backgroundColor: statusFilter === st ? 'rgba(24, 144, 255, 0.15)' : 'transparent',
                        color: statusFilter === st ? 'var(--accent-blue)' : 'var(--text-secondary)',
                        cursor: 'pointer',
                        fontWeight: statusFilter === st ? 600 : 400,
                        textTransform: 'uppercase'
                      }}
                    >
                      {st.replace(/_/g, ' ')}
                    </button>
                  ))}
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={() => setIsAddModalOpen(true)}
                data-testid="open-add-feedback-btn"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '7px 14px',
                  backgroundColor: 'var(--accent-blue)',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                <Plus size={14} />
                <span>+ Add Note</span>
              </button>
            </div>

            {/* Sticky Notes Grid / Stream */}
            <div 
              data-testid="feedback-notes-list"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
                gap: '12px',
                flex: 1
              }}
            >
              {filteredFeedback.length === 0 ? (
                <div style={{
                  gridColumn: '1 / -1',
                  textAlign: 'center',
                  padding: '48px 16px',
                  color: 'var(--text-muted)',
                  fontSize: '12.5px',
                  backgroundColor: 'var(--bg-app)',
                  borderRadius: '6px',
                  border: '1px dashed var(--border-card)'
                }}>
                  <p style={{ margin: '0 0 10px 0' }}>No sticky notes found matching criteria.</p>
                  <button
                    onClick={() => setIsAddModalOpen(true)}
                    style={{
                      padding: '6px 14px',
                      fontSize: '12px',
                      backgroundColor: 'transparent',
                      border: '1px solid var(--accent-blue)',
                      color: 'var(--accent-blue)',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontWeight: 600
                    }}
                  >
                    + Add First Sticky Note
                  </button>
                </div>
              ) : (
                filteredFeedback.map((item) => {
                  const isSelected = item.id === primarySelectedId;
                  const isChecked = selectedFeedbackIds.includes(item.id);

                  return (
                    <div
                      key={item.id}
                      onClick={() => {
                        setPrimarySelectedId(item.id);
                        if (!selectedFeedbackIds.includes(item.id)) {
                          setSelectedFeedbackIds([item.id]);
                        }
                      }}
                      data-testid={`feedback-card-${item.id}`}
                      style={{
                        padding: '12px 14px',
                        borderRadius: '6px',
                        border: isSelected 
                          ? '1px solid var(--accent-blue)' 
                          : '1px solid var(--border-subtle)',
                        backgroundColor: isSelected ? 'rgba(24, 144, 255, 0.05)' : 'var(--bg-app)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '8px',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {/* Note Top Bar: Checkbox, Page, Status Badge, Delete */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => handleToggleSelect(item.id, e as any)}
                            onClick={(e) => e.stopPropagation()}
                            style={{ cursor: 'pointer' }}
                          />
                          <span style={{
                            fontSize: '11px',
                            fontWeight: 600,
                            color: 'var(--accent-blue)',
                            backgroundColor: 'rgba(24, 144, 255, 0.1)',
                            padding: '2px 6px',
                            borderRadius: '3px'
                          }}>
                            {item.page}
                          </span>
                          <span style={{
                            fontSize: '10px',
                            color: 'var(--text-muted)',
                            textTransform: 'uppercase'
                          }}>
                            {item.category}
                          </span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          {getStatusBadge(item.status)}
                          <button
                            onClick={(e) => handleDeleteFeedback(item.id, e)}
                            data-testid={`delete-feedback-${item.id}`}
                            title="Delete sticky note"
                            style={{
                              background: 'none',
                              border: 'none',
                              color: 'var(--text-muted)',
                              cursor: 'pointer',
                              padding: '2px'
                            }}
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>

                      {/* Element Name & Source Reference */}
                      <div>
                        <div style={{
                          fontSize: '13px',
                          fontWeight: 700,
                          color: 'var(--text-primary)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px'
                        }}>
                          <span>{item.elementName}</span>
                        </div>
                        <div style={{
                          fontSize: '11px',
                          fontFamily: 'var(--font-mono)',
                          color: 'var(--text-muted)',
                          marginTop: '2px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          flexWrap: 'wrap'
                        }}>
                          <span>{item.sourceFile || item.elementSelector}</span>
                          {!item.isSourceMapped && (
                            <span style={{
                              color: '#FA8C16',
                              backgroundColor: 'rgba(250, 140, 22, 0.1)',
                              padding: '1px 5px',
                              borderRadius: '3px',
                              fontSize: '9.5px',
                              fontWeight: 600
                            }}>
                              Approximated (Unmapped fallback)
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Feedback Text Body */}
                      <p style={{
                        fontSize: '12.5px',
                        color: 'var(--text-secondary)',
                        margin: 0,
                        lineHeight: 1.5
                      }}>
                        "{item.feedback}"
                      </p>

                      {/* Bottom Footer: Timestamp & Action */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginTop: '2px',
                        paddingTop: '6px',
                        borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                        fontSize: '11px',
                        color: 'var(--text-muted)'
                      }}>
                        <span>{item.createdAt.slice(11, 16)} GMT</span>
                        <span style={{ color: isSelected ? 'var(--accent-blue)' : 'transparent', fontWeight: 600 }}>
                          Selected
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Bottom Floating Action Bar for Selected Notes */}
            {selectedFeedbackIds.length > 0 && (
              <div style={{
                padding: '12px 18px',
                borderRadius: '6px',
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--accent-blue)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle size={16} color="var(--accent-blue)" />
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {selectedFeedbackIds.length} feedback note(s) selected
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <button
                    onClick={() => setActiveTab('chat')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 14px',
                      backgroundColor: 'transparent',
                      color: 'var(--accent-blue)',
                      border: '1px solid var(--accent-blue)',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    <MessageSquare size={13} />
                    <span>Discuss with AI →</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('plan')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 14px',
                      backgroundColor: 'var(--accent-blue)',
                      color: '#FFFFFF',
                      border: 'none',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    <FileCode size={13} />
                    <span>Generate Implementation Plan →</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 2 CONTENT: AI CHAT (CHATGPT-STYLE CONVERSATION INTERFACE) */}
        {/* ============================================================== */}
        {activeTab === 'chat' && (
          <div 
            data-testid="agent-chat-panel"
            style={{
              display: 'flex',
              flexDirection: 'column',
              flex: 1,
              minHeight: 0,
              overflow: 'hidden',
              boxSizing: 'border-box'
            }}
          >
            {/* 1. AGENT HEADER (STATIONARY TOP SECTION) */}
            <div style={{
              flexShrink: 0,
              padding: '12px 20px 10px 20px',
              borderBottom: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-card)',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px'
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(24, 144, 255, 0.15)',
                    border: '1px solid rgba(24, 144, 255, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--accent-blue)'
                  }}>
                    <Cpu size={17} />
                  </div>
                  <div>
                    <div style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span>Main Architecture Agent</span>
                      <span style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        backgroundColor: 'rgba(24, 144, 255, 0.1)',
                        color: 'var(--accent-blue)',
                        padding: '1px 6px',
                        borderRadius: '4px',
                        border: '1px solid rgba(24, 144, 255, 0.2)'
                      }}>
                        Coding & UI Swarm
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Authoritative Engineering Swarm • Connected to Real Configured LLM
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    fontSize: '11px',
                    fontWeight: 600,
                    color: 'var(--status-completed)',
                    backgroundColor: 'rgba(82, 196, 26, 0.1)',
                    padding: '3px 8px',
                    borderRadius: '12px',
                    border: '1px solid rgba(82, 196, 26, 0.25)'
                  }}>
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--status-completed)' }}></span>
                    Active
                  </span>

                  <button
                    onClick={() => setActiveTab('plan')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '4px 10px',
                      fontSize: '11px',
                      fontWeight: 600,
                      backgroundColor: 'transparent',
                      border: '1px solid var(--border-subtle)',
                      color: 'var(--text-secondary)',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    <span>Review Plan →</span>
                  </button>
                </div>
              </div>

              {/* Attached Context Banner */}
              {primaryFeedback && (
                <div style={{
                  padding: '7px 12px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(24, 144, 255, 0.06)',
                  border: '1px solid rgba(24, 144, 255, 0.2)',
                  fontSize: '11.5px',
                  color: 'var(--text-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '8px',
                  flexWrap: 'wrap'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Layers size={13} color="var(--accent-blue)" />
                    <span>
                      Attached Context: <strong>[{primaryFeedback.page}]</strong> {primaryFeedback.elementName} — "{primaryFeedback.feedback}"
                    </span>
                  </div>
                  <span style={{ fontSize: '10.5px', color: 'var(--accent-blue)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                    Target: {primaryFeedback.sourceFile || primaryFeedback.elementSelector}
                  </span>
                </div>
              )}
            </div>

            {/* 2. CONVERSATION MESSAGES AREA (INDEPENDENTLY SCROLLABLE MIDDLE SECTION) */}
            <div 
              ref={messagesContainerRef}
              onScroll={handleMessagesScroll}
              data-testid="chat-messages-stream"
              style={{
                flex: 1,
                minHeight: 0,
                overflowY: 'auto',
                overflowX: 'hidden',
                padding: '20px 24px',
                backgroundColor: 'var(--bg-app)',
                display: 'flex',
                flexDirection: 'column',
                gap: '18px',
                position: 'relative'
              }}
            >
              {/* Empty state when conversation has no messages */}
              {(session?.chatMessages || []).length === 0 && !isSendingChat && (
                <div style={{
                  margin: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  textAlign: 'center',
                  padding: '30px 20px',
                  maxWidth: '540px',
                  gap: '12px'
                }}>
                  <div style={{
                    width: '44px',
                    height: '44px',
                    borderRadius: '12px',
                    backgroundColor: 'rgba(24, 144, 255, 0.1)',
                    border: '1px solid rgba(24, 144, 255, 0.25)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--accent-blue)'
                  }}>
                    <Sparkles size={22} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 6px 0' }}>
                      How can I help with the UI?
                    </h3>
                    <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
                      Discuss visual sticky notes, component layout improvements, inspect code diffs, or generate an implementation plan.
                    </p>
                  </div>
                </div>
              )}

              {/* Chat Message Stream */}
              {(session?.chatMessages || []).map((msg) => {
                const isAgent = msg.sender === 'agent';

                if (!isAgent) {
                  // User Message (Right-aligned, ChatGPT style)
                  return (
                    <div
                      key={msg.id}
                      data-testid={`chat-message-${msg.id}`}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'flex-end',
                        maxWidth: '82%',
                        alignSelf: 'flex-end'
                      }}
                    >
                      <div style={{
                        fontSize: '11px',
                        color: 'var(--text-muted)',
                        marginBottom: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}>
                        <span style={{ fontWeight: 600 }}>You</span>
                        <span>•</span>
                        <span>{msg.timestamp ? msg.timestamp.slice(11, 16) : ''}</span>
                      </div>

                      <div style={{
                        padding: '12px 16px',
                        borderRadius: '16px 16px 4px 16px',
                        backgroundColor: 'var(--accent-blue)',
                        color: '#FFFFFF',
                        fontSize: '13px',
                        lineHeight: 1.55,
                        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word'
                      }}>
                        {msg.content}
                      </div>
                    </div>
                  );
                }

                // Agent Message (Left-aligned, ChatGPT style with Avatar & Markdown code blocks)
                return (
                  <div
                    key={msg.id}
                    data-testid={`chat-message-${msg.id}`}
                    style={{
                      display: 'flex',
                      gap: '12px',
                      maxWidth: '92%',
                      alignSelf: 'flex-start',
                      width: '100%'
                    }}
                  >
                    {/* Agent Avatar */}
                    <div style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(24, 144, 255, 0.12)',
                      border: '1px solid rgba(24, 144, 255, 0.25)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--accent-blue)',
                      flexShrink: 0,
                      marginTop: '2px'
                    }}>
                      <Sparkles size={16} />
                    </div>

                    <div style={{
                      display: 'flex',
                      flexDirection: 'column',
                      flex: 1,
                      minWidth: 0
                    }}>
                      {/* Agent Header Metadata */}
                      <div style={{
                        fontSize: '11px',
                        color: 'var(--text-muted)',
                        marginBottom: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {msg.agentName || 'Main Architecture Agent'}
                        </span>
                        {msg.model && (
                          <span style={{
                            fontSize: '9.5px',
                            backgroundColor: 'rgba(255, 255, 255, 0.06)',
                            padding: '1px 6px',
                            borderRadius: '4px',
                            color: 'var(--text-muted)'
                          }}>
                            {msg.model}
                          </span>
                        )}
                        <span>•</span>
                        <span>{msg.timestamp ? msg.timestamp.slice(11, 16) : ''}</span>
                      </div>

                      {/* Message Content Area (Direct in Chat Area, No Nested Card) */}
                      <div style={{
                        padding: '2px 0 6px 0',
                        color: 'var(--text-primary)',
                        fontSize: '13.5px',
                        lineHeight: 1.65,
                        wordBreak: 'break-word',
                        width: '100%',
                        border: msg.status === 'error' ? '1px solid var(--status-failed-border)' : 'none',
                        borderRadius: msg.status === 'error' ? '6px' : '0'
                      }}>
                        {renderMessageContent(msg.content)}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Generating / Thinking indicator */}
              {isSendingChat && (
                <div style={{
                  display: 'flex',
                  gap: '12px',
                  alignSelf: 'flex-start',
                  maxWidth: '85%'
                }}>
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(24, 144, 255, 0.15)',
                    border: '1px solid rgba(24, 144, 255, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--accent-blue)',
                    flexShrink: 0
                  }}>
                    <Activity size={16} className="animate-spin" />
                  </div>

                  <div style={{
                    padding: '6px 0',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    color: 'var(--accent-blue)',
                    fontSize: '12.5px'
                  }}>
                    <span style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--accent-blue)', animation: 'pulse 1.4s infinite' }}></span>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--accent-blue)', animation: 'pulse 1.4s infinite 0.2s' }}></span>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--accent-blue)', animation: 'pulse 1.4s infinite 0.4s' }}></span>
                    </span>
                    <span style={{ color: 'var(--text-secondary)' }}>
                      Main Architecture Agent is analyzing and formulating response...
                    </span>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} style={{ height: '1px' }} />
            </div>

            {/* 3. MESSAGE COMPOSER (PERMANENTLY ANCHORED BOTTOM SECTION) */}
            <div style={{
              flexShrink: 0,
              padding: '12px 20px 14px 20px',
              backgroundColor: 'var(--bg-card)',
              borderTop: '1px solid var(--border-card)',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              position: 'relative'
            }}>
              {/* Floating "Jump to Latest" Pill Button */}
              {showScrollBottomBtn && (
                <button
                  onClick={() => scrollToBottom('smooth')}
                  data-testid="scroll-to-bottom-btn"
                  style={{
                    position: 'absolute',
                    top: '-34px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    backgroundColor: 'var(--bg-elevated)',
                    border: '1px solid var(--accent-blue)',
                    color: 'var(--accent-blue)',
                    borderRadius: '16px',
                    padding: '4px 12px',
                    fontSize: '11px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
                    zIndex: 20
                  }}
                >
                  <ArrowDown size={12} />
                  <span>Latest messages</span>
                </button>
              )}


              {/* Multiline Message Input with Integrated Send Button */}
              <div style={{
                display: 'flex',
                alignItems: 'flex-end',
                gap: '8px',
                padding: '8px 12px',
                backgroundColor: 'var(--bg-app)',
                borderRadius: '12px',
                border: '1px solid var(--border-card)',
                boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.2)'
              }}>
                <textarea
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={handleChatKeyDown}
                  placeholder="Message Main Architecture Agent... (Press Enter to send, Shift+Enter for new line)"
                  data-testid="agent-chat-input"
                  rows={2}
                  disabled={isSendingChat}
                  style={{
                    flex: 1,
                    minHeight: '44px',
                    maxHeight: '140px',
                    resize: 'none',
                    padding: '4px 0',
                    fontSize: '13px',
                    lineHeight: '1.5',
                    fontFamily: 'var(--font-sans)',
                    backgroundColor: 'transparent',
                    border: 'none',
                    color: 'var(--text-primary)',
                    outline: 'none'
                  }}
                />

                <button
                  onClick={() => handleSendMessage()}
                  disabled={isSendingChat || !chatInput.trim()}
                  data-testid="send-chat-btn"
                  title="Send message (Enter)"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    padding: '8px 14px',
                    backgroundColor: (isSendingChat || !chatInput.trim()) ? 'rgba(24, 144, 255, 0.2)' : 'var(--accent-blue)',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '12.5px',
                    fontWeight: 600,
                    cursor: (isSendingChat || !chatInput.trim()) ? 'not-allowed' : 'pointer',
                    opacity: (isSendingChat || !chatInput.trim()) ? 0.6 : 1,
                    transition: 'all 0.15s ease',
                    flexShrink: 0
                  }}
                >
                  {isSendingChat ? (
                    <Activity size={15} className="animate-spin" />
                  ) : (
                    <Send size={15} />
                  )}
                  <span>{isSendingChat ? 'Sending...' : 'Send'}</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 3 CONTENT: IMPLEMENTATION PLAN & GATE 1 APPROVAL */}
        {/* ============================================================== */}
        {activeTab === 'plan' && (
          <div 
            data-testid="change-review-panel"
            style={{
              padding: '20px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              flex: 1
            }}
          >
            {/* Top Plan Generation Banner */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              borderRadius: '6px',
              backgroundColor: 'var(--bg-app)',
              border: '1px solid var(--border-subtle)',
              flexWrap: 'wrap',
              gap: '12px'
            }}>
              <div>
                <h4 style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                  Architecture Implementation Plan
                </h4>
                <p style={{ fontSize: '11.5px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                  Selected: {selectedFeedbackIds.length > 0 ? `${selectedFeedbackIds.length} sticky note(s)` : 'All pending feedback'}
                </p>
              </div>

              <button
                onClick={handleGeneratePlan}
                disabled={isGeneratingPlan}
                data-testid="generate-plan-btn"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '7px 16px',
                  backgroundColor: 'var(--accent-blue)',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: isGeneratingPlan ? 'not-allowed' : 'pointer',
                  opacity: isGeneratingPlan ? 0.7 : 1
                }}
              >
                <Sparkles size={14} />
                <span>{isGeneratingPlan ? 'Generating Plan...' : 'Generate Plan'}</span>
              </button>
            </div>

            {/* The 5-Part Implementation Plan View */}
            {plan ? (
              <div 
                data-testid="implementation-plan-container"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '14px',
                  padding: '18px 20px',
                  backgroundColor: 'var(--bg-app)',
                  borderRadius: '6px',
                  border: '1px solid var(--border-card)'
                }}
              >
                {/* Plan Metadata Header */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingBottom: '10px',
                  borderBottom: '1px solid var(--border-card)',
                  fontSize: '11.5px',
                  color: 'var(--text-muted)',
                  flexWrap: 'wrap',
                  gap: '8px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Cpu size={14} color="var(--accent-blue)" />
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      Plan by {plan.generatedByAgent}
                    </span>
                  </div>
                  <div>
                    LLM: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>{plan.llmProvider} ({plan.llmModel || 'claude-code'})</span>
                  </div>
                </div>

                {/* Section 1: Understanding of Requested Changes */}
                <div>
                  <h5 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-cyan)', margin: '0 0 6px 0' }}>
                    1. UNDERSTANDING OF REQUESTED CHANGES
                  </h5>
                  <p style={{ margin: 0, fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.55 }}>
                    {plan.understanding}
                  </p>
                </div>

                {/* Section 2: Proposed UI Modifications */}
                <div>
                  <h5 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-cyan)', margin: '0 0 6px 0' }}>
                    2. PROPOSED UI MODIFICATIONS
                  </h5>
                  <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    {(plan.proposedModifications || []).map((mod, idx) => (
                      <li key={idx}>{mod}</li>
                    ))}
                  </ul>
                </div>

                {/* Section 3: Affected Components & Source Files */}
                <div>
                  <h5 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-cyan)', margin: '0 0 6px 0' }}>
                    3. AFFECTED COMPONENTS & SOURCE FILES
                  </h5>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {(plan.affectedComponents || []).map((comp, idx) => (
                      <div key={idx} style={{
                        padding: '8px 12px',
                        backgroundColor: 'var(--bg-card)',
                        borderRadius: '4px',
                        border: '1px solid var(--border-subtle)',
                        fontSize: '11.5px'
                      }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{comp.name}</div>
                        <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-blue)', margin: '2px 0' }}>{comp.sourceFile}</div>
                        <div style={{ color: 'var(--text-secondary)' }}>{comp.description}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Section 4: Potential Risks & Dependencies */}
                <div>
                  <h5 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-cyan)', margin: '0 0 6px 0' }}>
                    4. POTENTIAL RISKS & DEPENDENCIES
                  </h5>
                  <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    {(plan.risksAndDependencies || []).map((risk, idx) => (
                      <li key={idx}>{risk}</li>
                    ))}
                  </ul>
                </div>

                {/* Section 5: Validation & Testing Steps */}
                <div>
                  <h5 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-cyan)', margin: '0 0 6px 0' }}>
                    5. VALIDATION & TESTING STEPS
                  </h5>
                  <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    {(plan.validationAndTestingSteps || []).map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                </div>

                {/* --- GATE 1 SEPARATE APPROVAL ACTION --- */}
                <div style={{
                  marginTop: '8px',
                  paddingTop: '14px',
                  borderTop: '1px solid var(--border-card)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '12px'
                }}>
                  <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                    Gate 1 Rule: Code implementation is strictly blocked until this architecture plan is approved.
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {plan.planApproved ? (
                      <>
                        <div 
                          data-testid="plan-approved-badge"
                          style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--status-completed)', fontSize: '12px', fontWeight: 600 }}
                        >
                          <CheckCircle2 size={16} />
                          <span>Plan Approved (Gate 1 Passed)</span>
                        </div>

                        <button
                          onClick={() => setActiveTab('implementation')}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '7px 14px',
                            backgroundColor: 'var(--accent-blue)',
                            color: '#FFFFFF',
                            border: 'none',
                            borderRadius: '4px',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer'
                          }}
                        >
                          <span>Proceed to Implementation (Gate 2) →</span>
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={handleApprovePlan}
                        data-testid="approve-plan-btn"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '7px 18px',
                          backgroundColor: 'var(--status-completed)',
                          color: '#FFFFFF',
                          border: 'none',
                          borderRadius: '4px',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer'
                        }}
                      >
                        <ThumbsUp size={14} />
                        <span>Approve Plan (Gate 1)</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div style={{
                textAlign: 'center',
                padding: '48px 16px',
                color: 'var(--text-muted)',
                backgroundColor: 'var(--bg-app)',
                borderRadius: '6px',
                border: '1px dashed var(--border-card)'
              }}>
                <FileCode size={32} style={{ margin: '0 auto 10px auto', opacity: 0.5 }} />
                <h4 style={{ fontSize: '14px', color: 'var(--text-primary)', margin: '0 0 6px 0' }}>No Plan Generated Yet</h4>
                <p style={{ fontSize: '12px', margin: '0 0 14px 0' }}>
                  Click "Generate Plan" above to trigger architectural analysis by the Main Architecture Agent.
                </p>
                <button
                  onClick={handleGeneratePlan}
                  disabled={isGeneratingPlan}
                  style={{
                    padding: '7px 16px',
                    backgroundColor: 'var(--accent-blue)',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '4px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Generate Implementation Plan
                </button>
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 4 CONTENT: IMPLEMENTATION, GATE 2 AUTHORIZATION & REAL TESTS */}
        {/* ============================================================== */}
        {activeTab === 'implementation' && (
          <div 
            data-testid="implementation-panel"
            style={{
              padding: '20px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              flex: 1
            }}
          >
            {/* Gate 2 Authorization Status Card */}
            <div style={{
              padding: '16px 18px',
              borderRadius: '6px',
              backgroundColor: 'var(--bg-app)',
              border: '1px solid var(--border-card)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px'
            }}>
              <div>
                <h4 style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                  Gate 2: Implementation Authorization
                </h4>
                <p style={{ fontSize: '11.5px', color: 'var(--text-muted)', margin: '3px 0 0 0' }}>
                  Implementation requires prior plan approval (Gate 1). Code modifications are locked until authorized.
                </p>
              </div>

              <div>
                {plan?.implementationAuthorized ? (
                  <div 
                    data-testid="implementation-authorized-badge"
                    style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent-cyan)', fontSize: '12.5px', fontWeight: 600 }}
                  >
                    <ShieldCheck size={18} />
                    <span>Implementation Authorized (Gate 2 Passed)</span>
                  </div>
                ) : (
                  <button
                    onClick={handleAuthorizeImplementation}
                    disabled={!plan?.planApproved}
                    data-testid="authorize-implementation-btn"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 18px',
                      backgroundColor: plan?.planApproved ? 'var(--accent-blue)' : 'var(--bg-card)',
                      color: plan?.planApproved ? '#FFFFFF' : 'var(--text-muted)',
                      border: plan?.planApproved ? 'none' : '1px solid var(--border-card)',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: plan?.planApproved ? 'pointer' : 'not-allowed'
                    }}
                  >
                    <Play size={13} />
                    <span>Authorize Implementation (Gate 2)</span>
                  </button>
                )}
              </div>
            </div>

            {/* If Plan is not approved yet, display explicit warning */}
            {!plan?.planApproved && (
              <div style={{
                padding: '12px 16px',
                borderRadius: '4px',
                backgroundColor: 'rgba(250, 140, 22, 0.08)',
                border: '1px solid rgba(250, 140, 22, 0.25)',
                color: '#FA8C16',
                fontSize: '12px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <AlertTriangle size={16} />
                <span>Plan Approval Required: You must approve the architecture plan in the Implementation Plan tab before authorizing implementation.</span>
              </div>
            )}

            {/* Implementation Verification & Acceptance Testing Card */}
            {plan?.implementationAuthorized && (
              <div 
                data-testid="implementation-execution-card"
                style={{
                  padding: '16px 18px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-card)',
                  backgroundColor: 'var(--bg-app)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Terminal size={16} color="var(--accent-blue)" />
                    <span style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                      Implementation Verification & Acceptance Testing
                    </span>
                  </div>

                  <button
                    onClick={handleRunTests}
                    disabled={isRunningTests}
                    data-testid="run-implementation-tests-btn"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '7px 16px',
                      backgroundColor: 'var(--accent-blue)',
                      color: '#FFFFFF',
                      border: 'none',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: isRunningTests ? 'not-allowed' : 'pointer'
                    }}
                  >
                    <Activity size={13} />
                    <span>{isRunningTests ? 'Executing Acceptance Suite...' : 'Run Acceptance Tests'}</span>
                  </button>
                </div>

                {session?.testResults && (
                  <div style={{
                    padding: '12px',
                    borderRadius: '4px',
                    backgroundColor: 'var(--bg-card)',
                    border: `1px solid ${session.testResults.passed ? 'var(--status-completed-border)' : 'var(--status-failed-border)'}`,
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontWeight: 700, color: session.testResults.passed ? 'var(--status-completed)' : 'var(--status-failed)' }}>
                        {session.testResults.passed ? '✓ PASSED: ' : '✗ FAILED: '} {session.testResults.suiteName}
                      </span>
                      <span style={{ color: 'var(--text-muted)' }}>
                        Duration: {session.testResults.durationMs}ms
                      </span>
                    </div>
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', maxHeight: '160px', overflowY: 'auto' }}>
                      {session.testResults.output}
                    </pre>
                  </div>
                )}

                {/* Modified Files Overview */}
                <div style={{ marginTop: '4px' }}>
                  <h5 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 6px 0' }}>
                    Affected Components in Task:
                  </h5>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {(plan?.affectedComponents || []).map((c, i) => (
                      <span key={i} style={{
                        padding: '3px 8px',
                        borderRadius: '3px',
                        backgroundColor: 'var(--bg-card)',
                        border: '1px solid var(--border-subtle)',
                        fontSize: '11px',
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--accent-blue)'
                      }}>
                        {c.name} ({c.sourceFile})
                      </span>
                    ))}
                  </div>
                </div>

                {/* Bridge to Preview Tab */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '6px' }}>
                  <button
                    onClick={() => setActiveTab('preview')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '7px 14px',
                      backgroundColor: 'transparent',
                      color: 'var(--accent-blue)',
                      border: '1px solid var(--accent-blue)',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    <span>Proceed to Preview & Approval →</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 5 CONTENT: PREVIEW & FINAL UI APPROVAL (GATE 3) */}
        {/* ============================================================== */}
        {activeTab === 'preview' && (
          <div 
            data-testid="final-ui-review-container"
            style={{
              padding: '20px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              flex: 1
            }}
          >
            {/* Top Review Status Banner */}
            <div style={{
              padding: '14px 18px',
              borderRadius: '6px',
              backgroundColor: 'var(--bg-app)',
              border: '1px solid var(--border-card)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px'
            }}>
              <div>
                <h4 style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                  Gate 3: Preview & Final UI Approval
                </h4>
                <p style={{ fontSize: '11.5px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                  Review updated UI rendering against design standards and execute final sign-off.
                </p>
              </div>

              <div>
                <span style={{
                  padding: '3px 10px',
                  borderRadius: '12px',
                  fontSize: '11px',
                  fontWeight: 700,
                  backgroundColor: session?.finalUiStatus === 'approved' 
                    ? 'rgba(82, 196, 26, 0.15)' 
                    : (session?.finalUiStatus === 'changes_requested' ? 'rgba(250, 140, 22, 0.15)' : 'rgba(24, 144, 255, 0.15)'),
                  color: session?.finalUiStatus === 'approved' 
                    ? 'var(--status-completed)' 
                    : (session?.finalUiStatus === 'changes_requested' ? '#FA8C16' : 'var(--accent-blue)'),
                  border: '1px solid currentColor'
                }}>
                  STATUS: {session?.finalUiStatus?.replace(/_/g, ' ').toUpperCase() || 'PENDING REVIEW'}
                </span>
              </div>
            </div>

            {/* Target Component Preview Frame */}
            <div style={{
              padding: '18px 20px',
              borderRadius: '6px',
              backgroundColor: 'var(--bg-app)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Visual Preview of Modified UI Component
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  High-DPI Anti-Aliased • Tabular Numerals Active
                </span>
              </div>

              {/* Live Rendered Card Sample */}
              <div style={{
                padding: '16px',
                borderRadius: '6px',
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-card)',
                maxWidth: '420px',
                margin: '0 auto',
                boxShadow: 'var(--shadow-card)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>STAGE 01</span>
                  <span style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    backgroundColor: 'rgba(82, 196, 26, 0.15)',
                    color: 'var(--status-completed)',
                    padding: '2px 6px',
                    borderRadius: '4px'
                  }}>
                    READY
                  </span>
                </div>
                <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
                  Audio Input & Narration
                </div>
                <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                  Narration audio ingested and verified.
                </div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '12px',
                  color: 'var(--accent-blue)',
                  fontWeight: 700,
                  fontVariantNumeric: 'tabular-nums'
                }}>
                  <span>Progress</span>
                  <span>100%</span>
                </div>
              </div>
            </div>

            {/* Automated Acceptance Verification Telemetry Summary */}
            {session?.testResults && (
              <div style={{
                padding: '12px 16px',
                borderRadius: '4px',
                backgroundColor: 'var(--bg-app)',
                border: '1px solid var(--border-subtle)',
                fontSize: '11.5px',
                color: 'var(--text-secondary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <span>
                  Acceptance Suite: <strong>{session.testResults.suiteName}</strong>
                </span>
                <span style={{ color: session.testResults.passed ? 'var(--status-completed)' : 'var(--status-failed)', fontWeight: 600 }}>
                  {session.testResults.passed ? '✓ PASSED' : '✗ FAILED'} ({session.testResults.durationMs}ms)
                </span>
              </div>
            )}

            {/* GATE 3 SEPARATE ACTIONS */}
            <div style={{
              marginTop: '4px',
              paddingTop: '16px',
              borderTop: '1px solid var(--border-card)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px'
            }}>
              {/* Action 1: Request Further Changes */}
              <button
                onClick={() => handleFinalUiDecision('changes_requested')}
                data-testid="request-further-changes-btn"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 16px',
                  backgroundColor: 'transparent',
                  color: '#FA8C16',
                  border: '1px solid #FA8C16',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                <RotateCcw size={13} />
                <span>Request Further Changes</span>
              </button>

              {/* Action 2: Approve Final UI */}
              <button
                onClick={() => handleFinalUiDecision('approved')}
                data-testid="approve-final-ui-btn"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 20px',
                  backgroundColor: 'var(--status-completed)',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                <CheckCircle2 size={15} />
                <span>Approve Final UI</span>
              </button>
            </div>
          </div>
        )}
        </div>

        {/* RIGHT COLUMN: RIGHT-SIDE MENU BAR WITH TABS */}
        <aside
          data-testid="visual-editor-right-menu"
          style={{
            width: '240px',
            flexShrink: 0,
            borderLeft: '1px solid var(--border-card)',
            backgroundColor: 'var(--bg-app)',
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            boxSizing: 'border-box'
          }}
        >
          {/* Header of Right Menu */}
          <div style={{
            padding: '16px 16px 14px 16px',
            borderBottom: '1px solid var(--border-card)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0
          }}>
            <span style={{
              fontSize: '11px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.8px',
              color: 'var(--text-muted)'
            }}>
              Editor Tabs
            </span>
            <span style={{
              backgroundColor: 'rgba(24, 144, 255, 0.1)',
              color: 'var(--accent-blue)',
              padding: '2px 8px',
              borderRadius: '10px',
              fontSize: '10.5px',
              fontWeight: 700
            }}>
              Stage {activeTab === 'feedback' ? '1' : activeTab === 'chat' ? '2' : activeTab === 'plan' ? '3' : activeTab === 'implementation' ? '4' : '5'}
            </span>
          </div>

          {/* Navigation Items (The 5 Tabs) */}
          <nav style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            padding: '12px 10px',
            flex: 1,
            overflowY: 'auto'
          }}>
            {/* TAB 1: Feedback */}
            <button
              onClick={() => setActiveTab('feedback')}
              data-testid="tab-feedback"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
                padding: '10px 12px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: activeTab === 'feedback' ? 'rgba(24, 144, 255, 0.12)' : 'transparent',
                color: activeTab === 'feedback' ? 'var(--accent-blue)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'feedback' ? 600 : 400,
                fontSize: '13px',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
                borderLeft: activeTab === 'feedback' ? '3px solid var(--accent-blue)' : '3px solid transparent'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Layers size={15} style={{ color: activeTab === 'feedback' ? 'var(--accent-blue)' : 'var(--text-muted)' }} />
                <span>Feedback</span>
              </div>
              {feedbackList.length > 0 && (
                <span style={{
                  backgroundColor: activeTab === 'feedback' ? 'rgba(24, 144, 255, 0.25)' : 'var(--border-subtle)',
                  color: activeTab === 'feedback' ? 'var(--accent-blue)' : 'var(--text-muted)',
                  fontSize: '10.5px',
                  fontWeight: 700,
                  padding: '1px 6px',
                  borderRadius: '8px'
                }}>
                  {feedbackList.length}
                </span>
              )}
            </button>

            {/* TAB 2: AI Chat */}
            <button
              onClick={() => setActiveTab('chat')}
              data-testid="tab-ai-chat"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
                padding: '10px 12px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: activeTab === 'chat' ? 'rgba(24, 144, 255, 0.12)' : 'transparent',
                color: activeTab === 'chat' ? 'var(--accent-blue)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'chat' ? 600 : 400,
                fontSize: '13px',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
                borderLeft: activeTab === 'chat' ? '3px solid var(--accent-blue)' : '3px solid transparent'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <MessageSquare size={15} style={{ color: activeTab === 'chat' ? 'var(--accent-blue)' : 'var(--text-muted)' }} />
                <span>AI Chat</span>
              </div>
            </button>

            {/* TAB 3: Implementation Plan */}
            <button
              onClick={() => setActiveTab('plan')}
              data-testid="tab-plan"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
                padding: '10px 12px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: activeTab === 'plan' ? 'rgba(24, 144, 255, 0.12)' : 'transparent',
                color: activeTab === 'plan' ? 'var(--accent-blue)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'plan' ? 600 : 400,
                fontSize: '13px',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
                borderLeft: activeTab === 'plan' ? '3px solid var(--accent-blue)' : '3px solid transparent'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileCode size={15} style={{ color: activeTab === 'plan' ? 'var(--accent-blue)' : 'var(--text-muted)' }} />
                <span>Implementation Plan</span>
              </div>
              {plan?.planApproved && (
                <span style={{
                  backgroundColor: 'rgba(82, 196, 26, 0.15)',
                  color: 'var(--status-completed)',
                  fontSize: '10px',
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: '6px'
                }}>
                  Approved
                </span>
              )}
            </button>

            {/* TAB 4: Implementation */}
            <button
              onClick={() => setActiveTab('implementation')}
              data-testid="tab-implementation"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
                padding: '10px 12px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: activeTab === 'implementation' ? 'rgba(24, 144, 255, 0.12)' : 'transparent',
                color: activeTab === 'implementation' ? 'var(--accent-blue)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'implementation' ? 600 : 400,
                fontSize: '13px',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
                borderLeft: activeTab === 'implementation' ? '3px solid var(--accent-blue)' : '3px solid transparent'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Terminal size={15} style={{ color: activeTab === 'implementation' ? 'var(--accent-blue)' : 'var(--text-muted)' }} />
                <span>Implementation</span>
              </div>
              {session?.testResults && (
                <span style={{
                  backgroundColor: session.testResults.passed ? 'rgba(82, 196, 26, 0.15)' : 'rgba(255, 77, 79, 0.15)',
                  color: session.testResults.passed ? 'var(--status-completed)' : 'var(--status-failed)',
                  fontSize: '10px',
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: '6px'
                }}>
                  {session.testResults.passed ? 'Verified' : 'Failed'}
                </span>
              )}
            </button>

            {/* TAB 5: Preview & Approval */}
            <button
              onClick={() => setActiveTab('preview')}
              data-testid="tab-preview"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
                padding: '10px 12px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: activeTab === 'preview' ? 'rgba(24, 144, 255, 0.12)' : 'transparent',
                color: activeTab === 'preview' ? 'var(--accent-blue)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'preview' ? 600 : 400,
                fontSize: '13px',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
                borderLeft: activeTab === 'preview' ? '3px solid var(--accent-blue)' : '3px solid transparent'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle2 size={15} style={{ color: activeTab === 'preview' ? 'var(--accent-blue)' : 'var(--text-muted)' }} />
                <span>Preview & Approval</span>
              </div>
              {session?.finalUiStatus === 'approved' && (
                <span style={{
                  backgroundColor: 'rgba(82, 196, 26, 0.15)',
                  color: 'var(--status-completed)',
                  fontSize: '10px',
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: '6px'
                }}>
                  Signed Off
                </span>
              )}
            </button>
          </nav>

          {/* Footer Info / Stage Status */}
          <div style={{
            marginTop: 'auto',
            padding: '14px 16px',
            borderTop: '1px solid var(--border-card)',
            backgroundColor: 'rgba(0, 0, 0, 0.12)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            flexShrink: 0
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Workflow</span>
              <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>Active</span>
            </div>
            <div style={{
              fontSize: '11px',
              color: 'var(--text-secondary)',
              lineHeight: 1.45
            }}>
              {activeTab === 'feedback' && 'Collect & review sticky notes on UI components.'}
              {activeTab === 'chat' && 'Collaborate with Main Architecture Agent on changes.'}
              {activeTab === 'plan' && 'Review architectural sections, affected files, and sign off.'}
              {activeTab === 'implementation' && 'Inspect git diffs and run automated acceptance tests.'}
              {activeTab === 'preview' && 'Test live preview and give final UI approval.'}
            </div>
          </div>
        </aside>
      </div>

      {/* Add Feedback Modal */}
      <AddFeedbackModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSubmit={handleAddFeedback}
        catalog={catalog}
      />
    </div>
  );
};
