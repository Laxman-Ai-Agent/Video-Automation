"""Regression: the real render gave "Does this look like a foreign page?" because Remotion's own server landed on a port another application answers on.
render.render now passes a free --port, and the colour codes of Remotion's messages are removed from the error the user sees. Run: python -m pytest tests/test_render_port.py -q"""
import pytest

from backend import render


class FakeProc:
    def __init__(self, lines, rc):
        self.stdout, self._rc = iter(lines), rc

    def wait(self):
        return self._rc


@pytest.fixture
def fake(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(render, "preflight", lambda *a, **k: None)
    monkeypatch.setattr(render, "stage_audio", lambda *a, **k: None)
    monkeypatch.setattr(render, "write_profile", lambda *a, **k: {})
    monkeypatch.setattr(render, "output_path", lambda *a, **k: tmp_path / "out.mp4")
    return seen


def run(monkeypatch, seen, lines, rc):
    def popen(cmd, **kw):
        seen.append(cmd)
        return FakeProc(lines, rc)
    monkeypatch.setattr(render.subprocess, "Popen", popen)
    return render.render(render.config.PROJECTS_DIR / "p", False)


def test_render_passes_a_free_port_to_remotion(monkeypatch, fake):
    run(monkeypatch, fake, ["Rendered 10/10"], 0)
    run(monkeypatch, fake, ["Rendered 10/10"], 0)
    ports = [next(a for a in cmd if str(a).startswith("--port=")) for cmd in fake]
    assert len(ports) == 2 and all(1024 <= int(p.split("=")[1]) <= 65535 for p in ports)
    assert fake[0][:4] == ["npx", "remotion", "render", "src/index.ts"]                    # the rest of the command is unchanged


def test_error_shown_to_the_user_has_no_colour_codes(monkeypatch, fake):
    lines = ["\x1b[31mDoes this look like a foreign page? If so, try to stop this server.\x1b[39m", "[31mat innerSetPropsAndEnv[39m"]
    with pytest.raises(RuntimeError) as e:
        run(monkeypatch, fake, lines, 1)
    msg = str(e.value)
    assert "foreign page" in msg and "\x1b" not in msg and "[31m" not in msg and "[39m" not in msg
