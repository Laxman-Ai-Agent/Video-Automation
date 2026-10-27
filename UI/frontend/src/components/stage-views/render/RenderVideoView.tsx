import React, { useEffect, useState } from 'react';
import { Play, Download, X, Film, Settings, Info, Check, Loader2, RotateCcw, History, Gauge } from 'lucide-react';
import { API_BASE, fetchProject, fetchProjects, fetchRenderVideoState, stopStage } from '../../../services/api';
import styles from './RenderVideoView.module.css';

export interface RenderVideoViewProps {
  projectId: string;
  refreshKey?: string;                       // the stage status: everything is read again when it changes
  onRetryStage?: (stageId: string) => void;
}

// The phases of a render job in the order the renderer goes through them (VIDEO_ENGINE/stages/render_video.py), as steps of the progress card.
const STEPS = [
  { phase: 'validating', label: 'Check Approval' },
  { phase: 'rendering', label: 'Render Frames' },
  { phase: 'finalizing', label: 'Finalize' },
  { phase: 'verifying_output', label: 'Verify File' },
  { phase: 'publishing', label: 'Publish' },
  { phase: 'completed', label: 'Done' },
] as const;

const videoUrl = (pid: string, aspect: string, sha?: string) =>
  `${API_BASE}/projects/${pid}/video?aspect=${encodeURIComponent(aspect)}&preview=false${sha ? `&v=${sha.slice(0, 12)}` : ''}`;

const clock = (s?: number | null) => (s == null ? '-' : `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.round(s % 60)).padStart(2, '0')}`);
const megabytes = (b?: number | null) => (b == null ? '-' : `${(b / 1048576).toFixed(b < 10485760 ? 1 : 0)} MB`);
const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString('en-US', { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-');
const eta = (s?: number | null) => (s == null ? null : s >= 60 ? `${Math.floor(s / 60)} minutes ${Math.round(s % 60)} seconds` : `${Math.round(s)} seconds`);

interface PastRender { id: string; name: string; aspect: string; duration: number | null; size: number | null; created: string | null; current: boolean; sha?: string }

const isBusy = (st: any) => !!st && (st.running || ['rendering', 'validating', 'finalizing', 'verifying_output', 'publishing', 'cancel_requested'].includes(st.job?.status));

/** The Render Video page: the rendered video, the project and the render settings, the live progress of the render job, and the renders of the other projects. */
export const RenderVideoView: React.FC<RenderVideoViewProps> = ({ projectId, refreshKey, onRetryStage }) => {
  const [state, setState] = useState<any | null>(null);
  const [project, setProject] = useState<any | null>(null);
  const [past, setPast] = useState<PastRender[]>([]);
  const [stopping, setStopping] = useState(false);

  // The render state is read again every 3 s while a job runs.
  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    const load = async () => {
      const s = await fetchRenderVideoState(projectId);
      if (!alive) return;
      setState(s);
      if (isBusy(s)) timer = window.setTimeout(load, 3000);
    };
    load();
    return () => { alive = false; window.clearTimeout(timer); };
  }, [projectId, refreshKey]);

  useEffect(() => { fetchProject(projectId).then(setProject); }, [projectId]);

  useEffect(() => {
    let alive = true;
    (async () => {
      const projects = await fetchProjects();
      const rows = await Promise.all(projects.map(async (p: any): Promise<PastRender | null> => {
        const st = await fetchRenderVideoState(p.id);
        if (!st?.output?.exists) return null;
        const obs = st.report?.observed;
        return { id: p.id, name: p.name, aspect: st.aspect, duration: obs?.duration_seconds ?? st.expected?.duration_seconds ?? null, size: st.output.size_bytes, created: st.report?.created_at ?? null, current: !!st.output.current, sha: st.output.sha256 };
      }));
      if (alive) setPast(rows.filter((r): r is PastRender => r !== null).sort((a, b) => (b.created || '').localeCompare(a.created || '')));
    })();
    return () => { alive = false; };
  }, [refreshKey]);

  const aspect: string = state?.aspect || project?.aspect || '16:9';
  const portrait = aspect === '9:16';
  const exp = state?.expected;
  const obs = state?.report?.observed;
  const job = state?.job;
  const busy = isBusy(state);
  const hasVideo = !!state?.output?.exists;
  const phaseIdx = state?.status === 'completed' ? STEPS.length - 1 : Math.max(0, STEPS.findIndex(s => s.phase === job?.phase));
  const rendering = job?.phase === 'rendering';
  const percent = state?.status === 'completed' ? 100 : rendering ? Math.round(job?.render_percent ?? 0) : phaseIdx > 1 ? 100 : 0;
  const finished = state?.status === 'completed' && !busy;

  const cancel = async () => { setStopping(true); await stopStage(projectId, 'render'); setStopping(false); setState(await fetchRenderVideoState(projectId)); };

  return (
    <div className={styles.page} data-testid="render-video-view">
      <div className={styles.top}>
        <section className={styles.card} data-testid="render-preview-card">
          <header className={styles.cardHead}>
            <span className={styles.icon}><Film size={18} /></span>
            <div className={styles.headText}><h3>Video Preview</h3><p>Final rendered output preview</p></div>
            <span className={styles.badge}>{aspect}<br />{exp ? `${exp.width} x ${exp.height}` : '-'}</span>
          </header>
          <div className={`${styles.stage} ${portrait ? styles.stagePortrait : ''}`}>
            {hasVideo
              ? <video key={state.output.sha256} className={styles.video} src={videoUrl(projectId, aspect, state.output.sha256)} controls preload="metadata" data-testid="render-video-player" />
              : <div className={styles.empty}><Film size={34} /><div>{busy ? 'The video is being rendered...' : 'No rendered video yet.'}</div></div>}
          </div>
          {hasVideo && !state.output.current && <div className={styles.note}>This file belongs to an older timeline; render again to match the approved one.</div>}
        </section>

        <div className={styles.side}>
          <section className={styles.card} data-testid="render-project-card">
            <header className={styles.cardHead}>
              <span className={styles.icon}><Info size={18} /></span>
              <div className={styles.headText}><h3>Project Details</h3></div>
            </header>
            <dl className={styles.facts}>
              <dt>Title</dt><dd>{project?.name || projectId}</dd>
              <dt>Duration</dt><dd>{exp ? `${clock(exp.duration_seconds)} (${Math.round(exp.duration_seconds)} seconds)` : '-'}</dd>
              <dt>Aspect Ratio</dt><dd>{exp ? `${aspect} (${exp.width} x ${exp.height})` : aspect}</dd>
              <dt>Frames</dt><dd>{exp ? `${exp.frames} at ${exp.fps} fps` : '-'}</dd>
              <dt>Created On</dt><dd>{when(project?.created)}</dd>
            </dl>
          </section>

          <section className={styles.card} data-testid="render-settings-card">
            <header className={styles.cardHead}>
              <span className={styles.icon}><Settings size={18} /></span>
              <div className={styles.headText}><h3>Render Settings</h3></div>
            </header>
            <dl className={styles.facts}>
              <dt>Resolution</dt><dd>{exp ? `${exp.width} x ${exp.height}` : '-'}</dd>
              <dt>Frame Rate</dt><dd>{exp ? `${exp.fps} FPS` : '-'}</dd>
              <dt>Video Codec</dt><dd>{(obs?.video_codec || exp?.codec || 'h264').toUpperCase().replace('H264', 'H.264')} ({(exp?.container || 'mp4').toUpperCase()})</dd>
              <dt>Audio</dt><dd>{obs ? `${obs.audio_channels === 2 ? 'Stereo' : `${obs.audio_channels} ch`}, ${Math.round(obs.audio_sample_rate / 1000)} kHz` : 'Stereo, 48 kHz'}</dd>
              <dt>Visual Style</dt><dd>Motion Graphics (custom code)</dd>
              <dt>Renderer</dt><dd>{state?.report?.renderer ? `${state.report.renderer.name} ${state.report.renderer.version}` : 'Remotion'}</dd>
            </dl>
          </section>
        </div>
      </div>

      <section className={styles.card} data-testid="render-progress-card">
        <header className={styles.cardHead}>
          <span className={styles.icon}><Gauge size={18} /></span>
          <div className={styles.headText}><h3>Render Progress</h3><p>{busy ? 'Video rendering in progress...' : finished ? 'The last render finished.' : state?.status === 'failed' ? 'The last render failed.' : 'No render is running.'}</p></div>
        </header>
        <div className={styles.progress}>
          <ol className={styles.steps}>
            {STEPS.map((s, i) => {
              const done = i < phaseIdx || finished;
              const current = !done && i === phaseIdx && busy;
              return (
                <li key={s.phase} className={`${styles.step} ${done ? styles.stepDone : ''} ${current ? styles.stepNow : ''}`} data-testid={`render-step-${s.phase}`}>
                  <span className={styles.dot}>{done ? <Check size={16} /> : current ? <Loader2 size={16} className={styles.spin} /> : <span className={styles.dotEmpty} />}</span>
                  <span className={styles.stepLabel}>{s.label}</span>
                  <span className={styles.stepPct}>{done ? '100%' : current ? (rendering ? `${percent}%` : '...') : '0%'}</span>
                </li>
              );
            })}
          </ol>
          <div className={styles.meter}>
            <div className={styles.big} data-testid="render-percent">{percent}%</div>
            <div className={styles.small}>{busy ? (rendering ? `Rendering frame ${job?.frames_done ?? 0} of ${job?.frames_total ?? '?'}` : 'Working...') : finished ? 'Render complete' : 'Idle'}</div>
            <div className={styles.bar}><div className={styles.barFill} style={{ width: `${percent}%` }} /></div>
            {busy && eta(job?.eta_s) && <div className={styles.small}>Estimated time remaining: {eta(job?.eta_s)}</div>}
            {state?.last_attempt_failed && !busy && <div className={styles.error}>{state.last_attempt?.error || 'The last attempt failed.'}</div>}
          </div>
          {busy
            ? <button className={styles.cancel} onClick={cancel} disabled={stopping} data-testid="render-cancel-btn"><X size={16} /> Cancel Render</button>
            : <button className={styles.again} onClick={() => onRetryStage?.('render')} disabled={!onRetryStage} data-testid="render-again-btn"><RotateCcw size={16} /> Render Again</button>}
        </div>
      </section>

      <section className={styles.card} data-testid="render-previous-card">
        <header className={styles.cardHead}>
          <span className={styles.icon}><History size={18} /></span>
          <div className={styles.headText}><h3>Previous Renders</h3><p>Here are your completed videos</p></div>
        </header>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead><tr><th>#</th><th>Title</th><th>Duration</th><th>Aspect Ratio</th><th>Size</th><th>Status</th><th>Created On</th><th>Actions</th></tr></thead>
            <tbody>
              {past.map((r, i) => (
                <tr key={r.id} data-testid={`render-past-${r.id}`}>
                  <td>{i + 1}</td>
                  <td className={styles.titleCell}>{r.name}</td>
                  <td>{clock(r.duration)}</td>
                  <td>{r.aspect}</td>
                  <td>{megabytes(r.size)}</td>
                  <td><span className={r.current ? styles.ok : styles.old}>{r.current ? 'Completed' : 'Older timeline'}</span></td>
                  <td>{when(r.created)}</td>
                  <td className={styles.actions}>
                    <a className={styles.play} href={videoUrl(r.id, r.aspect, r.sha)} target="_blank" rel="noreferrer"><Play size={14} /> Play</a>
                    <a className={styles.download} href={videoUrl(r.id, r.aspect, r.sha)} download={`${r.id}.mp4`}><Download size={14} /> Download</a>
                  </td>
                </tr>
              ))}
              {past.length === 0 && <tr><td colSpan={8} className={styles.none}>No rendered videos yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};
