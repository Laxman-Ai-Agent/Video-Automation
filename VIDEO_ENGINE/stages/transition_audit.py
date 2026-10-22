"""python -m backend.transition_audit projects/demo -> the transition after every scene, plus variety and mood checks.

Uses the mood table Remotion's pickTransition uses (VIDEO_ENGINE/remotion/src/transitions/by_mood.json), so plan and renderer agree."""
import json
import re
import sys
from dataclasses import dataclass
from math import ceil
from pathlib import Path

from . import config
from .models import Composition, ScenePlan

_DIR = config.REMOTION_DIR / "src/transitions"
BY_MOOD: dict[str, list[str]] = json.loads((_DIR / "by_mood.json").read_text(encoding="utf-8"))
_LIST = re.search(r"TRANSITIONS = \[(.*?)\] as const", (_DIR / "index.ts").read_text(encoding="utf-8"), re.S)
if _LIST is None:
    raise RuntimeError("VIDEO_ENGINE/remotion/src/transitions/index.ts: TRANSITIONS list not found; update transition_audit.py")
KNOWN = set(re.findall(r'"([a-z-]+)"', _LIST.group(1)))
MIN_DISTINCT = 3      # from 5 transitions on, at least this many different types
MAX_SHARE = 1 / 3     # no type may carry more than this share of the transitions


def table_mood(mood: str) -> str | None:
    """The first table mood contained in the text, or None when the text names none (the planner writes free text: "busy, habitual")."""
    low = mood.lower()
    return next((k for k in BY_MOOD if k in low), None)


def mood_key(mood: str) -> str:
    """Same rule as pickTransition: first table mood contained in the text, else calm. Only for picking a transition; a fit is judged with table_mood."""
    return table_mood(mood) or "calm"


@dataclass
class Row:
    scene: int
    mood: str
    type: str | None
    fits: bool | None   # None = no transition to judge


def audit(plan: ScenePlan, comp: Composition) -> tuple[list[Row], list[str], list[str]]:
    """Returns (rows, errors, warnings). A transition fits when it suits the mood of the scene it leaves or the one it enters."""
    E: list[str] = []
    W: list[str] = []
    mood = {s.id: s.mood for s in plan.scenes}
    rows: list[Row] = []
    prev: str | None = None
    for i, c in enumerate(comp.scenes):
        t = (c.transition_out or {}).get("type")
        nxt = comp.scenes[i + 1] if i + 1 < len(comp.scenes) else None
        if t is None:
            if nxt is not None:
                W.append(f"scene {c.id}: no transition into scene {nxt.id} (hard cut)")
            rows.append(Row(c.id, mood.get(c.id, ""), None, None))
            prev = None
            continue
        if t not in KNOWN:
            E.append(f"scene {c.id}: unknown transition '{t}' (renderer would fall back to fade)")
        if t == prev:
            E.append(f"scene {c.id}: transition '{t}' repeats previous")
        seen = [table_mood(mood.get(c.id, ""))] + ([table_mood(mood.get(nxt.id, ""))] if nxt else [])
        allowed = {x for k in seen if k for x in BY_MOOD[k]}
        # a mood the table does not know cannot be judged (calling it "calm" flagged every free-text mood that is not calm): a transition is a
        # misfit only when every mood it sits between is known and none allows it; with an unknown mood and no match there is no verdict
        fits = True if t in allowed else False if all(seen) else None
        if fits is False and t in KNOWN:
            W.append(f"scene {c.id}: '{t}' does not fit mood '{mood.get(c.id, '')}' (fits: {', '.join(sorted(allowed))})")
        rows.append(Row(c.id, mood.get(c.id, ""), t, fits))
        prev = t
    used = [r.type for r in rows if r.type]
    if len(used) >= 5:
        if len(set(used)) < MIN_DISTINCT:
            W.append(f"variety: only {len(set(used))} different transitions in {len(used)}")
        for t in sorted(set(used)):
            if used.count(t) > ceil(len(used) * MAX_SHARE):
                W.append(f"variety: '{t}' used {used.count(t)}x of {len(used)}")
    return rows, E, W


def load(pdir: Path) -> tuple[ScenePlan, Composition]:
    return (ScenePlan.model_validate_json((pdir / "scene_plan.json").read_text(encoding="utf-8")),
            Composition.model_validate_json((pdir / "composition.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    rows, E, W = audit(*load(config.project_dir(sys.argv[1])))
    print(f"{'scene':>5}  {'transition':<13} {'fit':<4} mood")
    for r in rows:
        print(f"{r.scene:>5}  {(r.type or '-'):<13} {'-' if r.fits is None else ('ok' if r.fits else 'NO'):<4} {r.mood}")
    for m in W:
        print("warn :", m)
    for m in E:
        print("ERROR:", m)
    print(f"transition_audit: {len(E)} errors, {len(W)} warnings")
    sys.exit(1 if E else 0)
