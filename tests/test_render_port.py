"""Regression: the real render gave "Does this look like a foreign page?" because Remotion's own server landed on a port another application answers on.
render.render now passes a free --port to every chunk render, and the colour codes of Remotion's messages are removed from the error the user sees. Run: python -m pytest tests/test_render_port.py -q"""
import json

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
    comp = tmp_path / "composition.json"
    comp.write_text(json.dumps({"meta": {"fps": 30, "duration": 1, "audio": "a.wav"}, "scenes": [{"id": 1, "start": 0, "end": 1, "layers": []}]}), encoding="utf-8")
    (tmp_path / "cache").mkdir()
    chunk = {"scene": 1, "from": 0, "to": 30, "key": "k", "path": tmp_path / "cache" / "k.mp4"}
    monkeypatch.setattr(render, "preflight", lambda *a, **k: None)
    monkeypatch.setattr(render, "stage_audio", lambda *a, **k: None)
    monkeypatch.setattr(render, "stage_motion", lambda *a, **k: None)
    monkeypatch.setattr(render, "write_profile", lambda *a, **k: {})
    monkeypatch.setattr(render, "output_path", lambda *a, **k: tmp_path / "out.mp4")
    monkeypatch.setattr(render, "comp_path", lambda *a, **k: comp)
    monkeypatch.setattr(render.render_cache, "plan", lambda *a, **k: [chunk])
    monkeypatch.setattr(render.render_cache, "assemble", lambda *a, **k: None)
    monkeypatch.setattr(render.render_cache, "prune", lambda *a, **k: None)
    seen.append(chunk)
    return seen


def run(monkeypatch, seen, tmp_path, lines, rc):
    chunk, cmds = seen[0], seen                                                             # seen[0] is the chunk, the commands follow it

    def popen(cmd, **kw):
        cmds.append(cmd)
        if cmd[2] == "render":
            chunk["path"].with_suffix(".part.mp4").write_bytes(b"chunk")
            return FakeProc(lines, rc)
        return FakeProc([], 0)                                                             # the bundle step
    monkeypatch.setattr(render.subprocess, "Popen", popen)
    chunk["path"].unlink(missing_ok=True)                                                  # a cached chunk is not rendered again: every run starts without one
    return render.render(tmp_path / "p", False)


def test_render_passes_a_free_port_to_remotion(monkeypatch, fake, tmp_path):
    run(monkeypatch, fake, tmp_path, ["Rendered 10/10"], 0)
    run(monkeypatch, fake, tmp_path, ["Rendered 10/10"], 0)
    cmds = fake[1:]
    bundles = [c for c in cmds if c[2] == "bundle"]
    renders = [c for c in cmds if c[2] == "render"]
    ports = [next(a for a in cmd if str(a).startswith("--port=")) for cmd in renders]
    assert len(ports) == 2 and all(1024 <= int(p.split("=")[1]) <= 65535 for p in ports)
    assert bundles[0][:4] == ["npx", "remotion", "bundle", "src/index.ts"]                    # the project is bundled once, the chunks are rendered from that bundle
    assert renders[0][:3] == ["npx", "remotion", "render"] and renders[0][3].endswith("_bundle")
    assert "--frames=0-29" in renders[0] and "--muted" in renders[0]


def test_error_shown_to_the_user_has_no_colour_codes(monkeypatch, fake, tmp_path):
    lines = ["\x1b[31mDoes this look like a foreign page? If so, try to stop this server.\x1b[39m", "[31mat innerSetPropsAndEnv[39m"]
    with pytest.raises(RuntimeError) as e:
        run(monkeypatch, fake, tmp_path, lines, 1)
    msg = str(e.value)
    assert "foreign page" in msg and "\x1b" not in msg and "[31m" not in msg and "[39m" not in msg
