"""python -m backend.cuts projects/demo  ->  cuts.json (candidate cut points, snapped to word ends)."""
import json
import sys
from pathlib import Path

from . import config
from .audio_utils import silences
from .transcribe import find_audio, load_transcript

END_MARKS = (".", "?", "!", "।")


def make_cuts(pdir: Path) -> list[dict]:
    t = load_transcript(pdir)
    words = [w for s in t.segments for w in s.words]
    if not words:
        return []
    ends = [w.end for w in words]

    def snap(x: float) -> float:
        return min(ends, key=lambda e: abs(e - x))

    def gap_after(e: float) -> float:
        nxt = [w.start for w in words if w.start >= e - 1e-3]
        return round(max(0.0, (nxt[0] if nxt else t.duration) - e), 2)

    cand: list[tuple[float, str]] = []
    # ponytail: pysbd has no Telugu rules; split on punctuation + Whisper segment ends. Upgrade: Telugu sentence model.
    for s in t.segments:
        cand.append((s.words[-1].end if s.words else s.end, "segment_end"))
        for w in s.words:
            if w.w.endswith(END_MARKS):
                cand.append((w.end, "sentence_end"))
    for a, b in silences(find_audio(pdir)):
        cand.append((snap(a), "silence"))

    cand.sort()
    cuts: list[dict] = []
    for x, reason in cand:
        x = snap(x)
        if x >= words[-1].end - 0.5:       # no cut at the very end
            continue
        if cuts and x - cuts[-1]["t"] < 0.8:  # merge near-duplicates; keep the first reason
            continue
        cuts.append({"t": round(x, 2), "reason": reason, "silence": gap_after(x)})
    return cuts


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    c = make_cuts(pdir)
    (pdir / "cuts.json").write_text(json.dumps({"cuts": c}, indent=1), encoding="utf-8")
    print(f"cuts={len(c)}  first3={c[:3]}")
