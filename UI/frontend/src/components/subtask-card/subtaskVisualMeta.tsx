import React from 'react';
import {
  FileAudio,
  FileSearch,
  Sliders,
  Languages,
  Mic,
  BookOpen,
  Target,
  GitCompare,
  AlignLeft,
  Clock,
  AudioLines,
  Gauge,
  ShieldCheck,
  Database,
  Film,
  PlaySquare,
  Activity,
  Sparkles,
} from 'lucide-react';

/**
 * Returns a sleek Lucide icon and concise friendly label for each subtask.
 * Ensures cards don't suffer from clumsy text truncation and have strong visual identity.
 */
export function getSubtaskVisualMeta(stepNum: number, name: string): { icon: React.ReactNode; shortLabel: string } {
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
