"""Stages 6-9 of the Audio Analyzer: technical vocabulary, uncertain words, the Claude check of every word, the final corrected transcript, word timings of the corrected text.

  transcript.json            the raw ASR output. NEVER edited.
  transcript_review.json     what this stage found and did: vocabulary, uncertain words, the Claude answer's corrections (applied or rejected, each with a reason), what stays unresolved.
  transcript_corrected.json  the ONE final, LLM-verified transcript (same schema as transcript.json, so every consumer reads it through load_transcript()): written whenever the LLM checked
                             the transcript, with its corrections applied and re-aligned, or with the same words when it found nothing to fix. Not written when the LLM did not check it.

Rules: confidence is Whisper's own word probability (`p`), never made up; without it (older transcripts) nothing is flagged and the stage says so. Claude checks every word (the request carries
`p` and the word times as its audio evidence) and may replace a span of at most MAX_SPAN words, the "from" text must match the raw words exactly, and nothing it says is applied without these
checks. Words it writes get `edit: "llm"` and an
timing re-derived against the ORIGINAL audio: the edited segment's text is force-aligned with faster-whisper's own cross-attention alignment (the method behind Whisper's word
timestamps, so the result is model-inferred, never "ground truth") and accepted only if the segment's unchanged words land within MAX_SHIFT of the timestamps Whisper measured
for them; otherwise the new words keep an ESTIMATED timing inside the span of the words they replace and the stage reports a warning. Nothing keeps a stale timestamp of a word
that no longer exists. If Claude is not available the raw transcript stays the transcript and the stage reports it; it never reports a correction that did not happen.   python -m backend.transcript_review <project id>"""
import hashlib
import json
import os
import time
import re
import statistics
import sys
from pathlib import Path

from . import config
from .transcribe import TRANSCRIPT_FILES, Segment, Transcript, Word

SCHEMA = "transcript-review-1"
VERSION = 5                       # bump when the rules or the instructions to Claude change (it is part of the step fingerprint); 4: the request carries the word times, the verified final JSON is always written; 5: Telugu grammar, English capitalization, punctuation rules
LOW_P = float(os.environ.get("A2V_ASR_LOW_CONFIDENCE", "0.5"))      # a word below this Whisper probability is "uncertain"
MAX_SEGMENTS = 20                 # segments sent to Claude in one call
MAX_SPAN = 6                      # words one correction may replace
TIMEOUT = 120
MAX_SHIFT = 0.4                   # seconds: the largest median disagreement between a forced alignment and Whisper's own timestamps of the UNCHANGED words that still lets us trust it
ONSET_GAP = 0.15                  # seconds: a corrected word whose aligned start is this long before the first sound in its span is moved to that sound (measured from the signal)
PAD = 0.3                         # seconds of audio around an edited segment given to the aligner

SYSTEM = (
    "You proofread an automatic transcript (Whisper) of Telugu speech that contains English technical terms, company names, loanwords, and numbers. "
    "You get segments with the full sentence 'text' and individual 'words' with their index i and word w (and Whisper probability p, and s/e: the second the word starts and ends in the audio). "
    "Check every word and fix those that are mis-heard, phonetically distorted, or English words written in Telugu script. "
    "Guidelines: "
    "1. Convert English words and technical loanwords written in Telugu script into correct standard English spelling (e.g. 'స్మార్ట్' -> 'smart', 'సెన్సార్స్' -> 'sensors', 'బ్యాటరీ' -> 'battery', 'ఇంటిగ్రేషన్' -> 'integration'). "
    "2. Genuine Telugu words MUST remain in Telugu script. Never convert or translate genuine Telugu words into English! "
    "3. Mixed-language format: Natural Telugu grammar with standard English spelling for English words (e.g. 'మన smart phones లో AI integration ఉంది'). "
    "4. Remove hallucinated stray numbers or noise artifacts. "
    "5. Keep the speaker's original intended meaning. Never add words that were not spoken; never summarize. "
    "6. Telugu spelling and grammar: fix misspelled or mis-heard Telugu endings and join words that Telugu grammar writes as one (e.g. 'ఇంక' -> 'ఇంకా', 'ఉండాల అంటే' -> 'ఉండాలంటే'). "
    "7. Capitalize proper nouns, brand names, and acronyms (ChatGPT, Gemini, AI); ordinary English words in the middle of a sentence stay lowercase. "
    "8. Answer with JSON only: {\"corrections\":[{\"segment\":<id>,\"from_index\":<i>,\"to_index\":<j>,\"from\":\"<exact words>\",\"to\":\"<replacement or empty>\",\"reason\":\"<five words at most>\"}]}. An empty list is a good answer."
)

_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9+#.'\-]*")
_NUM = re.compile(r"\d[\d,.:]*")
_PUNCT = " \t.,;:!?()[]{}\"'“”‘’।"


def _bare(w: str) -> str:
    return w.strip(_PUNCT)


# ---------- stage 6: Telugu + English technical vocabulary ----------
def vocabulary(t: Transcript, listed: set[str]) -> list[dict]:
    """English terms, numbers and the words of the project's own vocabulary.txt that occur in the transcript (found by their script, not guessed)."""
    found: dict[str, dict] = {}
    for s in t.segments:
        for w in s.words:
            b = _bare(w.w)
            if not b:
                continue
            kind = "listed" if b.lower() in listed else "english" if _LATIN.fullmatch(b) else "number" if _NUM.fullmatch(b) else None
            if kind:
                e = found.setdefault(b, {"text": b, "kind": kind, "count": 0, "segments": []})
                e["count"] += 1
                if s.id not in e["segments"]:
                    e["segments"].append(s.id)
    return sorted(found.values(), key=lambda e: (-e["count"], e["text"]))


def _listed(pdir: Path) -> set[str]:
    f = pdir / "vocabulary.txt"
    return {x.strip().lower() for x in f.read_text(encoding="utf-8").splitlines() if x.strip()} if f.exists() else set()


# ---------- stage 7: confidence & linguistic uncertainty ----------
def uncertain(t: Transcript, low: float = LOW_P) -> dict:
    words = [w for s in t.segments for w in s.words]
    with_p = [w for w in words if w.p is not None]
    flagged = []
    for s in t.segments:
        for i, w in enumerate(s.words):
            if w.p is not None and w.p < low:
                flagged.append({
                    "segment": s.id,
                    "index": i,
                    "text": w.w,
                    "p": w.p,
                    "reason": "low_confidence",
                })
    return {"status": "available" if with_p else "unavailable", "threshold": low, "words_total": len(words), "words_with_confidence": len(with_p), "flagged": flagged}


# ---------- stage 8: Claude correction ----------
def _json_from(text: str) -> dict:
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("no JSON in the answer")
    return json.loads(text[a:b + 1])


def _request(t: Transcript, ids: list[int]) -> str:
    by = {s.id: s for s in t.segments}
    rows = [{"id": i, "text": by[i].text, "words": [{"i": k, "w": w.w, **({"p": w.p} if w.p is not None else {}), "s": round(w.start, 2), "e": round(w.end, 2)} for k, w in enumerate(by[i].words)]} for i in ids]
    return json.dumps({"segments": rows}, ensure_ascii=False)


def validate_corrections(t: Transcript, answer: list) -> list[dict]:
    """Every proposed correction with status applied/rejected and the reason for a rejection. Only checked, non-overlapping ones are 'applied'."""
    by = {s.id: s for s in t.segments}
    used: set[tuple[int, int]] = set()
    out = []
    for n, c in enumerate(answer if isinstance(answer, list) else []):
        rec = {"id": f"c{n + 1:03d}", "segment": None, "from_index": None, "to_index": None, "from": "", "to": "", "reason": "", "p_from": [], "status": "rejected", "why": None}
        try:
            sid, i, j = int(c["segment"]), int(c["from_index"]), int(c["to_index"])
            frm = " ".join(str(c["from"]).split())
            to = " ".join(str(c.get("to", "")).split()) if c.get("to") is not None else ""
            reason = str(c.get("reason", ""))[:60]
        except (KeyError, TypeError, ValueError, AttributeError):
            out.append({**rec, "why": "malformed"})
            continue
        rec.update(segment=sid, from_index=i, to_index=j, **{"from": frm, "to": to, "reason": reason})
        seg = by.get(sid)
        if seg is None or not (0 <= i <= j < len(seg.words)):
            out.append({**rec, "why": "bad_index"})
            continue
        words = seg.words[i:j + 1]
        rec["p_from"] = [w.p for w in words]
        cells = {(sid, k) for k in range(i, j + 1)}
        raw_words_text = " ".join(w.w for w in words).strip()
        if raw_words_text != frm and not (frm == "" and raw_words_text in ("", "\ufffd")):
            why = "from_mismatch"
        elif j - i + 1 > MAX_SPAN:
            why = "span_too_long"
        elif to == frm and not (frm == "" and raw_words_text in ("", "\ufffd")):
            why = "empty_or_unchanged"
        elif len(to.split()) > (j - i + 1) + 2:
            why = "adds_words"
        elif cells & used:
            why = "overlaps_another"
        else:
            why = None
        if why is None:
            used |= cells
            rec["status"] = "applied"
        else:
            rec["why"] = why
        out.append(rec)
    return out


def apply_corrections(t: Transcript, corrections: list[dict]) -> tuple[Transcript, int]:
    """The corrected transcript. A replaced span keeps the time span of the words it replaced. When the correction writes as many words as it replaced (a respelling: "క్రీటివిటి" -> "creativity"),
    each new word keeps the Whisper timestamp of the word it replaces: the same spoken word, so that time IS measured (timing None, edit "llm"). Only when the word count changes do the new words
    share the span by their length (timing 'estimated'), because then nothing says where one spoken word ends."""
    todo: dict[int, list[dict]] = {}
    for c in corrections:
        if c["status"] == "applied":
            todo.setdefault(c["segment"], []).append(c)
    edited, segs = 0, []
    for s in t.segments:
        if s.id not in todo:
            segs.append(s)
            continue
        words, at = [], 0
        for c in sorted(todo[s.id], key=lambda c: c["from_index"]):
            words += s.words[at:c["from_index"]]
            span = s.words[c["from_index"]:c["to_index"] + 1]
            new = c["to"].split()
            if len(new) == len(span):
                words += [Word(w=x, start=old.start, end=old.end, p=None, timing=None, edit="llm") for x, old in zip(new, span)]
                edited += len(new)
                at = c["to_index"] + 1
                continue
            t0, t1 = span[0].start, span[-1].end
            size = sum(len(x) for x in new) or 1
            cur = t0
            for x in new:
                nxt = cur + (t1 - t0) * len(x) / size
                words.append(Word(w=x, start=round(cur, 3), end=round(nxt, 3), p=None, timing="estimated", edit="llm"))
                cur = nxt
            edited += len(new) if new else 1
            at = c["to_index"] + 1
        words += s.words[at:]
        words = [w for w in words if w.w.strip(" \t\ufffd")]
        segs.append(Segment(id=s.id, start=s.start, end=s.end, text=" ".join(w.w for w in words), words=words))
    return Transcript(language=t.language, duration=t.duration, segments=segs), edited


def whisper_aligner():
    """A forced aligner on faster-whisper's cross-attention alignment. aligner(audio_16k, words) -> [(start, end)] per word, seconds from the start of `audio`.
    Loads the ASR model (about 3 GB of RAM), so it is built only when words were corrected."""
    import numpy as np
    from faster_whisper import WhisperModel
    from faster_whisper.audio import pad_or_trim
    from faster_whisper.tokenizer import Tokenizer

    model = WhisperModel(config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE, local_files_only=config.WHISPER_LOCAL_ONLY)
    tok = Tokenizer(model.hf_tokenizer, model.model.is_multilingual, task="transcribe", language="te")

    def align(audio, words):
        feats = model.feature_extractor(np.asarray(audio, dtype="float32"))
        frames = min(model.feature_extractor.nb_max_frames, feats.shape[-1] - 1)
        enc = model.encode(pad_or_trim(feats[:, :frames]))
        tokens = [t for t in tok.encode(" " + " ".join(words)) if t < tok.eot]
        entries = model.find_alignment(tok, [tokens], enc, frames)[0]
        spans, i = [], 0
        for want in words:                                 # entries are word pieces (punctuation separately): glue them back to the words we asked for
            text, first, last = "", None, None
            while i < len(entries) and len(text) < len(want):
                e = entries[i]
                text += e["word"].strip()
                first = e["start"] if first is None else first
                last = e["end"]
                i += 1
            if text != want or first is None:
                raise ValueError(f"the aligner returned '{text}' for '{want}'")
            spans.append((float(first), float(last)))
        return spans

    return align


def _voiced(pcm, hop: float = 0.025):
    """(frame times, voiced flags): a frame is voiced when it is clearly louder than this audio's own silence floor (measured from the signal)."""
    import numpy as np
    n = int(16000 * hop)
    k = len(pcm) // n
    rms = np.sqrt((np.asarray(pcm[:k * n], dtype="float64").reshape(k, n) ** 2).mean(axis=1))
    db = 20 * np.log10(rms + 1e-9)
    lo, hi = np.percentile(db, 10), np.percentile(db, 85)
    if hi - lo < 6.0:                                   # no loud/quiet difference in this audio (a constant tone): the signal cannot tell speech from silence, so it does not veto anything
        return hop, np.ones(k, dtype=bool)
    return hop, db > lo + max(8.0, 0.35 * (hi - lo))


def _onset(hop, voiced, x: float, y: float):
    """The first time in [x, y] where sound starts (two voiced frames in a row), or None when there is no sound in the span."""
    i, j = int(x / hop), min(len(voiced) - 1, int(y / hop))
    for k in range(i, j):
        if voiced[k] and voiced[k + 1]:
            return max(x, round(k * hop, 3))
    return None


def realign(pdir: Path, fixed: Transcript, aligner=None) -> dict:
    """Re-time the ESTIMATED words (corrections that changed the word count) against the original audio. Returns {"status", "segments": [...]}. Accepted words get timing 'aligned'; the others stay
    'estimated'. Every other word, unchanged or respelled in place, keeps a Whisper timestamp and is an anchor for the cross-check; with nothing estimated the model is not even loaded."""
    edited = [s for s in fixed.segments if any(w.timing == "estimated" for w in s.words)]
    out = {"status": "unchanged", "segments": []}
    if not edited:
        return out
    try:
        from faster_whisper.audio import decode_audio
        wav = pdir / "audio_16k.wav"
        if not wav.exists():
            from .audio_utils import to_wav16k
            from .transcribe import find_audio
            to_wav16k(find_audio(pdir), wav)
        pcm = decode_audio(str(wav), sampling_rate=16000)
        align = aligner or whisper_aligner()
    except Exception as e:     # no model / no memory / no audio: every edited segment keeps its estimated timing and the stage says why
        why = f"alignment could not start: {str(e)[:120]}"
        return {"status": "estimated_for_edits", "segments": [{"segment": s.id, "status": "estimated", "reason": why, "median_shift": None} for s in edited]}
    for s in edited:
        a, b = max(0.0, s.start - PAD), min(len(pcm) / 16000, s.end + PAD)
        rec = {"segment": s.id, "status": "estimated", "reason": None, "median_shift": None, "snapped": []}
        try:
            spans = align(pcm[int(a * 16000):int(b * 16000)], [w.w for w in s.words])
            spans = [(round(x + a, 3), round(y + a, 3)) for x, y in spans]
            if len(spans) != len(s.words) or any(not (a - 1e-6 <= x <= y <= b + 1e-6) for x, y in spans) or any(spans[k][0] < spans[k - 1][0] - 1e-6 for k in range(1, len(spans))):
                raise ValueError("the aligned times are out of order or outside the audio")
            anchors = [abs(x - w.start) for w, (x, _) in zip(s.words, spans) if w.timing != "estimated"]
            if not anchors:
                rec["median_shift"] = 0.0
            else:
                rec["median_shift"] = round(statistics.median(anchors), 3)
                if rec["median_shift"] > MAX_SHIFT:
                    raise ValueError(f"the alignment disagrees with Whisper's own timestamps of the unchanged words (median {rec['median_shift']} s)")
            fits = [(k, spans[k]) for k, w in enumerate(s.words) if w.timing == "estimated"]
            hop, voiced = _voiced(pcm)
            moved = []
            for n, (k, (x, y)) in enumerate(fits):                                       # check the model's times against the sound itself
                on = _onset(hop, voiced, x, y)
                if on is not None and on - x > ONSET_GAP:
                    moved.append({"word": s.words[k].w, "aligned_start": x, "first_sound": on})
                    fits[n] = (k, (on, y))
            rec["snapped"] = moved
            for k, (x, y) in fits:
                lo = s.words[k - 1].end if k and s.words[k - 1].edit is None else (s.words[k - 1].end if k else s.start)
                hi = s.words[k + 1].start if k + 1 < len(s.words) and s.words[k + 1].edit is None else (s.words[k + 1].start if k + 1 < len(s.words) else s.end)
                x = max(lo, round(x, 3))
                y = min(hi, max(x + 0.05, round(y, 3)))
                s.words[k].start, s.words[k].end, s.words[k].timing = x, y, "aligned"
            cur = s.start
            for w in s.words:
                if w.start < cur:
                    w.start = cur
                if w.end < w.start + 0.04:
                    w.end = w.start + 0.04
                cur = w.end
            if s.words and s.words[-1].end > s.end:
                s.words[-1].end = s.end
            rec["status"] = "aligned"
        except Exception as e:
            rec["reason"] = str(e)[:160]                  # the new words keep the ESTIMATED timing from apply_corrections
        out["segments"].append(rec)
    n_ok = sum(r["status"] == "aligned" for r in out["segments"])
    out["status"] = "aligned_for_edits" if n_ok == len(out["segments"]) else "partial" if n_ok else "estimated_for_edits"
    return out


def _alignment_block(align_r: dict, edited: int, estimated: int) -> dict:
    """The "alignment" record of transcript_review.json for an alignment result; `estimated_words` is how many corrected words still have an ESTIMATED timing."""
    return {"status": align_r["status"], "edited_words": edited, "estimated_words": estimated, "segments": align_r["segments"],
            "method": {"unchanged": "whisper word timestamps (model-inferred); a corrected word that replaces one word keeps that word's timestamp",
                       "aligned_for_edits": "corrected words re-aligned against the original audio (faster-whisper cross-attention forced alignment, model-inferred) and cross-checked against the unchanged words",
                       "partial": "some corrected words re-aligned, the others keep ESTIMATED timestamps (see segments)",
                       "estimated_for_edits": "ESTIMATED timestamps for the corrected words (not aligned or alignment failed, see segments)"}[align_r["status"]]}


def alignment_pending(review: dict) -> bool:
    """True while corrected words of this review still have an ESTIMATED timing. The `refine` step then counts as unfinished (its outputs list a file that never exists), so every new run tries
    the alignment again (resume); the Claude answer comes from the cache, no second call. A review written before `estimated_words` existed is judged by its alignment status."""
    a = review.get("alignment") or {}
    return a.get("estimated_words", 1) > 0 and a.get("status") in ("partial", "estimated_for_edits")


def last_review(pdir: Path) -> dict:
    try:
        return json.loads((pdir / "transcript_review.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _model() -> str | None:
    from . import llm_client
    try:
        _, model, _, _ = llm_client.resolve_provider_config()
        return model
    except Exception:
        return os.environ.get("PROMPTGEN_MODEL") or None


def refine(pdir: Path, progress=None, ask=None, aligner=None) -> dict:
    """Run stages 6-9 and write transcript_review.json and the final, LLM-verified transcript_corrected.json. The LLM checks every word (`ask(user, system=, timeout=)` defaults to the Claude CLI);
    the corrected words are re-aligned against the audio (or keep an ESTIMATED timing, and the step is retried with the alignment on the next run)."""
    say = progress or (lambda p, eta=None: None)
    t = Transcript.model_validate_json((pdir / "transcript.json").read_text(encoding="utf-8"))
    vocab = vocabulary(t, _listed(pdir))
    say(25)
    conf = uncertain(t)
    say(50)
    cache_f = pdir / "asr_llm_cache.json"
    cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
    llm = {"status": "not_needed", "error": None, "model": _model(), "segments_sent": 0}
    corrections: list[dict] = []
    if any(s.words for s in t.segments):
        ids = sorted(s.id for s in t.segments)
        answers, statuses = [], []
        try:
            for n in range(0, len(ids), MAX_SEGMENTS):
                user = _request(t, ids[n:n + MAX_SEGMENTS])
                key = hashlib.sha1(f"{VERSION}|{_model()}|{SYSTEM}|{user}".encode()).hexdigest()
                llm["segments_sent"] += len(ids[n:n + MAX_SEGMENTS])
                if key in cache:
                    answers.append(cache[key])
                    statuses.append("cached")                                 # the same question was answered before: no second call
                else:
                    from . import promptgen
                    cache[key] = (ask or promptgen.run_claude)(user, system=SYSTEM, timeout=TIMEOUT)
                    cache_f.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                    answers.append(cache[key])
                    statuses.append("applied")
            llm["status"] = "applied" if "applied" in statuses else "cached"
            for ans in answers:
                corrections += validate_corrections(t, _json_from(ans).get("corrections", []))
            for n, c in enumerate(corrections):
                c["id"] = f"c{n + 1:03d}"
        except Exception as e:     # CLI missing / not signed in / timeout / an answer that is not the JSON asked for: the raw transcript stays
            llm["status"] = "unavailable" if "not found" in str(e) or "sign" in str(e).lower() else "failed"
            llm["error"] = str(e)[:240]
            corrections = []
    say(75)
    fixed, edited = apply_corrections(t, corrections)
    if not edited:
        align_r = {"status": "unchanged", "segments": []}
    else:
        align_r = realign(pdir, fixed, aligner)
    out = pdir / "transcript_corrected.json"
    down = llm["status"] in ("unavailable", "failed")
    checked = llm["status"] in ("applied", "cached")             # the LLM answered for this transcript
    kept = bool(down and not edited and out.exists() and out.stat().st_mtime >= (pdir / "transcript.json").stat().st_mtime)
    if edited or checked:                                        # the one final, LLM-verified JSON: the corrected words, or the same words when the LLM checked them and found nothing to fix
        out.write_text(fixed.model_dump_json(indent=1), encoding="utf-8")
    elif kept:
        llm["kept_earlier_correction"] = True      # the LLM is not available now: the transcript it verified earlier (made after the current raw transcript) is NOT thrown away
    elif out.exists():
        out.unlink()            # a derived file of an earlier run that no longer applies (the raw text is the transcript again, or it was made from an older raw transcript)
    done = {(c["segment"], k) for c in corrections if c["status"] == "applied" for k in range(c["from_index"], c["to_index"] + 1)}
    left = [f for f in conf["flagged"] if (f["segment"], f["index"]) not in done]      # low-confidence words the LLM did not change
    review = {
        "schema_version": SCHEMA, "version": VERSION, "raw_file": "transcript.json", "corrected_file": "transcript_corrected.json" if edited or checked or kept else None,
        "vocabulary": {"terms": vocab, "project_list": (pdir / "vocabulary.txt").exists()},
        "confidence": conf, "llm": llm, "corrections": corrections,
        # The LLM looked at every word: a low-confidence word it left as it is was reviewed and kept (confirmed), not unresolved. Only when the LLM did not check, the words stay unresolved.
        "unresolved": [] if checked else left,
        "confirmed": [{"segment": f["segment"], "index": f["index"], "text": f["text"], "p": f["p"], "reason": "checked by the LLM and kept"} for f in left] if checked else [],
        "alignment": _alignment_block(align_r, edited, sum(w.timing == "estimated" for s in fixed.segments for w in s.words)),
    }
    tmp = pdir / "transcript_review.json.part"
    tmp.write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, pdir / "transcript_review.json")
    return review


MAX_FIX_ROUNDS = 2                # passes that tell the LLM what the stage review still found, counted on disk per raw transcript (a new raw transcript starts again)
FIX_SYSTEM = SYSTEM + (" THIS IS A SECOND PASS over a transcript you already proofread: a reviewer still found the problems listed under 'review_findings'. Fix exactly those problems, with the same JSON "
                       "answer, and change nothing else. A script boundary with no space ('directగా') is written 'direct గా', as everywhere else in this transcript. Never guess a word that neither the words, "
                       "their probabilities nor the sentence around them support: leave it (an empty list is a good answer).")


class FixError(RuntimeError):
    """The review's findings could not be fixed automatically; the message says why (the stage then stops with it)."""


def fix(pdir: Path, findings: list[dict], ask=None, aligner=None) -> dict:
    """One more pass over the transcript the LLM already corrected, told what the Audio Analyzer's stage review still found. The corrections go through the same checks as the first pass
    (`validate_corrections`: only exact, non-overlapping, bounded ones are applied), corrected words that changed the word count are re-aligned against the audio, and the pass is recorded in
    transcript_review.json (`fix_rounds`). Raises FixError when no pass is left, there is nothing to fix, or the LLM changed nothing."""
    raw_f = pdir / "transcript.json"
    review = last_review(pdir)
    raw_id = hashlib.sha1(raw_f.read_bytes()).hexdigest()[:12]
    rounds = [r for r in review.get("fix_rounds", []) if r.get("raw") == raw_id]
    if len(rounds) >= MAX_FIX_ROUNDS:
        raise FixError(f"{MAX_FIX_ROUNDS} automatic fix passes were already made for this transcript; what the review still finds could not be solved automatically")
    items = [{"severity": f.get("severity"), "category": f.get("category"), "message": str(f.get("message"))[:400]} for f in findings if f.get("severity") in ("warning", "error", "blocker")]
    if not items:
        raise FixError("the review has no warning or error left to solve")
    src = pdir / "transcript_corrected.json"
    t = Transcript.model_validate_json((src if src.exists() else raw_f).read_text(encoding="utf-8"))
    ids = sorted(s.id for s in t.segments if s.words)
    cache_f = pdir / "asr_llm_cache.json"
    cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
    corrections: list[dict] = []
    try:
        for n in range(0, len(ids), MAX_SEGMENTS):
            body = json.loads(_request(t, ids[n:n + MAX_SEGMENTS]))
            body["review_findings"] = items
            user = json.dumps(body, ensure_ascii=False)
            key = hashlib.sha1(f"fix{VERSION}|{_model()}|{FIX_SYSTEM}|{user}".encode()).hexdigest()
            if key not in cache:
                from . import promptgen
                cache[key] = (ask or promptgen.run_claude)(user, system=FIX_SYSTEM, timeout=TIMEOUT)
                cache_f.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            corrections += validate_corrections(t, _json_from(cache[key]).get("corrections", []))
    except Exception as e:                                         # CLI missing / not signed in / timeout / an answer that is not the JSON asked for
        raise FixError(f"the LLM could not be asked for the fix: {str(e)[:200]}") from e
    for n, c in enumerate(corrections):
        c["id"] = f"f{len(rounds) + 1}c{n + 1:03d}"
    fixed, edited = apply_corrections(t, corrections)
    rec = {"round": len(rounds) + 1, "raw": raw_id, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "findings": items, "corrections": corrections, "edited_words": edited}
    review["fix_rounds"] = review.get("fix_rounds", []) + [rec]
    if edited:
        align_r = realign(pdir, fixed, aligner)
        total = sum(1 for s in fixed.segments for w in s.words if w.edit)
        est = sum(w.timing == "estimated" for s in fixed.segments for w in s.words)
        if align_r["status"] == "unchanged":                        # only respellings: they keep the measured Whisper times, the earlier alignment record stands
            review["alignment"] = {**(review.get("alignment") or {}), "edited_words": total, "estimated_words": est}
        else:
            review["alignment"] = _alignment_block(align_r, total, est)
        src.write_text(fixed.model_dump_json(indent=1), encoding="utf-8")
        review["corrected_file"] = "transcript_corrected.json"
    tmp = pdir / "transcript_review.json.part"
    tmp.write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, pdir / "transcript_review.json")
    if not edited:
        raise FixError("the LLM found nothing it could fix with the words and probabilities it has: " + "; ".join(f"{c.get('why')}" for c in corrections if c["status"] != "applied")[:200])
    return rec


def is_verified(pdir: Path) -> bool:
    """True when the transcript the later stages read has been checked by the LLM: it answered for the current raw transcript (applied or cached) and no corrected word is still waiting for its
    timestamps. `transcript_corrected.json` exists only when something was corrected, so a transcript the LLM checked and left as it was is verified too; a corrected file newer than the raw
    transcript also counts (projects checked before the review file recorded this)."""
    raw, review_f, corrected = pdir / "transcript.json", pdir / "transcript_review.json", pdir / "transcript_corrected.json"
    if not raw.exists():
        return False
    if review_f.exists() and review_f.stat().st_mtime >= raw.stat().st_mtime:
        try:
            review = json.loads(review_f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return (review.get("llm") or {}).get("status") in ("applied", "cached") and not alignment_pending(review)
    return corrected.exists() and corrected.stat().st_mtime >= raw.stat().st_mtime        # no current review file: an older project that has only the corrected transcript


def comparison(pdir: Path) -> dict:
    """The raw Whisper output next to the final transcript, segment by segment, for the Audio Analyzer page. Read-only: transcript.json (never edited), the final transcript (the user's fix,
    else transcript_corrected.json, else the raw one), the review record and the stage's LLM review. `changed` segments carry `final_words` with the `edit` / `timing` of every word."""
    raw = Transcript.model_validate_json((pdir / "transcript.json").read_text(encoding="utf-8"))
    final_file = next((n for n in TRANSCRIPT_FILES if (pdir / n).exists()), "transcript.json")
    final = raw if final_file == "transcript.json" else Transcript.model_validate_json((pdir / final_file).read_text(encoding="utf-8"))
    review, stage = {}, {}
    for name, target in (("transcript_review.json", review), ("llm_review_analyzer.json", stage)):
        try:
            target.update(json.loads((pdir / name).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    raw_by = {s.id: s for s in raw.segments}
    segments = []
    for s in final.segments:
        r = raw_by.get(s.id)
        changed = r is None or r.text != s.text
        segments.append({"id": s.id, "start": s.start, "end": s.end, "raw_text": r.text if r else "", "final_text": s.text, "changed": changed,
                         **({"final_words": [{"w": w.w, "start": w.start, "end": w.end, "timing": w.timing, "edit": w.edit} for w in s.words]} if changed else {})})
    corrections = review.get("corrections") or []
    return {"raw_file": "transcript.json", "final_file": final_file, "verified": is_verified(pdir), "language": final.language, "duration": final.duration,
            "llm": {k: (review.get("llm") or {}).get(k) for k in ("status", "model", "segments_sent", "error")},
            "alignment": (review.get("alignment") or {}).get("status"),
            "stage_review": {"status": stage.get("status"), "score": stage.get("score")} if stage else None,
            "corrections_applied": sum(c.get("status") == "applied" for c in corrections), "corrections_rejected": sum(c.get("status") != "applied" for c in corrections),
            "corrections": corrections, "segments": segments}


if __name__ == "__main__":
    r = refine(config.project_dir(sys.argv[1]))
    print(r["llm"]["status"], f"flagged={len(r['confidence']['flagged'])} corrections={sum(c['status'] == 'applied' for c in r['corrections'])}")
