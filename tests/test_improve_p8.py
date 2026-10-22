"""Every improvement flag is registered in config.FLAG_NAMES and off by default. Run: python -m pytest tests/test_improve_p8.py -q"""
from backend import config

ALL_FLAGS = ("HIGHLIGHTS", "MATCH_DETAIL", "SHOTS", "VALIDATION", "ICONS", "CANCEL", "FINGERPRINTS", "MOTION")


def test_every_flag_is_registered_and_off_by_default(monkeypatch):
    for f in ALL_FLAGS:
        monkeypatch.delenv(f"A2V_{f}", raising=False)
    assert all(config.improve(f.lower()) is False for f in ALL_FLAGS)
    assert set(config.FLAG_NAMES) == {f.lower() for f in ALL_FLAGS}
