"""One redactor (SYSTEM.core.resilience.redact_secrets): every secret kind is removed by every public entry point."""
from __future__ import annotations

from pathlib import Path

import pytest

from SYSTEM.agents.shared.communication import redact_object
from SYSTEM.agents.shared.telugu_activity_mapper import TeluguActivityMapper
from SYSTEM.agents.skill_factory.security_validator import SecurityValidator
from SYSTEM.core.resilience import CREDENTIAL_KINDS, SECRET_RULES, redact_secrets, sanitize_secrets
from SYSTEM.registries.skill_registry import audit_skill_content
from VIDEO_ENGINE.pipeline.orchestrator import sanitize_message
from VIDEO_ENGINE.stages.motion_animation import audit_scene_tsx_security

# kind -> (text containing the secret, the secret value, the marker it becomes)
SECRETS = {
    "private_key": ("key:\n-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----", "MIIEow", "[REDACTED_PRIVATE_KEY]"),
    "json_secret": ('{"password": "hunter2hunter2"}', "hunter2hunter2", '"[REDACTED_SECRET]"'),
    "aws_key": ("key AKIAIOSFODNN7EXAMPLE used", "AKIAIOSFODNN7EXAMPLE", "[REDACTED_AWS_KEY]"),
    "google_key": ("key=AIzaSyA12345678901234567890123456789012", "AIzaSyA1234567890", "[REDACTED_GOOGLE_KEY]"),
    "github_token": ("pushed with ghp_abcdefghijklmnopqrstuvwxyz123456", "ghp_abcdefghij", "[REDACTED_GITHUB_TOKEN]"),
    "api_key": ("failed with sk-ant-api03-abcdef1234567890abcdef", "sk-ant-api03", "[REDACTED_API_KEY]"),
    "bearer_token": ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload", "eyJhbGciOi", "Bearer [REDACTED_TOKEN]"),
    "key_value_secret": ("connect?password=SuperSecret123!&x=1", "SuperSecret123", "password=[REDACTED_SECRET]"),
}

ENTRY_POINTS = {
    "sanitize_secrets": sanitize_secrets,
    "redact_secrets": lambda t: redact_secrets(t)[0],
    "orchestrator.sanitize_message": sanitize_message,
    "TeluguActivityMapper.sanitize_text": TeluguActivityMapper().sanitize_text,
    "communication.redact_object": lambda t: redact_object({"note": [t]})[0]["note"][0],
}


def test_every_rule_kind_has_a_case():
    assert {kind for kind, _, _ in SECRET_RULES} == set(SECRETS)


@pytest.mark.parametrize("entry", ENTRY_POINTS)
@pytest.mark.parametrize("kind", SECRETS)
def test_every_kind_is_removed_by_every_entry_point(entry, kind):
    text, secret, marker = SECRETS[kind]
    out = ENTRY_POINTS[entry](text)
    assert secret not in out
    assert marker in out


DETECTORS = {
    "motion_animation.audit_scene_tsx_security": lambda t: audit_scene_tsx_security(t)["findings"],
    "skill_registry.audit_skill_content": lambda t: audit_skill_content(t)["findings"],
    "SecurityValidator.audit": lambda t: SecurityValidator().audit(t).findings,
}


@pytest.mark.parametrize("detector", DETECTORS)
@pytest.mark.parametrize("kind", sorted(CREDENTIAL_KINDS))
def test_every_credential_kind_is_flagged_by_every_detector(detector, kind):
    assert any("secret" in f.lower() for f in DETECTORS[detector](SECRETS[kind][0]))


def test_a_variable_named_pin_or_token_in_code_is_not_a_secret():
    code = "const pin = spring({frame, fps}); const token = 'title';"
    assert not any("secret" in f.lower() for f in audit_scene_tsx_security(code)["findings"])


def test_kinds_are_reported_once_in_rule_order():
    text = " ".join(t for t, _, _ in SECRETS.values()) + " second sk-zzzzzzzzzzzzzzzzzzzzzzzz"
    _, kinds = redact_secrets(text)
    assert kinds == list(SECRETS)


def test_a_marker_is_not_redacted_again():
    assert sanitize_secrets("api_key=sk-abcdefghijklmnopqrstuvwx") == "api_key=[REDACTED_API_KEY]"


def test_plain_text_is_untouched():
    text = "Unexpected token: } in scene_3.tsx; spinner=on"
    assert redact_secrets(text) == (text, [])


def test_no_other_module_keeps_its_own_secret_patterns():
    root = Path(__file__).resolve().parents[1]
    owners = [
        p.relative_to(root).as_posix()
        for d in ("SYSTEM", "VIDEO_ENGINE", "UI/backend")
        for p in (root / d).rglob("*.py")
        if "tests" not in p.parts and r"sk-[" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert owners == ["SYSTEM/core/resilience.py"]
