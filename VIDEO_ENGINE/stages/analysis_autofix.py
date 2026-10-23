"""Clear the fixable warnings of the Audio Analyzer (audio_analysis.json) and re-check, in an automated loop.

Only fixable warnings:
1. `word_outside_segment` where a word starts BEFORE its segment starts (timing onset shifted to voiced sound).
2. `uncertain_words` where low-confidence words are verified in context via LLM or approved technical vocabulary.

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


def _fix_uncertain_words(pdir: Path, warnings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Resolves uncertain word warnings via LLM review or vocabulary verification. Returns (changes, not_fixed)."""
    rev_path = pdir / "transcript_review.json"
    if not rev_path.exists():
        return [], warnings
    try:
        rev = json.loads(rev_path.read_text(encoding="utf-8"))
    except Exception:
        return [], warnings

    unresolved = rev.get("unresolved", [])
    if not unresolved:
        return [], warnings

    changes = []
    left = []
    t = transcribe.load_transcript(pdir)
    target = next((n for n in transcribe.TRANSCRIPT_FILES if (pdir / n).exists()), "transcript_corrected.json")

    from . import llm_client
    terms = {term["text"].lower() for term in rev.get("vocabulary", {}).get("terms", [])}

    for item in list(unresolved):
        sid = item.get("segment")
        idx = item.get("index")
        word_text = item.get("text", "")
        clean_word = word_text.strip(".,!?:;\"' ")

        # 1. Recognized technical vocabulary term (exclude stray list numbers like '2.')
        is_stray_number = bool(re.match(r"^\d+\.$", word_text.strip()))
        if not is_stray_number and (clean_word.lower() in terms or (clean_word.isdigit() and len(clean_word) < 6)):
            changes.append({
                "word": word_text,
                "segment": sid,
                "action": "confirmed",
                "evidence": f"verified technical vocabulary / recognized number '{clean_word}'"
            })
            rev["unresolved"] = [u for u in rev["unresolved"] if not (u.get("segment") == sid and u.get("index") == idx)]
            rev.setdefault("confirmed", []).append({
                "segment": sid,
                "index": idx,
                "text": word_text,
                "reason": "verified technical vocabulary term",
            })
            continue

        # 2. In-context LLM review
        seg = next((s for s in t.segments if s.id == sid), None)
        seg_text = seg.text if seg else ""
        try:
            ask = (
                f"Narration context: '{seg_text}'\n"
                f"Word in question: '{word_text}'\n"
                f"Is this word accurate spoken Telugu/English in this context, or is it distorted / a hallucinated noise artifact (e.g. list numbering '2.')?\n"
                f"Return JSON: {{\"action\": \"confirm\"}} if the word is accurate in context, "
                f"{{\"action\": \"delete\"}} if it is hallucinated numbering or noise that should be removed, "
                f"or {{\"action\": \"correct\", \"to\": \"proper_word\", \"reason\": \"explanation\"}}."
            )
            from . import llm_gateway
            try:
                gw_req = llm_gateway.LlmGatewayRequest(
                    project_id=pdir.name,
                    stage_id="analyzer",
                    agent_id="audio_analyzer",
                    purpose="repair",
                    model_profile="fast_structured",
                    system_prompt="You verify speech-to-text words in context. Respond ONLY in JSON.",
                    user_prompt=ask,
                    timeout=45,
                )
                gw_resp = llm_gateway.get_gateway().execute(gw_req)
                res = gw_resp.raw_output or ""
            except Exception:
                res = llm_client.generate_text(ask, system="You verify speech-to-text words in context. Respond ONLY in JSON.", timeout=45)
            a, b = res.find("{"), res.rfind("}")
            if a >= 0 and b > a:
                res_json = json.loads(res[a:b + 1])
                act = res_json.get("action")
                if act == "confirm":
                    changes.append({"word": word_text, "segment": sid, "action": "confirmed", "evidence": "confirmed by LLM in context"})
                    rev["unresolved"] = [u for u in rev["unresolved"] if not (u.get("segment") == sid and u.get("index") == idx)]
                    rev.setdefault("confirmed", []).append({"segment": sid, "index": idx, "text": word_text, "reason": "confirmed by LLM in context"})
                elif act == "delete":
                    if seg and idx < len(seg.words):
                        seg.words.pop(idx)
                        seg.text = " ".join(w.w for w in seg.words)
                        (pdir / target).write_text(t.model_dump_json(indent=1), encoding="utf-8")
                    changes.append({"word": word_text, "segment": sid, "action": "deleted", "evidence": "hallucinated noise artifact removed"})
                    rev["unresolved"] = [u for u in rev["unresolved"] if not (u.get("segment") == sid and u.get("index") == idx)]
                    rev.setdefault("corrections", []).append({
                        "id": f"c{len(rev.get('corrections', [])) + 1:03d}",
                        "segment": sid,
                        "from_index": idx,
                        "to_index": idx,
                        "from": word_text,
                        "to": "",
                        "reason": "hallucinated noise artifact removed",
                        "status": "applied",
                    })
                elif act == "correct" and res_json.get("to"):
                    to_word = res_json["to"].strip()
                    if seg and idx < len(seg.words):
                        seg.words[idx].w = to_word
                        seg.words[idx].edit = "llm"
                        (pdir / target).write_text(t.model_dump_json(indent=1), encoding="utf-8")
                    changes.append({"word": word_text, "to": to_word, "segment": sid, "action": "corrected", "evidence": res_json.get("reason", "corrected by LLM")})
                    rev["unresolved"] = [u for u in rev["unresolved"] if not (u.get("segment") == sid and u.get("index") == idx)]
                    rev.setdefault("corrections", []).append({
                        "id": f"c{len(rev.get('corrections', [])) + 1:03d}",
                        "segment": sid,
                        "from_index": idx,
                        "to_index": idx,
                        "from": word_text,
                        "to": to_word,
                        "reason": res_json.get("reason", "corrected by LLM"),
                        "status": "applied",
                    })
                else:
                    left.append(item)
            else:
                left.append(item)
        except Exception:
            left.append(item)

    if changes:
        rev_path.write_text(json.dumps(rev, ensure_ascii=False, indent=1), encoding="utf-8")

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

            # 1. Timing/voiced onset fixes
            changes, left = _fix_once(pdir, data["validation"]["warnings"])

            # 2. Uncertain words resolution
            if not changes and any(w.get("code") == "uncertain_words" for w in data["validation"]["warnings"]):
                u_changes, u_left = _fix_uncertain_words(pdir, data["validation"]["warnings"])
                changes += u_changes
                if not u_changes and u_left:
                    left += [{**w, "why_not_fixed": "LLM review could not resolve this uncertain word"} for w in data["validation"]["warnings"] if w.get("code") == "uncertain_words"]

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
