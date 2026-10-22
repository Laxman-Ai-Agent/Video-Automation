"""Knowledge Promoter for Capability Finder.

Atomically promotes verified LessonProposals into active knowledge after passing
all LearningGate verification gates. Maintains version history and archives prior
active knowledge snapshots with thread-safe and process-safe transactional locking.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .authorization import (
    ELEVATED_SECURITY_ROLES,
    TRUSTED_OPERATOR_ROLES,
    AuthenticatedOperator,
    SecurityAuthError,
    authenticate_operator,
)
from .learning_gate import LearningGate, learning_gate
from .lesson_evaluator import LearningEvaluation
from .lesson_generator import LessonProposal
from .store_lock import StoreLock

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
ACTIVE_DIR = KNOWLEDGE_DIR / "active"
ARCHIVE_DIR = KNOWLEDGE_DIR / "archive"
ACTIVE_KNOWLEDGE_FILE = ACTIVE_DIR / "active_knowledge.json"

# Canonical lock for default active knowledge file
_KNOWLEDGE_LOCK = StoreLock.get(ACTIVE_KNOWLEDGE_FILE.with_name(ACTIVE_KNOWLEDGE_FILE.name + ".lock"))


class KnowledgePromoter:
    """Manages atomic promotion of approved proposals into active system knowledge."""

    def __init__(
        self,
        active_file: Path | None = None,
        archive_dir: Path | None = None,
        gate: LearningGate | None = None,
    ) -> None:
        self.active_file = active_file or ACTIVE_KNOWLEDGE_FILE
        self.archive_dir = archive_dir or ARCHIVE_DIR
        self.gate = gate or learning_gate
        self.lock_file = self.active_file.with_name(self.active_file.name + ".lock")
        self.lock = StoreLock.get(self.lock_file)
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        with self.lock:
            self.active_file.parent.mkdir(parents=True, exist_ok=True)
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            if not self.active_file.exists():
                self._write_baseline_active()

    def _write_baseline_active(self) -> None:
        baseline = {
            "version": "1.0.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "description": "Baseline active knowledge configuration for Capability Finder",
            "promoted_lessons": [],
            "routing_preferences": {},
            "synonym_expansions": {},
            "constraint_overrides": {},
        }
        temp_dir = self.active_file.parent
        tmp_path_str: str | None = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tmp:
                json.dump(baseline, tmp, indent=2)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path_str = tmp.name

            os.replace(tmp_path_str, str(self.active_file))
        except Exception:
            if tmp_path_str and os.path.exists(tmp_path_str):
                try:
                    os.unlink(tmp_path_str)
                except OSError:
                    pass
            raise

    def load_active_knowledge(self) -> dict[str, Any]:
        """Loads and returns current active knowledge under store lock."""
        with self.lock:
            self._ensure_dirs()
            try:
                with open(self.active_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                self._write_baseline_active()
                with open(self.active_file, "r", encoding="utf-8") as f:
                    return json.load(f)

    def _bump_version(self, current_ver: str) -> str:
        parts = current_ver.split(".")
        if len(parts) == 3 and parts[1].isdigit():
            return f"{parts[0]}.{int(parts[1]) + 1}.0"
        return f"{current_ver}.1"

    def promote_proposal(
        self,
        proposal: LessonProposal,
        evaluation: LearningEvaluation,
        authorized_by: str | None = None,
        operator: AuthenticatedOperator | None = None,
        operator_id: str | None = None,
        role: str | None = None,
        approval_request_id: str | None = None,
        check_case_existence: bool = True,
    ) -> dict[str, Any]:
        """Validates credentials and gates, archives prior knowledge, and atomically promotes proposal."""
        with self.lock:
            # 1. Authenticate operator first (anti-spoofing enforcement)
            try:
                auth_op = authenticate_operator(
                    operator=operator,
                    authorized_by=authorized_by,
                    operator_id=operator_id,
                    role=role,
                    approval_request_id=approval_request_id,
                    consume_approval=True,
                )
            except SecurityAuthError as e:
                raise ValueError(f"Promotion rejected: {e}") from e

            # 2. Gate verification
            passed, reasons = self.gate.check_promotion_gates(
                proposal=proposal,
                evaluation=evaluation,
                operator=auth_op,
                check_case_existence=check_case_existence,
            )
            if not passed:
                raise ValueError(f"Promotion rejected by gate: {'; '.join(reasons)}")

            current_knowledge = self.load_active_knowledge()
            current_ver = current_knowledge.get("version", "1.0.0")
            now_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

            # 3. Archive current active knowledge
            archive_name = f"active_knowledge_{now_ts}_v{current_ver}.json"
            archive_path = self.archive_dir / archive_name
            with open(archive_path, "w", encoding="utf-8") as f:
                json.dump(current_knowledge, f, indent=2)

            # 4. Update knowledge content with verified attribution
            new_version = self._bump_version(current_ver)
            updated_knowledge = dict(current_knowledge)
            updated_knowledge["version"] = new_version
            updated_knowledge["updated_at"] = datetime.now(timezone.utc).isoformat()
            attribution = auth_op.attribution_string()
            updated_knowledge["last_promoted_by"] = attribution

            proposal.status = "APPROVED"
            proposal_dict = proposal.to_dict()
            proposal_dict["promoted_at"] = updated_knowledge["updated_at"]
            proposal_dict["promoted_by"] = attribution
            proposal_dict["auth_method"] = auth_op.auth_method
            if auth_op.approval_request_id:
                proposal_dict["approval_request_id"] = auth_op.approval_request_id

            if "promoted_lessons" not in updated_knowledge:
                updated_knowledge["promoted_lessons"] = []
            updated_knowledge["promoted_lessons"].append(proposal_dict)

            # Apply specific rule types to active tables
            if proposal.rule_type == "routing_preference":
                domain = proposal.affected_domain
                if "routing_preferences" not in updated_knowledge:
                    updated_knowledge["routing_preferences"] = {}
                updated_knowledge["routing_preferences"][domain] = proposal.rule_content
            elif proposal.rule_type == "synonym_expansion":
                if "synonym_expansions" not in updated_knowledge:
                    updated_knowledge["synonym_expansions"] = {}
                updated_knowledge["synonym_expansions"].update(proposal.rule_content.get("synonyms", {}))
            elif proposal.rule_type == "constraint_override":
                domain = proposal.affected_domain
                if "constraint_overrides" not in updated_knowledge:
                    updated_knowledge["constraint_overrides"] = {}
                updated_knowledge["constraint_overrides"][domain] = proposal.rule_content

            # 5. Atomic write with fsync and os.replace
            temp_dir = self.active_file.parent
            tmp_path_str: str | None = None
            try:
                with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tmp:
                    json.dump(updated_knowledge, tmp, indent=2)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                    tmp_path_str = tmp.name

                os.replace(tmp_path_str, str(self.active_file))
            except Exception:
                if tmp_path_str and os.path.exists(tmp_path_str):
                    try:
                        os.unlink(tmp_path_str)
                    except OSError:
                        pass
                raise

            return {
                "promoted": True,
                "proposal_id": proposal.proposal_id,
                "previous_version": current_ver,
                "new_version": new_version,
                "archive_snapshot": archive_name,
                "promoted_at": updated_knowledge["updated_at"],
                "authorized_by": attribution,
                "operator": auth_op.to_dict(),
            }


knowledge_promoter = KnowledgePromoter()
