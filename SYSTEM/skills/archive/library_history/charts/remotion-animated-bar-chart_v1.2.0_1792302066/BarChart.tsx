import React from 'react';
import { spring, useCurrentFrame, useVideoConfig } from 'remotion';

export interface BarData { label: string; value: number; color?: string; }
export const BarChart: React.FC<{ data: BarData[] }> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({ frame, fps, config: { damping: 14, stiffness: 100 } });
  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end', height: 400 }}>
      {data.map((d, i) => (
        <div key={i} style={{ width: 60, height: `${d.value * progress}%`, backgroundColor: d.color || '#3b82f6', borderRadius: '8px 8px 0 0' }} />
      ))}
    </div>
  );
};
