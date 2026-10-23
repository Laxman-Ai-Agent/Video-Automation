"""Clear the fixable warnings of the Audio Analyzer (audio_analysis.json) and re-check, in an automated loop.

Only one warning is fixable here: `word_outside_segment`, where a word starts BEFORE its segment starts (its timing onset is moved to the first voiced sound in the audio). Words are never
corrected here: the LLM check of every word belongs to `transcript_review.refine` (one implementation).

Logs are preserved in `analysis_autofix.json`. Up to 5 attempts per run, with 5 additional attempts when explicitly requested.
Refused when a later stage already exists (Scene Segmentation ran): changing the transcript would make it stale behind the user's back."""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

from . import audio_analysis, transcribe

ROUNDS = 5
MIN_WORD = 0.08            # a word shorter than this after the move is not a word: not fixed
LOG = "analysis_autofix.json"


def blocked(pdir: Path) -> str | None:
    if (pdir / "scene_segmentation.json").exists():
        return "Scene Segmentation already ran: changing the transcript now would make it stale"
    return None


def _voiced(pdir: Path):
    from faster_whisper.audio import decode_audio

    from .transcript_review import _voiced as voiced
    wav = pdir / "audio_16k.wav"
    if not wav.exists():
        return None
    return voiced(decode_audio(str(wav), sampling_rate=16000))


def _fix_once(pdir: Path, warnings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Apply timing onset fixes. Returns (changes, not_fixed)."""
    from .transcript_review import _onset
    t = transcribe.load_transcript(pdir)
    target = next((n for n in transcribe.TRANSCRIPT_FILES if (pdir / n).exists()), "transcript.json")
    if target == "transcript.json":
        return [], [{**w, "why_not_fixed": "the transcript is the raw ASR output, which is never edited"} for w in warnings]
    flat = [(s, k, w) for s in t.segments for k, w in enumerate(s.words)]
    v = None
    changes, left = [], []
    for wn in warnings:
        m = re.match(r"word (\d+) ", wn.get("message", ""))
        if wn.get("code") != "word_outside_segment" or not m or int(m.group(1)) >= len(flat):
            left.append(wn)
            continue
        s, k, w = flat[int(m.group(1))]
        if not w.start < s.start - 0.05:
            left.append({**wn, "why_not_fixed": "the word does not start before its segment"})
            continue
        if v is None:
            v = _voiced(pdir) or False
        if not v:
            left.append({**wn, "why_not_fixed": "no audio copy to measure"})
            continue
        on = _onset(v[0], v[1], s.start, w.end)
        prev_end = s.words[k - 1].end if k else 0.0
        if on is None or w.end - on < MIN_WORD or on < prev_end - 0.05:
            left.append({**wn, "why_not_fixed": "no sound found inside the word, or the move would overlap its neighbour"})
            continue
        changes.append({"word_index": int(m.group(1)), "word": w.w, "segment": s.id, "start_before": w.start, "start_after": on, "end": w.end, "evidence": "first voiced audio frame inside the segment"})
        w.start, w.timing = on, "aligned"
    if changes:
        (pdir / target).write_text(t.model_dump_json(indent=1), encoding="utf-8")
    return changes, left


_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


class Busy(Exception):
    """A fix loop is already running for this project (a second request must not start another)."""


def _run_key(pdir: Path) -> str:
    """One analysis run = one raw ASR output: a new analysis writes a new transcript.json, so the attempt count starts again."""
    st = (pdir / "transcript.json").stat()
    return f"{st.st_mtime_ns}:{st.st_size}"


def _log(pdir: Path) -> dict:
    try:
        return json.loads((pdir / LOG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def run(pdir: Path, rounds: int = ROUNDS, additional: bool = False) -> dict:
    """The loop: analyse -> fix what is fixable -> analyse again. At most rounds attempts per run,
    or up to 5 additional attempts when additional=True. Status: clean | warnings_remain | exhausted | errors | blocked."""
    with _guard:
        lock = _locks.setdefault(pdir.name, threading.Lock())
    if not lock.acquire(blocking=False):
        raise Busy(pdir.name)
    try:
        key = _run_key(pdir)
        prev = _log(pdir)
        prev_attempts = prev.get("attempts", 0) if prev.get("run_key") == key else 0
        rounds_allowed = rounds if additional else max(0, rounds - prev_attempts)
        attempts = 0 if additional else prev_attempts
        current_attempt = 0
        history = prev.get("changes", []) if prev.get("run_key") == key else []
        why = blocked(pdir)
        data = audio_analysis.write(pdir)
        out = {"status": "clean", "run_key": key, "attempts": attempts, "rounds": 0, "changes": history, "remaining": [], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        left: list[dict] = []
        if why:
            out.update(status="blocked" if data["validation"]["warnings"] else "clean", remaining=data["validation"]["warnings"], reason=why)
            return out

        while data["validation"]["warnings"] and current_attempt < rounds_allowed:
            current_attempt += 1
            attempts += 1
            out["rounds"] += 1

            changes, left = _fix_once(pdir, data["validation"]["warnings"])        # timing onset fixes from the audio
            if not changes:
                break

            out["changes"] += changes
            data = audio_analysis.write(pdir)

        warnings = data["validation"]["warnings"]
        reasons = {w["message"]: w.get("why_not_fixed") for w in left}
        out["remaining"] = [{**w, "why_not_fixed": reasons.get(w["message"]) or ("the attempts for this analysis run are used up" if attempts >= rounds else "no automatic fix applies to this warning")} for w in warnings]
        out["attempts"] = min(rounds, current_attempt if additional else attempts)
        out["max_attempts"] = rounds
        out["status"] = "errors" if data["validation"]["errors"] else "clean" if not warnings else "exhausted" if (current_attempt if additional else attempts) >= rounds else "warnings_remain"
        (pdir / LOG).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        return out
    finally:
        lock.release()
