"""A segment the transcript review emptied has nothing to translate: it is not asked for (an empty answer made the translation fail with 'wrong shape') and not in transcript_en.json."""
import json

from backend import translate_io
from backend.transcribe import Segment, Transcript, Word


def _project(tmp_path):
    w = lambda t, a, b: Word(w=t, start=a, end=b)
    segs = [Segment(id=0, start=0, end=1, text="ఒకటి", words=[w("ఒకటి", 0, 1)]),
            Segment(id=1, start=1, end=2, text="", words=[]),
            Segment(id=2, start=2, end=3, text="రెండు", words=[w("రెండు", 2, 3)])]
    (tmp_path / "transcript.json").write_text(Transcript(language="te", duration=3, segments=segs).model_dump_json(), encoding="utf-8")


def test_an_emptied_segment_is_neither_asked_nor_kept(tmp_path):
    _project(tmp_path)
    asked = translate_io.prepare(tmp_path)
    assert asked.count("\n") == 3 and "\n1 [" not in asked and "\n0 [" in asked and "\n2 [" in asked
    (tmp_path / "translation.json").write_text(json.dumps({"segments": [{"id": 0, "en": "one"}, {"id": 2, "en": "two"}]}), encoding="utf-8")
    en = translate_io.merge(tmp_path)
    assert [(s.id, s.en) for s in en.segments] == [(0, "one"), (2, "two")]
