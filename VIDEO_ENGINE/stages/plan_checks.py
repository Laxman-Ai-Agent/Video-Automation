"""python -m backend.plan_checks projects/demo -> quality checks on the Phase 1 files (exit 1 on errors)."""
import json
import re
import sys
from pathlib import Path

from . import scene_segmentation
from . import config
from .models import Composition, Cuts, PromptsMap, ScenePlan
from .motion_checks import check as motion_check
from .palette import check as palette_check
from .transcribe import load_transcript
from .transition_audit import audit as audit_transitions

PATTERN_IMAGES: dict[str, int] = json.loads(
    (config.REMOTION_DIR / "src/patterns/images.json").read_text(encoding="utf-8"))
TELUGU = re.compile(r"[ఀ-౿]")
IMG_TEXT = re.compile(r"\b(with (the )?(text|words|letters|caption|title)|written|saying|logo|watermark|typography|signage|subtitles?)\b", re.I)
WHITE_BG = "isolated on plain white background"
EPS = 0.06


def check(pdir: Path) -> tuple[list[str], list[str]]:
    E: list[str] = []
    W: list[str] = []
    plan = ScenePlan.model_validate_json((pdir / "scene_plan.json").read_text(encoding="utf-8"))
    pm = PromptsMap.model_validate_json((pdir / "prompts_map.json").read_text(encoding="utf-8"))
    comp = Composition.model_validate_json((pdir / "composition.json").read_text(encoding="utf-8"))
    cuts = Cuts.model_validate_json((pdir / "cuts.json").read_text(encoding="utf-8")).cuts
    tr = load_transcript(pdir)
    scenes = plan.scenes
    seg = scene_segmentation.load_fresh(pdir)
    cut_t = [0.0, tr.duration, *[c.t for c in cuts], *([x for s in seg["scenes"] for x in (s["start_time"], s["end_time"])] if seg else [])]
    en_f = pdir / "transcript_en.json"
    en_txt = " ".join(x["en"] for x in json.loads(en_f.read_text(encoding="utf-8"))["segments"]) if en_f.exists() else ""
    digits = set(re.findall(r"\d+(?:[.,]\d+)?", " ".join(s.text for s in tr.segments) + " " + en_txt))

    # the scenes are the ones Scene Segmentation decided (one planned scene each, its start and the pause after it): a plan made from other boundaries is refused
    from .visual_planning import mapping_errors
    E += [e["message"] for e in mapping_errors(scenes, seg, tr.duration)]

    # coverage + scene length + snapping
    if abs(scenes[0].start) > EPS:
        E.append(f"coverage: first scene starts at {scenes[0].start}, expected 0")
    if abs(scenes[-1].end - tr.duration) > 0.15:
        E.append(f"coverage: last scene ends at {scenes[-1].end}, audio is {tr.duration:.2f}s")
    for a, b in zip(scenes, scenes[1:]):
        if abs(a.end - b.start) > EPS:
            E.append(f"coverage: gap/overlap between scene {a.id} ({a.end}) and {b.id} ({b.start})")
    for s in scenes:
        d = s.end - s.start
        if d < 2 or d > 20:
            E.append(f"scene {s.id}: length {d:.1f}s (must be 2-20s)")
        elif d < 3 or d > 15:
            W.append(f"scene {s.id}: length {d:.1f}s (typical 3-15s)")
        for t in (s.start, s.end):
            if min(abs(t - c) for c in cut_t) > EPS:
                W.append(f"scene {s.id}: boundary {t} is not a cut point")
        for k in s.keywords:
            if not s.start - EPS <= k.at <= s.end + EPS:
                E.append(f"scene {s.id}: keyword '{k.text}' at {k.at} outside scene")

    # patterns, images, text density, transitions
    by_scene = {s.id: s for s in scenes}
    for s in scenes:
        if s.pattern not in PATTERN_IMAGES:
            E.append(f"scene {s.id}: unknown pattern '{s.pattern}'")
    for c in comp.scenes:
        n_text = sum(1 for l in c.layers if l.type in ("text", "counter"))
        if n_text > 2:
            E.append(f"scene {c.id}: {n_text} text elements (max 2)")
        for l in c.layers:
            for key in ("at",):
                v = getattr(l, key, None) or (l.model_extra or {}).get(key)
                if isinstance(v, (int, float)) and not c.start - EPS <= v <= c.end + EPS:
                    E.append(f"scene {c.id}: layer {l.type} at={v} outside {c.start}-{c.end}")
    _, t_err, t_warn = audit_transitions(plan, comp)   # repeats, unknown types, mood fit, variety
    E += t_err
    W += t_warn
    comp_raw = json.loads((pdir / "composition.json").read_text(encoding="utf-8"))
    W += palette_check(comp_raw, plan.style.palette)                                                              # colors outside the palette, weak contrast
    W += motion_check(comp_raw, json.loads((pdir / "scene_plan.json").read_text(encoding="utf-8")))              # camera limits, effect timing
    motion_only = bool(json.loads((pdir / "composition.json").read_text(encoding="utf-8")).get("meta", {}).get("motionOnly"))
    img_slots = {(l.model_extra or {}).get("slot") for c in comp.scenes for l in c.layers if l.type == "image"}
    # prompts
    n = sorted(p.n for p in pm.prompts)
    if n != list(range(1, len(n) + 1)):
        E.append("prompts: numbers must be 1..N without gaps")
    per_scene: dict[int, int] = {}
    for p in pm.prompts:
        per_scene[p.scene] = per_scene.get(p.scene, 0) + 1
        if p.scene not in by_scene:
            E.append(f"prompt {p.n}: scene {p.scene} does not exist")
        if p.slot not in img_slots and not motion_only:      # a motion-only composition (Use Images OFF) has no picture layers on purpose
            E.append(f"prompt {p.n}: slot '{p.slot}' has no image layer in composition.json")
        if TELUGU.search(p.text):
            E.append(f"prompt {p.n}: contains Telugu script")
        if IMG_TEXT.search(re.sub(r"\bno (text|words|letters|logo|watermark)\b", "", p.text, flags=re.I)):
            E.append(f"prompt {p.n}: asks for text/logo inside the image")
        if p.role in ("icon", "object") and WHITE_BG not in p.text:
            W.append(f"prompt {p.n}: icon/object without '{WHITE_BG}' (prompts_writer adds it)")
        if p.role in ("icon", "object") and p.ratio != "1:1":
            W.append(f"prompt {p.n}: icon/object ratio {p.ratio}, expected 1:1")
    for sid, k in per_scene.items():
        sc = by_scene.get(sid)
        if sc and k > PATTERN_IMAGES.get(sc.pattern, 0):
            E.append(f"scene {sid}: {k} prompts but pattern '{sc.pattern}' shows {PATTERN_IMAGES[sc.pattern]} images")
    if len(pm.prompts) > 1.5 * len(scenes):
        W.append(f"prompts: {len(pm.prompts)} > 1.5 x {len(scenes)} scenes")
    # numbers must come from the audio
    for s in scenes:
        p = s.params
        vals = ([p.number] if p.number is not None else []) + [d.value for d in (p.data or [])]
        for v in vals:
            sv = str(int(v)) if float(v).is_integer() else str(v)
            if sv not in digits and not p.approximate:
                W.append(f"scene {s.id}: value {sv} not found as digits in transcript; set params.approximate=true or confirm")
    return E, W


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    E, W = check(pdir)
    for m in W:
        print("warn :", m)
    for m in E:
        print("ERROR:", m)
    print(f"plan_checks: {len(E)} errors, {len(W)} warnings")
    sys.exit(1 if E else 0)
