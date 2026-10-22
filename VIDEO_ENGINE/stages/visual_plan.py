"""visual_plan.json: the visual plan of the whole project, one file, Project -> Scenes -> Shots -> Assets / Layers.
The scenes are exactly the scenes of the analysis (scene_plan.json); everything that already exists (timing, narration, assets from prompts_map.json, camera /
text / icons / effects / transition from composition.json) is copied in, nothing is invented. The user then edits it, regenerates ONE scene (Claude CLI, planning
data only: never images, videos or prompts) and approves each scene. Saves change only the fields that were edited; every other scene stays untouched.
IDs are stable: scene_NN, scene_NN_shot_NN, assets use their prompt slot (s02_0), text / graphic / layer / effect / transition ids follow the same pattern.
This file is the planning stage's data: the render still reads composition.json, so editing here does not change the video until a later stage uses it.
ROLE: this is the user-editable shots/layers plan (API /visual-plan and the Timeline fill, which writes the user's edits into the composition). It is NOT the semantic Visual Plan the
Visual Planning page shows and Motion Planning receives: that is visual_planning.json (backend/visual_planning.py). An edit made on an older version of a scene is never written into the
composition (apply_edits skips the scenes that need_edit), and a file that is brought in line with a changed analysis is copied to plan_backups/ first when it holds edited scenes."""
import copy
import json
import threading
from pathlib import Path

from . import promptgen, review
from .promptgen import GenError

FILE = "visual_plan.json"
VERSION = 1
STATUSES = ("pending", "in_progress", "approved", "needs_edit")
ASSET_TYPES = ("image", "video", "none")
EPS = 0.06
# fields that belong to the analysis or to the system: shown, never edited from the table
READ_ONLY = (("id",), ("number",), ("start",), ("end",), ("duration",), ("narration_te",), ("narration_en",), ("counts",), ("meta",), ("approval",))
READ_ONLY_LEAVES = ("id", "prompt_number")
HASH_VERSION = 2
STALE_REASON = "the analysis of this scene changed after you worked on it"

_lock = threading.RLock()
_regenerating: set[tuple[str, str]] = set()


class PlanError(Exception):
    def __init__(self, message: str, code: str = "invalid_visual_plan", status: int = 422, hint: str = ""):
        super().__init__(message)
        self.message, self.code, self.status, self.hint = message, code, status, hint


def scene_id(n: int) -> str:
    return f"scene_{n:02d}"


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ---------- derive from the existing project data ----------
def _comp_scenes(pdir: Path) -> dict[int, dict]:
    data = review._load(pdir / "composition.json", {})
    return {s["id"]: s for s in data.get("scenes", []) if isinstance(s, dict) and "id" in s}


def _assets(pdir: Path, n: int, sid: str, params) -> list[dict]:
    out = [{"id": p["slot"], "type": "image", "role": p["role"], "ratio": p["ratio"], "required": p.get("required", True), "prompt_number": p["n"]}
           for p in review._prompts_raw(pdir)["prompts"] if p["scene"] == n]
    if params is not None and params.video:
        out.append({"id": f"{sid}_video_01", "type": "video", "source": params.video, "required": True})
    return out


def _counts(scene: dict) -> dict:
    assets = [a for sh in scene["shots"] for a in sh.get("assets", [])]
    return {"shots": len(scene["shots"]), "images": sum(a.get("type") == "image" for a in assets), "videos": sum(a.get("type") == "video" for a in assets),
            "text_elements": sum(len(sh.get("text", [])) for sh in scene["shots"]),
            "graphics": sum(len(sh.get("graphics", [])) for sh in scene["shots"]) + len(scene.get("motion_graphics", []))}


def _transitions(scene: dict, next_id: str | None) -> list[dict]:
    out = []
    for i, sh in enumerate(scene["shots"]):
        t = sh.get("transition")
        if t:
            to = scene["shots"][i + 1]["id"] if i + 1 < len(scene["shots"]) else next_id
            out.append({"id": f"{scene['id']}_transition_{len(out) + 1:02d}", "type": t.get("type"), "duration": t.get("duration"), "from": sh["id"], "to": to})
    return out


def _source_hash(row: dict, comp: dict | None, prompts: list[dict], params) -> str:
    keep = {k: row[k] for k in ("id", "start", "end", "narration", "narration_en", "meaning", "concept", "mood", "mode", "pattern", "keywords")}
    # what the planner decided (scene row, prompts, params), NOT the composition: building the timeline writes the pictures, the camera and the user's own edits into
    # the composition, and that must never look like "the analysis changed" and take the approval away
    return review.h(json.dumps([keep, prompts, params.model_dump() if params else None], sort_keys=True, ensure_ascii=False))


def _derive_scene(pdir: Path, row: dict, plan_scene, comp: dict | None, next_id: str | None) -> dict:
    n, sid = row["id"], scene_id(row["id"])
    params = plan_scene.params if plan_scene else None
    prompts = [p for p in review._prompts_raw(pdir)["prompts"] if p["scene"] == n]
    cam = (comp or {}).get("camera") or {}
    texts, graphics, effects, layers = [], [], [], []
    motion = []
    for k, layer in enumerate((comp or {}).get("layers", []), 1):
        kind = layer.get("type")
        layers.append({"id": f"{sid}_layer_{k:02d}", "type": kind, "z": layer.get("z"), "start": row["start"], "end": row["end"], "enabled": layer.get("enabled") is not False,
                       **({"asset_id": layer["slot"], "animation": layer.get("anim")} if kind == "image" else {})})
        if kind == "text":
            anim = (layer.get("enter") or {}).get("anim") or ("spring-fade" if layer.get("mark") else "fade")
            dur = layer.get("dur")
            if dur is None and layer.get("exit"):
                dur = layer["exit"].get("dur", 0.5)
            texts.append({"id": f"{sid}_text_{len(texts) + 1:02d}", "content": layer.get("text"), "mark": layer.get("mark"), "position": layer.get("pos"),
                          "font_style": layer.get("style", "caption"), "animation": anim, "start": layer.get("at"), "duration": dur})
        elif kind == "icon":
            enter = layer.get("enter") or {}
            graphics.append({"id": f"{sid}_graphic_{len(graphics) + 1:02d}", "type": "icon", "name": layer.get("lucide"), "position": layer.get("pos"),
                             "animation": enter.get("anim"), "start": enter.get("at"), "duration": enter.get("dur")})
        elif kind == "shape":
            graphics.append({"id": f"{sid}_graphic_{len(graphics) + 1:02d}", "type": "shape", "name": layer.get("kind"), "color": layer.get("color"),
                             "start": layer.get("at"), "duration": layer.get("dur")})
        elif kind == "effect":
            effects.append({"id": f"{sid}_effect_{len(effects) + 1:02d}", "type": layer.get("name"), "position": layer.get("pos"), "start": layer.get("at"), "duration": layer.get("dur")})
        elif kind in ("counter", "number counter"):
            motion.append({"id": f"{sid}_motion_{len(motion) + 1:02d}", "type": "number counter", "value": layer.get("to"), "unit": layer.get("unit"),
                           "start": layer.get("at"), "duration": layer.get("dur", 2.0), "position": layer.get("pos")})
        elif kind in ("chart", "bar chart", "line chart", "pie chart"):
            motion.append({"id": f"{sid}_motion_{len(motion) + 1:02d}", "type": f"{layer.get('kind', 'bar')} chart", "data": layer.get("data", []),
                           "start": layer.get("at"), "duration": layer.get("dur", 2.0), "box": layer.get("box")})
        elif kind in ("callout", "callout circle", "callout arrow", "callout box", "callout underline"):
            motion.append({"id": f"{sid}_motion_{len(motion) + 1:02d}", "type": f"callout {layer.get('kind', 'circle')}", "kind": layer.get("kind", "circle"),
                           "color": layer.get("color"), "target": layer.get("target"), "start": layer.get("at"), "duration": layer.get("dur", 1.0)})
    if not motion:
        if params is not None and params.number is not None:
            motion.append({"id": f"{sid}_motion_01", "type": "number counter", "value": params.number, "unit": params.unit, "start": row["keywords"][0]["at"] if row["keywords"] else None})
        if params is not None and params.data:
            motion.append({"id": f"{sid}_motion_{len(motion) + 1:02d}", "type": f"{params.kind or 'bar'} chart", "data": [d.model_dump() for d in params.data], "start": row["start"]})
    out = comp.get("transition_out") if comp else None
    shot = {"id": f"{sid}_shot_01", "start": row["start"], "end": row["end"], "purpose": row["meaning"], "visual_description": row["concept"],
            "assets": _assets(pdir, n, sid, params), "camera": {"movement": cam.get("move"), "zoom_from": cam.get("from"), "zoom_to": cam.get("to"), "focus": cam.get("focus")},
            "text": texts, "graphics": graphics, "transition": {"type": out.get("type"), "duration": out.get("dur")} if out else None}
    scene = {"id": sid, "number": n, "start": row["start"], "end": row["end"], "duration": row["duration"], "narration_te": row["narration"], "narration_en": row["narration_en"],
             "purpose": row["meaning"], "concept": row["concept"], "mood": row["mood"], "mode": row["mode"], "pattern": row["pattern"], "keywords": row["keywords"],
             "shots": [shot], "layers": layers, "motion_graphics": motion, "effects": effects}
    scene["transitions"] = _transitions(scene, next_id)
    scene["counts"] = _counts(scene)
    scene["approval"] = {"status": "pending", "updated_at": None, "approved_at": None, "reason": None}
    scene["meta"] = {"revision": 1, "source": "derived", "edited": False, "edited_paths": [], "updated_at": review.now(), "source_hash": _source_hash(row, comp, prompts, params), "hash_version": HASH_VERSION}
    return scene


# ---------- the file ----------
def _read(pdir: Path) -> dict | None:
    f = pdir / FILE
    if not f.exists():
        return None
    try:
        data = json.loads(review._read(f))
    except ValueError as e:
        raise PlanError(f"visual_plan.json is not valid JSON ({e})", "visual_plan_broken", 409, "fix or remove the file, then reload") from e
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
        raise PlanError("visual_plan.json has no scenes list", "visual_plan_broken", 409, "fix or remove the file, then reload")
    return data


def _backup_edits(pdir: Path, old: dict, scenes: list[dict], was: dict) -> None:
    """The user's edits are never lost to a migration: when a scene they edited is dropped (its number no longer exists) or is marked as stale, the file as it was is copied to
    plan_backups/<time>/visual_plan.json first."""
    now = {s.get("number"): s for s in scenes}
    at_risk = [n for n, sc in old.items() if sc.get("meta", {}).get("edited")
               and (n not in now or (now[n].get("approval", {}).get("reason") == STALE_REASON and was.get(n) != STALE_REASON))]
    if at_risk and (pdir / FILE).exists():
        dest = pdir / "plan_backups" / review.now().replace(":", "-")
        dest.mkdir(parents=True, exist_ok=True)
        (dest / FILE).write_bytes((pdir / FILE).read_bytes())


def ensure(pdir: Path, pid: str) -> dict:
    """The visual plan, created from the analysis when it does not exist and brought in line with it when the analysis changed (only the scenes that changed)."""
    with _lock:
        if not review.review(pdir, pid)["plan_ready"]:
            raise PlanError("the scenes do not exist yet", "plan_missing", 409, "wait for the Audio Analyzer to finish")
        rows = review.scene_rows(pdir)["scenes"]
        plan_scenes = {s.id: s for s in review._plan(pdir).scenes}
        comps = _comp_scenes(pdir)
        data = _read(pdir)
        before = json.dumps(data, sort_keys=True) if data else None
        data = data or {"version": VERSION, "project": pid, "duration": None, "style": None, "scenes": []}
        have = {s.get("number"): s for s in data["scenes"] if isinstance(s, dict)}
        was = {n: (s.get("approval") or {}).get("reason") for n, s in have.items()}      # before the scenes below are changed in place
        analysis = {r["id"]: [_issue(i["severity"], i["message"]) for i in r["issues"]] for r in rows}
        scenes = []
        for i, row in enumerate(rows):
            n = row["id"]
            next_id = scene_id(rows[i + 1]["id"]) if i + 1 < len(rows) else None
            fresh = _derive_scene(pdir, row, plan_scenes.get(n), comps.get(n), next_id)
            old = have.get(n)
            if old is None:
                scenes.append(fresh)
            elif old.get("meta", {}).get("source_hash") == fresh["meta"]["source_hash"]:
                scenes.append(old)
            elif old.get("meta", {}).get("hash_version") != HASH_VERSION:   # made before the hash left the composition out: take the new hash, keep the user's work and approval
                old.setdefault("meta", {}).update(source_hash=fresh["meta"]["source_hash"], hash_version=HASH_VERSION)
                scenes.append(old)
            elif not old.get("meta", {}).get("edited") and (old.get("approval", {}).get("status") in (None, "pending") or old.get("approval", {}).get("auto")):
                fresh["meta"]["revision"] = old.get("meta", {}).get("revision", 0) + 1
                scenes.append(fresh)
            else:                                                       # the user worked on it: keep their work, say that the analysis moved on
                old.setdefault("approval", {}).update(status="needs_edit", reason=STALE_REASON, approved_at=None)
                old.setdefault("meta", {})["source_hash"] = fresh["meta"]["source_hash"]
                scenes.append(old)
        for sc in scenes:        # a scene the user has not touched is judged by the rules: no error = approved, an error = unapproved with the reason
            if not sc.get("meta", {}).get("edited") and (sc.get("approval", {}).get("status") == "pending" or sc.get("approval", {}).get("auto")):
                judge(sc, analysis)
        style = review._plan(pdir).style
        data.update(version=VERSION, project=pid, duration=rows[-1]["end"] if rows else None, style={"suffix": style.suffix, "palette": style.palette}, scenes=scenes)
        if before != json.dumps(data, sort_keys=True):
            _backup_edits(pdir, have, data["scenes"], was)
            review._save(pdir / FILE, data)
        return data


def all_approved(data: dict) -> bool:
    return bool(data.get("scenes")) and all(s.get("approval", {}).get("status") == "approved" for s in data["scenes"])


def approved(pdir: Path, pid: str) -> bool:
    """True when every scene of the visual plan is approved: the condition for the Image & Video stage."""
    try:
        return all_approved(ensure(pdir, pid))
    except PlanError:
        return False


# ---------- validation ----------
def _issue(severity: str, message: str, path: list | None = None) -> dict:
    """One finding. `path` = keys and list indexes down to the exact field in the scene JSON (None: it concerns the scene as a whole)."""
    return {"severity": severity, "message": message, "path": path}


def _time_issues(obj, lo: float, hi: float, where: str, path: list, out: list[dict]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("start", "end", "duration") and _num(v):
                if v < 0:
                    out.append(_issue("error", f"{where} {k}: must not be negative", path + [k]))
                elif k != "duration" and not (lo - EPS <= v <= hi + EPS):
                    out.append(_issue("error", f"{where} {k} {v:g} s: outside the scene ({lo:g}-{hi:g} s)", path + [k]))
            _time_issues(v, lo, hi, f"{where} / {k}", path + [k], out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _time_issues(v, lo, hi, f"{where} / {i + 1}", path + [i], out)


def validate_issues(scene: dict) -> list[dict]:
    """Every error of one scene's planning data, each with the field it is about. No errors = the scene can be saved or approved."""
    out: list[dict] = []
    lo, hi = scene.get("start"), scene.get("end")
    if not (_num(lo) and _num(hi) and lo < hi):
        return [_issue("error", "the scene needs a numeric start before its end", ["start"])]
    if scene.get("approval", {}).get("status") not in STATUSES:
        out.append(_issue("error", f"approval status must be one of {', '.join(STATUSES)}", ["approval", "status"]))
    shots = scene.get("shots")
    if not isinstance(shots, list) or not shots:
        return out + [_issue("error", "the scene needs at least one shot", ["shots"])]
    ids: set[str] = set()
    last_end = lo
    for i, sh in enumerate(shots):
        w = f"shot {sh.get('id')}"
        if not (_num(sh.get("start")) and _num(sh.get("end"))) or sh["start"] >= sh["end"]:
            out.append(_issue("error", f"{w}: start must be before end", ["shots", i, "start"]))
            continue
        if sh["start"] < last_end - EPS:
            out.append(_issue("error", f"{w}: starts at {sh['start']:g} s before the previous shot ends ({last_end:g} s)", ["shots", i, "start"]))
        last_end = sh["end"]
        for j, a in enumerate(sh.get("assets", [])):
            if a.get("type") not in ASSET_TYPES:
                out.append(_issue("error", f"{w}: asset {a.get('id')} type must be one of {', '.join(ASSET_TYPES)}", ["shots", i, "assets", j, "type"]))
    if shots[0]["start"] > lo + EPS:
        out.append(_issue("error", f"the shots must cover the whole scene ({lo:g}-{hi:g} s)", ["shots", 0, "start"]))
    if shots[-1]["end"] < hi - EPS:
        out.append(_issue("error", f"the shots must cover the whole scene ({lo:g}-{hi:g} s)", ["shots", len(shots) - 1, "end"]))
    _time_issues({"shots": shots, "layers": scene.get("layers", []), "motion_graphics": scene.get("motion_graphics", []), "effects": scene.get("effects", [])}, lo, hi, "scene", [], out)

    def walk(o, path):
        if isinstance(o, dict):
            if isinstance(o.get("id"), str):
                if o["id"] in ids:
                    out.append(_issue("error", f"duplicate id {o['id']}", path + ["id"]))
                ids.add(o["id"])
            for k, v in o.items():
                walk(v, path + [k])
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + [i])
    walk({"shots": shots, "layers": scene.get("layers", []), "effects": scene.get("effects", []), "motion_graphics": scene.get("motion_graphics", [])}, [])
    return out


def validate_scene(scene: dict) -> list[str]:
    """The messages of every error of one scene; an empty list means it can be saved or approved."""
    return [i["message"] for i in validate_issues(scene)]


def analysis_issues(pdir: Path) -> dict[int, list[dict]]:
    """The planning-rule findings of the analysis (plan_checks: scene length, patterns, text count, transitions ...) per scene number, with their own severity."""
    return {r["id"]: [_issue(i["severity"], i["message"]) for i in r["issues"]] for r in review.scene_rows(pdir)["scenes"]}


def scene_issues(scene: dict, analysis: dict[int, list[dict]]) -> list[dict]:
    """All findings of one scene, errors first: this scene's own data errors plus the errors and warnings of the planning rules."""
    found = validate_issues(scene) + analysis.get(scene.get("number"), [])
    return sorted(found, key=lambda i: i["severity"] != "error")


def plan_issues(pdir: Path, data: dict) -> dict[str, list[dict]]:
    analysis = analysis_issues(pdir)
    return {s["id"]: scene_issues(s, analysis) for s in data["scenes"]}


def judge(scene: dict, analysis: dict[int, list[dict]]) -> None:
    """Approve a scene that has no error; keep one with an error unapproved and say what has to be fixed. Warnings never block. Changes the scene only when the verdict changed."""
    errors = [i["message"] for i in scene_issues(scene, analysis) if i["severity"] == "error"]
    status, reason = ("needs_edit", "Fix before approval: " + "; ".join(errors[:3])) if errors else ("approved", None)
    ap = scene["approval"]
    if ap.get("status") == status and ap.get("reason") == reason and ap.get("auto"):
        return
    stamp = review.now()
    ap.update(status=status, reason=reason, auto=True, updated_at=stamp, approved_at=None if errors else stamp)


# ---------- edit ----------
def _read_only(path: list) -> bool:
    keys = tuple(p for p in path if isinstance(p, str))
    return any(keys[:len(r)] == r for r in READ_ONLY) or (bool(keys) and keys[-1] in READ_ONLY_LEAVES)


def _apply(scene: dict, changes: list[dict]) -> list[str]:
    done = []
    for ch in changes:
        path, value = ch["path"], ch["value"]
        if not path:
            raise PlanError("a change needs a field path")
        label = " / ".join(str(p) for p in path)
        if len(path) == 3 and path[0] == "layers" and path[2] == "enabled" and isinstance(value, bool):
            # the on/off switch of a layer: a plan made before the switch existed does not have the field yet, so it may be added
            try:
                scene["layers"][path[1]]["enabled"] = value
            except (IndexError, TypeError, KeyError) as e:
                raise PlanError(f"{label} does not exist in this scene", "field_missing") from e
            done.append(label)
            continue
        if _read_only(path):
            raise PlanError(f"{label} cannot be edited here", "field_read_only")
        node = scene
        try:
            for p in path[:-1]:
                node = node[p]
            old = node[path[-1]]
        except (KeyError, IndexError, TypeError) as e:
            raise PlanError(f"{label} does not exist in this scene", "field_missing") from e
        if isinstance(old, (dict, list)):
            raise PlanError(f"{label} is a group of fields: edit its fields", "field_not_editable")
        same = (isinstance(old, str) and isinstance(value, str)) or (isinstance(old, bool) and isinstance(value, bool)) or (_num(old) and _num(value)) or old is None
        if not same:
            raise PlanError(f"{label}: expected a {'number' if _num(old) else type(old).__name__}", "wrong_type")
        node[path[-1]] = value
        done.append(label)
    return done


def _index(data: dict, sid: str) -> int:
    for i, s in enumerate(data["scenes"]):
        if s["id"] == sid:
            return i
    raise PlanError(f"{sid} is not a scene of this project", "scene_not_found", 404)


def _next_id(data: dict, idx: int) -> str | None:
    return data["scenes"][idx + 1]["id"] if idx + 1 < len(data["scenes"]) else None


def save_scene(pdir: Path, pid: str, sid: str, revision: int, changes: list[dict]) -> dict:
    """Apply the edited fields to one scene. Only those fields change; the file keeps every other scene as it was."""
    with _lock:
        data = ensure(pdir, pid)
        idx = _index(data, sid)
        old = data["scenes"][idx]
        if old["meta"]["revision"] != revision:
            raise PlanError("this scene was changed after you opened it", "scene_changed", 409, "reload the scene, then edit again")
        scene = copy.deepcopy(old)
        touched = _apply(scene, changes)
        scene["counts"] = _counts(scene)
        scene["transitions"] = _transitions(scene, _next_id(data, idx))
        problems = validate_scene(scene)
        if problems:
            raise PlanError("; ".join(problems[:6]), "invalid_values")
        scene["meta"].update(revision=old["meta"]["revision"] + 1, edited=True, updated_at=review.now(), edited_paths=sorted(set(old["meta"].get("edited_paths", [])) | set(touched)))
        judge(scene, analysis_issues(pdir))        # checked again right after the edit: approved when it has no error
        data["scenes"][idx] = scene
        review._save(pdir / FILE, data)
        return scene


def set_approval(pdir: Path, pid: str, sid: str, action: str) -> dict:
    with _lock:
        data = ensure(pdir, pid)
        idx = _index(data, sid)
        scene = copy.deepcopy(data["scenes"][idx])
        if action == "approve":
            problems = [i["message"] for i in scene_issues(scene, analysis_issues(pdir)) if i["severity"] == "error"]
            if problems:
                raise PlanError("; ".join(problems[:6]), "invalid_values", 422, "fix the values, then approve")
            scene["approval"].update(status="approved", approved_at=review.now(), updated_at=review.now(), reason=None, auto=False)
        elif action == "reopen":
            scene["approval"].update(status="in_progress", approved_at=None, updated_at=review.now(), reason=None, auto=False)
        else:
            raise PlanError("action must be approve or reopen")
        scene["meta"]["revision"] += 1
        data["scenes"][idx] = scene
        review._save(pdir / FILE, data)
        return scene


# ---------- regenerate one scene ----------
SYSTEM = ("You plan the visual shots of ONE scene of a documentary video from its narration. TEXT ONLY: planning data, never images, never prompts. "
          "Output ONLY one JSON object, no markdown: "
          '{"purpose": str, "shots": [{"start": s, "end": s, "purpose": str, "visual_description": str, "asset_ids": [str], '
          '"camera": {"shot_type": str, "angle": str, "movement": str}, "text": [{"content": str, "position": str, "font_style": str, "animation": str, "start": s}], '
          '"graphics": [{"type": str, "name": str, "animation": str, "start": s, "duration": s}], "transition": {"type": str, "duration": s} or null}], '
          '"layers": [{"type": str, "start": s, "end": s}], "motion_graphics": [{"type": str, "start": s}], "effects": [{"type": str, "start": s, "duration": s}]}. '
          "Times are seconds on the audio timeline: the shots are consecutive and cover the whole scene exactly; every other time lies inside the scene. "
          "Use only the asset ids given; every asset is used by one shot. English only. Max 2 text elements in the scene, key words only. "
          "The last shot carries the transition out of the scene (or null for the last scene).")


def _from_generated(old: dict, gen: dict, next_id: str | None) -> dict:
    sid = old["id"]
    if not isinstance(gen, dict) or not isinstance(gen.get("shots"), list) or not gen["shots"]:
        raise PlanError("the answer had no shots", "generated_plan_invalid", 502)
    assets = {a["id"]: a for sh in old["shots"] for a in sh.get("assets", [])}
    placed: set[str] = set()
    scene = copy.deepcopy(old)
    scene["shots"] = []
    for i, g in enumerate(gen["shots"], 1):
        if not isinstance(g, dict):
            raise PlanError("a shot was not an object", "generated_plan_invalid", 502)
        shot_assets = [assets[a] for a in g.get("asset_ids", []) if a in assets and a not in placed]
        placed |= {a["id"] for a in shot_assets}
        t0 = sum(len(s["text"]) for s in scene["shots"])
        g0 = sum(len(s["graphics"]) for s in scene["shots"])
        tx = [{"id": f"{sid}_text_{t0 + k:02d}", "content": t.get("content"), "mark": None, "position": t.get("position"), "font_style": t.get("font_style"),
               "animation": t.get("animation"), "start": t.get("start")} for k, t in enumerate(g.get("text") or [], 1) if isinstance(t, dict)]
        gr = [{"id": f"{sid}_graphic_{g0 + k:02d}", "type": x.get("type"), "name": x.get("name"), "animation": x.get("animation"),
               "start": x.get("start"), "duration": x.get("duration")} for k, x in enumerate(g.get("graphics") or [], 1) if isinstance(x, dict)]
        tr = g.get("transition") if isinstance(g.get("transition"), dict) else None
        scene["shots"].append({"id": f"{sid}_shot_{i:02d}", "start": g.get("start"), "end": g.get("end"), "purpose": g.get("purpose"), "visual_description": g.get("visual_description"),
                               "assets": shot_assets, "camera": g.get("camera") if isinstance(g.get("camera"), dict) else {}, "text": tx, "graphics": gr,
                               "transition": {"type": tr.get("type"), "duration": tr.get("duration")} if tr else None})
    scene["shots"][0]["assets"] += [a for k, a in assets.items() if k not in placed]       # an asset the answer forgot still belongs to the scene
    scene["purpose"] = gen.get("purpose") if isinstance(gen.get("purpose"), str) and gen["purpose"].strip() else old["purpose"]
    for key, label in (("layers", "layer"), ("motion_graphics", "motion"), ("effects", "effect")):
        scene[key] = [{"id": f"{sid}_{label}_{k:02d}", **{kk: vv for kk, vv in x.items() if kk != "id"}} for k, x in enumerate(gen.get(key) or [], 1) if isinstance(x, dict)]
    scene["transitions"] = _transitions(scene, next_id)
    scene["counts"] = _counts(scene)
    return scene


def regenerate_scene(pdir: Path, pid: str, sid: str, confirm_overwrite: bool = False) -> dict:
    """New planning data for this scene only. Needs a confirmation when it would replace the user's edits or an approval."""
    key = (str(pdir), sid)
    with _lock:
        data = ensure(pdir, pid)
        idx = _index(data, sid)
        old = copy.deepcopy(data["scenes"][idx])
        if (old["meta"].get("edited") or (old["approval"]["status"] == "approved" and not old["approval"].get("auto"))) and not confirm_overwrite:
            raise PlanError("regenerating would replace your edits or the approval of this scene", "confirm_overwrite", 409, "confirm to replace them")
        if key in _regenerating:
            raise PlanError("this scene is being regenerated right now", "regeneration_running", 409)
        _regenerating.add(key)
    try:
        ask = {"scene": {k: old[k] for k in ("id", "start", "end", "duration", "narration_en", "purpose", "concept", "mood", "mode", "pattern", "keywords")},
               "assets": [{k: a.get(k) for k in ("id", "type", "role", "ratio")} for sh in old["shots"] for a in sh.get("assets", [])],
               "current_plan": {k: old[k] for k in ("shots", "layers", "motion_graphics", "effects")}}
        try:
            answer = promptgen.run_claude(json.dumps(ask, ensure_ascii=False, indent=1) + "\n\nPlan the shots of this scene.", system=SYSTEM, timeout=300)
            a, b = answer.find("{"), answer.rfind("}")
            gen = json.loads(answer[a:b + 1]) if a >= 0 and b > a else None
        except GenError as e:
            raise PlanError(str(e), "generation_failed", 502, "retry, or edit the scene by hand") from e
        except ValueError as e:
            raise PlanError(f"the answer was not valid JSON ({e})", "generation_failed", 502, "retry") from e
        with _lock:
            data = ensure(pdir, pid)
            idx = _index(data, sid)
            if data["scenes"][idx]["meta"]["revision"] != old["meta"]["revision"]:
                raise PlanError("this scene was changed while the new plan was written; your version was kept", "scene_changed", 409)
            scene = _from_generated(data["scenes"][idx], gen, _next_id(data, idx))
            problems = validate_scene(scene)
            if problems:
                raise PlanError("the generated plan was not valid: " + "; ".join(problems[:4]), "generated_plan_invalid", 502, "retry")
            scene["meta"].update(revision=old["meta"]["revision"] + 1, source="generated", edited=False, edited_paths=[], updated_at=review.now())
            judge(scene, analysis_issues(pdir))    # a new plan is checked at once: approved when it has no error
            data["scenes"][idx] = scene
            review._save(pdir / FILE, data)
            return scene
    finally:
        _regenerating.discard(key)


# ---------- the user's edits reach the composition ----------
_TEXT = {"content": "text", "mark": "mark", "position": "pos", "font_style": "style", "start": "at", "duration": "dur"}
_ICON = {"name": "lucide", "position": "pos"}
_ICON_ENTER = {"animation": "anim", "start": "at", "duration": "dur"}
_SHAPE = {"name": "kind", "color": "color", "start": "at", "duration": "dur"}
_EFFECT = {"type": "name", "position": "pos", "start": "at", "duration": "dur"}
_COUNTER = {"value": "to", "to": "to", "unit": "unit", "start": "at", "duration": "dur", "position": "pos"}
_CHART = {"data": "data", "kind": "kind", "start": "at", "duration": "dur", "box": "box"}
_CALLOUT = {"kind": "kind", "color": "color", "target": "target", "start": "at", "duration": "dur"}
_CAMERA = {"movement": "move", "zoom_from": "from", "zoom_to": "to"}


def apply_edits(pdir: Path, comp: dict) -> int:
    """Write the fields the user edited in visual_plan.json (text, graphics, effects, camera, transition of a scene) into the composition layers they were derived
    from. Only the edited fields are written, so a scene that was never edited is exactly what the planner made. Returns how many fields were written."""
    data = _read(pdir)
    if not data:
        return 0
    try:
        data = ensure(pdir, pdir.name)           # brings the file in line with the analysis first: an edited scene whose analysis moved on is marked needs_edit (kept, backed up, never overwritten)
    except Exception:                            # no project around it (or the analysis is not ready): the file as it is
        pass
    by_number = {s.get("number"): s for s in data["scenes"]}
    written = 0
    for sc in comp["scenes"]:
        vs = by_number.get(sc["id"])
        if not vs or not vs.get("meta", {}).get("edited") or not vs.get("shots"):
            continue
        if vs.get("approval", {}).get("status") == "needs_edit" and vs["approval"].get("reason") == STALE_REASON:
            continue                             # edits made on an older version of this scene are not written into the scene as it is now
        edited = set(vs["meta"].get("edited_paths", []))
        shot = vs["shots"][0]

        def put(target: dict, key: str, value, *path) -> int:
            if " / ".join(str(p) for p in path) in edited and value is not None:
                target[key] = value
                return 1
            return 0

        texts = [l for l in sc["layers"] if l["type"] == "text"]
        for i, t in enumerate(shot.get("text", [])[:len(texts)]):
            for k, lk in _TEXT.items():
                written += put(texts[i], lk, t.get(k), "shots", 0, "text", i, k)
        graphics = [l for l in sc["layers"] if l["type"] in ("icon", "shape")]
        for i, g in enumerate(shot.get("graphics", [])[:len(graphics)]):
            layer = graphics[i]
            if layer["type"] == "icon":
                for k, lk in _ICON.items():
                    written += put(layer, lk, g.get(k), "shots", 0, "graphics", i, k)
                for k, lk in _ICON_ENTER.items():
                    written += put(layer.setdefault("enter", {}), lk, g.get(k), "shots", 0, "graphics", i, k)
            else:
                for k, lk in _SHAPE.items():
                    written += put(layer, lk, g.get(k), "shots", 0, "graphics", i, k)
        effects = [l for l in sc["layers"] if l["type"] == "effect"]
        for i, e in enumerate(vs.get("effects", [])[:len(effects)]):
            for k, lk in _EFFECT.items():
                written += put(effects[i], lk, e.get(k), "effects", i, k)
        motion_items = vs.get("motion_graphics", [])
        counter_layers = [l for l in sc["layers"] if l["type"] in ("counter", "number counter")]
        chart_layers = [l for l in sc["layers"] if l["type"] in ("chart", "bar chart", "line chart", "pie chart")]
        callout_layers = [l for l in sc["layers"] if l["type"] in ("callout", "callout circle", "callout arrow", "callout box", "callout underline")]
        ci, chi, cai = 0, 0, 0
        for i, m in enumerate(motion_items):
            m_type = str(m.get("type", "")).lower()
            if ("counter" in m_type or "value" in m or "to" in m) and ci < len(counter_layers):
                layer = counter_layers[ci]
                ci += 1
                for k, lk in _COUNTER.items():
                    written += put(layer, lk, m.get(k), "motion_graphics", i, k)
            elif ("chart" in m_type or "data" in m) and chi < len(chart_layers):
                layer = chart_layers[chi]
                chi += 1
                for k, lk in _CHART.items():
                    written += put(layer, lk, m.get(k), "motion_graphics", i, k)
            elif ("callout" in m_type or "target" in m) and cai < len(callout_layers):
                layer = callout_layers[cai]
                cai += 1
                for k, lk in _CALLOUT.items():
                    written += put(layer, lk, m.get(k), "motion_graphics", i, k)
        for i, vl in enumerate(vs.get("layers", [])[:len(sc["layers"])]):
            if f"layers / {i} / enabled" in edited and isinstance(vl.get("enabled"), bool):
                if vl["enabled"]:
                    sc["layers"][i].pop("enabled", None)          # on is the normal state: nothing is written
                else:
                    sc["layers"][i]["enabled"] = False            # off: the layer stays in the composition, the render leaves it out
                written += 1
        cam = shot.get("camera") or {}
        for k, lk in _CAMERA.items():
            written += put(sc.setdefault("camera", {}), lk, cam.get(k), "shots", 0, "camera", k)
        for j, v in enumerate(cam.get("focus") or []):
            focus = sc.setdefault("camera", {}).get("focus")
            if isinstance(focus, list) and j < len(focus):
                written += put(focus, j, v, "shots", 0, "camera", "focus", j)
        out = shot.get("transition") or {}
        if sc.get("transition_out"):
            written += put(sc["transition_out"], "type", out.get("type"), "shots", 0, "transition", "type")
            written += put(sc["transition_out"], "dur", out.get("duration"), "shots", 0, "transition", "duration")
    return written
