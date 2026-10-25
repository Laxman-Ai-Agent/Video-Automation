"""audio_analysis.json: what the Audio Analyzer measured and produced, in one inspectable file (additive; transcript.json and cuts.json stay as they are).
Every value says where it comes from: ffprobe / ffmpeg (measured), Whisper (model output), config (set by the project) or null (not available). Nothing is invented.
Scene Segmentation is a separate stage: nothing here decides scenes.   python -m backend.audio_analysis <project id>"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from . import config
from .audio_utils import _run
from .audio_utils import duration as probe_duration
from .audio_utils import silences
from .diagnose import UserProblem
from .transcribe import find_audio, load_transcript

SCHEMA = "audio-analysis-2"      # additive over audio-analysis-1: review, quality, caching, 14 stages, word confidence/timing
TOL = 0.5          # seconds a word end may pass the probed duration (decoder rounding)
CLIP_SHARE = 0.0001    # share of the samples at full scale (ffmpeg volumedetect histogram_0db) from which the audio counts as clipped: 0.01%
(S_VALID, S_META, S_PRE, S_LANG, S_ASR, S_VOCAB, S_CONF, S_LLM, S_ALIGN, S_INTEGRITY, S_PAUSE, S_QUALITY, S_FINAL, S_CACHE) = STAGES = (
    "Audio File Validation", "Audio Metadata Extraction", "Audio Preprocessing", "Language & Speech Detection", "Speech-to-Text (ASR)", "Telugu + English Technical Vocabulary",
    "Confidence-Based Correction", "Raw vs Corrected Transcript (LLM)", "Word-Level Alignment", "Word Timestamp Integrity", "Pause & Speech Rhythm Analysis",
    "Audio Quality & Uncertainty Detection", "Final Audio Analysis Validation", "Caching & Resume")      # Caching & Resume is shared by all stages, not a processing step


def probe(audio: Path) -> dict:
    """Measured facts of the file (ffprobe). Raises UserProblem for an empty, unreadable or audio-less file."""
    if not audio.exists() or audio.stat().st_size == 0:
        raise UserProblem("The audio file is empty or missing. Upload it again.")
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,sample_rate,channels:format=duration,format_name", "-of", "json", str(audio)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as e:
        raise UserProblem("ffprobe was not found. Install ffmpeg and make sure it is on PATH.") from e
    try:
        info = json.loads(r.stdout or "{}")
    except ValueError:
        info = {}
    if r.returncode != 0 or not info:
        raise UserProblem("The audio could not be read (the file is damaged or not an audio file).")
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not a:
        raise UserProblem("The file has no audio stream. Upload an audio file.")
    try:
        seconds = float(info.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds <= 0:
        raise UserProblem("The audio has no readable length (the file is empty or damaged).")
    return {"file": audio.name, "size_bytes": audio.stat().st_size, "duration_seconds": round(seconds, 3), "codec": a.get("codec_name"),
            "container": info.get("format", {}).get("format_name"), "sample_rate_hz": int(a["sample_rate"]) if a.get("sample_rate") else None,
            "channels": a.get("channels"), "metadata_source": "ffprobe"}


def check_timing(utterances: list[dict], duration: float) -> tuple[list[dict], list[dict]]:
    """(errors, warnings) of the timestamps: word and segment bounds, order, segment boundaries, empty or untimed segments."""
    err, warn = [], []
    add = lambda lst, code, msg: lst.append({"stage": S_INTEGRITY, "code": code, "message": msg})
    prev_end = 0.0
    for u in utterances:
        if not u["words"]:
            add(warn, "segment_without_words", f"segment {u['id']} has text but no word timings")
        if not 0 <= u["start_seconds"] <= u["end_seconds"] <= duration + TOL:
            add(err, "segment_out_of_range", f"segment {u['id']} ({u['start_seconds']}s - {u['end_seconds']}s) is outside the audio ({duration}s)")
        if u["start_seconds"] < prev_end - 0.05:
            add(warn, "segment_overlap", f"segment {u['id']} starts at {u['start_seconds']}s before the previous segment ended ({prev_end}s)")
        prev_end = max(prev_end, u["end_seconds"])
        prev = u["start_seconds"]
        for w in u["words"]:
            if not 0 <= w["start_seconds"] <= w["end_seconds"] <= duration + TOL:
                add(err, "word_out_of_range", f"word {w['index']} “{w['text']}” has times outside the audio or start after end")
            elif w["start_seconds"] < prev - 0.05:
                add(warn, "word_out_of_order", f"word {w['index']} “{w['text']}” starts before the previous word ended")
            elif not u["start_seconds"] - 0.05 <= w["start_seconds"] <= u["end_seconds"] + 0.05:
                add(warn, "word_outside_segment", f"word {w['index']} “{w['text']}” lies outside its segment {u['id']}")
            prev = max(prev, w["end_seconds"])
    return err[:20], warn[:20]


def quality(audio: Path) -> dict:
    """Loudness facts from ffmpeg volumedetect (measured). Noise level is not measured."""
    try:
        out = _run(["ffmpeg", "-i", str(audio), "-af", "volumedetect", "-f", "null", "-"])
    except UserProblem:
        return {"status": "unavailable", "max_volume_db": None, "mean_volume_db": None}
    g = lambda k: (lambda m: float(m.group(1)) if m else None)(re.search(k + r": (-?[\d.]+) dB", out))
    count = lambda k: (lambda m: int(m[-1]) if m else None)(re.findall(k + r": (\d+)", out))      # the last match: ffmpeg also prints the line for a filter instance that saw no samples
    total, top = count("n_samples"), count("histogram_0db")
    return {"status": "measured", "max_volume_db": g("max_volume"), "mean_volume_db": g("mean_volume"), "noise_level": "not measured",
            "peak_samples": top, "peak_share": round(top / total, 6) if total and top is not None else None}


def _json(f: Path):
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except (OSError, ValueError):
        return None


def segment_end_checks(t, pdir: Path) -> tuple[dict[int, float], list[dict]]:
    """A transcript segment whose end is before the end of its last word (seen: segment 3 ends 19.42 s, its last word 19.58 s). Nothing is changed until the audio has been looked at:
    - sound in the gap AND the next segment starts where the last word ends: the word times are right, the segment end is shown as the end of its last word (`segment_end_adjusted`);
    - silence in the gap (real example: no sound from 19.45 s to 19.62 s, speech ends at 19.40 s): the segment end matches the audio and the last word end reaches into the pause: both stay as the
      source has them, a note says so (`word_end_in_silence`; the transcript file is never edited and no timestamp is invented);
    - anything else (no audio copy to look at, word times not continuous): a WARNING that it could not be confirmed, nothing changed (`segment_end_unconfirmed`)."""
    fixes, notes = {}, []
    pcm = voiced = None
    wav = pdir / "audio_16k.wav"
    for k, s in enumerate(t.segments):
        if not s.words or s.words[-1].end - s.end <= 0.05 or s.words[-1].timing == "sentence":
            continue
        end = s.words[-1].end
        nxt = t.segments[k + 1].words[0].start if k + 1 < len(t.segments) and t.segments[k + 1].words else t.duration
        chain = abs(nxt - end) <= 0.05 and end <= t.duration + TOL
        sound = None
        if wav.exists():
            try:
                if pcm is None:
                    from faster_whisper.audio import decode_audio
                    from .transcript_review import _voiced
                    pcm = decode_audio(str(wav), sampling_rate=16000)
                    voiced = _voiced(pcm)
                hop, flags = voiced
                i, j = int(s.end / hop), max(int(s.end / hop) + 1, int(end / hop))
                sound = bool(sum(bool(x) for x in flags[i:j]) * 2 >= max(1, j - i))
            except Exception:
                sound = None
        base = {"segment": s.id, "segment_end": round(s.end, 3), "last_word_end": round(end, 3), "next_start": round(nxt, 3), "continuous_with_next": chain,
                "audio_check": "sound in the gap" if sound else "silence in the gap" if sound is False else "not checked (no audio copy)"}
        head = f"segment {s.id} ends at {s.end:.2f}s but its last word ends at {end:.2f}s (the next segment starts at {nxt:.2f}s)"
        if chain and sound:
            fixes[s.id] = round(end, 3)
            notes.append({**base, "code": "segment_end_adjusted", "message": f"{head}; the audio has sound in the gap, so the segment end is shown as the end of its last word"})
        elif sound is False:
            notes.append({**base, "code": "word_end_in_silence", "message": f"{head}; the audio has no sound in the gap: the segment end matches the audio and the last word time reaches into the pause. Both are kept as the source has them"})
        else:
            notes.append({**base, "code": "segment_end_unconfirmed", "message": f"{head}; this could not be confirmed ({base['audio_check']}{'' if chain else ', word times not continuous'}): nothing was changed"})
    return fixes, notes


def build(pdir: Path, progress=None) -> dict:
    say = progress or (lambda p, eta=None: None)
    audio = find_audio(pdir)
    src = probe(audio)
    dur = src["duration_seconds"]
    t = load_transcript(pdir)
    raw = _json(pdir / "transcript.json") or {}
    review = _json(pdir / "transcript_review.json")
    edited = (pdir / "transcript_fixed.json").exists()
    corrected = review is not None and review.get("corrected_file") is not None and (pdir / "transcript_corrected.json").exists()
    utterances, n = [], 0
    end_fixes, end_notes = segment_end_checks(t, pdir)
    for s in t.segments:
        words = []
        for w in s.words:
            words.append({"index": n, "text": w.w, "start_seconds": round(w.start, 3), "end_seconds": round(w.end, 3), "confidence": w.p,
                          "timing": w.timing or "measured", "edit": w.edit})
            n += 1
        utterances.append({"utterance_id": f"utt_{s.id + 1:03d}", "id": s.id, "text": s.text, "start_seconds": round(s.start, 3), "end_seconds": end_fixes.get(s.id, round(s.end, 3)),
                           "boundary_source": "whisper_segment", "alignment_status": "word_timestamps" if words else "unavailable", "words": words})
    add = lambda lst, stage, code, msg: lst.append({"stage": stage, "code": code, "message": msg})
    errors, warnings = check_timing(utterances, dur)                       # stage 10
    for nt in end_notes:
        if nt["code"] == "segment_end_unconfirmed":
            warnings.append({"stage": S_INTEGRITY, "code": nt["code"], "message": nt["message"]})
    say(25)
    if abs(t.duration - dur) > TOL:
        add(warnings, S_META, "duration_mismatch", f"transcript duration {t.duration}s differs from the probed {dur}s")
    if src["sample_rate_hz"] is None or src["channels"] is None:
        add(warnings, S_META, "metadata_incomplete", "sample rate or channel count could not be read")
    timed = sum(1 for u in utterances if u["words"])
    align = "unavailable" if not timed else "word_timestamps" if timed == len(utterances) else "partial"
    if align != "word_timestamps":
        add(warnings, S_ALIGN, "alignment_incomplete", "some or all segments have no word times")
    if edited:
        add(warnings, S_ASR, "transcript_edited", "transcript_fixed.json (a user correction) is used instead of the ASR output")
    try:                                                                   # stage 11
        pauses = [{"start_seconds": round(a, 3), "end_seconds": round(b, 3), "duration_seconds": round(b - a, 3), "kind": "silence", "source": "ffmpeg_silencedetect"} for a, b in silences(audio)]
        pause_status = "measured"
    except UserProblem as e:
        pauses, pause_status = [], "unavailable"
        add(warnings, S_PAUSE, "pause_detector_failed", str(e)[:160])
    say(50)
    q = quality(audio)                                                     # stage 12
    conf = (review or {}).get("confidence") or {}
    flagged = len(conf.get("flagged", []))
    unresolved = len((review or {}).get("unresolved", []))
    total_words = max(1, n)
    mx, mean = q.get("max_volume_db"), q.get("mean_volume_db")
    share = q.get("peak_share")
    if share is not None and share >= CLIP_SHARE:           # a peak-normalized recording touches 0 dB with a few samples; clipping is many samples flattened at full scale
        add(warnings, S_QUALITY, "clipping_risk", f"{q['peak_samples']} samples ({share:.3%}) sit within 1 dB of full scale: the audio is clipped")
    elif share is None and mx is not None and mx >= -0.3:   # the sample counts were not reported: only the peak is known
        add(warnings, S_QUALITY, "clipping_risk", f"the loudest sample is {mx} dB and the sample counts were not measured: the audio may be clipped")
    if mx is not None and mx < -20:
        add(warnings, S_QUALITY, "very_quiet", f"the loudest sample is only {mx} dB")
    if q["status"] == "unavailable":
        add(warnings, S_QUALITY, "quality_unavailable", "loudness could not be measured")
    if unresolved:
        add(warnings, S_QUALITY, "uncertain_words", f"{unresolved} uncertain word(s) were not corrected and need review")
    if flagged / total_words > 0.15:
        add(warnings, S_QUALITY, "high_uncertainty", f"{flagged} of {n} words are below the confidence threshold: the recognition of this audio is unreliable")
    q.update(uncertain_words=flagged, unresolved_words=unresolved, uncertain_share=round(flagged / total_words, 3) if conf.get("status") == "available" else None)
    wav = pdir / "audio_16k.wav"
    derived = None
    if wav.exists():
        try:
            derived = round(probe_duration(wav), 3)
        except UserProblem:
            derived = None
        if derived is not None and abs(derived - dur) > TOL:
            add(warnings, S_PRE, "preprocessing_duration_changed", f"the 16 kHz copy is {derived}s, the original {dur}s")
    say(75)
    llm = (review or {}).get("llm") or {}
    llm_name = "LLM"
    try:
        from SYSTEM.core import llm_client
        llm_name = llm_client.get_public_settings().get("provider_name") or "LLM"
    except Exception:
        pass

    if unresolved:
        add(warnings, S_LLM, "unresolved_words", f"{unresolved} uncertain word(s) were not corrected and need {llm_name} review")
    if llm.get("status") in ("unavailable", "failed"):
        if unresolved > 0:
            add(warnings, S_LLM, "correction_unavailable", f"{llm_name} could not check the uncertain words, the original ASR text is kept ({llm.get('error') or llm['status']})")
        else:
            end_notes.append({"segment": None, "code": "llm_skipped_high_confidence",
                              "message": f"{llm_name} was unreachable ({llm.get('error') or llm['status']}), but all words had high confidence so raw ASR was kept."})
    corr = (review or {}).get("corrections") or []
    applied = sum(c["status"] == "applied" for c in corr)
    ck = (review or {}).get("alignment") or {}
    words_all = [w for u in utterances for w in u["words"]]
    est = sum(w["timing"] == "estimated" for w in words_all)
    n_aligned = sum(w["timing"] == "aligned" for w in words_all)
    n_edit = sum(bool(w["edit"]) for w in words_all)
    if est:                                                  # a respelled word keeps its Whisper timestamp: only words whose time is really estimated are a finding
        why = "; ".join(sorted({r.get("reason") or "" for r in ck.get("segments", []) if r.get("status") != "aligned"} - {""}))[:200]
        add(warnings, S_ALIGN, "estimated_timestamps", f"{est} corrected word(s) have ESTIMATED timestamps, not measured ones ({why or 'alignment failed'})")
    snapped = [m for r in ck.get("segments", []) for m in r.get("snapped", [])]
    for m in snapped:
        end_notes.append({"segment": None, "code": "start_moved_to_sound",
                          "message": f"corrected word “{m.get('word', '')}” started before any sound in the model's alignment; the start was moved to the first sound measured in the audio ({m.get('aligned_start')}s -> {m.get('first_sound')}s)"})
    status = "error" if errors else "warning" if warnings else "ok"
    bad = {e["stage"] for e in errors}
    warned = {w["stage"] for w in warnings}
    state = lambda name, base="completed": "failed" if name in bad else "warning" if name in warned else base
    terms = (review or {}).get("vocabulary", {}).get("terms", [])
    timings = (_json(pdir / "timings.json") or {}).get("steps", {})
    reused = [k for k in ("transcribe", "refine", "cuts") if (timings.get(k) or {}).get("status") == "fresh"]
    cache_entries = len(_json(pdir / "asr_llm_cache.json") or {})
    no_review = "the review step has not run for this project"
    llm_text = {"not_needed": (f"no uncertain words: {llm_name} was not asked" if conf.get("status") == "available" else "not run: this transcript has no word confidences, so no word can be called uncertain"),
                "applied": f"{llm_name} checked {llm.get('segments_sent')} segment(s): {applied} correction(s) applied, {len(corr) - applied} rejected",
                "cached": f"answer reused (no new call): {applied} applied, {len(corr) - applied} rejected",
                "unavailable": f"{llm_name} not available: {llm.get('error')}", "failed": f"{llm_name}'s answer could not be used: {llm.get('error')}"}.get(llm.get("status"), no_review)
    rows = [
        (S_VALID, state(S_VALID), "file readable, has an audio stream"),
        (S_META, state(S_META), f"{dur}s, {src['sample_rate_hz']} Hz, {src['channels']} ch ({src['codec']})"),
        (S_PRE, state(S_PRE), f"16 kHz mono copy for the model{'' if derived is None else f' ({derived}s)'}; the original is untouched"),
        (S_LANG, state(S_LANG), f"language '{t.language}' set by config (no detection ran); confidence unavailable"),
        (S_ASR, state(S_ASR), f"{config.WHISPER_MODEL} ({config.WHISPER_COMPUTE}, {config.WHISPER_DEVICE}): {len(raw.get('segments', []))} segments, "
                              f"{sum(len(s.get('words', [])) for s in raw.get('segments', []))} words kept as the raw transcript"),
        (S_VOCAB, state(S_VOCAB) if review else "skipped",
         f"{sum(x['kind'] == 'english' for x in terms)} English terms, {sum(x['kind'] == 'number' for x in terms)} numbers found" if review else no_review),
        (S_CONF, state(S_CONF) if review and conf.get("status") == "available" else "skipped",
         f"{flagged} word(s) below p={conf.get('threshold')} (Whisper's own probability)" if conf.get("status") == "available" else
         ("no word confidences were saved for this transcript (made before they were recorded); nothing is flagged" if review else no_review)),
        (S_LLM, state(S_LLM, "warning" if unresolved else ("completed" if llm.get("status") in ("applied", "cached") else "skipped")) if review else "skipped", llm_text),
        (S_ALIGN, state(S_ALIGN),
         "Whisper word timestamps (model-inferred, not forced alignment); " + (
             f"{n_edit} corrected word(s): {n_aligned} re-aligned against the original audio (forced alignment, model-inferred), {est} ESTIMATED (not measured), "
             f"{n_edit - n_aligned - est} keep the Whisper timestamp of the word they replace" if n_edit else "no word was changed")),
        (S_INTEGRITY, state(S_INTEGRITY), f"{len(errors)} errors, {sum(w['stage'] == S_INTEGRITY for w in warnings)} warnings in {n} word timestamps"),
        (S_PAUSE, state(S_PAUSE, "completed" if pause_status == "measured" else "warning"),
         f"{len(pauses)} silences ≥ {config.SILENCE_MIN}s below {config.SILENCE_DB} dB" if pause_status == "measured" else "silence detector unavailable"),
        (S_QUALITY, state(S_QUALITY), f"max {mx} dB, mean {mean} dB; {flagged} uncertain, {unresolved} unresolved word(s); noise level not measured"),
        (S_FINAL, "failed" if errors else "warning" if warnings else "completed", f"{len(errors)} errors, {len(warnings)} warnings"),
        (S_CACHE, "completed", (f"reused unchanged: {', '.join(reused)}; " if reused else "") + f"{llm_name} answers cached: {cache_entries}; a failed run resumes from the last finished step"),
    ]
    return {
        "schema_version": SCHEMA, "source": src,
        "transcription": {"language": {"code": t.language, "source": "config (forced; no detection ran)", "confidence": None}, "full_text": " ".join(u["text"] for u in utterances),
                          "transcript_file": "transcript_fixed.json" if edited else "transcript_corrected.json" if corrected else "transcript.json", "raw_file": "transcript.json",
                          "corrected_file": "transcript_corrected.json" if corrected else None, "edited_by_user": edited,
                          "asr": {"engine": "faster-whisper", "model": config.WHISPER_MODEL, "model_version": config.WHISPER_VERSION, "device": config.WHISPER_DEVICE, "compute_type": config.WHISPER_COMPUTE}},
        "utterances": utterances, "pauses": pauses,
        "review": None if review is None else {"vocabulary": terms, "confidence": conf, "llm": llm, "corrections": corr, "unresolved": review.get("unresolved", [])},
        "quality": q,
        "processing": {"preprocessing": {"applied": True, "kind": "ffmpeg resample to 16 kHz mono (derived copy audio_16k.wav)", "derived_duration_seconds": derived},
                       "alignment_status": align, "alignment_method": ck.get("method") or "whisper word_timestamps (model-inferred)",
                       "pause_detection": {"status": pause_status, "method": "ffmpeg silencedetect", "min_seconds": config.SILENCE_MIN, "threshold_db": config.SILENCE_DB}},
        "caching": {"steps": {k: (timings.get(k) or {}).get("status") for k in ("transcribe", "refine", "cuts")}, "reused": reused, "llm_cache_entries": cache_entries},
        "stages": [{"n": i + 1, "name": nm, "status": st, "detail": d} for i, (nm, st, d) in enumerate(rows)],
        "validation": {"status": status, "errors": errors, "warnings": warnings, "notes": end_notes},
    }


def write(pdir: Path, progress=None) -> dict:
    """Build and save atomically (temp file + rename), so a half-written file is never read."""
    data = build(pdir, progress)
    f = pdir / "audio_analysis.json"
    tmp = f.with_suffix(".json.part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)
    return data


if __name__ == "__main__":
    d = write(config.project_dir(sys.argv[1]))
    print(d["validation"]["status"], [s["status"] for s in d["stages"]])
