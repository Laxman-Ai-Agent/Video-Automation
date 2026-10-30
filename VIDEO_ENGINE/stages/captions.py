"""Captions (docs/ROADMAP.md Phase 6): the ONE place that turns the spoken words into caption lines. Remotion (components/Subtitles.tsx) only draws what this builds.

A caption ends at the end of a sentence, at a pause, or when it would be wider than a phone screen shows comfortably (counted in grapheme clusters: a Telugu syllable is one
cluster, not one code point). The first caption is the HOOK when it starts inside the first seconds: it is drawn large. A word is a KEY term when it is a number or when the scene
it is spoken in shows the same word on screen (the planned texts of Motion Planning): the caption stresses what the picture stresses, with no extra LLM call."""
import re
from typing import Any

from .telugu import glen

HOOK_SECONDS = 3.0
PAUSE_S = 0.45                                          # a pause this long ends a caption
MAX_GRAPHEMES = {"16:9": 38, "9:16": 24}                # the width of one caption (it wraps to at most two lines on screen)
END_OF_SENTENCE = re.compile(r"[.?!।…]$")


def norm(word: str) -> str:
    """A word as it is compared (case and punctuation do not matter)."""
    return re.sub(r"[^\w]+", "", word.casefold())


def scene_terms(scenes: list[dict[str, Any]], planned_texts: dict) -> list[tuple[float, float, set[str]]]:
    """[(start, end, {words the scene shows on screen})] from the planned texts of Motion Planning (`planned_texts`: scene id -> its texts)."""
    return [(float(s.get("start", 0)), float(s.get("end", 0)), {norm(w) for t in planned_texts.get(s.get("id"), []) for w in str(t.get("text", "")).split()} - {""}) for s in scenes]


def is_key(word: str, at: float, terms: list[tuple[float, float, set[str]]]) -> bool:
    return any(c.isdigit() for c in word) or any(a <= at < b and norm(word) in shown for a, b, shown in terms)


def build(words: list[dict[str, Any]], aspect: str, terms: list[tuple[float, float, set[str]]]) -> list[dict[str, Any]]:
    """[{start, end, hook, words: [{w, start, end, key}]}] in time order. `words`: [{w, start, end}] in seconds."""
    limit, captions, cur = MAX_GRAPHEMES[aspect], [], []

    def flush() -> None:
        if cur:
            captions.append({"start": cur[0]["start"], "end": cur[-1]["end"], "hook": False, "words": list(cur)})
            cur.clear()

    for w in words:
        text = str(w["w"]).strip()
        if not text:
            continue
        if cur and (w["start"] - cur[-1]["end"] >= PAUSE_S or END_OF_SENTENCE.search(cur[-1]["w"]) or sum(glen(x["w"]) + 1 for x in cur) + glen(text) > limit):
            flush()
        cur.append({"w": text, "start": round(float(w["start"]), 3), "end": round(float(w["end"]), 3), "key": is_key(text, float(w["start"]), terms)})
    flush()
    if captions and captions[0]["start"] < HOOK_SECONDS:
        captions[0]["hook"] = True
    return captions
