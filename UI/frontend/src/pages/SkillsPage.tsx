import React, { useMemo, useState, useEffect } from 'react';
import styles from './SkillsPage.module.css';
import { Cpu, Search, RefreshCw } from 'lucide-react';
import { deleteSkill, fetchSkills } from '../services/api';
import { SkillTableRow } from './skills/SkillTableRow';
import { SkillDetailModal } from './skills/SkillDetailModal';
import { DeleteSkillModal } from './skills/DeleteSkillModal';

interface SkillsPageProps {
  skills: any[];
}

export function formatRelativeTime(isoString?: string | null): string {
  if (!isoString) return 'Never used';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  if (isNaN(diffMs) || diffMs < 0) return 'Just now';

  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return 'Just now';

  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;

  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}

export const SkillsPage: React.FC<SkillsPageProps> = ({ skills: initialSkills }) => {
  const [skills, setSkills] = useState<any[]>(initialSkills || []);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedDomain, setSelectedDomain] = useState<string>('all');
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Modals state
  const [viewingSkill, setViewingSkill] = useState<any | null>(null);
  const [skillToDelete, setSkillToDelete] = useState<{ skill_id: string; name: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (initialSkills && initialSkills.length > 0) {
      setSkills(initialSkills);
    }
  }, [initialSkills]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const fresh = await fetchSkills();
      if (fresh) setSkills(fresh);
    } catch {
      // keep current
    } finally {
      setIsRefreshing(false);
    }
  };

  const domains = useMemo(() => {
    return ['all', ...Array.from(new Set(skills.map((s) => s.domain).filter(Boolean)))];
  }, [skills]);

  const filteredSkills = useMemo(() => {
    return skills.filter((s) => {
      if (selectedDomain !== 'all' && s.domain !== selectedDomain) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const id = String(s.skill_id || '').toLowerCase();
        const name = String(s.name || '').toLowerCase();
        const summary = String(s.summary || '').toLowerCase();
        const domain = String(s.domain || '').toLowerCase();
        const caps = (s.capabilities || []).join(' ').toLowerCase();
        return id.includes(q) || name.includes(q) || summary.includes(q) || domain.includes(q) || caps.includes(q);
      }
      return true;
    });
  }, [skills, selectedDomain, searchQuery]);

  const handleConfirmDelete = async () => {
    if (!skillToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteSkill(skillToDelete.skill_id);
      setDeleteSuccess(`Skill "${skillToDelete.name}" was permanently deleted.`);
      setSkills((prev) => prev.filter((s) => s.skill_id !== skillToDelete.skill_id));
      if (viewingSkill?.skill_id === skillToDelete.skill_id) {
        setViewingSkill(null);
      }
      setSkillToDelete(null);
      setTimeout(() => setDeleteSuccess(null), 4000);
    } catch (err: any) {
      setDeleteError(err?.message || 'Failed to delete skill.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className={styles.container} data-testid="skills-page">
      {/* Header: Title, Search, Refresh */}
      <div className={styles.header}>
          <div>
            <div className={styles.titleGroup}>
              <Cpu size={22} color="var(--accent-blue)" />
              <h2 className={styles.title} data-testid="skills-count-title">
                Skills &amp; Capabilities Library
              </h2>
              <span className={styles.countBadge} data-testid="skills-count-badge">
                {filteredSkills.length} of {skills.length} Total
              </span>
            </div>
            <p className={styles.subtitle}>
              Audited video generation capabilities and agent workflows. Click on any row or View to inspect full details, or Delete to remove.
            </p>
          </div>

          {/* Search and Refresh Bar */}
          <div className={styles.searchBar}>
            <div className={styles.searchWrapper}>
              <Search size={14} color="var(--text-muted)" />
              <input
                type="text"
                placeholder="Search by skill name, ID, domain..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className={styles.searchInput}
                data-testid="skills-search-input"
              />
            </div>

            <button
              onClick={handleRefresh}
              title="Refresh Skills"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '8px',
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-card)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
              }}
              data-testid="skills-refresh-btn"
            >
              <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {/* Domain Filter Pills */}
        <div className={styles.filterBar} data-testid="skills-filter-bar">
          {domains.map((d) => {
            const isSelected = selectedDomain === d;
            const label = d === 'all' ? 'All Skills' : d.replace(/_/g, ' ');
            return (
              <button
                key={d}
                data-testid={`filter-domain-${d}`}
                onClick={() => setSelectedDomain(d)}
                className={`${styles.filterBtn} ${isSelected ? styles.filterBtnActive : ''}`}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Alerts */}
        {deleteSuccess && (
          <div className={styles.alertSuccess} data-testid="skill-delete-success-banner">
            {deleteSuccess}
          </div>
        )}

        {deleteError && (
          <div className={styles.alertError} data-testid="skill-delete-error-banner">
            {deleteError}
          </div>
        )}

        {/* Table View */}
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>Skill ID &amp; Name</th>
                <th className={styles.th} style={{ width: '160px' }}>Type / Domain</th>
                <th className={styles.th} style={{ width: '110px' }}>Version</th>
                <th className={styles.th} style={{ width: '150px' }}>Last Used</th>
                <th className={styles.th} style={{ width: '180px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredSkills.map((skill) => (
                <SkillTableRow
                  key={skill.skill_id}
                  skill={skill}
                  onView={(s) => setViewingSkill(s)}
                  onDeleteRequest={(s) => setSkillToDelete({ skill_id: s.skill_id, name: s.name || s.skill_id })}
                  formatRelativeTime={formatRelativeTime}
                />
              ))}

              {filteredSkills.length === 0 && (
                <tr>
                  <td colSpan={5} className={styles.emptyState}>
                    No skills found matching your search or selected domain filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

      {/* Detail Pop-up Modal */}
      {viewingSkill && (
        <SkillDetailModal
          skill={viewingSkill}
          onClose={() => setViewingSkill(null)}
          onDeleteRequest={(s) => setSkillToDelete({ skill_id: s.skill_id, name: s.name || s.skill_id })}
          formatRelativeTime={formatRelativeTime}
        />
      )}

      {/* Delete Confirmation Modal */}
      {skillToDelete && (
        <DeleteSkillModal
          skill={skillToDelete}
          isDeleting={isDeleting}
          onCancel={() => setSkillToDelete(null)}
          onConfirm={handleConfirmDelete}
        />
      )}
    </div>
  );
};
