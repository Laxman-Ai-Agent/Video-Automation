import json
import urllib.request
from pathlib import Path
import pytest
from VIDEO_ENGINE.stages.chart_generator import build_chart_config, generate_chart_url, render_and_save_chart

def test_build_chart_config_bar():
    cfg = build_chart_config(
        chart_type="bar",
        labels=["2021", "2022", "2023"],
        data=[10.5, 25.0, 42.8],
        title="Revenue Growth",
        dark_mode=True
    )
    assert cfg["type"] == "bar"
    assert cfg["data"]["labels"] == ["2021", "2022", "2023"]
    assert cfg["data"]["datasets"][0]["data"] == [10.5, 25.0, 42.8]
    assert cfg["options"]["plugins"]["title"]["text"] == "Revenue Growth"
    assert "scales" in cfg["options"]

def test_build_chart_config_doughnut():
    cfg = build_chart_config(
        chart_type="doughnut",
        labels=["A", "B", "C"],
        data=[30, 50, 20],
        title="Share"
    )
    assert cfg["type"] == "doughnut"
    assert len(cfg["data"]["datasets"][0]["backgroundColor"]) == 3
    assert cfg["options"]["plugins"]["legend"]["display"] is True

def test_generate_chart_url():
    cfg = {"type": "pie", "data": {"labels": ["X"], "datasets": [{"data": [100]}]}}
    url = generate_chart_url(cfg, width=1920, height=1080)
    assert "quickchart.io/chart" in url
    assert "w=1920" in url
    assert "h=1080" in url

def test_render_and_save_chart(monkeypatch, tmp_path):
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return b"fake_png_binary_data"

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=15: FakeResponse())
    
    out_file = tmp_path / "charts" / "output.png"
    cfg = build_chart_config("bar", ["Q1", "Q2"], [10, 20])
    res = render_and_save_chart(cfg, out_file)
    
    assert res.exists()
    assert res.read_bytes() == b"fake_png_binary_data"
