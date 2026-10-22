"""Cues: which phrase of the narration each prompt (picture) belongs to. No model: plain word overlap between the prompt text and the English
translation of the narration (transcript_en.json, segment times from Whisper). The English text is not aligned word by word, so a cue is as precise
as a SEGMENT and says so (timing="segment"). A prompt with no overlap gets no cue: it falls back to the scene-level picture.
  python -m backend.cues projects/demo"""
import json
import re
import sys
from pathlib import Path

from . import config
from .contracts import Cue
from .models import PromptsMap, ScenePlan

STOP = set("""a an the of and or to in on at for with from by is are was were be been it its this that these those as into over under near beside while which
who whose their his her they them we you he she not no but if so than then there here very more most can could will would should may might do does did have
has had about around across between through during each both own same other another such only just also like using used use""".split())
STYLE = set("view shot close closeup background lighting light soft style cinematic isolated white plain angle depth field shallow studio floating".split())


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "ly", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[:-len(suf)]
    return w


def stems(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOP and w not in STYLE}


def _same(a: str, b: str) -> bool:
    return a == b or (len(a) >= 5 and len(b) >= 5 and a[:5] == b[:5])


def overlap(prompt: str, narration: str) -> int:
    n = stems(narration)
    return sum(1 for p in stems(prompt) if any(_same(p, x) for x in n))


def build(pdir: Path) -> dict:
    """{"cues": [Cue], "links": {prompt n: cue id | None}, "scenes": {scene id: {"arrangement", "prompts"}}}"""
    plan = ScenePlan.model_validate_json((pdir / "scene_plan.json").read_text(encoding="utf-8"))
    prompts = PromptsMap.model_validate_json((pdir / "prompts_map.json").read_text(encoding="utf-8")).prompts
    ef = pdir / "transcript_en.json"
    segs = json.loads(ef.read_text(encoding="utf-8"))["segments"] if ef.exists() else []
    cues: list[Cue] = []
    links: dict[str, str | None] = {}
    scenes: dict[str, dict] = {}
    for sc in plan.scenes:
        mine = [p for p in prompts if p.scene == sc.id]
        inside = [s for s in segs if s["start"] < sc.end and s["end"] > sc.start]
        pick: dict[int, dict | None] = {}
        for p in mine:
            scored = [(overlap(p.text, s["en"]), -s["start"], s) for s in inside]
            best = max(scored, key=lambda x: (x[0], x[1]), default=None)
            pick[p.n] = best[2] if best and best[0] >= 1 else None
        made: dict[int, str] = {}
        for seg in sorted({id(s): s for s in pick.values() if s}.values(), key=lambda s: s["start"]):
            cid = f"scene_{sc.id:02d}_cue_{len(made) + 1:02d}"
            made[seg["id"]] = cid
            kinds = {p.role for p in mine if pick[p.n] is seg}
            cues.append(Cue(id=cid, scene=sc.id, start=round(seg["start"], 3), end=round(seg["end"], 3), text=seg["en"],
                            kind="object" if kinds & {"object", "icon"} else "concept", timing="segment"))
        for p in mine:
            links[str(p.n)] = made[pick[p.n]["id"]] if pick[p.n] else None
        used = [links[str(p.n)] for p in mine if links[str(p.n)]]
        starts = sorted({c.start for c in cues if c.id in used})
        if len(mine) < 2:
            arr = "single"
        elif not used:
            arr = "scene_level"                                  # no narration phrase found: the scene's own visual carries it
        elif len(set(used)) < len(used) or len(starts) < 2 or min(b - a for a, b in zip(starts, starts[1:])) < config.MIN_SHOT_SEC:
            arr = "combined"                                      # the same phrase (or phrases too close for separate shots): show the pictures together
        else:
            arr = "timed"                                         # different phrases far enough apart: one picture per phrase
        scenes[str(sc.id)] = {"arrangement": arr, "prompts": [p.n for p in mine]}
    return {"version": 1, "cues": [c.model_dump() for c in cues], "links": links, "scenes": scenes}


if __name__ == "__main__":
    out = build(config.project_dir(sys.argv[1]))
    for sid, s in out["scenes"].items():
        print(f"scene {sid}: {s['arrangement']:11} prompts {s['prompts']} -> {[out['links'][str(n)] for n in s['prompts']]}")
