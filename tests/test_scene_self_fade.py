"""A generated scene must not fade its whole picture in or out: the timeline's transition overlaps the two scenes at every cut, so a self-fading
scene leaves empty frames there (seen at 5 s, 22 s and 32 s of the test project's render)."""
from VIDEO_ENGINE.stages import motion_animation as ma

ROOT_FADE = """export const Scene1 = () => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [0, 10], [0, 1]);
  const exit = interpolate(frame, [140, 152], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ padding: "8%", opacity: enter * exit }}>
      <div>Title</div>
    </AbsoluteFill>
  );
};"""

EXIT_BY_DURATION = """export const Scene2 = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const out = interpolate(frame, [durationInFrames - 10, durationInFrames], [1, 0]);
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <div style={{ opacity: out }}>Title</div>
    </AbsoluteFill>
  );
};"""

CLEAN = """export const Scene3 = () => {
  const frame = useCurrentFrame();
  const card = interpolate(frame, [12, 24], [0, 1]);
  const dim = interpolate(frame, [40, 60], [1, 0]);
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <div style={{ opacity: card }}>Card</div>
      <div style={{ opacity: dim }}>Hint that leaves mid-scene</div>
    </AbsoluteFill>
  );
};"""


def test_root_opacity_and_exit_at_the_last_literal_frame_are_flagged():
    issues = ma.scene_self_fades(ROOT_FADE, 152)
    assert len(issues) == 2 and "root AbsoluteFill" in issues[0] and "last frames" in issues[1]


def test_an_exit_tied_to_the_duration_is_flagged():
    assert len(ma.scene_self_fades(EXIT_BY_DURATION, 200)) == 1


def test_elements_that_animate_inside_the_scene_are_fine():
    assert ma.scene_self_fades(CLEAN, 150) == []


def test_the_deterministic_template_does_not_fade_the_scene():
    code = ma.generate_scene_tsx("1", 5.0, "Head", "Sub", [], ["#000", "#fff", "#888"])
    assert ma.scene_self_fades(code, 150) == []


def test_the_generation_version_decides_whether_a_scene_is_written_again():
    """The rule lives in the code generator's instructions, so the version is what makes an existing project write its scenes again: it is part of every scene's input fingerprint.
    (The number itself is not pinned here: a later rule change bumps it, and that is exactly what must keep working.)"""
    args = dict(duration=5.0, headline="Head", subtext="", texts=["Head"], elements=[], palette=["#000"], aspect="16:9")
    before = ma.scene_input_fingerprint(**args)
    assert int(ma.CODEGEN_VERSION) >= 2                                  # 2 is the version that brought the rule: never below it again
    v = ma.CODEGEN_VERSION
    try:
        ma.CODEGEN_VERSION = str(int(v) + 1)
        assert ma.scene_input_fingerprint(**args) != before
    finally:
        ma.CODEGEN_VERSION = v
