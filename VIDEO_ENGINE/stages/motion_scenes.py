"""The scene logic of Motion Planning (backend/motion_planning.py): stage 2 the Element Resolver, stage 5 the Animation Builder (actions with dependencies) and stage 12 the
repairs. Split from motion_planning.py only to keep each file readable; it has no state of its own."""
from __future__ import annotations

from SYSTEM.core import media_kinds as mk

from .motion_planning import EPS, MIN_DUR, PHASE_RANK, Run, fr, norm


def intensity(importance: float) -> str:
    return "energetic" if importance >= 0.7 else "restrained" if importance <= 0.5 else "moderate"


def resolve(vps: dict | None, m: dict, sid: str, run: Run, assets: dict[str, dict] | None = None, is_custom_code: bool = False) -> tuple[list[dict], dict[int, str], dict[int, str], dict[int, str]]:
    """Stage 2: every Visual Plan element -> what draws it. Returns the elements and the ids to use as the target of each planned text / graphic / icon.
    `assets` = the real media Asset Collection kept for this scene, by element_id."""
    texts = [(i, norm(t["text"])) for i, t in enumerate(m["texts"])]
    classic = [norm(c["text"]) for c in m.get("classic_texts", [])]
    hints = (vps or {}).get("motion_hints", [])
    placed = [(gi, g) for gi, g in enumerate(m["graphics"]) if not g.get("atmosphere")]
    atmos = [g for g in m["graphics"] if g.get("atmosphere")]
    hint_gfx: dict[str, int] = {}
    for gi, g in placed:
        why = g.get("why") or ""
        if why.startswith("hint:"):
            for h in hints:
                if h["intent"] == why[5:] and h.get("element_id") and h["element_id"] not in hint_gfx:
                    hint_gfx[h["element_id"]] = gi
                    break
    carrier = placed[0][1]["preset"] if placed else (m["graphics"][0]["preset"] if m["graphics"] else None)
    dg = m.get("diagram") or {}
    drawn = {d["element_id"]: d for d in dg.get("placed", [])}                      # drawn by VIDEO_ENGINE/remotion/src/motion/diagram.ts (a disc, an icon, a link)
    refused = {d["element_id"]: d["reason"] for d in dg.get("skipped", [])}
    used: set[int] = set()
    text_ids: dict[int, str] = {}
    gfx_ids: dict[int, str] = {gi: eid for eid, gi in hint_gfx.items()}
    icon_ids: dict[int, str] = {}
    out: list[dict] = []
    carried: list[str] = []
    for e in (vps or {}).get("elements", []):
        t, eid, req = e["type"], e["element_id"], bool(e["required"])
        el = {"element_id": eid, "source_element_id": eid, "type": t, "semantic_role": e["role"], "required": req, "registry_id": None, "registry_kind": None,
              "status": "unresolved", "fallback": None, "note": None}
        if mk.is_text(t):
            c = norm(e.get("content") or "")
            idx = next((i for i, n in texts if n == c and i not in used), None)
            if idx is not None:
                used.add(idx)
                text_ids[idx] = eid
                el.update(status="resolved", registry_id=m["texts"][idx]["preset"], registry_kind="text_preset")
            elif is_custom_code:
                el.update(status="resolved", registry_id=eid, registry_kind="custom_code", note="drawn by custom React/TSX text")
            elif c in classic:
                el.update(status="resolved", registry_id="classic_text", registry_kind="layer", note="drawn as a classic text layer")
            else:
                run.rule("text_kept", 2, sid, bool(c), "error" if req else "warning", "required_text_missing",
                         f"{sid}: the on-screen text '{e.get('content')}' of {eid} is not in the motion plan")
        elif t == "background":
            el.update(status="resolved", registry_id=atmos[0]["preset"] if atmos else "scene_background", registry_kind="graphic_preset" if atmos else "layer",
                      note="the atmosphere layer" if atmos else "the scene's own gradient background")
        elif mk.is_real(t):                                             # a real picture / clip: drawn from the file Asset Collection kept, else the motion fallback the plan wrote for it
            a, fb = (assets or {}).get(eid), (e.get("media") or {}).get("fallback") or "a flat motion graphic of the same idea"
            if a:
                el.update(status="resolved", registry_id=a["file"], registry_kind="real_media", note=f"a collected {a['kind']} ({a.get('credit') or 'no credit line'}), drawn by the scene's own code")
            else:
                el.update(status="fallback", fallback={"id": "motion_graphic", "kind": "flat_graphic", "reason": fb})
                run.note(2, "error" if req and (e.get("media") or {}).get("must_be_real") else "info", "media_fallback", sid, f"{sid}: no real {t} was collected for {eid}: the scene draws {fb}")
        elif eid in drawn:
            d = drawn[eid]
            el.update(status=d["status"], registry_id=d["id"], registry_kind="primitive" if ":" in d["id"] else "graphic_preset", note=d["note"])
            if d["status"] == "approximate":
                run.note(2, "info", "element_approximate", sid, f"{sid}: {eid} is drawn as a stand-in: {d['note']}")
        else:                                                           # icon, graphic, diagram, chart, data_visualization, effect
            name = (e.get("registry_requirements") or {}).get("icon")
            ic = next((k for k, i in enumerate(m.get("icons", [])) if name and i.get("name") == name), None)
            if ic is not None:
                icon_ids[ic] = eid
                el.update(status="resolved", registry_id=name, registry_kind="icon")
            elif eid in hint_gfx:
                g = m["graphics"][hint_gfx[eid]]
                el.update(status="resolved", registry_id=g["preset"], registry_kind="graphic_preset", note=f"drawn by {g['preset']} for the hint '{(g.get('why') or '')[5:]}'")
            elif is_custom_code:
                el.update(status="resolved", registry_id=eid, registry_kind="custom_code", note="drawn by custom React/TSX component")
            elif carrier:
                el.update(status="fallback", fallback={"id": carrier, "kind": "graphic_preset", "reason": refused.get(eid) or "the library has no graphic that draws this element on its own"})
                if req:
                    carried.append(eid)
            else:
                el.update(status="unresolved", note="the scene has no graphic to carry it")
                run.note(2, "error" if req else "warning", "no_safe_fallback", sid, f"{sid}: {eid} has no registry id and the scene has no graphic to carry it")
        c2 = run.counts.setdefault("element_drawn", [0, 0])
        c2[1] += 1
        c2[0] += el["status"] in ("resolved", "approximate")
        out.append(el)
    if carried:
        acc = sid in run.accepted
        run.note(2, "info" if acc else "warning", "element_fallback", sid, f"{sid}: {len(carried)} required element(s) ({', '.join(carried[:4])}{'...' if len(carried) > 4 else ''}) are not drawn one by one: the scene is carried by '{carrier}' (the library has no primitive that draws them: " + "; ".join(sorted({refused[c] for c in carried if c in refused})[:1] or ["no diagram graphic"]) + ")" + (" - accepted as a recorded fallback: the element is still NOT drawn" if acc else ""))
    for i, t in enumerate(m["texts"]):                                  # planned text that is not a Visual Plan element: traceable only to the scene plan
        if i not in used:
            text_ids[i] = f"{sid}_text_{i + 1:02d}"
            out.append({"element_id": text_ids[i], "source_element_id": None, "type": "text", "semantic_role": "supporting", "required": False, "registry_id": t["preset"], "registry_kind": "text_preset",
                        "status": "resolved", "fallback": None, "note": "from the scene plan, not a Visual Plan element"})
            run.rule("text_traceable", 2, sid, vps is not None, "warning", "text_not_in_visual_plan", f"{sid}: the text '{t['text']}' is not an element of the Visual Plan")
    for gi, g in enumerate(m["graphics"]):
        if gi not in gfx_ids:
            gfx_ids[gi] = f"{sid}_gfx_{gi + 1:02d}"
            out.append({"element_id": gfx_ids[gi], "source_element_id": None, "type": "effect", "semantic_role": "decorative", "required": False, "registry_id": g["preset"], "registry_kind": "graphic_preset",
                        "status": "resolved", "fallback": None, "note": g.get("why")})
    for k, ic in enumerate(m.get("icons", [])):
        if k not in icon_ids:
            icon_ids[k] = f"{sid}_icon_{k + 1:02d}"
            out.append({"element_id": icon_ids[k], "source_element_id": None, "type": "icon", "semantic_role": "supporting", "required": False, "registry_id": ic.get("name"), "registry_kind": "icon",
                        "status": "resolved", "fallback": None, "note": "from the scene plan"})
    return out, text_ids, gfx_ids, icon_ids


def actions(m: dict, sid: str, fps: int, text_ids: dict, gfx_ids: dict, icon_ids: dict, scene_kw: list[float]) -> list[dict]:
    """Stage 5: the actions of the scene with absolute times and dependencies. depends_on = 'starts no earlier than the start of'; the order is establish -> reveal -> enter -> emphasis -> exit."""
    s0, s1 = m["start"], m["end"]
    acts: list[dict] = []

    def add(aid, target, phase, kind, preset, start, end, why, src, **params):
        acts.append({"action_id": aid, "target": target, "phase": phase, "kind": kind, "preset": preset, "registry": None, "start": round(start, 3), "end": round(end, 3),
                     "start_frame": fr(start, fps), "end_frame": fr(end, fps), "depends_on": [], "timing_source": src, "reason": why, "params": params})
    for gi, g in enumerate(m["graphics"]):
        start = g["start"] if g.get("start") is not None else s0
        end = g["end"] if g.get("end") is not None else s1
        add(f"{sid}_a_gfx_{gi + 1:02d}", gfx_ids[gi], "establish" if g.get("atmosphere") else "reveal", "graphic", g["preset"], start, end,
            g.get("why") or "topic", "plan" if g.get("start") is not None else "scene_interval", speed=g.get("speed", 1), box=g.get("box"), exit_s=g.get("exit_s"))
    for k, ic in enumerate(m.get("icons", [])):
        add(f"{sid}_a_icon_{k + 1:02d}", icon_ids[k], "reveal", "icon", None, ic["at"] if ic.get("at") is not None else s0, s1, "the scene plan's icon",
            "plan" if ic.get("at") is not None else "scene_interval", name=ic.get("name"))
    for ti, t in enumerate(m["texts"]):
        at = t["at"] if t.get("at") is not None else s0
        until = t["until"] if t.get("until") is not None else s1
        enter = t.get("enter_s")
        src = "keyword_time" if any(abs(at - k) < 0.011 for k in scene_kw) else "plan" if t.get("at") is not None else "scene_interval"
        ex = t.get("exit_s") or 0
        tid = text_ids[ti]
        add(f"{sid}_a_text_{ti + 1:02d}_enter", tid, "enter", "text", t["preset"], at, min(until, at + (enter if enter is not None else 0.5)), f"enters with '{t['preset']}' ({t.get('source', 'scene_plan')})", src,
            style=t.get("style"), duration_source="plan" if enter is not None else "estimated", text=t["text"], dir=t.get("dir"), k=t.get("k"))
        if t.get("emphasis") and t.get("emphasis_at"):
            add(f"{sid}_a_text_{ti + 1:02d}_emphasis", tid, "emphasis", "text", t["emphasis"], t["emphasis_at"][0], max(until - ex, t["emphasis_at"][0] + 1 / fps),
                "keyword emphasis from the spoken time until the exit starts", "keyword_time", style=t.get("style"))
        add(f"{sid}_a_text_{ti + 1:02d}_exit", tid, "exit", "text", t.get("exit"), max(at, until - ex), until, (f"leaves with '{t.get('exit')}'" if t.get("until") is not None else "no exit is rendered: the text stays until the scene ends and the transition removes it; this is the latest time the planner lets the reading run"), "scene_interval" if t.get("until") is None else "plan",
            duration_source="plan" if ex else "estimated")
    for d in (m.get("diagram") or {}).get("placed", []):
        if d["layer"] == "motion_scene":                                # a link drawn by a graphic that already has its own action above
            continue
        add(f"{sid}_a_draw_{d['element_id']}", d["element_id"], "reveal", "icon" if d["layer"] == "icon" else "graphic", d["id"], d["at"], s1,
            f"draws {d['element_id']}: {d['note']}", "plan", box=d["box"], status=d["status"])
    for ci, c in enumerate(m.get("classic_texts", [])):
        add(f"{sid}_a_classic_{ci + 1:02d}", f"{sid}_classic_{ci + 1:02d}", "enter", "text", None, c["at"] if c.get("at") is not None else s0, s1, "classic text layer (lower third)",
            "plan" if c.get("at") is not None else "scene_interval", text=c["text"])
    acts.sort(key=lambda a: (PHASE_RANK[a["phase"]], a["start"], a["action_id"]))
    first = next((a for a in acts if a["phase"] in ("establish", "reveal")), None)
    enters = {a["target"]: a for a in acts if a["phase"] == "enter"}
    for a in acts:
        deps: list[str] = []
        if a["phase"] == "reveal" and first and first is not a and first["phase"] == "establish" and a["start"] >= first["start"] - EPS:
            deps = [first["action_id"]]
        elif a["phase"] == "enter" and first and a["start"] >= first["start"] - EPS:
            deps = [first["action_id"]]
        elif a["phase"] in ("emphasis", "exit") and a["target"] in enters:
            deps = [enters[a["target"]]["action_id"]]
        a["depends_on"] = deps
    return acts


def acyclic(acts: list[dict]) -> bool:
    deps = {a["action_id"]: a["depends_on"] for a in acts}
    state: dict[str, int] = {}

    def visit(x: str) -> bool:
        if state.get(x) == 1:
            return False
        if state.get(x) == 2:
            return True
        state[x] = 1
        ok = all(visit(d) for d in deps.get(x, []) if d in deps)
        state[x] = 2
        return ok
    return all(visit(x) for x in deps)


def repair(scenes: list[dict], repairs: list[dict], reg: dict, fps: int) -> None:
    """Stage 12: only mechanical repairs. A time outside the scene is clamped, an end before the start is given the shortest allowed length, an id the registry does not have is replaced by
    a calm one of the same kind. Each repair is recorded (what, from, to, why); anything else stays an error (meaning is never changed)."""
    def rec(sid, aid, field, old, new, why):
        repairs.append({"scene": sid, "action": aid, "field": field, "from": old, "to": new, "reason": why})
    calm = {"text": "cinematic-fade", "exit": "fade-out", "emphasis": "pulse"}
    for s in scenes:
        t0, t1 = s["timing"]["start"], s["timing"]["end"]
        for a in s["sequence"]:
            for f in ("start", "end"):
                v = min(max(a[f], t0), t1)
                if abs(v - a[f]) > 1e-9:
                    rec(s["scene_id"], a["action_id"], f, a[f], round(v, 3), "outside the scene: clamped to the scene interval")
                    a[f] = round(v, 3)
            if a["end"] <= a["start"]:
                new = round(min(a["start"] + MIN_DUR, t1), 3)
                if new > a["start"]:
                    rec(s["scene_id"], a["action_id"], "end", a["end"], new, f"the end was not after the start: given the shortest allowed length ({MIN_DUR} s)")
                    a["end"] = new
            a["start_frame"], a["end_frame"] = fr(a["start"], fps), fr(a["end"], fps)
            if a["end_frame"] <= a["start_frame"]:
                a["end_frame"] = a["start_frame"] + 1
            kind = "graphic" if a["kind"] == "graphic" else "text" if a["phase"] == "enter" else "exit" if a["phase"] == "exit" else "emphasis" if a["phase"] == "emphasis" else None
            if a["preset"] and kind and a["preset"] not in reg[kind] and calm.get(kind) in reg[kind]:
                rec(s["scene_id"], a["action_id"], "preset", a["preset"], calm[kind], f"'{a['preset']}' is not in the registry: replaced by a calm {kind} preset")
                a["preset"] = calm[kind]
        ids: dict[str, int] = {}
        for a in s["sequence"]:
            ids[a["action_id"]] = ids.get(a["action_id"], 0) + 1
            if ids[a["action_id"]] > 1:
                new = f"{a['action_id']}_{ids[a['action_id']]}"
                rec(s["scene_id"], a["action_id"], "action_id", a["action_id"], new, "duplicate action id")
                a["action_id"] = new
