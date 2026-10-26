"""The rules of Visual Planning (stage `planning`): the frame geometry, the safe repairs the code makes on the planner's answer, the deterministic checks, the media mix.
Split from visual_planning.py only to keep each file readable; it has no state of its own. What an element can be comes from SYSTEM/core/media_kinds.py (never a tuple of type names here)."""
from __future__ import annotations

import re

from SYSTEM.core import media_kinds as mk

from . import config

EPS = 0.06
OVERLAP_MIN = 0.02                             # share of the frame two elements may share before they count as overlapping
PATH_REGION = "path_across_frame"
MAX_REAL_PER_SCENE = 6                         # real pictures / clips in one scene: the scene's own limit of 6 elements (clutter) is the only bound, there is no share of the video to reach
RELATIONS = ("connects_to", "flows_from", "compares_with", "labels", "explains", "contains", "follows", "part_of")
# The placement regions and where they are on the frame (x0, y0, x1, y1 as shares of a 16:9 frame). ONE definition: the instructions to the planner, the repair and the checks all read it.
# The margin is the project's safe margin (config.SAFE_AREA, remotion theme.json); the two caption bands are the only edge regions for text; around/over_primary_visual follow their primary.
_M = config.SAFE_AREA["margin"]
REGION_BOX: dict[str, tuple[float, float, float, float] | None] = {
    "center": (0.35, 0.28, 0.65, 0.72), "left": (_M, 0.22, 0.35, 0.78), "right": (0.65, 0.22, 1 - _M, 0.78), "top": (0.10, _M, 0.90, 0.28), "bottom": (_M, 0.68, 1 - _M, 1 - _M),
    "upper_left": (_M, 0.22, 0.35, 0.45), "upper_right": (0.65, 0.22, 1 - _M, 0.45), "lower_left": (_M, 0.55, 0.35, 0.78), "lower_right": (0.65, 0.55, 1 - _M, 0.78),
    "upper_safe_area": (0.10, _M, 0.90, 0.20), "lower_safe_area": (0.10, 0.80, 0.90, 1 - _M), "path_across_frame": (0.10, 0.42, 0.90, 0.58), "full_frame": (0.0, 0.0, 1.0, 1.0),
    "around_primary_visual": None, "over_primary_visual": None}
REGIONS = tuple(REGION_BOX)
EDGE_REGIONS = ("full_frame",)                 # text over the whole frame has no safe area; left/right/top/bottom are placement intents (the layout stage keeps them inside the safe area)
SAFE_AREA_POLICY = ("Text and key graphics stay inside the central 90% of the frame (5% margin on every side). Captions and short text sit in the upper or lower caption band inside that margin "
                    "(in 9:16 above the bottom 16% that phone apps cover) and never over the primary visual; only a background, or a real picture that is the backdrop of the scene, may fill the whole frame.")
PLACEHOLDER = re.compile(r"placeholder|\btbd\b|\btodo\b|lorem ipsum|\bxxx+\b", re.I)    # an unfilled value: a region, an id or an on-screen text that is a template word
BRAND_STEMS = ("youtub", "instagram", "facebook", "whatsapp", "tiktok", "twitter", "chatgpt", "openai", "linkedin", "snapchat", "netflix", "photoshop", "google", "microsoft", "iphone", "samsung")   # a media query names what is visible, never a brand or a word made from one ('youtuber'); only stems that are no ordinary word ('apple', 'zoom', 'canva(s)' are): the LLM review catches the rest
DRAWN_CARRIERS = ("text", "label", "graphic", "diagram", "chart", "data_visualization")    # what says the narration's meaning on top of a real picture or clip
UNFINISHED = re.compile(r"\btbd\b|\btodo\b|lorem ipsum|\bxxx+\b", re.I)                  # a description is prose: it may legitimately say "a photo placeholder inside the phone mockup", it may not be unfinished
TELUGU = re.compile(r"[ఀ-౿]")
FIGURE = re.compile(r"\b(figures?|persons?|people|humans?|astronauts?|crew|explorers?|silhouettes?)\b", re.I)
SINGLE = re.compile(r"\b(lone|single|solitary|alone|sole)\b", re.I)
MOTION_WORDS = re.compile(r"\b(preset|easing|ease[- ]?(in|out)|keyframes?|stagger|frame[- ]by[- ]frame|\d+\s*(ms|fps|frames?))\b", re.I)
SPOKEN = {**{w: n for n, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())},
          "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000, "million": 1000000,
          "ఒకటి": 1, "ఒక్క": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5, "ఆరు": 6, "ఏడు": 7, "ఎనిమిది": 8, "తొమ్మిది": 9, "పది": 10}      # a number said in words is as grounded as the digits
SEMANTIC_LEXICON: list[tuple[set[str], str, str]] = [
    ({"పుడుతోంది", "మొదటి", "సృష్టి", "సృష్టించే", "ప్రారంభం", "ఉదయం", "ignite", "birth", "born", "first", "start", "dawn"}, "ignite_birth", "luminescent core ignition expanding outward with radiance"),
    ({"వేగం", "వేగంగా", "త్వరగా", "క్షణాల్లో", "అందని", "energy", "speed", "velocity", "fast", "faster", "rapid", "accelerate"}, "velocity_pulse", "kinetic streak velocity pulse accelerating along directional vectors"),
    ({"వ్యవస్థ", "వ్యవస్థను", "కలిపే", "నెట్‌వర్క్", "network", "connect", "systems", "connected", "grid", "nodes"}, "network_connect", "interconnected synaptic node pathways bridging visual elements"),
    ({"కొత్త", "ఔషధాలు", "విజ్ఞానం", "మేధస్సు", "శక్తి", "breakthrough", "discovery", "growth"}, "staggered_cascade", "tiered harmonic reveal of complementary visual facets"),
    ({"ప్రమాదం", "మార్చేసే", "తుఫాను", "చీకటి", "danger", "threat", "storm", "darkening", "warning", "risk"}, "danger_alert_pulse", "amber warning focal shift with peripheral tension"),
    ({"ముగింపు", "అంతం", "closing", "disappear", "disappearing", "fade", "dissolve", "end"}, "dissolve_fade", "progressive particulate dispersion and contrast softening"),
    ({"భూమి", "civilization", "ప్రపంచం", "world", "earth", "global"}, "global_orbit", "planetary orbital sweep emphasizing broad systemic scale"),
    ({"super", "బలమైన", "తెలివైన", "expand", "scale", "intelligence"}, "scale_expand", "dimensional scale enlargement reinforcing authoritative dominance")]
CANDIDATES = {"text": ("lower_safe_area", "upper_safe_area"), "icon": ("upper_right", "upper_left", "lower_right", "lower_left"),
              "other": ("center", "left", "right", "lower_left", "lower_right", "upper_left", "upper_right")}
TEXT_SLOTS = {"quote_type": 2}                 # how many on-screen texts a scene pattern of src/patterns/index.ts draws: every pattern draws ONE (params.text), quote_type two (text, text2)
DEFAULT_TEXT_SLOTS = 1
LINKED = ("connects_to", "flows_from", "follows", "part_of", "contains")        # related elements may share an area (a path and the places it joins, a part and its whole)


class Issues:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, stage: int, severity: str, code: str, scene: str | None, message: str) -> bool:
        self.items.append({"stage": stage, "severity": severity, "code": code, "scene": scene, "message": message})
        return True

    def of(self, severity: str) -> list[dict]:
        return [i for i in self.items if i["severity"] == severity]


def text_slots(pattern: str) -> int:
    return TEXT_SLOTS.get(pattern, DEFAULT_TEXT_SLOTS)


def scene_id(n: int) -> str:
    return f"scene_{n:02d}"                       # the id convention of visual_plan.py (scene_01)


def words(s: str) -> list[str]:
    return [w for w in re.findall(r"[\w']+", s.lower(), flags=re.UNICODE) if len(w) > 2 or w.isdigit()]


# ---------- geometry ----------
def region_box(region: str, aspect: str = "16:9") -> tuple[float, float, float, float] | None:
    """Where a region is on the frame of this aspect (None for the regions that follow their primary element). In 9:16 the bottom 16% is covered by phone apps and the caption band sits above it."""
    b = REGION_BOX.get(region)
    if b is None or region == "full_frame" or aspect != "9:16":
        return b
    c = config.SAFE_AREA
    ui = 1 - c["portrait_ui_bottom"]
    if region == "lower_safe_area":
        return (b[0], 1 - c["portrait_caption_bottom"] - (b[3] - b[1]), b[2], 1 - c["portrait_caption_bottom"])
    if region == "upper_safe_area":
        return (b[0], c["portrait_label_top"], b[2], c["portrait_label_top"] + (b[3] - b[1]))
    return (b[0], min(b[1], ui), b[2], min(b[3], ui))


def overlap(a: tuple, b: tuple) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def foreground(e: dict) -> bool:
    """A backdrop is not in the way of anything: a background, an environment / decoration element, and a real picture that fills the whole frame."""
    backdrop = e["type"] == "background" or e["role"] in ("environment", "decoration") or (mk.is_real(e["type"]) and e["placement"]["region"] == "full_frame")
    return not backdrop


def free_region(e: dict, elements: list[dict], aspect: str) -> str:
    """The supported region that fits this element best: of the regions its kind may use, the one that shares the least area with the other foreground elements (the first on a tie)."""
    kind = "text" if mk.is_text(e["type"]) else "icon" if e["type"] == "icon" else "other"
    taken = [b for o in elements if o is not e and foreground(o) and (b := region_box(o["placement"]["region"], aspect))]
    return min(CANDIDATES[kind], key=lambda r: sum(overlap(region_box(r, aspect), b) for b in taken))


def clashes(els: list[dict], rels: list[dict], aspect: str = "16:9") -> list[tuple[dict, dict]]:
    """Pairs of foreground elements that share an area of the frame. Not a clash: a backdrop, a region that follows its primary, an element that travels along the path region, and two
    elements that are joined by a path / part-of relation. A text over the primary visual is a clash like any other."""
    fg = [e for e in els if foreground(e) and e["placement"]["avoid_overlap"] and e["placement"]["region"] != "full_frame"]
    linked = {frozenset((r["source"], r["target"])) for r in rels if r["relation"] in LINKED}
    on_path = lambda e: e["placement"]["region"] == PATH_REGION and not mk.is_text(e["type"])
    out = []
    for x, a in enumerate(fg):
        for b in fg[x + 1:]:
            ba, bb = region_box(a["placement"]["region"], aspect), region_box(b["placement"]["region"], aspect)
            if ba and bb and overlap(ba, bb) > OVERLAP_MIN and not (on_path(a) or on_path(b)) and frozenset((a["element_id"], b["element_id"])) not in linked:
                out.append((a, b))
    return out


def path_joins(rels: list[dict], eid: str) -> set[str]:
    """The elements a path element joins (connects_to / flows_from relationships)."""
    return {y for r in rels if r["relation"] in ("connects_to", "flows_from") and eid in (r["source"], r["target"]) for y in (r["source"], r["target"])} - {eid}


# ---------- the planner's times snap to spoken words ----------
def _spoken(nar: dict, ws: list) -> list:
    a, b = nar["start_seconds"], nar["end_seconds"]
    return [w for w in ws if a - EPS <= (w.start + w.end) / 2 <= b + EPS]


def snap_beats(beats: list[dict], nar: dict, ws: list, sid: str, iss: Issues) -> list[dict]:
    """A visual moment starts and ends on a spoken word. A beat inside its scene is moved to the nearest word start / end and the move is noted; a beat that is not inside its scene is left
    as it is (it is an error, never hidden by moving it)."""
    a, b = nar["start_seconds"], nar["end_seconds"]
    spoken = _spoken(nar, ws)
    if not spoken:
        return beats
    starts, ends = [a, *[w.start for w in spoken]], [b, *[w.end for w in spoken]]
    for x in beats:
        if not (a - 0.0005 <= x["start_seconds"] < x["end_seconds"] <= b + 0.0005):
            continue
        s, e = min(starts, key=lambda t: abs(t - x["start_seconds"])), min(ends, key=lambda t: abs(t - x["end_seconds"]))
        if (abs(s - x["start_seconds"]) > EPS or abs(e - x["end_seconds"]) > EPS) and s < e:
            iss.add(8, "info", "beat_snapped", sid, f"beat {x['beat_id']} moved from {x['start_seconds']:g}-{x['end_seconds']:g} s to {s:g}-{e:g} s to start and end on spoken words")
            x["start_seconds"], x["end_seconds"] = s, e
    return beats


def snap_word_events(events: list[dict], nar: dict, ws: list, sid: str, iss: Issues) -> list[dict]:
    """Word animation events start and end on the spoken words of the transcript."""
    a, b = nar["start_seconds"], nar["end_seconds"]
    spoken = _spoken(nar, ws)
    if not spoken:
        return events
    starts, ends = [a, *[w.start for w in spoken]], [b, *[w.end for w in spoken]]
    for x in events:
        if not (a - 0.0005 <= x["start_seconds"] < x["end_seconds"] <= b + 0.0005):
            x["start_seconds"] = max(a, min(b - EPS, x["start_seconds"]))
            x["end_seconds"] = max(x["start_seconds"] + 0.1, min(b, x["end_seconds"]))
        s, e = min(starts, key=lambda t: abs(t - x["start_seconds"])), min(ends, key=lambda t: abs(t - x["end_seconds"]))
        if (abs(s - x["start_seconds"]) > EPS or abs(e - x["end_seconds"]) > EPS) and s < e:
            iss.add(8, "info", "word_event_snapped", sid, f"word animation event {x['event_id']} snapped to spoken words {s:g}-{e:g}s")
            x["start_seconds"], x["end_seconds"] = round(s, 3), round(e, 3)
    return events


# ---------- repairs: each is recorded, nothing the planner meant is deleted silently, a required element is never dropped ----------
def _repair_media(sc: dict, ctx: dict, sid: str, iss: Issues) -> None:
    opts = ctx["opts"]
    for e in sc["elements"]:
        if not mk.is_real(e["type"]):
            e["media"] = None
            continue
        m = e["media"]
        m["alt_queries"] = [q for q in dict.fromkeys(m["alt_queries"]) if q != m["query"]][:2]
        if e["type"] == "image" and opts["ai_images"]:
            if not (m.get("ai_prompt") or "").strip():
                m["ai_prompt"] = f"{e['visual_description'].rstrip('. ')}. {ctx['plan'].style.suffix}".strip()
                iss.add(5, "info", "ai_prompt_derived", sid, f"{e['element_id']} had no AI prompt: written from its description and the project style")
        else:
            m["ai_prompt"] = None


def repair(sc: dict, ctx: dict, sid: str, iss: Issues) -> dict:
    """Safe repairs of one scene."""
    for e in sc["elements"]:                                      # layout: a region that is not a supported one (or is a placeholder) is replaced by the free region that fits the element
        r = e["placement"]["region"]
        if r not in REGION_BOX or PLACEHOLDER.search(r):
            e["placement"]["region"] = free_region(e, sc["elements"], ctx["aspect"])
            iss.add(3, "warning", "region_replaced", sid, f"{e['element_id']} had the unsupported placement region '{r}': placed in '{e['placement']['region']}' instead (the free region that fits a {e['type']})")
    _repair_media(sc, ctx, sid, iss)
    have = {e["element_id"] for e in sc["elements"]}
    good = []
    for r in sc["element_relationships"]:
        if r["source"] in have and r["target"] in have and r["source"] != r["target"]:
            good.append(r)
        else:
            iss.add(4, "warning", "relationship_removed", sid, f"relationship {r['source']} {r['relation']} {r['target']} named an element that does not exist (or itself): removed; no element was deleted")
    sc["element_relationships"] = good
    on_path = [e for e in sc["elements"] if e["placement"]["region"] == PATH_REGION and not mk.is_text(e["type"])]
    if not any(e["type"] not in ("graphic", "diagram") for e in on_path):          # nothing travels along it: a graphic there that joins fewer than two elements is a misplaced graphic, not a path
        for e in on_path:
            if len(path_joins(good, e["element_id"])) < 2:
                e["placement"]["region"] = free_region(e, sc["elements"], ctx["aspect"])
                iss.add(3, "info", "path_region_replaced", sid, f"{e['element_id']} was placed in the path region but joins fewer than two elements, so it is not a path: placed in '{e['placement']['region']}' instead")
    for e in sc["elements"]:                                      # a concrete icon id must exist, else a search descriptor for the downstream resolver
        reg = e.get("registry_requirements")
        if reg and reg.get("icon"):
            if ctx["icons"] is None:
                reg["resolved"] = None
            elif ctx["pascal"](reg["icon"]) in ctx["icons"]:
                reg["resolved"] = True
            else:
                iss.add(3, "warning", "icon_unknown", sid, f"icon '{reg['icon']}' of {e['element_id']} is not in the installed icon registry: kept as a search descriptor")
                reg["search_descriptors"] = list(dict.fromkeys([*reg.get("search_descriptors", []), reg["icon"].replace("-", " ")]))
                reg["icon"], reg["resolved"] = None, False
    for h in sc["motion_hints"]:
        if MOTION_WORDS.search(f"{h['intent']} {h.get('description') or ''}"):
            iss.add(5, "warning", "motion_detail", sid, f"motion hint '{h['intent']}' described presets, easing or timing: that belongs to Motion Planning, the description was dropped")
            h["description"] = None
    sc["motion_hints"] = [h for h in sc["motion_hints"] if not (h.get("element_id") and h["element_id"] not in have and iss.add(5, "warning", "motion_hint_element", sid, f"motion hint '{h['intent']}' named the unknown element {h['element_id']}: dropped"))]
    for b in sc.get("beats", []):
        bad = [x for x in b["element_ids"] if x not in have]
        if bad:
            iss.add(4, "warning", "beat_element", sid, f"beat {b['beat_id']} named unknown elements {bad}: removed from the beat")
            b["element_ids"] = [x for x in b["element_ids"] if x in have]
    for e in sc["elements"]:
        if not e.get("depth_layer"):
            e["depth_layer"] = "background" if e["type"] == "background" or e["role"] in ("environment", "decoration") else "foreground" if e["role"] == "primary" or mk.is_text(e["type"]) else "midground"
    prim = next((e["element_id"] for e in sc["elements"] if e["role"] == "primary"), sc["elements"][0]["element_id"] if sc["elements"] else None)
    events = []
    for we in sc.get("word_animation_events", []):
        if we.get("target_element_id") not in have:
            if not prim:
                continue
            iss.add(4, "info", "word_event_target_repaired", sid, f"word animation event '{we['event_id']}' targeted unknown element '{we.get('target_element_id')}': reassigned to primary visual '{prim}'")
            we["target_element_id"] = prim
        events.append(we)
    sc["word_animation_events"] = events or _derive_word_events(sc, ctx, prim)
    return sc


def _derive_word_events(sc: dict, ctx: dict, prim: str | None) -> list[dict]:
    """The planner gave no word animation event: up to four of the scene's own spoken words with a matching meaning (else its first, middle and last word), aimed at the primary element."""
    ps = next((s for s in ctx["plan"].scenes if s.id == sc.get("plan_scene_id")), None)
    if not prim or ps is None:
        return []
    spoken = [w for w in ctx["words"] if ps.start - EPS <= (w.start + w.end) / 2 <= ps.end + EPS]
    out: list[dict] = []
    seen: set[str] = set()
    for w in spoken:
        cleaned = w.w.strip(",.!? \t\n")
        for keywords, intent, treatment in SEMANTIC_LEXICON:
            if (cleaned in keywords or cleaned.lower() in keywords) and cleaned not in seen and len(out) < 4:
                seen.add(cleaned)
                out.append({"event_id": f"we_s{ps.id}_{len(out) + 1}", "word": w.w, "start_seconds": round(w.start, 3), "end_seconds": round(w.end, 3), "target_element_id": prim,
                            "semantic_intent": intent, "visual_treatment": treatment, "intensity": 1.0})
                break
    if not out and spoken:
        intents = ["ignite_birth", "scale_expand", "staggered_cascade"]
        for k, i in enumerate(sorted({0, len(spoken) // 2, len(spoken) - 1})):
            w = spoken[i]
            out.append({"event_id": f"we_s{ps.id}_{k + 1}", "word": w.w, "start_seconds": round(w.start, 3), "end_seconds": round(w.end, 3), "target_element_id": prim,
                        "semantic_intent": intents[min(k, 2)], "visual_treatment": f"dynamic semantic emphasis on spoken term '{w.w}'", "intensity": 1.0})
    return out


# ---------- the media mix ----------
def counts(elements: list[dict]) -> dict[str, int]:
    """How many elements of every group (text, icon, graphic, background, image, video) a scene has: what the page shows."""
    out = dict.fromkeys(mk.GROUPS, 0)
    for e in elements:
        out[mk.group_of(e["type"])] += 1
    return out


def hero(elements: list[dict]) -> str:
    """The family of the scene's primary element: what the viewer looks at first (motion when it has none)."""
    p = next((e for e in elements if e["role"] == "primary"), None)
    return mk.family_of(p["type"]) if p else "motion"


def media_mix(plan: dict, opts: dict) -> dict:
    """What the plan really carries, by the time each scene holds on the timeline (information only: media is unlimited, there is no share to reach)."""
    secs = dict.fromkeys(mk.FAMILIES, 0.0)
    by_family: dict[str, list[str]] = {f: [] for f in mk.FAMILIES}
    for s in plan["scenes"]:
        m = s["source_mapping"]
        secs[s["hero"]] += max(0.0, m["timeline_end"] - m["timeline_start"])
        by_family[s["hero"]].append(s["scene_id"])
    total = sum(secs.values())
    actual = {f: round(100 * secs[f] / total) if total else 0 for f in mk.FAMILIES}
    if total:
        actual["motion"] += 100 - sum(actual.values())            # rounding goes to motion so the three add up to 100
    return {"actual": actual, "scenes": by_family, "ai_images": opts["ai_images"],
            "note": "every scene is motion graphics; the shares above are the time in which the primary element is drawn, a real picture or a real clip (no share is asked for)"}


# ---------- deterministic checks ----------
def check(plan: dict, ctx: dict, iss: Issues, llm: bool) -> dict:
    """Deterministic validation. Returns {rule: [passed, total]}; an error blocks the plan, a warning does not."""
    counts_: dict[str, list[int]] = {}

    def rule(name: str, scene: str | None, bad: bool, stage: int, severity: str, code: str, message: str) -> None:
        c = counts_.setdefault(name, [0, 0])
        c[1] += 1
        if bad:
            iss.add(stage, severity, code, scene, message)
        else:
            c[0] += 1

    src = ctx["plan"].scenes
    canon = ctx["canonical"]
    rule("scene_count", None, len(plan["scenes"]) != len(src), 8, "error", "scene_count", f"the plan has {len(plan['scenes'])} scenes, the scene plan {len(src)}")
    if canon:                                                      # the planned scenes against the canonical ones (Scene Segmentation): count, start, end, gaps, no conflicting intervals
        found = ctx["mapping_errors"](src, ctx["seg"])
        rule("source_scene_count", None, any(e["code"] in ("source_scene_count", "source_extra_scene", "source_missing_scene") for e in found), 8, "error", "source_scene_count",
             next((e["message"] for e in found if e["code"] == "source_scene_count"), "a scene has no counterpart in Scene Segmentation"))
        for e in found:
            if e["code"] in ("source_extra_scene", "source_missing_scene"):
                iss.add(8, "error", e["code"], e["scene"], e["message"])
        for ps in src[:len(canon)]:
            for code in ("source_start", "source_end"):
                bad = next((e for e in found if e["scene"] == scene_id(ps.id) and e["code"] == code), None)
                rule(code, scene_id(ps.id), bad is not None, 8, "error", code, bad["message"] if bad else "")
        ids = [s["source_mapping"]["segmentation_scene_id"] for s in plan["scenes"] if s["source_mapping"]["segmentation_scene_id"]]
        rule("source_mapping_unique", None, len(ids) != len(set(ids)), 8, "error", "source_mapping_duplicate", "two planned scenes map to the same Scene Segmentation scene")
    for i in range(1, min(len(plan["scenes"]), len(canon))):
        a, b = plan["scenes"][i - 1]["narration"], plan["scenes"][i]["narration"]
        sid = plan["scenes"][i]["scene_id"]
        rule("gaps_preserved", sid, abs((b["start_seconds"] - a["end_seconds"]) - (canon[i]["start"] - canon[i - 1]["end"])) > 0.0005, 8, "error", "gap_changed",
             f"{sid}: the pause before the scene is {b['start_seconds'] - a['end_seconds']:.3f} s but Scene Segmentation has {canon[i]['start'] - canon[i - 1]['end']:.3f} s")
        rule("no_conflicting_intervals", sid, b["start_seconds"] < a["end_seconds"] - 0.0005, 8, "error", "interval_conflict", f"{sid} starts before the scene before it ends")
    for i, s in enumerate(plan["scenes"][:len(canon)]):            # the canonical interval of each scene, its pause and the interval it holds on the timeline (the pause is stored apart, never inside the scene)
        m, c, sid = s["source_mapping"], canon[i], s["scene_id"]
        nxt = canon[i + 1]["start"] if i + 1 < len(canon) else None
        rule("plan_interval", sid, abs(m["plan_start"] - c["start"]) > 0.0005 or abs(m["plan_end"] - c["end"]) > 0.0005, 8, "error", "plan_interval",
             f"{sid}: plan_start/plan_end {m['plan_start']:g}-{m['plan_end']:g} s are not the canonical {c['start']:g}-{c['end']:g} s of {c['id']} (the pause after a scene is not part of it)")
        gap = None if nxt is None else round(nxt - c["end"], 3)
        rule("gap_after", sid, (m["gap_after_seconds"] is None) != (gap is None) or (gap is not None and abs(m["gap_after_seconds"] - gap) > 0.0015), 8, "error", "gap_after_seconds",
             f"{sid}: gap_after_seconds is {m['gap_after_seconds']} but Scene Segmentation has {gap} s between {c['id']} and the next scene")
        held = (m["timeline_end"] >= m["plan_end"] - EPS) if nxt is None else abs(m["timeline_end"] - nxt) <= EPS
        rule("timeline_interval", sid, not held or m["timeline_start"] > m["plan_start"] + EPS, 8, "error", "timeline_interval",
             f"{sid}: the timeline interval {m['timeline_start']:g}-{m['timeline_end']:g} s is not the canonical scene plus the pause up to the next scene ({nxt if nxt is not None else 'audio end'})")
        if i:
            rule("no_overlapping_timeline", sid, m["timeline_start"] < plan["scenes"][i - 1]["source_mapping"]["timeline_end"] - EPS, 8, "error", "timeline_overlap",
                 f"{sid}: its timeline interval starts before the scene before it ends")
    alltext = " ".join(s["narration"]["text"] + " " + (s["narration"].get("text_en") or "") for s in plan["scenes"])
    digits = set(re.findall(r"\d+(?:[.,]\d+)?", alltext)) | {str(v) for w in words(alltext) for v in [SPOKEN.get(w)] if v is not None}    # "eight" / ఎనిమిది = 8
    for s in src:                                                                                    # numbers the scene plan itself was checked for (plan_checks): the planner may repeat them
        digits |= set(re.findall(r"\d+(?:[.,]\d+)?", f"{s.params.text or ''} {s.params.text2 or ''} {s.params.number if s.params.number is not None else ''} {' '.join(str(d.value) for d in (s.params.data or []))}"))
    allow: set[str] = set()
    for s in src:
        allow |= set(words(f"{s.meaning} {s.concept} {s.params.text or ''} {s.params.text2 or ''} {' '.join(k.text for k in s.keywords)} {' '.join(s.params.labels or [])} {s.params.region or ''}"))
    pal = {c.lower() for c in plan["visual_style"]["palette"]}
    for i, (s, ps) in enumerate(zip(plan["scenes"], src)):
        sid, els = s["scene_id"], s["elements"]
        ids = [e["element_id"] for e in els]
        texts = [e for e in els if mk.is_text(e["type"])]
        real = [e for e in els if mk.is_real(e["type"])]
        rule("element_ids_unique", sid, len(ids) != len(set(ids)), 3, "error", "element_id_duplicate", f"element ids repeat in {sid}: {sorted({x for x in ids if ids.count(x) > 1})}")
        rule("primary_element", sid, not any(e["role"] == "primary" for e in els), 4, "error", "no_primary", f"{sid} has no primary element")
        rule("required_element", sid, not any(e["required"] for e in els), 3, "warning", "no_required", f"{sid} has no required element")
        rule("element_count", sid, len(els) > 6, 3, "warning", "cluttered", f"{sid} has {len(els)} elements: clutter")
        slots = text_slots(ps.pattern)
        rule("text_capacity", sid, len(texts) > slots, 6, "error", "text_capacity",
             f"{sid} has {len(texts)} on-screen text elements ({', '.join(e['element_id'] for e in texts)}) but its pattern '{ps.pattern}' draws {slots}: keep the {slots} most important and put the other words into the description of the graphic they belong to")
        prim = [e["placement"]["priority"] for e in els if e["role"] == "primary"]
        rule("hierarchy", sid, bool(prim) and any(e["placement"]["priority"] < min(prim) for e in els if e["role"] != "primary"), 4, "warning", "hierarchy", f"{sid}: a supporting element has a higher priority than the primary one")
        odd = sorted({e["placement"]["region"] for e in els if e["placement"]["region"] not in REGIONS})
        rule("regions", sid, bool(odd), 3, "error", "region_unknown", f"{sid}: placement regions {odd} are not supported regions")
        rule("no_placeholders", sid, any(PLACEHOLDER.search(f"{e['placement']['region']} {e['element_id']} {e.get('content') or ''}") or UNFINISHED.search(e["visual_description"]) for e in els), 3, "error", "placeholder",
             f"{sid}: an element still holds a placeholder value (placement, id, text or description)")
        rule("text_safe_area", sid, any(e["placement"]["region"] in EDGE_REGIONS for e in texts), 6, "warning", "text_outside_safe_area", f"{sid}: text is placed over the whole frame instead of a safe area")
        clash = clashes(els, s["element_relationships"], ctx["aspect"])
        over = [(a, b) for a, b in clash if mk.is_text(a["type"]) != mk.is_text(b["type"]) and "primary" in (a["role"], b["role"])]
        rule("text_over_primary", sid, bool(over), 6, "warning", "text_over_primary", f"{sid}: the text {next((x for p in over for x in p if mk.is_text(x['type'])), {}).get('element_id')} shares its area of the frame with the primary visual")
        rule("layout_overlap", sid, bool(clash), 4, "warning", "layout_overlap", f"{sid}: {', '.join(f'{a['element_id']} / {b['element_id']}' for a, b in clash[:3])} share an area of the frame")
        have = set(ids)
        bad_ref = [r for r in s["element_relationships"] if r["source"] not in have or r["target"] not in have] + [h for h in s["motion_hints"] if h.get("element_id") and h["element_id"] not in have] \
            + [b for b in s.get("beats", []) if set(b["element_ids"]) - have]
        rule("references_valid", sid, bool(bad_ref), 4, "error", "reference_invalid", f"{sid}: a relationship, motion hint or beat names an element that the scene does not have")
        on_path = [e for e in els if e["placement"]["region"] == PATH_REGION and not mk.is_text(e["type"])]                  # a path is drawn (graphic/diagram); what travels along it is something else
        paths = [e for e in on_path if e["type"] in ("graphic", "diagram")]
        movers = [e for e in on_path if e["type"] not in ("graphic", "diagram")]
        rule("path_element", sid, bool(movers) and not paths, 4, "warning", "moving_without_path", f"{sid}: {movers[0]['element_id'] if movers else ''} travels across the frame but the scene has no path element to travel along")
        for p in paths:
            joined = path_joins(s["element_relationships"], p["element_id"])
            rule("path_connected", sid, len(joined) < 2, 4, "warning", "path_not_connected", f"{sid}: the path {p['element_id']} joins {len(joined)} element(s): a path connects at least two places")
        for mv in movers:
            rule("mover_on_path", sid, bool(paths) and not any({r["source"], r["target"]} == {mv["element_id"], p["element_id"]} for p in paths for r in s["element_relationships"]), 4, "warning",
                 "mover_not_on_path", f"{sid}: {mv['element_id']} is not related (follows) to the path it moves along")
        vc = s["visual_concept"]
        figs = [e["element_id"] for e in els if foreground(e) and e["type"] in ("icon", "graphic", "diagram") and FIGURE.search(f"{e['element_id']} {' '.join(e['visual_description'].split()[:5])}".replace("_", " "))]
        rule("concept_consistent", sid, bool(SINGLE.search(f"{vc['description']} {vc['primary_focus']}")) and len(figs) > 1, 4, "warning", "concept_elements_disagree",
             f"{sid}: the concept speaks of ONE figure but {len(figs)} elements show figures ({', '.join(figs)}): the concept and the elements must describe the same picture")
        n = s["narration"]
        c = canon[i] if i < len(canon) else None
        want = (c["start"], c["end"]) if c else (ps.start, ps.end)                          # the canonical times when Scene Segmentation exists: exactly (its own rounding), else the scene plan
        limit = (ctx["seg"] or {}).get("audio_duration_seconds")
        rule("timing", sid, not (0 <= n["start_seconds"] < n["end_seconds"]) or abs(n["start_seconds"] - want[0]) > 0.0005 or abs(n["end_seconds"] - want[1]) > 0.0005
             or (limit is not None and n["end_seconds"] > limit + EPS), 6, "error", "timing", f"{sid}: the times {n['start_seconds']:g}-{n['end_seconds']:g} s differ from the source {want[0]:g}-{want[1]:g} s")
        for b in s.get("beats", []):
            inside = n["start_seconds"] - 0.0005 <= b["start_seconds"] < b["end_seconds"] <= n["end_seconds"] + 0.0005
            rule("beats_inside_parent", sid, not inside, 8, "error", "beat_outside_scene", f"{sid}: beat {b['beat_id']} ({b['start_seconds']:g}-{b['end_seconds']:g} s) is not inside its scene ({n['start_seconds']:g}-{n['end_seconds']:g} s)")
        for we in s.get("word_animation_events", []):
            inside = n["start_seconds"] - 0.0005 <= we["start_seconds"] < we["end_seconds"] <= n["end_seconds"] + 0.0005
            rule("word_events_inside_scene", sid, not inside, 8, "error", "word_event_outside_scene",
                 f"{sid}: word animation event {we['event_id']} ({we['start_seconds']:g}-{we['end_seconds']:g} s) is outside scene ({n['start_seconds']:g}-{n['end_seconds']:g} s)")
            rule("word_events_target_valid", sid, we["target_element_id"] not in have, 8, "error", "word_event_target_invalid", f"{sid}: word animation event {we['event_id']} targets unknown element '{we['target_element_id']}'")
        bt = s.get("beats", [])
        spoken = [w for w in ctx["words"] if n["start_seconds"] - EPS <= (w.start + w.end) / 2 <= n["end_seconds"] + EPS]
        for b in bt if spoken else []:                              # a visual moment starts and ends with a spoken word (cut points snap to word boundaries)
            ok = (any(abs(b["start_seconds"] - w.start) <= EPS for w in spoken) or abs(b["start_seconds"] - n["start_seconds"]) <= EPS) \
                and (any(abs(b["end_seconds"] - w.end) <= EPS for w in spoken) or abs(b["end_seconds"] - n["end_seconds"]) <= EPS)
            rule("beats_on_words", sid, not ok, 8, "warning", "beat_off_word", f"{sid}: beat {b['beat_id']} ({b['start_seconds']:g}-{b['end_seconds']:g} s) does not start and end on spoken words")
        rule("beats_ordered", sid, any(y["start_seconds"] < x["start_seconds"] for x, y in zip(bt, bt[1:])) or len({b["beat_id"] for b in bt}) != len(bt), 8, "error", "beats_order", f"{sid}: the beats are not in order or repeat an id")
        rule("ordered", sid, i > 0 and n["start_seconds"] < plan["scenes"][i - 1]["narration"]["start_seconds"] - EPS, 6, "error", "order", f"{sid} starts before the scene before it")
        rule("narration_present", sid, not n["text"].strip(), 6, "warning", "narration_empty", f"{sid} has no narration text from the source")
        rule("real_media_count", sid, len(real) > MAX_REAL_PER_SCENE, 5, "warning", "too_many_real", f"{sid} has {len(real)} real pictures or clips (at most {MAX_REAL_PER_SCENE})")
        for e in real:
            q = e["media"]["query"]
            rule("media_query_english", sid, bool(TELUGU.search(q)) or len(q.split()) > 8, 5, "error", "media_query", f"{sid}: the search query '{q}' of {e['element_id']} must be 2 to 6 plain English words")
            brand = next((w for text in [q, *(e["media"].get("alt_queries") or [])] for w in re.findall(r"[a-z0-9]+", text.lower()) if w.startswith(BRAND_STEMS)), None)
            rule("media_query_brand", sid, brand is not None, 5, "warning", "brand_query", f"{sid}: a search query of {e['element_id']} holds '{brand}', a brand or a word made from one: name only what is visible")
        rule("real_media_with_meaning", sid, any(e["role"] == "primary" for e in real) and not any(e["type"] in DRAWN_CARRIERS for e in els), 5, "warning", "real_media_alone",
             f"{sid}: a real picture or clip is the primary element and nothing drawn (text, graphic, diagram, chart) says what the narration means")
        known = set(words(f"{n['text']} {n.get('text_en') or ''}")) | allow
        for e in texts:
            c = (e.get("content") or "").strip()
            w = words(c)
            nums = [x for x in re.findall(r"\d+(?:[.,]\d+)?", c) if x not in digits and not any("approximate" in k for k in e["constraints"])]
            strong = bool(nums) and bool(re.search(r"%|[$€£₹]|\d[.,]\d|\d{4,}", c))               # a percentage, an amount, a decimal or a long number is a statistic: never invented; a small number may be a spelled-out one
            rule("text_content", sid, not c, 6, "error", "text_without_content", f"{sid}: text element {e['element_id']} has no content")
            rule("numbers_grounded", sid, bool(nums), 6, "error" if llm and strong else "warning", "number_ungrounded", f"{sid}: '{c}' has a number that is not in the narration")
            rule("text_grounded", sid, bool(w) and sum(x in known for x in w) / len(w) < 0.5, 6, "warning", "text_ungrounded", f"{sid}: '{c}' is mostly not from the narration")
            rule("text_short", sid, len(c.split()) > 8 or len(c) > 70, 6, "warning", "text_long", f"{sid}: '{c[:40]}' is too long for an on-screen label")
            rule("text_not_narration", sid, len(c) > 20 and w == words(n["text"])[:len(w)], 6, "warning", "text_is_narration", f"{sid}: the on-screen text repeats the narration")
        if i:
            b, c = plan["scenes"][i - 1]["visual_concept"], s["visual_concept"]
            rule("variety", sid, b["representation"] == c["representation"] and b["primary_focus"] == c["primary_focus"] and c["representation"] != "typography", 7, "warning", "repeated_concept", f"{sid} repeats the concept of the scene before it")
        rule("palette", sid, any(isinstance(v, str) and v.startswith("#") and v.lower() not in pal for e in els for v in e["appearance"].values()), 7, "warning", "palette", f"{sid}: an element uses a colour that is not in the project palette")
        rule("motion_not_presets", sid, any(MOTION_WORDS.search(h["intent"]) for h in s["motion_hints"]), 5, "warning", "motion_preset", f"{sid}: a motion hint names presets or timing")
    return counts_
