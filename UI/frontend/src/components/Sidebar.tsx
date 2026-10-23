import React from 'react';
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
  Edit3,
  ScrollText
} from 'lucide-react';

interface SidebarProps {
  activeView: 'dashboard' | 'pipeline' | 'projects' | 'agents' | 'skills' | 'diagnostics' | 'audio-input' | 'visual-editor' | 'llm' | 'work-log';
  setActiveView: (view: 'dashboard' | 'pipeline' | 'projects' | 'agents' | 'skills' | 'diagnostics' | 'audio-input' | 'visual-editor' | 'llm' | 'work-log') => void;
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
      id: 'visual-editor',
      label: 'Visual AI Editor',
      icon: Edit3,
      view: 'visual-editor' as const
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
    <aside style={{
      width: collapsed ? '72px' : '230px',
      backgroundColor: 'var(--sidebar-bg)',
      color: 'var(--sidebar-text)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      height: '100%',
      maxHeight: '100vh',
      transition: 'width 0.2s cubic-bezier(0.2, 0, 0, 1), background-color 0.2s ease, border-color 0.2s ease',
      borderRight: '1px solid var(--sidebar-border)',
      zIndex: 100,
      userSelect: 'none',
      overflow: 'hidden'
    }}>
      {/* Brand Header matching logoipsum from reference image */}
      <div style={{
        height: '64px',
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        padding: collapsed ? '0 20px' : '0 24px',
        gap: '12px',
        borderBottom: '1px solid var(--sidebar-border)'
      }}>
        {/* Geometric logo mark */}
        <div style={{
          width: '32px',
          height: '32px',
          borderRadius: '8px',
          background: 'linear-gradient(135deg, #1890FF 0%, #0050B3 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          boxShadow: '0 2px 8px rgba(24, 144, 255, 0.35)'
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>

        {!collapsed && (
          <div style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>
            <div style={{
              fontSize: '18px',
              fontWeight: 800,
              letterSpacing: '-0.5px',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-sans)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <span>logoipsum</span>
              <span style={{ 
                fontSize: '9px', 
                backgroundColor: 'rgba(24, 144, 255, 0.25)', 
                color: '#40A9FF', 
                padding: '1px 5px', 
                borderRadius: '4px',
                fontWeight: 700
              }}>v2.0</span>
            </div>
          </div>
        )}
      </div>

      {/* Vertical Navigation Menu matching reference image */}
      <nav style={{
        flex: 1,
        padding: '16px 0',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        overflowY: 'auto',
        overflowX: 'hidden'
      }}>
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
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '14px',
                width: '100%',
                padding: collapsed ? '12px 0' : '12px 24px',
                justifyContent: collapsed ? 'center' : 'flex-start',
                backgroundColor: isActive ? '#1890FF' : 'transparent',
                color: isActive ? '#FFFFFF' : 'var(--sidebar-text)',
                border: 'none',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: isActive ? 600 : 400,
                transition: 'background-color 0.15s ease, color 0.15s ease',
                position: 'relative',
                textAlign: 'left'
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'var(--sidebar-hover-bg)';
                  e.currentTarget.style.color = 'var(--text-primary)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = 'var(--sidebar-text)';
                }
              }}
            >
              <Icon size={18} strokeWidth={isActive ? 2.3 : 1.8} style={{ flexShrink: 0 }} />
              {!collapsed && (
                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.label}
                </span>
              )}
            </button>
            </React.Fragment>
          );
        })}
      </nav>

      {/* Sidebar Footer with System Guard Status */}
      <div style={{
        flexShrink: 0,
        padding: collapsed ? '12px 8px' : '16px 20px',
        borderTop: '1px solid var(--sidebar-footer-border)',
        backgroundColor: 'var(--sidebar-footer-bg)',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}>

        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--sidebar-text)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: collapsed ? 'center' : 'flex-start',
              gap: '8px',
              fontSize: '12px',
              padding: '6px 0'
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
