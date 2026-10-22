"""python -m backend.plan_input projects/demo -> plan_input.txt (compact planner input)."""
import json
import sys
from pathlib import Path

from . import config, scene_segmentation
from .translate_io import ENTranscript

def build(pdir: Path) -> str:
    """English text (transcript_en.json) with original timestamps, grouped by cut candidates."""
    en = ENTranscript.model_validate_json((pdir / "transcript_en.json").read_text(encoding="utf-8"))
    seg = scene_segmentation.load_fresh(pdir)               # the user ran Scene Segmentation and it matches the transcript: its scenes are the candidates
    cuts = [s["start_time"] for s in seg["scenes"][1:]] if seg else [c["t"] for c in json.loads((pdir / "cuts.json").read_text(encoding="utf-8"))["cuts"]]
    bounds = [0.0, *cuts, en.duration]
    out = [f"duration={en.duration:.2f}s (narration translated from Telugu; plan in English)",
           ("Scene Segmentation already decided the scenes below from the meaning of the narration: make exactly one scene for each line S1, S2, ... (boundaries: 0, duration, or these starts): "
            if seg else "Cut points (scene boundaries must be 0, duration, or one of these): ") + ", ".join(f"{c:.2f}" for c in cuts),
           "", "English narration by time (start-end):"]
    out += [f"[{s.start:.1f}-{s.end:.1f}] {s.en}" for s in en.segments]
    if seg:
        out += ["", "Scenes decided by Scene Segmentation (one planned scene each):"]
        for i, (a, b) in enumerate(zip(bounds, bounds[1:]), 1):
            sc = seg["scenes"][i - 1]
            out.append(f"S{i} {a:.2f}-{b:.2f} ({b - a:.1f}s)" + (f" beat: {sc['semantic_beat']}" if sc.get("semantic_beat") else ""))
    else:
        out += ["", "Candidate segments between cuts (merge by meaning):"]
        for i, (a, b) in enumerate(zip(bounds, bounds[1:]), 1):
            out.append(f"C{i} {a:.2f}-{b:.2f} ({b - a:.1f}s)")
    return chr(10).join(out) + chr(10)


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    txt = build(pdir)
    (pdir / "plan_input.txt").write_text(txt, encoding="utf-8")
    print(f"plan_input.txt: {len(txt)} chars, {txt.count(chr(10))} lines")
