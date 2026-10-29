"""One definition of "the scene code draws this planned text" (motion_planning.text_is_drawn), used by Motion Generation's own check and by Motion Validation. Found on 2026-10-29: a scene that drew
"Tech Video Intro" word by word (const words = ["Tech", "Video", "Intro"], the kinetic style the shot rules ask for) was blocked as "text not in the generated code".
Run: python -m pytest tests/test_planned_text_drawn.py -q"""
import inspect

import pytest

from VIDEO_ENGINE.stages import motion_animation, motion_planning as mp, motion_validation_rules


@pytest.mark.parametrize("code", [
    '<h1>Tech Video Intro</h1>',                                         # the phrase as it is
    "<h1>  TECH   video INTRO </h1>",                                    # case and spacing aside
    'const words = ["Tech", "Video", "Intro"];',                         # word by word (kinetic typography)
    "const words = ['Tech', 'Video', 'Intro'];",
    "<b>Tech Video</b><b>Intro</b>",                                     # in two pieces
    'const lines = ["Tech Video", "Intro!"];',
    'const w = ["Tech", "Video", "Intro."]; const other = "x";',         # punctuation at the edge of a literal
])
def test_a_text_drawn_as_a_phrase_or_word_by_word_counts_as_drawn(code):
    assert mp.text_is_drawn(code, "Tech Video Intro")


@pytest.mark.parametrize("code", [
    "const tech = video; // intro",                                      # the words only occur as identifiers and comments
    'const words = ["Tech", "Video"];',                                  # a word is missing
    'const words = ["Intro", "Video", "Tech"];',                         # wrong order
    'const words = ["Tech", "Video", "x", "Intro"];',                    # another literal in between: not the phrase
    "",
])
def test_words_that_are_not_drawn_in_order_as_literals_do_not_count(code):
    assert not mp.text_is_drawn(code, "Tech Video Intro")


def test_a_single_word_needs_to_be_there_as_written_and_an_empty_text_is_never_drawn():
    assert mp.text_is_drawn("<b>Intro</b>", "Intro") and not mp.text_is_drawn("<b>Outro</b>", "Intro")
    assert not mp.text_is_drawn("<b>x</b>", "")


def test_telugu_words_drawn_one_by_one_count_too():
    assert mp.text_is_drawn('const w = ["నమస్కారం", "మిత్రులారా"];', "నమస్కారం మిత్రులారా")


def test_both_checks_use_the_shared_definition():
    assert "text_is_drawn" in inspect.getsource(motion_validation_rules) and "text_is_drawn" in inspect.getsource(motion_animation)


def test_a_short_text_must_stand_alone_not_sit_inside_a_name():                      # the rule Motion Validation's semantic check had on its own, now part of the one definition
    assert mp.text_is_drawn("const m9Zx = 1;\n<div>\n  5G\n</div>", "5G")
    assert not mp.text_is_drawn("const m9Zx = 1;", "9Z") and not mp.text_is_drawn("nothing", "7Q")


def test_the_semantic_check_no_longer_has_a_private_copy():
    from SYSTEM.agents.video_generation_agents.motion_timeline_validation import validation_intelligence as vi
    assert not hasattr(vi, "_text_is_drawn") and "motion_planning.text_is_drawn" in inspect.getsource(vi)
