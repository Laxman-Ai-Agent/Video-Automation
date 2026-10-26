"""Media kinds: the ONE place that says what a visual element of a scene can be. Visual Planning, Motion Planning, Asset Collection, the checks and the UI read it; nothing else lists element types.

Three families, fixed for good: motion (drawn by code: text, icons, graphics ...), image (a real or AI-made picture) and video (a real clip).
A new kind of element is one more row in KINDS (plus its handler, which tests/test_media_kinds.py insists on); no other file needs a new tuple of type names.

Every video is 100% motion graphics: real pictures and clips (and AI-made pictures when wanted) are drawn INSIDE the animated scenes, in any number the narration calls for; there is no share
to reach. Per project the user sets, at upload and never afterwards, only whether AI-made pictures are wanted: project.json key `media` = {"ai_images": false}."""
from __future__ import annotations

from dataclasses import dataclass

FAMILIES = ("motion", "image", "video")
GROUPS = ("text", "icon", "graphic", "background", "image", "video", "page")      # what the UI counts for every scene
DEFAULT_MEDIA = {"ai_images": False}


@dataclass(frozen=True)
class Kind:
    name: str
    family: str
    group: str
    text: bool            # words drawn on the screen
    about: str            # one line of the planner's instructions


KINDS: dict[str, Kind] = {k.name: k for k in (
    Kind("text", "motion", "text", True, "a headline or a keyword drawn with kinetic typography"),
    Kind("label", "motion", "text", True, "a short caption or a number attached to another element"),
    Kind("icon", "motion", "icon", False, "a simple pictogram (lucide icon)"),
    Kind("graphic", "motion", "graphic", False, "a drawn shape or object: a flat illustration built from shapes, lines and gradients"),
    Kind("diagram", "motion", "graphic", False, "nodes, links, a path or a flow that explains how things connect"),
    Kind("chart", "motion", "graphic", False, "a bar, line or pie chart of numbers that the narration states"),
    Kind("data_visualization", "motion", "graphic", False, "a drawn visualisation of a quantity or a trend"),
    Kind("background", "motion", "background", False, "the atmosphere behind the scene: gradient, particles, texture"),
    Kind("image", "image", "image", False, "a REAL photograph of something a camera can show (or an AI-made picture when the project allows it)"),
    Kind("video", "video", "video", False, "a REAL video clip where the movement itself is the point"),
    Kind("reference", "image", "page", False, "a screenshot of ONE infobox or table of a Wikipedia article: the facts and figures (dates, sizes, statistics) that the narration states about a person, place, event, organisation or object"),
)}
TYPES = tuple(KINDS)
TEXT_TYPES = tuple(k.name for k in KINDS.values() if k.text)
REAL_TYPES = tuple(k.name for k in KINDS.values() if k.family != "motion")


def family_of(type_: str) -> str:
    return KINDS[type_].family


def group_of(type_: str) -> str:
    return KINDS[type_].group


def is_text(type_: str) -> bool:
    return type_ in TEXT_TYPES


def is_real(type_: str) -> bool:
    return type_ in REAL_TYPES


def normalise(raw: dict | None) -> dict:
    """The media settings of a project from what the user sent (None = the defaults). Raises ValueError with the reason when they cannot be used.
    The shares of motion / image / video that an earlier version stored are ignored: media is unlimited."""
    raw = {**DEFAULT_MEDIA, **(raw or {})}
    if not isinstance(raw["ai_images"], bool):
        raise ValueError("ai_images must be true or false")
    return {"ai_images": raw["ai_images"]}


def options(info: dict) -> dict:
    """The media settings stored in a project's info (a project without any gets the defaults)."""
    try:
        return normalise(info.get("media"))
    except ValueError:
        return dict(DEFAULT_MEDIA)
