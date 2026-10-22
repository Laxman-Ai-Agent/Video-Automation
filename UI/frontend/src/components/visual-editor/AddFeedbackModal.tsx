import React, { useState } from 'react';
import { 
  X, 
  Tag, 
  Layers, 
  FileCode, 
  Check, 
  HelpCircle, 
  AlertCircle,
  Plus,
  Sparkles,
  Compass
} from 'lucide-react';
import { ComponentCatalogItem, FeedbackCategory } from '../../types/visualEditor';

interface AddFeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    page: string;
    route: string;
    elementSelector: string;
    elementName: string;
    componentRef?: string;
    sourceFile?: string;
    isSourceMapped: boolean;
    category: FeedbackCategory;
    feedback: string;
    tags: string[];
  }) => Promise<void>;
  catalog: ComponentCatalogItem[];
  defaultPage?: string;
}

const SUPPORTED_PAGES = [
  { name: 'Pipeline Execution Flow', route: '/pipeline' },
  { name: 'New Project / Audio Ingest', route: '/pipeline#new-project' },
  { name: 'Dashboard', route: '/dashboard' },
  { name: 'Previous Projects', route: '/projects' },
  { name: 'Approvals & Blockers', route: '/pipeline#approvals' },
  { name: 'Agent Communication', route: '/pipeline#communication' },
  { name: 'Agents Center (21 Agents)', route: '/agents' },
  { name: 'Skills Registry', route: '/skills' }
];

const CATEGORIES: { id: FeedbackCategory; label: string; icon: string }[] = [
  { id: 'layout', label: 'Layout & Spacing', icon: '📐' },
  { id: 'alignment', label: 'Alignment & Mobile', icon: '📱' },
  { id: 'style', label: 'Theme & Styling', icon: '🎨' },
  { id: 'spacing', label: 'Padding & Margins', icon: '↔️' },
  { id: 'logic', label: 'Workflow & State', icon: '⚡' },
  { id: 'bug', label: 'Bug / Visual Glitch', icon: '🐛' }
];

const EXAMPLE_SUGGESTIONS = [
  'Move this button to the right and align with the card header.',
  'Reduce the spacing between these sequential sections.',
  'Improve this card layout on high-DPI displays.',
  'Fix this element alignment and padding on mobile viewports.',
  'Ensure contrast ratio matches the dark theme specification.'
];

export const AddFeedbackModal: React.FC<AddFeedbackModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  catalog,
  defaultPage = 'Pipeline Execution Flow'
}) => {
  const [selectedPage, setSelectedPage] = useState<string>(defaultPage);
  const [selectionMode, setSelectionMode] = useState<'catalog' | 'custom'>('catalog');
  const [selectedCatalogId, setSelectedCatalogId] = useState<string>(catalog[0]?.id || '');
  
  // Custom element fields
  const [customSelector, setCustomSelector] = useState<string>('');
  const [customElementName, setCustomElementName] = useState<string>('');
  
  // Feedback content
  const [category, setCategory] = useState<FeedbackCategory>('layout');
  const [feedbackText, setFeedbackText] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const activePageObj = SUPPORTED_PAGES.find(p => p.name === selectedPage) || SUPPORTED_PAGES[0];
  const selectedCatalogItem = catalog.find(c => c.id === selectedCatalogId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!feedbackText.trim()) {
      setError('Please describe your feedback or requested UI modification.');
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);

      let elSelector = '';
      let elName = '';
      let compRef = '';
      let srcFile = '';
      let isMapped = true;

      if (selectionMode === 'catalog' && selectedCatalogItem) {
        elSelector = selectedCatalogItem.selector;
        elName = selectedCatalogItem.name;
        compRef = selectedCatalogItem.component;
        srcFile = selectedCatalogItem.source_file;
        isMapped = true;
      } else {
        elSelector = customSelector.trim() || 'div.custom-ui-node';
        elName = customElementName.trim() || 'Custom UI Element';
        compRef = 'UnmappedComponent';
        srcFile = 'Approximated / Unmapped';
        isMapped = false;
      }

      await onSubmit({
        page: selectedPage,
        route: activePageObj.route,
        elementSelector: elSelector,
        elementName: elName,
        componentRef: compRef,
        sourceFile: srcFile,
        isSourceMapped: isMapped,
        category,
        feedback: feedbackText.trim(),
        tags: [category, selectedPage.toLowerCase().replace(/[^a-z0-9]/g, '-')]
      });

      setFeedbackText('');
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to attach sticky note');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div 
        data-testid="add-feedback-modal"
        style={{
          backgroundColor: 'var(--bg-card)',
          borderRadius: '8px',
          border: '1px solid var(--border-card)',
          width: '100%',
          maxWidth: '680px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden',
          fontFamily: 'var(--font-sans)'
        }}
      >
        {/* Header */}
        <div style={{
          padding: '16px 24px',
          borderBottom: '1px solid var(--border-card)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '6px',
              backgroundColor: 'var(--accent-blue)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FFFFFF'
            }}>
              <Plus size={18} strokeWidth={2.5} />
            </div>
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Attach Visual Sticky Note
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>
                Select an application element, record requested changes, and link to source code
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            data-testid="modal-close-btn"
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '4px',
              display: 'flex'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {error && (
            <div style={{
              padding: '10px 14px',
              backgroundColor: 'var(--status-failed-bg)',
              border: '1px solid var(--status-failed-border)',
              borderRadius: '6px',
              color: 'var(--status-failed)',
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* 1. Target Page Selector */}
          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              1. Target Application Page & Route
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '8px' }}>
              {SUPPORTED_PAGES.map((page) => (
                <button
                  type="button"
                  key={page.name}
                  onClick={() => setSelectedPage(page.name)}
                  data-testid={`select-page-${page.name.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}
                  style={{
                    padding: '8px 12px',
                    textAlign: 'left',
                    borderRadius: '6px',
                    border: selectedPage === page.name ? '1px solid var(--accent-blue)' : '1px solid var(--border-card)',
                    backgroundColor: selectedPage === page.name ? 'rgba(24, 144, 255, 0.12)' : 'var(--bg-app)',
                    color: selectedPage === page.name ? 'var(--accent-blue)' : 'var(--text-secondary)',
                    fontSize: '12px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <span style={{ fontWeight: selectedPage === page.name ? 600 : 400 }}>{page.name}</span>
                  <span style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', opacity: 0.7 }}>{page.route}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 2. Target Element & Component Mapping */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                2. Target UI Element & Source Reference
              </label>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  type="button"
                  onClick={() => setSelectionMode('catalog')}
                  style={{
                    fontSize: '11px',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-card)',
                    backgroundColor: selectionMode === 'catalog' ? 'var(--accent-blue)' : 'transparent',
                    color: selectionMode === 'catalog' ? '#FFFFFF' : 'var(--text-secondary)',
                    cursor: 'pointer'
                  }}
                >
                  Verified Component Catalog
                </button>
                <button
                  type="button"
                  onClick={() => setSelectionMode('custom')}
                  style={{
                    fontSize: '11px',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-card)',
                    backgroundColor: selectionMode === 'custom' ? 'var(--accent-blue)' : 'transparent',
                    color: selectionMode === 'custom' ? '#FFFFFF' : 'var(--text-secondary)',
                    cursor: 'pointer'
                  }}
                >
                  Custom DOM Selector
                </button>
              </div>
            </div>

            {selectionMode === 'catalog' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <select
                  value={selectedCatalogId}
                  onChange={(e) => setSelectedCatalogId(e.target.value)}
                  data-testid="catalog-element-select"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '6px',
                    backgroundColor: 'var(--bg-app)',
                    border: '1px solid var(--border-card)',
                    color: 'var(--text-primary)',
                    fontSize: '13px',
                    outline: 'none'
                  }}
                >
                  {catalog.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} — {c.component} ({c.source_file})
                    </option>
                  ))}
                </select>

                {selectedCatalogItem && (
                  <div style={{
                    padding: '10px 14px',
                    backgroundColor: 'rgba(24, 144, 255, 0.08)',
                    borderRadius: '6px',
                    border: '1px solid rgba(24, 144, 255, 0.2)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '11px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent-blue)', fontWeight: 600 }}>
                      <FileCode size={13} />
                      <span>Component: {selectedCatalogItem.component}</span>
                      <span style={{ color: 'var(--text-muted)' }}>•</span>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{selectedCatalogItem.source_file}</span>
                    </div>
                    <div style={{ color: 'var(--text-secondary)' }}>
                      Selector: <code>{selectedCatalogItem.selector}</code> | {selectedCatalogItem.description}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div>
                  <input
                    type="text"
                    placeholder="Element description (e.g. Navigation Header Brand)"
                    value={customElementName}
                    onChange={(e) => setCustomElementName(e.target.value)}
                    data-testid="custom-element-name-input"
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      backgroundColor: 'var(--bg-app)',
                      border: '1px solid var(--border-card)',
                      color: 'var(--text-primary)',
                      fontSize: '13px',
                      outline: 'none'
                    }}
                  />
                </div>
                <div>
                  <input
                    type="text"
                    placeholder="DOM Selector (e.g. .brand-header, #menu-item-audio)"
                    value={customSelector}
                    onChange={(e) => setCustomSelector(e.target.value)}
                    data-testid="custom-element-selector-input"
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      backgroundColor: 'var(--bg-app)',
                      border: '1px solid var(--border-card)',
                      color: 'var(--text-primary)',
                      fontSize: '12px',
                      fontFamily: 'var(--font-mono)',
                      outline: 'none'
                    }}
                  />
                </div>
                <div style={{
                  padding: '8px 12px',
                  backgroundColor: 'var(--status-waiting-bg)',
                  borderRadius: '6px',
                  border: '1px solid var(--status-waiting-border)',
                  fontSize: '11px',
                  color: 'var(--text-muted)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  <HelpCircle size={14} />
                  <span>Clear fallback: Custom selectors are marked as unmapped source references until agent code inspection.</span>
                </div>
              </div>
            )}
          </div>

          {/* 3. Category Selection */}
          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              3. Feedback Category
            </label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {CATEGORIES.map((cat) => (
                <button
                  type="button"
                  key={cat.id}
                  onClick={() => setCategory(cat.id)}
                  data-testid={`category-btn-${cat.id}`}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '20px',
                    border: category === cat.id ? '1px solid var(--accent-blue)' : '1px solid var(--border-card)',
                    backgroundColor: category === cat.id ? 'var(--accent-blue)' : 'var(--bg-app)',
                    color: category === cat.id ? '#FFFFFF' : 'var(--text-secondary)',
                    fontSize: '12px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <span>{cat.icon}</span>
                  <span>{cat.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 4. Feedback Comment Textarea */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                4. Feedback / Requested UI Modification
              </label>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                {feedbackText.length}/400 chars
              </span>
            </div>

            <textarea
              rows={4}
              placeholder="Describe the requested UI change (e.g. Move this button to the right, reduce padding, fix alignment on mobile...)"
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              data-testid="feedback-note-textarea"
              maxLength={400}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: '6px',
                backgroundColor: 'var(--bg-app)',
                border: '1px solid var(--border-card)',
                color: 'var(--text-primary)',
                fontSize: '13px',
                outline: 'none',
                resize: 'none',
                lineHeight: 1.5
              }}
            />

            {/* Quick Suggestions */}
            <div style={{ marginTop: '8px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                Quick suggestions:
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {EXAMPLE_SUGGESTIONS.slice(0, 3).map((sug, idx) => (
                  <button
                    type="button"
                    key={idx}
                    onClick={() => setFeedbackText(sug)}
                    style={{
                      background: 'none',
                      border: 'none',
                      textAlign: 'left',
                      color: 'var(--accent-blue)',
                      fontSize: '11px',
                      cursor: 'pointer',
                      padding: '2px 0',
                      textDecoration: 'underline'
                    }}
                  >
                    • {sug}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Footer Submit Buttons */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '12px',
            borderTop: '1px solid var(--border-card)',
            paddingTop: '16px'
          }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                border: '1px solid var(--border-card)',
                backgroundColor: 'transparent',
                color: 'var(--text-secondary)',
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer'
              }}
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isSubmitting}
              data-testid="submit-feedback-note-btn"
              style={{
                padding: '8px 20px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: 'var(--accent-blue)',
                color: '#FFFFFF',
                fontSize: '13px',
                fontWeight: 600,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                opacity: isSubmitting ? 0.7 : 1,
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <Check size={14} />
              <span>{isSubmitting ? 'Saving Note...' : 'Pin Sticky Note'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
