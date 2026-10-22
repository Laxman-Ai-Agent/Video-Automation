"""Unit tests for central CapabilityRegistry."""
from __future__ import annotations

import pytest
from SYSTEM.registries.capability_registry import (
    CapabilityRecord,
    CapabilityRegistry,
    get_capability_registry,
)


def test_capability_registry_crud():
    reg = CapabilityRegistry()
    rec = CapabilityRecord(
        capability_id="test.motion_easing",
        name="Motion Easing Curves",
        description="Calculates spring and cubic-bezier easing curves.",
        source_type="skill",
        source_id="motion.easing",
        domain="motion",
        tags=["easing", "spring", "motion"],
        keywords=["spring", "curves", "animation"],
        dependencies=["remotion"],
        verification_status="verified",
    )
    reg.register(rec)

    # Retrieval
    found = reg.get_capability("test.motion_easing")
    assert found is not None
    assert found.name == "Motion Easing Curves"
    assert found.source_type == "skill"
    assert found.verification_status == "verified"

    # Duplicate registration prevention
    with pytest.raises(ValueError, match="already registered"):
        reg.register(rec)

    # Idempotent upsert
    rec.description = "Updated description"
    reg.upsert_capability(rec)
    updated = reg.get_capability("test.motion_easing")
    assert updated is not None
    assert updated.description == "Updated description"


def test_capability_registry_search_and_filtering():
    reg = CapabilityRegistry()
    rec1 = CapabilityRecord(
        capability_id="audio.transcribe",
        name="Audio Transcription",
        description="Transcribes audio to text.",
        source_type="agent",
        source_id="audio_input",
        domain="audio",
        tags=["speech", "whisper"],
        keywords=["transcribe", "subtitles"],
    )
    rec2 = CapabilityRecord(
        capability_id="motion.typography",
        name="Kinetic Typography",
        description="Renders animated text.",
        source_type="skill",
        source_id="motion.kinetic_typography",
        domain="motion",
        tags=["animation", "typography"],
        keywords=["text", "motion"],
    )
    reg.register(rec1)
    reg.register(rec2)

    # Filter by domain
    audio_results = reg.search_capabilities(domain="audio")
    assert len(audio_results) == 1
    assert audio_results[0].capability_id == "audio.transcribe"

    # Search by keyword
    motion_results = reg.search_capabilities(query="typography")
    assert len(motion_results) == 1
    assert motion_results[0].capability_id == "motion.typography"

    # Search by tag
    tag_results = reg.search_capabilities(tags=["speech"])
    assert len(tag_results) == 1
    assert tag_results[0].capability_id == "audio.transcribe"


def test_capability_registry_sync_with_registries():
    reg = CapabilityRegistry()
    sync_report = reg.sync_with_registries()

    assert sync_report["agents_synced"] > 0
    assert sync_report["skills_synced"] > 0
    assert sync_report["tools_synced"] > 0
    assert sync_report["total_records"] > 0

    # Verify known agent capability indexed
    motion_caps = reg.search_capabilities(query="motion_planning")
    assert len(motion_caps) > 0

    # Verify known tool indexed
    ffmpeg_caps = reg.search_capabilities(query="ffmpeg")
    assert len(ffmpeg_caps) > 0
