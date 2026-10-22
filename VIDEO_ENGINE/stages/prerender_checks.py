"""Pre-render validation: python -m backend.prerender_checks <project> [--aspect 9:16]  (exit 2 when something would break the render (error findings)).

Looks at what is about to be rendered (the filled composition, the images behind it, the match report and the audio) and writes
prerender_report.json (prerender_report_9x16.json for the vertical video). Findings have a severity:
  error   the render would fail or the video would be wrong (missing file, broken timeline, audio and video lengths far apart): blocks
  warning something looks wrong and a person should look (empty slot, heavy crop, blurry image): reviewable, never blocks
  info    worth knowing
Nothing is fixed automatically: crop and meaning decisions belong to the user. No new model or dependency: sizes come from Pillow, the
image quality marks from the match step (checks.py), geometry from theme.json."""
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image

from . import audio_utils, config
from .theme import THEME

ERROR, WARNING, INFO = "error", "warning", "info"
EPS = 0.05                  # seconds: timing noise that is not a problem
FRAME_TOL = 1.5             # frames: a scene boundary off by more than this is a gap or an overlap
AUDIO_WARN, AUDIO_BIG = 0.25, 1.0       # seconds between the audio file and the composition length (a mismatch renders fine, so it is never blocking)
PREFLIGHT = {"missing_file", "unreadable_image"}   # render.preflight already stops the render for these, with its own message
MIN_SHOT, MAX_SHOT = 1.0, 20.0          # seconds a scene should last
CROP_WARN = 0.55            # warn when less of a photo than this stays visible in its box
UPSCALE_WARN = 2.0          # warn when a photo must be enlarged more than this to fill its box (at the camera's closest zoom): visibly soft
MAX_ZOOM = THEME["camera"]["maxScale"]
UI_BOTTOM = 0.16            # share of a vertical frame that phone apps cover
EM = {"light": 0.6, "bold": 0.64}


@dataclass
class Finding:
    severity: str
    rule: str
    scene: int | None
    shot: str | None
    message: str
    advice: str


@dataclass
class Report:
    aspect: str
    findings: list[Finding] = field(default_factory=list)

    def add(self, severity, rule, scene, shot, message, advice):
        self.findings.append(Finding(severity, rule, scene, shot, message, advice))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def blocking(self) -> list[Finding]:
        """Errors this check stops the render for (missing and unreadable files are stopped by render.preflight, with its own message)."""
        return [f for f in self.errors if f.rule not in PREFLIGHT]

    def summary(self) -> dict:
        return {s: sum(1 for f in self.findings if f.severity == s) for s in (ERROR, WARNING, INFO)}

    def to_json(self) -> dict:
        return {"aspect": self.aspect, "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": not self.errors,
                "summary": self.summary(), "findings": [asdict(f) for f in self.findings]}


def report_path(pdir: Path, aspect: str = "16:9") -> Path:
    return pdir / f"prerender_report{'_9x16' if aspect == '9:16' else ''}.json"


def comp_file(pdir: Path, aspect: str) -> Path:
    return pdir / f"composition{'_9x16' if aspect == '9:16' else ''}.json"


# ---------- geometry (the same boxes and the same object-fit: cover rule the renderer uses) ----------
def box_px(pos, frame: tuple[int, int], portrait: bool) -> tuple[float, float, float, float]:
    fw, fh = frame
    if isinstance(pos, (list, tuple)) and len(pos) == 4:
        return tuple(float(v) for v in pos)
    boxes = THEME["portrait"]["boxes"] if portrait else THEME["boxes"]
    x, y, w, h = boxes.get(pos if isinstance(pos, str) else "full", boxes["full"])
    return x * fw, y * fh, w * fw, h * fh


def visible_share(image: tuple[int, int], box: tuple[float, float, float, float]) -> float:
    """Share of the photo's area that stays visible when it fills the box with object-fit: cover."""
    iw, ih = image
    bw, bh = box[2], box[3]
    s = max(bw / iw, bh / ih)
    return min(1.0, bw / (iw * s)) * min(1.0, bh / (ih * s))


def upscale(image: tuple[int, int], box: tuple[float, float, float, float]) -> float:
    """How many times the photo must be enlarged to fill the box (1.0 = exactly as many pixels as the screen needs)."""
    return max(box[2] / image[0], box[3] / image[1])


def text_width(text: str, size: float, weight: int) -> float:
    return len(text) * size * (EM["bold"] if weight >= 700 else EM["light"])      # same estimate as VIDEO_ENGINE/remotion/src/textfit.ts


def _times(layer: dict) -> float | None:
    at = layer.get("at")
    if at is None:
        at = (layer.get("enter") or {}).get("at")
    return at


# ---------- the rules ----------
def check_timeline(rep: Report, comp: dict, audio_seconds: float | None) -> None:
    meta, scenes = comp["meta"], comp["scenes"]
    fps = meta.get("fps", 30)
    tol = FRAME_TOL / fps
    first, last = scenes[0], scenes[-1]
    if abs(first["start"]) > tol:
        rep.add(ERROR, "timeline_start", first["id"], None, f"the first scene starts at {first['start']:.2f}s, not at 0",
                "the video would begin with a gap; regenerate the composition (/plan) so scene 1 starts at 0")
    if abs(last["end"] - meta["duration"]) > max(tol, 0.1):
        rep.add(ERROR if abs(last["end"] - meta["duration"]) > AUDIO_BIG else WARNING, "timeline_end", last["id"], None,
                f"the last scene ends at {last['end']:.2f}s but the composition length is {meta['duration']:.2f}s",
                "make the last scene end where the audio ends")
    for a, b in zip(scenes, scenes[1:]):
        gap = b["start"] - a["end"]
        if gap > tol:
            rep.add(ERROR, "timeline_gap", b["id"], None, f"{gap:.2f}s with no scene between scene {a['id']} and scene {b['id']}",
                    "extend a scene or fix the cut points so the audio is always covered")
        elif gap < -tol:
            rep.add(ERROR, "timeline_overlap", b["id"], None, f"scene {b['id']} starts {-gap:.2f}s before scene {a['id']} ends",
                    "scenes must not overlap; fix the cut points")
    for s in scenes:
        d = s["end"] - s["start"]
        if d <= 0 or d * fps < 1:
            rep.add(ERROR, "shot_duration", s["id"], None, f"scene {s['id']} lasts {d:.2f}s", "a scene needs at least one frame; fix its start and end")
        elif d < MIN_SHOT:
            rep.add(WARNING, "shot_duration", s["id"], None, f"scene {s['id']} lasts only {d:.2f}s", "a very short scene flashes by; merge it with a neighbour")
        elif d > MAX_SHOT:
            rep.add(WARNING, "shot_duration", s["id"], None, f"scene {s['id']} lasts {d:.1f}s", "a long scene needs more than one picture or a camera move; split it")
        t = (s.get("transition_out") or {}).get("dur")
        if t and d > 0 and t > d / 2:
            rep.add(WARNING, "transition_length", s["id"], None, f"the {t:.1f}s transition is more than half of the {d:.1f}s scene", "shorten the transition")
        for i, layer in enumerate(s["layers"]):
            if layer.get("enabled") is False:
                continue                                       # switched off: not rendered
            at = _times(layer)
            if at is None:
                continue
            shot = layer.get("slot") or f"layer {i} ({layer.get('type')})"
            if at >= s["end"] - EPS:
                rep.add(WARNING, "layer_timing", s["id"], shot, f"{shot} is set to appear at {at:.2f}s, after the scene ends at {s['end']:.2f}s",
                        "it would never be seen; move its time inside the scene")
            elif at < s["start"] - EPS:
                rep.add(WARNING, "layer_timing", s["id"], shot, f"{shot} is set to appear at {at:.2f}s, before the scene starts at {s['start']:.2f}s",
                        "it would show at the start of the scene instead; check its time")
    if audio_seconds is not None:
        diff = abs(meta["duration"] - audio_seconds)
        if diff > AUDIO_WARN:
            rep.add(WARNING, "audio_video_length", None, None,
                    f"the audio lasts {audio_seconds:.2f}s but the video is planned for {meta['duration']:.2f}s ({diff:.2f}s apart)" + (" - far apart" if diff > AUDIO_BIG else ""),
                    "the sound would stop early or the picture would end first; use the audio the plan was made for, or plan again")


def check_media(rep: Report, comp: dict, pdir: Path, aspect: str, match: dict | None, prompts: dict[str, dict]) -> None:
    portrait = aspect == "9:16"
    frame = (comp["meta"]["width"], comp["meta"]["height"])
    public = config.REMOTION_DIR / "public"
    warnings_by_slot: dict[str, list[str]] = {}
    if match:
        slot_of = {p["n"]: p["slot"] for p in prompts.values()}
        for w in match.get("warnings", []):
            slot = slot_of.get(w["n"])
            if slot:
                warnings_by_slot.setdefault(slot, []).append(w["type"])
    used: dict[str, list[tuple[int, str]]] = {}
    for s in comp["scenes"]:
        for i, layer in enumerate(s["layers"]):
            if layer.get("type") != "image" or layer.get("enabled") is False:
                continue
            slot = layer.get("slot") or f"layer {i}"
            f = layer.get("file")
            if not f:
                prompt = prompts.get(slot)
                required = prompt is None or prompt.get("required", True)
                rep.add(WARNING if required else INFO, "empty_slot", s["id"], slot,
                        f"{slot} has no picture" + (f" (prompt {prompt['n']})" if prompt else ""),
                        "upload an image for this prompt, or accept a scene that shows only its background and text" if required else "this picture is optional")
                continue
            path = public / f
            if not path.exists():
                rep.add(ERROR, "missing_file", s["id"], slot, f"{f} does not exist", "run the build again so the images are copied")
                continue
            used.setdefault(f, []).append((s["id"], slot))
            try:
                with Image.open(path) as im:
                    size = im.size
            except Exception:
                rep.add(ERROR, "unreadable_image", s["id"], slot, f"{f} cannot be read as an image", "re-export the image and upload it again")
                continue
            if layer.get("anim") == "float":
                continue                                            # a cut-out is contained, not cropped
            box = box_px(layer.get("pos"), frame, portrait)
            share = visible_share(size, box) / (layer.get("zoom") or 1) ** 2        # a zoom saved in the crop editor shows even less of the photo
            if share < CROP_WARN:
                rep.add(WARNING, "heavy_crop", s["id"], slot, f"only {share * 100:.0f}% of {Path(f).name} stays visible in its {box[2]:.0f}x{box[3]:.0f} box ({size[0]}x{size[1]} image)",
                        "the subject may be cut off; " + ("generate this picture in 9:16 or check the crop point" if portrait else "use a picture closer to the box's shape"))
            up = upscale(size, box) * MAX_ZOOM
            if up > UPSCALE_WARN and "low_res" not in warnings_by_slot.get(slot, []) or up > 2 * UPSCALE_WARN:
                rep.add(WARNING, "upscaled", s["id"], slot, f"{Path(f).name} ({size[0]}x{size[1]}) is enlarged {up:.1f}x to fill {box[2]:.0f}x{box[3]:.0f} at the camera's closest zoom",
                        "it will look soft; use a larger image")
            for kind in warnings_by_slot.get(slot, []):
                if kind == "blurry":
                    rep.add(WARNING, "blurry", s["id"], slot, f"{Path(f).name} looks blurry (low detail)", "generate it again with sharper detail")
                elif kind == "low_res":
                    rep.add(WARNING, "low_resolution", s["id"], slot, f"{Path(f).name} is smaller than the 1920 px a main picture needs", "use a larger image; the camera zoom is already limited for it")
                elif kind == "bad_ratio":
                    rep.add(WARNING, "bad_ratio", s["id"], slot, f"{Path(f).name} does not have the shape its prompt asked for", "the picture will be cropped or the subject may sit off-centre; generate it with the requested ratio")
    for f, uses in used.items():
        if len(uses) > 1:
            where = ", ".join(f"scene {sc} ({sl})" for sc, sl in uses)
            rep.add(WARNING, "reused_asset", uses[0][0], uses[0][1], f"{Path(f).name} is used more than once: {where}", "each prompt should have its own picture; upload another one")
    if match:
        assigned = {m["file"] for m in match.get("matches", []) if m.get("file")}
        for a, b in match.get("duplicates", []):
            both = a in assigned and b in assigned
            rep.add(WARNING if both else INFO, "duplicate_images", None, None, f"{a} and {b} look almost identical" + ("" if both else " (one of them is not used)"),
                    "two prompts would show the same picture; replace one of them" if both else "nothing to do")


def check_text(rep: Report, comp: dict, aspect: str) -> None:
    portrait = aspect == "9:16"
    fw, fh = comp["meta"]["width"], comp["meta"]["height"]
    scale = THEME["portrait"]["typeScale"] if portrait else 1.0
    t = {k: v * scale for k, v in THEME["type"].items()}
    safe = THEME["safeMargin"]
    max_w = fw * (1 - 2 * safe)
    for s in comp["scenes"]:
        for i, layer in enumerate(s["layers"]):
            if layer.get("type") != "text" or layer.get("enabled") is False:
                continue
            text, style = layer.get("text", ""), layer.get("style", "caption")
            shot = f"text {i} \"{text[:24]}\""
            size, weight = (t["display"], 800) if style == "big-highlight" else (t["body"], 600)
            w = text_width(text, size, weight)
            pos = layer.get("pos")
            if isinstance(pos, list) and len(pos) == 2:
                x, y = pos
                left, right = (x - w / 2, x + w / 2) if layer.get("center") else (x, x + w)
                if not portrait and (left < fw * safe - 1 or right > fw * (1 - safe) + 1):       # a vertical frame wraps pinned text instead
                    rep.add(WARNING, "text_safe_area", s["id"], shot, f"the text runs from x={left:.0f} to x={right:.0f}, outside the {safe * 100:.0f}% safe margin",
                            "shorten the text or move it inward")
                lo, hi = fh * safe, fh * (1 - (UI_BOTTOM if portrait else safe))
                if not lo - 1 <= y <= hi + 1:
                    rep.add(WARNING, "text_safe_area", s["id"], shot, f"the text sits at y={y:.0f}, outside the safe area ({lo:.0f}-{hi:.0f})",
                            "move it away from the edge" + (" and the area phone apps cover" if portrait else ""))
            else:
                lines = math.ceil(w / (max_w * (0.6 if style == "label" else 0.7 if style == "lower-third" else 1.0)))
                if lines > 2:
                    rep.add(WARNING, "text_length", s["id"], shot, f"the {style} text needs about {lines} lines", "show only the key words (rules: 1-2 short text elements per scene)")


def check(pdir: Path, aspect: str = "16:9") -> Report:
    rep = Report(aspect)
    comp = json.loads(comp_file(pdir, aspect).read_text(encoding="utf-8"))
    audio = next((f for f in sorted(pdir.glob("audio.*")) if f.suffix.lower() in {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}), None)
    audio_seconds = None
    if audio is not None:
        try:
            audio_seconds = audio_utils.duration(audio)
        except Exception:
            rep.add(INFO, "audio_length_unknown", None, None, "the audio length could not be read", "check that ffprobe works")
    match = json.loads((pdir / "match_report.json").read_text(encoding="utf-8")) if (pdir / "match_report.json").exists() else None
    pm = pdir / "prompts_map.json"
    prompts = {p["slot"]: p for p in json.loads(pm.read_text(encoding="utf-8"))["prompts"]} if pm.exists() else {}
    check_timeline(rep, comp, audio_seconds)
    check_media(rep, comp, pdir, aspect, match, prompts)
    check_text(rep, comp, aspect)
    if config.improve("validation"):          # improvement P6: extra rules + verdict (backend/quality.py)
        from . import quality
        quality.extend(rep, comp, pdir, aspect, match, prompts, audio_seconds)
    return rep


def write_report(pdir: Path, rep: Report) -> Path:
    path = report_path(pdir, rep.aspect)
    path.write_text(json.dumps(rep.to_json(), indent=1, ensure_ascii=False), encoding="utf-8")
    if config.improve("validation"):          # improvement P6: verdict + run info in the report, history of runs
        from . import quality
        quality.record_run(pdir, rep, path, comp_file(pdir, rep.aspect))
    return path


def format_text(rep: Report) -> str:
    s = rep.summary()
    out = [f"pre-render check ({rep.aspect}): {s[ERROR]} errors, {s[WARNING]} warnings, {s[INFO]} notes"]
    for f in sorted(rep.findings, key=lambda f: (f.severity != ERROR, f.severity != WARNING, f.scene or 0)):
        where = f"scene {f.scene}" if f.scene is not None else "video"
        out.append(f"  [{f.severity.upper():7}] {where}{' / ' + f.shot if f.shot else ''}: {f.message}\n            -> {f.advice}")
    return "\n".join(out)


def blocking_message(rep: Report) -> str:
    return ("The video would not render correctly: " + "; ".join((f"scene {f.scene}: " if f.scene is not None else "") + f.message for f in rep.blocking[:4])
            + f". Full list: {report_path(Path('.'), rep.aspect).name}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aspect = "9:16" if "9:16" in sys.argv else "16:9"
    pdir = config.project_dir(args[0])
    r = check(pdir, aspect)
    write_report(pdir, r)
    print(format_text(r))
    sys.exit(2 if r.errors else 0)
