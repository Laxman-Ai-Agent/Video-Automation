import React from 'react';
import { Compass, Sparkles } from 'lucide-react';

export interface MotionPlanTransformationGridProps {
  scene: any;
  isFullPage?: boolean;
}

export const MotionPlanTransformationGrid: React.FC<MotionPlanTransformationGridProps> = ({
  scene,
  isFullPage = false
}) => {
  const t0 = scene.timing?.start ?? 0;
  const t1 = scene.timing?.end ?? 0;
  const duration = Math.max(0, t1 - t0);
  const startFrame = scene.timing?.start_frame ?? 0;
  const endFrame = scene.timing?.end_frame ?? 0;
  const gapAfter = scene.timing?.gap_after_seconds;

  const teluguNarration = scene.visual_scene_data?.narration?.text || scene.segmentation_data?.llm_transcript || scene.segmentation_data?.transcript || '—';
  const englishNarration = scene.visual_scene_data?.narration?.text_en || scene.motion_intent?.takeaway || '—';

  const intent = scene.motion_intent || {};
  const mpScene = scene.motion_plan_scene || {};
  const graphics: any[] = mpScene.graphics || [];

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: isFullPage ? '1fr 1fr' : '1fr',
      gap: '14px'
    }}>
      {/* COLUMN 1: BEFORE — Input Visual Directives & Script */}
      <div style={{
        backgroundColor: 'var(--bg-card)',
        border: '1px solid var(--border-card)',
        borderRadius: '8px',
        padding: '14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Compass size={13} color="var(--accent-cyan)" />
            <span style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              BEFORE: Visual Directives & Script
            </span>
          </div>
          <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            From Visual Planning
          </span>
        </div>

        {/* Telugu Spoken Narration (Preserved) */}
        <div>
          <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
            Spoken Narration (Telugu Script Preserved)
          </div>
          <div style={{
            fontSize: '14px',
            lineHeight: 1.6,
            color: 'var(--text-primary)',
            backgroundColor: 'var(--bg-elevated)',
            padding: '10px 12px',
            borderRadius: '6px',
            border: '1px solid var(--border-subtle)',
            fontFamily: 'system-ui, -apple-system, sans-serif'
          }}>
            {teluguNarration}
          </div>
        </div>

        {/* English Translation */}
        <div>
          <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
            English Narration (Core Meaning)
          </div>
          <div style={{
            fontSize: '13px',
            fontStyle: 'italic',
            lineHeight: 1.5,
            color: 'var(--text-secondary)',
            backgroundColor: 'var(--bg-elevated)',
            padding: '8px 12px',
            borderRadius: '6px',
            border: '1px solid var(--border-subtle)'
          }}>
            "{englishNarration}"
          </div>
        </div>

        {/* Visual Concept Directives */}
        {(scene.visual_scene_data?.visual_concept?.description || scene.visual_scene_data?.scene_objective?.core_meaning) && (
          <div>
            <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
              Planned Visual Subject & Concept
            </div>
            <div style={{
              fontSize: '12.5px',
              color: 'var(--text-primary)',
              backgroundColor: 'var(--bg-elevated)',
              padding: '8px 12px',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle)',
              lineHeight: 1.4
            }}>
              {scene.visual_scene_data?.visual_concept?.description || scene.visual_scene_data?.scene_objective?.core_meaning}
            </div>
          </div>
        )}

        {/* Attention Goal & Hints from Visual Plan */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr',
          gap: '8px',
          backgroundColor: 'rgba(255, 255, 255, 0.02)',
          padding: '8px 10px',
          borderRadius: '6px'
        }}>
          {intent.hints && intent.hints.length > 0 && (
            <div>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Visual Motion Hints:</span>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
                {intent.hints.map((h: string, hIdx: number) => (
                  <span key={hIdx} style={{
                    fontSize: '10.5px',
                    backgroundColor: 'rgba(0, 216, 245, 0.1)',
                    color: 'var(--accent-cyan)',
                    padding: '1px 6px',
                    borderRadius: '3px',
                    fontFamily: 'var(--font-mono)'
                  }}>
                    {h}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div>
            <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Audio Window:</span>
            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {t0.toFixed(2)}s → {t1.toFixed(2)}s ({duration.toFixed(2)}s)
            </div>
          </div>
        </div>
      </div>

      {/* COLUMN 2: AFTER — Motion Planning Synthesis */}
      <div style={{
        backgroundColor: 'var(--bg-card)',
        border: '1px solid rgba(0, 216, 245, 0.3)',
        borderRadius: '8px',
        padding: '14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        boxShadow: 'inset 0 0 20px rgba(0, 216, 245, 0.03)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(0, 216, 245, 0.15)', paddingBottom: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={13} color="var(--accent-cyan)" />
            <span style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              AFTER: Motion Planning Synthesis
            </span>
          </div>
          <span style={{
            fontSize: '10px',
            fontWeight: 700,
            backgroundColor: 'rgba(0, 216, 245, 0.15)',
            color: 'var(--accent-cyan)',
            padding: '2px 8px',
            borderRadius: '10px',
            fontFamily: 'var(--font-mono)'
          }}>
            Kinetic Choreography
          </span>
        </div>

        {/* Motion Intent */}
        <div>
          <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase', marginBottom: '4px' }}>
            Motion Intent & Focus
          </div>
          <div style={{
            fontSize: '13px',
            lineHeight: 1.5,
            color: 'var(--text-primary)',
            backgroundColor: 'rgba(0, 216, 245, 0.04)',
            padding: '10px 12px',
            borderRadius: '6px',
            border: '1px solid rgba(0, 216, 245, 0.15)',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px'
          }}>
            <div>
              <strong style={{ color: 'var(--accent-cyan)' }}>Goal:</strong> {intent.attention_goal || 'Ignite core visual element'}
            </div>
            {intent.takeaway && (
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                <strong style={{ color: 'var(--text-primary)' }}>Takeaway:</strong> {intent.takeaway}
              </div>
            )}
            <div style={{ display: 'flex', gap: '8px', marginTop: '4px', fontSize: '11px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Mood: <strong style={{ color: 'var(--text-primary)' }}>{intent.mood || 'majestic, awe'}</strong></span>
              <span style={{ color: 'var(--text-muted)' }}>• Intensity: <strong style={{ color: '#FBBF24' }}>{intent.intensity || 'standard'}</strong></span>
            </div>
          </div>
        </div>

        {/* Kinetic Graphics */}
        {graphics.length > 0 && (
          <div>
            <div style={{ fontSize: '10.5px', fontWeight: 700, color: '#60A5FA', textTransform: 'uppercase', marginBottom: '4px' }}>
              Kinetic Graphics & Accents ({graphics.length})
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {graphics.map((g: any, gIdx: number) => (
                <div
                  key={gIdx}
                  style={{
                    backgroundColor: 'var(--bg-elevated)',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    border: '1px solid rgba(59, 130, 246, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '8px'
                  }}
                >
                  <div>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#93C5FD', fontFamily: 'var(--font-mono)' }}>
                      {g.preset}
                    </span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '8px' }}>
                      {g.why || (g.atmosphere ? 'Atmosphere' : 'Placed Graphic')}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '6px', fontSize: '10.5px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    <span>Speed: <strong style={{ color: 'var(--text-primary)' }}>{g.speed}x</strong></span>
                    <span>Start: <strong style={{ color: 'var(--text-primary)' }}>{g.start}s</strong></span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Frame Precision & Timing */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '6px',
          borderTop: '1px solid rgba(255, 255, 255, 0.05)',
          paddingTop: '6px'
        }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Frames: <strong style={{ color: '#FFFFFF' }}>{startFrame} → {endFrame}f</strong> ({endFrame - startFrame} frames)
          </span>
          {gapAfter !== undefined && (
            <span style={{
              fontSize: '10.5px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--accent-cyan)',
              backgroundColor: 'rgba(0, 216, 245, 0.08)',
              padding: '2px 6px',
              borderRadius: '4px'
            }}>
              Gap Pause: {gapAfter}s
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
