"""Reading a media file the same way for Render Video (Stage 13, its output verification) and Final QC (Stage 14): container and stream metadata from ffprobe, rational frame rates, a SHA-256 of the file.
Nothing is written. A value the tool cannot determine is None (never guessed), so a caller can say "not verifiable" instead of "passed"."""
from __future__ import annotations

import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

PROBE_TIMEOUT = 120
_sha_memo: dict = {}


class ProbeError(Exception):
    """The file cannot be read as media (missing, empty, not a container, truncated header)."""


def tool_version(tool: str = "ffprobe") -> str:
    try:
        r = subprocess.run([tool, "-version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return (r.stdout.splitlines() or [""])[0][:80]
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def rate(text: str | None) -> Fraction | None:
    """'30/1' -> Fraction(30); '0/0' or junk -> None."""
    try:
        f = Fraction(text or "")
        return f if f > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


def sha256_file(path: Path) -> str:
    """Memoised by (path, size, mtime): hashing a 30 MB video once per change is cheap, once per status poll is not."""
    st = path.stat()
    key = (str(path.resolve()), st.st_size, st.st_mtime_ns)
    if _sha_memo.get("key") == key:
        return _sha_memo["sha"]
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    _sha_memo.update(key=key, sha=h.hexdigest())
    return _sha_memo["sha"]


def probe(path: Path) -> dict:
    """{container, duration, size, video: {...}|None, audio: {...}|None, stream_count, tool}. Raises ProbeError when the file is not readable as media."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ProbeError(f"{path.name} does not exist or is empty")
    cmd = ["ffprobe", "-v", "error", "-show_entries",
           "stream=index,codec_type,codec_name,width,height,pix_fmt,r_frame_rate,avg_frame_rate,nb_frames,duration,start_time,sample_rate,channels,bit_rate:format=format_name,duration,size,start_time",
           "-of", "json", str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=PROBE_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as e:
        raise ProbeError(f"ffprobe could not run: {e}") from e
    if r.returncode != 0:
        raise ProbeError("ffprobe could not read the file: " + next((x.strip() for x in reversed(r.stderr.splitlines()) if x.strip()), "no details")[:200])
    try:
        info = json.loads(r.stdout)
    except ValueError as e:
        raise ProbeError("ffprobe gave no usable answer") from e
    streams = info.get("streams", [])
    fmt = info.get("format", {})

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    def pick(kind):
        s = next((x for x in streams if x.get("codec_type") == kind), None)
        if s is None:
            return None
        out = {"codec": s.get("codec_name"), "duration": num(s.get("duration")), "start_time": num(s.get("start_time")), "bit_rate": num(s.get("bit_rate"))}
        if kind == "video":
            fr = rate(s.get("r_frame_rate"))
            out.update(width=s.get("width"), height=s.get("height"), pix_fmt=s.get("pix_fmt"), frame_rate=str(fr) if fr else None, frame_rate_value=float(fr) if fr else None,
                       avg_frame_rate=s.get("avg_frame_rate"), nb_frames=int(s["nb_frames"]) if str(s.get("nb_frames", "")).isdigit() else None)
        else:
            out.update(sample_rate=int(s["sample_rate"]) if str(s.get("sample_rate", "")).isdigit() else None, channels=s.get("channels"))
        return out

    return {"container": fmt.get("format_name"), "duration": num(fmt.get("duration")), "size": int(fmt["size"]) if str(fmt.get("size", "")).isdigit() else None,
            "video": pick("video"), "audio": pick("audio"), "stream_count": len(streams), "tool": tool_version("ffprobe")}
