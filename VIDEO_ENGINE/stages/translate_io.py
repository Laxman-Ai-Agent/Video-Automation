"""Telugu segments -> English with the SAME timestamps.
  python -m backend.translate_io projects/demo prepare   -> translate_input.txt (id, time, Telugu)
  python -m backend.translate_io projects/demo merge     -> transcript_en.json (needs translation.json from /plan)
translation.json: {"segments":[{"id":0,"en":"..."}]}. Telugu stays in transcript.json (reference only)."""
import json
import sys
from pathlib import Path

from pydantic import BaseModel

from . import config
from .transcribe import load_transcript


class ENSegment(BaseModel):
    id: int
    start: float
    end: float
    te: str
    en: str


class ENTranscript(BaseModel):
    duration: float
    segments: list[ENSegment]


def prepare(pdir: Path) -> str:
    t = load_transcript(pdir)
    lines = [f"{s.id} [{s.start:.2f}-{s.end:.2f}] {s.text}" for s in t.segments]
    txt = "Translate each Telugu line to clean English (keep meaning, fix obvious ASR slips). Keep ids.\n" + "\n".join(lines) + "\n"
    (pdir / "translate_input.txt").write_text(txt, encoding="utf-8")
    return txt


def merge(pdir: Path) -> ENTranscript:
    t = load_transcript(pdir)
    tr = {x["id"]: x["en"] for x in json.loads((pdir / "translation.json").read_text(encoding="utf-8"))["segments"]}
    missing = [s.id for s in t.segments if s.id not in tr]
    if missing:
        raise ValueError(f"translation.json missing segment ids {missing}")
    en = ENTranscript(duration=t.duration, segments=[
        ENSegment(id=s.id, start=s.start, end=s.end, te=s.text, en=tr[s.id]) for s in t.segments])
    (pdir / "transcript_en.json").write_text(en.model_dump_json(indent=1), encoding="utf-8")
    return en


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    if sys.argv[2] == "prepare":
        print(f"translate_input.txt: {prepare(pdir).count(chr(10)) - 1} segments")
    else:
        print(f"transcript_en.json: {len(merge(pdir).segments)} segments")
