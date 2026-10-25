"""Pipeline: one Step registry, one executor.

Every step is declared once (name, requires, outputs, fingerprint, run). The executor is the ONLY place that
checks inputs, decides fresh/stale, writes job.json / log.txt / timings.json / .build_state.json and turns
errors into short messages (tracebacks go to log.txt). cli.py and the future API only call run_chain().

FRESHNESS RULE: a step fingerprint is computed from that step's INPUTS only. Files the step (or a later
step) creates must never be part of its own fingerprint, otherwise it would invalidate itself.
"""
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from SYSTEM.memory import store
from SYSTEM.policies import llm_review

try:
    from backend import config
except ImportError:
    import config

from backend import (
    prerender_checks as pc,
    review,
    scene_segmentation,
    transcript_review,
)
from backend.diagnose import UserProblem, check_disk, explain
from backend.fingerprint import versioned
from backend.transcribe import transcript_inputs

_REMOTION = config.REMOTION_DIR


class StepError(UserProblem):
    """A problem the user can fix; the message says how."""


@dataclass
class Ctx:
    """Per-run options + a progress callback bound to the running step (writes job.json via the executor)."""
    preview: bool = False
    force: bool = False
    progress: Callable[..., None] = lambda percent, eta=None: None


@dataclass(frozen=True)
class Step:
    name: str
    requires: tuple[str, ...]                    # glob patterns relative to the project folder that must exist
    outputs: Callable[[Path], list[Path]]        # files whose existence is part of "fresh"; [] = always run
    fingerprint: Callable[[Path, Ctx], str]      # INPUTS only
    run: Callable[[Path, Ctx], str]              # does the work, returns a short result message
    hint: str = ""                               # how to satisfy `requires`
    tools: tuple[str, ...] = ()                  # executables that must be on PATH


STEPS: dict[str, Step] = {}


def step(name, requires=(), outputs=lambda p: [], fingerprint=None, hint="", tools=()):
    def deco(fn):
        STEPS[name] = Step(name, tuple(requires), outputs, fingerprint, fn, hint, tuple(tools))
        return fn
    return deco


# ---------- hashing (inputs only) ----------
def digest(*parts) -> str:
    """sha1 over files/folders (content + relative names, sorted) and plain values."""
    m = hashlib.sha1()
    for p in parts:
        if isinstance(p, Path):
            base = p if p.is_dir() else p.parent
            files = sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else ([p] if p.exists() else [])
            for f in files:
                m.update(f.relative_to(base).as_posix().encode())
                m.update(f.read_bytes())
        else:
            m.update(str(p).encode())
        m.update(b"|")
    return m.hexdigest()


def _comp(pdir: Path, aspect: str = "16:9") -> Path:
    return pdir / ("composition_9x16.json" if aspect == "9:16" else "composition.json")


def _audio(pdir: Path):
    from backend.render import project_audio
    return project_audio(pdir)


def _referenced_public_files(pdir: Path, aspect: str = "16:9") -> list[Path]:
    comp = json.loads(_comp(pdir, aspect).read_text(encoding="utf-8"))
    pub = _REMOTION / "public"
    return sorted({pub / layer["file"] for sc in comp["scenes"] for layer in sc["layers"] if layer.get("file")})


def render_inputs(pdir: Path, mode: str, aspect: str = "16:9") -> str:
    """composition + the image files it references + the project audio + render mode + Remotion code/config.
    NOT included: the staged audio copy and the output mp4 (both are created by render itself)."""
    root = _REMOTION
    return digest(_comp(pdir, aspect), *_referenced_public_files(pdir, aspect), _audio(pdir) or "no-audio", mode,
                  root / "src", root / "remotion.config.ts", root / "package.json", root / "public" / "geo")


# ---------- bookkeeping (the single owner of job.json / log.txt / timings.json / .build_state.json) ----------
def log(pdir: Path, msg: str) -> None:
    with (pdir / "log.txt").open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def set_job(pdir: Path, name: str, percent: float = 0, error: str | None = None, eta: float | None = None) -> None:
    """The only writer of job.json. Schema: {step, percent, error, eta_s}."""
    (pdir / "job.json").write_text(json.dumps({"step": name, "percent": round(percent, 1), "error": error,
                                                "eta_s": None if eta is None else round(eta)}), encoding="utf-8")


def _read(pdir: Path, fname: str, default):
    f = pdir / fname
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default


def _timings(pdir: Path) -> dict:
    t = _read(pdir, "timings.json", {})
    return t if isinstance(t.get("steps"), dict) else {"steps": {}, "last_build": {}}   # also resets the old flat format


def _write(pdir: Path, fname: str, data) -> None:
    (pdir / fname).write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")


def _record_time(pdir: Path, name: str, seconds: float, status: str) -> None:
    """timings.json: per step {seconds (last real run), status (last outcome), runs, total_seconds, last_run}."""
    t = _timings(pdir)
    s = t["steps"].setdefault(name, {"seconds": 0.0, "status": "", "runs": 0, "total_seconds": 0.0, "last_run": ""})
    if status in ("ran", "failed", "stopped"):
        s["runs"] += 1
        s["total_seconds"] = round(s["total_seconds"] + seconds, 1)
        s["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        if status == "ran":
            s["seconds"] = round(seconds, 1)
    s["status"] = status
    _write(pdir, "timings.json", t)


# ---------- executor ----------
def execute(pdir: Path, name: str, ctx: Ctx) -> dict:
    """Run one registered step (or skip it when fresh). Returns {name, status, seconds, msg}."""
    st = STEPS[name]
    t0 = time.time()
    status, msg = "ran", ""
    try:
        missing_tools = [t for t in st.tools if shutil.which(t) is None]
        if missing_tools:
            raise StepError(f"missing tools on PATH: {', '.join(missing_tools)}")
        missing = [r for r in st.requires if not list(pdir.glob(r))]
        if missing:
            raise StepError(f"missing {', '.join(missing)} - {st.hint}")
        fp = versioned(name, st.fingerprint(pdir, ctx) if st.fingerprint else None)
        outs = st.outputs(pdir)
        known = _read(pdir, ".build_state.json", {}).get("fingerprints", {})
        if outs and fp is not None and all(o.exists() for o in outs) and known.get(name) == fp:
            status, msg = "fresh", "inputs unchanged, output kept"
        else:
            set_job(pdir, name)
            log(pdir, f"START {name}")
            ctx.progress = lambda percent, eta=None, _n=name: set_job(pdir, _n, percent, eta=eta)
            msg = st.run(pdir, ctx)
            after = versioned(name, st.fingerprint(pdir, ctx) if st.fingerprint else None)
            if fp is not None and after != fp:
                log(pdir, f"WARNING {name}: fingerprint changed while running (the step edited its own inputs)")
            state = _read(pdir, ".build_state.json", {"fingerprints": {}})
            state.setdefault("fingerprints", {})[name] = fp
            _write(pdir, ".build_state.json", state)
            set_job(pdir, name, 100)
    except UserProblem as e:      # StepError, or a clear message raised by a lower layer (audio, disk ...)
        status, msg = "stopped", str(e)
        log(pdir, f"STOP {name}: {e}")
        set_job(pdir, name, error=msg)
        if isinstance(e, StepError):
            raise
        raise StepError(msg) from e
    except Exception as e:
        status, msg = "failed", explain(e)
        log(pdir, f"FAIL {name}:\n{traceback.format_exc()}")
        set_job(pdir, name, error=msg)
        raise StepError(f"{name} failed: {msg} (details in {pdir / 'log.txt'}; fix and re-run, finished steps are kept)") from e
    finally:
        secs = time.time() - t0
        _record_time(pdir, name, secs, status)
        line = f"{name:<15} {secs:>7.1f}s  {status}" + (f": {msg}" if msg else "")
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(line.encode(enc, "replace").decode(enc))      # a message with a character the console cannot show (Remotion output) must not replace the real error
    return {"name": name, "status": status, "seconds": round(secs, 1), "msg": msg}


def run_analysis(pdir: Path, ctx: Ctx | None = None) -> list[dict]:
    """The Audio Analyzer: the steps of the "transcribe" chain (speech-to-text, the LLM check and correction of the transcript, the cuts). Whisper runs only for a project that has no
    transcript.json; a step whose inputs did not change is skipped by the executor, so a finished analysis costs nothing. The one implementation: the orchestrator and the LLM verification
    button of the Scene Segmentation page both call it."""
    ctx = ctx or Ctx()
    results = [execute(pdir, n, ctx) for n in CHAINS["transcribe"] if n != "transcribe" or not (pdir / "transcript.json").exists()]
    llm_review.run_stage_llm_review(pdir, "analyzer")      # the LLM approval of the final transcript: asked only when it is missing or its inputs changed (a cached answer costs nothing)
    return results


def run_chain(pdir: Path, names, label: str, ctx: Ctx | None = None) -> list[dict]:
    """Run steps in order; stop at the first error (earlier outputs stay). Records last_build in timings.json."""
    ctx = ctx or Ctx()
    started, t0, results = time.strftime("%Y-%m-%dT%H:%M:%S"), time.time(), []
    try:
        for n in names:
            results.append(execute(pdir, n, ctx))
    finally:
        t = _timings(pdir)
        t["last_build"] = {"label": label, "started": started, "total_seconds": round(time.time() - t0, 1),
                           "steps": {r["name"]: {"seconds": r["seconds"], "status": r["status"]} for r in results}}
        _write(pdir, "timings.json", t)
    return results


CHAINS = {
    "transcribe": ("transcribe", "refine", "cuts"),
    "segment": ("segment",),                # Scene Segmentation: its own stage, started by the user
    "plan-input": ("plan-input",),
    "prompts": ("prompts",),
    # the composition is built straight from the scene plan (Motion-Only: no picture layers)
    "build": ("motion-plan", "motion-build", "render-final"),
    "build-preview": ("motion-plan", "motion-build", "render-preview"),
    "build-9x16": ("motion-plan-9x16", "motion-build-9x16", "render-final-9x16"),
    "build-preview-9x16": ("motion-plan-9x16", "motion-build-9x16", "render-preview-9x16"),
    # the timeline: the motion branch, the pre-render check, then Stage 11 (extended below: the LLM approval and the render follow)
    "timeline": ("motion-plan", "motion-build", "motion-validate", "timeline-build"),
    "timeline-9x16": ("motion-plan-9x16", "motion-build-9x16", "motion-validate-9x16", "timeline-build-9x16"),
}
# the right-hand branch of the Pipeline page (Motion Planning -> Motion Animation) on its own
CHAINS["motion"] = ("motion-plan", "motion-build")
CHAINS["motion-9x16"] = ("motion-plan-9x16", "motion-build-9x16")
# Motion Planning on its own (its own page): the selector's plan and the checked plan, no Motion Generation
CHAINS["motion-plan"] = ("motion-plan",)
CHAINS["motion-plan-9x16"] = ("motion-plan-9x16",)
# Motion Generation on its own (its own page): the composition built from the checked plan and checked again, no Motion Planning
CHAINS["motion-gen"] = ("motion-build",)
CHAINS["motion-gen-9x16"] = ("motion-build-9x16",)
# Stage 10 on its own (its own page): validate the motion output, read-only; the preview (stills) is a separate explicit action that validates again afterwards
CHAINS["motion-validation"] = ("motion-validation",)
CHAINS["motion-validation-9x16"] = ("motion-validation-9x16",)
CHAINS["motion-validation-preview"] = ("motion-validation-preview", "motion-validation")
CHAINS["motion-validation-preview-9x16"] = ("motion-validation-preview-9x16", "motion-validation-9x16")
# Stage 14 on its own (its own page): it judges the verified rendered video and never renders
CHAINS["final-qc"] = ("final-qc",)
CHAINS["final-qc-9x16"] = ("final-qc-9x16",)


def chain_for(pdir: Path, label: str) -> tuple:
    """The step names of a chain. Every entry point that starts a build, a timeline or a render goes through here."""
    return CHAINS[label]


# ---------- steps ----------
@step("transcribe", requires=("audio.*",), hint="run: python -m backend.cli new <id> --audio <file>", tools=("ffmpeg", "ffprobe"),
      outputs=lambda p: [p / "transcript.json"],
      fingerprint=lambda p, c: digest(_audio(p), config.WHISPER_MODEL, config.WHISPER_VERSION))
def _transcribe(pdir, ctx):
    from backend.transcribe import transcribe
    check_disk(pdir, config.MIN_FREE_GB_WORK, "transcription")
    t = transcribe(pdir, progress=ctx.progress)
    return f"{len(t.segments)} segments, {sum(len(s.words) for s in t.segments)} words"


@step("refine", requires=("transcript.json",), hint="run: python -m backend.cli transcribe <id>",
      outputs=lambda p: [p / "transcript_review.json"] + ([p / "transcript_review.incomplete"] if transcript_review.alignment_pending(transcript_review.last_review(p)) else []),
      fingerprint=lambda p, c: digest(p / "transcript.json", p / "vocabulary.txt", _audio(p), config.WHISPER_MODEL, transcript_review.VERSION, transcript_review.LOW_P, os.environ.get("PROMPTGEN_MODEL", "")))
def _refine(pdir, ctx):
    """Audio Analyzer stages 6-9: technical vocabulary, uncertain words, the Claude check of every word (validated), the final corrected transcript. The raw transcript.json is never edited."""
    r = transcript_review.refine(pdir, progress=ctx.progress)
    n = sum(c["status"] == "applied" for c in r["corrections"])
    if r["llm"]["status"] in ("unavailable", "failed") and not r["corrected_file"]:
        # the final transcript is the LLM-verified one: without it the analysis is not finished (finished steps are kept, running again retries only this one)
        raise StepError(f"The LLM check of the transcript could not run ({r['llm']['error'] or r['llm']['status']}). The final JSON is saved only after the LLM check: sign in to the Claude CLI and run the Audio Analyzer again.")
    return f"{len(r['confidence']['flagged'])} uncertain words, {n} corrected, Claude: {r['llm']['status']}"


@step("cuts", requires=("transcript.json", "audio.*"), hint="run: python -m backend.cli transcribe <id>", tools=("ffmpeg",),
      outputs=lambda p: [p / "cuts.json", p / "audio_analysis.json"],
      fingerprint=lambda p, c: digest(*transcript_inputs(p), p / "transcript_review.json", _audio(p), config.SILENCE_MIN, config.SILENCE_DB))
def _cuts(pdir, ctx):
    from backend.audio_analysis import write as write_analysis
    from backend.cuts import make_cuts
    cuts = make_cuts(pdir)
    (pdir / "cuts.json").write_text(json.dumps({"cuts": cuts}, indent=1), encoding="utf-8")
    a = write_analysis(pdir, progress=ctx.progress)       # audio_analysis.json: the measured facts, the 14 stages and the validation of the analysis
    llm_review.run_stage_llm_review(pdir, "audio")
    llm_review.run_stage_llm_review(pdir, "analyzer")
    return f"{len(cuts)} cuts, analysis {a['validation']['status']}"


@step("segment", requires=("transcript.json",), hint="the final analysis JSON (transcript.json) is not in the project",
      outputs=lambda p: [p / "scene_segmentation.json"],
      fingerprint=lambda p, c: digest(*transcript_inputs(p), p / "audio_analysis.json", scene_segmentation.VERSION, scene_segmentation.TIMING_RULES, scene_segmentation.PAUSE_MIN, scene_segmentation.PAUSE_SCENE, scene_segmentation.SOFT_MIN,
                                      scene_segmentation.SOFT_MAX, scene_segmentation.LONG_UNIT, scene_segmentation.MIN_SPLIT, scene_segmentation.PAUSE_CLAUSE, os.environ.get("PROMPTGEN_MODEL", "")))
def _segment(pdir, ctx):
    """Scene Segmentation: which narration belongs together in one scene (runs only when the user starts it)."""
    r = scene_segmentation.run(pdir, progress=ctx.progress)
    llm_review.run_stage_llm_review(pdir, "segmentation")
    t = r["timings_seconds"]
    claude = round(sum(c.get("claude_s", 0) for c in r["llm"]["calls"]), 1)
    return f"{len(r['scenes'])} scenes, {r['segmentation_method']}, {r['validation']['status']} in {t['total']} s (Claude {claude} s, {r['llm']['attempts']} attempt(s), {r['llm']['status']})"


@step("plan-input", requires=("transcript.json", "cuts.json"), hint="run: python -m backend.cli transcribe <id>",
      outputs=lambda p: [p / "plan_input.txt"],
      fingerprint=lambda p, c: digest(*transcript_inputs(p), p / "cuts.json", p / "translation.json", p / "scene_segmentation.json"))
def _plan_input(pdir, ctx):
    from backend.plan_input import build
    from backend.translate_io import merge, prepare
    prepare(pdir)
    if not (pdir / "translation.json").exists():
        raise StepError(f"translate_input.txt is ready - now run /plan {pdir.name} in Claude Code (it writes translation.json and the plan)")
    merge(pdir)
    (pdir / "plan_input.txt").write_text(build(pdir), encoding="utf-8")
    return "plan_input.txt ready"


@step("prompts", requires=("scene_plan.json", "prompts_map.json"), hint="run /plan <id> in Claude Code first",
      outputs=lambda p: [p / "prompts.txt"], fingerprint=lambda p, c: digest(p / "scene_plan.json", p / "prompts_map.json"))
def _prompts(pdir, ctx):
    review.reapply_edits(pdir)
    return "prompts.txt generation is deprecated in Motion-Only mode"


def _prerender(pdir: Path, aspect: str) -> str:
    """Pre-render validation (prerender_checks.py): errors stop the render with a plain message; warnings are only counted here and kept
    in prerender_report*.json for the user to review. A bug in the check itself must never be the reason a video is not made."""
    try:
        rep = pc.check(pdir, aspect)
        pc.write_report(pdir, rep)
    except Exception as e:
        log(pdir, f"pre-render check skipped: {e}")
        if config.improve("validation"):      # improvement P6: the skipped check must not look like an all-clear
            from backend.quality import record_failure
            record_failure(pdir, aspect, e)
        return ""
    if rep.blocking:
        raise StepError(pc.blocking_message(rep))
    n = rep.summary()[pc.WARNING]
    return f"{n} warnings to review in {pc.report_path(pdir, aspect).name}" if n else ""


def _approval_still_holds(pdir: Path, aspect: str, preview: bool) -> None:
    """Stage 12 gate inside the final render job (Motion-Only projects): a missing, stale, rejected or unverifiable approval stops the job. A preview render needs no approval. The route's check is not the only one."""
    if preview:
        return
    from backend import timeline_approval
    if (why := timeline_approval.gate(pdir, aspect, in_render_job=True)):
        raise StepError("the final render needs the current timeline to be approved: " + "; ".join(why[:3]))


def _render_step(name: str, preview: bool, aspect: str = "16:9") -> None:
    from backend.render import output_path, render_flags
    sfx = "_9x16" if aspect == "9:16" else ""

    # the render flags are part of the inputs: changing the command (e.g. preview scale) must invalidate old output
    @step(name, requires=(f"composition{sfx}.json", "audio.*"), hint="run /plan <id> first, then build", tools=("node", "npx"),
          outputs=lambda p: [output_path(p, preview, aspect)],
          fingerprint=lambda p, c: render_inputs(p, ("preview " if preview else "final ") + " ".join(render_flags(preview)), aspect))
    def _render(pdir, ctx):
        from backend.render import SLOW_X_VIDEO, render
        _approval_still_holds(pdir, aspect, preview)                    # the worker checks the approval itself, at the start and again right before it uses the composition
        check_note = _prerender(pdir, aspect)
        _approval_still_holds(pdir, aspect, preview)
        from backend import timeline_approval
        if not preview:                                                 # Stage 13 (backend/render_video.py): a temporary output, verified, published atomically, reported
            from backend import render_video, final_qc
            try:
                rep = render_video.run(pdir, aspect, ctx.progress)
                llm_review.run_stage_llm_review(pdir, "render", aspect, force=True)

                # Automatically proceed to Final QC: the checks, then the decision about the file by the Final QC LLM review (no person). Delivery is a separate step.
                qc_note = ""
                try:
                    qc_rep = final_qc.run(pdir, aspect, progress=ctx.progress)
                    st = final_qc.llm_decide(pdir, aspect)
                    qc_note = f"; Final QC {st['status'].replace('_', ' ')} ({qc_rep['summary']['checks_passed']} checks passed), decided by the Final QC LLM review"
                except Exception as eqc:
                    log(pdir, f"Auto Final QC note: {eqc}")
            except render_video.RenderError as e:
                raise StepError(str(e)) from e
            o = rep["output"]
            return f"{o['artifact_ref']} rendered, verified and published ({o['size_bytes']} bytes, {rep['expected']['frames']} frames at {rep['expected']['fps']} fps, sha256 {o['sha256'][:12]}){qc_note}" + (f"; {check_note}" if check_note else "")
        out = render(pdir, preview, ctx.progress, **({"aspect": aspect} if aspect != "16:9" else {}))   # 16:9 keeps the original call
        if not preview:
            llm_review.run_stage_llm_review(pdir, "render", aspect)
        prof = _read(pdir, f"render_profile{sfx}.json", {})
        if not prof:
            return str(out) + (f"; {check_note}" if check_note else "")
        note = f"{prof['x_video_length']}x video length" + (f", heavy scenes {prof['heavy']}" if prof["heavy"] else "")
        if prof["x_video_length"] and prof["x_video_length"] > SLOW_X_VIDEO:
            log(pdir, f"WARNING render took {note}; docs/m9.md asks to tell the user above {SLOW_X_VIDEO:g}x")
            note += f" - slower than {SLOW_X_VIDEO:g}x"
        return f"{out} ({note})" + (f"; {check_note}" if check_note else "")


def _validate_step(name: str, aspect: str) -> None:
    sfx = "_9x16" if aspect == "9:16" else ""

    # no outputs: it always runs (about a second), so the report is never older than the files it describes (review.timeline_state compares times)
    @step(name, requires=(f"composition{sfx}.json",), hint="run the build first")
    def _validate(pdir, ctx):
        """The last stage of the timeline: the pre-render check on the composition. Errors stop here (the timeline is not verified); warnings stay reviewable.
        Motion & Timeline Validation must have cleared the motion output first: read now, so a result made before an input changed never lets this through."""
        from backend import motion_validation
        if (why := motion_validation.blockers(pdir, aspect, validate_if_needed=True)):
            raise StepError("; ".join(why))
        rep = pc.check(pdir, aspect)
        pc.write_report(pdir, rep)
        if rep.blocking:
            raise StepError(pc.blocking_message(rep))
        s = rep.summary()
        return f"timeline verified: {s[pc.WARNING]} warnings to review in {pc.report_path(pdir, aspect).name}"


_src_memo: dict = {}


def _remotion_src_digest() -> str:
    """Digest of the renderer's source (what the motion steps depend on). The view asks for freshness every few seconds, so the content hash is only recomputed when a
    file's size or modification time changed. Generated scene modules under VIDEO_ENGINE/remotion/src/generated are excluded because they are stage outputs."""
    files = tuple(f for f in sorted((_REMOTION / "src").rglob("*")) if f.is_file() and "generated" not in f.parts)
    stamp = hash(tuple((str(f), f.stat().st_mtime_ns, f.stat().st_size) for f in files))
    if _src_memo.get("stamp") != stamp:
        m = hashlib.sha1()
        for f in files:
            m.update(f.relative_to(_REMOTION / "src").as_posix().encode())
            m.update(f.read_bytes())
            m.update(b"|")
        _src_memo.update(stamp=stamp, digest=m.hexdigest())
    return _src_memo["digest"]


def _motion_flags(pdir: Path, aspect: str, plan_only: bool = False) -> str:
    """The motion library is always on in these steps; the picture layers are not built at all (Motion-Only)."""
    from backend import visual_planning
    vp = (pdir / "visual_planning.json").exists() and visual_planning.blockers(pdir) is None        # a current Visual Plan: its text and motion hints decide the scene's text and graphics
    from SYSTEM.memory import store
    no_images_flag = "" if store.uses_images(pdir) else " --no-images"
    return " --motion" + no_images_flag + (" --plan-only" if plan_only else "") + (" --aspect 9:16" if aspect == "9:16" else "") + (" --visual-plan" if vp else "") + (" --fixes" if (pdir / "motion_fixes.json").exists() else "")


def _run_build_script(pdir: Path, aspect: str, plan_only: bool) -> None:
    import os
    import subprocess
    r = subprocess.run(f'npx tsx scripts/build_composition.ts "{pdir.resolve()}"' + _motion_flags(pdir, aspect, plan_only), cwd=_REMOTION, shell=True, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env={**os.environ, "A2V_MOTION": "1"})
    if r.returncode:
        raise RuntimeError("build_composition failed: " + (r.stderr or r.stdout)[-400:])


def _motion_inputs(pdir: Path, aspect: str) -> list:
    return [pdir / "scene_plan.json", pdir / "visual_planning.json", pdir / "motion_fixes.json", *transcript_inputs(pdir), _audio(pdir) or "no-audio", _remotion_src_digest(),
            _REMOTION / "scripts" / "build_composition.ts", aspect, ("with-pictures" if __import__("SYSTEM.memory.store", fromlist=["uses_images"]).uses_images(pdir) else "motion-only"), config.MOTION_SPEED or "",
            *([f"style-kit:{config.STYLE_KIT}"] if config.STYLE_KIT not in ("", "0") else []),      # only when on: a project without a kit keeps its fingerprint
            Path(__file__).with_name("motion_planning.py"), Path(__file__).with_name("motion_scenes.py")]


def _generation_inputs() -> list:
    """What Motion Generation is made of besides the plan: the modules that check it and the renderer's validator."""
    stages = Path(__file__).resolve().parent.parent / "stages"
    return [stages / n for n in ("motion_generation.py", "motion_gen_rules.py", "motion_gen_report.py", "motion_animation.py")] + [_REMOTION / "scripts" / "motion_validate.ts"]


def _planned(plan: dict) -> list:
    return [(s["id"], [x["preset"] for x in s["texts"]], [g["preset"] for g in s["graphics"]]) for s in plan["scenes"]]


def _built(comp: dict) -> list:
    return [(s["id"], [l["preset"] for l in s["layers"] if l["type"] == "motion_text"],
             [i["preset"] for l in s["layers"] if l["type"] == "motion_scene" for i in l.get("items", [])]) for s in comp["scenes"]]


def _motion_steps(aspect: str) -> None:
    sfx = "_9x16" if aspect == "9:16" else ""
    tag = "-9x16" if aspect == "9:16" else ""

    @step(f"motion-plan{tag}", requires=("scene_plan.json",), hint="run /plan <id> first (the scene plan is the input of Motion Planning)", tools=("node", "npx"),
          outputs=lambda p: [p / f"motion_plan{sfx}.json", p / f"motion_planning{sfx}.json"], fingerprint=lambda p, c: digest(*_motion_inputs(p, aspect)))
    def _plan(pdir, ctx):
        """Motion Planning: timing, text animations, fallbacks, and motion intent."""
        from backend import motion_planning, visual_planning
        if (why := visual_planning.blockers(pdir)):                           # never plan the motion of a Visual Plan that is out of date or invalid
            raise StepError(f"Motion Planning waits for Visual Planning: {why}. Run Visual Planning again")
        ctx.progress(5)
        _run_build_script(pdir, aspect, plan_only=True)
        f = pdir / f"motion_plan{sfx}.json"
        plan = json.loads(f.read_text(encoding="utf-8"))
        hand = visual_planning.handoff(pdir)                                  # the Visual Plan this motion plan was made for: same scene ids, same intervals, the elements and the motion hints
        if hand["scenes"] and (bad := visual_planning.link_errors(plan["scenes"], hand)):
            raise StepError("the motion plan and the Visual Plan are not the same scenes: " + "; ".join(bad[:3]))
        plan["visual_plan"] = hand
        f.write_text(json.dumps(plan, indent=1), encoding="utf-8")
        try:
            checked = motion_planning.build(pdir, aspect, progress=ctx.progress)
        except motion_planning.MotionError as e:
            raise StepError(str(e)) from e
        motion_planning.save(pdir, aspect, checked)
        llm_review.run_stage_llm_review(pdir, "motion_plan", aspect)
        if (errs := checked["validation"]["errors"]):                         # an invalid plan never reaches Motion Generation
            raise StepError(f"the motion plan has {len(errs)} error(s): " + "; ".join(errs[:3]))
        v = checked["validation"]
        return (f"{len(plan['scenes'])} scenes planned ({plan['mode']}, pace x{plan['speed']}) from the Visual Plan ({hand['source']}); "
                f"{v['checks']['passed']} of {v['checks']['total']} checks passed, {len(v['warnings'])} warning(s)")

    @step(f"motion-build{tag}", requires=(f"motion_plan{sfx}.json", "scene_plan.json"), hint="run Motion Planning first", tools=("node", "npx"),
          outputs=lambda p: [p / f"composition{sfx}.json", p / f"motion_generation{sfx}.json", p / f"motion_animation{sfx}.json"],
          fingerprint=lambda p, c: digest(*_motion_inputs(p, aspect), p / f"motion_plan{sfx}.json", p / f"motion_planning{sfx}.json", *_generation_inputs()))
    def _build(pdir, ctx):
        """Motion Animation: generates executable scene-specific React/TSX animation code."""
        from backend import motion_animation, motion_gen_report, motion_planning
        ctx.progress(5)
        if (why := motion_planning.blockers(pdir, aspect)):                     # the checked plan is the gate: out of date, or with blocking errors, nothing is built from it
            raise StepError(why)

        # Generate scene-specific React/TSX code
        ctx.progress(15)
        manifest = motion_animation.generate_custom_motion_code(pdir, aspect)
        ctx.progress(60)
        comp_path = pdir / f"composition{sfx}.json"
        comp = json.loads(comp_path.read_text(encoding="utf-8"))
        audio = _audio(pdir)
        if audio is not None:
            comp["meta"]["audio"] = audio.name
            comp_path.write_text(json.dumps(comp, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        try:
            rep, comp = motion_gen_report.build(pdir, aspect, comp, {"identical": True, "note": "custom React/TSX generated code compiled"}, progress=ctx.progress)
        except motion_gen_report.GenerationError as e:
            raise StepError(str(e)) from e
        rep = motion_gen_report.finish(pdir, aspect, rep, comp)
        ctx.progress(100)
        return f"{len(manifest['scenes'])} scenes generated in Custom Code Mode (executable TSX compiled at 30 fps)"


_motion_steps("16:9")
_motion_steps("9:16")
_validate_step("motion-validate", "16:9")
_validate_step("motion-validate-9x16", "9:16")


def _validation_steps(aspect: str) -> None:
    """Stage 10, Motion & Timeline Validation (backend/motion_validation.py): read-only, it writes only its own report. It always runs (a stage whose inputs did not change keeps its result inside
    the report, see the cache there); a blocked or stale verdict is a result, not a failed job. The preview is its own explicit step: low-resolution stills, never a render of the video."""
    sfx = "-9x16" if aspect == "9:16" else ""

    @step(f"motion-validation{sfx}", hint="run Motion Planning and Motion Generation first")
    def _validation(pdir, ctx):
        from backend import motion_validation
        rep = motion_validation.run(pdir, aspect, progress=ctx.progress, force=ctx.force)
        llm_review.run_stage_llm_review(pdir, "motion_validation", aspect)
        s = rep["summary"]
        ctx.progress(100)
        return f"{rep['readiness']}: {s['blockers']} blocker(s), {s['errors']} error(s), {s['warnings']} warning(s), {s['checks_passed']} of {s['checks_total']} checks passed, {rep['cache']['stages_reused']} stage(s) reused"

    @step(f"motion-validation-preview{sfx}", hint="run Motion Generation first")
    def _preview(pdir, ctx):
        from backend import motion_validation_preview
        man = motion_validation_preview.generate(pdir, aspect, progress=ctx.progress)
        bad = sum(1 for x in man["samples"] if not x["decode_ok"] or x["blank"])
        return f"{len(man['samples'])} stills at {man['scale']:g} scale, {bad} undecodable or blank (not a render, not reviewed by a person)"


_validation_steps("16:9")
_validation_steps("9:16")


def _timeline_build_steps(aspect: str) -> None:
    """Stage 11, Timeline Build (backend/timeline_build.py): builds timeline.json and its report from the current composition and validates the built object. A blocked build is a failed step (the last good
    timeline is kept); nothing is approved and nothing is rendered."""
    sfx = "_9x16" if aspect == "9:16" else ""
    from backend import timeline_build as tb
    nm = tb.names(aspect)

    @step(f"timeline-build{'-9x16' if aspect == '9:16' else ''}", requires=(f"composition{sfx}.json",), hint="build the composition first (Motion Generation)",
          outputs=lambda p: [p / nm["timeline"], p / nm["report"]], fingerprint=lambda p, c: tb.fingerprint(p, aspect))
    def _timeline_build(pdir, ctx):
        try:
            rep = tb.run(pdir, aspect, progress=ctx.progress)
        except tb.BuildError as e:
            raise StepError(str(e)) from e
        if rep["status"] not in tb.OK:
            first = next((f for f in rep["findings"] if f["severity"] in tb.BLOCKING), None)
            raise StepError(f"Timeline Build is {rep['status']}: {rep['summary']['blockers']} blocker(s), {rep['summary']['errors']} error(s)" + (f" - {first['message']}" if first else "") + " (the last good timeline is kept)")
        llm_review.run_stage_llm_review(pdir, "timeline", aspect)
        c = rep["counts"]
        return f"{'reused: ' if rep.get('reused') else ''}{rep['status'].replace('_', ' ')}: {c['scenes']} scenes, {c['items']} items, {c['layers']} layers, {c['duration_frames']} frames at {c['fps']} fps, {rep['checks']['passed']} of {rep['checks']['total']} checks passed, {rep['checks']['warnings']} warning(s)"


_timeline_build_steps("16:9")
_timeline_build_steps("9:16")


def _timeline_approve_steps(aspect: str) -> None:
    """Stage 12, Timeline Approval: decided by the LLM approval review (timeline_approval.auto_approve), no person. A rejected or unverifiable version fails the step with the exact
    cause; nothing is approved and the render that follows in the chain never starts."""
    tag = "-9x16" if aspect == "9:16" else ""

    @step(f"timeline-approve{tag}", hint="build the timeline first (Timeline Build)")
    def _approve(pdir, ctx):
        from backend import timeline_approval as ta
        try:
            st = ta.auto_approve(pdir, aspect, in_job=True)
        except ta.ApprovalError as e:
            raise StepError(f"Timeline Approval (LLM) did not approve: {e}" + (f" - {'; '.join(e.blockers[:4])}" if e.blockers else "")) from e
        return f"approved by the LLM review: version {(st.get('fingerprint') or '')[:12]}"


_timeline_approve_steps("16:9")
_timeline_approve_steps("9:16")
# Timeline Build -> Timeline Approval (LLM) -> Render Video, without a human pause (the render step re-checks the approval itself)
for _sfx in ("", "-9x16"):
    _auto = (f"timeline-build{_sfx}", f"timeline-approve{_sfx}", f"render-final{_sfx}")
    CHAINS[f"timeline-build{_sfx}"] = (f"motion-validate{_sfx}",) + _auto      # Stage 11 on its own (its own page): the pre-render check of the composition, then the timeline artifact
    CHAINS[f"timeline{_sfx}"] = CHAINS[f"timeline{_sfx}"] + _auto[1:]


def _final_qc_steps(aspect: str) -> None:
    """Stage 14, Final QC (backend/final_qc.py): reads the verified rendered video and writes its own report; it never renders and never edits the video. It always runs (the media evidence is cached inside the report by the
    candidate's hash); a failed or blocked verdict is a result of the job, but a stopped step says why."""
    @step(f"final-qc{'-9x16' if aspect == '9:16' else ''}", hint="render the approved timeline first (Render Video)")
    def _final_qc(pdir, ctx):
        from backend import final_qc
        try:
            rep = final_qc.run(pdir, aspect, progress=ctx.progress)
        except final_qc.QcError as e:
            raise StepError(str(e)) from e
        # The decision about the file is the Final QC LLM review's (no person); nothing is delivered here: delivery is a separate step.
        try:
            st = final_qc.llm_decide(pdir, aspect)
        except final_qc.QcError as e:
            raise StepError(str(e)) from e
        s = rep["summary"]
        ctx.progress(100)
        return f"{st['status'].replace('_', ' ')}: {s['blocking_findings']} blocking, {s['warnings']} warning(s), {s['checks_passed']} of {s['checks_total']} checks passed; candidate {rep['candidate']['sha256'] and rep['candidate']['sha256'][:12]}; decided by the Final QC LLM review"


_final_qc_steps("16:9")
_final_qc_steps("9:16")


def is_fresh(pdir: Path, name: str) -> bool:
    """Would execute() skip this step right now (inputs unchanged and its output still there)? Same rule as the executor; used by the pipeline view and the gates."""
    st = STEPS[name]
    try:
        if [r for r in st.requires if not list(pdir.glob(r))]:
            return False
        fp = versioned(name, st.fingerprint(pdir, Ctx()) if st.fingerprint else None)
        outs = st.outputs(pdir)
        return bool(outs and fp is not None and all(o.exists() for o in outs) and _read(pdir, ".build_state.json", {}).get("fingerprints", {}).get(name) == fp)
    except Exception:
        return False


def record_fresh(pdir: Path, name: str) -> None:
    """Record the current input fingerprint of a step whose outputs were just rebuilt outside execute() (an orchestrator agent), so is_fresh() and the pipeline view agree."""
    st = STEPS[name]
    fp = versioned(name, st.fingerprint(pdir, Ctx()) if st.fingerprint else None)
    if fp is None:
        return
    state = _read(pdir, ".build_state.json", {"fingerprints": {}})
    state.setdefault("fingerprints", {})[name] = fp
    _write(pdir, ".build_state.json", state)


_render_step("render-preview", True)
_render_step("render-final", False)
_render_step("render-preview-9x16", True, "9:16")
_render_step("render-final-9x16", False, "9:16")


# ---------- non-step commands ----------
def new_project(pid: str, audio: Path) -> Path:
    if not audio.exists():
        raise StepError(f"audio file not found: {audio}")
    pdir = config.PROJECTS_DIR / pid
    pdir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(audio, pdir / f"audio{audio.suffix.lower()}")
    llm_review.run_stage_llm_review(pdir, "audio")
    return pdir


def status(pdir: Path) -> str:
    out = [f"project: {pdir.name}"]
    for f in ("audio.*", "transcript.json", "cuts.json", "transcript_en.json", "scene_plan.json", "prompts_map.json",
              "composition.json", "out_preview.mp4", "out.mp4"):
        out.append(f"  {'ok ' if list(pdir.glob(f)) else '-- '}{f}")
    if (pdir / "job.json").exists():
        out.append("job: " + (pdir / "job.json").read_text(encoding="utf-8"))
    prof = _read(pdir, "render_profile.json", None)
    if prof:
        out.append(f"last render: {prof['mode']} {prof['seconds']}s = {prof['x_video_length']}x video length; heavy scenes: {prof['heavy'] or 'none'}")
    t = _read(pdir, "timings.json", None)
    if t:
        lb = t.get("last_build", {})
        out.append(f"last build: {lb.get('label')} total={lb.get('total_seconds')}s " +
                   " ".join(f"{k}={v['seconds']}s({v['status']})" for k, v in lb.get("steps", {}).items()))
    return "\n".join(out)
