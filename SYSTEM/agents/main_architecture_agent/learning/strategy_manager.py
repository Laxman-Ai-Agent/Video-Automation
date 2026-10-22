"""Strategy Manager for Main Architecture Agent.

Manages the lifecycle of architecture strategies:
- Active strategy retrieval & hash calculation
- Candidate strategy staging & validation
- Atomic promotion with historical archival
- Atomic rollback preserving complete history
- Integration with audit and decision logs
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("main_architecture_agent.strategy_manager")

BASE_DIR = Path(__file__).resolve().parent.parent
STRATEGIES_DIR = BASE_DIR / "strategies"
ACTIVE_DIR = STRATEGIES_DIR / "active"
CANDIDATES_DIR = STRATEGIES_DIR / "candidates"
ARCHIVE_DIR = STRATEGIES_DIR / "archive"
ACTIVE_FILE = ACTIVE_DIR / "active_strategy.json"

_STRATEGY_LOCK = threading.RLock()

REQUIRED_STRATEGY_KEYS = {
    "strategy_id",
    "version",
    "task_decomposition_rules",
    "agent_routing_preferences",
    "fallback_routes",
    "retry_policies",
    "acceptance_criteria",
}

SAFE_BASELINE_STRATEGY: dict[str, Any] = {
    "strategy_id": "strategy_arch_default",
    "version": "1.0.0",
    "name": "Canonical Baseline Architecture Strategy",
    "description": "Safe default architecture strategy fallback",
    "created_at": "2026-10-17T05:00:00Z",
    "updated_at": "2026-10-17T05:00:00Z",
    "authorized_by": "system_bootstrap",
    "task_decomposition_rules": {
        "video_generation": {
            "keywords": ["video", "pipeline", "render", "generate video"],
            "subtasks": [
                {
                    "step": 1,
                    "title": "Evaluate system and media capabilities",
                    "assigned_agent_id": "capability_finder",
                    "action": "inspect_capabilities",
                    "dependencies": [],
                },
                {
                    "step": 2,
                    "title": "Execute video generation pipeline",
                    "assigned_agent_id": "main_orchestrator",
                    "action": "run",
                    "dependencies": [1],
                },
            ],
        },
        "skill_authoring": {
            "keywords": ["skill", "author skill", "custom skill", "typography skill"],
            "subtasks": [
                {
                    "step": 1,
                    "title": "Discover existing skills",
                    "assigned_agent_id": "capability_finder",
                    "action": "search_skills",
                    "dependencies": [],
                },
                {
                    "step": 2,
                    "title": "Create or stage requested skill",
                    "assigned_agent_id": "skill_factory",
                    "action": "create_skill",
                    "dependencies": [1],
                },
            ],
        },
        "audio_processing": {
            "keywords": ["audio", "transcribe", "transcription", "speech"],
            "subtasks": [
                {
                    "step": 1,
                    "title": "Ingest and normalize audio",
                    "assigned_agent_id": "audio_input",
                    "action": "ingest",
                    "dependencies": [],
                },
                {
                    "step": 2,
                    "title": "Transcribe audio narration",
                    "assigned_agent_id": "audio_analyzer",
                    "action": "transcribe",
                    "dependencies": [1],
                },
            ],
        },
        "system_discovery": {
            "keywords": ["discovery", "inspect", "capabilities"],
            "subtasks": [
                {
                    "step": 1,
                    "title": "System discovery and capability inspection",
                    "assigned_agent_id": "capability_finder",
                    "action": "inspect_all",
                    "dependencies": [],
                }
            ],
        },
    },
    "agent_routing_preferences": {
        "audio_ingest": ["audio_input"],
        "speech_transcription": ["audio_analyzer"],
        "semantic_segmentation": ["scene_segmentation"],
        "visual_concepts": ["visual_planning"],
        "real_media_assets": ["asset_collection"],
        "motion_planning": ["motion_planning"],
        "motion_animation": ["motion_animation"],
        "motion_validation": ["motion_timeline_validation"],
        "timeline_assembly": ["timeline_build"],
        "human_approval": ["timeline_approval"],
        "video_rendering": ["render_video"],
        "quality_control": ["final_qc"],
        "video_delivery": ["final_video_delivery"],
        "capability_inspection": ["capability_finder"],
        "skill_authoring": ["skill_factory"],
        "pipeline_coordination": ["main_orchestrator"],
    },
    "fallback_routes": {
        "motion_template_selection": "motion_planning",
        "unregistered_fallback": "capability_finder",
    },
    "retry_policies": {
        "default_max_retries": 2,
        "backoff_factor": 1.5,
        "retryable_error_codes": ["timeout", "transient_io", "rate_limit"],
    },
    "acceptance_criteria": {
        "require_all_subtasks_succeeded": True,
        "require_non_empty_outputs": True,
        "check_prerequisites_prior_to_delegation": True,
    },
}


def calculate_strategy_hash(strat: dict[str, Any]) -> str:
    """Computes a canonical SHA-256 hash of a strategy dictionary."""
    canonical = json.dumps(strat, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class StrategyManager:
    """Thread-safe manager for architecture strategy lifecycles."""

    def __init__(
        self,
        active_file: Path | None = None,
        candidates_dir: Path | None = None,
        archive_dir: Path | None = None,
    ) -> None:
        self.active_file = active_file or ACTIVE_FILE
        self.candidates_dir = candidates_dir or CANDIDATES_DIR
        self.archive_dir = archive_dir or ARCHIVE_DIR
        self._lock = _STRATEGY_LOCK

        self.active_file.parent.mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        # Initialize active strategy if absent
        if not self.active_file.exists():
            self._write_strategy_atomic(self.active_file, SAFE_BASELINE_STRATEGY)

    def _write_strategy_atomic(self, target_path: Path, strategy: dict[str, Any]) -> None:
        """Writes strategy JSON atomically using a temp file."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix="strat_tmp_",
            suffix=".json",
            dir=str(target_path.parent),
        )
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(strategy, f, indent=2)
            shutil.move(tmp_path, str(target_path))
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def validate_strategy(self, strategy: dict[str, Any]) -> tuple[bool, str]:
        """Validates that a strategy dictionary satisfies all schema requirements."""
        if not isinstance(strategy, dict):
            return False, "Strategy must be a JSON dictionary."

        missing = REQUIRED_STRATEGY_KEYS - set(strategy.keys())
        if missing:
            return False, f"Strategy missing required keys: {sorted(missing)}"

        if not isinstance(strategy.get("task_decomposition_rules"), dict):
            return False, "task_decomposition_rules must be a dict."

        if not isinstance(strategy.get("agent_routing_preferences"), dict):
            return False, "agent_routing_preferences must be a dict."

        if not isinstance(strategy.get("fallback_routes"), dict):
            return False, "fallback_routes must be a dict."

        if not isinstance(strategy.get("retry_policies"), dict):
            return False, "retry_policies must be a dict."

        if not isinstance(strategy.get("acceptance_criteria"), dict):
            return False, "acceptance_criteria must be a dict."

        return True, "Valid"

    def get_active_strategy(self) -> dict[str, Any]:
        """Loads and returns the currently active strategy."""
        with self._lock:
            if not self.active_file.exists():
                return copy.deepcopy(SAFE_BASELINE_STRATEGY)
            try:
                with open(self.active_file, "r", encoding="utf-8") as f:
                    strat = json.load(f)
                valid, msg = self.validate_strategy(strat)
                if not valid:
                    logger.error(f"Active strategy invalid ({msg}); falling back to safe default.")
                    return copy.deepcopy(SAFE_BASELINE_STRATEGY)
                return strat
            except Exception as e:
                logger.error(f"Error loading active strategy: {e}; falling back to safe default.")
                return copy.deepcopy(SAFE_BASELINE_STRATEGY)

    def get_active_strategy_hash(self) -> str:
        """Returns the SHA-256 hash of the active strategy."""
        return calculate_strategy_hash(self.get_active_strategy())

    def save_candidate(self, strategy: dict[str, Any], candidate_id: str | None = None) -> Path:
        """Saves a candidate strategy to strategies/candidates/."""
        valid, msg = self.validate_strategy(strategy)
        if not valid:
            raise ValueError(f"Invalid candidate strategy: {msg}")

        cid = candidate_id or f"cand_{strategy.get('version', '1.0.0')}_{hashlib.sha256(str(strategy).encode()).hexdigest()[:8]}"
        candidate_path = self.candidates_dir / f"{cid}.json"
        with self._lock:
            self._write_strategy_atomic(candidate_path, strategy)
        return candidate_path

    def list_candidates(self) -> list[dict[str, Any]]:
        """Lists candidate strategies currently staged."""
        with self._lock:
            candidates = []
            for f in sorted(self.candidates_dir.glob("*.json")):
                try:
                    with open(f, "r", encoding="utf-8") as file:
                        data = json.load(file)
                    candidates.append({
                        "file": f.name,
                        "candidate_id": f.stem,
                        "version": data.get("version"),
                        "strategy_id": data.get("strategy_id"),
                    })
                except Exception:
                    continue
            return candidates

    def activate_strategy(
        self,
        candidate_input: dict[str, Any] | str | Path,
        authorized_by: str = "operator",
        reason: str = "Candidate benchmark passed and approved",
    ) -> dict[str, Any]:
        """Atomically promotes a candidate strategy to active, archiving the prior active."""
        if isinstance(candidate_input, (str, Path)):
            cand_path = Path(candidate_input)
            if not cand_path.is_absolute():
                cand_path = self.candidates_dir / cand_path
            if not cand_path.exists() and not cand_path.suffix:
                cand_path = cand_path.with_suffix(".json")
            if not cand_path.exists():
                raise FileNotFoundError(f"Candidate strategy file not found: {cand_path}")
            with open(cand_path, "r", encoding="utf-8") as f:
                strategy_to_activate = json.load(f)
        else:
            strategy_to_activate = candidate_input

        valid, msg = self.validate_strategy(strategy_to_activate)
        if not valid:
            raise ValueError(f"Cannot activate invalid strategy: {msg}")

        with self._lock:
            current_active = self.get_active_strategy()
            old_version = current_active.get("version", "unknown")
            strat_id = current_active.get("strategy_id", "strategy_arch")
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

            archive_file = self.archive_dir / f"{strat_id}_{old_version}_{ts}.json"
            self._write_strategy_atomic(archive_file, current_active)

            # Mark activation metadata
            strategy_to_activate["authorized_by"] = authorized_by
            strategy_to_activate["activation_reason"] = reason
            strategy_to_activate["activated_at"] = datetime.now(timezone.utc).isoformat()

            # Atomically activate
            self._write_strategy_atomic(self.active_file, strategy_to_activate)

            # Record in history service if present
            self._record_promotion_history(
                old_version=old_version,
                new_version=strategy_to_activate.get("version", "unknown"),
                authorized_by=authorized_by,
                reason=reason,
                archive_file=str(archive_file),
            )

            logger.info(
                f"Activated strategy v{strategy_to_activate.get('version')} (archived v{old_version} to {archive_file.name})"
            )
            return strategy_to_activate

    def rollback(
        self,
        target_version: str | None = None,
        authorized_by: str = "operator",
        reason: str = "Emergency strategy rollback",
    ) -> dict[str, Any]:
        """Rolls back the active strategy to a previous archived version."""
        with self._lock:
            archived = sorted(self.archive_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
            if not archived:
                raise RuntimeError("No archived strategies available to rollback to.")

            chosen_file: Path | None = None
            if target_version:
                for f in archived:
                    try:
                        with open(f, "r", encoding="utf-8") as file:
                            data = json.load(file)
                        if data.get("version") == target_version:
                            chosen_file = f
                            break
                    except Exception:
                        continue
                if not chosen_file:
                    raise FileNotFoundError(f"No archived strategy found with version: {target_version}")
            else:
                chosen_file = archived[0]

            with open(chosen_file, "r", encoding="utf-8") as f:
                strategy_to_restore = json.load(f)

            valid, msg = self.validate_strategy(strategy_to_restore)
            if not valid:
                raise ValueError(f"Archived strategy {chosen_file.name} is invalid: {msg}")

            # Archive the currently active before replacing
            current_active = self.get_active_strategy()
            old_version = current_active.get("version", "unknown")
            strat_id = current_active.get("strategy_id", "strategy_arch")
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            cur_archive = self.archive_dir / f"{strat_id}_{old_version}_pre_rollback_{ts}.json"
            self._write_strategy_atomic(cur_archive, current_active)

            strategy_to_restore["rolled_back_by"] = authorized_by
            strategy_to_restore["rollback_reason"] = reason
            strategy_to_restore["rolled_back_at"] = datetime.now(timezone.utc).isoformat()

            self._write_strategy_atomic(self.active_file, strategy_to_restore)

            self._record_promotion_history(
                old_version=old_version,
                new_version=strategy_to_restore.get("version", "unknown"),
                authorized_by=authorized_by,
                reason=f"Rollback: {reason}",
                archive_file=str(chosen_file),
            )

            logger.info(
                f"Rolled back strategy to v{strategy_to_restore.get('version')} from {chosen_file.name}"
            )
            return strategy_to_restore

    def list_archived_strategies(self) -> list[dict[str, Any]]:
        """Lists all archived strategy files with version and timestamp."""
        with self._lock:
            results = []
            for f in sorted(self.archive_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
                try:
                    with open(f, "r", encoding="utf-8") as file:
                        data = json.load(file)
                    results.append({
                        "file": f.name,
                        "strategy_id": data.get("strategy_id"),
                        "version": data.get("version"),
                        "archived_at": data.get("updated_at") or data.get("activated_at"),
                    })
                except Exception:
                    continue
            return results

    def _record_promotion_history(
        self,
        old_version: str,
        new_version: str,
        authorized_by: str,
        reason: str,
        archive_file: str,
    ) -> None:
        try:
            from SYSTEM.history.history_service import HistoryService
            from SYSTEM.history.decision_history import DecisionRecord
            from SYSTEM.history.audit_history import AuditRecord

            svc = HistoryService()
            svc.record_decision(
                DecisionRecord(
                    agent_id="main_architecture_agent",
                    decision_type="strategy_lifecycle",
                    rationale=reason,
                    chosen_option=new_version,
                    alternatives_considered=[old_version],
                    parameters={"archive_file": archive_file, "authorized_by": authorized_by},
                )
            )
            svc.record_audit(
                AuditRecord(
                    agent_id="main_architecture_agent",
                    action="activate_strategy",
                    status="success",
                    actor=authorized_by,
                    details={"old_version": old_version, "new_version": new_version, "reason": reason},
                )
            )
        except Exception as e:
            logger.debug(f"Could not record strategy lifecycle to central history: {e}")


strategy_manager = StrategyManager()
