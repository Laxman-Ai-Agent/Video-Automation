"""Resource Library core (backend/resource_library.py): SVG sanitiser and composition checks. Pure, no network, no render."""
import pytest

from backend import resource_library as rl

OK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0L10 10" stroke="#000"/></svg>'


def test_svg_accepts_plain_icon():
    r = rl.parse_svg(OK)
    assert r["viewBox"] == "0 0 24 24" and r["children"][0]["tag"] == "path"


@pytest.mark.parametrize("bad", [
    OK.replace("<path", "<script/><path"),
    OK.replace("<path", "<path onclick='x()'"),
    OK.replace('stroke="#000"', 'stroke="url(http://evil/x)"'),
    "<!DOCTYPE svg [<!ENTITY a 'b'>]>" + OK,
    OK.replace(' viewBox="0 0 24 24"', ""),
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>',
    OK + "x" * 21000,
])
def test_svg_rejects_unsafe(bad):
    with pytest.raises(rl.ResourceError) as e:
        rl.parse_svg(bad)
    assert e.value.code == "svg_unsafe"


def test_composition_without_resources_has_no_findings():
    assert rl.check_composition({"scenes": [{"layers": [{"type": "background"}]}]}) == []


def test_unknown_resource_is_reported():
    comp = {"scenes": [{"id": 1, "layers": [{"type": "icon", "resource_id": "icon.nope", "resource_sha256": "0"}]}]}
    assert [f["code"] for f in rl.check_composition(comp)] == ["resource_unknown"]


def _font_comp(sha):
    layer = {"type": "motion_text", "fontId": "font.hind-guntur", "text": "x"}
    if sha:
        layer["fontSha"] = sha                       # the field the renderer and the gallery write (regression: Python once read `fontSha256`)
    return {"scenes": [{"id": 1, "layers": [layer]}]}


def test_font_hash_field_matches_the_renderer():
    sha = rl.get("font.hind-guntur").integrity.sha256
    assert rl.check_composition(_font_comp(sha)) == []
    assert [f["code"] for f in rl.check_composition(_font_comp(None))] == ["resource_hash_missing"]
    assert [f["code"] for f in rl.check_composition(_font_comp("0" * 64))] == ["resource_hash_mismatch"]


def test_fingerprint_follows_only_used_resources(monkeypatch):
    sha = rl.get("font.hind-guntur").integrity.sha256
    used, unrelated = _font_comp(sha), {"scenes": [{"id": 1, "layers": [{"type": "background"}]}]}
    a, b = rl.fingerprint(used), rl.fingerprint(unrelated)
    monkeypatch.setattr(rl, "effective_status", lambda e: "stale" if e.resource_id == "font.hind-guntur" else "verified")
    assert rl.fingerprint(used) != a                  # a used resource turned stale: the timeline fingerprint changes
    assert rl.fingerprint(unrelated) == b             # a composition that does not use it is untouched
    assert [f["code"] for f in rl.check_composition(used)] == ["resource_stale"]


def test_a_blank_chart_fails_and_a_drawn_one_passes_at_the_unchanged_threshold():
    import numpy as np

    from backend import resource_verify as rv
    assert rv.THRESH["chart"] == 0.01                                   # the project threshold, never lowered to make a resource pass
    e = rl.get("chart.svg.line")
    item = {"cells": {e.resource_id: [0, 0, 1920, 1080]}}
    base = np.full((540, 960), 90, dtype=np.int16)
    assert rv.evaluate(e, item, base.copy(), base)["ok"] is False        # nothing drawn
    drawn = base.copy()
    drawn[100:140, 100:900] = 255                                        # 5.9% of the frame changed
    assert rv.evaluate(e, item, drawn, base)["ok"] is True
    faint = base.copy()
    faint[100:104, 100:900] = 255                                        # a hairline (0.6%) is still not enough
    assert rv.evaluate(e, item, faint, base)["ok"] is False
