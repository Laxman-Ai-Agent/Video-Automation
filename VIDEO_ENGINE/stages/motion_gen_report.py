"""The Motion Generation report (see backend/motion_generation.py for the 13 stages): build it from the composition, persist composition + report, read it back, and say when it blocks the timeline.
Nothing is written by `build`; `finish` writes the composition, reads it back and only then saves the report (a stage is complete only after its output is on disk)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import motion_planning as mp
from .motion_generation import N, SCHEMA, STAGES, VERSION, GenerationError, dumps, names, sha, validate_composition


def fingerprint(pdir: Path, aspect: str) -> str:
    """What this report was made from: the checked plan, the composition on disk and these rules."""
    cname, _, _ = names(aspect)
    plan = mp._read(pdir / mp._names(aspect)[1]) or {}
    comp = (pdir / cname).read_bytes() if (pdir / cname).exists() else b""
    return sha(f"{plan.get('source_fingerprint')}:{plan.get('version')}:{sha(comp)}:{SCHEMA}:{VERSION}")


def build(pdir: Path, aspect: str, comp: dict, determinism: dict | None = None, progress=None, run_tests: bool = True) -> tuple[dict, dict]:
    """The report and the (possibly repaired) composition. `comp` is what build_composition.ts wrote (audio name set). Raises GenerationError when an input is missing."""
    from . import motion_gen_rules as R, store
    t0 = time.perf_counter()
    say = progress or (lambda p: None)
    cname, rname, mname = names(aspect)
    plan = mp.load(pdir, aspect)
    mplan = mp._read(pdir / mname)
    if mplan is None:
        raise GenerationError(f"{mname} is missing: run Motion Planning first")
    reg, run, images = mp.registry(), mp.Run("motion_gen"), store.uses_images(pdir)
    g = R.G(pdir, aspect, comp, plan, mplan, reg, images, run)
    repairs: list[dict] = []
    say(55)
    g.rebuild()
    passes = R.repair(g, repairs)                                                    # stage 12 first: the rules check the repaired composition
    if repairs:
        g.rebuild()
        for d in g.all_desc():
            if any(x["scene"] == d["scene_id"] and x["layer"] in (d["preset_id"], (d["props"] or {}).get("text")) for x in repairs):
                d["repaired"] = True
    say(62)
    check = pdir / ".motion_generation_check.json"
    check.write_text(dumps(g.comp), encoding="utf-8")
    val = validate_composition(check)
    check.unlink(missing_ok=True)
    say(75)
    R.stage1(g)
    R.stage2(g)
    R.stage3(g, val)
    R.stage4(g)
    R.stage5(g)
    R.stage6(g, val)
    R.stage7(g)
    R.stage8(g)
    R.stage9(g)
    R.stage10(g, val)
    tests = {"motion_checks": mp.run_checks(pdir) if run_tests else {"ok": None, "error": "not run"}, "determinism": determinism or {"identical": None, "note": "not run"},
             "renderer": {"zod": val.get("zod") is True, "unknown_layer_types": val.get("unknown", []), "wallclock_files": val.get("wallclock", []), "registered_components": val.get("registered")}}
    ok = tests["motion_checks"]["ok"]
    run.rule("motion_checks", 11, None, ok is False, "error", "motion_checks_failed", f"the motion library's own checks failed: {tests['motion_checks'].get('failed')}")
    run.rule("motion_checks_ran", 11, None, ok is None, "warning", "motion_checks_not_run", f"the motion library's checks could not run: {tests['motion_checks'].get('error')}")
    run.rule("deterministic", 11, None, tests["determinism"]["identical"] is False, "error", "nondeterministic", "a second build of the same plan gave a different composition")
    run.rule("deterministic_ran", 11, None, tests["determinism"]["identical"] is None, "warning", "determinism_not_checked", "the repeat build was not run")
    meta, scenes_c = g.comp["meta"], g.comp["scenes"]
    pics = sum(1 for s in scenes_c for l in s["layers"] if l["type"] == "image")
    run.rule("mode_flags", 13, None, meta.get("motion") != "rich" or bool(meta.get("motionOnly")) != (not images), "error", "mode_mismatch",
             f"the composition says motion={meta.get('motion')}, motionOnly={meta.get('motionOnly')} but Use Images is {'ON' if images else 'OFF'}")
    run.rule("no_pictures_in_motion_only", 13, None, not images and pics > 0, "error", "mode_asset_conflict", f"{pics} picture layer(s) in a Motion-Only composition")
    run.rule("scenes_present", 13, None, not scenes_c, "error", "schema_invalid", "the composition has no scenes")
    say(88)
    by = {t: 0 for t in ("text", "graphic", "shape", "icon")}
    for d in g.all_desc():
        if d["element_type"] in by:
            by[d["element_type"]] += 1
    layers = sum(len(s["layers"]) for s in scenes_c)
    out = {"composition_file": cname, "composition_sha": sha(dumps(g.comp)), "scenes": len(scenes_c), "layers": layers, "texts": by["text"], "graphics": by["graphic"], "shapes": by["shape"],
           "icons": by["icon"], "pictures": pics, "descriptors": len(g.all_desc()), "persisted": False}
    scenes_out = []
    for s in scenes_c:
        sid = g.sid(s)
        scenes_out.append({"scene_id": sid, "plan_scene_id": s["id"], "timing": {"start": s["start"], "end": s["end"], "start_frame": mp.fr(s["start"], g.fps), "end_frame": mp.fr(s["end"], g.fps)},
                           "transition_out": s.get("transition_out"), "descriptors": g.desc[s["id"]],
                           "validation_notes": [{"code": i["code"], "severity": i["severity"], "message": i["message"]} for i in run.items if i["scene"] == sid]})
    what = {1: "inputs", 2: "elements", 3: "ids", 4: "reuse", 5: "descriptors", 6: "engine", 7: "composition", 8: "timing", 9: "layout", 10: "contract", 11: "tests", 12: "repairs", 13: "output"}
    stages = []
    for n in range(1, N + 1):
        its = [i for i in run.items if i["stage"] == n and i["severity"] in ("error", "warning")]
        er = [i for i in its if i["severity"] == "error"]
        if n == 12:
            status = "failed" if run.of("error") else "warning" if repairs else "completed"
            detail = f"{len(run.of('error'))} error(s) could not be repaired safely" if run.of("error") else (f"{len(repairs)} mechanical repair(s) made and recorded" if repairs else "nothing needed repair")
        elif n == 13 and not its:
            status, detail = "completed", f"{layers} layers in {len(scenes_c)} scenes ready for Remotion ({'no pictures' if not images else str(pics) + ' picture slots'})"
        else:
            status = "failed" if er else "warning" if its else "completed"
            done = run.by_stage.get(n, [0, 0])
            detail = (er or its)[0]["message"] if its else (f"{done[0]} of {done[1]} {what[n]} checks passed" if done[1] else f"{what[n]} checked")
        stages.append({"n": n, "name": STAGES[n - 1][0], "status": status, "detail": detail[:240]})
    errors = [i["message"] for i in run.of("error")]
    rep = {"schema_version": SCHEMA, "version": VERSION, "source": "motion_plan",
           "project": {"mode": "image" if images else "motion_only", "aspect_ratio": aspect, "width": g.W, "height": g.H, "fps": g.fps},
           "input": {"file": "motion_planning.json", "plan_version": (plan or {}).get("version"), "plan_fingerprint": (plan or {}).get("source_fingerprint"), "motion_plan_file": mname,
                     "motion_plan_sha": sha((pdir / mname).read_bytes())},
           "scenes": scenes_out, "reuse": g.reuse, "output": out, "stages": stages,
           "validation": {"status": "error" if errors else "warning" if run.of("warning") else "ok", "errors": errors, "warnings": [i["message"] for i in run.of("warning")],
                          "checks": {"passed": sum(c[0] for c in run.counts.values()), "total": sum(c[1] for c in run.counts.values()),
                                     "by_rule": {k: {"passed": v[0], "total": v[1]} for k, v in run.counts.items()},
                                     "by_stage": {str(n): {k: {"passed": v[0], "total": v[1]} for k, v in rs.items()} for n, rs in sorted(run.stage_rules.items())}},
                          "note": "no probability is claimed: the result is the list of checks that passed; a still-frame preview is a separate, manual check"},
           "repairs": repairs, "repair_passes": passes, "tests": tests, "needs_review": bool(errors) or bool(run.of("warning")), "source_fingerprint": "", "timings_seconds": {"build": round(time.perf_counter() - t0, 3)}}
    return rep, g.comp


def finish(pdir: Path, aspect: str, rep: dict, comp: dict) -> dict:
    """Stage 13: write the composition, read it back and compare, then save the report. The stage is complete only after the file is on disk and equal."""
    cname, rname, _ = names(aspect)
    text = dumps(comp)
    f = pdir / cname
    f.write_text(text, encoding="utf-8")
    back = f.read_text(encoding="utf-8")
    same = sha(back) == rep["output"]["composition_sha"] and json.loads(back) == comp
    rep["output"]["persisted"] = same
    if not same:
        rep["validation"]["errors"].append("the composition read back from disk is not what was validated")
        rep["validation"]["status"] = "error"
        rep["stages"][N - 1].update(status="failed", detail="the composition on disk differs from the validated one")
    rep["source_fingerprint"] = fingerprint(pdir, aspect)
    tmp = (pdir / rname).with_suffix(".tmp")
    tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(pdir / rname)
    return rep


def load(pdir: Path, aspect: str) -> dict | None:
    """The stored report with `stale` (made from other inputs than the current ones). None when it has not been made."""
    rep = mp._read(pdir / names(aspect)[1])
    if not rep:
        return None
    try:
        rep["stale"] = rep.get("source_fingerprint") != fingerprint(pdir, aspect) or rep.get("schema_version") != SCHEMA or rep.get("version") != VERSION
    except OSError:
        rep["stale"] = True
    return rep


def blockers(pdir: Path, aspect: str) -> str | None:
    """Why the timeline must not be built from this composition (None = it may). A project without a report (made before this existed) is not blocked."""
    rep = load(pdir, aspect)
    if rep is None:
        return None
    if rep["stale"]:
        return "the Motion Generation report is out of date: run Motion Generation again"
    if rep["validation"]["errors"]:
        return f"Motion Generation has {len(rep['validation']['errors'])} blocking error(s) ({rep['validation']['errors'][0]})"
    return None
