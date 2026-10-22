"""Timeline approval gate for the routes and agents: Stage 12 (timeline_approval.py) is the authority; this module keeps the {ready, approved, stale, blockers} view every consumer reads
and the checks every final-render entry point repeats."""
import json
from pathlib import Path

from . import pipeline


def built_for_mode(pdir: Path, aspect: str) -> bool:
    """Was the composition on disk built by the motion-only build (meta.motionOnly)? A composition of the removed image workflow is never ready, never approvable and never rendered."""
    try:
        meta = json.loads(pipeline._comp(pdir, aspect).read_text(encoding="utf-8")).get("meta", {})
    except (OSError, ValueError):
        return True                                   # no composition yet: the other rules say "build the timeline first"
    return bool(meta.get("motionOnly"))


def state(pdir: Path, aspect: str) -> dict:
    """{ready, version, approved, stale, at, blockers, status ...}: Stage 12's record against the current inputs (timeline_approval.legacy_state)."""
    from . import timeline_approval
    return timeline_approval.legacy_state(pdir, aspect)


def require_approved(pdir: Path, aspect: str) -> None:
    """The guard of every entry point that starts a FINAL render (also /run final): the current version must be approved."""
    from .errors import ApiError
    st = state(pdir, aspect)
    if not st["approved"]:
        raise ApiError(409, "timeline_not_approved", "the current timeline is not approved" if not st["stale"] else "the timeline changed after it was approved",
                       ("; ".join(st["blockers"][:3]) or "approve the timeline on the Timeline Approval page, then Render Video") if st.get("status") else
                       "build the timeline, then press Approve Timeline and Render Video" if not st["ready"] else "press Approve Timeline, then Render Video")


def render_blockers(pdir: Path, aspect: str) -> list[str]:
    """Everything the server checks again when Render Video is pressed (the buttons being enabled proves nothing)."""
    st = state(pdir, aspect)
    out = list(st["blockers"])
    if st["ready"] and not st["approved"]:
        out.append("the timeline changed after it was approved: approve this version first" if st["stale"] else "approve the timeline first")
    from . import motion_branch
    out += motion_branch.blockers(pdir, aspect)
    return out
