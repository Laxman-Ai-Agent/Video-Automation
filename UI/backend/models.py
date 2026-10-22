"""Pydantic mirrors of docs/schemas.md. Every JSON file is validated through these."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Mode = Literal["image-composite", "graph", "typography", "map", "stock-video", "mixed"]
Role = Literal["main", "supporting", "icon", "object", "background"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Style(Strict):
    suffix: str
    palette: list[str] = Field(min_length=2)       # roles: [base, accent, secondary] (VIDEO_ENGINE/remotion/src/theme.ts)
    grade: Literal["warm", "cool", "teal-orange"] | None = None   # optional color grade overlay


class Keyword(Strict):
    text: str
    at: float


class DataPoint(Strict):
    label: str
    value: float


class Params(Strict):
    """Pattern parameters (see VIDEO_ENGINE/remotion/src/patterns PP). Claude fills only what the pattern needs."""
    text: str | None = None
    text2: str | None = None
    mark: str | None = None
    icon: str | None = None
    number: float | None = None
    unit: str | None = None
    data: list[DataPoint] | None = None
    kind: Literal["bar", "line", "pie"] | None = None
    region: str | None = None
    highlight: list[str] | None = None
    route: list[tuple[float, float]] | None = None
    labels: list[str] | None = None
    video: str | None = None
    approximate: bool = False   # numbers not literally stated in the audio


class PlanScene(Strict):
    id: int
    start: float
    end: float
    meaning: str
    concept: str
    mood: str
    mode: Mode
    pattern: str
    transition: str | None = None
    transition_dur: float | None = None
    keywords: list[Keyword] = []
    params: Params = Params()


class ScenePlan(Strict):
    style: Style
    scenes: list[PlanScene] = Field(min_length=1)


class PromptItem(Strict):
    n: int
    scene: int
    slot: str
    role: Role
    ratio: Literal["16:9", "4:3", "1:1", "9:16", "3:4"]
    required: bool = True
    bg: Literal["full", "removable"] = "full"
    text: str


class PromptsMap(Strict):
    prompts: list[PromptItem]


class Layer(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str
    z: float = 0


class CompScene(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int
    start: float
    end: float
    pattern: str | None = None
    layers: list[Layer]
    transition_out: dict | None = None


class Meta(BaseModel):
    fps: int = 30
    width: int = 1920
    height: int = 1080
    audio: str
    duration: float
    subtitles: bool = False
    palette: list[str] | None = None   # copied from scene_plan.style by the fill step
    grade: str | None = None


class Composition(BaseModel):
    meta: Meta
    scenes: list[CompScene] = Field(min_length=1)
    words: list[dict] | None = None


class Cut(BaseModel):
    t: float
    reason: str
    silence: float = 0


class Cuts(BaseModel):
    cuts: list[Cut]


class MatchItem(BaseModel):
    n: int
    file: str | None
    method: Literal["filename", "clip", "manual", "none"]
    score: float | None = None
    margin: float | None = None
    status: Literal["ok", "review", "missing"]
    note: str | None = None      # why it needs review (e.g. best alternative prompt)


class MatchReport(BaseModel):
    matches: list[MatchItem]
    unused: list[str] = []
    duplicates: list[list[str]] = []
    warnings: list[dict] = []
    broken: list[str] = []
