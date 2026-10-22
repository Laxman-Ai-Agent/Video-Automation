"""Test Suite C: Operator Authentication, Anti-Spoofing, and Approval Gating."""
import pytest
from SYSTEM.agents.capability_finder.learning.authorization import (
    AuthenticatedOperator,
    SecurityAuthError,
    authenticate_operator,
)
from SYSTEM.agents.skill_factory.lifecycle import SkillLifecycle
from SYSTEM.agents.skill_factory.publisher import PromotionError, skill_publisher
from SYSTEM.agents.skill_factory.specification import SkillSpecification


def test_unauthenticated_promotion_rejected():
    spec = SkillSpecification(
        skill_id="motion.unauth_test",
        name="Unauth Test",
        purpose="Testing unauthenticated promotion.",
        domain="motion",
        capabilities=["test-cap"],
    )
    lifecycle = SkillLifecycle(skill_id=spec.skill_id, version=spec.version, current_state="APPROVED")

    # Attempt promote with NO operator or approval
    with pytest.raises(SecurityAuthError) as exc_info:
        skill_publisher.promote_skill(
            spec=spec,
            content="---\nname: test\n---\n# Test",
            lifecycle=lifecycle,
            operator_id=None,
        )
    err = str(exc_info.value).lower()
    assert "credentials" in err


def test_role_spoofing_rejected():
    spec = SkillSpecification(
        skill_id="motion.spoof_test",
        name="Spoof Test",
        purpose="Testing role spoofing prevention.",
        domain="motion",
        capabilities=["test-cap"],
    )
    lifecycle = SkillLifecycle(skill_id=spec.skill_id, version=spec.version, current_state="APPROVED")

    # Attempt to spoof role as 'system_admin' without an approval
    with pytest.raises(SecurityAuthError):
        skill_publisher.promote_skill(
            spec=spec,
            content="---\nname: test\n---\n# Test",
            lifecycle=lifecycle,
            operator_id="attacker",
            role="system_admin",
        )


def test_unapproved_lifecycle_state_rejected():
    spec = SkillSpecification(
        skill_id="motion.draft_test",
        name="Draft Test",
        purpose="Testing draft cannot be promoted.",
        domain="motion",
        capabilities=["test-cap"],
    )
    # Lifecycle in DRAFT (not APPROVED)
    lifecycle = SkillLifecycle(skill_id=spec.skill_id, version=spec.version, current_state="DRAFT")

    with pytest.raises(PromotionError) as exc_info:
        skill_publisher.promote_skill(
            spec=spec,
            content="---\nname: test\n---\n# Test",
            lifecycle=lifecycle,
            operator_id="test_op",
            role="operator",
        )
    assert "cannot be promoted from state 'DRAFT'" in str(exc_info.value)
