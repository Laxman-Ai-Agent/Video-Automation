"""Central config. Import this FIRST so model caches are set before torch/HF/rembg load."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECTS_DIR = PROJECT_ROOT / "projects"
MODELS_DIR = PROJECT_ROOT / "models"
REMOTION_DIR = PROJECT_ROOT / "VIDEO_ENGINE" / "remotion"
FFMPEG_DIR = PROJECT_ROOT / "VIDEO_ENGINE" / "ffmpeg"

# HF_HOME is left unset on purpose: models are reused from the user cache (~/.cache/huggingface).
os.environ.setdefault("TORCH_HOME", str(MODELS_DIR / "torch"))
os.environ.setdefault("U2NET_HOME", str(MODELS_DIR / "u2net"))

# Whisper (CPU). Reused from the user HF cache; set WHISPER_MODEL=medium/small for speed.
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "large-v3")
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE = "int8"
# Whisper's decoder is limited to 448 tokens and Telugu is token-hungry, so 30 s windows get cut
# mid-character and speech is lost. We transcribe short chunks cut at low-energy points instead.
WHISPER_CHUNK_MAX = 9.0     # seconds
WHISPER_CHUNK_MIN = 4.0
WHISPER_VERSION = "v3"      # bump to invalidate cached transcripts after changing decode options
WHISPER_LOCAL_ONLY = True   # never download; fail loudly if the cache is missing

# Cuts
SILENCE_MIN = 0.35        # seconds
SILENCE_DB = -35          # ffmpeg silencedetect threshold

# Failure handling (M9)
SILENT_DB = -60              # a file whose loudest sample is below this has no sound (ffmpeg volumedetect)
MIN_FREE_GB_WORK = 0.3       # free disk needed to import images or transcribe
MIN_FREE_GB_RENDER = 2.0     # free disk needed before a Remotion render (frames + output)

# Matching (M5). All tunable here.
CLIP_MODEL = "ViT-B-32"
CLIP_PRETRAINED = "laion2b_s34b_b79k"   # reused from the user HF cache, local files only
CLIP_MIN_SCORE = 0.22
CLIP_MIN_MARGIN = 0.03
ROLE_PENALTY = 0.03          # soft penalty when an image disagrees with the prompt role
MAX_IMAGE_WIDTH = 2560       # pre-resize before embedding / checks
HERO_MIN_WIDTH = 1920
RATIO_TOLERANCE = 0.05
BLUR_MIN_VAR = 60.0          # Laplacian variance below this = blurry
DUP_HASH_DISTANCE = 4
WHITE_BORDER_FRACTION = 0.85  # share of border pixels that must be near-white for "white background"
LOW_RES_ZOOM_CAP = 1.05
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

FPS = 30


# ---------- improvement/audio-visual (see improvement/MASTER_PLAN.md) ----------
# Every new behavior is behind a flag that is OFF by default: with all flags off the output is identical to before.
# Turn one on with the environment variable A2V_<NAME>=1 (names: FINGERPRINTS, HIGHLIGHTS, MATCH_DETAIL, SHOTS, VALIDATION).
def improve(name: str) -> bool:
    return os.environ.get(f"A2V_{name.upper()}", "0") == "1"


# Stage-logic versions: bump a number when that stage's code changes its output, so cached results are not reused (used when A2V_FINGERPRINTS=1).
STAGE_VERSIONS = {"cuts": 1, "plan-input": 1, "prompts": 1, "ingest": 1, "match": 1, "fill": 1, "fill-9x16": 1,
                  "render-preview": 1, "render-final": 1, "render-preview-9x16": 1, "render-final-9x16": 1}
# Config values that change a stage's output (their current values go into that stage's fingerprint when A2V_FINGERPRINTS=1).
STAGE_CONFIG_KEYS = {"cuts": ("SILENCE_MIN", "SILENCE_DB"),
                     "match": ("CLIP_MODEL", "CLIP_PRETRAINED", "CLIP_MIN_SCORE", "CLIP_MIN_MARGIN", "ROLE_PENALTY", "WHITE_BORDER_FRACTION",
                               "MATCH_HIGH_SCORE", "MATCH_HIGH_MARGIN"),
                     "fill": ("LOW_RES_ZOOM_CAP", "HIGHLIGHT_SNAP_SEC", "HIGHLIGHT_TOLERANCE_SEC", "HIGHLIGHTS_MAX_PER_SENTENCE", "HIGHLIGHT_DURATION_SEC", "HIGHLIGHT_MIN_GAP_SEC"),
                     "fill-9x16": ("LOW_RES_ZOOM_CAP", "HIGHLIGHT_SNAP_SEC", "HIGHLIGHT_TOLERANCE_SEC", "HIGHLIGHTS_MAX_PER_SENTENCE", "HIGHLIGHT_DURATION_SEC", "HIGHLIGHT_MIN_GAP_SEC")}
# A2V_MOTION_SPEED: pace factor of the motion library (shorter entrances, stagger, exits and transitions; 1 = as designed). Empty = the default (1.3, or 1.4 without pictures).
MOTION_SPEED = os.environ.get("A2V_MOTION_SPEED", "").strip()
# A2V_STYLE_KIT: the style kit of the motion library (VIDEO_ENGINE/remotion/src/styleKit.ts): scenes change colour look from one visual family and the headline becomes a phrase (per-word font, size, colour, marker).
# Empty / 0 = off (the compositions are exactly what they were); `1` = editorial. It is part of the motion inputs, so switching it never reuses the other mode's plan.
STYLE_KIT = os.environ.get("A2V_STYLE_KIT", "").strip()
FLAG_NAMES = ("fingerprints", "highlights", "match_detail", "shots", "validation", "cancel", "icons", "motion")   # motion: VIDEO_ENGINE/remotion/src/motion (A2V_MOTION=1, read by build_composition.ts)

# Match confidence bands (values chosen from the real reports of projects/demo and my-video-project-5eca: scores 0.29-0.40, margins -0.02..0.15;
# the margin, not the score, separates good from doubtful matches). high -> use; medium -> review; low/none -> needs review / missing.
MATCH_HIGH_SCORE = 0.30
MATCH_HIGH_MARGIN = 0.06       # medium = the existing "ok" rule (CLIP_MIN_SCORE / CLIP_MIN_MARGIN); anything below is low

# Shots (a scene longer than LONG_SCENE_SEC may be split; no shot shorter than MIN_SHOT_SEC: median spoken word is 0.4 s)
LONG_SCENE_SEC = 8.0
MIN_SHOT_SEC = 1.5

SHOT_SNAP_SEC = 1.0                      # a shot boundary moves to a real pause/cut only if one lies within this distance of the narration cue
SHOT_TRANSITION_SEC = 0.5                # longest fade/wipe between two shots of one scene (also limited by TRANSITION_MAX_SHARE)
SHOT_TRANSITIONS = ("fade", "wipe")      # layer enter animations the renderer already has; never the same one twice in a row
SHOT_CAMERAS = ("ken-burns", "hold")     # simulated move on one picture; alternated so two neighbouring shots never repeat the same zoom

# Highlights (emphasis events). Tolerance: how far a highlight start may be from the spoken word it marks.
HIGHLIGHT_TOLERANCE_SEC = 0.15
HIGHLIGHT_SNAP_SEC = 0.35                # a plan keyword is moved to the nearest spoken word only if one starts within this distance (a median word lasts 0.4 s: farther is ambiguous, so it stays "estimated" and is reported)
HIGHLIGHT_MIN_GAP_SEC = 0.1              # two highlights never overlap: the earlier one ends this long before the next starts
HIGHLIGHTS_MAX_PER_SENTENCE = 2          # CLAUDE.md: max 1-2 text elements per scene
HIGHLIGHT_DURATION_SEC = (0.8, 3.0)      # motion_checks.MAX_EFFECT_SECONDS is 4.0 for any accent

# Transitions
TRANSITION_NO_REPEAT = True              # existing rule (build_composition.ts pickTransition), kept as one documented setting
TRANSITION_MAX_SHARE = 0.4               # a transition may take at most this share of the shorter neighbouring shot

# 9:16 safe area, ONE definition for new code (captions, graphics, validation). Fractions of the frame height/width.
# The existing numbers live in VIDEO_ENGINE/remotion/src/theme.json (safeMargin, portrait.captionBottom/lowerThirdBottom/labelTop) and
# backend/prerender_checks.py UI_BOTTOM; tests/test_improve_p05.py fails if they drift apart from this table.
SAFE_AREA = {"margin": 0.05,              # all sides, both aspects
             "portrait_ui_bottom": 0.16,  # phone apps cover this part of the frame bottom: nothing important below the line
             "portrait_caption_bottom": 0.18, "portrait_lower_third_bottom": 0.20, "portrait_label_top": 0.10}


def project_dir(project: str | Path) -> Path:
    p = Path(project)
    return p if p.exists() else PROJECTS_DIR / str(project)


