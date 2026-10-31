import React from 'react';
import styles from '../SkillsPage.module.css';
import { ChevronDown } from 'lucide-react';
import { SkillTableRow } from './SkillTableRow';

export interface SkillSectionCardProps {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  iconThemeClass: string;
  badgeThemeClass: string;
  skills: any[];
  isCollapsed: boolean;
  onToggleCollapse: (id: string) => void;
  onView: (skill: any) => void;
  onDeleteRequest: (skill: any) => void;
  formatRelativeTime: (iso?: string | null) => string;
}

export const SkillSectionCard: React.FC<SkillSectionCardProps> = ({
  id,
  title,
  description,
  icon: IconComponent,
  iconThemeClass,
  badgeThemeClass,
  skills,
  isCollapsed,
  onToggleCollapse,
  onView,
  onDeleteRequest,
  formatRelativeTime,
}) => {
  return (
    <div className={styles.sectionCard} data-testid={`skill-section-${id}`}>
      {/* Collapsible Section Header */}
      <div
        className={styles.sectionHeader}
        onClick={() => onToggleCollapse(id)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggleCollapse(id);
          }
        }}
        data-testid={`skill-section-header-${id}`}
      >
        <div className={styles.sectionHeaderLeft}>
          <div className={`${styles.sectionIconWrapper} ${iconThemeClass}`}>
            <IconComponent size={18} />
          </div>
          <div className={styles.sectionTitleGroup}>
            <div className={styles.sectionTitleRow}>
              <h3 className={styles.sectionTitle}>{title}</h3>
              <span className={`${styles.sectionBadge} ${badgeThemeClass}`}>
                {skills.length} {skills.length === 1 ? 'skill' : 'skills'}
              </span>
            </div>
            <p className={styles.sectionDesc}>{description}</p>
          </div>
        </div>

        <div className={styles.sectionHeaderRight}>
          <ChevronDown
            size={18}
            className={`${styles.chevronIcon} ${!isCollapsed ? styles.chevronExpanded : ''}`}
          />
        </div>
      </div>

      {/* Table Content */}
      {!isCollapsed && (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>Skill ID &amp; Name</th>
                <th className={`${styles.th} ${styles.thDomain}`}>Type / Domain</th>
                <th className={`${styles.th} ${styles.thVersion}`}>Version</th>
                <th className={`${styles.th} ${styles.thLastUsed}`}>Last Used</th>
                <th className={`${styles.th} ${styles.thActions}`}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {skills.map((skill) => (
                <SkillTableRow
                  key={skill.skill_id}
                  skill={skill}
                  onView={onView}
                  onDeleteRequest={onDeleteRequest}
                  formatRelativeTime={formatRelativeTime}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
