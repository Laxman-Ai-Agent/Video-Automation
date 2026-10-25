"""Canonical Pipeline Orchestrator and Monitoring Service.

Coordinates the 12 active stages in the Motion-Only pipeline dependency graph:
1. audio (Audio Input)
2. analyzer (Audio Analyzer - reuse outputs)
3. segmentation (Scene Segmentation - reuse outputs)
4. planning (Visual Planning)
5. motion_plan (Motion Planning)
6. motion_gen (Motion Animation - custom executable React/TSX)
7. motion_validation (Motion & Timeline Validation)
8. timeline (Timeline Build)
9. approval (Timeline Approval - decided by the LLM approval review, no human gate)
10. render (Render Video - Remotion renderer)
11. qc (Final QC - deterministic checks + the Final QC LLM review, which decides about the file; no person)
12. final (Final Video Delivery - verified manifest)

Enforces:
- Idempotent run start and concurrency serialization per project.
- State-aware stage eligibility evaluated from Phase 3 contracts, checkpoints, Phase 2 reviews and the LLM-decided approval gates.
- Safe resume via Phase 3 resume plans without rerunning valid upstream stages.
- Bounded retries for transient failures only; fail-closed on contract, auth, security, or approval gates.
- Cooperative cancellation with run-owned child process cleanup.
- Authentic lifecycle event emission and correlation IDs via backend/agents/communication.py.
- Truthful capability monitoring disclosing the Phase 7 headless Chromium/Remotion live render prerequisite.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from SYSTEM.core import artifact_contracts, pipeline_state, resilience
from SYSTEM.core.resilience import (
    ErrorCategory,
    FailureDiagnostic,
    is_retry_permitted,
    calculate_backoff,
    validate_checkpoint_deep,
    reconcile_interrupted_run,
    verify_path_confinement,
    record_recovery_experience,
)
from SYSTEM.core.errors import ApiError
from SYSTEM.policies import llm_review
from SYSTEM.observability import llm_usage
from SYSTEM.memory import store
from SYSTEM.agents.shared import communication
from SYSTEM.registries.agent_registry import registry
from SYSTEM.agents.shared.contracts import AgentMessage, AgentRequest, AgentResult, MessageType

from VIDEO_ENGINE.pipeline import procs, stage_gate

try:
    from VIDEO_ENGINE.stages import final_qc, timeline_approval
except ImportError:
    from backend import final_qc, timeline_approval

try:
    from SYSTEM.core import config
except ImportError:
    try:
        from backend import config
    except ImportError:
        import config

try:
    from SYSTEM.agents.video_generation_agents.main_orchestrator.diagnostician import orchestrator_diagnostician
    from SYSTEM.agents.video_generation_agents.main_orchestrator.learning_engine import learning_engine
except ImportError:
    orchestrator_diagnostician = None
    learning_engine = None


logger = logging.getLogger("orchestrator")

ACTIVE_STAGES: tuple[str, ...] = pipeline_state.ACTIVE_STAGES
class StageFixError(Exception):
    """A stage's own warning fixer could not solve what is left (the cause is the message)."""


MAX_AUTOFIX_ROUNDS = 2                                                      # rounds of a stage's own warning fixer before the next stage is activated
STAGE_TO_AGENT: dict[str, str] = pipeline_state.STAGE_TO_AGENT_MAP

STAGE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "audio": (),
    "analyzer": ("audio",),
    "segmentation": ("analyzer",),
    "planning": ("segmentation",),
    "assets": ("planning",),
    "motion_plan": ("assets",),
    "motion_gen": ("motion_plan",),
    "motion_validation": ("motion_gen",),
    "timeline": ("motion_validation",),
    "approval": ("timeline",),
    "render": ("approval",),
    "qc": ("render",),
    "final": ("qc",),
}

STAGE_WEIGHTS: dict[str, float] = {
    "audio": 0.05,
    "analyzer": 0.10,
    "segmentation": 0.08,
    "planning": 0.10,
    "assets": 0.04,
    "motion_plan": 0.10,
    "motion_gen": 0.10,
    "motion_validation": 0.08,
    "timeline": 0.07,
    "approval": 0.05,
    "render": 0.13,
    "qc": 0.05,
    "final": 0.05,
}

# In-memory index of active runs and project execution locks
_PROJECT_LOCKS: dict[str, threading.Lock] = {}
_RUN_LOCK = threading.Lock()
_ACTIVE_RUNS: dict[str, "RunRecord"] = {}
_RUN_THREADS: dict[str, threading.Thread] = {}

def _get_project_lock(pid: str) -> threading.Lock:
    return resilience.get_project_mutex(pid)


def is_running(pid: str) -> bool:
    """Returns True if there is an active orchestrator run executing for this project."""
    with _RUN_LOCK:
        run = _ACTIVE_RUNS.get(pid)
        return bool(run and run.status == "running")


def current_run(pid: str) -> RunRecord | None:
    """Returns the currently active orchestrator RunRecord for this project if running."""
    with _RUN_LOCK:
        run = _ACTIVE_RUNS.get(pid)
        if run and run.status == "running":
            return run
        return None


def sanitize_message(msg: str, project_dir: Path | None = None) -> str:
    """Sanitizes sensitive information, secrets, and local filesystem paths from strings."""
    if not msg:
        return ""
    text = str(msg)
    text = resilience.sanitize_secrets(text)
    if project_dir is not None:
        p_str = str(project_dir.resolve()).replace("\\", "/")
        text = text.replace("\\", "/").replace(p_str, f"projects/{project_dir.name}")
    # Also strip absolute windows drive paths if leaked
    text = re.sub(r"[a-zA-Z]:[/\\\\][^\s\"']+", "[CONFINED_PATH]", text)
    return text


def find_browser_executable() -> tuple[str | None, str | None]:
    """Locates an already-installed browser executable without downloading or modifying anything.
    Returns (executable_path, source_type) or (None, None).
    """
    browser_path = os.environ.get("PUPPETEER_EXECUTABLE_PATH") or os.environ.get("CHROME_BIN")
    if browser_path and Path(browser_path).exists():
        return browser_path, "environment_variable"

    # Check Remotion's typical local cache directory without triggering any download
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        cached_chrome = Path(local_app_data) / "remotion" / "chromium"
        if cached_chrome.exists():
            matches = list(cached_chrome.glob("**/chrome.exe"))
            if matches:
                return str(matches[0]), "remotion_cache"

    # Check standard system installation paths (Windows & Linux)
    system_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for cand in system_candidates:
        p = Path(cand)
        if p.exists() and p.is_file():
            return str(p), "system_installed"

    which_chrome = shutil.which("chrome") or shutil.which("google-chrome")
    if which_chrome:
        return which_chrome, "system_path"

    return None, None


def check_system_capabilities() -> dict[str, Any]:
    """Deterministically checks environmental tools and prerequisites without side effects."""
    node_path = shutil.which("node")
    npx_path = shutil.which("npx")
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    remotion_dir = config.REMOTION_DIR
    remotion_pkg = remotion_dir / "package.json"
    remotion_installed = (remotion_dir / "node_modules" / "remotion").exists()

    # Headless Chromium / Puppeteer verification (as noted in Phase 7 report)
    # Check whether a headless browser is deterministically configured
    browser_path, browser_source = find_browser_executable()
    browser_ready = browser_path is not None

    return {
        "tools": {
            "node": {"available": node_path is not None, "path": "node" if node_path else None},
            "npx": {"available": npx_path is not None, "path": "npx" if npx_path else None},
            "ffmpeg": {"available": ffmpeg_path is not None, "path": "ffmpeg" if ffmpeg_path else None},
            "ffprobe": {"available": ffprobe_path is not None, "path": "ffprobe" if ffprobe_path else None},
        },
        "remotion": {
            "root_exists": remotion_dir.exists(),
            "package_json_exists": remotion_pkg.exists(),
            "modules_installed": remotion_installed,
        },
        "browser": {
            "browser_ready": browser_ready,
            "browser_source": browser_source,
            "browser_prerequisite_met": browser_ready,
            "unresolved_limitation": (
                None
                if browser_ready
                else "Headless Chromium/Puppeteer is not preconfigured in the environment. Phase 7 live Remotion render remains an unresolved environment prerequisite. Synthetic/mocked probe tests are utilized for verification."
            ),
        },
        "all_basic_tools_ready": bool(node_path and npx_path and ffmpeg_path and ffprobe_path),
    }


def ensure_motion_planning_artifacts(pdir: Path, aspect: str = "16:9") -> None:
    """Ensures scene_plan.json, prompts_map.json, and baseline composition exist for new motion projects."""
    sp_file = pdir / "scene_plan.json"
    pm_file = pdir / "prompts_map.json"
    if sp_file.exists() and pm_file.exists():
        return

    seg_file = pdir / "scene_segmentation.json"
    scenes = []
    if seg_file.exists():
        try:
            seg_data = json.loads(seg_file.read_text(encoding="utf-8"))
            from VIDEO_ENGINE.stages import visual_planning
            canon = visual_planning.canonical(seg_data)
            for k, c in enumerate(canon):
                meaning_text = c["text"] or f"Scene {c['index'] + 1}"
                end_of_audio = seg_data.get("audio_duration_seconds", c["end"])
                scenes.append({
                    "id": k + 1,
                    "start": 0.0 if k == 0 else c["start"],                          # a planned scene holds its pause: it runs to where the next one starts
                    "end": canon[k + 1]["start"] if k + 1 < len(canon) else end_of_audio,
                    "meaning": meaning_text,
                    "concept": f"Visualizing {meaning_text[:30]}",
                    "mood": "modern, futuristic, digital",
                    "mode": "typography",
                    "pattern": "hero_text",
                    "keywords": [],
                    "params": {"text": meaning_text[:50]},
                })
        except Exception:
            pass

    if not scenes:
        scenes = [{
            "id": 1,
            "start": 0.0,
            "end": 10.0,
            "meaning": "Narration content",
            "concept": "Introductory visual",
            "mood": "modern, futuristic",
            "mode": "typography",
            "pattern": "hero_text",
            "keywords": [],
            "params": {"text": "Metaverse"},
        }]

    sp_data = {
        "style": {
            "suffix": "cinematic futuristic, deep teal and violet, clean typography",
            "palette": ["#0B1620", "#38BDF8", "#818CF8", "#F8FAFC"],
            "grade": "teal-orange",
        },
        "scenes": scenes,
    }
    sp_file.write_text(json.dumps(sp_data, indent=2, ensure_ascii=False), encoding="utf-8")
    if not pm_file.exists():
        pm_file.write_text(json.dumps({"prompts": []}, indent=2), encoding="utf-8")

    remotion_dir = config.REMOTION_DIR
    try:
        subprocess.run(
            ["npx", "tsx", "scripts/build_composition.ts", str(pdir.resolve()), "--no-images"],
            cwd=remotion_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except Exception:
        pass


def classify_error(error: Exception | str) -> tuple[bool, str]:
    """Classifies an error using resilience engine while maintaining (is_transient, code) return contract."""
    cat, code, is_transient = resilience.classify_error(error)
    cat_str = "transient_io_or_network" if is_transient else "non_transient_validation_or_gate"
    return is_transient, cat_str


@dataclass
class RunRecord:
    run_id: str
    project_id: str
    aspect: str = "16:9"
    idempotency_key: str = ""
    status: Literal["queued", "running", "completed", "blocked", "failed", "cancelled"] = "queued"
    current_stage: str | None = None
    stages_completed: list[str] = field(default_factory=list)
    stages_blocked: list[str] = field(default_factory=list)
    stages_failed: list[str] = field(default_factory=list)
    reused_stages: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    error: dict[str, Any] | None = None
    retry_counts: dict[str, int] = field(default_factory=dict)
    cancel_requested: bool = False
    progress_percent: float = 0.0
    correlation_id: str = field(default_factory=lambda: f"corr_{uuid.uuid4().hex[:8]}")
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunRecord":
        return cls(**data)


def _runs_dir(pdir: Path) -> Path:
    rdir = pdir / "runs"
    rdir.mkdir(parents=True, exist_ok=True)
    return rdir


def _run_file(pdir: Path, run_id: str) -> Path:
    return _runs_dir(pdir) / f"{run_id}.json"


def save_run_record(pdir: Path, run: RunRecord) -> None:
    """Atomically persists a run record to disk under project info lock."""
    run.updated_at = time.time()
    f = _run_file(pdir, run.run_id)
    tmp = f.with_suffix(".tmp")
    with store._info_lock(pdir):
        tmp.write_text(json.dumps(run.to_dict(), indent=2), encoding="utf-8")
        os.replace(tmp, f)


def load_run_record(pdir: Path, run_id: str) -> RunRecord | None:
    f = _run_file(pdir, run_id)
    if not f.exists():
        return None
    try:
        with store._info_lock(pdir):                                    # the lock save_run_record holds: on Windows a read during its os.replace makes the write fail (WinError 5)
            data = json.loads(f.read_text(encoding="utf-8"))
        return RunRecord.from_dict(data)
    except Exception:
        return None


def list_project_runs(project_id: str, limit: int = 50) -> list[dict[str, Any]]:
    try:
        pdir = store.project_dir(project_id)
    except Exception:
        return []
    rdir = pdir / "runs"
    if not rdir.exists():
        return []
    records = []
    for f in sorted(rdir.glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            with store._info_lock(pdir):                                # see load_run_record
                records.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return records


def compute_idempotency_key(project_id: str, aspect: str, from_stage: str | None, resume: bool, to_stage: str | None = None) -> str:
    raw = f"{project_id}:{aspect}:{from_stage or 'start'}:{to_stage or 'end'}:{resume}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def evaluate_stage_eligibility(
    pdir: Path,
    stage_id: str,
    aspect: str = "16:9",
    auto_pilot_mode: bool = False,
) -> dict[str, Any]:
    """Evaluates whether a stage is eligible to execute according to DAG and gate policies."""
    if stage_id not in ACTIVE_STAGES:
        return {
            "eligible": False,
            "stage_id": stage_id,
            "blockers": [f"Unknown stage '{stage_id}'"],
            "reusable": False,
            "status": "blocked",
            "capability_blocker": None,
        }

    pstate = pipeline_state.load_pipeline_state(pdir)
    srec = pstate.stages.get(stage_id)
    status = srec.status if srec else "pending"

    blockers: list[str] = []
    capability_blocker = None

    # 1. Dependency check: all upstream stages must be 'completed'
    deps = STAGE_DEPENDENCIES.get(stage_id, ())
    for dep in deps:
        dep_rec = pstate.stages.get(dep)
        if dep_rec is not None and dep_rec.status == "skipped":              # a stage this project never had (added later) does not block its dependants
            continue
        if not dep_rec or dep_rec.status != "completed":
            # Attempt deep validation to reconcile valid existing disk artifacts
            try:
                is_valid, _, _ = validate_checkpoint_deep(pdir, dep, aspect)
                if not is_valid:
                    if dep == "audio" and any((pdir / f"audio.{ext}").exists() for ext in ("mp3", "wav", "m4a", "ogg", "flac")):
                        is_valid = True
                    elif dep == "analyzer" and any((pdir / f).exists() for f in ("transcript_corrected.json", "transcript_fixed.json", "audio_analysis.json", "transcript.json")):
                        is_valid = True
                    elif dep == "segmentation" and (pdir / "scene_segmentation.json").exists():
                        from VIDEO_ENGINE.stages import scene_segmentation
                        is_valid = scene_segmentation.load_fresh(pdir) is not None
                    elif dep == "motion_validation" and (pdir / f"motion_timeline_validation{'_9x16' if aspect == '9:16' else ''}.json").exists():
                        from VIDEO_ENGINE.stages import motion_validation as mv_mod
                        is_valid = mv_mod.is_valid(pdir, aspect)
                    elif dep == "timeline" and (pdir / f"timeline_build_report{'_9x16' if aspect == '9:16' else ''}.json").exists():
                        from VIDEO_ENGINE.stages import timeline_build as tb_mod
                        tbs = tb_mod.load(pdir, aspect)
                        is_valid = bool(tbs and tbs.get("current") and tbs.get("report", {}).get("status") == "completed")
                    elif dep == "approval":
                        from VIDEO_ENGINE.stages import timeline_approval as ta_mod
                        snap = ta_mod.snapshot(pdir, aspect)
                        is_valid = snap.get("status") == "approved"
                if is_valid:
                    pipeline_state.transition_stage(pdir, dep, "completed", aspect=aspect)
                    pstate = pipeline_state.load_pipeline_state(pdir)
                    dep_rec = pstate.stages.get(dep)
            except Exception:
                pass
            if not dep_rec or dep_rec.status != "completed":
                blockers.append(f"Upstream stage '{dep}' is {dep_rec.status if dep_rec else 'missing'}")
                continue
        # completed is not enough: the upstream stage's own unresolved errors and warnings keep this stage blocked until they are fixed (or a person accepts the warnings)
        if (open_issues := stage_gate.unresolved(pdir, dep, aspect)):
            blockers.append(f"Upstream stage '{dep}' has unresolved issues: {stage_gate.describe(open_issues)}")

    # 2. Check stage-specific gates & capabilities
    if stage_id == "approval":
        # Timeline Approval is decided by the LLM approval review (timeline_approval.auto_approve), never by a person: the stage is eligible when the version has no blockers
        snap = timeline_approval.snapshot(pdir, aspect)
        if snap.get("blockers"):
            blockers.extend(snap["blockers"])

    elif stage_id == "render":
        # Render Video requires the current timeline version to be approved (by the LLM review) and the system capabilities
        snap = timeline_approval.snapshot(pdir, aspect)
        if snap["status"] != "approved":
            blockers.append(f"Render Video requires the current timeline version to be approved by the LLM approval review (approval status '{snap['status']}')")
        if snap.get("blockers"):
            blockers.extend(snap["blockers"])
        caps = check_system_capabilities()
        if not caps["browser"]["browser_ready"]:
            capability_blocker = caps["browser"]["unresolved_limitation"]

    elif stage_id == "qc":
        # Final QC runs on the rendered video; its decision is the Final QC LLM review's (final_qc.llm_decide), never a person's
        vid = pdir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")
        if not vid.exists():
            blockers.append("Final QC requires completed render video")

    elif stage_id == "final":
        # Final Delivery requires Final QC stage to be completed
        dm_check = pstate.stages.get("qc")
        if not dm_check or dm_check.status != "completed":
            blockers.append("Final Video Delivery requires Final QC stage to be completed")
        else:
            qc_gate = final_qc.gate(pdir, aspect)
            if qc_gate:
                blockers.extend(qc_gate)

    is_eligible = len(blockers) == 0

    return {
        "eligible": is_eligible,
        "stage_id": stage_id,
        "status": status,
        "blockers": blockers,
        "reusable": bool(srec and srec.reusable),
        "capability_blocker": capability_blocker,
    }


class PipelineOrchestrator:
    """Authoritative Run Coordinator for the 12-stage Motion-Only pipeline."""

    def __init__(self, project_id: str, aspect: str = "16:9", auto_pilot_mode: bool = True) -> None:
        self.project_id = project_id
        self.aspect = aspect
        self.auto_pilot_mode = auto_pilot_mode
        self.pdir = store.project_dir(project_id)
        self.project_lock = _get_project_lock(project_id)

    def get_active_run(self) -> RunRecord | None:
        with self.project_lock:
            run = _ACTIVE_RUNS.get(self.project_id)
            if run and run.status == "running":
                return run
            return None

    def start_run(
        self,
        from_stage: str | None = None,
        to_stage: str | None = None,
        resume: bool = True,
        idempotency_key: str | None = None,
        max_retries: int = 3,
        synchronous: bool = False,
        auto_pilot_mode: bool | None = None,
    ) -> RunRecord:
        """Starts or safely resumes an orchestrator run with idempotency and concurrency guards."""
        with self.project_lock:
            if auto_pilot_mode is not None:
                self.auto_pilot_mode = auto_pilot_mode
            # Reconcile orphaned runs and crashed executions on startup or prior to dispatch
            pipeline_state.reconcile_orphaned_jobs(self.pdir)
            try:
                reconcile_interrupted_run(self.pdir, self.project_id, self.aspect)
            except Exception as _reconcile_err:
                logger.warning(f"Crash reconciliation notice for project '{self.project_id}': {_reconcile_err}")

            active = _ACTIVE_RUNS.get(self.project_id)
            if active and active.status == "running":
                computed_key = idempotency_key or compute_idempotency_key(self.project_id, self.aspect, from_stage, resume, to_stage)
                if active.idempotency_key == computed_key:
                    # Idempotent return of existing active run
                    return active
                raise ApiError(
                    409,
                    "run_in_progress",
                    f"Run '{active.run_id}' is already executing for project '{self.project_id}'",
                    "Cancel the active run before starting a new run with different parameters",
                )

            run_id = f"run_{uuid.uuid4().hex[:8]}"
            computed_key = idempotency_key or compute_idempotency_key(self.project_id, self.aspect, from_stage, resume, to_stage)
            correlation_id = f"corr_{uuid.uuid4().hex[:8]}"

            run = RunRecord(
                run_id=run_id,
                project_id=self.project_id,
                aspect=self.aspect,
                idempotency_key=computed_key,
                status="running",
                started_at=time.time(),
                updated_at=time.time(),
                correlation_id=correlation_id,
                metadata={"auto_pilot": self.auto_pilot_mode},
            )

            # Store active run
            _ACTIVE_RUNS[self.project_id] = run
            save_run_record(self.pdir, run)

            # Mirror building state into project.json for UI header & list sync
            try:
                store.set_state(self.project_id, "building")
            except Exception:
                pass

            # Emit run_started lifecycle event
            communication.publish_lifecycle_event(
                project_id=self.project_id,
                stage_id=from_stage or "pipeline",
                sender_agent_id="main_orchestrator",
                event="run_started",
                detail=f"Run '{run_id}' started for aspect '{self.aspect}' (from_stage={from_stage}, to_stage={to_stage}, resume={resume})",
                run_id=run_id,
                correlation_id=correlation_id,
                metadata={"idempotency_key": computed_key, "resume": resume, "from_stage": from_stage, "to_stage": to_stage, "auto_pilot": self.auto_pilot_mode},
            )

        if synchronous:
            self._execute_run(run, from_stage=from_stage, to_stage=to_stage, resume=resume, max_retries=max_retries)
        else:
            t = threading.Thread(
                target=self._execute_run,
                args=(run,),
                kwargs={"from_stage": from_stage, "to_stage": to_stage, "resume": resume, "max_retries": max_retries},
                name=f"orchestrator_{self.project_id}_{run_id}",
                daemon=True,
            )
            with _RUN_LOCK:
                _RUN_THREADS[self.project_id] = t
            t.start()

        return run

    def cancel_run(self, run_id: str | None = None) -> RunRecord:
        """Cooperatively requests run cancellation, signals active processes, and transitions state."""
        with self.project_lock:
            run = _ACTIVE_RUNS.get(self.project_id)
            if not run or (run_id and run.run_id != run_id):
                # Search disk for requested run
                if run_id:
                    loaded = load_run_record(self.pdir, run_id)
                    if loaded:
                        return loaded
                raise ApiError(404, "no_active_run", f"No active run found for project '{self.project_id}'")

            run.cancel_requested = True
            run.updated_at = time.time()

            communication.publish_lifecycle_event(
                project_id=self.project_id,
                stage_id=run.current_stage or "pipeline",
                sender_agent_id="main_orchestrator",
                event="run_cancel_requested",
                detail=f"Cancellation requested by user for run '{run.run_id}'",
                run_id=run.run_id,
                correlation_id=run.correlation_id,
            )

            # Signal any executing process handle
            procs.kill(self.project_id)

            # Mark current stage cancelled if running
            if run.current_stage:
                try:
                    pipeline_state.transition_stage(
                        self.pdir,
                        run.current_stage,
                        "cancelled",
                        aspect=self.aspect,
                        error_message="Stage cancelled by user",
                    )
                except Exception:
                    pass

            run.status = "cancelled"
            run.completed_at = time.time()
            save_run_record(self.pdir, run)
            try:
                store.set_state(self.project_id, "cancelled")
            except Exception:
                pass

            communication.publish_lifecycle_event(
                project_id=self.project_id,
                stage_id=run.current_stage or "pipeline",
                sender_agent_id="main_orchestrator",
                event="run_cancelled",
                detail=f"Run '{run.run_id}' marked cancelled",
                run_id=run.run_id,
                correlation_id=run.correlation_id,
            )

            return run

    def _analysis_needed(self) -> bool:
        """The Audio Analyzer has work: there is no transcript yet, the LLM has not checked it (an analysis made before the check was part of it, or one whose check could not finish), or its
        approval of the final transcript is missing or out of date."""
        from VIDEO_ENGINE.stages import transcript_review
        return not (self.pdir / "transcript.json").exists() or not transcript_review.is_verified(self.pdir)

    def _analyze_audio(self, run: RunRecord) -> None:
        """The Audio Analyzer: speech-to-text only when there is no transcript, the LLM check and correction of it (with the corrected words re-aligned), then the cuts. Finished steps are
        reused (`legacy_pipeline_adapter.run_analysis`), Whisper never runs again for a project that has its transcript."""
        from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter
        communication.publish_lifecycle_event(
            project_id=self.project_id,
            stage_id="analyzer",
            sender_agent_id="audio_analyzer",
            event="stage_progress",
            detail="Analyzing the audio: transcript, LLM check and correction, cuts...",
            run_id=run.run_id,
            correlation_id=run.correlation_id,
        )
        legacy_pipeline_adapter.run_analysis(self.pdir)

    def _segmentation_needed(self) -> bool:
        """The scenes are missing or out of date (another transcript, or made under older scene rules)."""
        from VIDEO_ENGINE.stages import scene_segmentation
        return scene_segmentation.load_fresh(self.pdir) is None

    def _resolve_stage_issues(self, stage_id: str, run: RunRecord, rerun) -> None:
        """The next stage starts only after this one finished with nothing unresolved, and nobody has to accept a warning for that: the stage's own fixer solves its warnings here (bounded rounds,
        each followed by a fresh LLM review of the changed report). `rerun` executes the stage again (a fixer that only decides, like Motion Planning's, needs it to apply the decisions).
        What the fixer cannot solve stays, the event names the cause, and the next stage waits for it."""
        from VIDEO_ENGINE.stages import motion_autofix, motion_planning, visual_planning
        from VIDEO_ENGINE.stages.promptgen import GenError

        def fix_motion_plan() -> None:
            done = motion_planning.solve(self.pdir, self.aspect)
            if not (done["moved"] or done["earlier"] or done["accepted"]):
                raise StageFixError("no warning is left that can be solved automatically")
            motion_autofix.count(self.pdir, done)                      # at most MAX_AUTO_FIXES attempts per scene plan, counted on disk
            res = rerun()
            if res.status != "succeeded":
                raise StageFixError(res.error or res.summary or "the stage failed when it ran again with the fixes")

        fixer = {"planning": lambda: visual_planning.fix_warnings(self.pdir), "motion_plan": fix_motion_plan}.get(stage_id)
        for _ in range(MAX_AUTOFIX_ROUNDS):
            open_issues = stage_gate.unresolved(self.pdir, stage_id, self.aspect)
            if fixer is None or not open_issues:
                return
            communication.publish_lifecycle_event(
                project_id=self.project_id, stage_id=stage_id, sender_agent_id="main_orchestrator", event="stage_progress",
                detail=f"Fixing the stage's own warnings before the next stage starts: {stage_gate.describe(open_issues)}", run_id=run.run_id, correlation_id=run.correlation_id,
            )
            try:
                fixer()
            except (GenError, motion_planning.MotionError, motion_autofix.Exhausted, StageFixError) as e:
                communication.publish_lifecycle_event(
                    project_id=self.project_id, stage_id=stage_id, sender_agent_id="main_orchestrator", event="stage_progress",
                    detail=f"The warnings of '{stage_id}' could not be fixed automatically: {e}", run_id=run.run_id, correlation_id=run.correlation_id,
                )
                return
            llm_review.run_stage_llm_review(self.pdir, stage_id, aspect=self.aspect, auto_pilot=self.auto_pilot_mode)

    def _planning_needed(self) -> bool:
        """No scene plan yet, or one that does not follow the current Scene Segmentation (and nothing depends on it)."""
        from VIDEO_ENGINE.stages import autoplan, visual_planning
        if autoplan.needs_plan(self.pdir):
            return True
        return bool(visual_planning.plan_mismatch(self.pdir)) and autoplan.replace_blocker(self.pdir) is None

    def _plan_scenes(self, run: RunRecord) -> None:
        """The real planner (translation, scene plan, visual plan from Scene Segmentation's scenes), never a placeholder; a plan that does not follow the segmentation is replaced (the old one is
        kept in plan_backups/). Failing to plan stops the stage with the cause."""
        from VIDEO_ENGINE.stages import autoplan
        communication.publish_lifecycle_event(
            project_id=self.project_id,
            stage_id="planning",
            sender_agent_id="visual_planning",
            event="stage_progress",
            detail="Planning the scenes from the Scene Segmentation scenes...",
            run_id=run.run_id,
            correlation_id=run.correlation_id,
        )
        autoplan.run(self.pdir, replace=not autoplan.needs_plan(self.pdir))

    def _segment_scenes(self, run: RunRecord) -> None:
        """Scene Segmentation cuts the scenes from the transcript the Audio Analyzer checked with the LLM (`transcript_corrected.json` when it corrected something); its own LLM only decides the
        scene boundaries and grouping. A transcript the LLM has not verified stops here with the cause, it is never corrected a second time inside this stage."""
        from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter
        from VIDEO_ENGINE.stages import transcript_review
        if not transcript_review.is_verified(self.pdir):
            raise legacy_pipeline_adapter.StepError("The transcript has not been verified by the LLM yet: run the Audio Analyzer (it checks and corrects the transcript) before Scene Segmentation.")
        communication.publish_lifecycle_event(
            project_id=self.project_id,
            stage_id="segmentation",
            sender_agent_id="scene_segmentation",
            event="stage_progress",
            detail="Segmenting scenes based on speech and pause boundaries...",
            run_id=run.run_id,
            correlation_id=run.correlation_id,
        )
        legacy_pipeline_adapter.execute(self.pdir, "segment", legacy_pipeline_adapter.Ctx())

    def _execute_run(
        self,
        run: RunRecord,
        from_stage: str | None = None,
        to_stage: str | None = None,
        resume: bool = True,
        max_retries: int = 3,
    ) -> None:
        """Internal execution loop coordinating stage dispatch, checkpoint reuse, bounded retry, and terminal states."""
        try:
            # 1. Determine execution plan via Phase 3 resume resolution
            stages_to_run: list[str] = []
            reused_stages: list[str] = []

            if resume and not from_stage:
                resume_plan = pipeline_state.resolve_resume_plan(self.pdir, self.aspect)
                earliest_invalid = resume_plan["earliest_invalid_stage"]
                reused_ids = {rc["stage_id"] for rc in resume_plan["reusable_checkpoints"]}

                for sid in ACTIVE_STAGES:
                    if sid in reused_ids:
                        is_valid, issues, _ = validate_checkpoint_deep(self.pdir, sid, self.aspect)
                        if is_valid:
                            reused_stages.append(sid)
                            communication.publish_lifecycle_event(
                                project_id=self.project_id,
                                stage_id=sid,
                                sender_agent_id="main_orchestrator",
                                event="recovery_verified_previous",
                                detail=f"Verified valid checkpoint for stage '{sid}'. Reusing artifact without rerunning.",
                                run_id=run.run_id,
                                correlation_id=run.correlation_id,
                            )
                        else:
                            logger.warning(f"Checkpoint for stage '{sid}' failed deep validation: {issues}. Invalidating and re-running.")
                            stages_to_run.append(sid)
                    else:
                        stages_to_run.append(sid)

                run.reused_stages = reused_stages
                run.stages_completed = list(reused_stages)

                if not stages_to_run:
                    # All stages completed and checkpoints fresh
                    run.status = "completed"
                    run.completed_at = time.time()
                    run.progress_percent = 100.0
                    save_run_record(self.pdir, run)
                    try:
                        store.set_state(self.project_id, "done")
                    except Exception:
                        pass
                    communication.publish_lifecycle_event(
                        project_id=self.project_id,
                        stage_id="final",
                        sender_agent_id="main_orchestrator",
                        event="run_completed",
                        detail=f"All 12 stages verified from fresh checkpoints. Run '{run.run_id}' completed.",
                        run_id=run.run_id,
                        correlation_id=run.correlation_id,
                    )
                    return

            else:
                # Custom starting stage
                start_idx = ACTIVE_STAGES.index(from_stage) if from_stage in ACTIVE_STAGES else 0
                reused_stages = list(ACTIVE_STAGES[:start_idx])
                stages_to_run = list(ACTIVE_STAGES[start_idx:])
                run.reused_stages = reused_stages
                run.stages_completed = list(reused_stages)

            if to_stage and to_stage in ACTIVE_STAGES:
                end_idx = ACTIVE_STAGES.index(to_stage) + 1
                stages_to_run = [s for s in stages_to_run if ACTIVE_STAGES.index(s) < end_idx]

            # 2. Sequential DAG execution
            for stage_id in stages_to_run:
                # Cooperative cancellation check
                if run.cancel_requested:
                    run.status = "cancelled"
                    run.completed_at = time.time()
                    save_run_record(self.pdir, run)
                    communication.publish_lifecycle_event(
                        project_id=self.project_id,
                        stage_id=stage_id,
                        sender_agent_id="main_orchestrator",
                        event="run_cancelled",
                        detail=f"Execution halted due to cancellation before stage '{stage_id}'",
                        run_id=run.run_id,
                        correlation_id=run.correlation_id,
                    )
                    return

                run.current_stage = stage_id
                save_run_record(self.pdir, run)

                # Check stage eligibility
                elig = evaluate_stage_eligibility(self.pdir, stage_id, self.aspect, auto_pilot_mode=self.auto_pilot_mode)

                if not elig["eligible"]:
                    # Stage blocked by a gate or a missing input
                    status_target = "blocked"
                    err_detail = "; ".join(elig["blockers"])
                    try:
                        pipeline_state.transition_stage(
                            self.pdir,
                            stage_id,
                            status_target,
                            aspect=self.aspect,
                            error_message=err_detail,
                        )
                    except Exception:
                        pass

                    run.status = "blocked"
                    run.stages_blocked.append(stage_id)
                    run.error = {
                        "stage_id": stage_id,
                        "code": "stage_eligibility_blocked",
                        "message": sanitize_message(err_detail, self.pdir),
                    }
                    save_run_record(self.pdir, run)
                    try:
                        store.set_state(self.project_id, "blocked")
                    except Exception:
                        pass

                    communication.publish_lifecycle_event(
                        project_id=self.project_id,
                        stage_id=stage_id,
                        sender_agent_id="main_orchestrator",
                        event="stage_blocked",
                        detail=f"Stage '{stage_id}' is blocked: {err_detail}",
                        run_id=run.run_id,
                        correlation_id=run.correlation_id,
                        metadata={"blockers": elig["blockers"]},
                    )
                    return

                # Stage claimed
                communication.publish_lifecycle_event(
                    project_id=self.project_id,
                    stage_id=stage_id,
                    sender_agent_id="main_orchestrator",
                    event="stage_claimed",
                    detail=f"Stage '{stage_id}' claimed by orchestrator",
                    run_id=run.run_id,
                    correlation_id=run.correlation_id,
                )

                # Execute stage with bounded retry for transient faults
                attempt = 0
                stage_succeeded = False

                while attempt <= max_retries and not stage_succeeded:
                    if run.cancel_requested:
                        run.status = "cancelled"
                        run.completed_at = time.time()
                        save_run_record(self.pdir, run)
                        return

                    attempt += 1
                    run.retry_counts[stage_id] = attempt - 1

                    try:
                        # Move to running
                        pipeline_state.transition_stage(
                            self.pdir,
                            stage_id,
                            "running",
                            aspect=self.aspect,
                        )

                        communication.publish_lifecycle_event(
                            project_id=self.project_id,
                            stage_id=stage_id,
                            sender_agent_id=STAGE_TO_AGENT.get(stage_id, "main_orchestrator"),
                            event="stage_started",
                            detail=f"Stage '{stage_id}' execution started (attempt {attempt})",
                            run_id=run.run_id,
                            correlation_id=run.correlation_id,
                        )

                        # Invoke the registered Stage Adapter
                        agent_id = STAGE_TO_AGENT.get(stage_id)
                        agent_adapter = registry.get_adapter(agent_id) if agent_id else None

                        if not agent_adapter:
                            raise RuntimeError(f"No registered agent adapter found for stage '{stage_id}'")

                        req = AgentRequest(
                            project_id=self.project_id,
                            agent_id=agent_id,
                            stage_id=stage_id,
                            run_id=run.run_id,
                            correlation_id=run.correlation_id,
                            parameters={
                                "aspect": self.aspect,
                                "resume": resume,
                                "force": not resume,
                                "auto_pilot": self.auto_pilot_mode,
                                "task_id": run.run_id,
                            },
                        )

                        # If brand-new project has unanalyzed uploaded audio, coordinate initial upstream pipeline steps
                        if stage_id == "analyzer" and self._analysis_needed():
                            self._analyze_audio(run)

                        elif stage_id == "segmentation" and self._segmentation_needed():
                            self._segment_scenes(run)

                        elif stage_id == "planning" and self._planning_needed():
                            self._plan_scenes(run)

                        # Validate input constraints
                        val_errs = agent_adapter.validate(self.pdir, req)
                        if val_errs:
                            raise ApiError(400, "adapter_validation_error", "; ".join(val_errs))

                        # Execute adapter
                        res: AgentResult = agent_adapter.execute(self.pdir, req)

                        if res.status == "succeeded":
                            # Ensure Phase 2 mandatory LLM review gate is executed and fresh
                            try:
                                llm_review.run_stage_llm_review(
                                    self.pdir,
                                    stage_id,
                                    aspect=self.aspect,
                                    auto_pilot=self.auto_pilot_mode,
                                )
                            except Exception as review_err:
                                logger.warning(f"Stage {stage_id} review execution: {review_err}")

                            self._resolve_stage_issues(stage_id, run, lambda: agent_adapter.execute(self.pdir, req))

                            # Strict fail-closed completion transition
                            pipeline_state.transition_stage(
                                self.pdir,
                                stage_id,
                                "completed",
                                aspect=self.aspect,
                            )
                            stage_succeeded = True
                            run.stages_completed.append(stage_id)

                            if attempt > 1:
                                record_recovery_experience(
                                    agent_id=agent_id or "main_orchestrator",
                                    stage_id=stage_id,
                                    project_id=self.project_id,
                                    task_id=run.run_id,
                                    outcome="succeeded",
                                    attempt=attempt,
                                    details={"recovered_after_retries": attempt - 1},
                                )
                                if learning_engine:
                                    try:
                                        prior_act = run.metadata.get("prior_recovery_actions", {}).get(stage_id, ["RETRY_WITH_BACKOFF"])[-1]
                                        learning_engine.record_candidate_lesson(
                                            stage_id=stage_id,
                                            error_category="TRANSIENT",
                                            error_code="transient_recovered",
                                            trigger_condition=f"Recovered stage '{stage_id}' on attempt {attempt}",
                                            recommended_action=prior_act,
                                            repair_recipe=f"Applied recovery action '{prior_act}' with backoff",
                                            rationale=f"Empirically validated recovery of stage {stage_id} on attempt {attempt}.",
                                            evidence_ref=f"run:{run.run_id}:attempt_{attempt}",
                                        )
                                    except Exception as _lsn_err:
                                        logger.debug(f"Candidate lesson recording notice: {_lsn_err}")


                            # Calculate truthful progress percentage
                            completed_count = len(set(run.stages_completed))
                            total_count = len(ACTIVE_STAGES)
                            run.progress_percent = round((completed_count / total_count) * 100.0, 1)

                            communication.publish_lifecycle_event(
                                project_id=self.project_id,
                                stage_id=stage_id,
                                sender_agent_id=agent_id,
                                event="stage_completed",
                                detail=f"Stage '{stage_id}' completed successfully: {res.summary}",
                                run_id=run.run_id,
                                correlation_id=run.correlation_id,
                            )

                            # Record verified handoff to next stage if present
                            curr_idx = ACTIVE_STAGES.index(stage_id)
                            if curr_idx + 1 < len(ACTIVE_STAGES):
                                next_stage = ACTIVE_STAGES[curr_idx + 1]
                                next_agent = STAGE_TO_AGENT.get(next_stage, "main_orchestrator")
                                communication.publish_handoff(
                                    project_id=self.project_id,
                                    stage_id=stage_id,
                                    sender_agent_id=agent_id,
                                    recipient_agent_id=next_agent,
                                    reason=f"Stage '{stage_id}' completed; advancing to '{next_stage}'",
                                    run_id=run.run_id,
                                    correlation_id=run.correlation_id,
                                )

                        elif res.status in ("blocked", "needs_review"):
                            # Blocked, or the LLM review did not approve
                            pipeline_state.transition_stage(
                                self.pdir,
                                stage_id,
                                res.status,
                                aspect=self.aspect,
                                error_message=res.summary,
                            )
                            run.status = "blocked"
                            run.stages_blocked.append(stage_id)
                            run.error = {
                                "stage_id": stage_id,
                                "code": f"stage_{res.status}",
                                "message": sanitize_message(res.summary, self.pdir),
                            }
                            save_run_record(self.pdir, run)

                            communication.publish_lifecycle_event(
                                project_id=self.project_id,
                                stage_id=stage_id,
                                sender_agent_id=agent_id,
                                event="stage_blocked",
                                detail=f"Stage '{stage_id}' entered {res.status}: {res.summary}",
                                run_id=run.run_id,
                                correlation_id=run.correlation_id,
                            )
                            return

                        else:
                            # Failed execution
                            raise RuntimeError(res.error or res.summary or f"Stage {stage_id} returned failed status")

                    except Exception as err:
                        cat, code, is_transient = resilience.classify_error(err)
                        retry_ok, retry_reason = is_retry_permitted(
                            category=cat,
                            current_attempt=attempt,
                            max_retries=max_retries,
                            is_cancelled=run.cancel_requested,
                        )
                        clean_err = sanitize_message(str(err), self.pdir)

                        diag = FailureDiagnostic(
                            project_id=self.project_id,
                            task_id=run.run_id,
                            agent_id=STAGE_TO_AGENT.get(stage_id, "main_orchestrator"),
                            stage_id=stage_id,
                            category=cat.value,
                            code=code,
                            message=clean_err,
                            recovery_permitted=retry_ok,
                            attempt=attempt,
                            retry_limit=max_retries,
                            checkpoint_ref=f"checkpoint_{stage_id}",
                            current_task_state="retrying" if retry_ok else "failed",
                            blocker_reason=retry_reason if not retry_ok else None,
                        )

                        # Consult Intelligent Diagnostician & Lesson Store
                        diag_report = None
                        if orchestrator_diagnostician and learning_engine:
                            try:
                                lessons = learning_engine.retrieve_lessons(stage_id=stage_id, tier="verified")
                                prior_acts = run.metadata.get("prior_recovery_actions", {}).get(stage_id, [])
                                diag_report = orchestrator_diagnostician.diagnose_and_prescribe(
                                    project_dir=self.pdir,
                                    stage_id=stage_id,
                                    error=err,
                                    attempt=attempt,
                                    max_retries=max_retries,
                                    prior_actions=prior_acts,
                                    available_lessons=[l.to_dict() for l in lessons],
                                    aspect=self.aspect,
                                )
                                # If targeted artifact repair is recommended, apply it
                                if diag_report.recommended_action == "REPAIR_INTERMEDIATE_ARTIFACT":
                                    orchestrator_diagnostician.apply_repair(self.pdir, stage_id, diag_report)

                                run.metadata.setdefault("prior_recovery_actions", {}).setdefault(stage_id, []).append(diag_report.recommended_action)
                                run.metadata.setdefault("diagnostic_history", []).append(diag_report.to_dict())
                            except Exception as diag_err:
                                logger.debug(f"Diagnostician advisory notice: {diag_err}")

                        if retry_ok:
                            delay = calculate_backoff(attempt, base_seconds=0.5, max_seconds=4.0, jitter=True)
                            logger.warning(
                                f"Transient failure in stage '{stage_id}' (attempt {attempt}/{max_retries}, code={code}): {clean_err}. Backoff: {delay}s. Action: {diag_report.recommended_action if diag_report else 'RETRY_WITH_BACKOFF'}."
                            )
                            # Emit recovery detected
                            recovery_detail = (
                                f"Issue detected in stage '{stage_id}' ({code}): {clean_err}. "
                                f"Prescribed recovery: {diag_report.recommended_action if diag_report else 'RETRY_WITH_BACKOFF'}"
                            )
                            communication.publish_lifecycle_event(
                                project_id=self.project_id,
                                stage_id=stage_id,
                                sender_agent_id="main_orchestrator",
                                event="recovery_detected",
                                detail=recovery_detail,
                                run_id=run.run_id,
                                correlation_id=run.correlation_id,
                                metadata={
                                    "diagnostic": diag.to_dict(),
                                    "intelligent_diagnosis": diag_report.to_dict() if diag_report else None,
                                },
                            )
                            # Emit recovery safe to retry
                            communication.publish_lifecycle_event(
                                project_id=self.project_id,
                                stage_id=stage_id,
                                sender_agent_id="main_orchestrator",
                                event="recovery_safe_to_retry",
                                detail=f"Verified safe to retry stage '{stage_id}'. Scheduling attempt {attempt + 1}/{max_retries}.",
                                run_id=run.run_id,
                                correlation_id=run.correlation_id,
                                metadata={"delay_seconds": delay},
                            )
                            # Emit recovery retrying
                            communication.publish_lifecycle_event(
                                project_id=self.project_id,
                                stage_id=stage_id,
                                sender_agent_id="main_orchestrator",
                                event="recovery_retrying",
                                detail=f"Retrying stage '{stage_id}' (attempt {attempt + 1})...",
                                run_id=run.run_id,
                                correlation_id=run.correlation_id,
                            )
                            time.sleep(delay)
                        else:
                            # Non-transient or retry budget exhausted: fail closed
                            try:
                                pipeline_state.transition_stage(
                                    self.pdir,
                                    stage_id,
                                    "failed",
                                    aspect=self.aspect,
                                    error_code=code,
                                    error_message=clean_err,
                                )
                            except Exception as te:                 # e.g. the stage already set itself 'blocked' (its LLM gate): keep that state, the run still records the real cause below
                                logger.warning(f"Stage '{stage_id}' keeps its state ({te}); run error: {clean_err}")
                            run.status = "failed"
                            run.stages_failed.append(stage_id)
                            run.completed_at = time.time()
                            run.error = diag.to_dict()
                            save_run_record(self.pdir, run)
                            try:
                                store.set_state(self.project_id, "failed")
                            except Exception:
                                pass

                            record_recovery_experience(
                                agent_id=STAGE_TO_AGENT.get(stage_id, "main_orchestrator"),
                                stage_id=stage_id,
                                project_id=self.project_id,
                                task_id=run.run_id,
                                outcome="failed",
                                error_category=cat.value,
                                attempt=attempt,
                                details={"diagnostic": diag.to_dict()},
                            )

                            # Emit unresolvable event
                            communication.publish_lifecycle_event(
                                project_id=self.project_id,
                                stage_id=stage_id,
                                sender_agent_id="main_orchestrator",
                                event="recovery_unresolvable",
                                detail=f"Stage '{stage_id}' could not be resolved automatically: {clean_err} ({retry_reason})",
                                run_id=run.run_id,
                                correlation_id=run.correlation_id,
                                metadata={"diagnostic": diag.to_dict()},
                            )
                            communication.publish_lifecycle_event(
                                project_id=self.project_id,
                                stage_id=stage_id,
                                sender_agent_id="main_orchestrator",
                                event="stage_failed",
                                detail=f"Stage '{stage_id}' failed: {clean_err}",
                                run_id=run.run_id,
                                correlation_id=run.correlation_id,
                            )
                            return

            # All stages completed successfully
            run.status = "completed"
            run.completed_at = time.time()
            run.progress_percent = 100.0
            run.current_stage = None
            save_run_record(self.pdir, run)
            try:
                store.set_state(self.project_id, "done")
            except Exception:
                pass

            communication.publish_lifecycle_event(
                project_id=self.project_id,
                stage_id="final",
                sender_agent_id="main_orchestrator",
                event="run_completed",
                detail=f"All {len(ACTIVE_STAGES)} stages completed successfully. Run '{run.run_id}' finished.",
                run_id=run.run_id,
                correlation_id=run.correlation_id,
            )

        except Exception as e:
            clean_err = sanitize_message(str(e), self.pdir)
            run.status = "failed"
            run.completed_at = time.time()
            run.error = {"code": "unhandled_orchestrator_error", "message": clean_err}
            save_run_record(self.pdir, run)
            try:
                store.set_state(self.project_id, "failed")
            except Exception:
                pass

            try:
                communication.publish_lifecycle_event(
                    project_id=self.project_id,
                    stage_id="pipeline",
                    sender_agent_id="main_orchestrator",
                    event="run_failed",
                    detail=f"Run '{run.run_id}' encountered unexpected failure: {clean_err}",
                    run_id=run.run_id,
                    correlation_id=run.correlation_id,
                )
            except Exception:
                pass


def get_monitoring_status(project_id: str, aspect: str = "16:9") -> dict[str, Any]:
    """Assembles authoritative, truth-in-monitoring status across stages, gates, usage, and environment."""
    try:
        pdir = store.project_dir(project_id)
    except Exception as e:
        raise ApiError(404, "project_not_found", f"Project '{project_id}' not found")

    # 1. State & Revisions
    pstate = pipeline_state.load_pipeline_state(pdir)
    resume_plan = pipeline_state.resolve_resume_plan(pdir, aspect)

    # 2. Active Run
    active_run = None
    with _RUN_LOCK:
        run = _ACTIVE_RUNS.get(project_id)
        if run and run.status == "running":
            active_run = run.to_dict()

    recent_runs = list_project_runs(project_id, limit=5)

    # 3. Approval gates (both decided by an LLM review)
    snap = timeline_approval.snapshot(pdir, aspect)
    tl_app_status = {
        "status": snap["status"],
        "fingerprint": snap.get("fingerprint"),
        "approved_at": snap.get("approved_at"),
        "blockers": timeline_approval.gate(pdir, aspect, snap=snap),
        "decision_required": snap["status"] != "approved",
    }

    # Final QC: the Final QC LLM decision about the current candidate
    qc_rep = final_qc._rw_read(pdir, "report", aspect)
    qc_sha = qc_rep.get("candidate", {}).get("sha256") if qc_rep else None
    qc_dec = final_qc.current_review(pdir, aspect, qc_sha) if qc_sha else None
    final_qc_status = {
        "status": (qc_rep.get("status") if qc_rep else "not_started"),
        "candidate_sha256": qc_sha,
        "decision": (qc_dec.get("decision") if qc_dec else None),
        "reviewer": (qc_dec.get("reviewer") if qc_dec else None),
        "decision_required": (not qc_dec or qc_dec.get("decision") not in ("approved", "approved_with_accepted_risks")),
    }

    # 4. Capabilities & Environment Prerequisites
    caps = check_system_capabilities()

    # 5. LLM Usage Telemetry
    try:
        usage = llm_usage.get_usage_summary()
    except Exception:
        usage = None

    # 6. Overall Pipeline Health Determination
    # Explicit health states: healthy, degraded, blocked, running, completed, idle
    if active_run:
        overall_status = "running"
    elif any(s.status == "failed" for s in pstate.stages.values()):
        overall_status = "degraded"
    elif tl_app_status["decision_required"] and pstate.stages.get("timeline", {}).status == "completed":
        overall_status = "blocked"
    elif final_qc_status["decision_required"] and pstate.stages.get("render", {}).status == "completed":
        overall_status = "blocked"
    elif all(s.status == "completed" for s in pstate.stages.values()):
        overall_status = "completed"
    else:
        overall_status = "healthy"

    # Delivery Summary (from Stage 5 verified desktop export)
    sfx = "_9x16" if aspect == "9:16" else ""
    summary_file = pdir / f"delivery_summary{sfx}.json"
    delivery_summary = None
    if summary_file.exists():
        try:
            delivery_summary = json.loads(summary_file.read_text(encoding="utf-8"))
        except Exception:
            delivery_summary = None

    # In-flight active LLM telemetry
    try:
        from SYSTEM.core.llm_gateway import get_active_requests
        active_llm_list = get_active_requests(project_id=project_id)
        active_llm = active_llm_list[0] if active_llm_list else None
    except Exception:
        active_llm = None

    # Derive real progress percent grounded in STAGE_WEIGHTS
    try:
        from SYSTEM.agents.shared.telugu_activity_mapper import STAGE_WEIGHTS
        calc_progress = 0.0
        for sid, (start_pct, end_pct) in STAGE_WEIGHTS.items():
            stage_obj = pstate.stages.get(sid)
            if not stage_obj:
                continue
            if stage_obj.status == "completed":
                calc_progress += (end_pct - start_pct)
            elif stage_obj.status == "running":
                stage_internal_pct = getattr(stage_obj, "percent", None)
                if stage_internal_pct is not None and isinstance(stage_internal_pct, (int, float)):
                    calc_progress += (stage_internal_pct / 100.0) * (end_pct - start_pct)
        # Never report 100% until required pipeline stages and verified delivery summary exist
        final_stage = pstate.stages.get("final")
        if final_stage and final_stage.status == "completed" and delivery_summary is not None:
            calc_progress = 100.0
        else:
            calc_progress = min(98.0, calc_progress)
        real_progress = round(calc_progress, 1)
    except Exception:
        completed_stages = sum(1 for s in pstate.stages.values() if s.status == "completed")
        real_progress = round((completed_stages / len(ACTIVE_STAGES)) * 100.0, 1)

    return {
        "project_id": project_id,
        "aspect": aspect,
        "overall_status": overall_status,
        "progress_percent": real_progress,
        "active_run": active_run,
        "recent_runs": recent_runs,
        "pipeline_state": pstate.to_dict(),
        "resume_plan": {
            "can_resume": resume_plan["can_resume"],
            "earliest_invalid_stage": resume_plan["earliest_invalid_stage"],
            "reusable_count": resume_plan["reusable_count"],
            "invalidated_count": resume_plan["invalidated_count"],
            "invalidation_reason": resume_plan["invalidation_reason"],
        },
        "approval_gates": {
            "timeline_approval": tl_app_status,
            "final_qc": final_qc_status,
        },
        "capabilities": caps,
        "llm_usage": usage,
        "delivery_summary": delivery_summary,
        "active_llm": active_llm,
    }
