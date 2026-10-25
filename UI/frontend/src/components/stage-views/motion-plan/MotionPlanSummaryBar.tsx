import React from 'react';
import { Sparkles, Check, Copy } from 'lucide-react';

export interface MotionPlanSummaryBarProps {
  motionPlanData: any;
  motionScenesList: any[];
  copiedAllMotion: boolean;
  handleCopyAllMotionPlanJson: (e?: React.MouseEvent) => void;
}

export const MotionPlanSummaryBar: React.FC<MotionPlanSummaryBarProps> = ({
  motionPlanData,
  motionScenesList,
  copiedAllMotion,
  handleCopyAllMotionPlanJson
}) => {
  return (
    <div style={{
      backgroundColor: 'var(--bg-elevated)',
      border: '1px solid var(--border-card)',
      borderRadius: '8px',
      padding: '14px 18px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: '12px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{
          width: '32px',
          height: '32px',
          borderRadius: '6px',
          backgroundColor: 'rgba(0, 216, 245, 0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--accent-cyan)'
        }}>
          <Sparkles size={16} />
        </div>
        <div>
          <div style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
            Motion Planning & Kinetic Synthesis
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Mode: <strong style={{ color: 'var(--accent-cyan)' }}>{['image', 'with-pictures', 'mixed'].includes(motionPlanData?.project?.mode) ? 'mixed (motion + media)' : (motionPlanData?.project?.mode || 'motion_only')}</strong>
            {motionPlanData?.project?.aspect_ratio && <> • Aspect: <strong>{motionPlanData.project.aspect_ratio}</strong></>}
            {motionPlanData?.project?.fps && <> • FPS: <strong>{motionPlanData.project.fps}</strong></>}
            {motionPlanData?.timing_policy?.pace && <> • Pace: <strong>{motionPlanData.timing_policy.pace}x</strong></>}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Motion Scenes</span>
          <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
            {motionScenesList.length}
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Timeline Window</span>
          <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
            {motionScenesList.length > 0 && motionScenesList[motionScenesList.length - 1].timing?.end
              ? `${Number(motionScenesList[motionScenesList.length - 1].timing.end).toFixed(1)}s`
              : '—'}
          </div>
        </div>

        <span style={{
          fontSize: '10.5px',
          fontFamily: 'var(--font-mono)',
          fontWeight: 700,
          backgroundColor: 'rgba(0, 216, 245, 0.12)',
          color: 'var(--accent-cyan)',
          padding: '3px 8px',
          borderRadius: '4px',
          border: '1px solid rgba(0, 216, 245, 0.25)'
        }}>
          motion_planning.json
        </span>

        <button
          onClick={handleCopyAllMotionPlanJson}
          data-testid="copy-all-motion-plan-json-btn"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 14px',
            backgroundColor: copiedAllMotion ? 'rgba(16, 185, 129, 0.15)' : 'rgba(0, 216, 245, 0.12)',
            border: copiedAllMotion ? '1px solid #10B981' : '1px solid rgba(0, 216, 245, 0.35)',
            borderRadius: '6px',
            color: copiedAllMotion ? '#10B981' : 'var(--accent-cyan)',
            fontSize: '11.5px',
            fontWeight: 700,
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
        >
          {copiedAllMotion ? <Check size={13} color="#10B981" /> : <Copy size={13} />}
          <span>{copiedAllMotion ? 'Copied Full Motion Plan JSON!' : 'Copy Full Motion Plan JSON'}</span>
        </button>
      </div>
    </div>
  );
};
