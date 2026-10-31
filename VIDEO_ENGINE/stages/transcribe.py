"""python -m backend.transcribe projects/demo"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from pydantic import BaseModel

from . import config
from .audio_utils import chunk_points, duration, is_silent, to_wav16k
from .diagnose import UserProblem


class Word(BaseModel):
    w: str
    start: float
    end: float
    p: float | None = None          # Whisper's own probability of this word (0-1); None = not recorded (transcripts made before it was saved)
    timing: str | None = None       # None = Whisper's own timestamp; "aligned" = a corrected word re-aligned against the audio (model-inferred); "estimated" = a corrected word placed inside the span of the words it replaced (NOT measured)
    edit: str | None = None         # "llm" for a word written by the correction stage; None = spoken text as the ASR heard it


class Segment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    words: list[Word]


class Transcript(BaseModel):
    language: str
    duration: float
    segments: list[Segment]


def find_audio(pdir: Path) -> Path:
    for f in sorted(pdir.glob("audio.*")):
        if f.suffix.lower() in {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}:
            return f
    raise FileNotFoundError(f"no audio.* in {pdir}")


TRANSCRIPT_FILES = ("transcript_fixed.json", "transcript_corrected.json", "audio_analysis.json", "transcript.json")     # user correction > reviewed (LLM) correction > Audio Analyzer output JSON > raw ASR output


def transcript_from_analysis_json(path: Path) -> Transcript | None:
    """Extracts the LLM-corrected Transcript from an Audio Analyzer output JSON (audio_analysis.json)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        utterances = data.get("utterances", [])
        if not utterances:
            return None
        segments = []
        for idx, u in enumerate(utterances):
            words = [
                Word(
                    w=str(w.get("text", w.get("w", ""))),
                    start=float(w.get("start_seconds", w.get("start", 0.0))),
                    end=float(w.get("end_seconds", w.get("end", 0.0))),
                    p=w.get("confidence", w.get("p")),
                    timing=w.get("timing"),
                    edit=w.get("edit"),
                )
                for w in u.get("words", [])
            ]
            segments.append(
                Segment(
                    id=int(u.get("id", idx)),
                    start=float(u.get("start_seconds", 0.0)),
                    end=float(u.get("end_seconds", 0.0)),
                    text=str(u.get("text", "")),
                    words=words,
                )
            )
        dur = float(data.get("source", {}).get("duration_seconds") or (segments[-1].end if segments else 0.0))
        lang = str(data.get("transcription", {}).get("language", {}).get("code", "te"))
        return Transcript(language=lang, duration=dur, segments=segments)
    except Exception:
        return None


def transcript_inputs(pdir: Path) -> list[Path]:
    """Every file the effective transcript can come from (for stage fingerprints)."""
    return [pdir / n for n in TRANSCRIPT_FILES] + [pdir / "audio-analysis.json"]


def load_transcript(pdir: Path) -> Transcript:
    """The effective transcript: user fix (transcript_fixed.json) > LLM-corrected (transcript_corrected.json) > raw ASR (transcript.json) > Audio Analyzer output JSON (audio_analysis.json)."""
    for n in ("transcript_fixed.json", "transcript_corrected.json", "transcript.json"):
        if (pdir / n).exists():
            return Transcript.model_validate_json((pdir / n).read_text(encoding="utf-8"))
    for n in ("audio_analysis.json", "audio-analysis.json"):
        if (pdir / n).exists():
            t = transcript_from_analysis_json(pdir / n)
            if t is not None:
                return t
    raise FileNotFoundError(f"no transcript in {pdir}")


PARTIAL = "transcript.partial.json"      # the chunks Whisper finished in a run that was interrupted (deleted when the transcript is complete)


def _load_partial(pf: Path, key: str, chunks: list[list[float]]) -> tuple[int, list[Segment]]:
    """(chunks done, their segments) from an interrupted run of the same audio, model and chunking; nothing otherwise."""
    try:
        d = json.loads(pf.read_text(encoding="utf-8"))
        if d["key"] == key and d["chunks"] == chunks and 0 < d["done"] <= len(chunks):
            return d["done"], [Segment.model_validate(s) for s in d["segments"]]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return 0, []


def _save_partial(pf: Path, key: str, chunks: list[list[float]], done: int, out: list[Segment]) -> None:
    """Atomic (temp file + rename): a kill during the write never leaves a half-written checkpoint."""
    tmp = pf.with_suffix(".json.part")
    tmp.write_text(json.dumps({"key": key, "chunks": chunks, "done": done, "segments": [s.model_dump() for s in out]}, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, pf)


def transcribe(pdir: Path, progress=None) -> Transcript:
    """progress(percent) is optional; job.json is owned by backend/pipeline.py."""
    audio = find_audio(pdir)
    h = hashlib.sha1(audio.read_bytes()).hexdigest() + f":{config.WHISPER_MODEL}:{config.WHISPER_VERSION}"
    hf, tf = pdir / ".audio.sha1", pdir / "transcript.json"
    if tf.exists() and hf.exists() and hf.read_text() == h:
        print("cache hit: transcript.json unchanged")
        return Transcript.model_validate_json(tf.read_text(encoding="utf-8"))

    # Check if a remote transcript exists on Google Drive (Colab GPU execution)
    try:
        from SYSTEM.core import drive_sync
        if not tf.exists() and drive_sync.is_drive_connected():
            print("Google Drive connected: checking for cloud transcript...")
            synced = drive_sync.sync_transcript_from_drive(pdir)
            if synced and synced.exists():
                print("Successfully fetched transcript.json from Google Drive!")
                hf.write_text(h)
                return Transcript.model_validate_json(synced.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Drive sync check skipped: {e}")

    from .audio_analysis import probe
    probe(audio)   # empty / damaged / no audio stream: a clear error before any expensive work

    from faster_whisper import WhisperModel  # imported late: config sets cache env first
    from faster_whisper.audio import decode_audio

    wav = to_wav16k(audio, pdir / "audio_16k.wav")
    total = duration(wav)
    if is_silent(wav):   # checked before the model loads: minutes of work for nothing otherwise
        raise UserProblem("The audio is silent (no sound at all). Check that the right file was uploaded.")
    model = WhisperModel(config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE,
                         local_files_only=config.WHISPER_LOCAL_ONLY)
    pcm = decode_audio(str(wav), sampling_rate=16000)
    chunks = [list(c) for c in chunk_points(wav, config.WHISPER_CHUNK_MAX, config.WHISPER_CHUNK_MIN)]
    pf = pdir / PARTIAL
    done, out = _load_partial(pf, h, chunks)
    if done and progress:
        progress(100 * chunks[done - 1][1] / total)      # a resumed run shows where it continues, not 0%
    for i in range(done, len(chunks)):
        a, b = chunks[i]
        segs, _ = model.transcribe(pcm[int(a * 16000):int(b * 16000)], language="te", word_timestamps=True,
                                   vad_filter=False, condition_on_previous_text=False)
        for s in segs:
            words = [Word(w=w.word.strip(), start=a + w.start, end=a + w.end, p=round(float(w.probability), 3)) for w in (s.words or [])]
            # Whisper times the words by cross-attention and the segment by its own timestamp tokens: the last word can end a little after the segment (seen: 19.58 vs 19.42, while the next segment
            # starts at 19.58). A segment never ends before its own last word.
            out.append(Segment(id=len(out), start=a + s.start, end=max(a + s.end, words[-1].end) if words else a + s.end, text=s.text.strip(), words=words))
        _save_partial(pf, h, chunks, i + 1, out)           # a restart or crash continues after this chunk
        if progress:
            progress(100 * b / total)
    if not any(s.words for s in out):   # nothing is written: an empty transcript would look like a finished step
        pf.unlink(missing_ok=True)
        raise UserProblem("No speech was found in the audio. Check that it is Telugu speech and not music or noise.")
    t = Transcript(language="te", duration=round(total, 3), segments=out)
    tf.write_text(t.model_dump_json(indent=1), encoding="utf-8")
    hf.write_text(h)
    pf.unlink(missing_ok=True)
    return t


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    t0 = time.time()
    t = transcribe(pdir)
    print(f"segments={len(t.segments)} words={sum(len(s.words) for s in t.segments)} "
          f"duration={t.duration:.1f}s took={time.time() - t0:.1f}s")
