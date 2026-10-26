import React, { useCallback, useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Cpu } from 'lucide-react';
import {
  LlmAutoResult,
  LlmDetected,
  LlmSettings,
  autoConnectLlm,
  detectLlm,
  fetchLlmSettings,
  saveLlmSettings,
  testLlmConnection
} from '../services/api';

interface LlmPageProps {
  onChanged: () => void;   // the header pill re-reads the connection
  onBusyChange: (connecting: boolean) => void;   // the header pill blinks only while a connection is being tried
}

type Busy = 'auto' | 'recheck' | 'test' | 'save' | null;
type Notice = { area: 'status' | 'auto' | 'manual'; ok: boolean; text: string };

const URL_PROVIDERS = ['custom', 'ollama', 'openai'];   // providers whose endpoint can be changed

const card: React.CSSProperties = {
  backgroundColor: 'var(--bg-card)',
  border: '1px solid var(--border-card)',
  borderRadius: 'var(--radius-lg)',
  padding: '20px 22px',
  boxShadow: 'var(--shadow-card)'
};
const label: React.CSSProperties = { display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '6px' };
const field: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  padding: '9px 12px',
  borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-subtle)',
  backgroundColor: 'var(--bg-elevated)',
  color: 'var(--text-primary)',
  fontSize: '13px'
};
const button = (primary: boolean, disabled: boolean): React.CSSProperties => ({
  padding: '9px 18px',
  borderRadius: 'var(--radius-full)',
  fontSize: '13px',
  fontWeight: 700,
  cursor: disabled ? 'not-allowed' : 'pointer',
  opacity: disabled ? 0.55 : 1,
  border: primary ? 'none' : '1px solid var(--border-subtle)',
  backgroundColor: primary ? 'var(--accent-cyan)' : 'transparent',
  color: primary ? '#060D1A' : 'var(--text-primary)'
});
const heading: React.CSSProperties = { fontSize: '16px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 };
const hint: React.CSSProperties = { fontSize: '12.5px', color: 'var(--text-muted)', margin: '4px 0 14px' };

const NoticeLine: React.FC<{ notice: Notice | null; area: Notice['area'] }> = ({ notice, area }) => {
  if (!notice || notice.area !== area) return null;
  return (
    <div
      role="status"
      style={{
        display: 'flex', gap: '8px', alignItems: 'flex-start', marginTop: '12px', fontSize: '13px', lineHeight: 1.45,
        color: notice.ok ? 'var(--status-completed)' : 'var(--status-failed)'
      }}
    >
      {notice.ok ? <CheckCircle2 size={16} style={{ flexShrink: 0, marginTop: '2px' }} /> : <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />}
      <span style={{ wordBreak: 'break-word' }}>{notice.text}</span>
    </div>
  );
};

export const LlmPage: React.FC<LlmPageProps> = ({ onChanged, onBusyChange }) => {
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [detected, setDetected] = useState<LlmDetected[] | null>(null);
  const [loadError, setLoadError] = useState('');
  const [auto, setAuto] = useState<LlmAutoResult | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');

  const fillForm = (s: LlmSettings) => {
    setProvider(s.active_provider);
    setModel(s.active_model);
    setBaseUrl(URL_PROVIDERS.includes(s.active_provider) ? s.base_url : '');
    setApiKey('');
  };

  const load = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([fetchLlmSettings(), detectLlm()]);
      setSettings(s);
      setDetected(d.options);
      fillForm(s);
      setLoadError('');
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    onBusyChange(busy !== null);
    return () => onBusyChange(false);
  }, [busy, onBusyChange]);

  const run = async (kind: Exclude<Busy, null>, area: Notice['area'], job: () => Promise<void>) => {
    setBusy(kind);
    setNotice(null);
    try {
      await job();
    } catch (e) {
      setNotice({ area, ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(null);
    }
  };

  const info = settings?.available_providers.find((p) => p.id === provider);
  const showUrl = URL_PROVIDERS.includes(provider);
  const keySaved = !!settings?.has_api_key && provider === settings.active_provider;
  const missing = !info
    ? 'Choose a provider.'
    : info.needs_key && !apiKey.trim() && !keySaved
      ? 'Enter the API key for this provider.'
      : provider === 'custom' && !baseUrl.trim()
        ? 'Enter the endpoint URL of the custom provider.'
        : '';
  const form = () => ({
    provider,
    model: model.trim() || info?.default_model,
    api_key: apiKey.trim() || undefined,
    base_url: showUrl ? baseUrl.trim() : ''
  });

  const connectAutomatically = () => run('auto', 'auto', async () => {
    setAuto(null);
    setAuto(await autoConnectLlm());
    await load();
    onChanged();
  });

  const recheck = () => run('recheck', 'status', async () => {
    const r = await testLlmConnection({});
    setNotice({ area: 'status', ok: r.ok, text: r.message });
    await load();
    onChanged();
  });

  const testOnly = () => run('test', 'manual', async () => {
    const r = await testLlmConnection(form());
    setNotice({ area: 'manual', ok: r.ok, text: r.message });
  });

  const saveAndConnect = () => run('save', 'manual', async () => {
    await saveLlmSettings(form());
    const r = await testLlmConnection({});
    setNotice({ area: 'manual', ok: r.ok, text: r.ok ? `Saved and connected. ${r.message}` : `Saved, but the connection failed: ${r.message}` });
    await load();
    onChanged();
  });

  const changeProvider = (id: string) => {
    const next = settings?.available_providers.find((p) => p.id === id);
    setProvider(id);
    setModel(next?.default_model ?? '');
    setBaseUrl('');
    setApiKey('');
    setNotice(null);
  };

  const status = settings?.connection_status;
  const statusText = status === 'active' ? 'Connected' : status === 'offline' ? 'Not connected' : 'Not checked yet';
  const statusColor = status === 'active' ? 'var(--status-completed)' : status === 'offline' ? 'var(--status-failed)' : 'var(--text-muted)';

  return (
    <div data-testid="llm-page" style={{ padding: '32px', maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div>
        <h2 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>LLM Connection</h2>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
          The pipeline stages (planning, motion code, reviews) need a language model. Connect one automatically, or fill in the details yourself.
        </p>
      </div>

      {loadError && (
        <div role="alert" style={{ ...card, color: 'var(--status-failed)', fontSize: '13px' }}>
          Could not read the LLM settings from the backend: {loadError}
        </div>
      )}

      {/* Current connection */}
      <section style={card} aria-label="Current connection">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Cpu size={22} color={statusColor} />
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span data-testid="llm-status-text" style={{ fontSize: '15px', fontWeight: 800, color: statusColor }}>{statusText}</span>
                {settings?.model_locked && (
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    padding: '2px 8px',
                    borderRadius: '9999px',
                    backgroundColor: 'rgba(59, 130, 246, 0.15)',
                    color: '#60A5FA',
                    border: '1px solid rgba(59, 130, 246, 0.3)'
                  }}>
                    Model Lock Active
                  </span>
                )}
                {settings?.auth_method_name && (
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    padding: '2px 8px',
                    borderRadius: '9999px',
                    backgroundColor: 'rgba(255, 255, 255, 0.08)',
                    color: 'var(--text-secondary)'
                  }}>
                    {settings.auth_method_name}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                {settings ? `${settings.active_provider_name} · ${settings.active_model}${settings.latency_ms ? ` · ${Math.round(settings.latency_ms)} ms` : ''}` : 'Reading settings…'}
              </div>
            </div>
          </div>
          <button type="button" onClick={recheck} disabled={busy !== null || !settings} style={button(false, busy !== null || !settings)}>
            {busy === 'recheck' ? 'Checking…' : 'Check connection'}
          </button>
        </div>
        {settings?.status_message && <p style={{ ...hint, margin: '12px 0 0' }}>{settings.status_message}</p>}
        <NoticeLine notice={notice} area="status" />
      </section>

      {/* Automatic */}
      <section style={card} aria-label="Automatic connection">
        <h3 style={heading}>Connect automatically</h3>
        <p style={hint}>
          Looks for what this computer already has (API keys in the environment, Claude Code signed in, a local Ollama), tries each one, and keeps the first that answers.
        </p>
        <div data-testid="llm-detected" style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '14px', fontSize: '13px', color: 'var(--text-secondary)' }}>
          {detected === null && <span>Looking…</span>}
          {detected?.length === 0 && (
            <span>Nothing found: no API key in the environment, Claude Code is not installed, no Ollama is running. Use the manual form below.</span>
          )}
          {detected?.map((d) => (
            <span key={d.id}><strong style={{ color: 'var(--text-primary)' }}>{d.name}</strong> — {d.source}</span>
          ))}
        </div>
        <button
          type="button"
          data-testid="llm-auto-connect"
          onClick={connectAutomatically}
          disabled={busy !== null || !detected?.length}
          style={button(true, busy !== null || !detected?.length)}
        >
          {busy === 'auto' ? 'Trying… (up to 30 s per option)' : 'Detect & connect automatically'}
        </button>
        {auto && (
          <div data-testid="llm-auto-result" style={{ marginTop: '14px' }}>
            <NoticeLine notice={{ area: 'auto', ok: auto.connected, text: auto.connected ? `Connected to ${auto.provider_name} (${auto.model}).` : auto.message }} area="auto" />
            <ul style={{ listStyle: 'none', padding: 0, margin: '10px 0 0', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12.5px' }}>
              {auto.results.map((r) => (
                <li key={r.id} style={{ color: r.ok ? 'var(--status-completed)' : 'var(--text-secondary)' }}>
                  {r.ok ? '✓' : '✗'} <strong>{r.name}</strong> — {r.message}
                </li>
              ))}
            </ul>
          </div>
        )}
        <NoticeLine notice={notice} area="auto" />
      </section>

      {/* Manual */}
      <section style={card} aria-label="Manual connection">
        <h3 style={heading}>Connect manually</h3>
        <p style={hint}>Pick a provider and enter its details. “Test connection” only checks; “Save & connect” also makes it the one the pipeline uses.</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px' }}>
          <div>
            <label htmlFor="llm-provider" style={label}>Provider</label>
            <select id="llm-provider" data-testid="llm-provider" value={provider} onChange={(e) => changeProvider(e.target.value)} style={field}>
              {settings?.available_providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="llm-model" style={label}>Model</label>
            {info?.models?.length ? (
              <select id="llm-model" data-testid="llm-model" value={model} onChange={(e) => setModel(e.target.value)} style={field}>
                {!info.models.some((m) => m.id === model) && <option value={model}>{model}</option>}
                {info.models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            ) : (
              <input id="llm-model" data-testid="llm-model" value={model} onChange={(e) => setModel(e.target.value)} placeholder={info?.default_model} style={field} />
            )}
          </div>
          {info?.needs_key && (
            <div>
              <label htmlFor="llm-key" style={label}>API key{keySaved ? ` (saved: ${settings?.api_key_masked})` : ''}</label>
              <input
                id="llm-key"
                type="password"
                autoComplete="off"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={keySaved ? 'Leave empty to keep the saved key' : 'Paste the key here'}
                style={field}
              />
            </div>
          )}
          {showUrl && (
            <div>
              <label htmlFor="llm-url" style={label}>Endpoint URL{provider === 'custom' ? '' : ' (optional)'}</label>
              <input id="llm-url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://…/v1" style={field} />
            </div>
          )}
        </div>
        {info?.needs_key && (
          <p style={{ ...hint, margin: '10px 0 0' }}>The key is stored in <code>config/llm_settings.json</code> on this computer. Do not commit that file.</p>
        )}
        {provider === 'antigravity' && (
          <p style={{ ...hint, margin: '10px 0 0' }}>
            Uses your active Google Antigravity coding session on this computer (found &amp; active). Uses your locked Gemini model directly without needing any API key.
          </p>
        )}
        {provider === 'claude_cli' && (
          <p style={{ ...hint, margin: '10px 0 0' }}>
            Uses the Claude Code you are signed in to on this computer ({settings?.claude_cli_installed ? 'found' : 'not found: install Claude Code and sign in first'}). No key is needed.
          </p>
        )}
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '16px', alignItems: 'center' }}>
          <button type="button" onClick={testOnly} disabled={busy !== null || !!missing} style={button(false, busy !== null || !!missing)}>
            {busy === 'test' ? 'Testing…' : 'Test connection'}
          </button>
          <button type="button" data-testid="llm-save" onClick={saveAndConnect} disabled={busy !== null || !!missing} style={button(true, busy !== null || !!missing)}>
            {busy === 'save' ? 'Saving…' : 'Save & connect'}
          </button>
          {missing && <span style={{ fontSize: '12.5px', color: 'var(--text-muted)' }}>{missing}</span>}
        </div>
        <NoticeLine notice={notice} area="manual" />
      </section>
    </div>
  );
};
