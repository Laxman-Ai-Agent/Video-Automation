import React from 'react';
import styles from './Sidebar.module.css';
import { 
  LayoutDashboard, 
  FolderKanban, 
  CheckCircle, 
  Users, 
  Sparkles, 
  ChevronLeft, 
  ChevronRight,
  ShieldCheck,
  Zap,
  PlusCircle,
  FileAudio,
  ScrollText
} from 'lucide-react';

interface SidebarProps {
  activeView: 'dashboard' | 'pipeline' | 'projects' | 'agents' | 'skills' | 'diagnostics' | 'audio-input' | 'llm' | 'work-log';
  setActiveView: (view: 'dashboard' | 'pipeline' | 'projects' | 'agents' | 'skills' | 'diagnostics' | 'audio-input' | 'llm' | 'work-log') => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  pipelineTab?: string;
  onSelectNewProject?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeView,
  setActiveView,
  collapsed = false,
  onToggleCollapse,
  pipelineTab = 'flow',
  onSelectNewProject
}) => {

  const navItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
      view: 'dashboard' as const
    },
    {
      id: 'pipeline',
      label: 'New Project',
      icon: CheckCircle,
      view: 'pipeline' as const
    },
    {
      id: 'projects',
      label: 'Projects',
      icon: FolderKanban,
      view: 'projects' as const
    },
    {
      id: 'agents',
      label: '20 Agents',
      icon: Users,
      view: 'agents' as const
    },
    {
      id: 'skills',
      label: 'Skills',
      icon: Sparkles,
      view: 'skills' as const
    },
    {
      id: 'work-log',
      label: 'Work Log',
      icon: ScrollText,
      view: 'work-log' as const
    }
  ];

  return (
    <aside
      className={styles.sidebar}
      style={{
        width: collapsed ? '72px' : '230px'
      }}
    >
      {/* Brand Header matching logoipsum from reference image */}
      <div
        className={styles.brandHeader}
        style={{
          padding: collapsed ? '0 20px' : '0 24px'
        }}
      >
        {/* Geometric logo mark */}
        <div className={styles.logoIcon}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>

        {!collapsed && (
          <div style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>
            <div className={styles.brandTitle}>
              <span>logoipsum</span>
              <span className={styles.versionBadge}>v2.0</span>
            </div>
          </div>
        )}
      </div>

      {/* Vertical Navigation Menu matching reference image */}
      <nav className={styles.menuNav}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isPipelineItem = item.id === 'pipeline';
          const isActive = isPipelineItem 
            ? (activeView === 'pipeline' || activeView === 'audio-input')
            : activeView === item.view;

          const handleClick = () => {
            if (isPipelineItem) {
              if (onSelectNewProject) {
                onSelectNewProject();
              } else {
                setActiveView('pipeline');
              }
            } else {
              setActiveView(item.view);
            }
          };

          return (
            <React.Fragment key={item.id}>
            <button
              onClick={handleClick}
              title={collapsed ? item.label : undefined}
              data-testid={isPipelineItem ? 'sidebar-nav-pipeline' : `sidebar-nav-${item.id}`}
              className={`${styles.navButton} ${isActive ? styles.navButtonActive : ''}`}
              style={{
                padding: collapsed ? '12px 0' : '12px 24px',
                justifyContent: collapsed ? 'center' : 'flex-start'
              }}
            >
              <Icon size={18} strokeWidth={isActive ? 2.3 : 1.8} style={{ flexShrink: 0 }} />
              {!collapsed && (
                <span className={styles.navLabel}>
                  {item.label}
                </span>
              )}
            </button>
            </React.Fragment>
          );
        })}
      </nav>

      {/* Sidebar Footer with System Guard Status */}
      <div
        className={styles.sidebarFooter}
        style={{
          padding: collapsed ? '12px 8px' : '16px 20px'
        }}
      >
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className={styles.collapseButton}
            style={{
              justifyContent: collapsed ? 'center' : 'flex-start'
            }}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            {!collapsed && <span>Collapse Sidebar</span>}
          </button>
        )}
      </div>
    </aside>
  );
};
