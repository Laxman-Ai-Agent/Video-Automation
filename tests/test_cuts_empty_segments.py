"""A segment without words (noise, a pause) makes no cut of its own: its end used to be snapped into the NEXT segment as a "segment_end" cut in the middle of speech
(real project: a cut at 5.35 s labelled segment_end although no segment ends there). Run: python -m pytest tests/test_cuts_empty_segments.py -q"""
from types import SimpleNamespace

from VIDEO_ENGINE.stages import cuts


def _w(w, start, end):
    return SimpleNamespace(w=w, start=start, end=end)


def test_an_empty_segment_does_not_make_a_cut_inside_the_next_segment(tmp_path, monkeypatch):
    seg = lambda i, a, b, words: SimpleNamespace(id=i, start=a, end=b, words=words)
    t = SimpleNamespace(duration=30.0, segments=[
        seg(0, 0.0, 4.12, [_w("hello", 0.5, 1.0), _w("there", 3.6, 4.12)]),
        seg(1, 4.12, 5.02, []),                                                   # noise: no words
        seg(2, 5.05, 12.0, [_w("and", 5.1, 5.35), _w("more", 6.0, 11.9)]),
        seg(3, 12.5, 20.0, [_w("end", 12.6, 19.9)])])
    monkeypatch.setattr(cuts, "load_transcript", lambda pdir: t)
    monkeypatch.setattr(cuts, "find_audio", lambda pdir: None)
    monkeypatch.setattr(cuts, "silences", lambda audio: [])
    got = cuts.make_cuts(tmp_path)
    assert [c["t"] for c in got] == [4.12, 11.9]                                      # the ends of segments 0 and 2, both reasons segment_end; nothing at 5.35 (the end of the word "and")
    assert all(c["reason"] == "segment_end" for c in got)
