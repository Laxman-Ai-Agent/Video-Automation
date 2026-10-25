import React from 'react';
import {
  CheckCircle2,
  Clock,
  Layers,
  XCircle
} from 'lucide-react';
import { CapabilityStatus } from '../../data/agentAboutData';

export const StatusBadge: React.FC<{ status: CapabilityStatus }> = ({ status }) => {
  let bg = 'rgba(140, 140, 140, 0.15)';
  let text = '#8C8C8C';
  let border = 'rgba(140, 140, 140, 0.3)';

  if (status === 'VERIFIED WORKING') {
    bg = 'rgba(82, 196, 26, 0.15)';
    text = '#52C41A';
    border = 'rgba(82, 196, 26, 0.35)';
  } else if (status === 'PARTIALLY IMPLEMENTED') {
    bg = 'rgba(250, 173, 20, 0.15)';
    text = '#FAAD14';
    border = 'rgba(250, 173, 20, 0.35)';
  } else if (status === 'NOT IMPLEMENTED') {
    bg = 'rgba(24, 144, 255, 0.15)';
    text = '#1890FF';
    border = 'rgba(24, 144, 255, 0.35)';
  } else if (status === 'NOT SUPPORTED') {
    bg = 'rgba(255, 77, 79, 0.15)';
    text = '#FF4D4F';
    border = 'rgba(255, 77, 79, 0.35)';
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 8px',
        borderRadius: '4px',
        fontSize: '10.5px',
        fontWeight: 700,
        fontFamily: 'var(--font-mono)',
        backgroundColor: bg,
        color: text,
        border: `1px solid ${border}`,
        letterSpacing: '0.3px',
        textTransform: 'uppercase'
      }}
    >
      {status === 'VERIFIED WORKING' && <CheckCircle2 size={11} />}
      {status === 'PARTIALLY IMPLEMENTED' && <Clock size={11} />}
      {status === 'NOT IMPLEMENTED' && <Layers size={11} />}
      {status === 'NOT SUPPORTED' && <XCircle size={11} />}
      {status}
    </span>
  );
};
