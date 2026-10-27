"""Phase 1: a scene is cut into shots of 1.5-3.5 s on the spoken words, the generated code gets one Sequence per shot, and the preview samples every shot.
Run: python -m pytest tests/test_scene_shots.py -q"""
from collections import namedtuple

from VIDEO_ENGINE.stages import motion_animation as ma
from VIDEO_ENGINE.stages import motion_validation_preview as pv
from VIDEO_ENGINE.stages import visual_planning_rules as rules

W = namedtuple("W", "w start end")


def words(n: int, step: float = 0.4, start: float = 0.0) -> list[W]:
    """n spoken words of `step` seconds each, back to back: every word end is a possible cut point."""
    return [W(f"w{i}", round(start + i * step, 3), round(start + (i + 1) * step, 3)) for i in range(n)]


def scene(a: float, b: float, ws: list[W], beats: list[dict] | None = None):
    nar = {"start_seconds": a, "end_seconds": min(b, ws[-1].end if ws else b)}
    mapping = {"timeline_start": a, "timeline_end": b}
    iss = rules.Issues()
    return rules.shots(nar, mapping, beats or [], ws, "scene_01", iss), iss


def test_a_long_scene_is_cut_into_shots_of_the_allowed_length_covering_it():
    sh, iss = scene(0.0, 12.0, words(30))                       # 30 words x 0.4 s = 12 s
    assert len(sh) >= 4
    assert all(rules.SHOT_MIN - rules.EPS <= x["duration_seconds"] <= rules.SHOT_MAX + rules.EPS for x in sh), sh
    assert sh[0]["start_seconds"] == 0.0 and sh[-1]["end_seconds"] == 12.0
    assert all(abs(y["start_seconds"] - x["end_seconds"]) < 0.002 for x, y in zip(sh, sh[1:]))
    assert [x["shot_id"] for x in sh] == [f"scene_01_shot_{i}" for i in range(1, len(sh) + 1)]
    assert not iss.items


def test_every_cut_falls_on_the_end_of_a_spoken_word():
    ws = words(30)
    sh, _ = scene(0.0, 12.0, ws)
    ends = {w.end for w in ws}
    assert all(x["end_seconds"] in ends for x in sh[:-1]), [x["end_seconds"] for x in sh]


def test_frames_are_relative_to_the_scenes_own_frame_zero_and_carry_the_word_times():
    ws = words(30, start=5.0)
    nar = {"start_seconds": 5.0, "end_seconds": 17.0}
    sh = rules.shots(nar, {"timeline_start": 5.0, "timeline_end": 17.0}, [], ws, "scene_02", rules.Issues())
    assert sh[0]["start_frame"] == 0
    assert sh[-1]["end_frame"] == 360                                 # 12 s x 30 fps
    assert all(x["start_frame"] < x["end_frame"] for x in sh)
    every = [w for x in sh for w in x["words"]]
    assert len(every) == len(ws) and every[0]["start_frame"] == 0     # the first word starts at the scene's frame 0
    assert all(0 <= w["start_frame"] < w["end_frame"] <= 360 for w in every)


def test_a_beat_the_planner_wrote_is_the_preferred_cut():
    ws = words(30)
    beat = {"beat_id": "b1", "start_seconds": 0.0, "end_seconds": 2.0, "description": "the hook", "element_ids": ["s1_title"]}
    sh, _ = scene(0.0, 12.0, ws, [beat])
    assert sh[0]["end_seconds"] == 2.0
    assert sh[0]["beat_id"] == "b1" and sh[0]["description"] == "the hook" and sh[0]["element_ids"] == ["s1_title"]


def test_a_tail_shorter_than_the_minimum_belongs_to_the_shot_before_it():
    sh, _ = scene(0.0, 4.0, words(10))                              # 4 s: one cut would leave a 0.5 s tail
    assert len(sh) == 1 or all(x["duration_seconds"] >= rules.SHOT_MIN - rules.EPS for x in sh)
    assert sh[-1]["end_seconds"] == 4.0


def test_a_scene_without_spoken_words_stays_one_shot_and_says_why():
    sh, iss = scene(0.0, 8.0, [])
    assert len(sh) == 1 and sh[0]["duration_seconds"] == 8.0
    assert [i["code"] for i in iss.items] == ["shot_uncuttable"]
    assert iss.items[0]["severity"] == "info"                        # the words allow no cut: never a warning that nobody can clear


def test_check_shots_catches_a_gap_a_short_shot_and_no_shots():
    found: list[tuple] = []
    rule = lambda name, sid, bad, *a: found.append((name, bad))
    good = {"scene_id": "scene_01", "source_mapping": {"timeline_start": 0.0, "timeline_end": 6.0},
            "shots": [{"shot_id": "a", "start_seconds": 0.0, "end_seconds": 3.0, "duration_seconds": 3.0},
                      {"shot_id": "b", "start_seconds": 3.0, "end_seconds": 6.0, "duration_seconds": 3.0}]}
    rules.check_shots(good, rule)
    assert not [n for n, bad in found if bad]
    found.clear()
    gap = {**good, "shots": [good["shots"][0], {"shot_id": "b", "start_seconds": 4.0, "end_seconds": 6.0, "duration_seconds": 2.0}]}
    rules.check_shots(gap, rule)
    assert ("shots_contiguous", True) in found
    found.clear()
    short = {**good, "shots": [{"shot_id": "a", "start_seconds": 0.0, "end_seconds": 0.5, "duration_seconds": 0.5},
                               {"shot_id": "b", "start_seconds": 0.5, "end_seconds": 6.0, "duration_seconds": 5.5}]}
    rules.check_shots(short, rule)
    assert ("shots_min_length", True) in found
    found.clear()
    rules.check_shots({**good, "shots": []}, rule)
    assert ("shots_present", True) in found


SHOTS = [{"shot_id": "s1", "start_frame": 0, "end_frame": 60}, {"shot_id": "s2", "start_frame": 60, "end_frame": 150}]


def test_the_code_must_start_a_sequence_for_every_shot():
    flat = '<AbsoluteFill><div data-element-id="s1_title" /></AbsoluteFill>'
    assert len(ma.missing_shot_sequences(flat, SHOTS)) == 2
    cut = '<Sequence from={0} durationInFrames={60}><A /></Sequence><Sequence from={ 60 } durationInFrames={90}><B /></Sequence>'
    assert ma.missing_shot_sequences(cut, SHOTS) == []
    assert ma.missing_shot_sequences(flat, SHOTS[:1]) == []          # a single-shot scene needs no Sequence of its own


def test_the_shots_are_part_of_what_a_scenes_code_is_written_from():
    base = dict(duration=5.0, headline="h", subtext="", texts=["h"], elements=[], palette=["#000"], aspect="16:9")
    assert ma.scene_input_fingerprint(**base, shots=SHOTS) != ma.scene_input_fingerprint(**base, shots=SHOTS[:1])


def test_the_preview_samples_the_middle_of_every_shot():
    comp = {"meta": {"fps": 30}, "scenes": [{"id": 1, "start": 0.0, "end": 5.0}, {"id": 2, "start": 5.0, "end": 8.0}]}
    plan = pv.sample_plan(comp, {"scene_01": SHOTS, "scene_02": [{"shot_id": "x", "start_frame": 0, "end_frame": 90}]})
    one = [p for p in plan if p["scene_id"] == "scene_01"]
    assert [p["kind"] for p in one] == ["shot_1", "shot_2"]
    assert [p["frame"] for p in one] == [30, 105]                    # the middle of each shot, in frames of the composition
    assert [p["kind"] for p in plan if p["scene_id"] == "scene_02"] == [k for k, _ in pv.FRACTIONS]    # one shot: sampled as before


def test_picture_change_measures_how_much_two_stills_differ():
    assert pv.picture_change([0] * 256, [0] * 256) == 0.0
    assert pv.picture_change([0] * 256, [255] * 256) == 255.0
    assert pv.picture_change([0] * 256, None) is None
