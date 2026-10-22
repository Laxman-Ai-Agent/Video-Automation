"""Rollback Manager for Capability Finder Knowledge.

Enables safe, audited rollbacks to previously archived active knowledge snapshots.
Automatically snapshots current state before restoring an archive with transactional
store locking and authenticated operator verification.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
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
from .knowledge_promoter import (
    _KNOWLEDGE_LOCK,
    ACTIVE_KNOWLEDGE_FILE,
    ARCHIVE_DIR,
    KnowledgePromoter,
    knowledge_promoter,
)
from .store_lock import StoreLock


class RollbackManager:
    """Manages restoration of prior archived knowledge configurations."""

    def __init__(
        self,
        active_file: Path | None = None,
        archive_dir: Path | None = None,
        promoter: KnowledgePromoter | None = None,
    ) -> None:
        self.active_file = active_file or ACTIVE_KNOWLEDGE_FILE
        self.archive_dir = archive_dir or ARCHIVE_DIR
        self.promoter = promoter or knowledge_promoter
        self.lock_file = self.active_file.with_name(self.active_file.name + ".lock")
        self.lock = StoreLock.get(self.lock_file)

    def list_archive_versions(self) -> list[dict[str, Any]]:
        """Returns sorted list of available archived knowledge snapshots."""
        with self.lock:
            if not self.archive_dir.exists():
                return []

            archives: list[dict[str, Any]] = []
            for p in self.archive_dir.glob("*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    archives.append({
                        "filename": p.name,
                        "path": str(p),
                        "version": data.get("version", "unknown"),
                        "updated_at": data.get("updated_at", ""),
                        "promoted_lessons_count": len(data.get("promoted_lessons", [])),
                        "size_bytes": p.stat().st_size,
                        "mtime": p.stat().st_mtime,
                    })
                except Exception:
                    continue

            # Sort descending by mtime (newest first)
            archives.sort(key=lambda x: x["mtime"], reverse=True)
            return archives

    def rollback(
        self,
        target_archive_filename: str | None = None,
        authorized_by: str | None = None,
        operator: AuthenticatedOperator | None = None,
        operator_id: str | None = None,
        role: str | None = None,
        approval_request_id: str | None = None,
    ) -> dict[str, Any]:
        """Rolls back active knowledge to a specified archive snapshot or the most recent one."""
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
                raise ValueError(f"Rollback rejected: {e}") from e

            if auth_op.role not in TRUSTED_OPERATOR_ROLES:
                raise ValueError(
                    f"Unauthorized operator role '{auth_op.role}' for rollback. "
                    f"Must be a trusted role ({', '.join(sorted(TRUSTED_OPERATOR_ROLES))})."
                )

            archives = self.list_archive_versions()
            if not archives:
                raise FileNotFoundError("No archived knowledge snapshots found for rollback.")

            if target_archive_filename:
                target_entry = next((a for a in archives if a["filename"] == target_archive_filename), None)
                if not target_entry:
                    raise FileNotFoundError(f"Target archive '{target_archive_filename}' not found.")
            else:
                # Default to the most recent non-prerollback archive
                non_prerollback = [a for a in archives if "pre_rollback" not in a["filename"]]
                target_entry = non_prerollback[0] if non_prerollback else archives[0]

            target_path = Path(target_entry["path"])
            with open(target_path, "r", encoding="utf-8") as f:
                restored_data = json.load(f)

            # 2. Snapshot current active knowledge as pre_rollback
            current_active = self.promoter.load_active_knowledge()
            current_ver = current_active.get("version", "unknown")
            now_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            pre_rollback_name = f"active_knowledge_pre_rollback_{now_ts}_v{current_ver}.json"
            pre_rollback_path = self.archive_dir / pre_rollback_name
            with open(pre_rollback_path, "w", encoding="utf-8") as f:
                json.dump(current_active, f, indent=2)

            # 3. Atomically restore target data to active file
            temp_dir = self.active_file.parent
            tmp_path_str: str | None = None
            try:
                with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tmp:
                    json.dump(restored_data, tmp, indent=2)
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

            attribution = auth_op.attribution_string()
            return {
                "rolled_back": True,
                "restored_from": target_entry["filename"],
                "restored_version": restored_data.get("version", "unknown"),
                "pre_rollback_archive": pre_rollback_name,
                "authorized_by": attribution,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operator": auth_op.to_dict(),
            }


rollback_manager = RollbackManager()
