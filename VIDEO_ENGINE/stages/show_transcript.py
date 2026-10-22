"""python -m backend.show_transcript projects/demo  (uses transcript_fixed.json if present)"""
import sys

from . import config
from .transcribe import load_transcript

if __name__ == "__main__":
    t = load_transcript(config.project_dir(sys.argv[1]))
    for s in t.segments:
        print(f"{s.id:>3} [{s.start:7.2f}-{s.end:7.2f}] {s.text}")
