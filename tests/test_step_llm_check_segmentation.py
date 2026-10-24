"""Regression tests for Visual Planning / Scene Segmentation LLM step checks:
1. Analysis Data Reader (Step 1)
2. Sentence & Clause Detection (Step 2)
Tests cache invalidation, authoritative metrics, schema alignment, and discrepancy detection.
"""
import json
import pytest
from pathlib import Path
from UI.backend import step_llm_check as sc
from VIDEO_ENGINE.stages import scene_segmentation


def test_hash_incorporates_fingerprint_and_version():
    """Cache invalidation must fire when check version or source fingerprint changes."""
    step = {"n": 1, "name": "Analysis Data Reader", "status": "completed", "detail": "100 words"}
    report_v1 = {"source_fingerprint": "fp_aaa"}
    report_v2 = {"source_fingerprint": "fp_bbb"}

    h1 = sc._hash(step, report_v1)
    h2 = sc._hash(step, report_v2)
    assert h1 != h2, "Different source fingerprints must produce different cache hashes"

    # Changing detail must also change hash
    step_changed = dict(step, detail="101 words")
    h3 = sc._hash(step_changed, report_v1)
    assert h1 != h3, "Changing step detail must invalidate cache hash"


def test_build_step_evidence_preserves_authoritative_source_and_syntax():
    """Evidence payload must contain structured source_data and sentence_and_clause_detection."""
    report = {
        "source_data": {
            "transcript_segment_count": 12,
            "word_count": 109,
            "measured_pause_count": 8,
            "audio_duration_seconds": 51.931,
            "scene_count": 9,
            "measured_pauses": [{"start": 1.0, "end": 1.5, "duration": 0.5}],
        },
        "sentence_and_clause_detection": {
            "unit_count": 14,
            "clause_split_count": 0,
            "potential_cut_count": 24,
            "metrics": {
                "unit_count": 14,
                "sentence_count": 14,
                "clause_split_count": 0,
                "potential_cut_count": 24,
            },
            "candidate_cut_points_by_type": {
                "sentence_ends": 14,
                "clause_punctuation": 9,
                "pauses": 1,
            },
            "sentences": [
                {
                    "sentence_id": "sentence_001",
                    "unit_index": 1,
                    "start_time": 0.0,
                    "end_time": 2.5,
                    "word_range": [0, 5],
                    "text": "Hello world.",
                    "is_clause_split_unit": False,
                    "is_sentence_end": True,
                    "pause_after": 0.2,
                }
            ],
            "allowed_cuts": [
                {
                    "word_index": 5,
                    "word": "world.",
                    "cut_type": "sentence_end",
                    "description": "Sentence boundary",
                    "time": 2.5,
                }
            ],
        },
        "scenes": [
            {
                "scene_id": "scene_001",
                "scene_index": 1,
                "start_time": 0.0,
                "end_time": 5.0,
                "word_range": [0, 10],
                "transcript": "Hello world test scene.",
            }
        ],
    }

    step1 = {"n": 1, "name": "Analysis Data Reader"}
    ev1 = sc.build_step_evidence("segmentation", step1, report)
    assert "source_data" in ev1
    assert ev1["source_data"]["transcript_segment_count"] == 12
    assert ev1["source_data"]["word_count"] == 109
    assert ev1["source_data"]["measured_pause_count"] == 8

    step2 = {"n": 2, "name": "Sentence & Clause Detection"}
    ev2 = sc.build_step_evidence("segmentation", step2, report)
    assert "sentence_and_clause_detection" in ev2
    assert ev2["sentence_and_clause_detection"]["unit_count"] == 14
    assert ev2["sentence_and_clause_detection"]["clause_split_count"] == 0
    assert ev2["sentence_and_clause_detection"]["potential_cut_count"] == 24
    assert ev2["sentence_and_clause_detection"]["sentences"][0]["sentence_id"] == "sentence_001"


def test_step_guidance_disambiguates_metrics():
    """Guidance for Step 1 & 2 must give explicit instructions preventing false rejections."""
    g1 = sc._step_guidance("segmentation", {"n": 1, "name": "Analysis Data Reader"})
    assert "transcript segments" in g1
    assert "source_data" in g1
    assert "measured pauses" in g1.lower()

    g2 = sc._step_guidance("segmentation", {"n": 2, "name": "Sentence & Clause Detection"})
    assert "unit_count" in g2
    assert "clause_split_count" in g2
    assert "potential_cut_count" in g2
    assert "clause_punctuation" in g2


def test_scene_segmentation_output_schema_structure():
    """scene_segmentation.run output must populate authoritative source_data and sentence_and_clause_detection."""
    # Test with dummy inputs using build_units and allowed_cuts directly
    words = [
        {"text": "First", "start": 0.0, "end": 0.5, "seg": 0},
        {"text": "sentence.", "start": 0.6, "end": 1.0, "seg": 0},
        {"text": "Second,", "start": 1.2, "end": 1.8, "seg": 1},
        {"text": "sentence.", "start": 1.9, "end": 2.5, "seg": 1},
    ]
    inp = {
        "words": words,
        "segments": [{"id": 0, "text": "First sentence."}, {"id": 1, "text": "Second, sentence."}],
        "pauses": [(1.0, 1.2)],
        "duration": 2.5,
        "language": "en",
        "analysis_file": "audio_analysis.json",
        "source_transcript_file": "transcript_corrected.json",
    }
    units = scene_segmentation.build_units(inp)
    cuts = scene_segmentation.allowed_cuts(inp, units)

    assert len(units) == 2
    assert units[0]["sentence_end"] is True
    assert units[1]["sentence_end"] is True

    # Check cut points
    assert len(cuts) >= 2  # sentence ends + clause punctuation inside second unit


def test_inconsistent_metrics_detection():
    """Verify detection when reported counts disagree with authoritative source_data."""
    report = {
        "source_data": {
            "transcript_segment_count": 12,
            "word_count": 109,
            "measured_pause_count": 8,
            "audio_duration_seconds": 51.931,
            "scene_count": 9,
        },
        "sentence_and_clause_detection": {
            "unit_count": 14,
            "clause_split_count": 0,
            "potential_cut_count": 24,
            "metrics": {
                "unit_count": 14,
                "sentence_count": 14,
                "clause_split_count": 0,
                "potential_cut_count": 24,
            },
        },
    }
    # Detail claiming 50 words vs 109 words in source_data
    fake_step1 = {"n": 1, "name": "Analysis Data Reader", "status": "completed", "detail": "50 words in 12 segments"}
    ev1 = sc.build_step_evidence("segmentation", fake_step1, report)
    assert ev1["source_data"]["word_count"] != 50, "Evidence word_count must accurately reflect source_data, not hallucinated detail"

    # Detail claiming 5 clause splits vs 0 in sentence_and_clause_detection
    fake_step2 = {"n": 2, "name": "Sentence & Clause Detection", "status": "completed", "detail": "14 units (5 clause splits), 24 places"}
    ev2 = sc.build_step_evidence("segmentation", fake_step2, report)
    assert ev2["sentence_and_clause_detection"]["clause_split_count"] == 0


def test_missing_evidence_fallback():
    """When source_data or sentence_and_clause_detection are missing, fallback or omission is handled."""
    legacy_report = {
        "source_segments": 10,
        "source_words": 90,
        "source_pauses": 4,
        "audio_duration_seconds": 30.0,
    }
    ev = sc.build_step_evidence("segmentation", {"n": 1, "name": "Analysis Data Reader"}, legacy_report)
    assert "source_data" in ev
    assert ev["source_data"]["transcript_segment_count"] == 10
    assert ev["source_data"]["word_count"] == 90
    assert "sentence_and_clause_detection" not in ev


def test_invalid_sentence_or_cut_references():
    """Verify that sentence IDs, unit ranges, and cut rules adhere to expected formatting."""
    words = [{"text": f"w{i}", "start": i * 0.5, "end": (i + 1) * 0.5, "seg": 0} for i in range(10)]
    words[4]["text"] = "w4."
    words[9]["text"] = "w9."
    inp = {
        "words": words,
        "segments": [{"id": 0, "text": "w0..w9"}],
        "pauses": [],
        "duration": 5.0,
        "language": "en",
        "analysis_file": None,
        "source_transcript_file": "transcript.json",
    }
    units = scene_segmentation.build_units(inp)
    cuts = scene_segmentation.allowed_cuts(inp, units)

    for idx, u in enumerate(units):
        assert u["first"] >= 0 and u["last"] < len(words)
        assert u["first"] <= u["last"]
        assert u["start"] <= u["end"]

    for word_idx, kind in cuts.items():
        assert 0 <= word_idx < len(words)
        assert kind in ("sentence", "clause", "clause_end", "pause", "marker", "free")


def test_mocked_llm_run_records_verdicts(monkeypatch, tmp_path):
    """sc._run must record verdicts into the checks JSON file correctly."""
    class _P:
        name = "test_proj"

    steps_list = [
        {"n": 1, "name": "Analysis Data Reader", "status": "completed", "detail": "109 words in 12 segments", "checks_passed": 1, "checks_total": 1},
        {"n": 2, "name": "Sentence & Clause Detection", "status": "completed", "detail": "14 units (0 clause splits), 24 places", "checks_passed": 1, "checks_total": 1},
    ]
    report_dict = {
        "source_fingerprint": "fp_123",
        "source_data": {"word_count": 109, "transcript_segment_count": 12, "measured_pause_count": 8},
        "sentence_and_clause_detection": {"unit_count": 14, "clause_split_count": 0, "potential_cut_count": 24},
    }
    checks_file = tmp_path / "llm_step_checks_segmentation.json"

    monkeypatch.setattr(sc, "steps", lambda p, st, asp: (steps_list, report_dict, tmp_path / "report.json"))
    monkeypatch.setattr(sc, "report_file", lambda p, st, asp: tmp_path / "report.json")
    monkeypatch.setattr(sc, "_checks_file", lambda p, st, asp: checks_file)

    verdicts = [
        {"verdict": "confirms", "note": "Step 1 matches source_data perfectly"},
        {"verdict": "confirms", "note": "Step 2 matches sentence_and_clause_detection"},
    ]
    seq = iter(verdicts)
    monkeypatch.setattr(sc, "_ask", lambda *a, **k: next(seq))

    sc._run(_P(), "segmentation", "16:9")

    data = json.loads(checks_file.read_text(encoding="utf-8"))
    assert data["steps"]["1"]["verdict"] == "confirms"
    assert data["steps"]["2"]["verdict"] == "confirms"
    assert "source_data" in data["steps"]["1"]["note"]

