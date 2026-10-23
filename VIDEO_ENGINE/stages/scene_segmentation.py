"""Scene Segmentation: which narration belongs together in one scene (improvements/Scene_Segmentation_Complete_Roadmap). It runs only when the user starts it.

  input   the effective transcript (load_transcript: user fix > LLM-corrected > original, words with their times) and audio_analysis.json (measured pauses)
  output  scene_segmentation.json (atomic): scenes with exact narration, start/end taken from the first and last word, links to the transcript segments and words, boundary reasons,
          semantic beat, warnings with their cause, the 7 stages and a validation

The 7 logical stages are steps of this module, not agents: 1 read, 2 sentence & clause units + the places where a scene MAY end, 3-5 semantic understanding, idea-change detection and
grouping (ONE call of the existing Claude CLI, validated, one bounded retry, answer cached; no LLM = deterministic fallback from sentence ends, measured pauses and discourse markers,
marked as reduced semantic confidence), 6 timing, 7 validation.

A scene is NOT a transcript segment: a recognizer segment is only a chunk of speech. A scene can end inside a segment (when the idea changes there: the cut is allowed only at a sentence
end, a clause, a marker, a measured pause or, in a long stretch, between two words with enough narration on both sides) and several short segments can form one scene.
It never rewrites a word, never invents a timestamp and decides no graphics or motion (Visual Planning does).   python -m backend.scene_segmentation <project id>"""
import hashlib
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

from . import config
from .diagnose import UserProblem
from .transcribe import TRANSCRIPT_FILES, Transcript

SCHEMA = "1.1"
VERSION = 2                                  # bump when the rules or the instructions to Claude change (part of the step fingerprint and of the cache key of Claude's answers)
TIMING_RULES = 3                             # bump when only the rules for the scene times change (2: a scene ends where the next one starts when their words overlap; 3: a tiny last scene joins the one before it, for Claude's grouping too): old results are stale, Claude's cached answers stay valid
# configurable guidance (environment A2V_SEG_*), soft limits: meaning comes first
PAUSE_MIN = float(os.environ.get("A2V_SEG_PAUSE_MIN", "0.35"))         # a gap this long between two words is evidence of a boundary, never a boundary by itself
PAUSE_SCENE = float(os.environ.get("A2V_SEG_PAUSE_SCENE", "0.5"))      # the fallback may start a new scene at a pause this long
PAUSE_CLAUSE = float(os.environ.get("A2V_SEG_PAUSE_CLAUSE", "0.15"))   # a gap this long inside a sentence is a place where a scene MAY end
SOFT_MIN = float(os.environ.get("A2V_SEG_SOFT_MIN", "3.0"))            # seconds: shorter scenes are merged (fallback) or noted
SOFT_MAX = float(os.environ.get("A2V_SEG_SOFT_MAX", "12.0"))           # seconds: longer scenes are split at a clause (fallback) or noted
LONG_UNIT = float(os.environ.get("A2V_SEG_LONG_UNIT", "6.0"))          # a sentence/clause longer than this may be cut between any two words (with MIN_SPLIT on both sides)
MIN_SPLIT = float(os.environ.get("A2V_SEG_MIN_SPLIT", "1.5"))
TOL = 0.5
END_MARKS = (".", "?", "!", "।")
CLAUSE_MARKS = (",", ";", ":")
MARKERS = ("కానీ", "ఎందుకంటే", "దీనివల్ల", "మరోవైపు", "చివరగా", "అందుకే", "అయితే", "అంటే", "మొదట", "ఆ తర్వాత", "ఆ సమయం", "కాబట్టి", "ఉదాహరణకు", "అక్కడ", "అయినా", "అయనా")      # discourse markers: evidence only
BOUNDARY_TYPES = ("topic_change", "concept_change", "cause_effect_step", "example", "contrast", "conclusion", "pause", "sentence_boundary")
STAGES = ("Analysis Data Reader", "Sentence & Clause Detection", "Semantic Understanding", "Topic & Idea Change Detection", "Scene Boundary & Grouping", "Duration & Timing Assignment",
          "Scene Validation & Continuity")
TIMEOUT = 180
log = logging.getLogger(__name__)

SYSTEM = (
    "You split the narration of a Telugu explainer video into scenes. Every scene shows ONE visual idea. The narration is a numbered list of words (number:word). The speech recognizer's "
    "segments are only chunks of speech and NOT scenes: a scene may end inside a segment, and several short segments may belong to one scene. A scene may end only after a word that is "
    "followed by '|' (those are the allowed cut points) and after the last word. Start a new scene when the narration moves to a different concept: another kind of challenge, how long "
    "something takes versus what it feels like, a new place, an example, a contrast, a cause-effect step, a reveal or a conclusion. Keep words together when they explain the same idea "
    "and fit one picture; group very short related fragments. Do not make one scene per sentence or per segment by default. A pause is evidence, not a rule. Scene length is a guideline "
    "of about {lo}-{hi} seconds, not a limit: but if a scene would run longer than {hi} seconds and carries two concepts, cut it at an allowed point. Never rewrite, add or skip words: "
    "the scenes must cover words 1..N exactly once, in order. Write the beat and the objective in English, using only what the narration says. Answer with JSON only: "
    '{{"scenes":[{{"first_word":<number>,"last_word":<number>,"beat":"<what this scene is about, at most 12 words>","objective":"<one short sentence>",'
    '"boundary_after":{{"type":"<one of: {types}>","reason":"<why the scene ends here, at most 15 words>"}}}}]}}')


# ---------- stage 1: read ----------
class SourceError(UserProblem):
    """The existing analysis JSON of the project is missing or not usable. Scene Segmentation never goes back to the audio: it says so instead."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def load_source(pdir: Path) -> Transcript:
    """The final analysis JSON of the project as it is: transcript_fixed.json > transcript_corrected.json > transcript.json (the same order every stage reads). Nothing is generated: when it is
    missing or invalid this raises SourceError (the audio is NOT processed again), and word times that cannot be true (negative, end before start, past the audio) are refused."""
    f = next((pdir / n for n in TRANSCRIPT_FILES if (pdir / n).exists()), None)
    if f is None:
        raise SourceError("analysis_json_missing", "The final analysis JSON (transcript.json) is not in this project. The audio was not processed: add the JSON file to the project, or run the Audio Analyzer yourself.")
    try:
        t = Transcript.model_validate_json(f.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        raise SourceError("analysis_json_invalid", f"{f.name} is not a valid analysis JSON ({str(e).splitlines()[0][:160]}). The audio was not processed again: fix or replace the file.") from e
    if t.duration <= 0 or not any(s.words or s.text.strip() for s in t.segments):
        raise SourceError("analysis_json_invalid", f"{f.name} has no duration or no narration. The audio was not processed again: fix or replace the file.")
    for s in t.segments:
        for w in s.words:
            if w.start < 0 or w.end < w.start or w.end > t.duration + TOL:
                raise SourceError("analysis_json_invalid", f"{f.name}: the word {w.w!r} in segment {s.id} has impossible times ({w.start}-{w.end} s, audio {t.duration} s). The audio was not processed again: fix or replace the file.")
    return t


def read_input(pdir: Path) -> dict:
    """The final analysis JSON as a flat word list with ids and the transcript segment each word came from, plus the pauses of audio_analysis.json when that file is there (optional: without
    it the gaps between the words are used). Reading never starts any audio processing."""
    t = load_source(pdir)
    words, segs = [], []
    for s in t.segments:
        first = len(words)
        if s.words:
            for w in s.words:
                words.append({"id": f"w{len(words) + 1:03d}", "text": w.w, "start": w.start, "end": w.end, "timing": w.timing or "measured", "seg": s.id})
        else:                                    # a segment without word times: kept as one unit with the sentence-level times
            words.append({"id": f"w{len(words) + 1:03d}", "text": s.text, "start": s.start, "end": s.end, "timing": "sentence", "seg": s.id})
        segs.append({"id": s.id, "start": s.start, "end": s.end, "first": first, "last": len(words) - 1})
    aa = {}
    try:
        aa = json.loads((pdir / "audio_analysis.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    pauses = [(p["start_seconds"], p["end_seconds"]) for p in aa.get("pauses", [])]
    return {"language": t.language, "duration": t.duration, "words": words, "segments": segs, "pauses": pauses, "analysis_file": "audio_analysis.json" if aa else None,
            "analysis_status": (aa.get("validation") or {}).get("status"), "audio_notes": {n["segment"]: n for n in (aa.get("validation") or {}).get("notes", []) if "segment" in n}}


def fingerprint_of(inp: dict) -> str:
    """What the segmentation was made from: every word with its time (a changed transcript, correction or alignment makes an old segmentation stale)."""
    return hashlib.sha1(json.dumps([(w["text"], w["start"], w["end"]) for w in inp["words"]] + [inp["duration"]], ensure_ascii=False).encode()).hexdigest()


def load_fresh(pdir: Path) -> dict | None:
    """scene_segmentation.json when it was made from the transcript that is the transcript now, in the current file format (an older one lacks the source links the page and Visual Planning use); otherwise None (stale or missing)."""
    try:
        data = json.loads((pdir / "scene_segmentation.json").read_text(encoding="utf-8"))
        return data if data.get("schema_version") == SCHEMA and data.get("timing_rules") == TIMING_RULES and data.get("source_fingerprint") == fingerprint_of(read_input(pdir)) else None
    except (OSError, ValueError, KeyError, UserProblem):          # missing, unreadable or an unusable source: not fresh
        return None


# ---------- stage 2: sentence & clause units, and where a scene may end ----------
def build_units(inp: dict) -> list[dict]:
    """Sentences (a sentence ends at . ? ! । or at the end of a recognizer segment). A sentence longer than LONG_UNIT is also cut into clauses (after , ; : or before a discourse marker)."""
    ws = inp["words"]
    sentences, a = [], 0
    for i, w in enumerate(ws):
        last = i == len(ws) - 1 or ws[i + 1]["seg"] != w["seg"]
        if w["text"].endswith(END_MARKS) or last:
            sentences.append((a, i))
            a = i + 1
    units = []
    for sa, sb in sentences:
        parts = [(sa, sb)]
        if ws[sb]["end"] - ws[sa]["start"] > LONG_UNIT:
            cuts = [i for i in range(sa, sb) if ws[i]["text"].endswith(CLAUSE_MARKS) or _marker_after(ws, i)]
            parts, p = [], sa
            for c in cuts:
                if ws[c]["end"] - ws[p]["start"] >= MIN_SPLIT and ws[sb]["end"] - ws[c + 1]["start"] >= MIN_SPLIT:
                    parts.append((p, c))
                    p = c + 1
            parts.append((p, sb))
        for k, (x, y) in enumerate(parts):
            units.append({"first": x, "last": y, "clause": len(parts) > 1 and k < len(parts) - 1, "sentence_end": y == sb})
    for n, u in enumerate(units):
        u["n"] = n + 1
        u["text"] = " ".join(w["text"] for w in ws[u["first"]:u["last"] + 1])
        u["start"], u["end"] = ws[u["first"]]["start"], ws[u["last"]]["end"]
        u["pause_after"] = gap_after(inp, u["last"])
        u["marker_next"] = _marker_after(ws, u["last"])
    return units


def _marker_after(ws: list[dict], i: int) -> bool:
    return i + 1 < len(ws) and any(ws[i + 1]["text"].startswith(m) for m in MARKERS)


def gap_after(inp: dict, i: int) -> float:
    ws = inp["words"]
    nxt = ws[i + 1]["start"] if i + 1 < len(ws) else inp["duration"]
    return round(max(0.0, nxt - ws[i]["end"]), 3)


def allowed_cuts(inp: dict, units: list[dict]) -> dict[int, str]:
    """{word index i: why} for the places where a scene may END after word i (never the last word: that is always the end of the last scene): a unit end, a clause mark, a discourse
    marker that follows, a pause inside a sentence, or, in a stretch longer than LONG_UNIT, between two words with at least MIN_SPLIT of narration on both sides."""
    ws, out = inp["words"], {}
    for u in units:
        for i in range(u["first"], u["last"]):
            kind = ("clause" if ws[i]["text"].endswith(CLAUSE_MARKS) else "marker" if _marker_after(ws, i) else "pause" if gap_after(inp, i) >= PAUSE_CLAUSE else
                    "free" if u["end"] - u["start"] > LONG_UNIT and ws[i]["end"] - u["start"] >= MIN_SPLIT and u["end"] - ws[i + 1]["start"] >= MIN_SPLIT else None)
            if kind:
                out[i] = kind
        if u["last"] < len(ws) - 1:
            out[u["last"]] = "sentence" if u["sentence_end"] else "clause_end"
    return out


# ---------- stages 3-5: semantic grouping (Claude) or the deterministic fallback ----------
def _json_from(text: str) -> dict:
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("no JSON in the answer")
    text = text[a:b + 1]
    try:
        return json.loads(text)
    except ValueError:
        for m in reversed(list(re.finditer(r'\{\s*"scenes"', text))):     # Claude sometimes writes a broken answer, notices it and writes the corrected JSON after it: the last complete object wins
            try:
                return json.JSONDecoder().raw_decode(text[m.start():])[0]
            except ValueError:
                continue
        # Claude copies the input notation "70:word" into the numbers: `"first_word":70:,` or `"first_word":70:77,` (seen in about 1 run in 3). Repairing it saves a whole second call;
        # the repaired ranges are still checked word by word (coverage once, in order), so a wrong repair is rejected, never accepted.
        text = re.sub(r'"first_word"\s*:\s*(\d+)\s*:\s*(\d+)\s*,', r'"first_word":\1,"last_word":\2,', text)
        text = re.sub(r'("(?:first|last)_word"\s*:\s*\d+)\s*:\s*(?=[,}])', r'\1', text)
        return json.loads(text)


def numbered_text(inp: dict, cuts: dict[int, str], unit_ends: dict[int, dict]) -> list[dict]:
    """The request: per recognizer segment, the words as 'number:word', with '|' after every word where a scene may end."""
    ws, rows = inp["words"], []
    for s in inp["segments"]:
        text = " ".join(f"{i + 1}:{ws[i]['text']}{'|' if i in cuts else ''}" for i in range(s["first"], s["last"] + 1))
        rows.append({"segment": s["id"], "start": round(ws[s["first"]]["start"], 2), "end": round(ws[s["last"]]["end"], 2), "words": text})
    return rows


def check_grouping(answer: dict, inp: dict, units: list[dict], cuts: dict[int, str]) -> tuple[list[dict], list[str]]:
    """(scenes, problems). A scene is a word range (first_word/last_word, 1-based; the old units list is also understood). Ranges must cover every word once, in order, and end only at an allowed cut."""
    n, problems, out, expect = len(inp["words"]), [], [], 1
    scenes = answer.get("scenes") if isinstance(answer, dict) else None
    if not isinstance(scenes, list) or not scenes:
        return [], ["the answer needs a non-empty 'scenes' list"]
    for k, sc in enumerate(scenes, 1):
        try:
            if "first_word" in sc:
                a, b = int(sc["first_word"]), int(sc["last_word"])
            else:
                us = [int(u) for u in sc["units"]]
                a, b = units[us[0] - 1]["first"] + 1, units[us[-1] - 1]["last"] + 1
            beat, obj = " ".join(str(sc["beat"]).split()), " ".join(str(sc.get("objective", "")).split())
            ba = sc.get("boundary_after") or {}
            typ, reason = str(ba.get("type", "")), " ".join(str(ba.get("reason", "")).split())
        except (KeyError, TypeError, ValueError, AttributeError, IndexError):
            problems.append(f"scene {k} is malformed")
            continue
        if a != expect or b < a or b > n:
            problems.append(f"scene {k} must start at word {expect} and end at a later word (at most {n}), got {a}-{b}")
        else:
            if b < n and (b - 1) not in cuts:
                problems.append(f"scene {k} ends after word {b}, which is not an allowed cut point (a word followed by '|')")
            expect = b + 1
        if not beat:
            problems.append(f"scene {k} has no beat")
        if k < len(scenes) and typ not in BOUNDARY_TYPES:
            problems.append(f"scene {k}: boundary type '{typ}' is not one of {', '.join(BOUNDARY_TYPES)}")
        out.append({"first": a - 1, "last": b - 1, "beat": beat, "objective": obj, "type": typ if typ in BOUNDARY_TYPES else "concept_change", "reason": reason})
    if expect != n + 1:
        problems.append(f"the scenes must use every word 1..{n} exactly once (they stopped at word {expect - 1})")
    return out, problems


def tiny_last_joins_previous(ws: list[dict], bounds: list) -> bool:
    """True when the last scene (`bounds`: one (first_word, last_word) per scene) is shorter than SOFT_MIN and the scene before it can take it without becoming longer than SOFT_MAX. The same rule
    for the fallback and for Claude's grouping: a last scene of two or three seconds cannot carry its own picture, and Claude's answer is only guided (not checked) on scene length."""
    if len(bounds) < 2:
        return False
    (first_prev, _), (first_last, last_last) = bounds[-2], bounds[-1]
    return ws[last_last]["end"] - ws[first_last]["start"] < SOFT_MIN and ws[last_last]["end"] - ws[first_prev]["start"] <= SOFT_MAX


def fallback_grouping(inp: dict, units: list[dict], cuts: dict[int, str]) -> list[dict]:
    """No LLM: close a scene at a sentence end when it is long enough and a measured pause or a discourse marker follows (or it would become too long); then cut a scene that is still
    longer than SOFT_MAX at the strongest allowed place inside it. Meaning is NOT judged."""
    ws = inp["words"]
    groups, cur = [], []
    for i, u in enumerate(units):
        cur.append(u)
        dur = u["end"] - cur[0]["start"]
        nxt_dur = (units[i + 1]["end"] - cur[0]["start"]) if i + 1 < len(units) else 0
        if (u["sentence_end"] and dur >= SOFT_MIN and (u["pause_after"] >= PAUSE_SCENE or u["marker_next"] or nxt_dur > SOFT_MAX)) or i == len(units) - 1:
            groups.append([cur[0]["first"], cur[-1]["last"]])
            cur = []
    if tiny_last_joins_previous(ws, groups):                           # a tiny last scene joins the one before it
        last = groups.pop()
        groups[-1][1] = last[1]
    out = []
    for a, b in groups:
        pieces = [(a, b)]
        while True:                                                     # cut a too long scene at the best allowed place with SOFT_MIN on both sides
            x, y = pieces[-1]
            if ws[y]["end"] - ws[x]["start"] <= SOFT_MAX:
                break
            ok = [i for i in range(x, y) if i in cuts and ws[i]["end"] - ws[x]["start"] >= SOFT_MIN and ws[y]["end"] - ws[i + 1]["start"] >= SOFT_MIN]
            if not ok:
                break
            rank = {"sentence": 3, "clause_end": 2, "clause": 2, "marker": 2, "pause": 1, "free": 0}
            best = max(ok, key=lambda i: (rank.get(cuts[i], 0), gap_after(inp, i), -abs((ws[i]["end"] - ws[x]["start"]) - (ws[y]["end"] - ws[x]["start"]) / 2)))
            pieces[-1:] = [(x, best), (best + 1, y)]
        out += pieces
    return [{"first": a, "last": b, "beat": None, "objective": None, "type": "pause" if gap_after(inp, b) >= PAUSE_SCENE else "sentence_boundary",
             "reason": "a pause follows" if gap_after(inp, b) >= PAUSE_SCENE else "the sentence ends and the scene is long enough"} for a, b in out]


def group(pdir: Path, inp: dict, units: list[dict], cuts: dict[int, str], ask=None) -> tuple[list[dict], dict]:
    cache_f = pdir / "scene_llm_cache.json"
    try:
        cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
    except ValueError:
        cache = {}
    from . import llm_client
    try:
        _, active_model, _, _ = llm_client.resolve_provider_config()
    except Exception:
        active_model = os.environ.get("PROMPTGEN_MODEL") or None
    llm = {"status": "not_run", "error": None, "model": active_model, "attempts": 0, "problems": [], "calls": []}   # calls: where each attempt's time went
    system = SYSTEM.format(lo=SOFT_MIN, hi=SOFT_MAX, types=", ".join(BOUNDARY_TYPES))
    user = json.dumps({"duration_seconds": round(inp["duration"], 2), "words_total": len(inp["words"]), "segments": numbered_text(inp, cuts, {})}, ensure_ascii=False)
    problems: list[str] = []
    try:
        for attempt in (0, 1):
            ask_text = user if not problems else user + "\n\nYour previous answer had these problems:\n- " + "\n- ".join(problems[:8]) + "\nReturn the complete corrected JSON."
            t0 = time.perf_counter()
            key = hashlib.sha1(f"{VERSION}|{llm['model']}|{system}|{ask_text}".encode()).hexdigest()
            llm["attempts"] = attempt + 1
            call = {"attempt": attempt + 1, "source": "cache" if key in cache else "claude", "prompt_chars": len(ask_text) + len(system), "lookup_s": round(time.perf_counter() - t0, 4)}
            llm["calls"].append(call)
            if key in cache:
                answer, llm["status"] = cache[key], "cached"                      # the same question was answered before: no second call
            else:
                from . import promptgen
                t1 = time.perf_counter()
                try:
                    answer = (ask or promptgen.run_claude)(ask_text, system=system, timeout=TIMEOUT)
                finally:
                    call["claude_s"] = round(time.perf_counter() - t1, 2)         # also recorded when the call fails or times out
                cache[key] = answer
                cache_f.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                llm["status"] = "applied"
            t2 = time.perf_counter()
            try:
                scenes, problems = check_grouping(_json_from(answer), inp, units, cuts)
            except ValueError as e:
                scenes, problems = [], [f"the answer is not valid JSON ({e})"]
            call["check_s"], call["problems"] = round(time.perf_counter() - t2, 4), problems[:4]      # what made the answer unusable (a retry costs a whole second call)
            if not problems:
                if tiny_last_joins_previous(inp["words"], [(s["first"], s["last"]) for s in scenes]):         # Claude was told the length guideline, nothing checks it
                    last = scenes.pop()
                    scenes[-1]["last"] = last["last"]
                return scenes, llm
        llm["status"], llm["problems"] = "rejected", problems[:6]
    except Exception as e:     # CLI missing / not signed in / timeout
        llm["status"] = "unavailable" if "not found" in str(e) or "sign" in str(e).lower() else "failed"
        llm["error"] = str(e)[:240]
    return fallback_grouping(inp, units, cuts), llm


# ---------- stages 6-7: timing and validation ----------
def assemble(inp: dict, units: list[dict], cuts: dict[int, str], groups: list[dict], method: str) -> list[dict]:
    ws, scenes = inp["words"], []
    for k, g in enumerate(groups, 1):
        first, last = g["first"], g["last"]
        seg_words = ws[first:last + 1]
        kinds = {w["timing"] for w in seg_words}
        source = "sentence_timestamps" if "sentence" in kinds else "estimated_words" if "estimated" in kinds else "aligned_words"
        dur = seg_words[-1]["end"] - seg_words[0]["start"]
        details = []
        if source == "sentence_timestamps":
            details.append({"code": "sentence_level_timing", "message": "some narration has no word times: the sentence times of the transcript are used for it"})
        if source == "estimated_words":
            est = [w["text"] for w in seg_words if w["timing"] == "estimated"]
            details.append({"code": "estimated_timing", "message": f"{len(est)} corrected word(s) have estimated times ({', '.join(est[:3])}{'...' if len(est) > 3 else ''})"})
        if dur < SOFT_MIN and len(groups) > 1:
            details.append({"code": "short_scene", "message": f"short scene ({dur:.1f}s, guideline {SOFT_MIN:g}-{SOFT_MAX:g}s)"})
        if dur > SOFT_MAX:
            details.append({"code": "long_scene", "message": f"long scene ({dur:.1f}s, guideline {SOFT_MIN:g}-{SOFT_MAX:g}s): it may hold more than one idea"})
        segs = sorted({w["seg"] for w in seg_words})
        inside = last < len(ws) - 1 and ws[last]["seg"] == ws[last + 1]["seg"]       # the cut falls inside a transcript segment: intentional (the allowed-cut rule), recorded here
        kind = cuts.get(last)
        ev = {"sentence": ["sentence_boundary"], "clause_end": ["clause_boundary"], "clause": ["clause_boundary"], "marker": ["discourse_marker"], "pause": ["pause"], "free": ["within_long_sentence"]}.get(kind, ["sentence_boundary"])
        if gap_after(inp, last) >= PAUSE_MIN and "pause" not in ev:
            ev.append("pause")
        if _marker_after(ws, last) and "discourse_marker" not in ev:
            ev.append("discourse_marker")
        if method == "llm_semantic_grouping":
            ev.append("semantic_change")
        scenes.append({
            "scene_id": f"scene_{k:03d}", "scene_index": k, "start_time": round(seg_words[0]["start"], 3), "end_time": round(seg_words[-1]["end"], 3),
            "source_segment_ids": segs, "source_sentence_ids": [f"sentence_{u['n']:03d}" for u in units if u["last"] >= first and u["first"] <= last],
            "source_word_ids": [w["id"] for w in seg_words], "word_range": [first, last], "transcript": " ".join(w["text"] for w in seg_words),
            "semantic_beat": g["beat"], "scene_objective": g["objective"],
            "boundary_after": {"type": g["type"], "reason": g["reason"] or None, "evidence": ev, "confidence": None, "inside_segment": inside}, "timing_source": source,
            "pause_after_seconds": gap_after(inp, last), "starts_inside_segment": first > 0 and ws[first - 1]["seg"] == ws[first]["seg"],
            "warnings": [d["message"] for d in details], "warning_details": details})
    for a, b in zip(scenes, scenes[1:]):
        # Whisper times words one by one, so the last word of a scene can end after the first word of the next one starts (seen: 0.18-0.28 s). The timeline needs scenes that do not overlap: the
        # earlier scene ends where the next one starts (the next word's start is the firmer time; the earlier word's end overshoots into it). No word time is changed; the original end is kept.
        if a["start_time"] + 0.1 < b["start_time"] < a["end_time"]:
            a["end_time_word"], a["end_time"] = a["end_time"], b["start_time"]
    for k, s in enumerate(scenes):
        s["boundary_before"] = {"type": "start", "reason": "first scene", "evidence": ["sentence_boundary"], "confidence": None, "inside_segment": False} if k == 0 else scenes[k - 1]["boundary_after"]
    scenes[-1]["boundary_after"] = {"type": "end", "reason": "end of the narration", "evidence": [], "confidence": None, "inside_segment": False}
    return scenes


def source_notes(inp: dict) -> list[dict]:
    """Differences inside the source transcript itself, checked against the words: a segment whose end is before the end of its last word. The words' own times are used, and the note says
    whether they are consistent (the next segment starts where the last word ends)."""
    ws, segs, notes = inp["words"], inp["segments"], []
    for k, s in enumerate(segs):
        end = ws[s["last"]]["end"]
        if ws[s["last"]]["timing"] != "sentence" and end - s["end"] > 0.05:
            nxt = ws[segs[k + 1]["first"]]["start"] if k + 1 < len(segs) else inp["duration"]
            cont = abs(nxt - end) <= 0.05
            audio = inp.get("audio_notes", {}).get(s["id"])               # what the Audio Analyzer found when it looked at the sound in that gap
            notes.append({"code": "segment_end_before_last_word", "segment": s["id"], "segment_end": round(s["end"], 3), "last_word_end": round(end, 3), "continuous_with_next": cont,
                          "audio_check": audio["audio_check"] if audio else "not checked (no audio analysis note)",
                          "message": f"transcript segment {s['id']} ends at {s['end']:.2f}s but its last word ends at {end:.2f}s"
                                     + (f"; the next segment starts at {nxt:.2f}s, so the word times are consistent" if cont else f"; the next segment starts at {nxt:.2f}s")
                                     + (f"; audio check: {audio['audio_check']}" if audio else "") + ". The scene times use the word times as the source has them"})
    return notes


def validate(inp: dict, scenes: list[dict]) -> dict:
    ws, errors, warnings = inp["words"], [], []
    got = [i for s in scenes for i in range(s["word_range"][0], s["word_range"][1] + 1)]
    coverage = "complete" if got == list(range(len(ws))) else "incomplete"
    if coverage != "complete":
        errors.append("the scenes do not cover every spoken word exactly once, in order")
    if " ".join(s["transcript"] for s in scenes) != " ".join(w["text"] for w in ws):
        errors.append("the scene narration differs from the transcript")
    if any(s["source_word_ids"] != [w["id"] for w in ws[s["word_range"][0]:s["word_range"][1] + 1]] for s in scenes):
        errors.append("a scene points to words that are not its own")
    order = all(a["start_time"] <= b["start_time"] for a, b in zip(scenes, scenes[1:]))
    within = all(0 <= s["start_time"] < s["end_time"] <= inp["duration"] + TOL for s in scenes)
    if not order:
        errors.append("the scenes are not in chronological order")
    if not within:
        errors.append("a scene has a zero or negative length or lies outside the audio")
    for a, b in zip(scenes, scenes[1:]):
        if b["start_time"] < a["end_time"] - 0.05:
            warnings.append(f"{b['scene_id']} starts {a['end_time'] - b['start_time']:.2f}s before {a['scene_id']} ends (overlapping word times)")
    for s in scenes:
        warnings += [f"{s['scene_id']}: {m}" for m in s["warnings"]]
    return {"status": "error" if errors else "warning" if warnings else "ok", "transcript_coverage": coverage, "chronological_order": order,
            "timestamps_within_audio": within, "errors": errors, "warnings": warnings,
            "notes": source_notes(inp) + [{"code": "scene_end_adjusted", "scene": s["scene_id"], "message": f"{s['scene_id']} ends at {s['end_time']:.2f}s, where the next scene starts: its last word ends at {s['end_time_word']:.2f}s in the source (word times overlap). The word times themselves are unchanged"}
                                         for s in scenes if "end_time_word" in s]}


def run(pdir: Path, progress=None, ask=None) -> dict:
    say = progress or (lambda p, eta=None: None)
    n = len(STAGES)
    mark = lambda k: say(round(100 * k / n, 2))                  # k stages are finished
    mark(0)
    T, t0 = {}, time.perf_counter()
    def lap(name):                                               # seconds since the previous lap
        nonlocal t0
        now = time.perf_counter()
        T[name], t0 = round(now - t0, 3), now
    inp = read_input(pdir)                                       # 1
    if not inp["words"]:
        raise ValueError("the transcript has no words")
    lap("1_read_input")
    mark(1)
    units = build_units(inp)                                     # 2
    cuts = allowed_cuts(inp, units)
    lap("2_units_and_cuts")
    mark(2)
    groups, llm = group(pdir, inp, units, cuts, ask)             # 3-5 (one call)
    lap("3-5_grouping")
    method = "llm_semantic_grouping" if llm["status"] in ("applied", "cached") else "deterministic_fallback"
    mark(5)
    scenes = assemble(inp, units, cuts, groups, method)          # 6
    lap("6_assemble")
    mark(6)
    val = validate(inp, scenes)                                  # 7
    lap("7_validate")
    llm_on = method == "llm_semantic_grouping"
    inside = sum(bool(s["boundary_after"]["inside_segment"]) for s in scenes)
    stat = lambda i: "failed" if val["errors"] and i == 6 else "warning" if (i in (2, 3, 4) and not llm_on) or (i == 6 and val["status"] == "warning") else "completed"
    detail = [f"{len(inp['words'])} words in {len(inp['segments'])} transcript segments, {len(inp['pauses'])} measured pauses, duration {inp['duration']}s"
              + ("" if inp["analysis_file"] else " (no audio_analysis.json: pauses come from word gaps)"),
              f"{len(units)} units ({sum(u['clause'] for u in units)} clause splits), {len(cuts)} places where a scene may end",
              {"applied": "Claude read the numbered words in context", "cached": "earlier answer reused, no new call"}.get(llm["status"], "no LLM: meaning was not judged (" + (llm["error"] or ", ".join(llm["problems"]) or llm["status"]) + ")"),
              "topic and idea changes decided together with the grouping" if llm_on else "no LLM: only sentence ends, pauses and discourse markers were used",
              f"{len(scenes)} scenes from {len(inp['segments'])} segments ({inside} cut(s) inside a segment)",
              "start = first word start, end = last word end (" + ", ".join(sorted({s['timing_source'] for s in scenes})) + ")",
              f"coverage {val['transcript_coverage']}, order {'ok' if val['chronological_order'] else 'wrong'}, {len(val['errors'])} errors, {len(val['warnings'])} warnings, {len(val['notes'])} source note(s)"]
    out = {"schema_version": SCHEMA, "timing_rules": TIMING_RULES, "source_fingerprint": fingerprint_of(inp), "source_audio_analysis": inp["analysis_file"], "language": inp["language"], "audio_duration_seconds": inp["duration"],
           "segmentation_method": method, "semantic_confidence": "supported_by_llm" if llm_on else "reduced", "needs_review": bool(val["errors"]) or not llm_on, "llm": llm,
           "config": {"pause_min": PAUSE_MIN, "pause_scene": PAUSE_SCENE, "pause_clause": PAUSE_CLAUSE, "soft_min": SOFT_MIN, "soft_max": SOFT_MAX, "long_unit": LONG_UNIT, "min_split": MIN_SPLIT},
           "source_segments": len(inp["segments"]), "timings_seconds": T, "scenes": scenes, "stages": [{"n": i + 1, "name": nm, "status": stat(i), "detail": detail[i]} for i, nm in enumerate(STAGES)], "validation": val}
    if val["errors"]:
        raise ValueError("; ".join(val["errors"]))               # nothing is written: a broken segmentation must not look finished
    tmp = pdir / "scene_segmentation.json.part"
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, pdir / "scene_segmentation.json")
    lap("write")
    T["total"] = round(sum(T.values()), 3)
    log.info("scene segmentation %s: %s | llm %s", pdir.name, T, llm["calls"])
    say(100)
    return out


if __name__ == "__main__":
    r = run(config.project_dir(sys.argv[1]))
    print(r["segmentation_method"], f"{len(r['scenes'])} scenes", r["validation"]["status"])
