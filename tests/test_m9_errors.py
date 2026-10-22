"""A step that stops with a message the console cannot print (Remotion colours and box characters) still reports that message, not "unexpected error".
Run: python -m pytest tests/test_m9_errors.py -q"""
import io

import pytest

from backend import pipeline
from backend.diagnose import UserProblem


def test_a_message_the_console_cannot_encode_reaches_the_caller(tmp_path, monkeypatch):
    @pipeline.step("zz-unicode-stop")
    def _stop(pdir, ctx):
        raise UserProblem("A font could not be loaded │ \x1b[90mboxes and colours\x1b[39m")

    monkeypatch.setattr(pipeline.sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict"))
    try:
        with pytest.raises(pipeline.StepError) as e:
            pipeline.execute(tmp_path, "zz-unicode-stop", pipeline.Ctx())
        assert "font could not be loaded" in str(e.value)
    finally:
        pipeline.STEPS.pop("zz-unicode-stop", None)
