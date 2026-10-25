import React from 'react';
import styles from './Header.module.css';
import { PipelineIssue } from '../types/pipeline';
import { 
  Menu, 
  Search, 
  HelpCircle, 
  Bell, 
  AlertCircle,
  Cpu,
  Moon,
  Sun
} from 'lucide-react';

interface HeaderProps {
  onToggleSidebar?: () => void;
  onNewProject?: () => void;
  backendHealthy: boolean;
  llmHealthy?: boolean;
  llmConnecting?: boolean;
  activeLlmCount: number;
  projectCount: number;
  activeProjectId?: string;
  theme?: 'dark' | 'light';
  onToggleTheme?: () => void;
  issues?: PipelineIssue[];
  onOpenIssues?: () => void;
  onOpenLlm?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onToggleSidebar,
  onNewProject,
  backendHealthy,
  llmHealthy = false,
  llmConnecting = false,
  activeLlmCount,
  projectCount,
  activeProjectId,
  theme = 'dark',
  onToggleTheme,
  issues = [],
  onOpenIssues,
  onOpenLlm
}) => {
  const errorCount = issues.filter((i) => i.severity === 'error' || i.severity === 'stuck').length;
  const warningCount = issues.filter((i) => i.severity === 'warning').length;

  return (
    <header className={styles.header}>
      {/* Left side: Hamburger collapse button & Title / Breadcrumb */}
      <div className={styles.leftSection}>
        <button
          onClick={onToggleSidebar}
          className={styles.iconButton}
          title="Toggle Navigation"
        >
          <Menu size={20} strokeWidth={2} />
        </button>

        <div className={styles.breadcrumb}>
          <span className={styles.breadcrumbPrefix}>Workspace /</span>
          <span className={styles.breadcrumbTitle}>
            {activeProjectId ? `Project: ${activeProjectId}` : 'Autonomous Pipeline Studio'}
          </span>
        </div>
      </div>

      {/* Right side: Navigation group (5 tabs), Health, In-flight LLM, Theme, Search, Help, Notifications, User */}
      <div className={styles.rightSection}>
        {/* Issues: real errors, stuck stages and warnings of this project; blinks while any is unresolved */}
        {onOpenIssues && (
          <button
            onClick={onOpenIssues}
            data-testid="issues-button"
            title={issues.length ? `${errorCount} error(s), ${warningCount} warning(s)` : 'No issues detected'}
            className={errorCount > 0 ? 'issue-blink' : (warningCount > 0 ? 'issue-blink-amber' : undefined)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px', height: '28px', padding: '0 12px', borderRadius: '9999px',
              fontSize: '12px', fontWeight: 700, cursor: 'pointer',
              color: errorCount > 0 ? '#FCA5A5' : (warningCount > 0 ? '#FBBF24' : '#9CA3AF'),
              backgroundColor: errorCount > 0 ? 'rgba(239, 68, 68, 0.12)' : (warningCount > 0 ? 'rgba(245, 158, 11, 0.12)' : 'rgba(140, 140, 140, 0.12)'),
              border: `1px solid ${errorCount > 0 ? 'rgba(239, 68, 68, 0.45)' : (warningCount > 0 ? 'rgba(245, 158, 11, 0.45)' : 'rgba(140, 140, 140, 0.35)')}`
            }}
          >
            <AlertCircle size={14} />
            <span>Issues</span>
            <span data-testid="issues-count">{errorCount > 0 ? `${errorCount}E` : ''}{errorCount > 0 && warningCount > 0 ? ' · ' : ''}{warningCount > 0 ? `${warningCount}W` : ''}{issues.length === 0 ? '0' : ''}</span>
          </button>
        )}

        {/* 1. Real-time LLM Connectivity Status Indicator: opens the LLM connection page */}
        <button
          type="button"
          onClick={onOpenLlm}
          data-testid="llm-status-pill"
          title={(llmHealthy && backendHealthy ? "LLM is online, connected and responding" : "LLM is offline or unreachable") + " - click to set up the LLM connection"}
          className={styles.statusPill}
          style={{
            backgroundColor: (llmHealthy && backendHealthy) ? 'rgba(16, 185, 129, 0.15)' : 'rgba(140, 140, 140, 0.14)',
            border: `1px solid ${(llmHealthy && backendHealthy) ? 'rgba(16, 185, 129, 0.45)' : 'rgba(140, 140, 140, 0.35)'}`,
            color: (llmHealthy && backendHealthy) ? '#10B981' : '#8C8C8C'
          }}
        >
          {(llmHealthy && backendHealthy) ? (
            <>
              <span
                className={`${styles.statusDot} ${llmConnecting ? 'animate-blink-indicator' : ''}`}
                style={{ backgroundColor: '#10B981' }}
              />
              <span>LLM</span>
            </>
          ) : (
            <>
              <span
                className={`${styles.statusDot} ${llmConnecting ? 'animate-blink-indicator' : ''}`}
                style={{ backgroundColor: '#8C8C8C' }} 
              />
              <span>LLM OFF</span>
            </>
          )}
        </button>

        {/* 2. Real-time Backend Server Status Indicator */}
        <div 
          data-testid="backend-status-pill"
          title={backendHealthy ? "Backend server is running and healthy" : "Backend server is stopped or unreachable"}
          className={styles.statusPill}
          style={{
            backgroundColor: backendHealthy ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `1px solid ${backendHealthy ? 'rgba(16, 185, 129, 0.45)' : 'rgba(239, 68, 68, 0.45)'}`,
            color: backendHealthy ? '#10B981' : '#EF4444',
            cursor: 'default'
          }}
        >
          {backendHealthy ? (
            <>
              <span 
                className={`${styles.statusDot} animate-blink-indicator`}
                style={{ backgroundColor: '#10B981' }} 
              />
              <span>SERVER ONLINE</span>
            </>
          ) : (
            <>
              <span 
                className={styles.statusDot}
                style={{ 
                  backgroundColor: '#EF4444',
                  boxShadow: '0 0 5px rgba(239, 68, 68, 0.6)'
                }} 
              />
              <span>NO SERVER</span>
            </>
          )}
        </div>

        {/* LLM in-flight requests indicator */}
        {activeLlmCount > 0 && (
          <div className={styles.inFlightBadge}>
            <Cpu size={13} className="animate-spin" />
            <span>LLM: {activeLlmCount} in flight</span>
          </div>
        )}

        {/* Theme Toggle (Dark / Light) */}
        {onToggleTheme && (
          <button
            onClick={onToggleTheme}
            data-testid="theme-toggle-btn"
            className={styles.roundIconButton}
            title={`Switch to ${theme === 'dark' ? 'Light Mode' : 'Dark Theme'}`}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        )}

        {/* Search icon */}
        <button
          className={styles.roundIconButton}
          title="Search stages, logs, or agents"
        >
          <Search size={18} strokeWidth={2} />
        </button>

        {/* Help icon */}
        <button
          className={styles.roundIconButton}
          title="Pipeline Documentation & Operator Guide"
        >
          <HelpCircle size={18} strokeWidth={2} />
        </button>

        {/* Notification Bell with Badge '8' */}
        <div className={styles.notificationWrapper}>
          <button
            className={styles.roundIconButton}
            title="8 System Notifications"
          >
            <Bell size={18} strokeWidth={2} />
          </button>
          <span className={styles.notificationBadge}>
            8
          </span>
        </div>

        {/* User Profile Avatar with Name John */}
        <div className={styles.userProfile}>
          <div className={styles.userAvatar}>
            J
          </div>
          <span className={styles.userName}>
            John
          </span>
        </div>
      </div>
    </header>
  );
};
