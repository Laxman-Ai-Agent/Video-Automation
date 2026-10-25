import React from 'react';

export const sceneTableStyle: React.CSSProperties = {
  width: '100%',
  tableLayout: 'fixed',
  borderCollapse: 'separate',
  borderSpacing: 0,
  border: '1px solid var(--border-card)',
  borderRadius: '10px',
  overflow: 'hidden',
  backgroundColor: 'var(--bg-elevated)',
};

export const sceneThStyle: React.CSSProperties = {
  padding: '10px 14px',
  textAlign: 'left',
  fontSize: '11px',
  fontWeight: 700,
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
  color: 'var(--text-muted)',
  backgroundColor: 'var(--bg-card)',
  borderBottom: '1px solid var(--border-card)',
};

export const sceneTdStyle: React.CSSProperties = {
  padding: '12px 14px',
  verticalAlign: 'middle',
  borderBottom: '1px solid var(--border-subtle)',
  overflow: 'hidden',
};

export const sceneRowStyle = (expanded: boolean): React.CSSProperties => ({
  cursor: 'pointer',
  userSelect: 'none',
  backgroundColor: expanded ? 'var(--bg-card-hover)' : 'transparent',
});
