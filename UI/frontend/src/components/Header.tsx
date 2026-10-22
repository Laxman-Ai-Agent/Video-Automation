import React from 'react';
import { PipelineIssue } from '../types/pipeline';
import { 
  Menu, 
  Search, 
  HelpCircle, 
  Bell, 
  CheckCircle2, 
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
    <header style={{
      height: '64px',
      backgroundColor: 'var(--header-bg)',
      borderBottom: '1px solid var(--header-border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px',
      position: 'relative',
      flexShrink: 0,
      zIndex: 90,
      boxShadow: 'var(--shadow-card)',
      transition: 'background-color 0.2s ease, border-color 0.2s ease'
    }}>
      {/* Left side: Hamburger collapse button & Title / Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <button
          onClick={onToggleSidebar}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-primary)',
            cursor: 'pointer',
            padding: '6px',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background-color 0.15s ease'
          }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-elevated)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          title="Toggle Navigation"
        >
          <Menu size={20} strokeWidth={2} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Workspace /</span>
          <span style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
            {activeProjectId ? `Project: ${activeProjectId}` : 'Autonomous Pipeline Studio'}
          </span>
        </div>
      </div>

      {/* Right side: Navigation group (5 tabs), Health, In-flight LLM, Theme, Search, Help, Notifications, User */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
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
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 10px',
            borderRadius: '9999px',
            backgroundColor: (llmHealthy && backendHealthy) ? 'rgba(16, 185, 129, 0.15)' : 'rgba(140, 140, 140, 0.14)',
            border: `1px solid ${(llmHealthy && backendHealthy) ? 'rgba(16, 185, 129, 0.45)' : 'rgba(140, 140, 140, 0.35)'}`,
            fontSize: '12px',
            fontWeight: 700,
            letterSpacing: '0.2px',
            color: (llmHealthy && backendHealthy) ? '#10B981' : '#8C8C8C',
            cursor: 'pointer',
            fontFamily: 'inherit',
            transition: 'all 0.2s ease'
          }}
        >
          {(llmHealthy && backendHealthy) ? (
            <>
              <span 
                className="animate-blink-indicator"
                style={{ 
                  width: '7px', 
                  height: '7px', 
                  borderRadius: '50%', 
                  backgroundColor: '#10B981',
                  display: 'inline-block',
                  flexShrink: 0
                }} 
              />
              <span>LLM</span>
            </>
          ) : (
            <>
              <span 
                style={{ 
                  width: '7px', 
                  height: '7px', 
                  borderRadius: '50%', 
                  backgroundColor: '#8C8C8C',
                  display: 'inline-block',
                  flexShrink: 0
                }} 
              />
              <span>LLM OFF</span>
            </>
          )}
        </button>

        {/* 2. Real-time Backend Server Status Indicator */}
        <div 
          data-testid="backend-status-pill"
          title={backendHealthy ? "Backend server is running and healthy" : "Backend server is stopped or unreachable"}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 10px',
            borderRadius: '9999px',
            backgroundColor: backendHealthy ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `1px solid ${backendHealthy ? 'rgba(16, 185, 129, 0.45)' : 'rgba(239, 68, 68, 0.45)'}`,
            fontSize: '12px',
            fontWeight: 700,
            letterSpacing: '0.2px',
            color: backendHealthy ? '#10B981' : '#EF4444',
            transition: 'all 0.2s ease'
          }}
        >
          {backendHealthy ? (
            <>
              <span 
                className="animate-blink-indicator"
                style={{ 
                  width: '7px', 
                  height: '7px', 
                  borderRadius: '50%', 
                  backgroundColor: '#10B981',
                  display: 'inline-block',
                  flexShrink: 0
                }} 
              />
              <span>SERVER ONLINE</span>
            </>
          ) : (
            <>
              <span 
                style={{ 
                  width: '7px', 
                  height: '7px', 
                  borderRadius: '50%', 
                  backgroundColor: '#EF4444',
                  boxShadow: '0 0 5px rgba(239, 68, 68, 0.6)',
                  display: 'inline-block',
                  flexShrink: 0
                }} 
              />
              <span>NO SERVER</span>
            </>
          )}
        </div>

        {/* LLM in-flight requests indicator */}
        {activeLlmCount > 0 && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            padding: '4px 8px',
            borderRadius: '6px',
            backgroundColor: 'var(--status-running-bg)',
            color: 'var(--status-running)',
            border: '1px solid var(--status-running-border)',
            fontSize: '11px',
            fontWeight: 600
          }}>
            <Cpu size={13} className="animate-spin" />
            <span>LLM: {activeLlmCount} in flight</span>
          </div>
        )}

        {/* Theme Toggle (Dark / Light) */}
        {onToggleTheme && (
          <button
            onClick={onToggleTheme}
            data-testid="theme-toggle-btn"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background-color 0.15s ease, color 0.15s ease'
            }}
            onMouseEnter={(e) => { 
              e.currentTarget.style.backgroundColor = 'var(--bg-elevated)';
              e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={(e) => { 
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
            title={`Switch to ${theme === 'dark' ? 'Light Mode' : 'Dark Theme'}`}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        )}

        {/* Search icon */}
        <button
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            padding: '6px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background-color 0.15s ease'
          }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-elevated)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          title="Search stages, logs, or agents"
        >
          <Search size={18} strokeWidth={2} />
        </button>

        {/* Help icon */}
        <button
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            padding: '6px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background-color 0.15s ease'
          }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-elevated)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          title="Pipeline Documentation & Operator Guide"
        >
          <HelpCircle size={18} strokeWidth={2} />
        </button>

        {/* Notification Bell with Badge '8' */}
        <div style={{ position: 'relative' }}>
          <button
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background-color 0.15s ease'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-elevated)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            title="8 System Notifications"
          >
            <Bell size={18} strokeWidth={2} />
          </button>
          <span style={{
            position: 'absolute',
            top: '0px',
            right: '0px',
            backgroundColor: 'var(--accent-red)',
            color: '#FFFFFF',
            fontSize: '10px',
            fontWeight: 700,
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '2px solid var(--header-bg)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.3)'
          }}>
            8
          </span>
        </div>

        {/* User Profile Avatar with Name John */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          paddingLeft: '6px',
          borderLeft: '1px solid var(--header-border)',
          cursor: 'pointer'
        }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #13C2C2 0%, #08979C 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFFFFF',
            fontWeight: 700,
            fontSize: '13px',
            boxShadow: '0 2px 6px rgba(19, 194, 194, 0.4)'
          }}>
            J
          </div>
          <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>
            John
          </span>
        </div>
      </div>
    </header>
  );
};
