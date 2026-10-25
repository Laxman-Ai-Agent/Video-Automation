import React from 'react';
import { Layers, Code, Check, Copy } from 'lucide-react';
import { MotionPlanTransformationGrid } from './MotionPlanTransformationGrid';
import { MotionPlanActionQueue } from './MotionPlanActionQueue';

export interface MotionPlanSceneExpandedProps {
  scene: any;
  sceneNum: string;
  sceneKey: string;
  isFullPage?: boolean;
  isRawJsonOpen: boolean;
  isCopied: boolean;
  handleCopyMotionSceneJson: (scene: any, e?: React.MouseEvent) => void;
}

export const MotionPlanSceneExpanded: React.FC<MotionPlanSceneExpandedProps> = ({
  scene,
  sceneNum,
  sceneKey: _sceneKey,
  isFullPage = false,
  isRawJsonOpen,
  isCopied,
  handleCopyMotionSceneJson
}) => {
  const sequence: any[] = scene.sequence || [];
  const elements: any[] = scene.elements || [];

  return (
    <div style={{
      padding: '18px 20px',
      borderTop: '1px solid var(--border-card)',
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
      backgroundColor: 'var(--bg-app)'
    }}>
      {/* Section Title Banner: Before & After Transformation */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 12px',
        backgroundColor: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '6px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '13px' }}>🔄</span>
          <span style={{ fontSize: '12px', fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Before vs After Scene Transformation
          </span>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          Input Visual Directives & Script ➔ Motion Planning & Kinetic Sequence
        </span>
      </div>

      {/* 2-Column Comparative Grid */}
      <MotionPlanTransformationGrid
        scene={scene}
        isFullPage={isFullPage}
      />

      {/* Kinetic Elements & Resolved Presets */}
      {elements.length > 0 && (
        <div style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-card)',
          borderRadius: '8px',
          padding: '14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Layers size={13} color="var(--accent-cyan)" />
              <span style={{ fontSize: '11.5px', fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Kinetic Elements & Presets ({elements.length} Layers)
              </span>
            </div>
            <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
              Resolved Registry Components
            </span>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: isFullPage ? 'repeat(auto-fit, minmax(260px, 1fr))' : '1fr',
            gap: '10px'
          }}>
            {elements.map((el: any, elIdx: number) => (
              <div
                key={el.element_id || elIdx}
                style={{
                  backgroundColor: 'var(--bg-elevated)',
                  border: el.semantic_role === 'primary' ? '1px solid rgba(0, 216, 245, 0.3)' : '1px solid rgba(255, 255, 255, 0.06)',
                  borderRadius: '6px',
                  padding: '10px 12px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    {el.element_id}
                  </span>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <span style={{
                      fontSize: '9.5px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      padding: '1px 6px',
                      borderRadius: '3px',
                      backgroundColor: el.semantic_role === 'primary' ? 'rgba(0, 216, 245, 0.2)' : 'rgba(255, 255, 255, 0.08)',
                      color: el.semantic_role === 'primary' ? 'var(--accent-cyan)' : 'var(--text-muted)'
                    }}>
                      {el.semantic_role}
                    </span>
                    <span style={{
                      fontSize: '9.5px',
                      fontFamily: 'var(--font-mono)',
                      padding: '1px 6px',
                      borderRadius: '3px',
                      backgroundColor: 'rgba(168, 85, 247, 0.15)',
                      color: '#D8B4FE'
                    }}>
                      {el.type}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Preset:</span>
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--accent-cyan)',
                    backgroundColor: 'rgba(0, 216, 245, 0.1)',
                    padding: '1px 6px',
                    borderRadius: '3px'
                  }}>
                    {el.registry_id || 'default'}
                  </span>
                  <span style={{ fontSize: '10px', color: '#10B981', marginLeft: 'auto' }}>
                    ✓ {el.status || 'resolved'}
                  </span>
                </div>

                {el.note && (
                  <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', lineHeight: 1.3 }}>
                    {el.note}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Sequence Timeline */}
      <MotionPlanActionQueue sequence={sequence} />

      {/* Raw Scene JSON Box (Toggleable via JSON button) */}
      {isRawJsonOpen && (
        <div style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid rgba(0, 216, 245, 0.3)',
          borderRadius: '6px',
          overflow: 'hidden'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 12px',
            backgroundColor: 'var(--bg-elevated)',
            borderBottom: '1px solid var(--border-card)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Code size={13} color="var(--accent-cyan)" />
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                Motion Scene {sceneNum} Raw JSON Data ({Object.keys(scene).length} attributes)
              </span>
            </div>
            <button
              onClick={(e) => handleCopyMotionSceneJson(scene, e)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '3px 8px',
                backgroundColor: isCopied ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.08)',
                border: isCopied ? '1px solid #10B981' : '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '4px',
                color: isCopied ? '#10B981' : '#FFFFFF',
                fontSize: '10.5px',
                cursor: 'pointer'
              }}
            >
              {isCopied ? <Check size={11} color="#10B981" /> : <Copy size={11} />}
              <span>{isCopied ? 'Copied!' : 'Copy'}</span>
            </button>
          </div>
          <pre style={{
            margin: 0,
            padding: '12px 14px',
            maxHeight: '340px',
            overflowY: 'auto',
            fontSize: '11.5px',
            fontFamily: 'Consolas, monospace',
            color: '#93C5FD',
            lineHeight: 1.5,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all'
          }}>
            {JSON.stringify(scene, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
