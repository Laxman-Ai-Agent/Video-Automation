import React, { useState, useEffect } from 'react';
import styles from './VisualSceneModal.module.css';
import {
  X,
  Volume2,
  Clock,
  Layers,
  Link2,
  Sparkles,
  Film,
  Image as ImageIcon,
  Type,
  Shapes,
  Compass,
  ArrowRight,
  Target,
  Monitor
} from 'lucide-react';
import { HeroBadge } from './VisualPlanningView';

export interface VisualSceneModalProps {
  scene: any;
  onClose: () => void;
}

type TabKey = 'elements' | 'relationships' | 'cues' | 'motion' | 'media' | 'continuity';

export const VisualSceneModal: React.FC<VisualSceneModalProps> = ({ scene, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabKey>('elements');
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!scene) return null;

  const elements = scene.elements || [];
  const relationships = scene.element_relationships || [];
  const wordCues = scene.word_animation_events || [];
  const motionHints = scene.motion_hints || [];
  const mediaReqs = scene.media_requirements || [];
  const counts = scene.counts || {};
  const narration = scene.narration || {};
  const objective = scene.scene_objective || {};
  const concept = scene.visual_concept || {};
  const continuity = scene.continuity || {};
  const beats = scene.beats || [];

  const getTypeClass = (type: string) => {
    switch (type) {
      case 'text': return styles.typeText;
      case 'icon': return styles.typeIcon;
      case 'graphic': return styles.typeGraphic;
      case 'image': return styles.typeImage;
      case 'video': return styles.typeVideo;
      case 'background': return styles.typeBackground;
      default: return styles.typeGraphic;
    }
  };

  const getRegionStyle = (region: string): React.CSSProperties => {
    switch (region) {
      case 'full_frame':
        return { top: '3%', left: '3%', right: '3%', bottom: '3%', zIndex: 1, border: '1px dashed rgba(255, 255, 255, 0.2)', backgroundColor: 'rgba(255, 255, 255, 0.03)' };
      case 'center':
        return { top: '25%', left: '26%', right: '26%', bottom: '25%', zIndex: 3, backgroundColor: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.4)' };
      case 'center_left':
        return { top: '22%', left: '6%', width: '42%', bottom: '22%', zIndex: 3, backgroundColor: 'rgba(59, 130, 246, 0.14)', border: '1px solid rgba(59, 130, 246, 0.4)' };
      case 'center_right':
        return { top: '22%', right: '6%', width: '42%', bottom: '22%', zIndex: 3, backgroundColor: 'rgba(59, 130, 246, 0.14)', border: '1px solid rgba(59, 130, 246, 0.4)' };
      case 'top_center':
      case 'upper_safe_area':
        return { top: '6%', left: '16%', right: '16%', height: '22%', zIndex: 4, backgroundColor: 'rgba(56, 189, 248, 0.14)', border: '1px solid rgba(56, 189, 248, 0.45)' };
      case 'bottom_center':
      case 'lower_safe_area':
        return { bottom: '6%', left: '16%', right: '16%', height: '22%', zIndex: 4, backgroundColor: 'rgba(56, 189, 248, 0.14)', border: '1px solid rgba(56, 189, 248, 0.45)' };
      case 'upper_left':
        return { top: '6%', left: '6%', width: '38%', height: '36%', zIndex: 3, backgroundColor: 'rgba(245, 158, 11, 0.14)', border: '1px solid rgba(245, 158, 11, 0.4)' };
      case 'upper_right':
        return { top: '6%', right: '6%', width: '38%', height: '36%', zIndex: 3, backgroundColor: 'rgba(245, 158, 11, 0.14)', border: '1px solid rgba(245, 158, 11, 0.4)' };
      case 'lower_left':
        return { bottom: '6%', left: '6%', width: '38%', height: '36%', zIndex: 3, backgroundColor: 'rgba(168, 85, 247, 0.14)', border: '1px solid rgba(168, 85, 247, 0.4)' };
      case 'lower_right':
        return { bottom: '6%', right: '6%', width: '38%', height: '36%', zIndex: 3, backgroundColor: 'rgba(168, 85, 247, 0.14)', border: '1px solid rgba(168, 85, 247, 0.4)' };
      case 'path_across_frame':
        return { top: '44%', left: '4%', right: '4%', height: '14%', zIndex: 2, backgroundColor: 'rgba(236, 72, 153, 0.14)', border: '1px dashed rgba(236, 72, 153, 0.5)' };
      default:
        return { top: '25%', left: '25%', right: '25%', bottom: '25%', zIndex: 3, backgroundColor: 'rgba(255, 255, 255, 0.08)', border: '1px solid rgba(255, 255, 255, 0.2)' };
    }
  };

  const sceneDuration = Math.max(0.1, (narration.end_seconds || 1) - (narration.start_seconds || 0));

  return (
    <div className={styles.overlay} onClick={onClose} data-testid="visual-scene-modal">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h3 className={styles.sceneTitle}>
              <Layers size={17} color="var(--accent-cyan)" />
              {scene.scene_id}
            </h3>
            {narration.start_seconds !== undefined && (
              <span className={styles.timePill}>
                <Clock size={11} />
                {narration.start_seconds.toFixed(1)}s – {narration.end_seconds?.toFixed(1)}s ({sceneDuration.toFixed(1)}s)
              </span>
            )}
            {scene.hero && <HeroBadge family={scene.hero} />}
            {objective.narrative_role && (
              <span className={styles.roleBadge}>
                {objective.narrative_role}
              </span>
            )}
          </div>
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            data-testid="visual-scene-modal-close"
            title="Close"
          >
            <X size={17} />
          </button>
        </div>

        {/* 2-Column Split Body */}
        <div className={styles.body}>
          {/* LEFT COLUMN: Visual Storyboard, Timeline, & Concept */}
          <div className={styles.leftCol}>
            {/* Narration Box */}
            <div className={styles.narrationBox} data-testid="scene-narration-box">
              <div className={styles.narrationHeader}>
                <Volume2 size={13} />
                <span>Original Narration ({narration.start_seconds?.toFixed(1)}s – {narration.end_seconds?.toFixed(1)}s)</span>
              </div>
              {narration.text && (
                <div className={styles.teluguText}>
                  {narration.text}
                </div>
              )}
              {narration.text_en && (
                <div className={styles.englishText}>
                  {narration.text_en}
                </div>
              )}
            </div>

            {/* 16:9 Canvas Storyboard Wireframe */}
            <div className={styles.canvasCard}>
              <div className={styles.canvasHeader}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Monitor size={13} color="var(--accent-cyan)" />
                  16:9 Visual Layout Wireframe
                </span>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Click element to inspect</span>
              </div>
              <div className={styles.canvasAspectRatio}>
                <div className={styles.canvasSafeZone} />
                <div className={styles.canvasCenterDot} />
                {elements.map((el: any) => {
                  const reg = el.placement?.region || 'center';
                  const isSelected = selectedElementId === el.element_id;
                  const customStyle = getRegionStyle(reg);
                  return (
                    <div
                      key={el.element_id}
                      className={`${styles.canvasElementBox} ${isSelected ? styles.canvasElementSelected : ''}`}
                      style={customStyle}
                      onClick={() => {
                        setSelectedElementId(el.element_id);
                        setActiveTab('elements');
                      }}
                      title={`${el.element_id} (${el.type}) placed in ${reg}`}
                    >
                      <span style={{ color: el.role === 'primary' ? '#38bdf8' : 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%' }}>
                        {el.element_id}
                      </span>
                      <span style={{ fontSize: '9px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        {el.type} · {el.role}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Audio Word-Cues Timeline */}
            {wordCues.length > 0 && (
              <div className={styles.timelineCard}>
                <div className={styles.canvasHeader}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Sparkles size={13} color="#fde047" />
                    Audio-Sync Kinetic Cues
                  </span>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{wordCues.length} Cues</span>
                </div>
                <div className={styles.timelineTrack}>
                  {wordCues.map((cue: any, idx: number) => {
                    const cueStart = cue.start_seconds || narration.start_seconds || 0;
                    const sceneStart = narration.start_seconds || 0;
                    const offsetPct = Math.max(4, Math.min(94, ((cueStart - sceneStart) / sceneDuration) * 100));
                    return (
                      <div
                        key={idx}
                        className={styles.cueMarker}
                        style={{ left: `${offsetPct}%` }}
                        onClick={() => setActiveTab('cues')}
                        title={`"${cue.word}" at ${cue.start_seconds?.toFixed(1)}s -> ${cue.semantic_intent}`}
                      >
                        <Sparkles size={9} />
                        {cue.word}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Objective & Concept Section */}
            <div className={styles.objectiveCard}>
              <div className={styles.objectiveCol}>
                <span className={styles.sectionLabel}>Core Meaning & Takeaway</span>
                <div className={styles.objectiveValue}>
                  <strong>{objective.core_meaning || 'Meaning not specified'}</strong>
                </div>
                {objective.audience_takeaway && (
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    Takeaway: {objective.audience_takeaway}
                  </div>
                )}
              </div>
              <div className={styles.objectiveCol}>
                <span className={styles.sectionLabel}>Visual Representation</span>
                <div className={styles.objectiveValue}>
                  {concept.description || 'Concept not specified'}
                </div>
                {concept.primary_focus && (
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    Focus: <strong>{concept.primary_focus}</strong> {concept.representation ? `(${concept.representation})` : ''}
                  </div>
                )}
              </div>
            </div>

            {/* Quick Stats Grid */}
            <div className={styles.statsRow}>
              <div className={styles.statCard}>
                <div className={styles.statValue}>{counts.text ?? 0}</div>
                <div className={styles.statLabel}>Text</div>
              </div>
              <div className={styles.statCard}>
                <div className={styles.statValue}>{counts.icon ?? 0}</div>
                <div className={styles.statLabel}>Icons</div>
              </div>
              <div className={styles.statCard}>
                <div className={styles.statValue}>{counts.graphic ?? 0}</div>
                <div className={styles.statLabel}>Cards</div>
              </div>
              <div className={styles.statCard}>
                <div className={styles.statValue}>{counts.image ?? 0}</div>
                <div className={styles.statLabel}>Images</div>
              </div>
            </div>
          </div>

          {/* RIGHT COLUMN: Interactive Tabs and In-Depth Details */}
          <div className={styles.rightCol}>
            {/* Tab Navigation */}
            <div className={styles.navTabs}>
              <button
                type="button"
                className={`${styles.navTab} ${activeTab === 'elements' ? styles.navTabActive : ''}`}
                onClick={() => setActiveTab('elements')}
              >
                <Layers size={13} />
                Elements
                <span className={styles.tabBadge}>{elements.length}</span>
              </button>
              <button
                type="button"
                className={`${styles.navTab} ${activeTab === 'relationships' ? styles.navTabActive : ''}`}
                onClick={() => setActiveTab('relationships')}
              >
                <Link2 size={13} />
                Relationships
                <span className={styles.tabBadge}>{relationships.length}</span>
              </button>
              <button
                type="button"
                className={`${styles.navTab} ${activeTab === 'cues' ? styles.navTabActive : ''}`}
                onClick={() => setActiveTab('cues')}
              >
                <Sparkles size={13} />
                Word Cues
                <span className={styles.tabBadge}>{wordCues.length}</span>
              </button>
              <button
                type="button"
                className={`${styles.navTab} ${activeTab === 'motion' ? styles.navTabActive : ''}`}
                onClick={() => setActiveTab('motion')}
              >
                <Compass size={13} />
                Motion Hints
                <span className={styles.tabBadge}>{motionHints.length}</span>
              </button>
              <button
                type="button"
                className={`${styles.navTab} ${activeTab === 'media' ? styles.navTabActive : ''}`}
                onClick={() => setActiveTab('media')}
              >
                <ImageIcon size={13} />
                Stock/Media
                <span className={styles.tabBadge}>{mediaReqs.length}</span>
              </button>
              <button
                type="button"
                className={`${styles.navTab} ${activeTab === 'continuity' ? styles.navTabActive : ''}`}
                onClick={() => setActiveTab('continuity')}
              >
                <ArrowRight size={13} />
                Beats
              </button>
            </div>

            {/* Tab Content: Elements */}
            {activeTab === 'elements' && (
              <div className={styles.elementsList}>
                {elements.map((el: any) => {
                  const isHighlighted = selectedElementId === el.element_id;
                  return (
                    <div
                      key={el.element_id}
                      className={`${styles.elementCard} ${isHighlighted ? styles.elementCardHighlighted : ''}`}
                    >
                      <div className={styles.elementHeader}>
                        <div className={styles.elementBadges}>
                          <span className={styles.elementId}>{el.element_id}</span>
                          <span className={`${styles.elementTypeBadge} ${getTypeClass(el.type)}`}>
                            {el.type}
                          </span>
                          {el.role === 'primary' && (
                            <span className={styles.rolePrimaryBadge}>Primary Hero</span>
                          )}
                          {el.depth_layer && (
                            <span className={styles.tagPill}>{el.depth_layer}</span>
                          )}
                        </div>
                        <span className={styles.regionBadge}>
                          {el.placement?.region || 'default'}
                        </span>
                      </div>

                      <div className={styles.elementDescription}>
                        {el.visual_description}
                      </div>

                      {el.content && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                          <Type size={13} color="var(--accent-cyan)" />
                          <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>"{el.content}"</span>
                          {el.text_purpose && (
                            <span className={styles.tagPill}>Purpose: {el.text_purpose}</span>
                          )}
                        </div>
                      )}

                      {el.constraints?.length > 0 && (
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '2px' }}>
                          {el.constraints.map((c: string, idx: number) => (
                            <span key={idx} className={styles.tagPill}>
                              ⚡ {c}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Tab Content: Relationships */}
            {activeTab === 'relationships' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {relationships.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No explicit relationships defined between elements.
                  </div>
                ) : (
                  relationships.map((rel: any, idx: number) => (
                    <div key={idx} className={styles.relationCard}>
                      <span className={styles.relationNode}>{rel.source}</span>
                      <div className={styles.relationArrow}>
                        <ArrowRight size={12} />
                        <span>{rel.relation}</span>
                      </div>
                      <span className={styles.relationNode}>{rel.target}</span>
                      {rel.description && (
                        <span style={{ fontSize: '12px', color: 'var(--text-secondary)', marginLeft: 'auto' }}>
                          {rel.description}
                        </span>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Tab Content: Word Cues */}
            {activeTab === 'cues' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {wordCues.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No word animation cues synchronized for this scene.
                  </div>
                ) : (
                  wordCues.map((cue: any, idx: number) => (
                    <div key={idx} className={styles.elementCard}>
                      <div className={styles.elementHeader}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span className={styles.timePill}>{cue.start_seconds?.toFixed(1)}s – {cue.end_seconds?.toFixed(1)}s</span>
                          <span style={{ fontSize: '15px', fontWeight: 800, color: '#fde047' }}>
                            "{cue.word}"
                          </span>
                        </div>
                        <span className={styles.tagPill} style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>
                          🎯 {cue.semantic_intent}
                        </span>
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                        <strong>Target:</strong> {cue.target_element_id}
                      </div>
                      <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                        {cue.visual_treatment}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Tab Content: Motion Hints */}
            {activeTab === 'motion' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {motionHints.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No motion hints specified for this scene.
                  </div>
                ) : (
                  motionHints.map((hint: any, idx: number) => (
                    <div key={idx} className={styles.motionCard}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontWeight: 700, color: 'var(--accent-blue)', textTransform: 'uppercase', fontSize: '12px' }}>
                          🎬 {hint.intent}
                        </span>
                        {hint.element_id && (
                          <span className={styles.relationNode}>{hint.element_id}</span>
                        )}
                      </div>
                      {hint.description && (
                        <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                          {hint.description}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Tab Content: Stock / Media Requirements */}
            {activeTab === 'media' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {mediaReqs.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    100% Motion Graphic scene — no external stock photo/video files required.
                  </div>
                ) : (
                  mediaReqs.map((r: any, idx: number) => (
                    <div key={idx} className={styles.elementCard}>
                      <div className={styles.elementHeader}>
                        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{r.element_id}</span>
                        <span className={styles.tagPill}>{r.kind}</span>
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--accent-cyan)' }}>
                        <strong>Query:</strong> {r.query}
                      </div>
                      {r.alt_queries?.length > 0 && (
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          Alts: {r.alt_queries.join(', ')}
                        </div>
                      )}
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        <strong>Why needed:</strong> {r.why}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        <strong>Motion Fallback:</strong> {r.fallback}
                      </div>
                      {r.ai_prompt && (
                        <div style={{ fontSize: '12px', color: 'var(--accent-cyan)' }}>
                          <strong>AI Prompt:</strong> {r.ai_prompt}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Tab Content: Continuity & Beats */}
            {activeTab === 'continuity' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div className={styles.objectiveCard}>
                  <div className={styles.objectiveCol}>
                    <span className={styles.sectionLabel}>Transition Flow</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', marginTop: '4px' }}>
                      <span className={styles.relationNode}>{continuity.previous_scene_id || 'Start of video'}</span>
                      <ArrowRight size={13} color="var(--text-muted)" />
                      <span className={styles.relationNode} style={{ color: 'var(--accent-cyan)' }}>{scene.scene_id}</span>
                      <ArrowRight size={13} color="var(--text-muted)" />
                      <span className={styles.relationNode}>{continuity.next_scene_id || 'End of video'}</span>
                    </div>
                    {continuity.transition_intent && (
                      <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        <strong>Intent:</strong> {continuity.transition_intent}
                      </div>
                    )}
                  </div>
                  <div className={styles.objectiveCol}>
                    <span className={styles.sectionLabel}>Carried Motifs</span>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
                      {continuity.motifs?.length ? (
                        continuity.motifs.map((motif: string, idx: number) => (
                          <span key={idx} className={styles.tagPill}>{motif}</span>
                        ))
                      ) : (
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>No shared motifs</span>
                      )}
                    </div>
                  </div>
                </div>

                {beats.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <span className={styles.sectionLabel}>Internal Scene Beats</span>
                    {beats.map((b: any, idx: number) => (
                      <div key={idx} className={styles.motionCard}>
                        <span className={styles.timePill}>{b.start_seconds?.toFixed(1)}s – {b.end_seconds?.toFixed(1)}s</span>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{b.description}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button type="button" className={styles.closeFooterButton} onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
