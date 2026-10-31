import React, { useState } from 'react';
import { BarChart2, MapPin, Volume2, X, Loader2 } from 'lucide-react';
import { generateChartAsset, generateMapAsset, fetchSfxCatalog } from '../../services/api';
import styles from './AssetGeneratorsBar.module.css';

interface AssetGeneratorsBarProps {
  projectId: string;
  onAssetCreated?: () => void;
}

export const AssetGeneratorsBar: React.FC<AssetGeneratorsBarProps> = ({
  projectId,
  onAssetCreated,
}) => {
  const [activeModal, setActiveModal] = useState<'chart' | 'map' | 'sfx' | null>(null);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  // Chart form state
  const [chartType, setChartType] = useState('bar');
  const [chartTitle, setChartTitle] = useState('Key Statistics');
  const [chartLabels, setChartLabels] = useState('Q1, Q2, Q3, Q4');
  const [chartData, setChartData] = useState('25, 45, 65, 90');

  // Map form state
  const [placeName, setPlaceName] = useState('Hyderabad, India');

  // SFX catalog state
  const [sfxList, setSfxList] = useState<any[]>([]);

  const handleOpenChart = () => {
    setStatusMsg(null);
    setActiveModal('chart');
  };

  const handleOpenMap = () => {
    setStatusMsg(null);
    setActiveModal('map');
  };

  const handleOpenSfx = async () => {
    setStatusMsg(null);
    setActiveModal('sfx');
    setLoading(true);
    const res = await fetchSfxCatalog();
    if (res.ok && res.sfx) {
      setSfxList(res.sfx);
    }
    setLoading(false);
  };

  const handleGenerateChart = async () => {
    if (!projectId) return;
    setLoading(true);
    setStatusMsg(null);
    const labels = chartLabels.split(',').map((s) => s.trim()).filter(Boolean);
    const data = chartData
      .split(',')
      .map((s) => parseFloat(s.trim()))
      .filter((n) => !isNaN(n));

    const res = await generateChartAsset(projectId, {
      chart_type: chartType,
      labels,
      data,
      title: chartTitle,
      dark_mode: true,
    });

    setLoading(false);
    if (res.ok) {
      setStatusMsg(`Chart generated: ${res.filename}`);
      if (onAssetCreated) onAssetCreated();
      setTimeout(() => setActiveModal(null), 1200);
    } else {
      setStatusMsg(res.error || 'Failed to generate chart');
    }
  };

  const handleGenerateMap = async () => {
    if (!projectId || !placeName.trim()) return;
    setLoading(true);
    setStatusMsg(null);

    const res = await generateMapAsset(projectId, {
      place_name: placeName.trim(),
    });

    setLoading(false);
    if (res.ok) {
      setStatusMsg(`Map generated: ${res.filename}`);
      if (onAssetCreated) onAssetCreated();
      setTimeout(() => setActiveModal(null), 1200);
    } else {
      setStatusMsg(res.error || 'Failed to generate map');
    }
  };

  return (
    <>
      <div className={styles.container} data-testid="asset-generator-bar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Asset Toolkits:
          </span>
        </div>

        <div className={styles.buttonGroup}>
          <button
            type="button"
            className={styles.actionButton}
            data-testid="gen-chart-btn"
            onClick={handleOpenChart}
          >
            <BarChart2 size={14} color="#60A5FA" />
            <span>Generate Chart</span>
          </button>

          <button
            type="button"
            className={styles.actionButton}
            data-testid="gen-map-btn"
            onClick={handleOpenMap}
          >
            <MapPin size={14} color="#34D399" />
            <span>Generate Map</span>
          </button>

          <button
            type="button"
            className={styles.actionButton}
            data-testid="sfx-catalog-btn"
            onClick={handleOpenSfx}
          >
            <Volume2 size={14} color="#FBBF24" />
            <span>Browse SFX</span>
          </button>


        </div>
      </div>

      {/* Modal Dialog */}
      {activeModal && (
        <div className={styles.modalOverlay} onClick={() => setActiveModal(null)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div className={styles.modalTitle}>
                {activeModal === 'chart' && <><BarChart2 size={16} color="#60A5FA" /> QuickChart Infographic Generator</>}
                {activeModal === 'map' && <><MapPin size={16} color="#34D399" /> OpenStreetMap Map Visual Generator</>}
                {activeModal === 'sfx' && <><Volume2 size={16} color="#FBBF24" /> Motion Sound Effects (SFX) Catalog</>}
              </div>
              <button
                type="button"
                className={styles.closeButton}
                onClick={() => setActiveModal(null)}
              >
                <X size={16} />
              </button>
            </div>

            {statusMsg && (
              <div style={{ fontSize: '12px', color: 'var(--accent-cyan)', padding: '6px 0' }}>
                {statusMsg}
              </div>
            )}

            {/* Chart Form */}
            {activeModal === 'chart' && (
              <>
                <div className={styles.formGroup}>
                  <label className={styles.label}>Chart Type</label>
                  <select
                    className={styles.select}
                    value={chartType}
                    onChange={(e) => setChartType(e.target.value)}
                  >
                    <option value="bar">Bar Chart</option>
                    <option value="line">Line Chart</option>
                    <option value="pie">Pie Chart</option>
                    <option value="doughnut">Doughnut Chart</option>
                  </select>
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.label}>Title</label>
                  <input
                    className={styles.input}
                    value={chartTitle}
                    onChange={(e) => setChartTitle(e.target.value)}
                  />
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.label}>Labels (comma-separated)</label>
                  <input
                    className={styles.input}
                    value={chartLabels}
                    onChange={(e) => setChartLabels(e.target.value)}
                  />
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.label}>Data Values (comma-separated numbers)</label>
                  <input
                    className={styles.input}
                    value={chartData}
                    onChange={(e) => setChartData(e.target.value)}
                  />
                </div>
                <div className={styles.modalFooter}>
                  <button
                    type="button"
                    className={styles.primaryButton}
                    disabled={loading}
                    onClick={handleGenerateChart}
                  >
                    {loading ? <Loader2 size={14} className="animate-spin" /> : 'Render & Save Chart'}
                  </button>
                </div>
              </>
            )}

            {/* Map Form */}
            {activeModal === 'map' && (
              <>
                <div className={styles.formGroup}>
                  <label className={styles.label}>Place Name (City, Landmark, Country)</label>
                  <input
                    className={styles.input}
                    value={placeName}
                    onChange={(e) => setPlaceName(e.target.value)}
                    placeholder="e.g. Hyderabad, India"
                  />
                </div>
                <div className={styles.modalFooter}>
                  <button
                    type="button"
                    className={styles.primaryButton}
                    disabled={loading || !placeName.trim()}
                    onClick={handleGenerateMap}
                  >
                    {loading ? <Loader2 size={14} className="animate-spin" /> : 'Render & Save Map'}
                  </button>
                </div>
              </>
            )}

            {/* SFX Catalog */}
            {activeModal === 'sfx' && (
              <div className={styles.sfxGrid}>
                {loading && <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Loading SFX cues...</div>}
                {sfxList.map((sfx) => (
                  <div key={sfx.id} className={styles.sfxItem}>
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{sfx.name}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {sfx.category} · {sfx.duration_seconds}s
                      </div>
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)' }}>
                      cue: {sfx.id}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};
