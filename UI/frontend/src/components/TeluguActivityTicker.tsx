import React from 'react';
import { Activity, ShieldCheck } from 'lucide-react';

interface TeluguActivityTickerProps {
  teluguMessage: string;
  stageName?: string;
}

export const TeluguActivityTicker: React.FC<TeluguActivityTickerProps> = ({
  teluguMessage,
  stageName
}) => {
  if (!teluguMessage) return null;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      padding: '10px 18px',
      backgroundColor: 'rgba(0, 216, 245, 0.08)',
      border: '1px solid rgba(0, 216, 245, 0.25)',
      borderRadius: 'var(--radius-full)',
      boxShadow: '0 2px 12px rgba(0, 216, 245, 0.1)',
      maxWidth: '100%',
      overflow: 'hidden'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        color: 'var(--accent-cyan)',
        fontWeight: 700,
        fontSize: '12px',
        textTransform: 'uppercase',
        flexShrink: 0
      }}>
        <Activity size={14} className="animate-pulse" />
        <span>Telugu Live:</span>
      </div>

      <div style={{
        fontSize: '13.5px',
        fontWeight: 600,
        color: 'var(--text-primary)',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }}>
        {teluguMessage}
      </div>

      {stageName && (
        <div style={{
          fontSize: '11px',
          fontWeight: 700,
          color: 'var(--text-muted)',
          backgroundColor: 'var(--bg-card)',
          padding: '2px 8px',
          borderRadius: 'var(--radius-sm)',
          flexShrink: 0
        }}>
          {stageName}
        </div>
      )}
    </div>
  );
};
