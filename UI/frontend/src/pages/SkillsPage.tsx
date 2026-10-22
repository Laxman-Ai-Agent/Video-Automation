import React, { useState } from 'react';
import { BookOpen, ShieldCheck, Tag, Cpu, CheckCircle2, Search } from 'lucide-react';

interface SkillsPageProps {
  skills: any[];
}

export const SkillsPage: React.FC<SkillsPageProps> = ({ skills }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDomain, setSelectedDomain] = useState<string>('all');

  const domains = ['all', ...Array.from(new Set(skills.map((s) => s.domain).filter(Boolean)))];

  const filteredSkills = skills.filter((s) => {
    if (selectedDomain !== 'all' && s.domain !== selectedDomain) return false;
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      return (
        s.name?.toLowerCase().includes(q) ||
        s.summary?.toLowerCase().includes(q) ||
        s.skill_id?.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div style={{ padding: '32px', maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '28px'
      }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-primary)' }}>
            Skills & Capabilities Library ({skills.length})
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Audited, sandboxed capabilities bound to video generation and system agents.
          </p>
        </div>

        {/* Domain Filter Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {domains.map((d) => (
            <button
              key={d}
              onClick={() => setSelectedDomain(d)}
              style={{
                padding: '7px 16px',
                borderRadius: 'var(--radius-full)',
                border: 'none',
                backgroundColor: selectedDomain === d ? 'var(--accent-cyan)' : 'var(--bg-elevated)',
                color: selectedDomain === d ? '#060D1A' : 'var(--text-secondary)',
                fontWeight: 700,
                fontSize: '12.5px',
                cursor: 'pointer',
                textTransform: 'capitalize'
              }}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Skills Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
        gap: '20px'
      }}>
        {filteredSkills.map((skill) => (
          <div
            key={skill.skill_id}
            style={{
              backgroundColor: 'var(--bg-card)',
              borderRadius: 'var(--radius-xl)',
              border: '1px solid var(--border-card)',
              padding: '22px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              minHeight: '220px',
              boxShadow: 'var(--shadow-card)'
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--accent-cyan)',
                  backgroundColor: 'var(--status-running-bg)',
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-sm)',
                  fontWeight: 700
                }}>
                  {skill.domain || 'general'}
                </span>

                <span style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: 'var(--status-completed)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  <CheckCircle2 size={12} />
                  v{skill.version || '1.0.0'}
                </span>
              </div>

              <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '14px' }}>
                {skill.name}
              </h3>
              <p style={{
                fontSize: '12.5px',
                color: 'var(--text-secondary)',
                marginTop: '6px',
                lineHeight: 1.5,
                display: '-webkit-box',
                WebkitLineClamp: 3,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden'
              }}>
                {skill.summary}
              </p>
            </div>

            <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {(skill.capabilities || []).slice(0, 3).map((cap: string) => (
                  <span
                    key={cap}
                    style={{
                      fontSize: '10.5px',
                      padding: '2px 8px',
                      backgroundColor: 'var(--bg-elevated)',
                      color: 'var(--text-muted)',
                      borderRadius: 'var(--radius-sm)',
                      fontFamily: 'var(--font-mono)'
                    }}
                  >
                    {cap}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
