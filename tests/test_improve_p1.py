"""Phase 1 of improvement/MASTER_PLAN.md: Telugu graphemes/wrapping, emphasis events (timestamps, durations, caps, overlaps, fallbacks)."""
import json
import shutil
import unicodedata
from pathlib import Path

import pytest

from backend import config, highlights, telugu

FIX = Path(__file__).parent / "fixtures"


# ---------- Telugu graphemes and wrapping ----------
@pytest.mark.parametrize("text,n", [("క్ష", 1), ("స్త్రీ", 1), ("కొన్ని", 2), ("తెలుగు", 3), ("ఉహించుకొలేమ్", 6), ("AI", 2), ("క‍ష", 1)])
def test_graphemes_keep_conjuncts_and_signs_together(text, n):
    assert telugu.glen(text) == n


def test_wrap_never_cuts_inside_a_cluster():
    text = "ఈరోజులో మనం చేత్లో మోబైలేకుండా ఒక్క క్షనం కూడా ఉహించుకొలేమ్ స్త్రీ పురుషులు కార్యక్రమాలు"
    for width in (3, 4, 5, 7, 12):
        lines = telugu.wrap(text, width)
        assert "".join(lines).replace(" ", "") == text.replace(" ", "")          # nothing lost, nothing added
        assert [g for ln in lines for w in ln.split() for g in telugu.graphemes(w)] == [g for w in text.split() for g in telugu.graphemes(w)]     # every cut falls BETWEEN clusters
        for ln in lines:
            assert telugu.glen(ln) <= width
            assert unicodedata.category(ln[0]) not in ("Mn", "Mc")             # a line never starts with a vowel sign / anusvara


def test_wrap_long_single_word_is_cut_between_clusters():
    word = "కార్యక్రమాలకుసంబంధించిన"
    parts = telugu.wrap(word, 5)
    assert "".join(parts) == word and all(telugu.glen(p) <= 5 for p in parts)


# ---------- helpers for synthetic projects ----------
def _project(tmp: Path, segments, scenes, duration=30.0) -> Path:
    segs = []
    for i, words in enumerate(segments):
        ws = [{"w": w, "start": s, "end": e} for w, s, e in words]
        segs.append({"id": i, "start": words[0][1] if words else 0, "end": words[-1][2] if words else 0, "text": " ".join(w for w, _, _ in words), "words": ws})
    (tmp / "transcript.json").write_text(json.dumps({"language": "te", "duration": duration, "segments": segs}), encoding="utf-8")
    plan = {"style": {"suffix": "x", "palette": ["#000000", "#ffffff"]},
            "scenes": [{"id": i + 1, "start": a, "end": b, "meaning": "m", "concept": "c", "mood": "m", "mode": "typography", "pattern": "hero_text",
                        "keywords": [{"text": t, "at": at} for t, at in kws]} for i, (a, b, kws) in enumerate(scenes)]}
    (tmp / "scene_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    return tmp


def _check_invariants(out, duration):
    ev = out["events"]
    lo, hi = config.HIGHLIGHT_DURATION_SEC
    assert [e["start"] for e in ev] == sorted(e["start"] for e in ev)              # timestamp ordering
    for e in ev:
        assert 0 <= e["start"] < e["end"] <= duration                                # inside the audio
        assert e["end"] - e["start"] <= hi + 1e-6                                    # safe duration
        assert e["reason"]["rule"]                                                   # every highlight says why
    for a, b in zip(ev, ev[1:]):
        assert a["end"] <= b["start"] - config.HIGHLIGHT_MIN_GAP_SEC + 1e-6          # no overlap
    assert len({e["id"] for e in ev}) == len(ev)


def test_detects_numbers_terms_contrast_and_ignores_plain_words(tmp_path):
    words = [("మనం", 0.0, 0.4), ("2030", 0.5, 1.0), ("లో.", 1.1, 1.3), ("Python", 2.0, 2.6), ("కానీ.", 3.0, 3.4), ("ఒక", 3.5, 3.7), ("౫", 4.2, 4.6), ("ఇల్లు.", 4.7, 5.2)]
    pdir = _project(tmp_path, [words], [(0, 6, [])], duration=6.0)
    out = highlights.build(pdir)
    kinds = {e["text"]: e["kind"] for e in out["events"]}
    assert kinds.get("2030") == "number" and kinds.get("Python") == "name" and kinds.get("౫") == "number"
    assert "ఒక" not in kinds and "మనం" not in kinds and "ఇల్లు" not in kinds
    _check_invariants(out, 6.0)


def test_sentence_cap_and_priority(tmp_path):
    words = [(w, 0.5 * i, 0.5 * i + 0.3) for i, w in enumerate(["1", "2", "3", "Python", "కానీ", "మనం."])]       # one sentence, five candidates
    out = highlights.build(_project(tmp_path, [words], [(0, 4, [])], duration=4.0))
    assert len(out["events"]) <= config.HIGHLIGHTS_MAX_PER_SENTENCE
    assert all(e["kind"] == "number" for e in out["events"])                                   # numbers beat names and contrast words
    assert any(s["reason"] == "sentence cap" for s in out["skipped"])                          # what was dropped is reported, not hidden
    _check_invariants(out, 4.0)


def test_adjacent_events_never_overlap(tmp_path):
    words = [("10", 1.0, 1.3), ("20.", 1.35, 1.7), ("30", 2.5, 2.8), ("40", 2.85, 3.1)]
    out = highlights.build(_project(tmp_path, [words], [(0, 5, [])], duration=5.0))
    _check_invariants(out, 5.0)
    assert len(out["events"]) >= 2


def test_keyword_snaps_to_spoken_word_or_stays_estimated(tmp_path):
    words = [("ఒకటి", 1.0, 1.4), ("మాట", 1.5, 1.9), ("అంతే", 5.0, 5.4)]
    out = highlights.build(_project(tmp_path, [words], [(0, 8, [("Near", 1.55), ("Far", 3.2)])], duration=8.0))
    by = {e["text"]: e for e in out["events"] if e["kind"] == "keyword"}
    assert by["Near"]["timing"] == "word" and by["Near"]["start"] == 1.5           # moved onto the word that is spoken
    assert by["Far"]["timing"] == "estimated" and by["Far"]["start"] == 3.2         # nothing spoken near it: time kept, honestly labelled
    _check_invariants(out, 8.0)


def test_missing_word_timestamps_fall_back_to_segment_level(tmp_path):
    pdir = _project(tmp_path, [[("అ", 0.0, 0.4)]], [(0, 6, [("Idea", 2.0)])], duration=6.0)
    t = json.loads((pdir / "transcript.json").read_text(encoding="utf-8"))
    t["segments"] = [{"id": 0, "start": 0.0, "end": 5.0, "text": "అ ఆ ఇ", "words": []}]        # Whisper gave text but no words
    (pdir / "transcript.json").write_text(json.dumps(t), encoding="utf-8")
    out = highlights.build(pdir)
    assert out["precision"]["level"] == "segment" and out["precision"]["unreliable_segments"] == [0]
    e = out["events"][0]
    assert e["timing"] == "segment" and e["start"] == 2.0                           # never claims word precision
    _check_invariants(out, 6.0)


def test_unreliable_segment_is_detected_and_reliable_one_still_used(tmp_path):
    good = [("5", 0.5, 0.9), ("మాట.", 1.0, 1.4)]
    bad = [("7", 3.0, 3.5), ("అది", 3.2, 3.6)]                                        # overlapping word times
    out = highlights.build(_project(tmp_path, [good, bad], [(0, 6, [])], duration=6.0))
    assert out["precision"]["level"] == "mixed" and out["precision"]["unreliable_segments"] == [1]
    assert [e["text"] for e in out["events"]] == ["5"]                              # the broken segment contributes no word-level events


def test_events_stay_inside_short_audio(tmp_path):
    out = highlights.build(_project(tmp_path, [[("99", 4.8, 5.0)]], [(0, 5, [])], duration=5.0))
    _check_invariants(out, 5.0)
    assert out["events"][0]["end"] == 5.0


# ---------- real transcript (the golden sample): word-level, scene 7 keyword is NOT moved ----------
def _sample(tmp_path: Path) -> Path:
    for f in ("transcript.json", "scene_plan.json", "prompts_map.json", "composition.json"):
        shutil.copy(FIX / "plan_sample" / f, tmp_path / f)
    return tmp_path


def test_real_sample_precision_and_invariants(tmp_path):
    out = highlights.build(_sample(tmp_path))
    assert out["precision"]["level"] == "word" and out["precision"]["unreliable_segments"] == []
    _check_invariants(out, 70.131)
    by = {e["text"]: e for e in out["events"] if e["kind"] == "keyword"}
    assert by["n8n, Zapier, Make"]["timing"] == "estimated"                       # 0.55 s from the nearest word: ambiguous, left alone and reported
    assert by["Routine tasks"]["timing"] == "word" and by["Routine tasks"]["start"] == 57.75


def test_apply_emphasis_moves_headline_and_leaves_estimated_alone(tmp_path):
    pdir = _sample(tmp_path)
    comp = json.loads((pdir / "composition.json").read_text(encoding="utf-8"))
    before = {s["id"]: [l.get("at") for l in s["layers"] if l.get("type") == "text"] for s in comp["scenes"]}
    changed = highlights.apply_emphasis(pdir, comp)
    after = {s["id"]: [l.get("at") for l in s["layers"] if l.get("type") == "text"] for s in comp["scenes"]}
    assert changed >= 1
    assert after[8] == [57.75] and before[8] != after[8]                             # scene 8 headline now starts on the spoken word
    assert after[7] == before[7]                                                      # scene 7 untouched (estimated keyword)


# ---------- the real renderer: where do Telugu subtitles actually land? (Chrome + Noto Sans Telugu, stills of 360x640 / 640x360) ----------
def _render_ready() -> str | None:
    import socket
    if not shutil.which("node") or not shutil.which("npx"):
        return "node/npx not on PATH"
    if not (config.REMOTION_DIR / "node_modules" / "@remotion" / "renderer").exists():
        return "remotion dependencies are not installed"
    try:
        [socket.create_connection((h, 443), timeout=4).close() for h in ("fonts.googleapis.com", "fonts.gstatic.com")]
    except OSError:
        return "Google Fonts unreachable (the renderer fetches Poppins/Noto Sans Telugu at render time)"
    return None


def _ink_box(png: Path, lower_from: float = 0.6):
    import numpy as np
    from PIL import Image
    im = np.array(Image.open(png).convert("RGB")).astype(int)
    h, w, _ = im.shape
    band = im.mean(axis=2)[int(lower_from * h):, :]
    ink = band > np.median(band) + 60                       # text is much brighter than the dark gradient behind it
    ys, xs = np.where(ink)
    assert len(xs) > 150, "no subtitle ink found: the caption did not render"
    return xs.min() / w, xs.max() / w, (ys.min() / h) + lower_from, (ys.max() / h) + lower_from


def test_subtitles_stay_inside_safe_area_in_the_real_renderer(tmp_path):
    why = _render_ready()
    if why:
        pytest.skip(why)
    import subprocess
    seven = "ఈరోజులో మనం చేత్లో మోబైలేకుండా ఒక్క క్షనం కూడా".split()
    long7 = "ఉహించుకొలేమ్ మోబైలేకుండా కార్యక్రమాలకు ఆలోచించినప్పుడు ప్రపంచమంతటా చేసుకుంటున్నారు తెలుసుకోవాలంటే".split()

    from VIDEO_ENGINE.stages import captions as cap

    def comp(words, w, h):
        ws = [{"w": x, "start": 1.0 + 0.4 * i, "end": 1.0 + 0.4 * i + 0.35} for i, x in enumerate(words)]
        return {"meta": {"fps": 15, "width": w, "height": h, "audio": "audio_test.wav", "duration": 6.0, "subtitles": True, "palette": ["#0B1D26", "#F2A541", "#2A9D8F"]},
                "scenes": [{"id": 1, "start": 0, "end": 6, "camera": {"move": "static", "from": 1, "to": 1, "focus": [0.5, 0.5]},
                            "layers": [{"type": "background", "kind": "gradient", "colors": ["#0B1D26", "#2A9D8F"], "z": 0}]}], "words": ws,
                "captions": cap.build(ws, "9:16" if h > w else "16:9", [])}                   # the lines are built by the backend (stages/captions.py), Subtitles.tsx only draws them
    cases = {"portrait_7": (comp(seven, 1080, 1920), True), "landscape_7": (comp(seven, 1920, 1080), False), "portrait_long7": (comp(long7, 1080, 1920), True)}
    (tmp_path / "cases.json").write_text(json.dumps({"scale": 0.3333, "cases": [{"name": n, "frame": 33, "props": c} for n, (c, _) in cases.items()]}, ensure_ascii=False), encoding="utf-8")
    cmd = f'npx tsx scripts/caption_probe.ts "{tmp_path / "cases.json"}" "{tmp_path / "out"}"'
    for attempt in range(2):                                                                      # the renderer start can fail once on a locked temp file (Windows): one retry
        r = subprocess.run(cmd, cwd=config.REMOTION_DIR, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        if r.returncode == 0:
            break
    if r.returncode != 0 and "fetchFontData" in (r.stderr + r.stdout):
        pytest.skip("the web fonts could not be downloaded at render time (network): not a code failure")
    assert r.returncode == 0, (r.stderr or r.stdout)[-600:]
    m, tol = config.SAFE_AREA["margin"], 0.012
    for name, (_, portrait) in cases.items():
        x0, x1, y0, y1 = _ink_box(tmp_path / "out" / f"{name}.png")
        assert x0 >= m - tol and x1 <= 1 - m + tol, f"{name}: caption spans {x0:.3f}-{x1:.3f} of the width, outside the {m:.0%} margins"
        assert y1 <= 1 - (config.SAFE_AREA["portrait_ui_bottom"] if portrait else m) + tol, f"{name}: caption bottom at {y1:.3f}, inside the covered/unsafe zone"
        assert y0 >= m, f"{name}: caption top at {y0:.3f}"


