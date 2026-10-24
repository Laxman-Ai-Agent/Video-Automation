"""Verification suite: Scene Segmentation reads and uses the LLM-corrected transcript
from the previous Audio Analyzer stage (audio_analysis.json / transcript_corrected.json).

Guards:
- Reuses existing Audio Analyzer output JSON containing the LLM-corrected transcript.
- Uses the corrected transcript as the primary input for Scene Segmentation, script breakdown, and scene narration.
- Does not use the raw Whisper transcript as the primary narration source.
- Does not rerun ASR or repeat the LLM correction process.
- Preserves the original Whisper transcript separately for comparison and displays it alongside the corrected transcript.
- Ensures all scene boundaries, narration text, and downstream visual planning use the corrected transcript.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from VIDEO_ENGINE.stages import scene_segmentation
from VIDEO_ENGINE.stages.transcribe import Transcript, Segment, Word
from UI.backend.routes.pipeline import _enrich_scenes_with_transcripts


@pytest.fixture
def project_with_audio_analysis(tmp_path: Path) -> Path:
    """Fixture creating a project with both raw transcript.json and Audio Analyzer output JSON (audio_analysis.json)."""
    pdir = tmp_path / "test_proj_corrected"
    pdir.mkdir(parents=True)

    # 1. Raw Whisper output (with phonetic Telugu loanwords)
    raw_whisper_data = {
        "language": "te",
        "duration": 10.0,
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 5.0,
                "text": "ఫ్యూచర్ లో హ్యూమంస్ రోల్ మారుతుంది.",
                "words": [
                    {"w": "ఫ్యూచర్", "start": 0.0, "end": 1.0, "p": 0.9},
                    {"w": "లో", "start": 1.0, "end": 1.5, "p": 0.95},
                    {"w": "హ్యూమంస్", "start": 1.5, "end": 2.5, "p": 0.9},
                    {"w": "రోల్", "start": 2.5, "end": 3.5, "p": 0.95},
                    {"w": "మారుతుంది.", "start": 3.5, "end": 5.0, "p": 0.98},
                ],
            },
            {
                "id": 1,
                "start": 5.0,
                "end": 10.0,
                "text": "AI ఏజెంట్స్ పని చేస్తాయి.",
                "words": [
                    {"w": "AI", "start": 5.0, "end": 6.0, "p": 0.95},
                    {"w": "ఏజెంట్స్", "start": 6.0, "end": 7.5, "p": 0.92},
                    {"w": "పని", "start": 7.5, "end": 8.5, "p": 0.96},
                    {"w": "చేస్తాయి.", "start": 8.5, "end": 10.0, "p": 0.97},
                ],
            },
        ],
    }
    (pdir / "transcript.json").write_text(json.dumps(raw_whisper_data, ensure_ascii=False), encoding="utf-8")

    # 2. Audio Analyzer stage output JSON (with LLM-corrected words: future, humans, role, AI agents)
    audio_analysis_data = {
        "schema_version": "audio-analysis-2",
        "source": {
            "file": "audio.wav",
            "duration_seconds": 10.0,
        },
        "transcription": {
            "language": {"code": "te"},
            "full_text": "future లో humans role మారుతుంది. AI agents పని చేస్తాయి.",
            "transcript_file": "transcript_corrected.json",
            "raw_file": "transcript.json",
            "corrected_file": "transcript_corrected.json",
        },
        "utterances": [
            {
                "utterance_id": "utt_001",
                "id": 0,
                "text": "future లో humans role మారుతుంది.",
                "start_seconds": 0.0,
                "end_seconds": 5.0,
                "words": [
                    {"index": 0, "text": "future", "start_seconds": 0.0, "end_seconds": 1.0, "edit": "llm"},
                    {"index": 1, "text": "లో", "start_seconds": 1.0, "end_seconds": 1.5, "edit": None},
                    {"index": 2, "text": "humans", "start_seconds": 1.5, "end_seconds": 2.5, "edit": "llm"},
                    {"index": 3, "text": "role", "start_seconds": 2.5, "end_seconds": 3.5, "edit": "llm"},
                    {"index": 4, "text": "మారుతుంది.", "start_seconds": 3.5, "end_seconds": 5.0, "edit": None},
                ],
            },
            {
                "utterance_id": "utt_002",
                "id": 1,
                "text": "AI agents పని చేస్తాయి.",
                "start_seconds": 5.0,
                "end_seconds": 10.0,
                "words": [
                    {"index": 5, "text": "AI", "start_seconds": 5.0, "end_seconds": 6.0, "edit": None},
                    {"index": 6, "text": "agents", "start_seconds": 6.0, "end_seconds": 7.5, "edit": "llm"},
                    {"index": 7, "text": "పని", "start_seconds": 7.5, "end_seconds": 8.5, "edit": None},
                    {"index": 8, "text": "చేస్తాయి.", "start_seconds": 8.5, "end_seconds": 10.0, "edit": None},
                ],
            },
        ],
        "pauses": [],
        "validation": {"status": "ok"},
    }
    (pdir / "audio_analysis.json").write_text(json.dumps(audio_analysis_data, ensure_ascii=False), encoding="utf-8")

    return pdir


def test_load_source_reuses_audio_analyzer_corrected_json(project_with_audio_analysis):
    """Verifies that scene_segmentation.load_source reuses the Audio Analyzer output JSON and extracts LLM-corrected words."""
    pdir = project_with_audio_analysis
    t = scene_segmentation.load_source(pdir)

    assert isinstance(t, Transcript)
    assert t.duration == 10.0
    assert len(t.segments) == 2

    # Segments must use LLM-corrected transcript words (future, humans, role), NOT raw Whisper
    assert t.segments[0].text == "future లో humans role మారుతుంది."
    assert t.segments[0].words[0].w == "future"
    assert t.segments[0].words[2].w == "humans"
    assert t.segments[0].words[3].w == "role"
    assert t.segments[1].words[1].w == "agents"


def test_read_input_preserves_whisper_for_comparison(project_with_audio_analysis):
    """Verifies read_input extracts corrected words as primary while preserving raw Whisper words separately for comparison."""
    pdir = project_with_audio_analysis
    inp = scene_segmentation.read_input(pdir)

    # Primary words are LLM-corrected
    assert inp["words"][0]["text"] == "future"
    assert inp["words"][2]["text"] == "humans"

    # Separate raw Whisper words are preserved
    assert len(inp["whisper_words"]) == 9
    assert inp["whisper_words"][0]["w"] == "ఫ్యూచర్"
    assert inp["whisper_words"][2]["w"] == "హ్యూమంస్"


def test_assemble_assigns_corrected_narration_and_preserves_whisper(project_with_audio_analysis):
    """Verifies assembled scenes use corrected transcript as primary narration and keep whisper_transcript separately."""
    pdir = project_with_audio_analysis
    inp = scene_segmentation.read_input(pdir)
    units = scene_segmentation.build_units(inp)
    cuts = scene_segmentation.allowed_cuts(inp, units)

    # Deterministic grouping of 2 segments into 2 scenes
    groups = [
        {"first": 0, "last": 4, "beat": "Human role change", "objective": "Explain future role", "type": "concept_change", "reason": "topic shifts"},
        {"first": 5, "last": 8, "beat": "AI handles work", "objective": "Highlight AI agents", "type": "conclusion", "reason": "summary"},
    ]
    scenes = scene_segmentation.assemble(inp, units, cuts, groups, "llm_semantic_grouping")

    assert len(scenes) == 2
    s0 = scenes[0]

    # Primary narration is LLM-corrected
    assert s0["transcript"] == "future లో humans role మారుతుంది."
    assert s0["llm_transcript"] == "future లో humans role మారుతుంది."

    # Whisper raw transcript is preserved separately for comparative display
    assert s0["whisper_transcript"] == "ఫ్యూచర్ లో హ్యూమంస్ రోల్ మారుతుంది."
    assert s0["whisper_transcript"] != s0["transcript"]

    s1 = scenes[1]
    assert s1["transcript"] == "AI agents పని చేస్తాయి."
    assert s1["llm_transcript"] == "AI agents పని చేస్తాయి."
    assert s1["whisper_transcript"] == "AI ఏజెంట్స్ పని చేస్తాయి."


def test_enrich_scenes_with_transcripts_guarantees_corrected_primary(project_with_audio_analysis):
    """Verifies that _enrich_scenes_with_transcripts enforces the corrected transcript as primary narration."""
    pdir = project_with_audio_analysis
    raw_scenes_data = {
        "scenes": [
            {
                "scene_id": "scene_001",
                "start_time": 0.0,
                "end_time": 5.0,
                "transcript": "ఫ్యూచర్ లో హ్యూమంస్ రోల్ మారుతుంది.",  # suppose old raw transcript was stored
            }
        ]
    }

    enriched = _enrich_scenes_with_transcripts(pdir, raw_scenes_data)
    sc = enriched["scenes"][0]

    # Authoritative primary transcript MUST be corrected
    assert sc["transcript"] == "future లో humans role మారుతుంది."
    assert sc["llm_transcript"] == "future లో humans role మారుతుంది."

    # Raw Whisper transcript is preserved in whisper_transcript
    assert sc["whisper_transcript"] == "ఫ్యూచర్ లో హ్యూమంస్ రోల్ మారుతుంది."
