"""Test Suite D: Atomic Promotion, Version Archiving, Registry Sync, and Rollback."""
import shutil
from pathlib import Path
import pytest

from SYSTEM.agents.capability_finder.learning.authorization import AuthenticatedOperator
from SYSTEM.agents.skill_factory.lifecycle import SkillLifecycle
from SYSTEM.agents.skill_factory.publisher import skill_publisher
from SYSTEM.agents.skill_factory.specification import SkillSpecification
from SYSTEM.registries.capability_registry import get_capability_registry
from SYSTEM.registries.skill_registry import SKILLS_DIR, get_skill_registry


@pytest.fixture
def mock_operator():
    return AuthenticatedOperator(
        operator_id="test_admin",
        role="operator",
        auth_method="trusted_context",
        verified_at="2026-10-17T00:00:00Z",
    )


def test_atomic_promotion_and_registry_sync(mock_operator):
    skill_reg = get_skill_registry()
    cap_reg = get_capability_registry()

    skill_id = "motion.test_publisher_flow"
    spec_v1 = SkillSpecification(
        skill_id=skill_id,
        name="Test Publisher Flow Skill",
        purpose="Testing promotion pipeline.",
        domain="motion",
        version="1.0.0",
        capabilities=["publisher-test-flow"],
        tags=["motion", "test"],
    )
    content_v1 = spec_v1.to_yaml_manifest()
    lifecycle_v1 = SkillLifecycle(skill_id=skill_id, version="1.0.0", current_state="APPROVED")

    try:
        # 1. Promote v1.0.0
        res_v1 = skill_publisher.promote_skill(
            spec=spec_v1,
            content=content_v1,
            lifecycle=lifecycle_v1,
            operator=mock_operator,
        )
        assert res_v1.status == "ACTIVE"
        assert res_v1.version == "1.0.0"

        # 2. Verify on-disk file existence
        dest_file = SKILLS_DIR / res_v1.entrypoint
        assert dest_file.exists()
        assert dest_file.read_text(encoding="utf-8") == content_v1

        # 3. Verify discoverability in SkillRegistry
        rec, loaded_content = skill_reg.get_skill(skill_id, load_content=True)
        assert rec.status == "approved"
        assert rec.version == "1.0.0"
        assert loaded_content == content_v1

        # 4. Verify discoverability in CapabilityRegistry
        matching_caps = cap_reg.search_capabilities(query="publisher-test-flow")
        assert len(matching_caps) > 0
        assert any(c.source_id == skill_id for c in matching_caps)

        # 5. Promote adapted v1.1.0 with archive preservation
        spec_v2 = SkillSpecification(
            skill_id=skill_id,
            name="Test Publisher Flow Skill",
            purpose="Testing promotion pipeline v1.1.0.",
            domain="motion",
            version="1.1.0",
            capabilities=["publisher-test-flow", "extended-physics"],
            tags=["motion", "test"],
        )
        content_v2 = spec_v2.to_yaml_manifest()
        lifecycle_v2 = SkillLifecycle(skill_id=skill_id, version="1.1.0", current_state="APPROVED")

        res_v2 = skill_publisher.promote_skill(
            spec=spec_v2,
            content=content_v2,
            lifecycle=lifecycle_v2,
            operator=mock_operator,
        )
        assert res_v2.status == "ACTIVE"
        assert res_v2.version == "1.1.0"
        assert res_v2.archive_path != ""  # Prior version archived

        # Check archive file exists
        assert Path(res_v2.archive_path).exists()

        # 6. Rollback back to v1.0.0
        rb_res = skill_publisher.rollback_skill(
            skill_id=skill_id,
            reason="Testing rollback restoration to prior version.",
            operator=mock_operator,
            target_version="1.0.0",
        )
        assert rb_res.status == "ROLLED_BACK"
        assert rb_res.rolled_back_version == "1.1.0"
        assert rb_res.restored_version == "1.0.0"

        # Verify SkillRegistry has restored v1.0.0
        restored_rec, restored_content = skill_reg.get_skill(skill_id, load_content=True)
        assert restored_rec.version == "1.0.0"
        assert restored_content == content_v1

    finally:
        # Cleanup test artifacts
        if skill_id in skill_reg._skills:
            del skill_reg._skills[skill_id]
            skill_reg._save()
        s_dir = SKILLS_DIR / "motion" / "test_publisher_flow"
        if s_dir.exists():
            shutil.rmtree(s_dir, ignore_errors=True)
        arch_dir = SKILLS_DIR / "archive" / skill_id
        if arch_dir.exists():
            shutil.rmtree(arch_dir, ignore_errors=True)
        cap_reg.sync_with_registries()


def test_rollback_initial_version_deprecates(mock_operator):
    skill_reg = get_skill_registry()
    cap_reg = get_capability_registry()

    skill_id = "audio.test_initial_rollback"
    spec = SkillSpecification(
        skill_id=skill_id,
        name="Test Initial Rollback",
        purpose="Testing deprecation on single-version rollback.",
        domain="audio",
        version="1.0.0",
        capabilities=["single-ver-rollback"],
    )
    lifecycle = SkillLifecycle(skill_id=skill_id, version="1.0.0", current_state="APPROVED")

    try:
        skill_publisher.promote_skill(
            spec=spec,
            content=spec.to_yaml_manifest(),
            lifecycle=lifecycle,
            operator=mock_operator,
        )

        # Rollback when no prior version was archived
        rb_res = skill_publisher.rollback_skill(
            skill_id=skill_id,
            reason="Rolling back sole active version.",
            operator=mock_operator,
        )
        assert rb_res.status == "ROLLED_BACK"
        assert rb_res.restored_version is None

        # Status in SkillRegistry should now be deprecated
        rec = skill_reg._skills.get(skill_id)
        assert rec is not None
        assert rec.status == "deprecated"

    finally:
        # Cleanup
        if skill_id in skill_reg._skills:
            del skill_reg._skills[skill_id]
            skill_reg._save()
        s_dir = SKILLS_DIR / "audio" / "test_initial_rollback"
        if s_dir.exists():
            shutil.rmtree(s_dir, ignore_errors=True)
        arch_dir = SKILLS_DIR / "archive" / skill_id
        if arch_dir.exists():
            shutil.rmtree(arch_dir, ignore_errors=True)
        cap_reg.sync_with_registries()
