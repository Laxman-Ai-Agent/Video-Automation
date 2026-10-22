"""python -m backend.transcribe projects/demo"""
import hashlib
import json
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


TRANSCRIPT_FILES = ("transcript_fixed.json", "transcript_corrected.json", "transcript.json")     # user correction > reviewed (LLM) correction > raw ASR output


def transcript_inputs(pdir: Path) -> list[Path]:
    """Every file the effective transcript can come from (for stage fingerprints)."""
    return [pdir / n for n in TRANSCRIPT_FILES]


def load_transcript(pdir: Path) -> Transcript:
    """transcript_fixed.json (user-corrected) wins over transcript_corrected.json (the reviewed correction) which wins over transcript.json (the raw ASR output, never edited)."""
    for n in TRANSCRIPT_FILES:
        if (pdir / n).exists():
            return Transcript.model_validate_json((pdir / n).read_text(encoding="utf-8"))
    raise FileNotFoundError(f"no transcript in {pdir}")


def transcribe(pdir: Path, progress=None) -> Transcript:
    """progress(percent) is optional; job.json is owned by backend/pipeline.py."""
    audio = find_audio(pdir)
    h = hashlib.sha1(audio.read_bytes()).hexdigest() + f":{config.WHISPER_MODEL}:{config.WHISPER_VERSION}"
    hf, tf = pdir / ".audio.sha1", pdir / "transcript.json"
    if tf.exists() and hf.exists() and hf.read_text() == h:
        print("cache hit: transcript.json unchanged")
        return Transcript.model_validate_json(tf.read_text(encoding="utf-8"))

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
    out: list[Segment] = []
    for a, b in chunk_points(wav, config.WHISPER_CHUNK_MAX, config.WHISPER_CHUNK_MIN):
        segs, _ = model.transcribe(pcm[int(a * 16000):int(b * 16000)], language="te", word_timestamps=True,
                                   vad_filter=False, condition_on_previous_text=False)
        for s in segs:
            words = [Word(w=w.word.strip(), start=a + w.start, end=a + w.end, p=round(float(w.probability), 3)) for w in (s.words or [])]
            # Whisper times the words by cross-attention and the segment by its own timestamp tokens: the last word can end a little after the segment (seen: 19.58 vs 19.42, while the next segment
            # starts at 19.58). A segment never ends before its own last word.
            out.append(Segment(id=len(out), start=a + s.start, end=max(a + s.end, words[-1].end) if words else a + s.end, text=s.text.strip(), words=words))
        if progress:
            progress(100 * b / total)
    if not any(s.words for s in out):   # nothing is written: an empty transcript would look like a finished step
        raise UserProblem("No speech was found in the audio. Check that it is Telugu speech and not music or noise.")
    t = Transcript(language="te", duration=round(total, 3), segments=out)
    tf.write_text(t.model_dump_json(indent=1), encoding="utf-8")
    hf.write_text(h)
    return t


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    t0 = time.time()
    t = transcribe(pdir)
    print(f"segments={len(t.segments)} words={sum(len(s.words) for s in t.segments)} "
          f"duration={t.duration:.1f}s took={time.time() - t0:.1f}s")
