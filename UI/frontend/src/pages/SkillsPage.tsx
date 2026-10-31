import React, { useMemo, useState, useEffect } from 'react';
import styles from './SkillsPage.module.css';
import { Cpu, Search, RefreshCw, Film, BarChart3, Zap, Bot } from 'lucide-react';
import { deleteSkill, fetchSkills } from '../services/api';
import { SkillDetailModal } from './skills/SkillDetailModal';
import { DeleteSkillModal } from './skills/DeleteSkillModal';
import { SkillSectionCard } from './skills/SkillSectionCard';

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

interface SectionDefinition {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  iconThemeClass: string;
  badgeThemeClass: string;
  domains: string[];
}

const SECTION_DEFINITIONS: SectionDefinition[] = [
  {
    id: 'video_motion',
    title: 'Video & Motion Graphics Engine',
    description: 'Remotion animations, kinetic typography, spring dynamics, camera moves, and scene transitions',
    icon: Film,
    iconThemeClass: styles.iconWrapperBlue,
    badgeThemeClass: styles.badgeBlue,
    domains: ['motion', 'remotion', 'motion_animation', 'video_editing', 'timeline'],
  },
  {
    id: 'visual_assets',
    title: 'Dynamic Visual Assets & Data Generators',
    description: 'Interactive charts, SVG maps, infographics, science diagrams, layouts, and visual scene planning',
    icon: BarChart3,
    iconThemeClass: styles.iconWrapperPurple,
    badgeThemeClass: styles.badgePurple,
    domains: ['graphics', 'charts', 'science_visuals', 'layouts', 'validation', 'visual_planning'],
  },
  {
    id: 'automation_qc',
    title: 'Production Automation, Audio & Quality Inspection',
    description: 'Pipeline automation, Whisper audio transcription, Remotion rendering, and automated QC verification',
    icon: Zap,
    iconThemeClass: styles.iconWrapperEmerald,
    badgeThemeClass: styles.badgeEmerald,
    domains: ['qc', 'testing', 'audio', 'transcript', 'rendering', 'external'],
  },
  {
    id: 'agent_workflows',
    title: 'AI Agent Engineering Workflows',
    description: 'Autonomous engineering: systematic debugging, test-driven development, planning, and memory',
    icon: Bot,
    iconThemeClass: styles.iconWrapperAmber,
    badgeThemeClass: styles.badgeAmber,
    domains: ['agent_workflows'],
  },
];

export const SkillsPage: React.FC<SkillsPageProps> = ({ skills: initialSkills }) => {
  const [skills, setSkills] = useState<any[]>(initialSkills || []);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedDomain, setSelectedDomain] = useState<string>('all');
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});

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

  // Partition filtered skills into defined sections
  const sectionedSkills = useMemo(() => {
    const map: Record<string, any[]> = {
      video_motion: [],
      visual_assets: [],
      automation_qc: [],
      agent_workflows: [],
    };

    filteredSkills.forEach((skill) => {
      const domain = skill.domain || '';
      const matched = SECTION_DEFINITIONS.find((sec) => sec.domains.includes(domain));
      if (matched) {
        map[matched.id].push(skill);
      } else {
        // Fallback for unclassified domains
        map.automation_qc.push(skill);
      }
    });

    return map;
  }, [filteredSkills]);

  const toggleSectionCollapse = (sectionId: string) => {
    setCollapsedSections((prev) => ({
      ...prev,
      [sectionId]: !prev[sectionId],
    }));
  };

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
            Organized library of Remotion motion graphics, dynamic asset generators, automation pipelines, and engineering workflows.
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
            className={styles.refreshBtn}
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

      {/* Section-wise Cards */}
      <div className={styles.sectionsContainer}>
        {SECTION_DEFINITIONS.map((sec) => {
          const items = sectionedSkills[sec.id] || [];
          if (items.length === 0) return null;

          return (
            <SkillSectionCard
              key={sec.id}
              id={sec.id}
              title={sec.title}
              description={sec.description}
              icon={sec.icon}
              iconThemeClass={sec.iconThemeClass}
              badgeThemeClass={sec.badgeThemeClass}
              skills={items}
              isCollapsed={Boolean(collapsedSections[sec.id])}
              onToggleCollapse={toggleSectionCollapse}
              onView={(s) => setViewingSkill(s)}
              onDeleteRequest={(s) => setSkillToDelete({ skill_id: s.skill_id, name: s.name || s.skill_id })}
              formatRelativeTime={formatRelativeTime}
            />
          );
        })}

        {filteredSkills.length === 0 && (
          <div className={styles.tableWrapper}>
            <div className={styles.emptyState}>
              No skills found matching your search or selected domain filter.
            </div>
          </div>
        )}
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
