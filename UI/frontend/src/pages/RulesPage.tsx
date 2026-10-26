import React, { useEffect, useMemo, useState } from 'react';
import { ListChecks, ChevronDown, ChevronRight } from 'lucide-react';
import { fetchRules, switchRules, type RulesView, type RuleRow } from '../services/api';
import styles from './RulesPage.module.css';

const SEVERITY_CLASS: Record<string, string> = { blocker: styles.sevBlocker, error: styles.sevError, warning: styles.sevWarning, review: styles.sevReview };

/** Every deterministic rule of the stages with a switch: OFF = the stage never evaluates it, so it cannot block or warn. The stage's LLM reviewer is told which rules are off. */
export const RulesPage: React.FC = () => {
  const [view, setView] = useState<RulesView | null>(null);
  const [online, setOnline] = useState(true);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [onlyOff, setOnlyOff] = useState(false);
  const [closed, setClosed] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let alive = true;
    fetchRules().then((v) => {
      if (!alive) return;
      setOnline(v !== null);
      if (v) setView(v);
    });
    return () => { alive = false; };
  }, []);

  const apply = async (body: { on: boolean; stage?: string; rule?: string }) => {
    setBusy(true);
    const next = await switchRules(body);
    setBusy(false);
    if (next) setView(next);
  };

  const q = query.trim().toLowerCase();
  const stages = useMemo(() => {
    const match = (r: RuleRow) => (!onlyOff || !r.on) && (!q || `${r.rule} ${r.says}`.toLowerCase().includes(q));
    return (view?.stages || []).map((s) => ({ ...s, shown: s.rules.filter(match) })).filter((s) => s.shown.length > 0);
  }, [view, q, onlyOff]);

  return (
    <div className={styles.container} data-testid="rules-page">
      <h2 className={styles.title}><ListChecks size={24} /> Rules</h2>
      <p className={styles.intro}>
        ప్రతి స్టేజ్ తనిఖీ చేసే rules ఇవి. ఒక rule ని OFF చేస్తే ఆ స్టేజ్ దాన్ని అస్సలు చూడదు: అది పని ఆపదు, వార్నింగ్ ఇవ్వదు. ఆ స్టేజ్ LLM review కి "ఈ rule లను యూజర్ ఆపారు" అని చెప్తుంది.
        మార్పు తరువాత run అయ్యే స్టేజ్‌ల నుంచి వర్తిస్తుంది.{online ? '' : ' — server కి కనెక్ట్ కాలేదు.'}
      </p>
      <div className={styles.bar}>
        <span className={styles.summary} data-testid="rules-summary">
          {view ? <>{view.total} rules · <span className={view.off ? styles.summaryOff : undefined}>{view.off} OFF</span></> : 'loading…'}
        </span>
        <input className={styles.search} placeholder="Search rules…" value={query} onChange={(e) => setQuery(e.target.value)} data-testid="rules-search" />
        <button className={`${styles.pill} ${onlyOff ? styles.pillActive : ''}`} onClick={() => setOnlyOff(!onlyOff)} data-testid="rules-only-off">Only OFF</button>
        <button className={styles.pill} disabled={busy || !view?.off} onClick={() => apply({ on: true })} data-testid="rules-all-on">Turn all ON</button>
      </div>
      {view && stages.length === 0 && <div className={styles.empty}>No rule matches.</div>}
      {stages.map((s) => (
        <section key={s.stage} className={styles.stage} data-testid={`rules-stage-${s.stage}`}>
          <div className={styles.stageHead} onClick={() => setClosed({ ...closed, [s.stage]: !closed[s.stage] })}>
            {closed[s.stage] ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
            <span className={styles.stageName}>{s.label}</span>
            <span className={styles.stageCount}>{s.total} rules{s.off ? <> · <span className={styles.stageOff}>{s.off} OFF</span></> : null}</span>
            <button className={styles.small} disabled={busy} onClick={(e) => { e.stopPropagation(); apply({ on: false, stage: s.stage }); }} data-testid={`rules-stage-off-${s.stage}`}>All OFF</button>
            <button className={styles.small} disabled={busy} onClick={(e) => { e.stopPropagation(); apply({ on: true, stage: s.stage }); }} data-testid={`rules-stage-on-${s.stage}`}>All ON</button>
          </div>
          {!closed[s.stage] && s.shown.map((r) => (
            <div key={r.rule} className={`${styles.row} ${r.on ? '' : styles.rowOff}`} data-testid={`rule-row-${s.stage}-${r.rule}`}>
              <span className={styles.name}>{r.rule}</span>
              <span className={styles.says}>{r.says}</span>
              <span className={`${styles.sev} ${SEVERITY_CLASS[r.severity] || ''}`}>{r.severity || '—'}</span>
              <button
                role="switch"
                aria-checked={r.on}
                aria-label={`${r.rule} ${r.on ? 'ON' : 'OFF'}`}
                className={styles.switch}
                disabled={busy}
                onClick={() => apply({ on: !r.on, stage: s.stage, rule: r.rule })}
                data-testid={`rule-switch-${s.stage}-${r.rule}`}
              >
                <span className={styles.knob} />
              </button>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
};
