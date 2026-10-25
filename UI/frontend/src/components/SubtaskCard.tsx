import React, { useState, useEffect } from 'react';
import styles from './SubtaskCard.module.css';
import {
  CheckCircle2,
  Clock,
  AlertTriangle,
  AlertCircle,
  Loader2,
  FileAudio,
  FileSearch,
  Sliders,
  Languages,
  Mic,
  BookOpen,
  Target,
  GitCompare,
  AlignLeft,
  AudioLines,
  Gauge,
  ShieldCheck,
  Database,
  Film,
  PlaySquare,
  Activity,
  Sparkles,
} from 'lucide-react';
import { SubtaskStep } from '../services/api';
import { SubtaskDetailModal } from './SubtaskDetailModal';

export interface SubtaskCardProps {
  subtask: SubtaskStep;
  index: number;
  stageRunning?: boolean;
  llmChecksRunning?: boolean;
  activeModel?: string;
}

/**
 * Returns a sleek Lucide icon and concise friendly label for each subtask.
 * Ensures cards don't suffer from clumsy text truncation and have strong visual identity.
 */
function getSubtaskVisualMeta(stepNum: number, name: string): { icon: React.ReactNode; shortLabel: string } {
  const lower = (name || '').toLowerCase();

  // Known Audio Analysis steps (1 - 14)
  if (stepNum === 1 || lower.includes('file valid') || lower.includes('audio file')) {
    return { icon: <FileAudio size={22} />, shortLabel: 'Audio File' };
  }
  if (stepNum === 2 || lower.includes('metadata') || lower.includes('format probe')) {
    return { icon: <FileSearch size={22} />, shortLabel: 'Metadata' };
  }
  if (stepNum === 3 || lower.includes('preprocess') || lower.includes('16k') || lower.includes('resample')) {
    return { icon: <Sliders size={22} />, shortLabel: '16k Resample' };
  }
  if (stepNum === 4 || lower.includes('language') || lower.includes('speech detect')) {
    return { icon: <Languages size={22} />, shortLabel: 'Language' };
  }
  if (stepNum === 5 || lower.includes('speech-to-text') || lower.includes('asr') || lower.includes('whisper')) {
    return { icon: <Mic size={22} />, shortLabel: 'Whisper ASR' };
  }
  if (stepNum === 6 || lower.includes('vocabulary') || lower.includes('vocab')) {
    return { icon: <BookOpen size={22} />, shortLabel: 'Vocabulary' };
  }
  if (stepNum === 7 || lower.includes('confidence') || lower.includes('correction')) {
    return { icon: <Target size={22} />, shortLabel: 'Confidence' };
  }
  if (stepNum === 8 || lower.includes('raw vs corrected') || lower.includes('transcript (llm)')) {
    return { icon: <GitCompare size={22} />, shortLabel: 'Transcript LLM' };
  }
  if (stepNum === 9 || lower.includes('word-level') || lower.includes('alignment')) {
    return { icon: <AlignLeft size={22} />, shortLabel: 'Alignment' };
  }
  if (stepNum === 10 || lower.includes('timestamp') || lower.includes('integrity')) {
    return { icon: <Clock size={22} />, shortLabel: 'Timestamps' };
  }
  if (stepNum === 11 || lower.includes('pause') || lower.includes('rhythm')) {
    return { icon: <AudioLines size={22} />, shortLabel: 'Pauses & Rhythm' };
  }
  if (stepNum === 12 || lower.includes('quality') || lower.includes('uncertainty')) {
    return { icon: <Gauge size={22} />, shortLabel: 'Audio Quality' };
  }
  if (stepNum === 13 || lower.includes('final audio analysis') || lower.includes('final validation')) {
    return { icon: <ShieldCheck size={22} />, shortLabel: 'Validation' };
  }
  if (stepNum === 14 || lower.includes('caching') || lower.includes('resume')) {
    return { icon: <Database size={22} />, shortLabel: 'Cache & Resume' };
  }

  // General fallbacks for other pipeline stages
  if (lower.includes('scene') || lower.includes('segment')) {
    return { icon: <Film size={22} />, shortLabel: name.slice(0, 14) };
  }
  if (lower.includes('motion') || lower.includes('animat') || lower.includes('layer')) {
    return { icon: <PlaySquare size={22} />, shortLabel: name.slice(0, 14) };
  }
  if (lower.includes('render') || lower.includes('stream') || lower.includes('video')) {
    return { icon: <Activity size={22} />, shortLabel: name.slice(0, 14) };
  }
  if (lower.includes('validat') || lower.includes('gate') || lower.includes('qc') || lower.includes('check')) {
    return { icon: <ShieldCheck size={22} />, shortLabel: name.slice(0, 14) };
  }
  return { icon: <Sparkles size={22} />, shortLabel: name.slice(0, 14) };
}

export const SubtaskCard: React.FC<SubtaskCardProps> = ({
  subtask,
  index,
  stageRunning = false,
  llmChecksRunning = false,
  activeModel = 'gemini-3.8-flash-high',
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const n = subtask.n ?? index + 1;
  const name = subtask.name || `Subtask #${n}`;
  const rawStatus = (subtask.status || '').toLowerCase();

  // Completion Percentage calculation
  const passed = subtask.checks_passed;
  const total = subtask.checks_total;
  let completionPercent = subtask.completion_percent;
  if (completionPercent === undefined || completionPercent === null) {
    if (total && total > 0 && passed !== null && passed !== undefined) {
      completionPercent = Math.round((passed / total) * 100);
    } else if (subtask.progress_percent !== undefined && subtask.progress_percent !== null) {
      completionPercent = subtask.progress_percent;
    } else if (rawStatus === 'completed' || rawStatus === 'passed') {
      completionPercent = 100;
    } else if (rawStatus === 'running') {
      completionPercent = 50;
    } else {
      completionPercent = 0;
    }
  }

  // LLM Verification status
  const c = subtask.llm_check;
  const hasCurrentCheck = Boolean(c && c.current);

  const modelName = subtask.llm_verification?.model || c?.model || activeModel;
  const latencyMs = subtask.llm_verification?.latency_ms ?? c?.latency_ms;
  const noteText = subtask.llm_verification?.note || c?.note || '';

  // Explicit Card State Hierarchy:
  // 1. FAILED: raw status failed/error, or LLM rejected
  // 2. WARNING: raw status warning, 0% with warning, or LLM questioned
  // 3. IN_PROGRESS: step actively running or LLM verification in progress
  // 4. PENDING: disabled, pending, or queued for verification
  // 5. VERIFIED: raw status completed/passed AND (verdict confirms or no contradiction)

  const isRawWarning = rawStatus === 'warning';
  const isRawError = rawStatus === 'failed' || rawStatus === 'error' || rawStatus === 'blocked';
  const isQuestioned = (hasCurrentCheck && c?.verdict === 'questions') || subtask.llm_verification?.state === 'questioned';
  const isRejected = (hasCurrentCheck && (c?.verdict === 'rejects' || c?.verdict === 'error')) ||
                     subtask.llm_verification?.state === 'rejected' ||
                     subtask.llm_verification?.state === 'failed';

  let cardState: 'verified' | 'warning' | 'in_progress' | 'pending' | 'failed' = 'pending';

  if (isRawError || isRejected) {
    cardState = 'failed';
  } else if (isRawWarning || isQuestioned || (subtask.completion_percent === 0 && rawStatus !== 'pending' && !subtask.disabled && rawStatus !== 'running')) {
    cardState = 'warning';
  } else if (subtask.disabled || subtask.llm_verification?.state === 'pending' || rawStatus === 'pending') {
    cardState = 'pending';
  } else if (rawStatus === 'running' || subtask.llm_verification?.state === 'in_progress') {
    cardState = 'in_progress';
  } else if ((rawStatus === 'completed' || rawStatus === 'passed') && ((hasCurrentCheck && c?.verdict === 'confirms') || subtask.llm_verification?.state === 'verified' || (!c && !subtask.llm_verification))) {
    cardState = 'verified';
  } else if (llmChecksRunning && !hasCurrentCheck) {
    cardState = 'pending';
  } else {
    cardState = 'pending';
  }

  // Active in-flight live ticker
  const [inFlightTick, setInFlightTick] = useState<number>(0);

  useEffect(() => {
    if (cardState !== 'in_progress') {
      setInFlightTick(0);
      return;
    }
    const interval = setInterval(() => {
      setInFlightTick((prev) => prev + 1);
    }, 450);
    return () => clearInterval(interval);
  }, [cardState]);

  // Display percentage based strictly on active state and actual work ("work batti percent marali"):
  let displayedPercent: number = 0;

  if (cardState === 'verified') {
    displayedPercent = 100;
  } else if (cardState === 'warning') {
    displayedPercent = subtask.completion_percent !== undefined && subtask.completion_percent !== null && subtask.completion_percent > 0
      ? subtask.completion_percent
      : 100;
  } else if (cardState === 'failed') {
    displayedPercent = 0;
  } else if (cardState === 'pending') {
    displayedPercent = 0;
  } else if (cardState === 'in_progress') {
    // Actively running / processing: NEVER show 100%!
    if (subtask.progress_percent !== undefined && subtask.progress_percent !== null && subtask.progress_percent > 0 && subtask.progress_percent < 100) {
      displayedPercent = Math.round(subtask.progress_percent);
    } else if (subtask.checks_total && subtask.checks_total > 1 && subtask.checks_passed !== undefined && subtask.checks_passed !== null && subtask.checks_passed > 0) {
      displayedPercent = Math.min(95, Math.round((subtask.checks_passed / subtask.checks_total) * 100));
    } else {
      // Dynamic work progress in flight: starts at ~18%, advances smoothly towards 95% while active
      const simulated = Math.min(95, Math.round(18 + Math.atan(inFlightTick / 3) * (77 / (Math.PI / 2))));
      displayedPercent = simulated;
    }
  }

  // Status Styling Tokens
  const statusConfig = {
    verified: {
      border: 'rgba(16, 185, 129, 0.65)',
      borderHover: 'rgba(16, 185, 129, 1)',
      accent: '#10B981',
      bg: 'rgba(16, 185, 129, 0.12)',
      cardBg: 'rgba(16, 185, 129, 0.08)',
      icon: <CheckCircle2 size={12} color="#10B981" />,
      label: 'LLM Verified',
      shortLabel: 'LLM Verified',
      badgeBg: 'rgba(16, 185, 129, 0.22)',
      badgeBorder: 'rgba(16, 185, 129, 0.5)',
      badgeColor: '#10B981',
      shadow: '0 0 10px rgba(16, 185, 129, 0.25)',
    },
    warning: {
      border: 'rgba(245, 158, 11, 0.75)',
      borderHover: 'rgba(245, 158, 11, 1)',
      accent: '#F59E0B',
      bg: 'rgba(245, 158, 11, 0.15)',
      cardBg: 'rgba(245, 158, 11, 0.08)',
      icon: <AlertTriangle size={12} color="#F59E0B" />,
      label: 'Warning Detected',
      shortLabel: 'WARNING',
      badgeBg: 'rgba(245, 158, 11, 0.22)',
      badgeBorder: 'rgba(245, 158, 11, 0.55)',
      badgeColor: '#F59E0B',
      shadow: '0 0 12px rgba(245, 158, 11, 0.35)',
    },
    failed: {
      border: 'rgba(239, 68, 68, 0.75)',
      borderHover: 'rgba(239, 68, 68, 1)',
      accent: '#EF4444',
      bg: 'rgba(239, 68, 68, 0.15)',
      cardBg: 'rgba(239, 68, 68, 0.08)',
      icon: <AlertCircle size={12} color="#EF4444" />,
      label: 'Check Failed',
      shortLabel: 'FAILED',
      badgeBg: 'rgba(239, 68, 68, 0.22)',
      badgeBorder: 'rgba(239, 68, 68, 0.55)',
      badgeColor: '#EF4444',
      shadow: '0 0 12px rgba(239, 68, 68, 0.35)',
    },
    in_progress: {
      border: '#38BDF8',
      borderHover: '#38BDF8',
      accent: '#0EA5E9',
      bg: 'rgba(14, 165, 233, 0.16)',
      cardBg: 'rgba(14, 165, 233, 0.06)',
      icon: <Loader2 size={12} className="animate-spin" color="#0EA5E9" />,
      label: 'Running Check',
      shortLabel: 'RUN',
      badgeBg: 'rgba(14, 165, 233, 0.25)',
      badgeBorder: 'rgba(14, 165, 233, 0.55)',
      badgeColor: '#0EA5E9',
      shadow: '0 0 14px rgba(14, 165, 233, 0.5)',
    },
    pending: {
      border: 'rgba(148, 163, 184, 0.25)',
      borderHover: 'rgba(148, 163, 184, 0.5)',
      accent: '#94A3B8',
      bg: 'rgba(148, 163, 184, 0.06)',
      cardBg: 'var(--bg-elevated, #131b2e)',
      icon: <Clock size={12} color="#94A3B8" />,
      label: 'Pending Verification',
      shortLabel: 'WAIT',
      badgeBg: 'rgba(148, 163, 184, 0.12)',
      badgeBorder: 'rgba(148, 163, 184, 0.25)',
      badgeColor: '#94A3B8',
      shadow: '0 2px 6px rgba(0, 0, 0, 0.2)',
    },
  }[cardState];

  const visual = getSubtaskVisualMeta(n, name);
  const isCardActive = cardState === 'in_progress';
  const isCardVerified = cardState === 'verified';
  const hasIssue = cardState === 'warning' || cardState === 'failed';

  return (
    <>
      {/* ================= ELEGANT SQUARE SUBTASK CARD ================= */}
      <div
        data-testid={`subtask-card-${n}`}
        onClick={() => setIsModalOpen(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setIsModalOpen(true);
          }
        }}
        className={`${styles.card} ${isCardActive ? styles.cardActive : ''}`}
        style={{
          backgroundColor: statusConfig.cardBg,
          border: `1px solid ${isCardActive ? '#38BDF8' : statusConfig.border}`,
          opacity: subtask.disabled ? 0.65 : 1,
          boxShadow: isCardActive ? undefined : statusConfig.shadow,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = statusConfig.borderHover;
          e.currentTarget.style.boxShadow = `0 6px 18px ${statusConfig.badgeBg}`;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = isCardActive ? '#38BDF8' : statusConfig.border;
          e.currentTarget.style.boxShadow = isCardActive ? '' : statusConfig.shadow;
        }}
        title={`${name}${subtask.detail ? ` (${subtask.detail})` : ''} - Click for Telugu & English narration`}
      >
        {/* Top Row: Status Badge (Step Number removed per user request) */}
        <div className={styles.topRow}>
          <div
            data-testid={`subtask-llm-box-${n}`}
            className={styles.badge}
            style={{
              backgroundColor: statusConfig.badgeBg,
              border: `1px solid ${statusConfig.badgeBorder}`,
            }}
          >
            {statusConfig.icon}
            <span
              style={{
                fontSize: '9.5px',
                fontWeight: 800,
                color: statusConfig.accent,
                fontFamily: 'var(--font-mono, monospace)',
                textTransform: 'uppercase',
              }}
            >
              {statusConfig.shortLabel}
            </span>
          </div>
        </div>

        {/* Center Hero: Step Icon + Percentage (Process text removed per user request) */}
        <div className={styles.centerIconBox}>
          <div
            className={`${styles.iconCircle} ${isCardActive ? styles.iconBlink : ''}`}
            style={{
              backgroundColor: statusConfig.bg,
              border: `1px solid ${statusConfig.border}`,
              color: statusConfig.accent,
              boxShadow: `0 0 10px ${statusConfig.badgeBg}`,
            }}
          >
            {visual.icon}
          </div>

          <div className={styles.bottomRow}>
            <span
              data-testid={`subtask-percentage-${n}`}
              className={styles.bigPercentage}
              style={{
                color: statusConfig.accent,
                textShadow: `0 0 12px ${statusConfig.badgeBg}`,
              }}
            >
              {displayedPercent}
            </span>
            <span
              style={{
                fontSize: '13px',
                fontWeight: 800,
                color: statusConfig.accent,
                opacity: 0.85,
                marginLeft: '1px',
              }}
            >
              %
            </span>
          </div>
        </div>

        {/* Bottom Row: Concise Step Label + Progress Bar */}
        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'center' }}>
          <span
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: isCardVerified ? '#10B981' : (hasIssue ? statusConfig.accent : 'var(--text-secondary, #cbd5e1)'),
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '100%',
              textAlign: 'center',
              lineHeight: '14px',
            }}
            title={name}
          >
            {visual.shortLabel}
          </span>

          <div
            style={{
              width: '100%',
              height: '3px',
              backgroundColor: 'rgba(255, 255, 255, 0.08)',
              borderRadius: '2px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${Math.min(100, Math.max(0, displayedPercent))}%`,
                height: '100%',
                backgroundColor: statusConfig.accent,
                borderRadius: '2px',
                transition: 'width 0.35s ease',
              }}
            />
          </div>
        </div>

        {/* Hidden model pill for tests and aria */}
        <span
          data-testid={`subtask-model-pill-${n}`}
          style={{ display: 'none' }}
        >
          {modelName}
        </span>
      </div>

      {/* ================= IN-DETAIL POPUP MODAL ================= */}
      {isModalOpen && (
        <SubtaskDetailModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          subtask={subtask}
          n={n}
          name={name}
          cardState={cardState}
          statusConfig={statusConfig}
          displayedPercent={displayedPercent}
          modelName={modelName}
          latencyMs={latencyMs}
          noteText={noteText}
        />
      )}
    </>
  );
};
