import React, { useEffect, useState } from 'react';
import styles from './SkillDetailModal.module.css';
import { X, Clock, Shield, Tag, FileText, Trash2, Copy, Check, Cpu } from 'lucide-react';
import { fetchSkillDetails } from '../../services/api';

export interface SkillDetailModalProps {
  skill: any;
  onClose: () => void;
  onDeleteRequest: (skill: any) => void;
  formatRelativeTime: (iso?: string | null) => string;
}

export const SkillDetailModal: React.FC<SkillDetailModalProps> = ({
  skill,
  onClose,
  onDeleteRequest,
  formatRelativeTime
}) => {
  const [details, setDetails] = useState<any>(skill);
  const [loading, setLoading] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    fetchSkillDetails(skill.skill_id)
      .then((data) => {
        if (mounted && data) {
          setDetails((prev: any) => ({ ...prev, ...data }));
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [skill.skill_id]);

  const isAgentSkill = details.domain === 'agent_workflows' || details.metadata?.is_agent_skill;
  const contentText = details.content || details.instructions || '';

  const handleCopy = () => {
    if (!contentText) return;
    navigator.clipboard.writeText(contentText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className={styles.overlay} onClick={onClose} data-testid="skill-detail-modal">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.titleGroup}>
            <div className={styles.iconBox}>
              <Cpu size={22} />
            </div>
            <div>
              <h3 className={styles.title} data-testid="modal-skill-title">
                {details.name || details.skill_id}
              </h3>
              <div className={styles.idLabel}>ID: {details.skill_id}</div>
            </div>
          </div>
          <button
            onClick={onClose}
            className={styles.closeButton}
            title="Close Modal"
            data-testid="modal-close-btn"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className={styles.body}>
          {/* Metadata Grid */}
          <div className={styles.metaGrid}>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>Type / Domain</span>
              <span className={styles.metaValue}>
                {isAgentSkill ? '🤖 Agent Workflow' : '🎬 Video Engine'}
              </span>
            </div>

            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>
                <Clock size={11} /> Last Used
              </span>
              <span className={styles.metaValue}>
                {formatRelativeTime(details.last_used_at)}
              </span>
            </div>

            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>Version</span>
              <span className={styles.metaValue}>v{details.version || '1.0.0'}</span>
            </div>

            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>
                <Shield size={11} /> License
              </span>
              <span className={styles.metaValue}>{details.license || 'Apache-2.0'}</span>
            </div>
          </div>

          {/* Summary / Description */}
          <div className={styles.section}>
            <span className={styles.sectionTitle}>
              <FileText size={13} /> Description &amp; Scope
            </span>
            <p className={styles.summaryText}>{details.summary || 'No description provided.'}</p>
          </div>

          {/* Capabilities */}
          {details.capabilities && details.capabilities.length > 0 && (
            <div className={styles.section}>
              <span className={styles.sectionTitle}>Capabilities</span>
              <div className={styles.badgeList}>
                {details.capabilities.map((c: string) => (
                  <span key={c} className={styles.tagBadge}>
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Tags */}
          {details.tags && details.tags.length > 0 && (
            <div className={styles.section}>
              <span className={styles.sectionTitle}>
                <Tag size={12} /> Tags
              </span>
              <div className={styles.badgeList}>
                {details.tags.map((t: string) => (
                  <span key={t} className={styles.tagBadge}>
                    #{t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Instructions / Code Content */}
          <div className={styles.section}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span className={styles.sectionTitle}>
                <FileText size={13} /> Instructions / Execution Guide
              </span>
              {contentText && (
                <button
                  onClick={handleCopy}
                  className={styles.closeBtn}
                  style={{ padding: '4px 10px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                  title="Copy Instructions to Clipboard"
                >
                  {copied ? <Check size={12} color="var(--status-completed)" /> : <Copy size={12} />}
                  <span>{copied ? 'Copied!' : 'Copy'}</span>
                </button>
              )}
            </div>

            {loading ? (
              <div className={styles.codeBox}>Loading verified instructions...</div>
            ) : contentText ? (
              <pre className={styles.codeBox}>{contentText}</pre>
            ) : (
              <div className={styles.codeBox} style={{ color: 'var(--text-muted)' }}>
                No standalone markdown instruction file found. Registered via catalog.
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button
            onClick={() => onDeleteRequest(details)}
            className={styles.deleteBtn}
            data-testid="modal-delete-skill-btn"
          >
            <Trash2 size={14} />
            <span>Delete Skill</span>
          </button>

          <button onClick={onClose} className={styles.closeBtn}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
