import re
import subprocess
from pathlib import Path

from .config import SILENCE_DB, SILENCE_MIN, SILENT_DB
from .diagnose import UserProblem


def _run(args: list[str]) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as e:
        raise UserProblem(f"{args[0]} was not found. Install ffmpeg and make sure it is on PATH.") from e
    if r.returncode != 0:
        last = next((x.strip() for x in reversed(r.stderr.splitlines()) if x.strip()), "no details")
        raise UserProblem(f"{args[0]} could not read the audio (is the file damaged or not an audio file?): {last[:200]}")
    return r.stderr + r.stdout


def to_wav16k(src: Path, dst: Path) -> Path:
    _run(["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(dst)])
    return dst


def duration(path: Path) -> float:
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    try:
        seconds = float(out.strip().splitlines()[-1])
    except (IndexError, ValueError):
        seconds = 0.0
    if seconds <= 0:
        raise UserProblem("The audio has no readable length (the file is empty or damaged).")
    return seconds


def max_volume_db(path: Path) -> float | None:
    """Loudest sample in dB (-inf = digital silence); None when ffmpeg finds no audio stream."""
    m = re.search(r"max_volume: (-?(?:[\d.]+|inf)) dB", _run(["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"]))
    return float(m.group(1)) if m else None


def integrated_loudness_lufs(path: Path) -> float | None:
    """Measures EBU R128 integrated loudness in LUFS (-inf for digital silence). None when no audio stream or error."""
    try:
        out = _run(["ffmpeg", "-i", str(path), "-af", "ebur128", "-f", "null", "-"])
        m = re.search(r"Integrated loudness:\s+I:\s+(-?(?:[\d.]+|inf))\s+LUFS", out)
        if m:
            val = m.group(1)
            return float("-inf") if "inf" in val else float(val)
    except Exception:
        pass
    return None


def is_silent(path: Path, db: float = SILENT_DB) -> bool:
    """True when the file has no sound worth transcribing (silent, or no audio stream)."""
    loudest = max_volume_db(path)
    return loudest is None or loudest < db


def silences(path: Path, min_len: float = SILENCE_MIN, db: int = SILENCE_DB) -> list[tuple[float, float]]:
    """[(start, end)] of silent stretches longer than min_len."""
    out = _run(["ffmpeg", "-i", str(path), "-af", f"silencedetect=noise={db}dB:d={min_len}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(starts, ends))


def chunk_points(path: Path, max_len: float, min_len: float) -> list[tuple[float, float]]:
    """Split speech into [(start, end)] pieces <= max_len, cutting at the quietest 50 ms frame."""
    import numpy as np
    from pydub import AudioSegment

    a = AudioSegment.from_file(path).set_channels(1)
    x = np.array(a.get_array_of_samples(), dtype=np.float32)
    hop = int(a.frame_rate * 0.05)
    n = len(x) // hop
    rms = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    total, start, out = n * 0.05, 0.0, []
    while total - start > max_len:
        lo, hi = int((start + min_len) / 0.05), int((start + max_len) / 0.05)
        cut = (lo + int(np.argmin(rms[lo:hi]))) * 0.05
        out.append((start, cut))
        start = cut
    out.append((start, total))
    return out
