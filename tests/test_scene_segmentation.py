"""Scene Segmentation (backend/scene_segmentation.py): synthetic transcripts, mocked LLM, deterministic fallback, validation, caching, and that it never starts by itself.
Run: python -m pytest tests/test_scene_segmentation.py -q"""
import importlib
import json

import pytest

from backend import autoplan, config, jobs, pipeline, plan_input, promptgen
from backend import scene_segmentation as ss
from backend.transcribe import Segment, Transcript, Word

_m7 = importlib.import_module("test_m7")
client, create, wait_job = _m7.client, _m7.create, _m7.wait_job


def W(w, a, b, timing=None):
    return Word(w=w, start=a, end=b, timing=timing)


def project(tmp_path, segments, duration=None):
    segs = [Segment(id=i, start=s[0].start, end=s[-1].end, text=" ".join(w.w for w in s), words=s) for i, s in enumerate(segments)]
    t = Transcript(language="te", duration=duration or segs[-1].end + 0.5, segments=segs)
    (tmp_path / "transcript.json").write_text(t.model_dump_json(indent=1), encoding="utf-8")
    return t


def sentence(words, start, step=0.5):
    """words = list of texts; evenly timed from `start`."""
    return [W(w, round(start + i * step, 3), round(start + (i + 1) * step - 0.05, 3)) for i, w in enumerate(words)]


class Ask:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), 0

    def __call__(self, user, system="", timeout=0):
        self.calls += 1
        r = self.replies[min(self.calls - 1, len(self.replies) - 1)]
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)


def scenes_of(*groups):
    return {"scenes": [{"units": g, "beat": f"beat {i + 1}", "objective": "x", "boundary_after": {"type": "topic_change", "reason": "the idea changes"}} for i, g in enumerate(groups)]}


def _analysis_done(pdir):
    """The Audio Analyzer is recorded as finished for this project (Scene Segmentation starts after it: the orchestrator reads that record)."""
    from SYSTEM.core import pipeline_state as ps
    st = ps.init_default_state(pdir)
    for sid in ("audio", "analyzer"):
        st.stages[sid].status = "completed"
    ps.save_pipeline_state(pdir, st)


def three_sentences(tmp_path, gap=0.3):
    a = sentence(["మన", "గుండె", "కొట్టుకుంటుంది."], 0.0)
    b = sentence(["అది", "రక్తాన్ని", "పంపిస్తుంది."], a[-1].end + gap)
    c = sentence(["కానీ", "వ్యాయామం", "అవసరం."], b[-1].end + gap)
    out = project(tmp_path, [a, b, c])
    _analysis_done(tmp_path)
    return out


def _prep(tmp_path):
    three_sentences(tmp_path)
    inp = ss.read_input(tmp_path)
    return inp, ss.build_units(inp)


def by_words(*ranges):
    """The answer of the LLM as word ranges (1-based): (first, last) per scene."""
    return {"scenes": [{"first_word": a, "last_word": b, "beat": f"beat {i + 1}", "objective": "x", "boundary_after": {"type": "concept_change", "reason": "a different idea starts"}} for i, (a, b) in enumerate(ranges)]}


def words_of(out):
    return " ".join(s["transcript"] for s in out["scenes"])


@pytest.fixture
def short_scenes(monkeypatch):
    """Synthetic fixtures with scenes of one or two seconds: the minimum scene length (configurable, A2V_SEG_SOFT_MIN) is lowered so the test is about what its name says, not about a too short
    last scene joining the one before it (that rule has its own tests below)."""
    monkeypatch.setattr(ss, "SOFT_MIN", 1.0)


ALL = "మన గుండె కొట్టుకుంటుంది. అది రక్తాన్ని పంపిస్తుంది. కానీ వ్యాయామం అవసరం."


# ---------- the seven stages on synthetic fixtures ----------
def test_one_sentence_one_scene_with_exact_narration_and_word_times(tmp_path):
    t = project(tmp_path, [sentence(["మన", "గుండె", "కొట్టుకుంటుంది."], 0.4)])
    out = ss.run(tmp_path, ask=Ask(scenes_of([1])))
    sc = out["scenes"][0]
    assert len(out["scenes"]) == 1 and sc["transcript"] == "మన గుండె కొట్టుకుంటుంది." and sc["scene_id"] == "scene_001"
    assert (sc["start_time"], sc["end_time"]) == (t.segments[0].words[0].start, t.segments[0].words[-1].end) and sc["timing_source"] == "aligned_words"
    assert sc["source_word_ids"] == ["w001", "w002", "w003"] and sc["boundary_before"]["type"] == "start" and sc["boundary_after"]["type"] == "end"
    assert [s["status"] for s in out["stages"]] == ["completed"] * 7 and [s["name"] for s in out["stages"]] == list(ss.STAGES)


def test_related_sentences_merge_and_a_topic_change_splits_and_it_is_not_one_scene_per_sentence(tmp_path, short_scenes):
    three_sentences(tmp_path)
    out = ss.run(tmp_path, ask=Ask(scenes_of([1, 2], [3])))
    assert [len(s["source_sentence_ids"]) for s in out["scenes"]] == [2, 1] and out["segmentation_method"] == "llm_semantic_grouping"
    assert words_of(out) == ALL and out["scenes"][0]["semantic_beat"] == "beat 1"
    assert out["scenes"][1]["boundary_before"] == out["scenes"][0]["boundary_after"] and out["needs_review"] is False


def test_a_long_sentence_is_offered_as_clauses_and_can_split_at_a_clause(tmp_path):
    long = sentence(["ఇది,", "మొదటి", "భాగం", "గురించి", "మాట్లాడుతుంది,", "ఆ", "తర్వాత", "రెండో", "భాగం", "వస్తుంది."], 0.0, step=1.2)       # 12 s, commas
    project(tmp_path, [long])
    units = ss.build_units(ss.read_input(tmp_path))
    assert len(units) >= 2 and units[0]["clause"] is True and units[-1]["sentence_end"] is True
    out = ss.run(tmp_path, ask=Ask(scenes_of([1], list(range(2, len(units) + 1)))))
    assert len(out["scenes"]) == 2 and out["scenes"][0]["boundary_after"]["evidence"][0] == "clause_boundary" and words_of(out) == " ".join(w.w for w in long)


def test_mixed_telugu_english_numbers_and_repeated_words_are_kept_exactly(tmp_path):
    ws = sentence(["ఈ", "API", "ప్రతి", "ప్రతి", "2024", "లో", "work", "చేస్తుంది!"], 0.0)
    project(tmp_path, [ws])
    out = ss.run(tmp_path, ask=Ask(scenes_of([1])))
    assert out["scenes"][0]["transcript"] == "ఈ API ప్రతి ప్రతి 2024 లో work చేస్తుంది!" and len(out["scenes"][0]["source_word_ids"]) == 8


def test_a_segment_without_word_times_uses_sentence_times_and_says_so(tmp_path):
    a = sentence(["ఒకటి", "రెండు."], 0.0)
    t = Transcript(language="te", duration=8.0, segments=[Segment(id=0, start=0, end=a[-1].end, text="ఒకటి రెండు.", words=a),
                                                           Segment(id=1, start=3.0, end=6.0, text="మూడు నాలుగు ఐదు.", words=[])])
    (tmp_path / "transcript.json").write_text(t.model_dump_json(), encoding="utf-8")
    out = ss.run(tmp_path, ask=Ask(scenes_of([1, 2])))
    assert out["scenes"][0]["timing_source"] == "sentence_timestamps" and out["scenes"][0]["end_time"] == 6.0 and out["scenes"][0]["warnings"]
    assert out["validation"]["status"] == "warning" and out["stages"][6]["status"] == "warning"


def test_a_segment_the_review_emptied_is_no_word_and_no_warning(tmp_path, short_scenes):
    """The LLM review decides what stays: a segment whose words it removed has no text and no words. It must not become an empty 'word' with sentence times (a false word count and warning)."""
    a, b = sentence(["ఒకటి", "రెండు."], 0.0), sentence(["మూడు", "నాలుగు."], 4.0)
    t = Transcript(language="te", duration=8.0, segments=[Segment(id=0, start=0, end=a[-1].end, text="ఒకటి రెండు.", words=a),
                                                           Segment(id=1, start=1.5, end=2.5, text="", words=[]),
                                                           Segment(id=2, start=4.0, end=b[-1].end, text="మూడు నాలుగు.", words=b)])
    (tmp_path / "transcript.json").write_text(t.model_dump_json(), encoding="utf-8")
    inp = ss.read_input(tmp_path)
    assert len(inp["words"]) == 4 and [s["id"] for s in inp["segments"]] == [0, 2]
    out = ss.run(tmp_path, ask=Ask(scenes_of([1, 2])))
    assert out["validation"]["warnings"] == [] and out["source_data"]["word_count"] == 4
    assert [s["timing_source"] for s in out["scenes"]] == ["aligned_words"] and words_of(out) == "ఒకటి రెండు. మూడు నాలుగు."


def test_the_cut_point_breakdown_adds_up_to_the_potential_cuts(tmp_path):
    long = sentence(["ఇది,", "మొదటి", "భాగం", "గురించి", "మాట్లాడుతుంది,", "ఆ", "తర్వాత", "రెండో", "భాగం", "వస్తుంది."], 0.0, step=1.2)
    short = sentence(["అది", "చివరి", "భాగం."], long[-1].end + 0.3)
    project(tmp_path, [long, short])
    d = ss.run(tmp_path, ask=Ask(scenes_of([1], [2], [3])))["sentence_and_clause_detection"]
    by_type = d["candidate_cut_points_by_type"]
    assert sum(by_type.values()) == d["potential_cut_count"] and by_type["clause_ends"] >= 1


def test_a_scene_a_fraction_of_a_second_over_the_guideline_is_not_flagged_but_a_clearly_long_one_is(tmp_path):
    def long_scene(step):
        words = ["ఒకటి"] * 9 + ["రెండు."]
        project(tmp_path, [sentence(words, 0.0, step=step)])
        return ss.run(tmp_path, ask=Ask(by_words((1, 10))))["scenes"][0]
    near = long_scene(1.208)                                              # 12.03 s: the guideline is 3-12 s
    assert 12.0 < near["end_time"] - near["start_time"] < ss.SOFT_MAX + ss.LONG_TOL and near["warnings"] == []
    far = long_scene(1.5)                                                 # 14.95 s
    assert any("long scene" in str(w) for w in far["warnings"])


def test_estimated_word_times_of_corrected_words_are_reported_not_hidden(tmp_path):
    ws = sentence(["ఒకటి", "రెండు", "మూడు."], 0.0)
    ws[1] = W("రెండు", ws[1].start, ws[1].end, timing="estimated")
    project(tmp_path, [ws])
    out = ss.run(tmp_path, ask=Ask(scenes_of([1])))
    assert out["scenes"][0]["timing_source"] == "estimated_words" and "estimated" in out["scenes"][0]["warnings"][0]


# ---------- no LLM, bad LLM answers ----------
def test_without_the_llm_the_fallback_uses_pauses_and_says_the_meaning_was_not_judged(tmp_path):
    three_sentences(tmp_path, gap=0.9)
    out = ss.run(tmp_path, ask=Ask(promptgen.GenError("the Claude CLI was not found on this machine")))
    assert out["segmentation_method"] == "deterministic_fallback" and out["semantic_confidence"] == "reduced" and out["needs_review"] is True
    assert out["llm"]["status"] == "unavailable" and out["scenes"][0]["semantic_beat"] is None
    assert [s["status"] for s in out["stages"]][2:5] == ["warning"] * 3 and words_of(out) == ALL


def test_a_short_pause_does_not_force_a_new_scene_but_a_pause_after_enough_narration_does(tmp_path):
    a = sentence(["ఒకటి", "రెండు", "మూడు", "నాలుగు", "ఐదు", "ఆరు", "ఏడు."], 0.0)                     # 3.3 s
    b = sentence(["ఎనిమిది", "తొమ్మిది", "పది."], a[-1].end + 0.1)
    project(tmp_path, [a, b])
    short = ss.run(tmp_path, ask=Ask(RuntimeError("x")))
    assert len(short["scenes"]) == 1                                                      # a 0.1 s pause: one scene
    b2 = sentence(["ఎనిమిది", "తొమ్మిది", "పది", "పదకొండు", "పన్నెండు", "పదమూడు", "పద్నాలుగు."], a[-1].end + 1.0)      # a 1.0 s pause, the second part is long enough too
    project(tmp_path, [a, b2])
    long = ss.run(tmp_path, ask=Ask(RuntimeError("x")))
    assert len(long["scenes"]) == 2 and long["scenes"][0]["boundary_after"]["type"] == "pause"


def _tail_project(tmp_path, first_words, last_words):
    """Two sentences 0.3 s apart: `first_words` and `last_words` are numbers of words (0.5 s each)."""
    names = ["ఒకటి", "రెండు", "మూడు", "నాలుగు", "ఐదు", "ఆరు", "ఏడు", "ఎనిమిది", "తొమ్మిది", "పది", "పదకొండు", "పన్నెండు"]
    texts = lambda n: [names[i % len(names)] for i in range(n)]
    a = sentence(texts(first_words - 1) + [names[0] + "."], 0.0)
    b = sentence(texts(last_words - 1) + [names[1] + "."], a[-1].end + 0.3)
    project(tmp_path, [a, b])


def test_a_last_scene_that_is_too_short_joins_the_one_before_it_whoever_made_the_grouping(tmp_path):
    """Claude is told the length guideline but nothing checked it: a last scene of two seconds stayed alone, was reported as a "short scene" warning and the warning stopped the pipeline."""
    _tail_project(tmp_path, 5, 4)                                                          # 2.45 s, then 1.95 s
    out = ss.run(tmp_path, ask=Ask(by_words((1, 5), (6, 9))))
    assert out["segmentation_method"] == "llm_semantic_grouping" and len(out["scenes"]) == 1 and out["scenes"][0]["word_range"] == [0, 8]
    assert out["scenes"][0]["boundary_after"]["type"] == "end" and not [w for w in out["validation"]["warnings"] if "short scene" in w]
    ws = ss.read_input(tmp_path)["words"]
    assert len(ss.merge_short_scenes(ws, [{"first": 0, "last": 4}, {"first": 5, "last": 8}])) == 1 and len(ss.merge_short_scenes(ws, [{"first": 0, "last": 8}])) == 1
    project(tmp_path, [sentence(["ఒకటి", "రెండు", "మూడు", "నాలుగు", "ఐదు", "ఆరు", "ఏడు."], 0.0), sentence(["ఎనిమిది", "తొమ్మిది", "పది."], 4.4)])       # without Claude: the same rule
    fb = ss.run(tmp_path, ask=Ask(RuntimeError("x")))
    assert fb["segmentation_method"] == "deterministic_fallback" and len(fb["scenes"]) == 1


def test_a_short_last_scene_stays_alone_when_joining_it_would_make_the_scene_before_too_long(tmp_path):
    _tail_project(tmp_path, 22, 4)                                                         # 10.95 s, then 1.95 s: together 13.2 s, above the 12 s guideline
    out = ss.run(tmp_path, ask=Ask(by_words((1, 22), (23, 26))))
    assert len(out["scenes"]) == 2 and [d["code"] for d in out["scenes"][1]["warning_details"]] == ["short_scene"]


def test_a_segmentation_made_under_older_scene_rules_is_not_fresh(tmp_path):
    three_sentences(tmp_path)
    ss.run(tmp_path, ask=Ask(scenes_of([1, 2], [3])))
    assert ss.load_fresh(tmp_path) is not None
    f = tmp_path / "scene_segmentation.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data["timing_rules"] = ss.TIMING_RULES - 1                                             # made before the short-scene rule
    f.write_text(json.dumps(data), encoding="utf-8")
    assert ss.load_fresh(tmp_path) is None


def test_scenes_never_overlap_when_the_words_of_the_source_overlap(tmp_path, short_scenes):
    a = sentence(["మన", "గుండె", "కొట్టుకుంటుంది."], 0.0)
    b = sentence(["అది", "రక్తాన్ని", "పంపిస్తుంది."], 1.6)
    a[-1].end = 1.9                                                       # the last word of the first sentence ends 0.3 s after the next one starts
    project(tmp_path, [a, b])
    out = ss.run(tmp_path, ask=Ask(scenes_of([1], [2])))
    s1, s2 = out["scenes"]
    assert s1["end_time"] == s2["start_time"] == 1.6 and s1["end_time_word"] == 1.9           # ended where the next one starts, the original end is kept
    assert [n["scene"] for n in out["validation"]["notes"] if n["code"] == "scene_end_adjusted"] == ["scene_001"]
    assert not [w for w in out["validation"]["warnings"] if "overlapping" in w]                  # (the short-scene warnings of this tiny fixture are unrelated)
    words = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))["segments"][0]["words"]
    assert words[-1]["end"] == 1.9                                                              # the words themselves are untouched
    assert "end_time_word" not in s2


def test_a_failed_segmentation_leaves_the_analysis_files_untouched_and_writes_nothing(tmp_path):
    three_sentences(tmp_path)
    (tmp_path / "audio_analysis.json").write_text("{}", encoding="utf-8")
    before = {f.name: f.read_bytes() for f in tmp_path.iterdir() if f.is_file()}
    bad = {"scenes": [{"units": [1, 1], "beat": "x", "objective": "x", "boundary_after": {"type": "topic_change", "reason": "x"}}]}      # a unit twice: rejected, and the fallback is used, never a half result
    out = ss.run(tmp_path, ask=Ask(bad))
    assert out["segmentation_method"] == "deterministic_fallback"
    assert {n: b for n, b in before.items() if n in ("transcript.json", "audio_analysis.json")} == {n: (tmp_path / n).read_bytes() for n in ("transcript.json", "audio_analysis.json")}
    assert not (tmp_path / "scene_segmentation.json.part").exists()
    (tmp_path / "scene_segmentation.json").unlink()
    (tmp_path / "transcript.json").write_text("not json", encoding="utf-8")
    with pytest.raises(ss.SourceError):
        ss.run(tmp_path, ask=Ask(bad))
    assert not (tmp_path / "scene_segmentation.json").exists() and not (tmp_path / "scene_segmentation.json.part").exists()      # nothing half-written


def test_a_segmentation_file_of_an_older_format_is_not_fresh(tmp_path):
    three_sentences(tmp_path)
    out = ss.run(tmp_path, ask=Ask(scenes_of([1, 2], [3])))
    assert ss.load_fresh(tmp_path) is not None
    old = dict(out, schema_version="1.0")
    (tmp_path / "scene_segmentation.json").write_text(json.dumps(old), encoding="utf-8")
    assert ss.load_fresh(tmp_path) is None                         # the page asks for a new run instead of showing scenes without source links


def test_the_numbers_copied_with_a_colon_from_the_input_are_repaired_without_a_second_call():
    ok = json.dumps(by_words((1, 5), (6, 9)))
    a = ok.replace('"first_word": 1, "last_word": 5', '"first_word": 1:, "last_word": 5')                  # `70:,`
    b = ok.replace('"first_word": 6, "last_word": 9', '"first_word": 6:9')                                # `70:77,` (the last_word is lost)
    assert a != ok and b != ok
    assert ss._json_from(a) == ss._json_from(b) == json.loads(ok)
    twice = a.replace('1:,', '1:x,') + "\n\nCorrection: the first_word must be a number. Here is the valid JSON:\n\n" + ok + "\nDone."          # a broken answer (not repairable), then the corrected one
    assert ss._json_from(twice) == json.loads(ok)
    with pytest.raises(ValueError):
        ss._json_from("{\"scenes\": [oops]}")


def test_malformed_json_is_retried_once_with_the_problems_and_then_accepted(tmp_path):
    three_sentences(tmp_path)
    ask = Ask("not json at all", scenes_of([1, 2], [3]))
    out = ss.run(tmp_path, ask=ask)
    assert ask.calls == 2 and out["segmentation_method"] == "llm_semantic_grouping" and out["llm"]["attempts"] == 2


def test_an_answer_that_skips_or_repeats_units_is_rejected_and_the_fallback_keeps_every_word(tmp_path):
    three_sentences(tmp_path)
    out = ss.run(tmp_path, ask=Ask(scenes_of([1], [3]), scenes_of([1, 2], [2, 3])))       # unit 2 missing, then unit 2 twice
    assert out["segmentation_method"] == "deterministic_fallback" and out["llm"]["status"] == "rejected" and out["llm"]["problems"]
    assert words_of(out) == ALL and out["validation"]["transcript_coverage"] == "complete"


def test_an_unknown_boundary_type_is_a_problem(tmp_path):
    inp, units = _prep(tmp_path)
    _, problems = ss.check_grouping({"scenes": [{"units": [1], "beat": "a", "boundary_after": {"type": "fancy", "reason": "x"}}, {"units": [2, 3], "beat": "b", "boundary_after": {"type": "end", "reason": "x"}}]},
                                    inp, units, ss.allowed_cuts(inp, units))
    assert any("fancy" in p for p in problems)


def test_empty_input_is_an_error_and_changed_narration_is_a_validation_error(tmp_path):
    (tmp_path / "transcript.json").write_text(Transcript(language="te", duration=1.0, segments=[]).model_dump_json(), encoding="utf-8")
    with pytest.raises(ss.SourceError) as e:
        ss.run(tmp_path, ask=Ask(scenes_of([1])))
    assert e.value.code == "analysis_json_invalid" and not (tmp_path / "scene_segmentation.json").exists()
    three_sentences(tmp_path)
    inp = ss.read_input(tmp_path)
    units = ss.build_units(inp)
    g = {"beat": "a", "objective": "", "type": "topic_change", "reason": ""}
    cuts = ss.allowed_cuts(inp, units)
    scenes = ss.assemble(inp, units, cuts, [{**g, "first": units[0]["first"], "last": units[1]["last"]}, {**g, "first": units[2]["first"], "last": units[2]["last"]}], "llm_semantic_grouping")
    assert ss.validate(inp, scenes)["errors"] == []
    scenes[1]["transcript"] = "changed"
    assert ss.validate(inp, scenes)["errors"]


def test_same_input_gives_the_same_scenes_and_the_llm_is_asked_once(tmp_path):
    three_sentences(tmp_path)
    ask = Ask(scenes_of([1, 2], [3]))
    a = ss.run(tmp_path, ask=ask)
    b = ss.run(tmp_path, ask=ask)
    assert ask.calls == 1 and b["llm"]["status"] == "cached"
    key = lambda o: [(s["scene_id"], s["start_time"], s["end_time"], s["transcript"]) for s in o["scenes"]]
    assert key(a) == key(b)
    assert [c["source"] for c in a["llm"]["calls"]] == ["claude"] and [c["source"] for c in b["llm"]["calls"]] == ["cache"]      # where the time went is recorded
    assert "claude_s" in a["llm"]["calls"][0] and "claude_s" not in b["llm"]["calls"][0]
    assert {"1_read_input", "2_units_and_cuts", "3-5_grouping", "6_assemble", "7_validate", "write", "total"} <= set(b["timings_seconds"])


# ---------- pipeline: its own step, caching, invalidation, hand-off to Visual Planning ----------
def test_the_segment_step_is_cached_and_a_changed_transcript_invalidates_it_and_the_plan_input(tmp_path, monkeypatch):
    three_sentences(tmp_path)
    (tmp_path / "audio_analysis.json").write_text(json.dumps({"pauses": [], "validation": {"status": "ok"}}), encoding="utf-8")
    ask = Ask(scenes_of([1, 2], [3]))
    monkeypatch.setattr(promptgen, "run_claude", ask)
    assert pipeline.execute(tmp_path, "segment", pipeline.Ctx())["status"] == "ran"
    assert pipeline.execute(tmp_path, "segment", pipeline.Ctx())["status"] == "fresh" and ask.calls == 1
    pi = pipeline.STEPS["plan-input"].fingerprint(tmp_path, pipeline.Ctx())
    assert ss.load_fresh(tmp_path) is not None
    (tmp_path / "transcript_corrected.json").write_text((tmp_path / "transcript.json").read_text(encoding="utf-8").replace("వ్యాయామం", "వ్యాయమం"), encoding="utf-8")
    assert ss.load_fresh(tmp_path) is None                                                # the transcript changed: the old segmentation is stale
    assert pipeline.execute(tmp_path, "segment", pipeline.Ctx())["status"] == "ran"
    assert pipeline.STEPS["plan-input"].fingerprint(tmp_path, pipeline.Ctx()) != pi


def test_visual_planning_receives_the_segmentation_scenes_and_ignores_a_stale_one(tmp_path, short_scenes):
    three_sentences(tmp_path)
    (tmp_path / "audio_analysis.json").write_text("{}", encoding="utf-8")
    (tmp_path / "cuts.json").write_text(json.dumps({"cuts": [{"t": 1.0, "reason": "silence", "silence": 0.3}]}), encoding="utf-8")
    (tmp_path / "transcript_en.json").write_text(json.dumps({"language": "en", "duration": 6.0, "segments": [{"id": 0, "start": 0, "end": 2, "te": "x", "en": "one"}]}), encoding="utf-8")
    before = plan_input.build(tmp_path)
    assert "Candidate segments between cuts" in before and "Scene Segmentation already decided" not in before
    ss.run(tmp_path, ask=Ask(scenes_of([1, 2], [3])))
    after = plan_input.build(tmp_path)
    assert "Scene Segmentation already decided" in after and "S1 0.00-" in after and "S2 " in after and "beat: beat 1" in after and "C1 " not in after
    (tmp_path / "transcript_corrected.json").write_text((tmp_path / "transcript.json").read_text(encoding="utf-8").replace("వ్యాయామం", "వ్యాయమం"), encoding="utf-8")
    assert "Candidate segments between cuts" in plan_input.build(tmp_path)               # stale segmentation: not used


# ---------- the API and: nothing starts by itself ----------
def _analyzed(pid):
    pdir = config.PROJECTS_DIR / pid
    three_sentences(pdir)
    (pdir / "audio_analysis.json").write_text(json.dumps({"pauses": [], "validation": {"status": "ok"}}), encoding="utf-8")
    (pdir / "cuts.json").write_text(json.dumps({"cuts": []}), encoding="utf-8")                   # the analysis is finished: its transcript and its cuts
    return pdir


@pytest.fixture(autouse=True)
def reviews_pass(monkeypatch):
    """These tests are about Scene Segmentation, not about the Audio Analyzer's LLM review (the stage gate waits for it: tests/test_stage_gate.py, tests/test_autonomous_pipeline.py)."""
    from SYSTEM.policies import llm_review
    monkeypatch.setattr(llm_review, "is_stage_review_passed", lambda *a, **k: (True, "passed", {}))
    from VIDEO_ENGINE.stages import transcript_review
    monkeypatch.setattr(transcript_review, "is_verified", lambda pdir: True)                 # the Audio Analyzer's LLM check of the transcript has its own tests


def test_segmentation_runs_only_on_the_run_request_and_opening_it_starts_nothing(client, monkeypatch):
    pid = create(client).json()["id"]
    assert client.get(f"/projects/{pid}/segmentation").json()["error"]["code"] == "segmentation_missing"
    assert client.post(f"/projects/{pid}/segmentation/run").json()["error"]["code"] == "analysis_json_missing"
    _analyzed(pid)
    ask = Ask(scenes_of([1, 2], [3]))
    monkeypatch.setattr(promptgen, "run_claude", ask)
    assert client.get(f"/projects/{pid}/segmentation").status_code == 409 and ask.calls == 0          # viewing starts nothing
    assert any(s["id"] == "segmentation" and s["status"] == "queued" and "Run" in s["detail"] for s in client.get(f"/projects/{pid}/pipeline").json()["stages"])
    r = client.post(f"/projects/{pid}/segmentation/run")
    assert r.status_code == 202 and r.json()["steps"] == ["segment"]
    wait_job(client, pid)
    d = client.get(f"/projects/{pid}/segmentation").json()
    n_scenes = len(d["scenes"])
    assert n_scenes >= 1 and d["stale"] is False and [s["name"] for s in d["stages"]] == list(ss.STAGES)
    st = {s["id"]: s for s in client.get(f"/projects/{pid}/pipeline").json()["stages"]}
    assert st["segmentation"]["status"] == "completed" and st["segmentation"]["detail"] == f"{n_scenes} scenes segmented" and ask.calls == 1


def test_no_stage_starts_after_the_audio_analysis_finishes(client, monkeypatch):
    """The transcribe job used to start Visual Planning (and its LLM calls) by itself when it finished. Now it must not."""
    pid = create(client).json()["id"]
    started = []
    monkeypatch.setattr(autoplan, "start", lambda pdir: started.append("plan") or {})
    monkeypatch.setattr(autoplan, "maybe_start", lambda pdir: started.append("plan"))
    monkeypatch.setattr(promptgen, "run_claude", lambda *a, **k: started.append("llm") or "{}")
    monkeypatch.setattr(pipeline, "execute", lambda pdir, name, ctx: {"name": name, "status": "ran", "seconds": 0, "msg": ""})
    assert client.post(f"/projects/{pid}/transcribe").status_code == 202
    wait_job(client, pid)
    assert started == [] and not (config.PROJECTS_DIR / pid / "scene_segmentation.json").exists() and not (config.PROJECTS_DIR / pid / "scene_plan.json").exists()
    assert jobs.current(pid).names == ("audio", "analyzer")                              # the analysis stages only: segmentation is not part of the chain
    assert "segment" not in pipeline.CHAINS["transcribe"]


# ---------- the sample transcript JSON in testing_audio_files (a real Audio Analyzer result, 57.6 s, with LLM-corrected words) ----------
SAMPLE = config.PROJECT_ROOT / "testing_audio_files" / "sample json.txt"


@pytest.mark.skipif(not SAMPLE.exists(), reason="testing_audio_files/sample json.txt is not there")
def test_the_sample_audio_analyzer_json_segments_with_and_without_the_llm(tmp_path):
    (tmp_path / "transcript.json").write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    t = json.loads(SAMPLE.read_text(encoding="utf-8"))
    all_words = [w["w"] for s in t["segments"] for w in s["words"]]
    inp = ss.read_input(tmp_path)
    units = ss.build_units(inp)
    assert [w["text"] for w in inp["words"]] == all_words and len(units) >= len(t["segments"])
    # with the LLM (mocked): one scene per two units
    pairs = [list(range(i, min(i + 2, len(units)) + 1)) if i < len(units) else [i] for i in range(1, len(units) + 1, 2)]
    pairs = [[u for u in g if u <= len(units)] for g in pairs]
    out = ss.run(tmp_path, ask=Ask(scenes_of(*pairs)))
    assert out["validation"]["transcript_coverage"] == "complete" and words_of(out) == " ".join(all_words)
    assert out["scenes"][0]["start_time"] == t["segments"][0]["words"][0]["start"] and out["scenes"][-1]["end_time"] == t["segments"][-1]["words"][-1]["end"]
    assert any(s["timing_source"] == "estimated_words" for s in out["scenes"])                # the corrected words of the sample keep their estimated timing: reported, not hidden
    # without the LLM: the deterministic fallback keeps every word too, and says so
    (tmp_path / "scene_llm_cache.json").unlink()
    fb = ss.run(tmp_path, ask=Ask(RuntimeError("no llm")))
    assert fb["segmentation_method"] == "deterministic_fallback" and words_of(fb) == " ".join(all_words) and fb["needs_review"] is True
    assert all(a["end_time"] <= b["start_time"] + 0.05 for a, b in zip(fb["scenes"], fb["scenes"][1:]))


# ---------- meaning, not segments: split a long multi-idea segment, merge short related ones ----------
def long_segment_project(tmp_path):
    """One recognizer segment of 8.6 s with no punctuation and no pause (two ideas: how long the trip takes, and being away from everything), then a second short segment."""
    a = sentence(["చేరడానికి", "ఎనిమిది", "నెలలు", "ప్రయాణం", "చేయాలి", "ఆ", "సమయంలో", "కుటుంబం", "భూమికి", "దూరంగా", "ఉండాలి"], 0.0, step=0.8)
    b = sentence(["అక్కడ", "సంభాషణ", "ఆలస్యం."], a[-1].end + 0.2)
    return project(tmp_path, [a, b])


def test_a_long_segment_with_two_ideas_is_split_inside_the_segment_at_an_allowed_cut_and_every_word_keeps_its_time(tmp_path, short_scenes):
    t = long_segment_project(tmp_path)
    inp = ss.read_input(tmp_path)
    cuts = ss.allowed_cuts(inp, ss.build_units(inp))
    assert 4 in cuts and 4 != inp["segments"][0]["last"]                                  # after word 5 a cut is allowed inside the long segment
    out = ss.run(tmp_path, ask=Ask(by_words((1, 5), (6, 11), (12, 14))))
    a, b, c = out["scenes"]
    assert (a["start_time"], a["end_time"]) == (t.segments[0].words[0].start, t.segments[0].words[4].end) and b["start_time"] == t.segments[0].words[5].start
    assert a["source_segment_ids"] == [0] and b["source_segment_ids"] == [0] and c["source_segment_ids"] == [1]
    assert a["boundary_after"]["inside_segment"] is True and b["starts_inside_segment"] is True and b["boundary_after"]["inside_segment"] is False
    assert words_of(out) == " ".join(w.w for s in t.segments for w in s.words)
    assert [w for s in out["scenes"] for w in s["source_word_ids"]] == [f"w{i:03d}" for i in range(1, 15)]


def test_a_cut_at_a_place_that_is_not_allowed_is_refused(tmp_path):
    long_segment_project(tmp_path)
    ask = Ask(by_words((1, 1), (2, 14)), by_words((1, 1), (2, 14)))                      # after word 1 only 0.75 s of narration: too early for a free cut
    out = ss.run(tmp_path, ask=ask)
    assert out["segmentation_method"] == "deterministic_fallback" and out["llm"]["status"] == "rejected" and any("not an allowed cut" in p for p in out["llm"]["problems"])
    assert " ".join(s["transcript"] for s in out["scenes"]) == " ".join(w["text"] for w in ss.read_input(tmp_path)["words"])


def test_short_related_segments_are_merged_into_one_scene_that_lists_all_their_segments(tmp_path):
    segs = [sentence(["ఇది", "ఒక."], 0.0), sentence(["చిన్న", "వాక్యం."], 1.2), sentence(["కానీ", "ఒకే", "ఆలోచన."], 2.4), sentence(["ఇప్పుడు", "కొత్త", "విషయం", "మొదలు", "మరో", "చోట", "కాలం."], 4.6)]
    project(tmp_path, segs)
    out = ss.run(tmp_path, ask=Ask(by_words((1, 7), (8, 14))))
    assert [s["source_segment_ids"] for s in out["scenes"]] == [[0, 1, 2], [3]] and out["scenes"][0]["transcript"] == "ఇది ఒక. చిన్న వాక్యం. కానీ ఒకే ఆలోచన."
    assert out["scenes"][0]["boundary_after"]["inside_segment"] is False


def test_the_fallback_cuts_a_scene_that_is_too_long_at_the_strongest_allowed_place(tmp_path):
    a = sentence(["ఒకటి", "రెండు", "మూడు", "నాలుగు,", "ఐదు", "ఆరు", "ఏడు", "ఎనిమిది,", "తొమ్మిది", "పది", "పదకొండు", "పన్నెండు", "పదమూడు", "పద్నాలుగు."], 0.0, step=1.0)
    project(tmp_path, [a])
    out = ss.run(tmp_path, ask=Ask(RuntimeError("x")))
    assert len(out["scenes"]) >= 2 and all(s["end_time"] - s["start_time"] <= ss.SOFT_MAX for s in out["scenes"]) and words_of(out) == " ".join(w.w for w in a)
    assert out["scenes"][0]["boundary_after"]["inside_segment"] is True and out["scenes"][0]["boundary_after"]["evidence"][0] == "clause_boundary"


def test_warnings_say_what_is_wrong_and_the_timing_source_is_not_blamed(tmp_path):
    long = sentence(["ఒకటి", "రెండు", "మూడు", "నాలుగు", "ఐదు", "ఆరు", "ఏడు", "ఎనిమిది", "తొమ్మిది", "పది", "పదకొండు", "పన్నెండు", "పదమూడు", "పద్నాలుగు."], 0.0, step=1.0)
    project(tmp_path, [long])
    out = ss.run(tmp_path, ask=Ask(by_words((1, 14))))                                  # the LLM keeps 14 s together
    sc = out["scenes"][0]
    assert sc["timing_source"] == "aligned_words" and [d["code"] for d in sc["warning_details"]] == ["long_scene"] and "13.9" in sc["warnings"][0] and "more than one idea" in sc["warnings"][0]
    assert out["validation"]["status"] == "warning" and out["validation"]["warnings"] == ["scene_001: " + sc["warnings"][0]]          # the summary lists the cause, not an empty list


def test_a_segment_that_ends_before_its_last_word_is_noted_with_the_evidence(tmp_path):
    a = sentence(["ఒకటి", "రెండు", "మూడు", "నాలుగు."], 0.0)                              # last word ends at 1.95
    b = sentence(["ఐదు", "ఆరు", "ఏడు."], a[-1].end)                                       # the next segment starts exactly where it ends
    t = Transcript(language="te", duration=4.0, segments=[Segment(id=0, start=0.0, end=1.75, text="x", words=a), Segment(id=1, start=b[0].start, end=b[-1].end, text="y", words=b)])
    (tmp_path / "transcript.json").write_text(t.model_dump_json(), encoding="utf-8")
    out = ss.run(tmp_path, ask=Ask(by_words((1, 7))))
    note = out["validation"]["notes"][0]
    assert note["code"] == "segment_end_before_last_word" and note["segment"] == 0 and note["continuous_with_next"] is True and "consistent" in note["message"]
    assert out["scenes"][0]["end_time"] == b[-1].end and out["scenes"][0]["start_time"] == 0.0                # the scene times come from the words


def test_the_same_input_always_gives_the_same_segmentation(tmp_path):
    long_segment_project(tmp_path)
    ask = Ask(by_words((1, 5), (6, 11), (12, 14)))
    first = ss.run(tmp_path, ask=ask)
    second = ss.run(tmp_path, ask=ask)
    pick = lambda o: [(s["scene_id"], s["start_time"], s["end_time"], s["transcript"], s["source_word_ids"], s["source_segment_ids"]) for s in o["scenes"]]
    assert pick(first) == pick(second) and ask.calls == 1
    for f in tmp_path.glob("scene_*"):
        f.unlink()
    fb1, fb2 = ss.run(tmp_path, ask=Ask(RuntimeError("x"))), ss.run(tmp_path, ask=Ask(RuntimeError("x")))
    assert pick(fb1) == pick(fb2)


def test_the_source_note_carries_what_the_audio_check_found(tmp_path):
    a = sentence(["ఒకటి", "రెండు", "మూడు", "నాలుగు."], 0.0)
    b = sentence(["ఐదు", "ఆరు", "ఏడు."], a[-1].end)
    t = Transcript(language="te", duration=4.0, segments=[Segment(id=0, start=0.0, end=1.75, text="x", words=a), Segment(id=1, start=b[0].start, end=b[-1].end, text="y", words=b)])
    (tmp_path / "transcript.json").write_text(t.model_dump_json(), encoding="utf-8")
    (tmp_path / "audio_analysis.json").write_text(json.dumps({"pauses": [], "validation": {"notes": [{"segment": 0, "code": "word_end_in_silence", "audio_check": "silence in the gap"}]}}), encoding="utf-8")
    out = ss.run(tmp_path, ask=Ask(by_words((1, 7))))
    note = out["validation"]["notes"][0]
    assert note["audio_check"] == "silence in the gap" and "audio check: silence in the gap" in note["message"] and "word times as the source has them" in note["message"]



# ---------- the existing analysis JSON is the input: no audio is processed, a missing or invalid JSON is an error ----------
def _no_audio_processing(monkeypatch):
    """Anything that would process the audio (ASR, silence detection, ffmpeg, the analysis writer) explodes: Scene Segmentation must never reach it."""
    from backend import audio_analysis, audio_utils, transcribe

    def boom(*a, **k):
        raise AssertionError("the audio was processed")
    for obj, name in ((transcribe, "transcribe"), (audio_analysis, "write"), (audio_analysis, "build"), (audio_utils, "silences"), (audio_utils, "to_wav16k"), (audio_utils, "_run")):
        monkeypatch.setattr(obj, name, boom)
    monkeypatch.setattr("subprocess.run", boom)
    monkeypatch.setattr("subprocess.Popen", boom)


def test_it_runs_from_the_existing_json_alone_without_touching_the_audio_or_the_json(client, monkeypatch):
    pid = create(client).json()["id"]
    pdir = config.PROJECTS_DIR / pid
    three_sentences(pdir)                                                  # only the final analysis JSON: no cuts.json, no audio_analysis.json
    assert not (pdir / "cuts.json").exists() and not (pdir / "audio_analysis.json").exists()
    before = {f.name: f.read_bytes() for f in pdir.iterdir() if f.is_file()}
    _no_audio_processing(monkeypatch)
    monkeypatch.setattr(promptgen, "run_claude", Ask(scenes_of([1, 2], [3])))
    assert client.post(f"/projects/{pid}/segmentation/run").status_code == 202
    wait_job(client, pid)
    d = client.get(f"/projects/{pid}/segmentation").json()
    assert "scenes" in d, (d, jobs.current(pid).error)
    assert len(d["scenes"]) >= 1 and d["source_audio_analysis"] is None and d["validation"]["transcript_coverage"] == "complete"      # (how many scenes the short sample makes depends on the scene length rules)
    after = {f.name: f.read_bytes() for f in pdir.iterdir() if f.is_file()}
    for name, data in before.items():
        if name not in ("job.json", "log.txt", "timings.json", ".build_state.json", "project.json", "pipeline_state.json"):
            assert after[name] == data, name                                # the transcript and every analysis file are unchanged


def test_a_missing_or_invalid_json_is_a_409_error_and_nothing_starts(client, monkeypatch):
    pid = create(client).json()["id"]
    pdir = config.PROJECTS_DIR / pid
    _no_audio_processing(monkeypatch)
    ask = Ask(scenes_of([1]))
    monkeypatch.setattr(promptgen, "run_claude", ask)
    r = client.post(f"/projects/{pid}/segmentation/run")
    assert r.status_code == 409 and r.json()["error"]["code"] == "analysis_json_missing" and "not processed" in r.json()["error"]["message"]
    (pdir / "transcript.json").write_text("{not json", encoding="utf-8")
    r = client.post(f"/projects/{pid}/segmentation/run")
    assert r.status_code == 409 and r.json()["error"]["code"] == "analysis_json_invalid" and "not processed again" in r.json()["error"]["message"]
    bad = Transcript(language="te", duration=2.0, segments=[Segment(id=0, start=0, end=1, text="x", words=[W("ఒకటి", 1.5, 0.5)])])        # a word that ends before it starts
    (pdir / "transcript.json").write_text(bad.model_dump_json(), encoding="utf-8")
    r = client.post(f"/projects/{pid}/segmentation/run")
    assert r.json()["error"]["code"] == "analysis_json_invalid" and "impossible times" in r.json()["error"]["message"]
    assert ask.calls == 0 and not (pdir / "scene_segmentation.json").exists() and not jobs.is_running(pid)
    assert [s["status"] for s in client.get(f"/projects/{pid}/pipeline").json()["stages"] if s["id"] == "segmentation"] == ["waiting"]      # there is no analysis to follow: the stage waits for it


# ---------- a short scene anywhere joins a neighbour ----------
def _words(*seconds):
    """Words of one second each: `seconds` words per scene."""
    ws, t, groups = [], 0.0, []
    for n in seconds:
        groups.append({"first": len(ws), "last": len(ws) + n - 1, "beat": f"b{len(groups) + 1}", "objective": None, "type": "concept_change", "reason": f"r{len(groups) + 1}"})
        ws += [{"start": t + i, "end": t + i + 1.0} for i in range(n)]
        t += n
    return ws, groups


def test_a_short_middle_scene_joins_the_neighbour_that_gives_the_shorter_scene_and_keeps_both_beats():
    """Real case (07-5df8): Claude left scene 8 of 9 alone at 2.6 s; only the last scene was ever merged, so the warning stayed and stopped the pipeline."""
    ws, g = _words(7, 2, 5)                                                                 # 7 s, 2 s, 5 s: joining the 5 s one gives 7 s, the 7 s one gives 9 s
    out = ss.merge_short_scenes(ws, g)
    assert [(x["first"], x["last"]) for x in out] == [(0, 6), (7, 13)] and out[1]["beat"] == "b2 + b3" and out[1]["reason"] == "r3"
    assert [(x["first"], x["last"]) for x in ss.merge_short_scenes(*_words(2, 6, 6))] == [(0, 7), (8, 13)]      # a short first scene joins the next one
    ws2, g2 = _words(2, 2, 2, 2, 2, 2, 2)
    out2 = ss.merge_short_scenes(ws2, g2)                                                                        # chains of short scenes keep merging until none is short, never beyond SOFT_MAX
    assert [x['last'] - x['first'] + 1 for x in out2] == [4, 4, 6]


def test_a_short_scene_stays_when_both_neighbours_are_too_long_to_take_it():
    ws, g = _words(11, 2, 11)
    assert len(ss.merge_short_scenes(ws, g)) == 3
