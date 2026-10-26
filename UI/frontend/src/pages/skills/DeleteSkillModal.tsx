import React from 'react';
import styles from './DeleteSkillModal.module.css';
import { AlertTriangle, Trash2 } from 'lucide-react';

export interface DeleteSkillModalProps {
  skill: { skill_id: string; name: string };
  isDeleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export const DeleteSkillModal: React.FC<DeleteSkillModalProps> = ({
  skill,
  isDeleting,
  onCancel,
  onConfirm
}) => {
  return (
    <div className={styles.overlay} onClick={onCancel} data-testid="delete-skill-modal">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.iconBox}>
            <AlertTriangle size={20} />
          </div>
          <h3 className={styles.title}>Delete Skill Confirmation</h3>
        </div>

        <div className={styles.body}>
          <p className={styles.message}>
            Are you sure you want to permanently delete this skill?
          </p>

          <div className={styles.skillInfoBox}>
            <span className={styles.skillName}>{skill.name}</span>
            <span className={styles.skillId}>ID: {skill.skill_id}</span>
          </div>

          <div className={styles.warningBox}>
            ⚠️ This will permanently remove the skill files or remove it from the registered catalog.
          </div>
        </div>

        <div className={styles.footer}>
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className={styles.cancelBtn}
            data-testid="cancel-delete-skill-btn"
          >
            Cancel
          </button>

          <button
            onClick={onConfirm}
            disabled={isDeleting}
            className={styles.confirmDeleteBtn}
            data-testid="confirm-delete-skill-btn"
          >
            <Trash2 size={13} />
            <span>{isDeleting ? 'Deleting...' : 'Delete Skill'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
