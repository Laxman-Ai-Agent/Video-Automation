"""Improvement contracts (P0.5): small pydantic models for the NEW data (cues, emphasis events, shots, match detail, validation items).
They are written to sidecar files and never change an existing schema (models.py, api_models.py are untouched), so old projects keep working.
Every decision carries a Reason (which rule, which score, which cue). User-chosen assets are locked: the matcher, the shot planner and resume skip them."""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from . import config

Band = Literal["high", "medium", "low", "none"]
Severity = Literal["error", "warning", "info"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Reason(Strict):
    rule: str                       # the rule that decided, e.g. "clip_margin", "plan_keyword", "one_shot_per_scene"
    score: float | None = None
    source_cue: str | None = None   # Cue.id that caused it
    detail: str = ""


class Cue(Strict):
    """A phrase of the narration a visual or a highlight can be tied to. Times are seconds from the start of the audio."""
    id: str
    scene: int
    start: float
    end: float
    text: str
    kind: Literal["object", "number", "name", "concept", "contrast", "other"] = "other"
    timing: Literal["word", "phrase", "segment"] = "word"      # how precise `start`/`end` really are (never claim more than we have)


class EmphasisEvent(Strict):
    id: str
    scene: int
    start: float
    end: float
    text: str
    kind: Literal["number", "name", "concept", "contrast", "keyword"]
    timing: Literal["word", "phrase", "segment", "estimated"]
    reason: Reason


class Shot(Strict):
    """kind=whole_scene: the scene's single visual. kind=shot_change: a real change of picture inside a scene.
    `camera` is a SIMULATED move on one picture (push-in, pan ...) and is never a shot change."""
    id: str
    scene: int
    start: float
    end: float
    kind: Literal["whole_scene", "shot_change"]
    slots: list[str] = []
    camera: str | None = None
    locked: bool = False
    transition: str | None = None       # how this shot comes in (None for the first shot of a scene); transition_dur in seconds
    transition_dur: float = 0.0
    reason: Reason


class MatchDetail(Strict):
    n: int
    slot: str
    file: str | None
    status: Literal["ok", "review", "missing"]
    band: Band
    score: float | None = None
    margin: float | None = None
    locked: bool = False
    reason: Reason


class ValidationItem(Strict):
    severity: Severity
    rule: str
    scene: int | None = None
    shot: str | None = None
    issue: str
    action: str


def band(score: float | None, margin: float | None, has_file: bool = True) -> Band:
    """high: use it. medium: the existing "ok" rule (needs a look). low: below it. none: no image / no score (e.g. a manual choice)."""
    if not has_file or score is None:
        return "none"
    m = margin if margin is not None else 0.0
    if score >= config.MATCH_HIGH_SCORE and m >= config.MATCH_HIGH_MARGIN:
        return "high"
    if score >= config.CLIP_MIN_SCORE and m >= config.CLIP_MIN_MARGIN:
        return "medium"
    return "low"


# ---------- locks: prompt numbers the user chose by hand ----------
def locked_numbers(pdir: Path, matches: list | None = None) -> set[int]:
    """locks.json (list of prompt numbers) + every match with method "manual". Both mean: nobody but the user changes this image."""
    f = pdir / "locks.json"
    nums: set[int] = set(int(n) for n in json.loads(f.read_text(encoding="utf-8"))) if f.exists() else set()
    return nums | {m.n for m in (matches or []) if getattr(m, "method", None) == "manual"}


def set_lock(pdir: Path, n: int, locked: bool = True) -> None:
    nums = locked_numbers(pdir)
    nums = nums | {n} if locked else nums - {n}
    (pdir / "locks.json").write_text(json.dumps(sorted(nums)), encoding="utf-8")
