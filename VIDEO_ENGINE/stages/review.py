"""Review workflow on top of the existing project files: the scene table, prompt review (edit / approve / regenerate request), approval gates,
saved crops and the state of the timeline. Nothing here replaces a stage; it reads scene_plan.json, prompts_map.json, match_report.json and
the transcripts, and keeps what the user decides in two small files:
  review.json  gates {analysis, prompts, images} with a fingerprint of what was approved, and per-prompt edits / history / approvals
  crops.json   {slot: {aspect: {x, y, zoom, file}}}   (the original image is never touched)
An approval is only valid while its fingerprint still matches the files: editing a prompt, replacing an image or moving a crop makes the
affected gates stale by itself, so nothing downstream can run on outdated decisions."""
import hashlib
import json
import re
import threading
import time
from pathlib import Path

from PIL import Image

from . import config
from .assets import raw_dir, work_dir
from .models import MatchReport, ScenePlan

WHITE_BG = "isolated on plain white background"

GATES = ("analysis", "prompts", "images")
ASPECTS = ("16:9", "9:16")
MIN_PROMPT, MAX_PROMPT = 8, 1500
ZOOM_MIN, ZOOM_MAX = 1.0, 4.0


LOCK = threading.RLock()                 # the background prompt writer (promptgen.py) and the request threads read-modify-write the same files


def _locked(fn):
    def wrapper(*a, **k):
        with LOCK:
            return fn(*a, **k)
    wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
    return wrapper


class ReviewError(ValueError):
    """A request the current project state does not allow (the API turns it into a 409/422 with this message)."""

    def __init__(self, message: str, blockers: list[str] | None = None):
        super().__init__(message)
        self.blockers = blockers or []


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def h(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def _retry(fn):
    """Windows refuses to read or replace a file for a moment while another thread replaces it (the prompt writer runs beside the requests)."""
    for i in range(20):
        try:
            return fn()
        except PermissionError:
            if i == 19:
                raise
            time.sleep(0.05)


def _read(path: Path) -> str:
    return _retry(lambda: path.read_text(encoding="utf-8"))


def _load(path: Path, default):
    try:
        return json.loads(_read(path)) if path.exists() else default
    except (OSError, ValueError):
        return default


def _save(path: Path, data) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    _retry(lambda: tmp.replace(path))


def state_of(pdir: Path) -> dict:
    st = _load(pdir / "review.json", {})
    st.setdefault("gates", {})
    st.setdefault("prompts", {})
    return st


def _plan(pdir: Path) -> ScenePlan | None:
    f = pdir / "scene_plan.json"
    return ScenePlan.model_validate_json(_read(f)) if f.exists() else None


def _prompts_raw(pdir: Path) -> dict:
    return json.loads(_read(pdir / "prompts_map.json"))


def _report(pdir: Path) -> MatchReport | None:
    f = pdir / "match_report.json"
    return MatchReport.model_validate_json(f.read_text(encoding="utf-8")) if f.exists() else None


# ---------- fingerprints ----------
def analysis_fp(pdir: Path) -> str:
    f = pdir / "scene_plan.json"
    return h(f.read_text(encoding="utf-8")) if f.exists() else ""


def prompts_fp(pdir: Path) -> str:
    if not (pdir / "prompts_map.json").exists():
        return ""
    return h(analysis_fp(pdir), *[f"{p['slot']}:{h(p['text'])}" for p in sorted(_prompts_raw(pdir)["prompts"], key=lambda p: p["n"])])


def images_fp(pdir: Path) -> str:
    rep = _report(pdir)
    assigned = [f"{m.n}:{m.file}:{m.status}" for m in rep.matches] if rep else []
    crops = (pdir / "crops.json").read_text(encoding="utf-8") if (pdir / "crops.json").exists() else ""
    return h(prompts_fp(pdir), *assigned, crops)


# ---------- scene table ----------
def _in(seg: dict, start: float, end: float) -> bool:
    return start <= (seg["start"] + seg["end"]) / 2 < end


def _plan_issues(pdir: Path) -> tuple[list[str], list[str]]:
    try:
        from . import plan_checks
        return plan_checks.check(pdir)
    except Exception:                                  # the plan files are still being written, or the composition is not built yet
        return [], []


def scene_rows(pdir: Path) -> dict:
    plan = _plan(pdir)
    if plan is None:
        return {"scenes": [], "general": [], "duration": None, "status": "empty"}
    tr = _load(pdir / "transcript_fixed.json", None) or _load(pdir / "transcript_corrected.json", None) or _load(pdir / "transcript.json", {"segments": [], "duration": None})
    en = _load(pdir / "transcript_en.json", {"segments": []})
    errors, warnings = _plan_issues(pdir)
    issues = [("error", m) for m in errors] + [("warning", m) for m in warnings]
    pm = _prompts_raw(pdir) if (pdir / "prompts_map.json").exists() else {"prompts": []}
    rows, claimed = [], set()
    for s in plan.scenes:
        mine = []
        for i, (sev, msg) in enumerate(issues):
            if re.match(rf"scene {s.id}\b", msg):
                mine.append({"severity": sev, "message": msg})
                claimed.add(i)
        rows.append({
            "id": s.id, "start": s.start, "end": s.end, "duration": round(s.end - s.start, 2),
            "narration": " ".join(x["text"] for x in tr["segments"] if _in(x, s.start, s.end)),
            "narration_en": " ".join(x.get("en", "") for x in en["segments"] if _in(x, s.start, s.end)),
            "meaning": s.meaning, "concept": s.concept, "mood": s.mood, "mode": s.mode, "pattern": s.pattern,
            "keywords": [{"text": k.text, "at": k.at} for k in s.keywords],
            "slots": [p["slot"] for p in pm["prompts"] if p["scene"] == s.id],
            "status": "error" if any(i["severity"] == "error" for i in mine) else "warning" if mine else "ok", "issues": mine,
        })
    general = [{"severity": sev, "message": msg} for i, (sev, msg) in enumerate(issues) if i not in claimed]
    worst = "error" if any(r["status"] == "error" for r in rows) or any(g["severity"] == "error" for g in general) else \
        "warning" if any(r["status"] == "warning" for r in rows) or general else "ok"
    return {"scenes": rows, "general": general, "duration": tr.get("duration"), "status": worst}


# ---------- prompts ----------
def full_prompt(p: dict, plan: ScenePlan) -> str:
    """The complete text the user sends to the image generator (what prompts.txt contains), without its number."""
    parts = [p["text"].strip().rstrip(".,")]
    if p["role"] in ("icon", "object") and WHITE_BG not in p["text"]:
        parts.append(WHITE_BG)
    parts += [plan.style.suffix.strip().rstrip(","), p["ratio"]]
    return ", ".join(parts)


def _image_info(pdir: Path, name: str | None) -> dict:
    path = work_dir(pdir) / (Path(name or "").stem + ".png")
    try:
        with Image.open(path) as im:
            w, ht = im.size
        return {"width": w, "height": ht, "ratio": round(w / ht, 3)}
    except (OSError, ValueError):
        return {"width": None, "height": None, "ratio": None}


def crops_of(pdir: Path) -> dict:
    return _load(pdir / "crops.json", {})


def crop_for(pdir: Path, slot: str, aspect: str, file: str | None) -> dict | None:
    """The saved crop of a slot for one aspect, only while it was made for the image that is assigned now."""
    c = crops_of(pdir).get(slot, {}).get(aspect)
    return c if c and (file is None or c.get("file") == file) else None


def prompt_items(pdir: Path) -> list[dict]:
    plan = _plan(pdir)
    if plan is None or not (pdir / "prompts_map.json").exists():
        return []
    st, rep, crops = state_of(pdir), _report(pdir), crops_of(pdir)
    scenes = {s.id: s for s in plan.scenes}
    rows = {r["id"]: r for r in scene_rows(pdir)["scenes"]}
    matches = {m.n: m for m in rep.matches} if rep else {}
    out = []
    for p in sorted(_prompts_raw(pdir)["prompts"], key=lambda x: x["n"]):
        ps = st["prompts"].get(p["slot"], {})
        approved = ps.get("approved_hash") == h(p["text"])
        edited = ps.get("base") is not None and ps.get("base") != p["text"]
        m = matches.get(p["n"])
        file = m.file if m else None
        sc = scenes.get(p["scene"])
        item_crops = {}
        for aspect in ASPECTS:
            c = crops.get(p["slot"], {}).get(aspect)
            if c:
                item_crops[aspect] = {**c, "stale": bool(file and c.get("file") != file)}
        out.append({
            "n": p["n"], "scene": p["scene"], "slot": p["slot"], "role": p["role"], "ratio": p["ratio"], "required": p.get("required", True),
            "text": p["text"], "full_text": full_prompt(p, plan),
            "scene_start": sc.start if sc else None, "scene_end": sc.end if sc else None,
            "concept": sc.concept if sc else "", "narration_en": rows.get(p["scene"], {}).get("narration_en", ""),
            "status": "approved" if approved else "regenerating" if ps.get("regen_requested") else "edited" if edited else "generated",
            "approved": approved, "edited": edited, "regen_requested": ps.get("regen_requested"),
            "generated_text": ps.get("base") if edited else None,
            "history": ps.get("history", [])[-6:], "history_count": len(ps.get("history", [])),
            "image": None if m is None else {
                "file": file, "status": m.status, "method": m.method, "score": m.score, "margin": m.margin, "note": m.note,
                "warnings": [w["type"] for w in (rep.warnings if rep else []) if w["n"] == p["n"]], **_image_info(pdir, file)},
            "crops": item_crops,
        })
    return out


def _write_prompts(pdir: Path, raw: dict) -> None:
    _save(pdir / "prompts_map.json", raw)
    # Note: prompts.txt generation for raster image generators was removed in Motion-Only mode


def _find(raw: dict, n: int) -> dict:
    for p in raw["prompts"]:
        if p["n"] == n:
            return p
    raise ReviewError(f"prompt {n} does not exist")


def _clean(text: str) -> str:
    text = " ".join(text.split())
    if not MIN_PROMPT <= len(text) <= MAX_PROMPT:
        raise ReviewError(f"a prompt needs {MIN_PROMPT}-{MAX_PROMPT} characters (this one has {len(text)})")
    return text


@_locked
def save_prompt(pdir: Path, n: int, text: str) -> dict:
    """Save one edited prompt. Only this prompt changes; its previous text is kept in the history; its approval is dropped by itself (the hash differs)."""
    text = _clean(text)
    raw = _prompts_raw(pdir)
    p = _find(raw, n)
    if text == p["text"]:
        return p
    st = state_of(pdir)
    ps = st["prompts"].setdefault(p["slot"], {})
    if ps.get("base") is None:
        ps["base"] = p["text"]                       # the generated text, so the edit is visible as a change and can be undone
    ps.setdefault("history", []).append({"text": p["text"], "at": now(), "by": "edit"})
    ps["edited_text"] = text
    ps.pop("regen_requested", None)
    p["text"] = text
    _write_prompts(pdir, raw)
    _save(pdir / "review.json", st)
    return p


@_locked
def approve_prompts(pdir: Path, ns: list[int] | None = None) -> int:
    raw, st = _prompts_raw(pdir), state_of(pdir)
    count = 0
    for p in raw["prompts"]:
        if ns is None or p["n"] in ns:
            st["prompts"].setdefault(p["slot"], {})["approved_hash"] = h(p["text"])
            count += 1
    _save(pdir / "review.json", st)
    return count


@_locked
def request_regen(pdir: Path, n: int) -> None:
    """Record that a new text was asked for (the card shows 'regeneration requested' until set_generated() replaces it). promptgen.py then writes
    it; /regen <id> <n> in Claude Code ends in the same set_generated()."""
    raw, st = _prompts_raw(pdir), state_of(pdir)
    p = _find(raw, n)
    st["prompts"].setdefault(p["slot"], {})["regen_requested"] = now()
    _save(pdir / "review.json", st)


def scene_context(pdir: Path, n: int) -> dict:
    """What a regeneration has to follow: the approved scene, its narration, the prompt role and the current text."""
    raw = _prompts_raw(pdir)
    p = _find(raw, n)
    row = next((r for r in scene_rows(pdir)["scenes"] if r["id"] == p["scene"]), {})
    plan = _plan(pdir)
    return {"prompt": p, "scene": row, "style_suffix": plan.style.suffix if plan else "",
            "same_scene_prompts": [{"n": q["n"], "role": q["role"], "text": q["text"]} for q in raw["prompts"] if q["scene"] == p["scene"] and q["n"] != n]}


@_locked
def set_generated(pdir: Path, n: int, text: str, expect: str | None = None, fp: str | None = None, keep_approved: bool = False) -> dict:
    """A newly GENERATED text for one prompt (/regen or the app's own writer). It replaces the current text because the user asked for it; the previous
    text stays in the history. Other prompts, and their approvals, are not touched. With `expect` the text is only replaced while it is still that
    text (the user may have edited it while the new one was being written); with keep_approved an approved prompt is left alone. `fp` marks the
    prompt as written for that analysis, so a retry does not write it again."""
    text = _clean(text)
    raw, st = _prompts_raw(pdir), state_of(pdir)
    p = _find(raw, n)
    ps = st["prompts"].setdefault(p["slot"], {})
    if expect is not None and p["text"] != expect:
        raise ReviewError(f"prompt {n} was changed while the new text was written; your version was kept")
    if keep_approved and ps.get("approved_hash") == h(p["text"]):
        raise ReviewError(f"prompt {n} was approved while the new text was written; the approved version was kept")
    ps.setdefault("history", []).append({"text": p["text"], "at": now(), "by": "regenerated"})
    for k in ("base", "edited_text", "approved_hash", "regen_requested"):
        ps.pop(k, None)
    if fp:
        ps["generated_for"] = fp
    p["text"] = text
    _write_prompts(pdir, raw)
    _save(pdir / "review.json", st)
    return p


@_locked
def reapply_edits(pdir: Path) -> int:
    """/plan writes prompts_map.json again from scratch. A prompt the user edited must survive that: put the user's text back and keep the newly
    generated text as the 'generated' reference. Returns how many prompts were restored."""
    if not (pdir / "prompts_map.json").exists():
        return 0
    raw, st = _prompts_raw(pdir), state_of(pdir)
    restored = 0
    for p in raw["prompts"]:
        ps = st["prompts"].get(p["slot"])
        mine = ps.get("edited_text") if ps else None
        if mine and p["text"] != mine:
            if p["text"] != ps.get("base"):
                ps.setdefault("history", []).append({"text": p["text"], "at": now(), "by": "plan"})
            ps["base"] = p["text"]
            p["text"] = mine
            restored += 1
    if restored:
        _write_prompts(pdir, raw)
        _save(pdir / "review.json", st)
    return restored


# ---------- crops ----------
@_locked
def save_crop(pdir: Path, n: int, aspect: str, x: float, y: float, zoom: float) -> dict:
    if aspect not in ASPECTS:
        raise ReviewError(f"aspect must be one of {', '.join(ASPECTS)}")
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ReviewError("the crop centre must be inside the picture (0..1)")
    if not ZOOM_MIN <= zoom <= ZOOM_MAX:
        raise ReviewError(f"zoom must be between {ZOOM_MIN:g} and {ZOOM_MAX:g}")
    p = _find(_prompts_raw(pdir), n)
    rep = _report(pdir)
    m = next((m for m in rep.matches if m.n == n), None) if rep else None
    if m is None or not m.file:
        raise ReviewError(f"prompt {n} has no image yet: upload and match an image before cropping")
    crops = crops_of(pdir)
    crops.setdefault(p["slot"], {})[aspect] = {"x": round(x, 4), "y": round(y, 4), "zoom": round(zoom, 3), "file": m.file, "at": now()}
    _save(pdir / "crops.json", crops)
    return crops[p["slot"]][aspect]


@_locked
def reset_crop(pdir: Path, n: int, aspect: str | None = None) -> bool:
    slot = _find(_prompts_raw(pdir), n)["slot"]
    crops = crops_of(pdir)
    if slot not in crops:
        return False
    for a in ([aspect] if aspect else list(crops[slot])):
        crops[slot].pop(a, None)
    if not crops[slot]:
        crops.pop(slot)
    _save(pdir / "crops.json", crops)
    return True


# ---------- gates ----------
def _record_ok(st: dict, gate: str, fp: str) -> bool:
    r = st["gates"].get(gate)
    return bool(r and fp and r.get("fp") == fp)


def gates(pdir: Path) -> dict:
    st = state_of(pdir)
    plan = _plan(pdir)
    a_fp, p_fp, i_fp = analysis_fp(pdir), prompts_fp(pdir), images_fp(pdir)
    errors, warnings = _plan_issues(pdir) if plan else ([], [])
    a_ok = _record_ok(st, "analysis", a_fp)
    p_ok = a_ok and _record_ok(st, "prompts", p_fp)
    i_ok = p_ok and _record_ok(st, "images", i_fp)

    a_block = ["The plan does not exist yet: run /plan in Claude Code"] if plan is None else [f"plan error: {e}" for e in errors]
    items = prompt_items(pdir) if plan else []
    unapproved = [p["n"] for p in items if not p["approved"]]
    p_block = [] if a_ok else ["Approve the analysis first"]
    if not items:
        p_block.append("There are no prompts yet")
    elif unapproved:
        p_block.append(f"{len(unapproved)} prompts are not approved yet: {', '.join(map(str, unapproved[:8]))}{'...' if len(unapproved) > 8 else ''}")
    rep = _report(pdir)
    i_block = [] if p_ok else ["Approve the prompts first"]
    if rep is None:
        i_block.append("The images have not been matched yet: upload them and press Apply or Submit")
    else:
        req = {p["n"]: p["required"] for p in items}
        for m in rep.matches:
            if (not m.file or m.status == "missing") and req.get(m.n, True):
                i_block.append(f"prompt {m.n}: {'has conflicting files' if m.note and 'claim' in m.note else 'has no image'}")

    def one(gate, ok, block, extra=None):
        rec = st["gates"].get(gate)
        return {"approved": ok, "stale": bool(rec) and not ok, "at": rec.get("at") if rec else None, "ready": not block,
                "blockers": block, **(extra or {})}
    return {
        "analysis": one("analysis", a_ok, a_block, {"warnings": warnings}),
        "prompts": one("prompts", p_ok, p_block, {"total": len(items), "approved_count": len(items) - len(unapproved)}),
        "images": one("images", i_ok, i_block),
    }


@_locked
def set_gate(pdir: Path, gate: str, approved: bool) -> dict:
    if gate not in GATES:
        raise ReviewError(f"unknown gate {gate!r} (use {', '.join(GATES)})")
    st = state_of(pdir)
    if not approved:
        st["gates"].pop(gate, None)
        _save(pdir / "review.json", st)
        return gates(pdir)[gate]
    g = gates(pdir)
    for before in GATES[:GATES.index(gate)]:
        if not g[before]["approved"]:
            raise ReviewError(f"approve the {before} first", g[gate]["blockers"])
    if not g[gate]["ready"]:
        raise ReviewError(f"the {gate} cannot be approved yet", g[gate]["blockers"])
    fp = {"analysis": analysis_fp, "prompts": prompts_fp, "images": images_fp}[gate](pdir)
    st["gates"][gate] = {"fp": fp, "at": now()}
    _save(pdir / "review.json", st)
    return gates(pdir)[gate]


# ---------- timeline ----------
def timeline_state(pdir: Path) -> dict:
    """Per aspect: has the pre-render check run on the current composition, and did it pass. A passed check on fresh files = a verified timeline."""
    out = {}
    for aspect in ASPECTS:
        sfx = "_9x16" if aspect == "9:16" else ""
        comp, report = pdir / f"composition{sfx}.json", pdir / f"prerender_report{sfx}.json"
        data = _load(report, None)
        inputs = [f for f in (comp, pdir / "match_report.json", pdir / "prompts_map.json", pdir / "crops.json") if f.exists()]
        fresh = bool(data and comp.exists() and report.stat().st_mtime >= max(f.stat().st_mtime for f in inputs))
        summary = (data or {}).get("summary", {})
        out[aspect] = {
            "composition": comp.exists(), "checked": data is not None, "fresh": fresh, "ok": bool(data and data.get("ok")),
            "errors": summary.get("error", 0), "warnings": summary.get("warning", 0), "ready": bool(fresh and data and data.get("ok")),
            "preview_video": (pdir / f"out_preview{sfx}.mp4").exists(), "final_video": (pdir / f"out{sfx}.mp4").exists(),
            "findings": [f for f in (data or {}).get("findings", []) if f["severity"] != "info"][:60],
        }
    return out


def review(pdir: Path, pid: str) -> dict:
    return {"project": pid, "plan_ready": _plan(pdir) is not None and (pdir / "prompts_map.json").exists(), "analysis": scene_rows(pdir),
            "prompts": prompt_items(pdir), "gates": gates(pdir), "timeline": timeline_state(pdir)}


def asset_path(pdir: Path, name: str) -> Path | None:
    """The picture to show for an image of this project (the 2560 px work copy when there is one). Names are checked against the project's own folders."""
    for folder, convert in ((raw_dir(pdir), True), (pdir / "assets" / "inbox", False)):
        if (folder / name).is_file():
            work = work_dir(pdir) / (Path(name).stem + ".png")
            return work if convert and work.exists() else folder / name
    return None
