"""Pydantic request/response models of the API (JSON contracts for the UI)."""
from typing import Any, Literal

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


class UploadResult(BaseModel):
    saved: list[str]
    renamed: dict[str, str] = {}        # original name -> saved name (collisions inside one upload)
    replaced: list[str] = []            # names that already existed and were overwritten


class Deleted(BaseModel):
    deleted: str


# ---------- review workflow (scene table, prompt review, approvals, crops, timeline); new models, the ones above are unchanged ----------
Severity = Literal["error", "warning"]
Aspect = Literal["16:9", "9:16"]
GateName = Literal["analysis", "prompts", "images"]


class Issue(BaseModel):
    severity: Severity
    message: str


class Keyword(BaseModel):
    text: str
    at: float


class SceneRow(BaseModel):
    id: int
    start: float
    end: float
    duration: float
    narration: str                      # Telugu, from the transcript
    narration_en: str
    meaning: str
    concept: str
    mood: str
    mode: str
    pattern: str
    keywords: list[Keyword]
    slots: list[str]                    # image slots of this scene (prompts_map)
    status: Literal["ok", "warning", "error"]
    issues: list[Issue]


class SceneTable(BaseModel):
    scenes: list[SceneRow]
    general: list[Issue]
    duration: float | None
    status: Literal["ok", "warning", "error", "empty"]


class CropValue(BaseModel):
    x: float
    y: float
    zoom: float
    file: str
    stale: bool = False                 # the image was replaced after the crop was made


class PromptImage(BaseModel):
    file: str | None
    status: Literal["ok", "review", "missing"]
    method: str
    score: float | None
    margin: float | None
    note: str | None
    warnings: list[str]
    width: int | None
    height: int | None
    ratio: float | None


class HistoryEntry(BaseModel):
    text: str
    at: str
    by: str


class PromptItem(BaseModel):
    n: int
    scene: int
    slot: str
    role: str
    ratio: str
    required: bool
    text: str
    full_text: str                      # what prompts.txt contains (style suffix and ratio included)
    scene_start: float | None
    scene_end: float | None
    concept: str
    narration_en: str
    status: Literal["generated", "edited", "approved", "regenerating"]
    approved: bool
    edited: bool
    regen_requested: str | None
    generated_text: str | None          # the text before the user's edit
    history: list[HistoryEntry]
    history_count: int
    image: PromptImage | None
    crops: dict[str, CropValue]


class Gate(BaseModel):
    approved: bool
    stale: bool                         # was approved, but something upstream changed since
    at: str | None
    ready: bool
    blockers: list[str]
    warnings: list[str] = []
    total: int | None = None
    approved_count: int | None = None


class Gates(BaseModel):
    analysis: Gate
    prompts: Gate
    images: Gate


class TimelineFinding(BaseModel):
    severity: Literal["error", "warning", "info"]
    rule: str
    scene: int | None
    shot: str | None
    message: str
    advice: str


class TimelineAspect(BaseModel):
    composition: bool
    checked: bool
    fresh: bool
    ok: bool
    errors: int
    warnings: int
    ready: bool
    preview_video: bool
    final_video: bool
    findings: list[TimelineFinding] = []        # the pre-render check's errors and warnings (scene, shot, message, advice)


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


class ReviewState(BaseModel):
    project: str
    plan_ready: bool
    analysis: SceneTable
    prompts: list[PromptItem]
    gates: Gates
    timeline: dict[str, TimelineAspect]
    generation: Generation = Generation()


class CropRequest(BaseModel):
    aspect: Aspect = "9:16"
    x: float | None = None              # crop centre in the picture, 0..1
    y: float | None = None
    zoom: float = 1.0                   # 1 = the picture just fills the frame
    reset: bool = False


class CropResult(BaseModel):
    n: int
    aspect: Aspect
    crop: CropValue | None


class ApproveRequest(BaseModel):
    gate: GateName
    approved: bool = True


class RunRequest(BaseModel):
    stage: Literal["timeline", "preview", "final"]
    aspect: Aspect = "9:16"

# ---------- visual plan (visual_plan.json) ----------
class PlanIssue(BaseModel):
    severity: Severity
    message: str
    path: list[str | int] | None = None  # keys and list indexes to the exact field of the scene JSON; None = the scene as a whole


class VisualPlanState(BaseModel):
    plan: dict[str, Any]                # the real visual_plan.json
    all_approved: bool                  # every scene approved: the condition for the Image & Video stage
    issues: dict[str, list[PlanIssue]] = {}   # per scene id: every error and warning found now (not stored in the file)


class VisualSceneState(BaseModel):
    scene: dict[str, Any]               # the real JSON of one scene
    all_approved: bool
    issues: list[PlanIssue] = []


class SceneChange(BaseModel):
    path: list[str | int]               # keys and list indexes down to one value, e.g. ["shots", 0, "camera", "movement"]
    value: Any


class SceneSave(BaseModel):
    revision: int                       # meta.revision of the scene the user opened; a different one means it changed meanwhile
    changes: list[SceneChange]


class SceneRegenerate(BaseModel):
    confirm_overwrite: bool = False


class SceneApproval(BaseModel):
    action: Literal["approve", "reopen"]


# ---------- video QC (measured on the rendered mp4) ----------
class QcCheck(BaseModel):
    id: str
    check: str
    source: str
    severity: Literal["error", "warning", "info"]
    result: Literal["passed", "warning", "failed"]
    detail: str
    scene: int | None = None
    at: float | None = None          # where in the video (seconds) the finding is, when it has a place
    until: float | None = None


class QcMedia(BaseModel):
    size_bytes: int
    duration: float
    width: int | None = None
    height: int | None = None
    fps: float
    video_codec: str | None = None
    audio_codec: str | None = None
    modified: float


class QcReport(BaseModel):
    aspect: Aspect
    preview: bool
    video: str
    result: Literal["passed", "passed_with_warning", "failed"]
    checks: list[QcCheck]
    media: QcMedia | None = None

