import urllib.request
import json
from pathlib import Path
from VIDEO_ENGINE.stages.map_generator import geocode_place, deg_to_tile, build_location_svg_card, render_location_map

def test_deg_to_tile():
    # Hyderabad coordinates: 17.3850 N, 78.4867 E at zoom 10
    x, y = deg_to_tile(17.3850, 78.4867, 10)
    assert x > 0
    assert y > 0

def test_build_location_svg_card():
    svg = build_location_svg_card("Hyderabad", 17.3850, 78.4867, "Hyderabad, Telangana, India", 1920, 1080)
    assert "<svg" in svg
    assert "Hyderabad" in svg
    assert "17.3850° N" in svg
    assert "78.4867° E" in svg

def test_render_location_map(monkeypatch, tmp_path):
    class FakeGeoResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return json.dumps([{
                "display_name": "Amaravati, Andhra Pradesh, India",
                "lat": "16.5131",
                "lon": "80.5160",
                "boundingbox": ["16.4", "16.6", "80.4", "80.6"]
            }]).encode("utf-8")

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=10: FakeGeoResponse())

    out_file = tmp_path / "maps" / "amaravati.svg"
    res = render_location_map("Amaravati", out_file)
    assert res.exists()
    content = res.read_text(encoding="utf-8")
    assert "Amaravati" in content
    assert "16.5131° N" in content
