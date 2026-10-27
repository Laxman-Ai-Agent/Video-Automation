"""The Claude calls of the planning stages and the generation record of their background jobs. `run_claude` asks the LLM (through the LLM gateway, the user's own Claude CLI by default: no tools, no
project settings, a temp folder) and raises GenError when it cannot answer. `_record` / `state` / `launch` keep the progress and the failure of a planning job in review.json ("generation") and
make sure one job runs at a time per project."""
import contextlib
import threading
from pathlib import Path

from . import review

TIMEOUT = 180
_running: dict[str, threading.Thread] = {}     # project folder -> the thread that runs its generation job (planning, Visual Planning)
_guard = threading.RLock()                 # re-entrant: a launcher holds it while _record() may write a final state


class GenError(RuntimeError):
    """The CLI is missing, not signed in, timed out or returned nothing usable."""


def run_claude(user: str, system: str = "", timeout: int = TIMEOUT) -> str:
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
