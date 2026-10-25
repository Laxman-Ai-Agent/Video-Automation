import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import styles from '../StageDrawer.module.css';

export interface StageRightNavBarProps {
  isFullPage: boolean;
  rightNavCollapsed: boolean;
  setRightNavCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  availableTabs: Array<{ id: string; label: string; icon: React.ReactNode }>;
  activeTab: string;
  setActiveTab: (tabId: any) => void;
  subStepsCount: number;
}

export const StageRightNavBar: React.FC<StageRightNavBarProps> = ({
  isFullPage,
  rightNavCollapsed,
  setRightNavCollapsed,
  availableTabs,
  activeTab,
  setActiveTab,
  subStepsCount
}) => {
  return (
    <aside
      data-testid="stage-right-navbar"
      className={isFullPage ? styles.rightNavbarFixed : styles.rightNavbarDrawer}
      style={{
        width: rightNavCollapsed ? '72px' : '230px',
      }}
    >
      {/* Redesigned sleek top spacing without Stage Views header or icon */}
      <div className={styles.navbarTopSpacer} />

      {/* Vertical Navigation Menu matching Left Sidebar */}
      <nav className={styles.navMenu}>
        {availableTabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const isSubtasks = tab.id === 'subtasks';
          const displayLabel = isSubtasks ? 'Subtasks' : tab.label;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              title={rightNavCollapsed ? tab.label : undefined}
              data-testid={`stage-drawer-tab-${tab.id}`}
              className={`${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
              style={{
                padding: rightNavCollapsed ? '10px 0' : '10px 14px',
                justifyContent: rightNavCollapsed ? 'center' : 'flex-start',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                {tab.icon}
              </span>
              {!rightNavCollapsed && (
                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {displayLabel}
                </span>
              )}
              {!rightNavCollapsed && isSubtasks && subStepsCount > 0 && (
                <span className={styles.tabBadge}>
                  {subStepsCount}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Sidebar Footer with Collapse Toggle matching Left Sidebar */}
      <div 
        className={styles.navbarFooter}
        style={{ justifyContent: rightNavCollapsed ? 'center' : 'flex-end' }}
      >
        <button
          onClick={() => setRightNavCollapsed(!rightNavCollapsed)}
          data-testid="stage-right-sidebar-collapse-btn"
          title={rightNavCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          className={styles.collapseBtn}
          style={{ justifyContent: rightNavCollapsed ? 'center' : 'space-between' }}
        >
          {rightNavCollapsed ? (
            <ChevronLeft size={16} />
          ) : (
            <>
              <span>Collapse Sidebar</span>
              <ChevronRight size={16} />
            </>
          )}
        </button>
      </div>
    </aside>
  );
};
