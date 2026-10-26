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
  Target
} from 'lucide-react';
import { HeroBadge } from './VisualPlanningView';

export interface VisualSceneModalProps {
  scene: any;
  onClose: () => void;
}

type TabKey = 'elements' | 'relationships' | 'cues' | 'motion' | 'media' | 'continuity';

export const VisualSceneModal: React.FC<VisualSceneModalProps> = ({ scene, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabKey>('elements');

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

  return (
    <div className={styles.overlay} onClick={onClose} data-testid="visual-scene-modal">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h3 className={styles.sceneTitle}>
              <Layers size={18} color="var(--accent-cyan)" />
              {scene.scene_id}
            </h3>
            {narration.start_seconds !== undefined && (
              <span className={styles.timePill}>
                <Clock size={11} />
                {narration.start_seconds.toFixed(1)}s – {narration.end_seconds?.toFixed(1)}s
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
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className={styles.body}>
          {/* Narration Section */}
          <div className={styles.narrationBox} data-testid="scene-narration-box">
            <div className={styles.narrationHeader}>
              <Volume2 size={14} />
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

          {/* Objective & Concept Section */}
          <div className={styles.objectiveCard}>
            <div className={styles.objectiveCol}>
              <span className={styles.sectionLabel}>Core Meaning & Takeaway</span>
              <div className={styles.objectiveValue}>
                <strong>{objective.core_meaning || 'Meaning not specified'}</strong>
              </div>
              {objective.audience_takeaway && (
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
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
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Focus: <strong>{concept.primary_focus}</strong> {concept.representation ? `(${concept.representation})` : ''}
                </div>
              )}
            </div>
          </div>

          {/* Quick Stats Row */}
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
              <div className={styles.statLabel}>Graphics</div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statValue}>{counts.image ?? 0}</div>
              <div className={styles.statLabel}>Images</div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statValue}>{counts.video ?? 0}</div>
              <div className={styles.statLabel}>Videos</div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statValue}>{motionHints.length}</div>
              <div className={styles.statLabel}>Motion</div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statValue}>{relationships.length}</div>
              <div className={styles.statLabel}>Relations</div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statValue}>{wordCues.length}</div>
              <div className={styles.statLabel}>Word Cues</div>
            </div>
          </div>

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
              Stock Requirements
              <span className={styles.tabBadge}>{mediaReqs.length}</span>
            </button>
            <button
              type="button"
              className={`${styles.navTab} ${activeTab === 'continuity' ? styles.navTabActive : ''}`}
              onClick={() => setActiveTab('continuity')}
            >
              <Target size={13} />
              Continuity &amp; Beats
            </button>
          </div>

          {/* Tab Content Panels */}
          {activeTab === 'elements' && (
            <div className={styles.elementsList}>
              {elements.length === 0 ? (
                <div className={styles.emptySection}>No elements defined for this scene.</div>
              ) : (
                elements.map((e: any) => (
                  <div key={e.element_id} className={styles.elementCard}>
                    <div className={styles.elementHeader}>
                      <div className={styles.elementBadges}>
                        <span className={`${styles.elementTypeBadge} ${getTypeClass(e.type)}`}>
                          {e.type}
                        </span>
                        <span className={styles.elementId}>{e.element_id}</span>
                        {e.role && <span className={styles.tagPill}>Role: {e.role}</span>}
                        {e.depth_layer && <span className={styles.tagPill}>Layer: {e.depth_layer}</span>}
                        {e.placement?.region && <span className={styles.tagPill}>Region: {e.placement.region}</span>}
                      </div>
                      {e.text_purpose && (
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          Purpose: {e.text_purpose}
                        </span>
                      )}
                    </div>

                    {e.content ? (
                      <div className={styles.elementTextContent}>
                        &ldquo;{e.content}&rdquo;
                      </div>
                    ) : null}

                    {e.visual_description && (
                      <div className={styles.elementContent}>
                        {e.visual_description}
                      </div>
                    )}

                    {e.registry_requirements?.icon && (
                      <div style={{ fontSize: '11.5px', color: 'var(--accent-cyan)' }}>
                        Lucide Icon: <code>{e.registry_requirements.icon}</code>
                      </div>
                    )}

                    {e.media && (
                      <div className={styles.mediaDetails}>
                        <div><strong>Stock Query:</strong> &ldquo;{e.media.query}&rdquo;</div>
                        {e.media.alt_queries?.length > 0 && (
                          <div><strong>Alt Queries:</strong> {e.media.alt_queries.join(', ')}</div>
                        )}
                        <div><strong>Fallback Graphic:</strong> {e.media.fallback}</div>
                        {e.media.ai_prompt && (
                          <div><strong>AI Prompt:</strong> {e.media.ai_prompt}</div>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'relationships' && (
            <div className={styles.relationshipsList}>
              {relationships.length === 0 ? (
                <div className={styles.emptySection}>No explicit element relationships defined in this scene.</div>
              ) : (
                relationships.map((r: any, idx: number) => (
                  <div key={idx} className={styles.relationRow}>
                    <span className={styles.relationNode}>{r.source}</span>
                    <span className={styles.relationArrow}>
                      <ArrowRight size={12} />
                      {r.relation}
                    </span>
                    <span className={styles.relationNode}>{r.target}</span>
                    {r.description && <span className={styles.relationDesc}>{r.description}</span>}
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'cues' && (
            <div className={styles.cuesList}>
              {wordCues.length === 0 ? (
                <div className={styles.emptySection}>No word-level animation cues defined in this scene.</div>
              ) : (
                wordCues.map((c: any, idx: number) => (
                  <div key={idx} className={styles.cueCard}>
                    <div>
                      <div className={styles.cueWord}>&ldquo;{c.word}&rdquo;</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {c.start_seconds?.toFixed(2)}s – {c.end_seconds?.toFixed(2)}s
                      </div>
                    </div>
                    <div>
                      <span className={styles.cueIntent}>{c.semantic_intent}</span>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                        Target: {c.target_element_id}
                      </div>
                    </div>
                    <div className={styles.cueTreatment}>
                      {c.visual_treatment}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'motion' && (
            <div className={styles.motionList}>
              {motionHints.length === 0 ? (
                <div className={styles.emptySection}>No motion hints defined for this scene.</div>
              ) : (
                motionHints.map((m: any, idx: number) => (
                  <div key={idx} className={styles.motionCard}>
                    <span className={styles.relationNode}>{m.element_id}</span>
                    <span className={styles.motionIntent}>{m.intent}</span>
                    <span style={{ color: 'var(--text-secondary)' }}>
                      {m.description || 'Semantic animation motion hint'}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'media' && (
            <div className={styles.elementsList}>
              {mediaReqs.length === 0 ? (
                <div className={styles.emptySection}>No real media requirements (images or videos) needed for this scene.</div>
              ) : (
                mediaReqs.map((r: any, idx: number) => (
                  <div key={idx} className={styles.elementCard}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className={`${styles.elementTypeBadge} ${r.media_type === 'video' ? styles.typeVideo : styles.typeImage}`}>
                        {r.media_type}
                      </span>
                      <strong>Search Query:</strong> &ldquo;{r.query}&rdquo;
                    </div>
                    {r.alt_queries?.length > 0 && (
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Alternative queries: {r.alt_queries.join(', ')}
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

          {activeTab === 'continuity' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div className={styles.objectiveCard}>
                <div className={styles.objectiveCol}>
                  <span className={styles.sectionLabel}>Transition Flow</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', marginTop: '4px' }}>
                    <span className={styles.relationNode}>{continuity.previous_scene_id || 'Start of video'}</span>
                    <ArrowRight size={14} color="var(--text-muted)" />
                    <span className={styles.relationNode} style={{ color: 'var(--accent-cyan)' }}>{scene.scene_id}</span>
                    <ArrowRight size={14} color="var(--text-muted)" />
                    <span className={styles.relationNode}>{continuity.next_scene_id || 'End of video'}</span>
                  </div>
                  {continuity.transition_intent && (
                    <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '6px' }}>
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
