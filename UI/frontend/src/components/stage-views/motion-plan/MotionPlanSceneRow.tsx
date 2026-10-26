import React from 'react';
import { ChevronRight, Check, Copy, Code } from 'lucide-react';
import {
  sceneTdStyle,
  sceneRowStyle
} from '../sceneTableStyles';

export interface MotionPlanSceneRowProps {
  scene: any;
  idx: number;
  isCopied: boolean;
  onOpen: (id: string, withJson: boolean) => void;                    // opens the scene's popup (withJson: with its raw JSON shown)
  handleCopyMotionSceneJson: (scene: any, e?: React.MouseEvent) => void;
}

export const MotionPlanSceneRow: React.FC<MotionPlanSceneRowProps> = ({
  scene,
  idx,
  isCopied,
  onOpen,
  handleCopyMotionSceneJson
}) => {
  const sceneKey = scene.scene_id || scene.plan_scene_id || String(idx + 1);
  const sceneNum = String(idx + 1).padStart(2, '0');

  const t0 = scene.timing?.start ?? 0;
  const t1 = scene.timing?.end ?? 0;
  const duration = Math.max(0, t1 - t0);
  const startFrame = scene.timing?.start_frame ?? 0;
  const endFrame = scene.timing?.end_frame ?? 0;

  const teluguNarration = scene.visual_scene_data?.narration?.text || scene.segmentation_data?.llm_transcript || scene.segmentation_data?.transcript || '—';
  const intent = scene.motion_intent || {};
  const mpScene = scene.motion_plan_scene || {};
  const pattern = mpScene.pattern || 'hero_text';
  const sequence: any[] = scene.sequence || [];

  return (
    <React.Fragment key={sceneKey}>
      {/* Scene Table Row (Clickable) */}
      <tr
        onClick={() => onOpen(sceneKey, false)}
        data-testid={`motion-scene-card-${sceneNum}`}
        style={sceneRowStyle(false)}
      >
        <td style={{ ...sceneTdStyle, paddingRight: 0, color: 'var(--text-muted)', borderLeft: `3px solid ${scene.segmentation_data?.llm_transcript ? '#10B981' : '#6B7280'}` }}>
          <ChevronRight size={16} />
        </td>
        <td style={sceneTdStyle}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: 'rgba(0, 216, 245, 0.1)',
            padding: '3px 8px',
            borderRadius: '4px',
            border: '1px solid rgba(0, 216, 245, 0.25)'
          }}>
            <span style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
              SCENE {sceneNum}
            </span>
            <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              #{scene.plan_scene_id || idx + 1}
            </span>
          </div>
        </td>
        <td style={sceneTdStyle}>
          {/* Purpose & Attention Goal Preview */}
          <div style={{ minWidth: 0 }}>
            <div style={{
              fontSize: '13px',
              fontWeight: 700,
              color: 'var(--text-primary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '480px'
            }}>
              <span style={{ color: 'var(--accent-cyan)', textTransform: 'capitalize' }}>{intent.purpose || 'Motion Beat'}:</span> {intent.attention_goal || intent.takeaway || 'Kinetic animation focus'}
            </div>
            <div style={{
              fontSize: '11px',
              color: 'var(--text-muted)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '480px'
            }}>
              {teluguNarration}
            </div>
          </div>
        </td>
        <td style={sceneTdStyle}>
          {/* Timing Badge */}
          <span style={{
            whiteSpace: 'nowrap',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            backgroundColor: 'rgba(255, 255, 255, 0.05)',
            color: 'var(--text-muted)',
            padding: '3px 8px',
            borderRadius: '4px',
            border: '1px solid var(--border-card)'
          }}>
            ⏱ {t0.toFixed(1)}s - {t1.toFixed(1)}s ({duration.toFixed(1)}s)
          </span>
        </td>
        <td style={sceneTdStyle}>
          {/* Frames Badge */}
          <span style={{
            whiteSpace: 'nowrap',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            color: '#60A5FA',
            padding: '3px 8px',
            borderRadius: '4px',
            border: '1px solid rgba(59, 130, 246, 0.25)'
          }}>
            🎞 {startFrame} - {endFrame}f
          </span>
        </td>
        <td style={sceneTdStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            {/* Pattern Tag */}
            <span style={{
              fontSize: '10.5px',
              backgroundColor: 'rgba(245, 158, 11, 0.12)',
              color: '#FBBF24',
              padding: '3px 8px',
              borderRadius: '4px',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              fontFamily: 'var(--font-mono)'
            }}>
              {pattern}
            </span>

            {/* Intensity Tag */}
            {intent.intensity && (
              <span style={{
                fontSize: '10.5px',
                backgroundColor: 'rgba(168, 85, 247, 0.12)',
                color: '#C084FC',
                padding: '3px 8px',
                borderRadius: '4px',
                border: '1px solid rgba(168, 85, 247, 0.25)',
                fontFamily: 'var(--font-mono)'
              }}>
                ⚡ {intent.intensity}
              </span>
            )}

            {/* Actions Count */}
            <span style={{
              fontSize: '10.5px',
              backgroundColor: 'rgba(16, 185, 129, 0.12)',
              color: '#34D399',
              padding: '3px 8px',
              borderRadius: '4px',
              border: '1px solid rgba(16, 185, 129, 0.25)',
              fontFamily: 'var(--font-mono)'
            }}>
              ✨ {sequence.length} actions
            </span>
          </div>
        </td>
        <td style={sceneTdStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {/* Copy Scene JSON Button */}
            <button
              onClick={(e) => handleCopyMotionSceneJson(scene, e)}
              data-testid={`motion-scene-${sceneNum}-copy-json-btn`}
              title="Copy complete motion JSON for this scene"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 10px',
                backgroundColor: isCopied ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.06)',
                border: isCopied ? '1px solid #10B981' : '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '4px',
                color: isCopied ? '#10B981' : '#E2E8F0',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              {isCopied ? (
                <>
                  <Check size={12} color="#10B981" />
                  <span>Copied JSON!</span>
                </>
              ) : (
                <>
                  <Copy size={12} />
                  <span>Copy JSON</span>
                </>
              )}
            </button>

            {/* Toggle Raw JSON View Button */}
            <button
              onClick={(e) => { e.stopPropagation(); onOpen(sceneKey, true); }}
              data-testid={`motion-scene-${sceneNum}-toggle-raw-json-btn`}
              title="Open this motion scene with its raw JSON"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 8px',
                backgroundColor: 'transparent',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '4px',
                color: 'var(--text-muted)',
                fontSize: '11px',
                cursor: 'pointer'
              }}
            >
              <Code size={12} />
              <span>JSON</span>
            </button>
          </div>
        </td>
      </tr>
    </React.Fragment>
  );
};
