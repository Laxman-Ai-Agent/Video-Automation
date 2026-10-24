import React, { useEffect, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Clock, Loader2 } from 'lucide-react';
import { AnalysisSubtask, AnalysisSubtasks as Data, fetchAnalysisSubtasks } from '../services/api';

interface Props {
  projectId: string;
  isRunning: boolean;   // the page's own running flag: polling is fast while it runs, slow otherwise
  onFinished?: () => void;
}

const STATUS_LABEL: Record<AnalysisSubtask['status'], string> = { pending: 'Pending', running: 'Running', completed: 'Completed', failed: 'Failed' };
const STATUS_COLOR: Record<AnalysisSubtask['status'], string> = {
  pending: 'var(--text-muted)', running: 'var(--accent-cyan)', completed: 'var(--status-completed)', failed: 'var(--status-failed)'
};
const LLM_LABEL: Record<AnalysisSubtask['llm']['status'], string> = {
  none: 'No LLM check', pending: 'LLM check pending', running: 'LLM check running', completed: 'LLM check completed', failed: 'LLM check failed'
};

const Icon: React.FC<{ status: AnalysisSubtask['status'] }> = ({ status }) =>
  status === 'completed' ? <CheckCircle2 size={16} /> : status === 'failed' ? <AlertCircle size={16} /> : status === 'running' ? <Loader2 size={16} className="animate-spin" /> : <Clock size={16} />;

export const AnalysisSubtasks: React.FC<Props> = ({ projectId, isRunning, onFinished }) => {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState('');
  const running = isRunning || !!data?.running;

  useEffect(() => {
    let alive = true;
    const read = async () => {
      try {
        const d = await fetchAnalysisSubtasks(projectId);
        if (alive) { setData(d); setError(''); }
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    };
    void read();
    const timer = setInterval(read, running ? 1500 : 10000);
    return () => { alive = false; clearInterval(timer); };
  }, [projectId, running]);

  const wasRunning = useRef(false);
  useEffect(() => {
    if (data?.running) wasRunning.current = true;
    else if (wasRunning.current && data) { wasRunning.current = false; onFinished?.(); }   // the run ended: the page reads the finished artifact
  }, [data, onFinished]);

  return (
    <section data-testid="analysis-subtasks" aria-label="Audio Analysis subtasks" style={{
      backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: '8px', padding: '16px 18px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', gap: '12px' }}>
        <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>Audio Analysis subtasks</h4>
        {data && <span data-testid="analysis-overall-percent" style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>Overall {data.percent}%</span>}
      </div>
      {error && <div role="alert" style={{ fontSize: '12.5px', color: 'var(--status-failed)' }}>{error}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {data?.subtasks.map((t) => (
          <div key={t.id} data-testid={`analysis-subtask-${t.id}`} style={{
            border: `1px solid ${t.status === 'running' ? 'var(--accent-cyan)' : 'var(--border-subtle)'}`, borderRadius: '6px', padding: '10px 12px',
            backgroundColor: 'var(--bg-elevated)', display: 'flex', flexDirection: 'column', gap: '6px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                <span style={{ color: STATUS_COLOR[t.status], display: 'flex' }}><Icon status={t.status} /></span>
                {t.name}
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px', fontWeight: 700 }}>
                <span data-testid={`analysis-subtask-${t.id}-status`} style={{ color: STATUS_COLOR[t.status] }}>{STATUS_LABEL[t.status]}</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{t.percent === null ? '—' : `${Math.round(t.percent)}%`}</span>
              </span>
            </div>
            <div style={{ height: '4px', borderRadius: '2px', backgroundColor: 'var(--bg-card)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${t.percent ?? 0}%`, backgroundColor: STATUS_COLOR[t.status], transition: 'width 0.3s ease' }} />
            </div>
            <div data-testid={`analysis-subtask-${t.id}-llm`} style={{
              fontSize: '12px', color: t.llm.status === 'failed' ? 'var(--status-failed)' : t.llm.status === 'completed' ? 'var(--status-completed)' : 'var(--text-muted)'
            }}>
              {LLM_LABEL[t.llm.status]}{t.llm.detail ? ` · ${t.llm.detail}` : ''}
            </div>
            {t.status === 'failed' && t.message && <div style={{ fontSize: '12px', color: 'var(--status-failed)', wordBreak: 'break-word' }}>{t.message}</div>}
          </div>
        ))}
        {!data && !error && <span style={{ fontSize: '12.5px', color: 'var(--text-muted)' }}>Reading the subtasks…</span>}
      </div>
    </section>
  );
};
