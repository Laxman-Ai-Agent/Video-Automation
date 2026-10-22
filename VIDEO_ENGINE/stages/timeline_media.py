"""Read-only media for the Timeline page: the narration waveform and the narration file. Nothing here builds, approves or renders anything."""
from __future__ import annotations

import array
import json
import re
import wave
from pathlib import Path

PER_SECOND = 20             # peak buckets per second of audio
CACHE = "timeline_waveform.json"


def audio_file(pdir: Path, source_ref: str) -> Path | None:
    """The project audio named by the timeline (a plain file name inside the project folder), or None."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", source_ref or ""):
        return None
    f = pdir / source_ref
    return f if f.is_file() else None


def waveform(pdir: Path) -> dict | None:
    """Peaks (0..1, `PER_SECOND` per second) of the 16 kHz mono wav the analyzer made from the project audio; cached by file size and time. None when that wav does not exist."""
    src = pdir / "audio_16k.wav"
    if not src.is_file():
        return None
    st = src.stat()
    key = f"{st.st_size}:{int(st.st_mtime)}"
    cache = pdir / CACHE
    try:
        c = json.loads(cache.read_text(encoding="utf-8"))
        if c.get("key") == key:
            return c
    except (OSError, ValueError):
        pass
    with wave.open(str(src), "rb") as w:
        rate, n, width, ch = w.getframerate(), w.getnframes(), w.getsampwidth(), w.getnchannels()
        if width != 2:
            return None
        pcm = array.array("h")
        pcm.frombytes(w.readframes(n))
    step = max(1, rate // PER_SECOND) * ch
    peaks = [max((abs(v) for v in pcm[i:i + step]), default=0) for i in range(0, len(pcm), step)]
    top = max(peaks, default=0) or 1
    out = {"key": key, "per_second": PER_SECOND, "duration_seconds": round(n / rate, 3), "peaks": [round(p / top, 3) for p in peaks]}
    try:
        cache.write_text(json.dumps(out), encoding="utf-8")
    except OSError:
        pass                                  # a read-only folder only loses the cache
    return out
