"""Pydantic request/response models of the API (JSON contracts for the UI)."""
from typing import Literal

from pydantic import BaseModel


class AudioRef(BaseModel):
    """The uploaded audio of a project, as the server stored it."""
    file: str                           # the file inside the project folder, e.g. audio.mp3
    original_name: str
    size_bytes: int
    format: str                         # MP3, WAV, M4A ...
    duration: float | None = None       # seconds; None for projects made before this was stored


class MediaMix(BaseModel):
    """Whether AI-made pictures are wanted (every video is 100% motion graphics, with real media of any amount drawn inside it)."""
    ai_images: bool = False


class ProjectInfo(BaseModel):
    id: str
    name: str
    created: str
    state: str
    aspect: Literal["9:16", "16:9"] | None = None     # chosen when the project was created; projects made before this existed have none
    use_images: bool = True                            # Use Images toggle: False = Motion-Only mode (no image stages)
    motion_branch: bool = False                        # the run has the Motion Planning -> Motion Generation branch (projects made before it existed: false)
    reusable_motion_templates: bool = True             # Reusable Motion Templates toggle: True = Template Mode, False = Custom Code Mode
    media: MediaMix | None = None                      # the media settings chosen at upload (SYSTEM/core/media_kinds.py); projects made before it existed have none (defaults apply)
    motion_kit: bool = False                           # the optional motion kit (VIDEO_ENGINE/remotion/src/kit) is on; chosen at upload, locked afterwards
    audio: AudioRef | None = None


class Status(BaseModel):
    step: str | None = None
    percent: float = 0
    message: str = ""
    error: str | None = None
    hint: str | None = None
    waiting_for: Literal["plan", "images", "review"] | None = None
    command: str | None = None          # exact text to run in Claude Code when waiting_for == "plan"
    running: bool = False
    state: str = ""


class JobStarted(BaseModel):
    project: str
    label: str
    steps: list[str]


class Deleted(BaseModel):
    deleted: str


class GenerationFailure(BaseModel):
    n: int
    error: str


class Generation(BaseModel):
    """Progress of the app's own prompt writer (promptgen.py): all prompts after the analysis approval, or one prompt."""
    state: Literal["idle", "running", "done", "failed"] = "idle"
    kind: Literal["all", "one", "plan"] | None = None
    n: int | None = None
    total: int = 0
    done: int = 0
    current: int | None = None
    failed: list[GenerationFailure] = []
    skipped: list[int] = []             # the user changed or approved these while a new text was written: their version stayed
    error: str | None = None
    started: str | None = None
    finished: str | None = None
