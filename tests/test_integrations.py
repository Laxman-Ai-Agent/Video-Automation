"""The Agent System never imports a domain project: it asks SYSTEM.core.integrations for named capabilities, and a missing one is a normal state."""
import sys
import textwrap

import pytest

from SYSTEM.core import integrations


@pytest.fixture(autouse=True)
def clean_registry(monkeypatch):
    """An empty registry for each test; monkeypatch puts the real one back (a domain project registers itself when it is imported)."""
    monkeypatch.delenv(integrations.ENV_MODULES, raising=False)
    for name in ("_providers", "_factories", "_failures"):
        monkeypatch.setattr(integrations, name, {})
    monkeypatch.setattr(integrations, "_configured_loaded", False)


def test_a_missing_capability_is_none_or_the_default():
    assert integrations.get("jobs") is None
    assert integrations.get("jobs", "fallback") == "fallback"
    assert integrations.available() == []


def test_a_registered_provider_is_returned_and_can_be_removed():
    provider = object()
    integrations.register("jobs", provider)
    assert integrations.get("jobs") is provider and integrations.available() == ["jobs"]
    integrations.unregister("jobs")
    assert integrations.get("jobs") is None


def test_a_lazy_provider_is_built_once_and_only_when_first_asked_for():
    calls = []

    def factory():
        calls.append(1)
        return {"stage": ()}
    integrations.register("stage_dependencies", factory=factory)
    assert calls == []                                   # registering costs nothing: no heavy import at start-up
    assert integrations.get("stage_dependencies") == {"stage": ()}
    assert integrations.get("stage_dependencies") == {"stage": ()}
    assert calls == [1]


def test_registering_needs_exactly_one_of_provider_or_factory():
    with pytest.raises(ValueError):
        integrations.register("jobs")
    with pytest.raises(ValueError):
        integrations.register("jobs", object(), factory=object)


def test_modules_named_in_the_environment_register_themselves(tmp_path, monkeypatch):
    (tmp_path / "demo_integration_ok.py").write_text(textwrap.dedent("""
        from SYSTEM.core import integrations
        def register():
            integrations.register("jobs", "demo-jobs")
    """), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv(integrations.ENV_MODULES, "demo_integration_ok")
    assert integrations.get("jobs") == "demo-jobs"       # loaded on first lookup
    assert integrations.failures() == {}
    sys.modules.pop("demo_integration_ok", None)


def test_a_module_that_cannot_load_is_reported_never_raised(monkeypatch):
    monkeypatch.setenv(integrations.ENV_MODULES, "no_such_domain_project, ")
    assert integrations.get("jobs") is None              # the Agent System keeps working without it
    assert list(integrations.failures()) == ["no_such_domain_project"]
    assert "No module named" in integrations.failures()["no_such_domain_project"]
