"""Extra pre-render rules (A2V_VALIDATION=1) on top of prerender_checks.py, and the verdict of a run.
Pure functions over the composition + small metadata (no vision model). Each finding says scene/shot, issue and what to do.
A rule that crashes becomes a visible warning ("check_failed"): a broken check must never look like an all-clear.
verdict: "blocked" (an error stops the render), "needs_attention" (warnings: can render), "clear" (nothing found AND the checks really had something to look at)."""
import json
import re
import shutil
import subprocess
import time
from functools import lru_cache
from pathlib import Path

from . import config
from .prerender_checks import ERROR, INFO, WARNING, Report, text_width
from .theme import THEME

ASPECT_SIZE = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
CONTENT_LAYERS = {"image", "text", "counter", "chart", "map", "callout", "icon", "stock-video"}


def pascal(name: str) -> str:
    """Same conversion as VIDEO_ENGINE/remotion/src/components/IconPop.tsx: "map-pin" -> "MapPin"."""
    return re.sub(r"(^|-)(\w)", lambda m: m.group(2).upper(), name)


@lru_cache(maxsize=1)
def icon_names() -> frozenset[str] | None:
    """Keys of lucide-react's `icons` object (exactly what IconPop looks the name up in), read once through node. None when node or the package is
    missing (the rule is then skipped, never guessed)."""
    root = config.REMOTION_DIR
    if not (root / "node_modules" / "lucide-react").exists() or shutil.which("node") is None:
        return None
    try:
        r = subprocess.run(["node", "-e", "console.log(JSON.stringify(Object.keys(require('lucide-react').icons)))"], cwd=root, capture_output=True, text=True, timeout=30)
        names = frozenset(json.loads(r.stdout))
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return names or None


# ---------- rules: (rep, ctx) ----------
def r_meta_and_audio(rep: Report, c: dict) -> None:
    meta = c["comp"]["meta"]
    miss = [k for k in ("fps", "width", "height", "audio", "duration") if meta.get(k) in (None, "")]
    if miss:
        rep.add(ERROR, "render_config", None, None, f"the composition has no {', '.join(miss)}", "rebuild the composition")
    want = ASPECT_SIZE[c["aspect"]]
    if (meta.get("width"), meta.get("height")) != want:
        rep.add(ERROR, "aspect_mismatch", None, None, f"a {c['aspect']} video needs {want[0]}x{want[1]} but the composition is {meta.get('width')}x{meta.get('height')}", "rebuild the composition for this aspect")
    if c["audio_seconds"] is None and not any(c["pdir"].glob("audio.*")):
        rep.add(ERROR, "audio_missing", None, None, "the project has no audio file", "upload the narration audio: the video length follows it")


def r_prompts_in_video(rep: Report, c: dict) -> None:
    slots = {l.get("slot") for s in c["comp"]["scenes"] for l in s["layers"] if l.get("type") == "image" and l.get("enabled") is not False}
    for slot, p in c["prompts"].items():
        if p.get("required", True) and p.get("role") not in ("icon", "object") and slot not in slots:
            rep.add(WARNING, "prompt_not_in_video", p.get("scene"), slot, f"prompt {p['n']} ({slot}) has no picture layer in the video", "its picture would never show; restore the layer or remove the prompt")
    for m in (c["match"] or {}).get("matches", []):
        if m.get("status") == "review":
            slot = next((s for s, p in c["prompts"].items() if p["n"] == m["n"]), None)
            rep.add(WARNING, "needs_review", c["prompts"].get(slot, {}).get("scene"), slot, f"prompt {m['n']}: the match needs a decision" + (f" ({m['note']})" if m.get("note") else ""),
                    "confirm or replace the image; until then its slot stays empty")


def r_empty_scene(rep: Report, c: dict) -> None:
    for s in c["comp"]["scenes"]:
        shown = [l for l in s["layers"] if l.get("type") in CONTENT_LAYERS and l.get("enabled") is not False and (l.get("type") != "image" or l.get("file"))
                 and (l.get("type") != "text" or (l.get("text") or "").strip())]
        if not shown:
            rep.add(WARNING, "empty_scene", s["id"], None, f"scene {s['id']} would show only its background", "add a picture or a key word, or merge the scene with a neighbour")


def r_icons(rep: Report, c: dict) -> None:
    names, (w, h) = icon_names(), (c["comp"]["meta"]["width"], c["comp"]["meta"]["height"])
    safe = config.SAFE_AREA["margin"]
    low = h * (1 - (config.SAFE_AREA["portrait_ui_bottom"] if c["aspect"] == "9:16" else safe))
    for s in c["comp"]["scenes"]:
        for i, l in enumerate(s["layers"]):
            if l.get("type") != "icon" or l.get("enabled") is False or l.get("resource_id"):      # a registry icon is checked by the Resource Library (Stage 10), not against lucide
                continue
            name = l.get("lucide", "")
            where = f"icon {i} \"{name}\""
            if names is not None and pascal(name) not in names:
                rep.add(WARNING, "icon_unknown", s["id"], where, f"\"{name}\" is not an icon of the icon set, so nothing would be drawn", "pick an existing lucide icon name (e.g. map-pin, code, star)")
            x, y = l.get("pos") or (w / 2, h / 2)
            half = (l.get("size") or 160) / 2
            if x - half < w * safe or x + half > w * (1 - safe) or y - half < h * safe or y + half > low:
                rep.add(WARNING, "icon_position", s["id"], where, f"the icon at ({x:.0f}, {y:.0f}) reaches outside the safe area", "move it inward")


def r_repeats(rep: Report, c: dict) -> None:
    sc = c["comp"]["scenes"]
    for a, b in zip(sc, sc[1:]):
        ta, tb = (a.get("transition_out") or {}).get("type"), (b.get("transition_out") or {}).get("type")
        if config.TRANSITION_NO_REPEAT and ta and ta == tb:
            rep.add(WARNING, "transition_repeat", b["id"], None, f"scenes {a['id']} and {b['id']} both end with a '{ta}' transition", "use a different transition for one of them")
    for x, y, z in zip(sc, sc[1:], sc[2:]):
        m = [(s.get("camera") or {}).get("move") for s in (x, y, z)]
        if m[0] == m[1] == m[2] and m[0] not in (None, "static"):
            rep.add(INFO, "camera_repeat", z["id"], None, f"three scenes in a row use the same camera move ({m[0]})", "vary the camera for variety")


def r_shots(rep: Report, c: dict) -> None:
    from .shots import validate
    for s in c["comp"]["scenes"]:
        if s.get("shots"):
            for it in validate(s["start"], s["end"], s["shots"]):
                rep.add(it.severity, it.rule, s["id"], it.shot, it.issue, it.action)


def r_text(rep: Report, c: dict) -> None:
    comp, portrait = c["comp"], c["aspect"] == "9:16"
    meta = comp["meta"]
    scale = THEME["portrait"]["typeScale"] if portrait else 1.0
    body = THEME["type"]["body"] * scale
    max_w = meta["width"] * (1 - 2 * config.SAFE_AREA["margin"])
    if meta.get("subtitles"):                              # a single word wider than the safe width can never wrap
        from .telugu import glen
        for w in comp.get("words") or []:
            est = glen(w["w"]) * body * 0.62
            if est > max_w:
                rep.add(WARNING, "subtitle_width", None, w["w"], f"the subtitle word '{w['w']}' needs about {est:.0f}px, wider than the {max_w:.0f}px safe width", "split or shorten it in the transcript")
                break
    for s in comp["scenes"]:
        focus = (s.get("camera") or {}).get("focus")
        has_img = any(l.get("type") == "image" and l.get("file") for l in s["layers"])
        for i, l in enumerate(s["layers"]):
            if l.get("type") != "text" or l.get("enabled") is False or not (isinstance(l.get("pos"), list) and len(l["pos"]) == 2) or not focus or not has_img:
                continue
            size = THEME["type"]["display"] * scale if l.get("style") == "big-highlight" else body
            w = text_width(l.get("text", ""), size, 800 if l.get("style") == "big-highlight" else 600)
            x, y = l["pos"]
            left = x - w / 2 if l.get("center") else x
            fx, fy = focus[0] * meta["width"], focus[1] * meta["height"]
            if left <= fx <= left + w and y <= fy <= y + size * 1.2:
                rep.add(WARNING, "text_over_subject", s["id"], f"text {i} \"{l.get('text', '')[:24]}\"", "the text sits on the picture's focus point", "move the text away from the subject")


def r_highlight_timing(rep: Report, c: dict) -> None:
    from .highlights import segment_reliable
    from .transcribe import load_transcript
    try:
        t = load_transcript(c["pdir"])
    except FileNotFoundError:
        return
    words = [w for s in t.segments if segment_reliable(s) for w in s.words]
    bad = [s.id for s in t.segments if not segment_reliable(s)]
    if bad:
        rep.add(INFO, "word_timing_unreliable", None, None, f"word times of segment(s) {bad} look wrong; emphasis there is timed per segment", "check the transcript of those segments")
    for s in c["comp"]["scenes"]:
        for i, l in enumerate(s["layers"]):
            if l.get("type") == "text" and l.get("at") is not None and l.get("style") == "big-highlight" and words:
                off = min(abs(w.start - l["at"]) for w in words)
                if off > config.HIGHLIGHT_TOLERANCE_SEC:
                    rep.add(INFO, "highlight_timing", s["id"], f"text {i} \"{l.get('text', '')[:24]}\"", f"the headline appears {off:.2f}s from the nearest spoken word (tolerance {config.HIGHLIGHT_TOLERANCE_SEC}s)", "turn on A2V_HIGHLIGHTS or move its time onto the word")


RULES = (r_meta_and_audio, r_prompts_in_video, r_empty_scene, r_icons, r_repeats, r_shots, r_text, r_highlight_timing)


def extend(rep: Report, comp: dict, pdir: Path, aspect: str, match: dict | None, prompts: dict, audio_seconds: float | None) -> None:
    ctx = {"comp": comp, "pdir": pdir, "aspect": aspect, "match": match, "prompts": prompts, "audio_seconds": audio_seconds}
    for rule in RULES:
        try:
            rule(rep, ctx)
        except Exception as e:      # a broken rule is visible, never silent
            rep.add(WARNING, "check_failed", None, None, f"the check '{rule.__name__}' failed ({type(e).__name__}: {e})", "report this; the other checks still ran, but this part is NOT verified")
    rep.checked = {"scenes": len(comp["scenes"]), "image_layers": sum(1 for s in comp["scenes"] for l in s["layers"] if l.get("type") == "image"), "rules": len(RULES) + 3}


def verdict(rep: Report) -> str:
    if rep.blocking:
        return "blocked"
    if rep.summary()[WARNING] or rep.summary()[ERROR]:
        return "needs_attention"
    checked = getattr(rep, "checked", None)
    if checked is not None and checked["scenes"] == 0:      # nothing was looked at: never "clear"
        return "needs_attention"
    return "clear"


def record_failure(pdir: Path, aspect: str, err: Exception) -> None:
    """The check itself crashed and the render goes on (a bug in a check must not stop a video): the report says "unverified", never "clear"."""
    from .prerender_checks import report_path
    f = {"severity": WARNING, "rule": "check_failed", "scene": None, "shot": None, "message": f"the pre-render check could not run ({type(err).__name__}: {err})",
         "advice": "the video was NOT verified; look at log.txt and run `python -m backend.cli check <id>`"}
    report_path(pdir, aspect).write_text(json.dumps({"aspect": aspect, "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False, "verdict": "unverified",
                                                     "summary": {ERROR: 0, WARNING: 1, INFO: 0}, "findings": [f]}, indent=1, ensure_ascii=False), encoding="utf-8")


def record_run(pdir: Path, rep: Report, report_file: Path, comp_file: Path) -> None:
    """Adds verdict + run info to the report JSON just written and appends the run to validation_history.json (last 20 runs)."""
    data = json.loads(report_file.read_text(encoding="utf-8"))
    data["verdict"] = verdict(rep)
    data["run"] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "composition": comp_file.name, "checked": getattr(rep, "checked", None)}
    report_file.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    hf = pdir / "validation_history.json"
    hist = json.loads(hf.read_text(encoding="utf-8")) if hf.exists() else []
    hist.append({"at": data["run"]["at"], "aspect": rep.aspect, "verdict": data["verdict"], "summary": rep.summary()})
    hf.write_text(json.dumps(hist[-20:], indent=1), encoding="utf-8")
