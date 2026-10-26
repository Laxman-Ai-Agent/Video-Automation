import React, { useState } from 'react';
import { Sparkles, Search, RefreshCw, Play } from 'lucide-react';
import {
  sceneTableStyle,
  sceneThStyle
} from './sceneTableStyles';
import { MotionPlanSummaryBar } from './motion-plan/MotionPlanSummaryBar';
import { MotionPlanSceneRow } from './motion-plan/MotionPlanSceneRow';
import { MotionSceneModal } from './motion-plan/MotionSceneModal';

export interface MotionPlanSceneTableProps {
  motionPlanData: any;
  motionScenesList: any[];
  filteredMotionScenes: any[];
  sceneSearch: string;
  setSceneSearch: (val: string) => void;
  motionPlanLoading: boolean;
  copiedMotionSceneId: string | null;
  copiedAllMotion: boolean;
  handleCopyMotionSceneJson: (scene: any, e?: React.MouseEvent) => void;
  handleCopyAllMotionPlanJson: (e?: React.MouseEvent) => void;
  onRunStage?: (stageId: string) => void;
}

export const MotionPlanSceneTable: React.FC<MotionPlanSceneTableProps> = ({
  motionPlanData,
  motionScenesList,
  filteredMotionScenes,
  sceneSearch,
  setSceneSearch,
  motionPlanLoading,
  copiedMotionSceneId,
  copiedAllMotion,
  handleCopyMotionSceneJson,
  handleCopyAllMotionPlanJson,
  onRunStage,
}) => {
  const [open, setOpen] = useState<{ key: string; json: boolean } | null>(null);       // the scene whose popup is open
  const keyOf = (s: any, i: number) => s.scene_id || s.plan_scene_id || String(i + 1);
  const openIdx = open ? filteredMotionScenes.findIndex((s: any, i: number) => keyOf(s, i) === open.key) : -1;
  const step = (delta: number) => {
    const next = filteredMotionScenes[openIdx + delta];
    if (next) setOpen({ key: keyOf(next, openIdx + delta), json: open?.json ?? false });
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }} data-testid="motion-planning-tab-content">
      {/* Summary Metadata Bar */}
      <MotionPlanSummaryBar
        motionPlanData={motionPlanData}
        motionScenesList={motionScenesList}
        copiedAllMotion={copiedAllMotion}
        handleCopyAllMotionPlanJson={handleCopyAllMotionPlanJson}
      />

      {/* Filter / Search Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        backgroundColor: 'var(--bg-elevated)',
        border: '1px solid var(--border-card)',
        borderRadius: '6px',
        padding: '8px 14px'
      }}>
        <Search size={14} color="var(--text-muted)" />
        <input
          type="text"
          placeholder="Search motion scenes by preset, keyword, Telugu narration, mood, or timing..."
          value={sceneSearch}
          onChange={(e) => setSceneSearch(e.target.value)}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            color: 'var(--text-primary)',
            fontSize: '13px',
            outline: 'none'
          }}
        />
        {sceneSearch && (
          <button
            onClick={() => setSceneSearch('')}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '11px'
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Loading State */}
      {motionPlanLoading && (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          backgroundColor: 'var(--bg-elevated)',
          borderRadius: '8px',
          border: '1px solid var(--border-card)',
          color: 'var(--text-muted)'
        }}>
          <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px auto', display: 'block', color: 'var(--accent-cyan)' }} />
          <div style={{ fontSize: '13.5px', color: 'var(--text-primary)', fontWeight: 600 }}>Loading Motion Planning Scenes & Animation Timelines...</div>
        </div>
      )}

      {/* Empty State */}
      {!motionPlanLoading && motionScenesList.length === 0 && (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          backgroundColor: 'var(--bg-elevated)',
          borderRadius: '8px',
          border: '1px solid var(--border-card)'
        }}>
          <Sparkles size={32} color="var(--text-muted)" style={{ margin: '0 auto 12px auto', display: 'block' }} />
          <div style={{ fontSize: '14px', color: 'var(--text-primary)', fontWeight: 700, marginBottom: '6px' }}>
            No Motion Planning Data Available
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '420px', margin: '0 auto 16px auto' }}>
            Motion Planning has not been executed yet for this project. Run Motion Planning to generate kinetic typography, graphic presets, and action sequences.
          </div>
          {onRunStage && (
            <button
              onClick={() => onRunStage('motion_plan')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 18px',
                backgroundColor: 'var(--accent-cyan)',
                color: '#000000',
                border: 'none',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              <Play size={13} fill="currentColor" />
              <span>Run Motion Planning</span>
            </button>
          )}
        </div>
      )}

      {/* Motion Scene List Cards */}
      {!motionPlanLoading && filteredMotionScenes.length > 0 && (
        <table data-testid="motion-scenes-list" style={sceneTableStyle}>
          <colgroup>
            <col style={{ width: '44px' }} /><col style={{ width: '120px' }} /><col />
            <col style={{ width: '175px' }} /><col style={{ width: '130px' }} /><col style={{ width: '230px' }} /><col style={{ width: '170px' }} />
          </colgroup>
          <thead>
            <tr>
              <th style={sceneThStyle}></th><th style={sceneThStyle}>Scene</th><th style={sceneThStyle}>Purpose / Narration</th>
              <th style={sceneThStyle}>Time</th><th style={sceneThStyle}>Frames</th><th style={sceneThStyle}>Pattern / Intensity</th><th style={sceneThStyle}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredMotionScenes.map((s: any, idx: number) => {
              const sceneKey = keyOf(s, idx);
              return (
                <MotionPlanSceneRow
                  key={sceneKey}
                  scene={s}
                  idx={idx}
                  isCopied={copiedMotionSceneId === sceneKey}
                  onOpen={(key, json) => setOpen({ key, json })}
                  handleCopyMotionSceneJson={handleCopyMotionSceneJson}
                />
              );
            })}
          </tbody>
        </table>
      )}

      {/* The scene in full, in a popup */}
      {open && openIdx >= 0 && (
        <MotionSceneModal
          scene={filteredMotionScenes[openIdx]}
          idx={openIdx}
          total={filteredMotionScenes.length}
          startWithJson={open.json}
          isCopied={copiedMotionSceneId === open.key}
          handleCopyMotionSceneJson={handleCopyMotionSceneJson}
          onClose={() => setOpen(null)}
          onStep={step}
        />
      )}
    </div>
  );
};
