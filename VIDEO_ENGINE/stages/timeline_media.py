"""Read-only media for the Timeline page: the narration waveform, the narration file and the thumbnail sheet of the rendered video. Nothing here builds, approves or renders anything (the
only things written are caches that can be made again)."""
from __future__ import annotations

import array
import json
import math
import os
import re
import shutil
import subprocess
import threading
import wave
from pathlib import Path

from . import config

PER_SECOND = 20             # peak buckets per second of audio
CACHE = "timeline_waveform.json"
THUMBS, THUMBS_META = "timeline_thumbs.jpg", "timeline_thumbs.json"
TILE_H, COLS, MAX_TILES = 180, 10, 300          # one picture per second (fewer for a long video) in a sheet of 10 columns
_thumbs_lock = threading.Lock()                 # two page loads never run ffmpeg twice for the same video


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


def thumbnails(pdir: Path, video: Path, key: str, duration_s: float) -> dict | None:
    """One JPEG sheet of small frames of the rendered video, one per `interval_s` seconds, read left to right and top to bottom, and the numbers to cut it up:
    {key, interval_s, cols, rows, count, tile_w, tile_h}. Cached for the video's hash (`key`); a new render makes a new sheet. None when ffmpeg is missing or fails: the page then keeps the stills."""
    exe = shutil.which("ffmpeg")
    if not exe or duration_s <= 0:
        return None
    interval = max(1, math.ceil(duration_s / MAX_TILES))
    count = math.ceil(duration_s / interval)
    rows = math.ceil(count / COLS)
    meta_f, sheet = pdir / THUMBS_META, pdir / THUMBS
    with _thumbs_lock:
        try:
            c = json.loads(meta_f.read_text(encoding="utf-8"))
            if c.get("key") == key and c.get("interval_s") == interval and sheet.is_file():
                return c
        except (OSError, ValueError):
            pass
        tmp = pdir / "timeline_thumbs.tmp.jpg"
        r = subprocess.run([exe, "-v", "error", "-y", "-i", str(video), "-vf", f"fps=1/{interval},scale=-2:{TILE_H},tile={COLS}x{rows}", "-frames:v", "1", "-q:v", "5", str(tmp)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, creationflags=config.LOW_PRIORITY)
        if r.returncode != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            return None
        from PIL import Image
        with Image.open(tmp) as im:
            width, height = im.size
        os.replace(tmp, sheet)
        out = {"key": key, "interval_s": interval, "cols": COLS, "rows": rows, "count": count, "tile_w": width // COLS, "tile_h": height // rows}
        meta_f.write_text(json.dumps(out), encoding="utf-8")
        return out
