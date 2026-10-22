"""Writes image prompts from the approved analysis with the user's own Claude CLI (`claude -p`, already signed in on this machine; no API key,
no new provider). Started by the analysis approval (all prompts that are not yet written for this analysis) or by "Regenerate This Prompt" (one prompt).
The CLI runs with no tools, no project settings and no memory, in a temp folder, so it only turns the scene context into text.
Progress and failures are kept in review.json ("generation"); a retry writes only what is still missing. Prompts the user edited or approved are never
replaced by the all-prompts run, and a text the user changes while a new one is being written is kept."""
import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from . import review
from .review import ReviewError

TIMEOUT = 180
SYSTEM = (
    "You write ONE text-to-image prompt for a documentary video scene. Output only the prompt: English, one paragraph, no quotes, no labels, no markdown. "
    "One clear subject, setting, light, camera angle, mood. No text, numbers, logos, watermarks or real people's names inside the image. "
    "Do not add a style suffix or an aspect ratio (the app appends them). Icon or object prompts: a flat, simple subject."
)
_running: dict[str, threading.Thread] = {}     # project folder -> the thread that runs its generation job (prompts, planning, Visual Planning)
_guard = threading.RLock()                 # re-entrant: start() holds it while _record() may write a final state


class GenError(RuntimeError):
    """The CLI is missing, not signed in, timed out or returned nothing usable."""


def run_claude(user: str, system: str = SYSTEM, timeout: int = TIMEOUT) -> str:
    from . import llm_client, llm_gateway
    try:
        gw_req = llm_gateway.LlmGatewayRequest(
            project_id="shared",
            stage_id="planning",
            agent_id="visual_planning",
            purpose="generation",
            model_profile="default",
            system_prompt=system,
            user_prompt=user,
            timeout=timeout,
        )
        gw_resp = llm_gateway.get_gateway().execute(gw_req)
        if gw_resp.raw_output:
            return gw_resp.raw_output
        return llm_client.generate_text(user, system=system, timeout=timeout)
    except Exception:
        try:
            return llm_client.generate_text(user, system=system, timeout=timeout)
        except Exception as e:
            raise GenError(str(e)) from e


def _text(raw: str) -> str:
    paras = [p for p in raw.strip().split("\n\n") if p.strip()]
    t = " ".join((paras[0] if paras else "").split()).strip("`\"' ")
    if t.lower().startswith("prompt:"):
        t = t[7:].strip()
    return t


def _ask(ctx: dict, must_differ: bool) -> str:
    p, sc = ctx["prompt"], ctx["scene"]
    info = {"role": p["role"], "ratio": p["ratio"], "scene_meaning": sc.get("meaning"), "concept": sc.get("concept"), "mood": sc.get("mood"),
            "narration_en": sc.get("narration_en"), "keywords": [k["text"] for k in sc.get("keywords", [])],
            "other_prompts_of_this_scene": [q["text"] for q in ctx["same_scene_prompts"]], "current_text": p["text"]}
    return (json.dumps(info, ensure_ascii=False, indent=1) + "\n\nWrite the prompt for this slot."
            + (" It must clearly differ from current_text." if must_differ else " current_text is a draft; improve it, keep its subject if it fits."))


def _record(pdir: Path, **kw) -> None:
    """Writes the generation record. A final state (done / failed) written by the job's own thread also releases the job in the same lock, so a Retry
    pressed right after a failure starts a new run instead of being handed the old record as if the job still ran."""
    final = kw.get("state") in ("done", "failed")
    with _guard if final else contextlib.nullcontext():
        with review.LOCK:
            st = review.state_of(pdir)
            st.setdefault("generation", {}).update(kw)
            review._save(pdir / "review.json", st)
        if final:
            _release(pdir)


def _release(pdir: Path) -> None:
    """Frees the job of this project, but only for the thread that runs it: a finished worker can never free the job a Retry started after it."""
    with _guard:
        if _running.get(str(pdir)) is threading.current_thread():
            del _running[str(pdir)]


def launch(pdir: Path, target, *args) -> None:
    """Starts the generation job's thread and makes it the job's owner. Call with _guard held, after recording state="running"."""
    def run():
        try:
            target(pdir, *args)
        finally:
            _release(pdir)                                              # never leaves the job claimed (an unexpected error, a final state not written)
    t = threading.Thread(target=run, daemon=True)
    _running[str(pdir)] = t
    t.start()


def state(pdir: Path) -> dict:
    g = dict(review.state_of(pdir).get("generation") or {})
    if g.get("state") == "running" and str(pdir) not in _running:      # the app was restarted while it ran
        g.update(state="failed", error="interrupted (the app was restarted): press Retry", current=None)
    return {"state": "idle", "kind": None, "n": None, "total": 0, "done": 0, "current": None, "failed": [], "skipped": [], "error": None,
            "started": None, "finished": None, **g}


def _targets(pdir: Path, fp: str) -> list[int]:
    st, raw = review.state_of(pdir), review._prompts_raw(pdir)
    out = []
    for p in raw["prompts"]:
        ps = st["prompts"].get(p["slot"], {})
        if ps.get("generated_for") == fp or ps.get("edited_text") or ps.get("approved_hash") == review.h(p["text"]):
            continue
        out.append(p["n"])
    return sorted(out)


def _work(pdir: Path, ns: list[int], fp: str, single: bool) -> None:
    done, failed, skipped = 0, [], []
    try:
        for n in ns:
            _record(pdir, current=n, done=done)
            try:
                ctx = review.scene_context(pdir, n)
                text = _text(run_claude(_ask(ctx, must_differ=single)))
                review.set_generated(pdir, n, text, expect=ctx["prompt"]["text"], fp=fp, keep_approved=not single)
                done += 1
            except ReviewError as e:
                if "was changed" in str(e) or "was approved" in str(e):       # the user got there first: their version stays
                    skipped.append(n)
                else:
                    failed.append({"n": n, "error": str(e)})
            except GenError as e:                                           # the CLI itself failed: stop; a retry continues with what is missing
                failed.append({"n": n, "error": str(e)})
                break
        _record(pdir, state="failed" if failed else "done", done=done, failed=failed, skipped=skipped, current=None,
                error=failed[0]["error"] if failed else None, finished=review.now())
    except Exception as e:                                                  # never leave the record on "running"
        _record(pdir, state="failed", error=f"unexpected error: {e}", current=None, finished=review.now())


def start(pdir: Path, n: int | None = None) -> dict:
    """All prompts still missing for the approved analysis (n=None), or one prompt (n). Asking again while it runs returns the running job."""
    key = str(pdir)
    with _guard:
        if key in _running:
            cur = state(pdir)
            if (n is None and cur["kind"] == "all") or (n is not None and cur["kind"] == "one" and cur["n"] == n):
                return cur
            raise ReviewError("prompts are being written right now: wait until that finishes")
        if n is None:
            if not review.gates(pdir)["analysis"]["approved"]:
                raise ReviewError("approve the analysis first")
            ns = _targets(pdir, review.analysis_fp(pdir))
        else:
            review.request_regen(pdir, n)                               # also checks that the prompt exists
            ns = [n]
        base = dict(kind="one" if n is not None else "all", n=n, total=len(ns), done=0, failed=[], skipped=[], current=None, error=None,
                    started=review.now(), finished=None)
        if not ns:
            _record(pdir, **{**base, "state": "done", "finished": review.now()})
            return state(pdir)
        _record(pdir, **base, state="running")
        launch(pdir, _work, ns, review.analysis_fp(pdir), n is not None)
    return state(pdir)
