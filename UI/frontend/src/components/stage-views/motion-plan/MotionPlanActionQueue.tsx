import React from 'react';
import { Film } from 'lucide-react';

export interface MotionPlanActionQueueProps {
  sequence: any[];
}

export const MotionPlanActionQueue: React.FC<MotionPlanActionQueueProps> = ({ sequence }) => {
  if (!sequence || sequence.length === 0) return null;

  return (
    <div style={{
      backgroundColor: 'var(--bg-card)',
      padding: '14px',
      borderRadius: '8px',
      border: '1px solid var(--border-card)',
      display: 'flex',
      flexDirection: 'column',
      gap: '10px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Film size={13} color="var(--accent-cyan)" />
          <span style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Kinetic Action Sequence ({sequence.length} Timed Events)
          </span>
        </div>
        <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
          Chronological Animation Queue
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {sequence.map((act: any, aIdx: number) => {
          const phaseColors: Record<string, { bg: string; text: string }> = {
            establish: { bg: 'rgba(59, 130, 246, 0.15)', text: '#60A5FA' },
            enter: { bg: 'rgba(16, 185, 129, 0.15)', text: '#34D399' },
            sustain: { bg: 'rgba(245, 158, 11, 0.15)', text: '#FBBF24' },
            exit: { bg: 'rgba(239, 68, 68, 0.15)', text: '#F87171' }
          };
          const pColor = phaseColors[act.phase] || { bg: 'rgba(255, 255, 255, 0.08)', text: '#FFFFFF' };

          return (
            <div
              key={act.action_id || aIdx}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                backgroundColor: 'var(--bg-elevated)',
                padding: '8px 12px',
                borderRadius: '4px',
                borderLeft: `3px solid ${pColor.text}`,
                flexWrap: 'wrap',
                gap: '8px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                <span style={{
                  fontSize: '10px',
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  backgroundColor: pColor.bg,
                  color: pColor.text,
                  padding: '2px 6px',
                  borderRadius: '3px'
                }}>
                  {act.phase}
                </span>

                <span style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--accent-cyan)',
                  backgroundColor: 'rgba(0, 216, 245, 0.1)',
                  padding: '2px 6px',
                  borderRadius: '3px'
                }}>
                  {act.start?.toFixed(2)}s - {act.end?.toFixed(2)}s ({act.start_frame}-{act.end_frame}f)
                </span>

                <span style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {act.registry?.label || act.preset || act.action_id}
                </span>

                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  ➔ Target: <strong style={{ color: 'var(--text-primary)' }}>{act.target}</strong>
                </span>
              </div>

              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                {act.registry?.category && (
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)', backgroundColor: 'rgba(255, 255, 255, 0.05)', padding: '1px 5px', borderRadius: '3px' }}>
                    {act.registry.category}
                  </span>
                )}
                {act.depends_on && act.depends_on.length > 0 ? (
                  <span style={{ fontSize: '10px', color: '#FBBF24', backgroundColor: 'rgba(245, 158, 11, 0.1)', padding: '1px 5px', borderRadius: '3px' }}>
                    deps: {act.depends_on.join(', ')}
                  </span>
                ) : (
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>independent</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
