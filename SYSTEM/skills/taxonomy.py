"""Authoritative Machine-Readable 25 Video-Editing Categories Taxonomy and Classification Engine.

Centrally manages:
1. Canonical definitions, subcategories, keywords, tech stacks, and agent permissions for 25 categories.
2. Machine-readable persistence in categories.json.
3. Extensible registration allowing future category additions without code redesign.
4. Intelligent semantic classification mapping natural language or capability queries to categories with confidence scoring.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("skill_library.taxonomy")

TAXONOMY_DIR = Path(__file__).parent
CATEGORIES_FILE = TAXONOMY_DIR / "categories.json"


@dataclass
class VideoEditingCategory:
    """Canonical metadata defining a video editing skill category."""
    category_id: str
    name: str
    description: str
    subcategories: list[dict[str, str]] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    technology_stack: list[str] = field(default_factory=list)
    applicable_agents: list[str] = field(default_factory=list)
    sample_capabilities: list[str] = field(default_factory=list)
    validation_rules: dict[str, Any] = field(default_factory=dict)
    is_core: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VideoEditingCategory:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class CategoryClassificationResult:
    """Result of classifying a capability query against the 25-category taxonomy."""
    primary_category: str
    primary_category_name: str
    subcategory: str | None
    confidence: float
    matched_keywords: list[str]
    alternative_categories: list[dict[str, Any]]
    query: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Initial 25 Video-Editing Categories Canonical Definitions
# ---------------------------------------------------------------------------

INITIAL_CATEGORIES: list[dict[str, Any]] = [
    {
        "category_id": "graphics",
        "name": "Graphics",
        "description": "Graphic elements, badges, lower-thirds, shape layers, callouts, and visual accents.",
        "subcategories": [
            {"id": "lower_thirds", "name": "Lower Thirds", "description": "Presenter nameplates, topic banners, and title bars."},
            {"id": "callouts", "name": "Callouts & Pointers", "description": "Focus pointers, circular highlights, and callout labels."},
            {"id": "vector_shapes", "name": "Vector Shapes & Accents", "description": "Polygons, badges, starbursts, framing corners."},
        ],
        "keywords": ["graphics", "lower-third", "badge", "callout", "shape", "overlay", "accent", "ribbon", "banner"],
        "technology_stack": ["remotion", "react", "svg", "css"],
        "applicable_agents": ["visual_planning", "motion_animation", "motion_template_selection", "timeline_build"],
        "sample_capabilities": ["lower-third-animator", "svg-callout-generator", "vector-shape-overlay"],
        "validation_rules": {"requires_svg_or_canvas": True, "max_fps_impact": "low"},
    },
    {
        "category_id": "charts",
        "name": "Charts",
        "description": "Animated statistical charts, bar graphs, line plots, pie charts, and data meters.",
        "subcategories": [
            {"id": "bar_charts", "name": "Bar & Column Charts", "description": "Vertical and horizontal animated bar graphs."},
            {"id": "line_charts", "name": "Line & Trend Plots", "description": "Multi-series line graphs with area fills and cursor followers."},
            {"id": "radial_pie", "name": "Pie, Donut & Gauge Meters", "description": "Circular progress rings, donut charts, and dials."},
        ],
        "keywords": ["charts", "chart", "bar chart", "line plot", "pie chart", "donut chart", "graph", "data visualization", "metrics", "plot"],
        "technology_stack": ["remotion", "react", "d3", "svg"],
        "applicable_agents": ["visual_planning", "motion_animation", "timeline_build"],
        "sample_capabilities": ["dynamic-bar-chart", "interpolated-line-plot", "donut-percentage-ring"],
        "validation_rules": {"requires_data_prop": True, "spring_animated": True},
    },
    {
        "category_id": "maps",
        "name": "Maps",
        "description": "Interactive maps, geographical route paths, territory highlights, and pin animations.",
        "subcategories": [
            {"id": "geo_borders", "name": "Regional & Country Borders", "description": "GeoJSON border outlines, state maps, choropleth fills."},
            {"id": "route_animation", "name": "Route & Flight Paths", "description": "Animated dashed paths, waypoint markers, flight curves."},
            {"id": "pin_markers", "name": "Location Pins & Popups", "description": "Bouncing pin icons, location tags, pulse radars."},
        ],
        "keywords": ["maps", "map", "geojson", "route", "geography", "india", "borders", "location pin", "gps", "travel path"],
        "technology_stack": ["remotion", "react", "d3-geo", "svg"],
        "applicable_agents": ["visual_planning", "motion_animation", "timeline_build"],
        "sample_capabilities": ["india-states-highlighter", "animated-travel-route", "location-pin-radar"],
        "validation_rules": {"supports_aspect_ratios": ["16:9", "9:16"]},
    },
    {
        "category_id": "typography",
        "name": "Typography",
        "description": "Kinetic typography, animated text headers, glitch text, and expressive font treatments.",
        "subcategories": [
            {"id": "kinetic_titles", "name": "Kinetic Title Sequences", "description": "High-impact spring-driven hero headlines and dynamic type."},
            {"id": "typewriter", "name": "Typewriter & Word-Reveal", "description": "Character-by-character typewriter and word staggered fades."},
            {"id": "text_styling", "name": "Telugu & Bilingual Typography", "description": "Native script typography, complex glyph shaping, dual-script styling."},
        ],
        "keywords": ["typography", "kinetic typography", "text animation", "title", "headline", "typewriter", "font", "telugu text", "script"],
        "technology_stack": ["remotion", "react", "css-animation", "opentype"],
        "applicable_agents": ["motion_animation", "motion_planning", "timeline_build", "audio_analyzer"],
        "sample_capabilities": ["kinetic-typography-springs", "telugu-word-reveal", "staggered-headline-animator"],
        "validation_rules": {"preserves_telugu_orthography": True, "no_overflow": True},
    },
    {
        "category_id": "motion_animation",
        "name": "Motion Animation",
        "description": "Core motion physics, spring curves, keyframed transforms, easing, and spatial choreography.",
        "subcategories": [
            {"id": "spring_physics", "name": "Remotion Spring Physics", "description": "Damped harmonic spring curves, bounce stiffness, mass tuning."},
            {"id": "spatial_transforms", "name": "Spatial Transforms & Scale", "description": "3D rotation, perspective scaling, orbital tracking."},
            {"id": "interpolations", "name": "Easing & Value Interpolations", "description": "Bézier easing curves, color transitions, staggered sequences."},
        ],
        "keywords": ["motion animation", "motion", "spring curves", "easing", "animation", "keyframe", "physics", "interpolation", "remotion-spring"],
        "technology_stack": ["remotion", "react", "typescript"],
        "applicable_agents": ["motion_animation", "motion_planning", "motion_template_selection", "timeline_build"],
        "sample_capabilities": ["remotion-spring-curves", "elastic-bounce-interpolator", "staggered-children-motion"],
        "validation_rules": {"deterministic_frame_based": True},
    },
    {
        "category_id": "transitions",
        "name": "Transitions",
        "description": "Scene-to-scene transitions including crossfades, whip pans, zoom transitions, and glitch wipes.",
        "subcategories": [
            {"id": "whip_pan", "name": "Whip Pan & Directional Slides", "description": "High-velocity directional camera sweeps and motion blur slides."},
            {"id": "zoom_morph", "name": "Zoom In/Out & Morph Cuts", "description": "Centred scale transitions, optic zooms, seamless push-ins."},
            {"id": "alpha_wipes", "name": "Shape & Matte Wipes", "description": "Diagonal wipes, circular iris cuts, pattern reveals."},
        ],
        "keywords": ["transitions", "transition", "whip pan", "crossfade", "zoom transition", "wipe", "cut", "dissolve", "morph transition"],
        "technology_stack": ["remotion", "react", "gl-transitions", "css"],
        "applicable_agents": ["motion_animation", "motion_planning", "timeline_build", "main_orchestrator"],
        "sample_capabilities": ["whip-pan-directional", "smooth-crossfade-dissolve", "circular-iris-wipe"],
        "validation_rules": {"zero_gap_guarantee": True, "frame_aligned": True},
    },
    {
        "category_id": "vfx",
        "name": "VFX",
        "description": "Visual effects, particle emitters, light leaks, chromatic aberration, glow, and camera shake.",
        "subcategories": [
            {"id": "particles", "name": "Particle Systems", "description": "Floating dust particles, embers, confetti, abstract geometric sparks."},
            {"id": "lighting", "name": "Light Leaks & Lens Flares", "description": "Organic anamorphic flares, warm vintage light leaks, bokeh."},
            {"id": "distortion", "name": "Chromatic Aberration & Shake", "description": "RGB split displacement, handheld camera jitter, scanlines."},
        ],
        "keywords": ["vfx", "particle", "glow", "chromatic aberration", "light leak", "flare", "camera shake", "shader", "visual effect"],
        "technology_stack": ["remotion", "react", "webgl", "svg-filter"],
        "applicable_agents": ["motion_animation", "timeline_build", "visual_planning"],
        "sample_capabilities": ["subtle-floating-particles", "anamorphic-light-leak", "rgb-split-glitch-filter"],
        "validation_rules": {"deterministic_seed": True, "headless_render_compatible": True},
    },
    {
        "category_id": "infographics",
        "name": "Infographics",
        "description": "Information graphics, comparison cards, sequential timelines, process flowcharts, and stats.",
        "subcategories": [
            {"id": "process_timelines", "name": "Timelines & Roadmaps", "description": "Horizontal and vertical chronological milestones."},
            {"id": "comparison_cards", "name": "Side-by-Side Comparisons", "description": "Versus tables, pros/cons cards, feature check grids."},
            {"id": "stats_counters", "name": "Metric Counters & Badges", "description": "Animated counting numbers, percentages, KPI cards."},
        ],
        "keywords": ["infographics", "infographic", "timeline", "flowchart", "comparison", "stats card", "counter", "milestones", "diagram"],
        "technology_stack": ["remotion", "react", "svg"],
        "applicable_agents": ["visual_planning", "motion_animation", "timeline_build"],
        "sample_capabilities": ["chronological-timeline-slider", "side-by-side-feature-compare", "animated-kpi-counter"],
        "validation_rules": {"clear_contrast": True, "safe_zone_adherent": True},
    },
    {
        "category_id": "2d_graphics",
        "name": "2D Graphics",
        "description": "2D vector artwork, flat illustrations, icon sets, character cards, and line art.",
        "subcategories": [
            {"id": "flat_illustrations", "name": "Flat Vector Illustrations", "description": "Modern editorial illustrations, character vignettes, spot art."},
            {"id": "animated_icons", "name": "Animated Icon Packs", "description": "Stroke-drawn icons, Lucide animated vectors, tech icons."},
            {"id": "badges_emblems", "name": "Emblems & Stamps", "description": "Circular certification seals, verification badges, stamps."},
        ],
        "keywords": ["2d graphics", "2d", "vector", "illustration", "icons", "flat design", "svg art", "line art"],
        "technology_stack": ["remotion", "react", "svg"],
        "applicable_agents": ["visual_planning", "motion_animation", "motion_template_selection"],
        "sample_capabilities": ["lucide-icon-stroke-animator", "flat-vector-character-card", "certified-seal-stamp"],
        "validation_rules": {"scalable_vector": True},
    },
    {
        "category_id": "3d_graphics",
        "name": "3D Graphics",
        "description": "Three.js / 3D models, isometric elements, spatial geometry, and 3D camera projections.",
        "subcategories": [
            {"id": "isometric_objects", "name": "Isometric Graphics", "description": "Isometric tech buildings, server racks, geometric cubes."},
            {"id": "threejs_elements", "name": "Three.js Render Components", "description": "3D spinning globe, wireframe models, particle clouds."},
            {"id": "spatial_camera", "name": "3D Camera Rig & Flythrough", "description": "Perspective camera flythrough, orbital pan, z-depth shifts."},
        ],
        "keywords": ["3d graphics", "3d", "three.js", "isometric", "threejs", "camera flythrough", "mesh", "wireframe", "globe"],
        "technology_stack": ["remotion", "react", "three", "@react-three/fiber"],
        "applicable_agents": ["visual_planning", "motion_animation", "timeline_build"],
        "sample_capabilities": ["isometric-tech-rack", "spinning-3d-wireframe-globe", "orbital-perspective-camera"],
        "validation_rules": {"cpu_fallback_available": True, "headless_compatible": True},
    },
    {
        "category_id": "science_visuals",
        "name": "Science Visuals",
        "description": "Scientific animations, mathematical equations, atomic structures, space physics, and schematics.",
        "subcategories": [
            {"id": "math_equations", "name": "KaTeX & Formula Animations", "description": "Step-by-step mathematical proof reveals, calculus graphs."},
            {"id": "molecular_space", "name": "Physics & Space Visuals", "description": "Orbital mechanics, planet renders, Bohr atomic models."},
            {"id": "circuit_schematics", "name": "Technical Schematics", "description": "Circuit board traces, architectural blueprints, radar scans."},
        ],
        "keywords": ["science visuals", "science", "formula", "katex", "atomic", "physics", "orbital", "schematic", "molecule", "math"],
        "technology_stack": ["remotion", "react", "katex", "svg", "canvas"],
        "applicable_agents": ["visual_planning", "motion_animation", "timeline_build"],
        "sample_capabilities": ["katex-equation-animator", "orbital-planet-system", "blueprint-circuit-tracer"],
        "validation_rules": {"high_precision_rendering": True},
    },
    {
        "category_id": "documentary_graphics",
        "name": "Documentary Graphics",
        "description": "Archival framing, historical photo pan/zoom Ken Burns, newspaper clippings, and document highlights.",
        "subcategories": [
            {"id": "ken_burns", "name": "Ken Burns Photo Pan & Zoom", "description": "Smooth cinematic drift across historical photographs."},
            {"id": "newspaper_archival", "name": "Newspaper & Headline Clips", "description": "Vintage paper texture, yellowing highlight marker, clipping frames."},
            {"id": "document_redaction", "name": "Document Scan & Redaction", "description": "Government file dossiers, black marker un-redactions, typewriter stamps."},
        ],
        "keywords": ["documentary graphics", "documentary", "ken burns", "archival", "newspaper", "historical photo", "vintage", "dossier"],
        "technology_stack": ["remotion", "react", "css-filters", "svg"],
        "applicable_agents": ["visual_planning", "motion_animation", "timeline_build"],
        "sample_capabilities": ["cinematic-ken-burns-animator", "yellow-marker-text-highlighter", "archival-dossier-frame"],
        "validation_rules": {"aspect_ratio_responsive": True},
    },
    {
        "category_id": "ui_hud",
        "name": "UI / HUD",
        "description": "Futuristic heads-up displays (HUD), cyberpunk interfaces, UI mockups, and terminal windows.",
        "subcategories": [
            {"id": "tech_hud", "name": "Sci-Fi HUD Overlays", "description": "Targeting reticles, telemetry bars, circular radar sweeps, hex grids."},
            {"id": "terminal_cli", "name": "Code Terminal & Bash CLI", "description": "Hacker terminal windows, syntax-highlighted code typing, log streams."},
            {"id": "device_mockups", "name": "Mobile & Web Browser Frames", "description": "iPhone/browser UI frames with scrolling screencasts."},
        ],
        "keywords": ["ui hud", "ui", "hud", "terminal", "cyberpunk", "reticle", "cli", "code window", "interface", "mockup", "telemetry"],
        "technology_stack": ["remotion", "react", "svg", "css"],
        "applicable_agents": ["visual_planning", "motion_animation", "timeline_build"],
        "sample_capabilities": ["scifi-hud-reticle-radar", "code-typing-terminal-window", "browser-mockup-screencast"],
        "validation_rules": {"pixel_sharpness": True},
    },
    {
        "category_id": "layouts",
        "name": "Layouts",
        "description": "Multi-window grids, split-screen layouts, picture-in-picture (PiP), and safe-zone bounding.",
        "subcategories": [
            {"id": "split_screens", "name": "Split Screen & Multi-Panel Grids", "description": "2-way, 3-way, and 4-way dynamic split screen panels."},
            {"id": "pip_layouts", "name": "Picture-in-Picture (PiP)", "description": "Floating presenter oval/rectangle with drop shadow and border."},
            {"id": "safe_zones", "name": "Safe Zone Framing", "description": "YouTube Shorts / Reels UI safety zone alignment and framing."},
        ],
        "keywords": ["layouts", "layout", "split screen", "grid", "pip", "picture in picture", "multi-panel", "safe zone", "letterbox"],
        "technology_stack": ["remotion", "react", "css-grid", "flexbox"],
        "applicable_agents": ["visual_planning", "motion_planning", "timeline_build", "motion_validation"],
        "sample_capabilities": ["dynamic-split-screen-panel", "reels-safe-zone-container", "floating-pip-presenter"],
        "validation_rules": {"enforces_safe_margins": True},
    },
    {
        "category_id": "image_animation",
        "name": "Image Animation",
        "description": "Parallax photo depth, 2.5D spatial separation, image morphing, cutout animation, and background defocus.",
        "subcategories": [
            {"id": "parallax_depth", "name": "2.5D Parallax Depth", "description": "Foreground subject separated from background with depth drift."},
            {"id": "cutout_animation", "name": "Cutout Puppet Motion", "description": "Collage paper cutout animations with subtle joint rotations."},
            {"id": "focus_racks", "name": "Focus Rack & Bokeh Blur", "description": "Depth-of-field transition shifting blur between foreground and background."},
        ],
        "keywords": ["image animation", "parallax", "2.5d", "depth", "cutout", "photo animation", "bokeh", "defocus"],
        "technology_stack": ["remotion", "react", "css-3d", "canvas"],
        "applicable_agents": ["visual_planning", "motion_animation", "timeline_build"],
        "sample_capabilities": ["parallax-subject-background-drift", "paper-cutout-collage-mover", "bokeh-depth-of-field-shift"],
        "validation_rules": {"supports_transparent_png": True},
    },
    {
        "category_id": "audio_visualization",
        "name": "Audio Visualization",
        "description": "Reactive waveforms, frequency spectrum bars, circular audio visualizers, and beat pulses.",
        "subcategories": [
            {"id": "waveform_bars", "name": "Linear Spectrum Bars", "description": "Dynamic frequency equalizer bars synced to narration audio."},
            {"id": "circular_reactive", "name": "Circular & Radial Visualizers", "description": "Radial spikes expanding outward based on audio energy."},
            {"id": "beat_pulse", "name": "Beat & Speech Pulse Rings", "description": "Expanding concentric glow rings triggered on voice activity."},
        ],
        "keywords": ["audio visualization", "waveform", "spectrum", "audio reactive", "equalizer", "sound waves", "frequency bars", "beat pulse"],
        "technology_stack": ["remotion", "@remotion/media-utils", "react", "canvas"],
        "applicable_agents": ["audio_analyzer", "motion_animation", "visual_planning", "timeline_build"],
        "sample_capabilities": ["remotion-audio-waveform", "radial-frequency-visualizer", "speech-energy-pulse-rings"],
        "validation_rules": {"deterministic_audio_sampling": True},
    },
    {
        "category_id": "backgrounds",
        "name": "Backgrounds",
        "description": "Ambient animated loops, organic gradient meshes, abstract motion backdrops, and subtle textures.",
        "subcategories": [
            {"id": "gradient_mesh", "name": "Animated Gradient Meshes", "description": "Smoothly shifting chromatic gradients and aurora waves."},
            {"id": "noise_grid", "name": "Cyber Grids & Tech Textures", "description": "Subtle perspective wireframe floor grids, dot matrix canvases."},
            {"id": "dark_world", "name": "Dark World Ambient Loops", "description": "Moody, high-contrast dark backdrops designed for the core brand look."},
        ],
        "keywords": ["backgrounds", "background", "backdrop", "gradient mesh", "aurora", "ambient loop", "dark world", "grid pattern", "texture"],
        "technology_stack": ["remotion", "react", "css", "svg"],
        "applicable_agents": ["visual_planning", "motion_animation", "timeline_build", "motion_template_selection"],
        "sample_capabilities": ["dark-world-ambient-canvas", "shifting-gradient-mesh", "perspective-wireframe-grid"],
        "validation_rules": {"loopable": True, "low_contrast_for_readability": True},
    },
    {
        "category_id": "compositing",
        "name": "Compositing",
        "description": "Multi-layer alpha masking, blend modes, chroma keying, luma mattes, and depth layering.",
        "subcategories": [
            {"id": "alpha_mattes", "name": "Alpha & Luma Mattes", "description": "Text or shape masking video layers using SVG clipPaths and CSS mask."},
            {"id": "blend_modes", "name": "Blend Mode Compositing", "description": "Screen, multiply, overlay, and color-dodge layer mixing."},
            {"id": "green_screen", "name": "Chroma Key & Spill Suppression", "description": "FFmpeg colorkey / chromakey extraction and spill neutralization."},
        ],
        "keywords": ["compositing", "composite", "alpha matte", "luma matte", "blend mode", "chroma key", "masking", "clip-path", "layer stacking"],
        "technology_stack": ["remotion", "react", "ffmpeg", "css-mask"],
        "applicable_agents": ["timeline_build", "render_video", "motion_animation"],
        "sample_capabilities": ["svg-clip-path-matte", "multi-layer-blend-compositor", "ffmpeg-chroma-keyer"],
        "validation_rules": {"supports_hardware_accel": True},
    },
    {
        "category_id": "color_grading",
        "name": "Color Grading",
        "description": "Color correction, 3D LUT application, tone mapping, contrast curves, and duotone grading.",
        "subcategories": [
            {"id": "lut_filters", "name": "3D LUT Application", "description": "Cinematic .cube LUT grading via FFmpeg lut3d filter or CSS matrix."},
            {"id": "tone_contrast", "name": "Tone Mapping & Contrast Curves", "description": "S-curve contrast, shadows lift, highlights rolloff, vibrance."},
            {"id": "duotone_monochrome", "name": "Duotone & Tint Treatments", "description": "High-impact brand duotones (e.g. Dark Cyan / Orange)."},
        ],
        "keywords": ["color grading", "color correction", "lut", "tone mapping", "contrast", "duotone", "saturation", "cinematic grade"],
        "technology_stack": ["ffmpeg", "css-filter", "svg-color-matrix"],
        "applicable_agents": ["render_video", "final_qc", "timeline_build"],
        "sample_capabilities": ["ffmpeg-lut3d-cinematic", "css-duotone-brand-grade", "contrast-tone-mapper"],
        "validation_rules": {"broadcast_safe_colors": True},
    },
    {
        "category_id": "time_effects",
        "name": "Time Effects",
        "description": "Speed ramping, smooth slow motion, freeze-frames, time-lapse, and reverse playback.",
        "subcategories": [
            {"id": "speed_ramping", "name": "Dynamic Speed Ramps", "description": "Bézier speed curve ramping from fast motion to slow impact."},
            {"id": "freeze_frames", "name": "Freeze Frame Accents", "description": "Audio-hit freeze frames with title or callout overlay."},
            {"id": "time_reversal", "name": "Time-Lapse & Reversals", "description": "Accelerated temporal sequences and smooth reverse looping."},
        ],
        "keywords": ["time effects", "speed ramp", "slow motion", "freeze frame", "time-lapse", "time", "motion rate", "pts"],
        "technology_stack": ["ffmpeg", "remotion"],
        "applicable_agents": ["motion_planning", "timeline_build", "render_video"],
        "sample_capabilities": ["ffmpeg-speed-ramp-pts", "freeze-frame-accent-layer", "timelapse-cadence-scaler"],
        "validation_rules": {"audio_pitch_compensation": True},
    },
    {
        "category_id": "audio_editing",
        "name": "Audio Editing",
        "description": "Voice cleanup, noise gating, silence trimming, loudness normalization (EBU R128), and EQ.",
        "subcategories": [
            {"id": "loudness_norm", "name": "EBU R128 Loudness Normalization", "description": "Two-pass loudness matching to -16 LUFS / -14 LUFS."},
            {"id": "noise_gate", "name": "Noise Gate & Silence Trimming", "description": "Background hiss reduction and clean leading/trailing silence trimming."},
            {"id": "audio_ducking", "name": "Background Music Ducking", "description": "Automatic sidechain attenuation of BGM under speech."},
        ],
        "keywords": ["audio editing", "audio", "loudness", "normalization", "ebu r128", "silence trimming", "noise gate", "ducking", "eq"],
        "technology_stack": ["ffmpeg", "python"],
        "applicable_agents": ["audio_analyzer", "final_qc", "render_video"],
        "sample_capabilities": ["ffmpeg-ebur128-loudnorm", "voice-activity-silence-trimmer", "sidechain-bgm-ducker"],
        "validation_rules": {"no_clipping_true_peak": True},
    },
    {
        "category_id": "captions",
        "name": "Captions",
        "description": "Word-level synced subtitles, karaoke word highlights, Telugu font shaping, and bilingual styling.",
        "subcategories": [
            {"id": "karaoke_highlight", "name": "Active Word Karaoke Highlight", "description": "Color highlight on the exact spoken word based on Whisper timestamps."},
            {"id": "telugu_shaping", "name": "Telugu Subtitle Typography", "description": "Correct Noto Sans Telugu / Mandali conjunct shaping, no broken glyphs."},
            {"id": "bilingual_captions", "name": "Bilingual Telugu/English Captions", "description": "Telugu script for vernacular words, Latin script for technical terms."},
        ],
        "keywords": ["captions", "subtitles", "karaoke", "word timestamps", "telugu captions", "closed captions", "srt", "vtt"],
        "technology_stack": ["remotion", "react", "css"],
        "applicable_agents": ["audio_analyzer", "motion_animation", "timeline_build", "final_qc"],
        "sample_capabilities": ["word-level-karaoke-captions", "telugu-shaping-subtitles", "bilingual-caption-formatter"],
        "validation_rules": {"word_timing_alignment": True, "zero_broken_glyphs": True},
    },
    {
        "category_id": "video_editing",
        "name": "Video Editing",
        "description": "Shot pacing, scene sequencing, B-roll cutting, visual rhythm, and jump cut smoothing.",
        "subcategories": [
            {"id": "shot_sequencing", "name": "Scene & Shot Sequencing", "description": "Assembling multi-scene timelines following narration structure."},
            {"id": "broll_matching", "name": "B-Roll Cut Insertion", "description": "Contextual B-roll cutaway placement over speech beats."},
            {"id": "pacing_control", "name": "Rhythmic Pacing Alignment", "description": "Snapping cut points to pause boundaries and musical beats."},
        ],
        "keywords": ["video editing", "video editor", "shot sequencing", "b-roll", "cut", "pacing", "scene assembly", "timeline edit"],
        "technology_stack": ["ffmpeg", "python", "remotion"],
        "applicable_agents": ["main_orchestrator", "scene_segmentation", "timeline_build", "final_qc"],
        "sample_capabilities": ["scene-cut-sequencer", "broll-beat-snapper", "pacing-rhythm-aligner"],
        "validation_rules": {"no_black_frames": True, "timeline_continuity": True},
    },
    {
        "category_id": "render_qa",
        "name": "Render QA",
        "description": "Automated video quality control, black frame detection, frozen video detection, and audio sync audit.",
        "subcategories": [
            {"id": "black_freeze_detect", "name": "Black & Freeze Frame Auditing", "description": "FFmpeg blackdetect and freezedetect pipeline scanner."},
            {"id": "av_sync_audit", "name": "Audio/Video Synchronization", "description": "Verifying that narration audio duration matches timeline frame count."},
            {"id": "codec_standards", "name": "Codec & Bitrate Compliance", "description": "Validating H.264/AAC MP4 profile, faststart moov atom, and resolution."},
        ],
        "keywords": ["render qa", "quality control", "qc", "black frame", "freeze detection", "audio sync", "bitrate", "codec compliance", "media probe"],
        "technology_stack": ["ffmpeg", "python", "ffprobe"],
        "applicable_agents": ["final_qc", "render_video", "final_video_delivery"],
        "sample_capabilities": ["ffmpeg-black-freeze-qc", "av-sync-duration-verifier", "mp4-faststart-validator"],
        "validation_rules": {"zero_black_frames": True, "tolerance_ms": 50},
    },
    {
        "category_id": "templates",
        "name": "Templates",
        "description": "Reusable motion templates, layout style kits, composition blueprints, and brand theme packs.",
        "subcategories": [
            {"id": "motion_templates", "name": "Reusable Motion Templates", "description": "Self-contained parametric compositions with customizable props."},
            {"id": "style_kits", "name": "Style Kits & Color Themes", "description": "Preset palettes, typography scales, border radii, and safe zones."},
            {"id": "scene_blueprints", "name": "Scene Composition Blueprints", "description": "Multi-layer composition archetypes (intro, explainer, stat, outro)."},
        ],
        "keywords": ["templates", "template", "style kit", "motion template", "preset", "theme", "blueprint", "brand kit", "reusable"],
        "technology_stack": ["remotion", "react", "typescript", "json"],
        "applicable_agents": ["motion_template_selection", "visual_planning", "motion_animation", "timeline_build"],
        "sample_capabilities": ["dark-world-motion-template", "explainer-scene-blueprint", "brand-style-kit-theme"],
        "validation_rules": {"parameterized_props": True, "has_preview_thumbnail": True},
    },
]

# Alias dictionary for convenience
CATEGORY_ALIASES: dict[str, list[str]] = {
    "2d_3d_graphics": ["2d_graphics", "3d_graphics"],
    "2d/3d graphics": ["2d_graphics", "3d_graphics"],
    "2d/3d": ["2d_graphics", "3d_graphics"],
    "motion": ["motion_animation"],
    "animation": ["motion_animation"],
    "audio": ["audio_editing", "audio_visualization"],
    "data_viz": ["charts", "infographics"],
    "hud": ["ui_hud"],
    "qa": ["render_qa"],
}


class CategoryTaxonomy:
    """Central management and semantic classification for the 25 Video Editing Categories."""

    def __init__(self, persistence_file: Path | None = None) -> None:
        self._persistence_file = persistence_file or CATEGORIES_FILE
        self._categories: dict[str, VideoEditingCategory] = {}
        self._initialize()

    def _initialize(self) -> None:
        """Loads categories from persistence or seeds initial 25 canonical categories."""
        if self._persistence_file.exists():
            try:
                data = json.loads(self._persistence_file.read_text(encoding="utf-8"))
                for c_data in data.get("categories", []):
                    cat = VideoEditingCategory.from_dict(c_data)
                    self._categories[cat.category_id] = cat
                logger.info(f"Loaded {len(self._categories)} categories from {self._persistence_file}")
                return
            except Exception as e:
                logger.warning(f"Failed to read existing categories file: {e}. Rebuilding defaults.")

        # Seed initial 25 categories
        for cat_data in INITIAL_CATEGORIES:
            cat = VideoEditingCategory.from_dict(cat_data)
            self._categories[cat.category_id] = cat

        self.save()

    def save(self) -> None:
        """Persists category taxonomy to machine-readable JSON."""
        self._persistence_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "1.0.0",
            "total_categories": len(self._categories),
            "categories": [c.to_dict() for c in self._categories.values()],
        }
        self._persistence_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_categories(self) -> list[VideoEditingCategory]:
        """Returns all registered categories in deterministic order."""
        return sorted(self._categories.values(), key=lambda c: c.category_id)

    def get_category(self, category_id: str) -> VideoEditingCategory | None:
        """Retrieves a category by ID or alias."""
        norm_id = category_id.lower().strip().replace("-", "_").replace(" ", "_")
        if norm_id in self._categories:
            return self._categories[norm_id]

        # Check aliases
        if norm_id in CATEGORY_ALIASES:
            first_target = CATEGORY_ALIASES[norm_id][0]
            return self._categories.get(first_target)

        return None

    def register_category(self, category: VideoEditingCategory | dict[str, Any]) -> VideoEditingCategory:
        """Registers a new or updated category dynamically, supporting future extensions."""
        if isinstance(category, dict):
            cat_obj = VideoEditingCategory.from_dict(category)
        else:
            cat_obj = category

        if not cat_obj.category_id:
            raise ValueError("Category category_id cannot be empty")

        self._categories[cat_obj.category_id] = cat_obj
        self.save()
        logger.info(f"Registered category '{cat_obj.category_id}' ({cat_obj.name})")
        return cat_obj

    def get_subcategories(self, category_id: str) -> list[dict[str, str]]:
        """Returns the list of subcategories for a given category."""
        cat = self.get_category(category_id)
        return cat.subcategories if cat else []

    def classify_capability(
        self,
        capability_query: str,
        description: str = "",
        keywords: list[str] | None = None,
    ) -> CategoryClassificationResult:
        """Intelligently classifies a requested capability or natural language requirement into the 25-category taxonomy.
        
        Calculates confidence score (0.0 to 1.0) based on:
        - Exact category ID / name matches (weight: 1.0)
        - Subcategory ID / name matches (weight: 0.85)
        - Keyword and capability token overlaps (weight: 0.6)
        - Technology stack relevance (weight: 0.4)
        """
        combined_text = f"{capability_query} {description} {' '.join(keywords or [])}".lower()
        query_tokens = set(re.findall(r"\b[a-z0-9_-]+\b", combined_text))

        # Check for direct alias match
        norm_q = capability_query.lower().strip().replace(" ", "_")
        raw_q = capability_query.lower().strip()
        matched_alias = CATEGORY_ALIASES.get(norm_q) or CATEGORY_ALIASES.get(raw_q)
        if not matched_alias and ("2d/3d" in raw_q or "2d_3d" in norm_q):
            matched_alias = ["2d_graphics", "3d_graphics"]

        if matched_alias:
            primary_id = matched_alias[0]
            cat = self._categories[primary_id]
            return CategoryClassificationResult(
                primary_category=cat.category_id,
                primary_category_name=cat.name,
                subcategory=cat.subcategories[0]["id"] if cat.subcategories else None,
                confidence=0.95,
                matched_keywords=[raw_q],
                alternative_categories=[
                    {"category_id": c_id, "name": self._categories[c_id].name, "confidence": 0.90}
                    for c_id in matched_alias[1:]
                    if c_id in self._categories
                ],
                query=capability_query,
            )

        scored_categories: list[tuple[VideoEditingCategory, str | None, float, list[str]]] = []

        for cat in self._categories.values():
            cat_score = 0.0
            matched_terms: list[str] = []
            best_subcat: str | None = None

            # 1. Exact Category ID or Name Match
            cat_id_clean = cat.category_id.replace("_", " ")
            if cat.category_id in combined_text or cat_id_clean in combined_text:
                cat_score += 0.50
                matched_terms.append(cat.category_id)
            if cat.name.lower() in combined_text:
                cat_score += 0.40
                matched_terms.append(cat.name.lower())

            # 2. Subcategory Match
            for sub in cat.subcategories:
                sub_id_clean = sub["id"].replace("_", " ")
                if sub["id"] in combined_text or sub_id_clean in combined_text or sub["name"].lower() in combined_text:
                    cat_score += 0.35
                    matched_terms.append(sub["name"])
                    if not best_subcat:
                        best_subcat = sub["id"]

            # 3. Keyword Match
            for kw in cat.keywords:
                kw_lower = kw.lower()
                if kw_lower in combined_text or any(token in kw_lower for token in query_tokens):
                    cat_score += 0.15
                    matched_terms.append(kw)

            # 4. Sample Capabilities Match
            for sample_cap in cat.sample_capabilities:
                if sample_cap in combined_text:
                    cat_score += 0.40
                    matched_terms.append(sample_cap)

            if cat_score > 0.0:
                normalized_score = min(1.0, round(cat_score, 3))
                scored_categories.append((cat, best_subcat, normalized_score, list(dict.fromkeys(matched_terms))))

        # Sort descending by confidence score
        scored_categories.sort(key=lambda x: x[2], reverse=True)

        if not scored_categories:
            # Fallback to general category
            fallback = self._categories.get("graphics", list(self._categories.values())[0])
            return CategoryClassificationResult(
                primary_category=fallback.category_id,
                primary_category_name=fallback.name,
                subcategory=None,
                confidence=0.10,
                matched_keywords=[],
                alternative_categories=[],
                query=capability_query,
            )

        top_cat, top_subcat, top_confidence, top_matches = scored_categories[0]
        alternatives = [
            {
                "category_id": c.category_id,
                "name": c.name,
                "subcategory": s,
                "confidence": score,
                "matched_terms": terms[:3],
            }
            for c, s, score, terms in scored_categories[1:4]
        ]

        return CategoryClassificationResult(
            primary_category=top_cat.category_id,
            primary_category_name=top_cat.name,
            subcategory=top_subcat or (top_cat.subcategories[0]["id"] if top_cat.subcategories else None),
            confidence=top_confidence,
            matched_keywords=top_matches,
            alternative_categories=alternatives,
            query=capability_query,
        )


# Singleton instance
_taxonomy_singleton: CategoryTaxonomy | None = None


def get_category_taxonomy() -> CategoryTaxonomy:
    """Returns the singleton CategoryTaxonomy instance."""
    global _taxonomy_singleton
    if _taxonomy_singleton is None:
        _taxonomy_singleton = CategoryTaxonomy()
    return _taxonomy_singleton
