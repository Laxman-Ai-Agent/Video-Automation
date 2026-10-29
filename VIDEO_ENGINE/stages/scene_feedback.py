"""Phase 5b: what Final QC saw in the rendered video goes back to the scene it names.

The Final QC LLM review (`llm_review_qc.json`) looks at the frames and raises findings of category `visual` with a scene. Each becomes a repair note of that scene here; Motion
Generation puts the note into the scene's input fingerprint and its prompt, so ONLY the named scenes are written again (every other scene's code is reused). One round per plan:
a plan that changed (`plan` key) starts again with no notes and a full budget, the notes of a plan stay while it stands (without them the next run would write the scene a third time).
File: `scene_feedback[_9x16].json` = {"plan": sha of scene_plan + visual_planning, "rounds": n, "notes": {"<scene number>": "<what is wrong and what it should show>"}}."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

MAX_ROUNDS = 1                         # automatic rewrites per plan: after that the warnings stay disclosed in the QC report, an error keeps the stage blocked with its cause
SEVERITIES = ("error", "warning")      # `info` is a remark, not a request


def path(pdir: Path, aspect: str) -> Path:
    return pdir / ("scene_feedback_9x16.json" if aspect == "9:16" else "scene_feedback.json")


def _plan_key(pdir: Path) -> str:
    h = hashlib.sha256()
    for n in ("scene_plan.json", "visual_planning.json"):
        f = pdir / n
        h.update(f.read_bytes() if f.is_file() else b"-")
    return h.hexdigest()


def load(pdir: Path, aspect: str) -> dict:
    """The notes of the CURRENT plan (a stored file of another plan reads as empty)."""
    key = _plan_key(pdir)
    try:
        data = json.loads(path(pdir, aspect).read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("plan") == key:
            return {"plan": key, "rounds": int(data.get("rounds", 0)), "notes": dict(data.get("notes") or {})}
    except (OSError, ValueError):
        pass
    return {"plan": key, "rounds": 0, "notes": {}}


def note_for(pdir: Path, aspect: str, scene_id) -> str | None:
    return load(pdir, aspect)["notes"].get(str(scene_id))


def _number(scene_id) -> str | None:
    """`scene_002` (the timeline's name), 2 or "2" -> "2": the id Motion Generation gives the scene."""
    m = re.search(r"\d+", str(scene_id or ""))
    return str(int(m.group())) if m else None


def apply(pdir: Path, aspect: str) -> list[str]:
    """Turn the visual findings of the CURRENT Final QC review into repair notes and spend the plan's one round; returns the scene numbers to write again (none: no finding, no current review, or the round was spent)."""
    from SYSTEM.policies import llm_review
    cur = load(pdir, aspect)
    if cur["rounds"] >= MAX_ROUNDS or not llm_review.review_is_current(pdir, "qc", aspect):
        return []
    found: dict[str, list[str]] = {}
    for f in (llm_review.load_review(pdir, "qc", aspect) or {}).get("findings", []):
        n = _number(f.get("scene_id"))
        if n and f.get("category") == "visual" and f.get("severity") in SEVERITIES:
            found.setdefault(n, []).append(f"{f.get('message') or ''} {f.get('recommendation') or ''}".strip())
    if not found:
        return []
    cur["notes"].update({n: " ".join(t)[:1200] for n, t in found.items()})
    cur["rounds"] += 1
    f = path(pdir, aspect)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(cur, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, f)
    return sorted(found, key=int)
