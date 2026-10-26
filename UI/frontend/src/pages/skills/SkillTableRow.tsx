import React from 'react';
import styles from './SkillTableRow.module.css';
import { Cpu, Eye, Trash2, Clock, CheckCircle2 } from 'lucide-react';

export interface SkillTableRowProps {
  skill: any;
  onView: (skill: any) => void;
  onDeleteRequest: (skill: any) => void;
  formatRelativeTime: (iso?: string | null) => string;
}

export const SkillTableRow: React.FC<SkillTableRowProps> = ({
  skill,
  onView,
  onDeleteRequest,
  formatRelativeTime
}) => {
  const isAgentSkill = skill.domain === 'agent_workflows' || skill.metadata?.is_agent_skill;
  const relativeTime = formatRelativeTime(skill.last_used_at);
  const isNeverUsed = !skill.last_used_at;

  return (
    <tr
      className={styles.row}
      onClick={() => onView(skill)}
      data-testid={`skill-row-${skill.skill_id}`}
    >
      {/* Skill ID & Name */}
      <td className={styles.td}>
        <div className={styles.skillMain}>
          <div className={styles.iconBox}>
            <Cpu size={16} />
          </div>
          <div>
            <div className={styles.skillTitle} data-testid={`skill-name-${skill.skill_id}`}>
              {skill.name}
            </div>
            <div className={styles.skillId}>{skill.skill_id}</div>
          </div>
        </div>
      </td>

      {/* Domain / Category */}
      <td className={styles.td}>
        <span
          className={`${styles.domainBadge} ${isAgentSkill ? styles.agentDomainBadge : ''}`}
        >
          {isAgentSkill ? '🤖 ' : '🎬 '}
          {skill.domain ? skill.domain.replace(/_/g, ' ') : 'general'}
        </span>
      </td>

      {/* Version & Status */}
      <td className={styles.td}>
        <span className={styles.versionBadge}>
          <CheckCircle2 size={11} />
          v{skill.version || '1.0.0'}
        </span>
      </td>

      {/* Last Used Timestamp */}
      <td className={styles.td}>
        <div className={`${styles.lastUsed} ${isNeverUsed ? styles.neverUsed : ''}`}>
          <Clock size={12} />
          <span title={skill.last_used_at ? new Date(skill.last_used_at).toLocaleString() : 'Never executed'}>
            {relativeTime}
          </span>
        </div>
      </td>

      {/* Actions */}
      <td className={styles.td} style={{ textAlign: 'right' }}>
        <div className={styles.actionsGroup} onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => onView(skill)}
            className={styles.viewBtn}
            title="View Full Skill Details & Instructions"
            data-testid={`view-skill-btn-${skill.skill_id}`}
          >
            <Eye size={13} />
            <span>View</span>
          </button>

          <button
            onClick={() => onDeleteRequest(skill)}
            className={styles.deleteBtn}
            title="Delete Skill"
            data-testid={`delete-skill-btn-${skill.skill_id}`}
          >
            <Trash2 size={13} />
            <span>Delete</span>
          </button>
        </div>
      </td>
    </tr>
  );
};
