import React, { useEffect, useState } from 'react';
import { CheckCircle2, Loader2, AlertTriangle, Wrench, ScrollText } from 'lucide-react';
import { fetchWorkLog, type WorkLogEntry } from '../services/api';

const STATUS: Record<WorkLogEntry['status'], { label: string; color: string; Icon: React.ElementType }> = {
  doing: { label: 'చేస్తున్నాను', color: '#38BDF8', Icon: Loader2 },
  done: { label: 'పూర్తయింది', color: '#34D399', Icon: CheckCircle2 },
  problem: { label: 'సమస్య దొరికింది', color: '#FBBF24', Icon: AlertTriangle },
  fixed: { label: 'సరిచేశాను', color: '#A78BFA', Icon: Wrench },
};

const clock = (iso: string) => new Date(iso).toLocaleTimeString('te-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

export const WorkLogPage: React.FC = () => {
  const [entries, setEntries] = useState<WorkLogEntry[]>([]);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const got = await fetchWorkLog();
      if (!alive) return;
      setOnline(got !== null);
      if (got) setEntries(got);
    };
    load();
    const timer = setInterval(load, 2000);
    return () => { alive = false; clearInterval(timer); };
  }, []);

  const newest = [...entries].reverse();
  const now = newest[0]?.status === 'doing' ? newest[0] : null;      // the last line says what is being done right now

  return (
    <div style={{ padding: '32px', maxWidth: '1000px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <ScrollText size={24} /> Work Log
      </h2>
      <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: '6px 0 20px' }}>
        నేను చేసే ప్రతి పని ఇక్కడ live గా కనిపిస్తుంది (ప్రతి 2 సెకన్లకు కొత్తది వస్తుంది). {online ? '' : '— server కి కనెక్ట్ కాలేదు.'}
      </p>

      <div style={{ padding: '16px 20px', borderRadius: 'var(--radius-sm)', marginBottom: '20px', border: '1px solid var(--border-card)', backgroundColor: 'var(--bg-card)' }}>
        <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.5px' }}>ఇప్పుడు</div>
        <div style={{ fontSize: '17px', fontWeight: 700, color: now ? '#38BDF8' : 'var(--text-secondary)', marginTop: '4px' }}>
          {now ? now.title : 'ప్రస్తుతం ఏ పనీ జరగడం లేదు'}
        </div>
        {now && <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>{now.detail}</div>}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }} data-testid="work-log-list">
        {newest.length === 0 && <div style={{ color: 'var(--text-muted)' }}>ఇంకా ఏ పనీ నమోదు కాలేదు.</div>}
        {newest.map((e) => {
          const s = STATUS[e.status] ?? STATUS.done;
          return (
            <div key={e.id} style={{ display: 'flex', gap: '12px', padding: '12px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-card)', borderLeft: `4px solid ${s.color}`, backgroundColor: 'var(--bg-card)' }}>
              <s.Icon size={18} color={s.color} style={{ flexShrink: 0, marginTop: '2px' }} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{e.title}</span>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{clock(e.time)}</span>
                </div>
                <div style={{ fontSize: '12px', fontWeight: 600, color: s.color, margin: '2px 0' }}>{s.label}</div>
                {e.detail && <div style={{ fontSize: '13px', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>{e.detail}</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
