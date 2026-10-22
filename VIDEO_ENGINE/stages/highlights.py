"""Emphasis events from the transcript's real timestamps (A2V_HIGHLIGHTS=1 puts them into the composition).
  python -m backend.highlights projects/demo [--write]      (--write saves emphasis.json)
What is highlighted: numbers (digits, Telugu digits, number words), Latin-script terms (AI, Python), contrast words, and the plan's own keywords
moved onto the word that is actually spoken. Never invents precision: a segment whose word times look wrong (zero length, overlap, outside the
segment) falls back to segment timing, and a keyword with no spoken word nearby stays "estimated". At most HIGHLIGHTS_MAX_PER_SENTENCE per sentence."""
import json
import re
import statistics
import sys
from pathlib import Path

from . import config
from .contracts import EmphasisEvent, Reason
from .models import ScenePlan
from .transcribe import load_transcript

END_MARKS = (".", "?", "!", "।")
PRIORITY = {"number": 0, "name": 1, "keyword": 2, "concept": 2, "contrast": 3}
# Exact forms only (Whisper's Telugu spelling varies, a prefix match would hit ordinary words). "ఒక" (a/one) is left out: it is an article.
NUMBER_WORDS = {"ఒకటి", "రెండు", "మూడు", "నాలుగు", "ఐదు", "అయిదు", "ఆరు", "ఏడు", "ఎనిమిది", "తొమ్మిది", "పది", "వంద", "వెయ్యి", "లక్ష", "కోటి"}
CONTRAST_WORDS = {"కానీ", "కాని", "అయితే", "అయినా", "అయినప్పటికీ", "కాదు", "బదులుగా"}
_PUNCT = re.compile(r"[.,?!।\"'()\[\]:;]")
_DIGIT = re.compile(r"[0-9౦-౯]")
_LATIN = re.compile(r"[A-Za-z]{2,}")
MIN_AFTER_TRIM = 0.4        # a highlight cut short by the next one must still cover about one spoken word


def segment_reliable(seg) -> bool:
    """Word times can be trusted only if they are ordered, non-overlapping, plausibly long and inside the segment."""
    if not seg.words:
        return False
    prev_end = seg.start - 0.25
    for w in seg.words:
        d = w.end - w.start
        if d < 0.02 or d > 3.0 or w.start + 0.001 < prev_end or w.start < seg.start - 0.25 or w.end > seg.end + 0.25:
            return False
        prev_end = w.end
    return True


def precision(t) -> dict:
    bad = [s.id for s in t.segments if not segment_reliable(s)]
    durs = [w.end - w.start for s in t.segments for w in s.words]
    return {"level": "word" if not bad else ("segment" if len(bad) == len(t.segments) else "mixed"), "segments": len(t.segments),
            "unreliable_segments": bad, "words": len(durs), "median_word_s": round(statistics.median(durs), 3) if durs else None}


def _sentences(t) -> list[tuple[int, object, int]]:
    """(sentence index, word, segment id) for every word; a sentence ends at an end mark or at the end of a segment."""
    out, n = [], 0
    for s in t.segments:
        for w in s.words:
            out.append((n, w, s.id))
            if w.w.endswith(END_MARKS):
                n += 1
        n += 1 if (s.words and not s.words[-1].w.endswith(END_MARKS)) else 0
    return out


def _kind(word: str) -> tuple[str, str] | None:
    c = _PUNCT.sub("", word)
    if _DIGIT.search(c):
        return "number", "digits"
    if c in NUMBER_WORDS:
        return "number", "number_word"
    if _LATIN.fullmatch(c):
        return "name", "latin_term"
    if c in CONTRAST_WORDS:
        return "contrast", "contrast_word"
    return None


def _scene_of(plan: ScenePlan | None, t: float) -> int:
    if plan is None:
        return 0
    for sc in plan.scenes:
        if sc.start <= t < sc.end:
            return sc.id
    return plan.scenes[-1].id


def _end(start: float, word_end: float, limit: float) -> float:
    lo, hi = config.HIGHLIGHT_DURATION_SEC
    return round(min(start + min(max(word_end + 0.6 - start, lo), hi), limit), 3)


def build(pdir: Path) -> dict:
    t = load_transcript(pdir)
    pf = pdir / "scene_plan.json"
    plan = ScenePlan.model_validate_json(pf.read_text(encoding="utf-8")) if pf.exists() else None
    rel = {s.id for s in t.segments if segment_reliable(s)}
    sent = _sentences(t)
    cands: list[tuple[int, EmphasisEvent]] = []                     # (sentence index, event)
    for n, w, sid in sent:
        k = _kind(w.w) if sid in rel else None
        if k:
            cands.append((n, EmphasisEvent(id="", scene=_scene_of(plan, w.start), start=round(w.start, 3), end=_end(w.start, w.end, t.duration),
                                           text=_PUNCT.sub("", w.w), kind=k[0], timing="word", reason=Reason(rule=k[1], detail=f"spoken {w.start:.2f}-{w.end:.2f}s"))))
    for sc in (plan.scenes if plan else []):
        for kw in sc.keywords:
            near = min((x for x in sent if x[2] in rel), key=lambda x: abs(x[1].start - kw.at), default=None)
            if near and abs(near[1].start - kw.at) <= config.HIGHLIGHT_SNAP_SEC:
                w = near[1]
                cands.append((near[0], EmphasisEvent(id="", scene=sc.id, start=round(w.start, 3), end=_end(w.start, w.end, min(sc.end, t.duration)), text=kw.text,
                                                     kind="keyword", timing="word", reason=Reason(rule="plan_keyword_snapped", detail=f"moved {w.start - kw.at:+.2f}s onto the spoken word"))))
                continue
            seg = next((s for s in t.segments if s.start - 0.05 <= kw.at <= s.end + 0.05), None)
            timing = "segment" if seg is not None and seg.id not in rel else "estimated"
            cands.append((-1, EmphasisEvent(id="", scene=sc.id, start=round(kw.at, 3), end=_end(kw.at, kw.at, min(sc.end, t.duration)), text=kw.text, kind="keyword",
                                            timing=timing, reason=Reason(rule="plan_keyword_unsnapped", detail="word times unreliable here" if timing == "segment" else "no spoken word starts near this time"))))
    skipped: list[dict] = []
    chosen: list[EmphasisEvent] = []
    by_sent: dict[int, list[EmphasisEvent]] = {}
    for n, e in cands:
        by_sent.setdefault(n if n >= 0 else 10_000 + e.scene, []).append(e)        # unsnapped keywords: capped per scene instead of per sentence
    for evs in by_sent.values():
        evs.sort(key=lambda e: (PRIORITY[e.kind], e.start))
        chosen += evs[:config.HIGHLIGHTS_MAX_PER_SENTENCE]
        skipped += [{"text": e.text, "start": e.start, "kind": e.kind, "reason": "sentence cap"} for e in evs[config.HIGHLIGHTS_MAX_PER_SENTENCE:]]
    chosen.sort(key=lambda e: e.start)
    final: list[EmphasisEvent] = []
    for e in chosen:
        if final and final[-1].end > e.start - config.HIGHLIGHT_MIN_GAP_SEC:
            p = final[-1]
            p.end = round(e.start - config.HIGHLIGHT_MIN_GAP_SEC, 3)
            if p.end - p.start < MIN_AFTER_TRIM:
                final.pop()
                skipped.append({"text": p.text, "start": p.start, "kind": p.kind, "reason": "overlaps the next highlight"})
        final.append(e)
    count: dict[int, int] = {}
    for e in final:
        count[e.scene] = count.get(e.scene, 0) + 1
        e.id = f"scene_{e.scene:02d}_hl_{count[e.scene]:02d}"
    return {"version": 1, "precision": precision(t), "events": [e.model_dump() for e in final], "skipped": skipped}


def apply_emphasis(pdir: Path, comp: dict) -> int:
    """Move each scene's headline (`at`) and later-keyword pulses onto the spoken word times. Returns how many values changed."""
    pf = pdir / "scene_plan.json"
    if not pf.exists():
        return 0
    plan = ScenePlan.model_validate_json(pf.read_text(encoding="utf-8"))
    kw = {sc.id: sc.keywords for sc in plan.scenes}
    ev = [EmphasisEvent(**e) for e in build(pdir)["events"] if e["kind"] == "keyword" and e["timing"] == "word"]
    changed = 0
    for s in comp["scenes"]:
        mine = sorted((e for e in ev if e.scene == s["id"]), key=lambda e: e.start)
        keys = kw.get(s["id"], [])
        if not mine or not keys:
            continue
        first = next((e for e in mine if e.text == keys[0].text), None)
        for l in s["layers"]:
            if first and l.get("type") in ("text", "counter") and l.get("at") is not None and abs(l["at"] - keys[0].at) < 1e-6 and l["at"] != first.start:
                l["at"], changed = first.start, changed + 1
            if l.get("pulses"):
                new = [e.start for e in mine if e.text != keys[0].text]
                if new and new != l["pulses"]:
                    l["pulses"], changed = new, changed + 1
    return changed


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    out = build(pdir)
    if "--write" in sys.argv:
        (pdir / "emphasis.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(out["precision"], f"events={len(out['events'])} skipped={len(out['skipped'])}")
    for e in out["events"]:
        print(f"  {e['id']} {e['start']:>6}-{e['end']:<6} {e['kind']:8} {e['timing']:9} {e['text']}  [{e['reason']['rule']}: {e['reason']['detail']}]")
