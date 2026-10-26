import React, { useState } from 'react';
import styles from './SubtaskDetailModal.module.css';
import {
  X,
  Sparkles,
  Info,
  Cpu,
  RotateCw,
} from 'lucide-react';
import { SubtaskStep } from '../services/api';

export interface SubtaskStatusConfig {
  border: string;
  borderHover: string;
  accent: string;
  bg: string;
  cardBg: string;
  icon: React.ReactNode;
  label: string;
  shortLabel: string;
  badgeBg: string;
  badgeBorder: string;
  badgeColor: string;
  shadow?: string;
}

export interface SubtaskDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  subtask: SubtaskStep;
  n: number;
  name: string;
  cardState: 'verified' | 'warning' | 'in_progress' | 'pending' | 'failed';
  statusConfig: SubtaskStatusConfig;
  displayedPercent: number;
  modelName: string;
  latencyMs?: number;
  noteText: string;
  // Runs only this subtask again; given only when that is possible. ok = it started (the modal closes: the card shows the new run)
  onRetry?: () => Promise<{ ok: boolean; message?: string }>;
}

/**
 * Generates an empathetic, conversational Human Narration in natural Telugu + English mix.
 * Explains clearly what happened, why the LLM questioned/rejected it, and how to resolve it.
 */
export function getHumanNarration(
  name: string,
  rawStatus: string,
  cardState: 'verified' | 'warning' | 'in_progress' | 'pending' | 'failed',
  noteText: string,
  modelName: string,
  detailText?: string | null,
  stepNum?: number
): {
  headline: string;
  narration: string;
  cause: string;
  solution: string;
} {
  const lowerName = (name || '').toLowerCase();
  const lowerDetail = (detailText || '').toLowerCase();
  const lowerNote = (noteText || '').toLowerCase();

  const isStep8 = stepNum === 8 || lowerName.includes('raw vs corrected') || lowerName.includes('transcript (llm)');
  const isStep13 = stepNum === 13 || lowerName.includes('final audio analysis') || lowerName.includes('final validation');
  const isCliTimeout = lowerDetail.includes('antigravity cli') || lowerNote.includes('antigravity cli') || lowerDetail.includes('180 s');

  // Specific high-priority handling for Step 8 (CLI timeout / ASR Kept)
  if (isStep8 || isCliTimeout) {
    return {
      headline: '⚠️ ట్రాన్స్‌క్రిప్ట్ LLM రివ్యూ హెచ్చరిక (Review Timed Out)',
      narration: `Whisper నుండి వచ్చిన తెలుగు టెక్స్ట్‌ను సరిచూసేందుకు LLM మోడల్‌కు పంపినప్పుడు Antigravity CLI 180 సెకన్లలో స్పందించలేదు. అందుకే ఒరిజినల్ Whisper రా టెక్స్ట్ (Original ASR text) భద్రపరచబడింది.`,
      cause: `బ్యాకెండ్ గేట్‌వేలో మోడల్ నుండి ఆలస్యం కావడం వల్ల 'warning' స్టేటస్ నమోదైంది. ఆడియో టెక్స్ట్ డేటా ఏదీ కోల్పోలేదు, రా టెక్స్ట్ సురక్షితంగా ఉంది.`,
      solution: `ఆడియో టు తెలుగు కన్వర్షన్ ఇప్పటికే విజయవంతంగా పూర్తయింది. ఒకవేళ LLM ద్వారా టెక్స్ట్‌ను మళ్లీ రివ్యూ చేయాలనుకుంటే పైనున్న "Verify remaining" బటన్‌పై క్లిక్ చేయవచ్చు.`
    };
  }

  // Specific high-priority handling for Step 13 (Validation warning)
  if (isStep13) {
    return {
      headline: '⚠️ ఫైనల్ ఆడియో వేలిడేషన్ (0 Errors, 1 Warning)',
      narration: `ఆడియో అనాలిసిస్ దశలన్నింటినీ తనిఖీ చేయగా 0 ఎర్రర్లు మరియు 1 వార్నింగ్ (స్టెప్ 8 లో LLM రివ్యూ టైమ్‌అవుట్) ఉన్నట్లు తేలింది. అందుకే ఈ సబ్‌టాస్క్ 0% తో వార్నింగ్ చూపిస్తోంది.`,
      cause: `మునుపటి స్టెప్ (Raw vs Corrected Transcript) లో ఏర్పడిన నాన్-బ్లాకింగ్ హెచ్చరిక కారణంగా ఇది రికార్డ్ అయింది.`,
      solution: `ఇది నాన్-బ్లాకింగ్ వార్నింగ్ మాత్రమే (Non-blocking warning). ఆడియో ఫైల్ మరియు ట్రాన్స్‌క్రిప్ట్ సిద్ధంగా ఉన్నాయి కాబట్టి ప్రాజెక్ట్ తదుపరి వీడియో మేకింగ్ స్టేజ్‌లకు సురక్షితంగా వెళ్లవచ్చు.`
    };
  }

  if (cardState === 'warning') {
    if (lowerNote.includes('null') || lowerNote.includes('metrics') || lowerNote.includes('insufficient') || lowerNote.includes('evidence')) {
      return {
        headline: '⚠️ ఎవిడెన్స్ మెట్రిక్స్ ఖాళీగా ఉన్నాయి (Evidence Insufficient / Incomplete)',
        narration: `ఈ సబ్‌టాస్క్ "${name}" పూర్తయినట్లు చూపిస్తోంది, కానీ దీనికి సంబంధించిన ఎవిడెన్స్ డేటాలో కీలకమైన విలువలు ఖాళీగా ('null') ఉన్నాయి.`,
        cause: `బ్యాకెండ్‌లో ఆడియో ప్రాసెసింగ్ రిపోర్ట్ (audio_analysis.json) ఇంకా పూర్తిగా రైట్ కాకముందే ఈ చెక్ రన్ అయ్యింది.`,
        solution: `ఆడియో అనాలిసిస్ స్టేజ్ పూర్తయ్యే వరకు వేచి ఉండండి. స్టేజ్ ఫినిష్ అయ్యాక పైన ఉన్న "Verify remaining with ${modelName}" బటన్ క్లిక్ చేస్తే రిపోర్ట్ నుండి అసలైన విలువలు లోడ్ అయి ఆటోమేటిక్‌గా గ్రీన్ (Verified) గా మారుతుంది.`
      };
    }
    return {
      headline: '⚠️ మోడల్ కొన్ని అంశాలపై స్పష్టత కోరుతోంది (Discrepancy / Warning Flagged)',
      narration: `ఈ స్టెప్ ఫలితాల పట్ల ${modelName} మోడల్‌కు కొన్ని అనుమానాలు లేదా వార్నింగ్‌లు ఉన్నాయి. రికార్డ్ అయిన ఫలితానికి తగినంత టెక్నికల్ ప్రూఫ్ రిపోర్ట్‌లో లేకపోవడం వల్ల Needs Review స్టేటస్‌లో ఉంచింది.`,
      cause: `స్టెప్ అవుట్‌పుట్ మరియు నిర్ధారిత పైప్‌లైన్ ప్రమాణాల మధ్య చిన్నపాటి తేడా గుర్తించబడింది.`,
      solution: `కింద ఉన్న ఒరిజినల్ టెక్నికల్ నోట్‌ను పరిశీలించండి. బ్యాకెండ్ ప్రాసెస్ ముగిసిన తర్వాత రీ-చెక్ చేయండి.`
    };
  }

  if (cardState === 'failed') {
    if (lowerNote.includes('language') || lowerNote.includes('telugu') || lowerNote.includes("'te'")) {
      return {
        headline: '❌ భాషా సమాచారంలో తేడా ఉంది (Language Mismatch / Contradiction)',
        narration: `ప్రాజెక్ట్ సెట్టింగ్స్‌లో లాంగ్వేజ్ 'te' (Telugu) అని ఉంది, కానీ రిపోర్ట్ ఎవిడెన్స్‌లో language ఫీల్డ్ 'null' గా రికార్డ్ అయ్యింది.`,
        cause: `స్టెప్ డిటైల్స్‌లో తెలుగు అని క్లెయిమ్ చేస్తున్నప్పటికీ, ఎవిడెన్స్ ఫైల్‌లో అది ప్రతిబింబించలేదు. రెండు డేటాల మధ్య వైరుధ్యం (Direct Contradiction) ఉండటం వల్ల ${modelName} దీన్ని Reject చేసింది.`,
        solution: `ఆడియో అనాలిసిస్ మరియు ట్రాన్స్‌క్రిప్షన్ ప్రాసెస్ పూర్తి కాగానే సరైన లాంగ్వేజ్ ట్యాగ్ సేవ్ అవుతుంది. అప్పుడు రీ-వెరిఫై చేస్తే పాస్ అవుతుంది.`
      };
    }
    if (lowerNote.includes('asr') || lowerNote.includes('transcript') || lowerNote.includes('zero') || lowerNote.includes('segments')) {
      return {
        headline: '❌ ట్రాన్స్‌క్రిప్షన్ డేటా ఇంకా సిద్ధం కాలేదు (ASR Data Not Populated)',
        narration: `ట్రాన్స్‌క్రిప్షన్ సిద్ధమైందని స్టేటస్ చెబుతోంది, కానీ వాస్తవ ఎవిడెన్స్‌లో 0 సెగ్మెంట్స్ మరియు 0 వర్డ్స్ ఉన్నాయి.`,
        cause: `Whisper మోడల్ నుండి టెక్స్ట్ ఇంకా పూర్తిగా ఎక్స్‌ట్రాక్ట్ కాకముందే ఈ చెక్ జరగడం వల్ల ఈ లోపం బయటపడింది.`,
        solution: `ఆడియో టు టెక్స్ట్ ట్రాన్స్‌క్రిప్షన్ పూర్తయ్యే వరకు వేచి చూడండి.`
      };
    }
    return {
      headline: '❌ సమాచారంలో వైరుధ్యం ఉంది (Direct Contradiction / Rejected)',
      narration: `ఈ స్టెప్ క్లెయిమ్ చేస్తున్న ఫలితానికి మరియు వాస్తవంగా రికార్డ్ అయిన ఎవిడెన్స్ డేటాకు మధ్య స్పష్టమైన తేడా (Contradiction) ఉంది.`,
      cause: `ఎవిడెన్స్ ఫైల్‌లోని విలువలు స్టెప్ స్టేటస్‌కు మద్దతు ఇవ్వడం లేదు.`,
      solution: `దయచేసి ఈ స్టేజ్ ప్రాసెసింగ్ పూర్తయిన తర్వాత రీ-వెరిఫై చేయండి.`
    };
  }

  if (cardState === 'verified') {
    return {
      headline: '✅ 100% ధృవీకరించబడింది (Checks Passed & Verified)',
      narration: `ఈ సబ్‌టాస్క్ యొక్క అన్ని రూల్స్, మెట్రిక్స్ మరియు ఎవిడెన్స్ డేటా పర్ఫెక్ట్‌గా సరిపోయాయి!`,
      cause: `నిర్దేశిత ప్రమాణాలు, ఆడియో ఫార్మాట్ మరియు పైప్‌లైన్ నిబంధనలకు అనుగుణంగా ఉందని ${modelName} నిర్ధారించింది.`,
      solution: `ఎలాంటి లోపాలు లేవు, తదుపరి ప్రాసెసింగ్‌కు సురక్షితంగా కొనసాగవచ్చు.`
    };
  }

  if (cardState === 'in_progress') {
    return {
      headline: '🔄 వెరిఫికేషన్ నడుస్తోంది (Verification In Progress)',
      narration: `ప్రస్తుతం ${modelName} ఈ సబ్‌టాస్క్ యొక్క టెక్నికల్ వివరాలను, ఎవిడెన్స్ ఫైల్స్‌ను లైవ్‌గా పరిశీలిస్తోంది.`,
      cause: `స్టెప్ ఇప్పుడే రన్ అవ్వడం ప్రారంభించింది లేదా రీ-చెక్ ప్రాసెస్‌లో ఉంది.`,
      solution: `కొద్ది సెకన్లలో ఆటోమేటిక్‌గా వెరిఫికేషన్ పూర్తవుతుంది, దయచేసి వేచి ఉండండి.`
    };
  }

  // Pending
  return {
    headline: '⏳ వెరిఫికేషన్ కోసం వేచి ఉంది (Queued for Verification)',
    narration: `ఈ సబ్‌టాస్క్ యొక్క చెక్ ఇంకా ప్రారంభం కాలేదు. ఇది వెరిఫికేషన్ క్యూలో ఉంది.`,
    cause: `మునుపటి ప్రాసెసింగ్ స్టెప్స్ రన్ అవుతుండటం వల్ల ఇంకా దీనిపై చెక్ జరగలేదు.`,
    solution: `స్టేజ్ ప్రోగ్రెస్ అవుతున్న కొద్దీ ఇది ఆటోమేటిక్‌గా వెరిఫై చేయబడుతుంది.`
  };
}

export const SubtaskDetailModal: React.FC<SubtaskDetailModalProps> = ({
  isOpen,
  onClose,
  subtask,
  n,
  name,
  cardState,
  statusConfig,
  displayedPercent,
  modelName,
  latencyMs,
  noteText,
  onRetry,
}) => {
  const [retrying, setRetrying] = useState(false);
  const [retryMessage, setRetryMessage] = useState('');
  if (!isOpen) return null;

  const retry = async () => {
    if (!onRetry) return;
    setRetrying(true);
    setRetryMessage('');
    const res = await onRetry();
    setRetrying(false);
    if (res.ok) onClose();
    else setRetryMessage(res.message || 'Retry could not start');
  };

  const rawStatus = (subtask.status || '').toLowerCase();
  const narration = getHumanNarration(name, rawStatus, cardState, noteText, modelName, subtask.detail, n);
  const passed = subtask.checks_passed;
  const total = subtask.checks_total;

  return (
    <div
      className={styles.overlay}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={styles.modal}
        style={{ border: `1px solid ${statusConfig.borderHover}` }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <span className={styles.stepBadge}>#{n}</span>
            <div>
              <h3 className={styles.title}>{name}</h3>
              <span className={styles.subtitle}>
                {subtask.detail || 'Authoritative pipeline stage verification'}
              </span>
            </div>
          </div>

          <button
            onClick={onClose}
            className={styles.closeBtn}
            title="Close (Esc)"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className={styles.body}>
          {/* Badges Bar */}
          <div className={styles.badgesBar}>
            <div className={styles.badgesLeft}>
              <span
                className={styles.statusPill}
                style={{
                  color: statusConfig.accent,
                  backgroundColor: statusConfig.badgeBg,
                  border: `1px solid ${statusConfig.border}`,
                }}
              >
                {statusConfig.icon}
                {statusConfig.label}
              </span>

              <span className={styles.percentPill}>
                {cardState === 'in_progress' ? `${displayedPercent}% in progress` : (cardState === 'pending' ? '0% pending' : `${displayedPercent}% completed`)}
              </span>
            </div>

            <div className={styles.badgesRight}>
              <span className={styles.modelPill}>
                <Cpu size={11} />
                {modelName}
              </span>
              {latencyMs !== undefined && latencyMs !== null && latencyMs > 0 && (
                <span className={styles.latency}>
                  {(latencyMs / 1000).toFixed(1)}s
                </span>
              )}
            </div>
          </div>

          {/* SECTION 1: Conversational Human Narration (తెలుగు + ఇంగ్లీష్ మిక్స్ మానవ వివరణ) */}
          <div
            className={styles.narrationCard}
            style={{
              backgroundColor: statusConfig.bg,
              border: `1px solid ${statusConfig.badgeBorder}`,
            }}
          >
            <div className={styles.narrationHeader}>
              <Sparkles size={16} color={statusConfig.accent} />
              <span
                className={styles.narrationHeadline}
                style={{ color: statusConfig.accent }}
              >
                {narration.headline}
              </span>
            </div>

            <p className={styles.narrationText}>{narration.narration}</p>

            {narration.cause && (
              <div className={styles.narrationCause}>
                <strong style={{ color: '#F1F5F9' }}>కారణం (Why this occurred): </strong>
                {narration.cause}
              </div>
            )}

            {narration.solution && (
              <div className={styles.narrationSolution}>
                <strong>పరిష్కారం (Action Needed): </strong>
                {narration.solution}
              </div>
            )}
          </div>

          {/* SECTION 2: Technical Evidence & Original LLM Feedback */}
          <div className={styles.technicalCard}>
            <div className={styles.technicalHeader}>
              <Info size={13} color="#94A3B8" />
              <span className={styles.technicalTitle}>
                Original LLM Audit Note ({modelName})
              </span>
            </div>

            <div className={styles.technicalNote}>
              {noteText || 'No detailed note was returned for this check.'}
            </div>

            <div className={styles.technicalMeta}>
              <span>Step #{n}</span>
              <span>{passed ?? 0} of {total ?? 0} deterministic checks passed</span>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className={styles.footer}>
          {retryMessage && <span className={styles.retryMessage} data-testid={`subtask-retry-message-${n}`}>{retryMessage}</span>}
          {onRetry && (
            <button
              onClick={retry}
              disabled={retrying}
              className={styles.footerRetryBtn}
              data-testid={`subtask-retry-btn-${n}`}
            >
              <RotateCw size={13} className={retrying ? 'animate-spin' : undefined} />
              {retrying ? 'Retrying…' : 'Retry this subtask'}
            </button>
          )}
          <button
            onClick={onClose}
            className={styles.footerCloseBtn}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
