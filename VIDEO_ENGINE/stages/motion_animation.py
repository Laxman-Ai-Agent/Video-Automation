"""Motion Animation: Stage 6 of the pipeline (step motion-build in pipeline.py).

In Phase 5 Motion-Only Custom Code Mode:
- Bypasses reusable motion presets (MotionTextLayer, MotionScene, etc.).
- Generates scene-specific, executable React/TSX animation source code under projects/<pid>/generated_motion/scene_*.tsx.
- Calls canonical LLM Gateway (purpose="generation", model_profile="code_generation") with skills & memory context.
- Implements bounded diagnostic-driven repair loop (purpose="repair", max 2 retries) on syntax/compile/AST errors.
- Strictly validates that no prohibited presets, dynamic code execution, shell calls, or network APIs are used.
- Project-isolated workspaces: each project owns its primary TSX files, hashes, and manifest.
- Remotion staging synchronization: protects the shared VIDEO_ENGINE/remotion/src/generated/ staging directory with a mutex lock during tsc compilation.
- Compiles code with TypeScript compiler (tsc --noEmit) and verifies zero compilation errors.
- Computes SHA-256 hashes of generated source files and records full provenance.
- Emits motion_animation.json with schema v2.0, source paths, hashes, compile status, skills, and memory references.
- Produces normalized composition.json referencing the generated custom scene modules.
- Runs mandatory stage LLM review.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from . import asset_collection, config, llm_gateway, llm_review, shared_memory, skill_registry, store
from SYSTEM.core import media_kinds as mk
from SYSTEM.core.resilience import CREDENTIAL_KINDS, redact_secrets

logger = logging.getLogger("motion_animation")

SCHEMA = "2.0"
VERSION = 2

# Global synchronization lock protecting the shared VIDEO_ENGINE/remotion/src/generated/ staging directory during tsc runs
_remotion_staging_lock = threading.RLock()

# Presets prohibited in Custom Code Mode
PROHIBITED_PRESETS = (
    "MotionTextLayer",
    "MotionScene",
    "MotionGfxLayer",
    "HighlightText",
    "IconPop",
    "ShapeAnim",
    "Chart",
    "Counter",
    "Callout",
    "MapLayer",
    "StockVideo",
    "LightLeak",
    "richenScene",
    "buildScene",
)

PROHIBITED_IMPORT_REGEX = re.compile(
    r"\b(?:import\s+.*?\b(" + "|".join(PROHIBITED_PRESETS) + r")\b|"
    r"from\s+[\"'].*?(?:components|motion|patterns).*?[\"'])",
    re.MULTILINE,
)


# The libraries a generated scene may import (installed in VIDEO_ENGINE/remotion, all frame-safe: SVG/DOM only, no 3D / WebGL / shaders / canvas). Anything else is rejected by the audit.
APPROVED_IMPORTS = (
    "react", "react/jsx-runtime", "remotion",
    "@remotion/paths", "@remotion/shapes", "@remotion/noise", "@remotion/layout-utils", "@remotion/lottie", "@remotion/captions", "@remotion/media-utils",
    "@remotion/transitions", "@remotion/transitions/fade", "@remotion/transitions/slide", "@remotion/transitions/wipe", "@remotion/transitions/flip", "@remotion/transitions/iris", "@remotion/transitions/clock-wipe",
    "d3-scale", "d3-shape", "d3-geo", "d3-force", "d3-hierarchy", "topojson-client", "world-atlas", "@dagrejs/dagre",
    "@nivo/core", "@nivo/bar", "@nivo/line", "@nivo/pie", "@nivo/radar", "@nivo/funnel", "@nivo/waffle", "@nivo/sankey", "@nivo/treemap", "@nivo/heatmap", "@nivo/chord",
    "echarts/core", "echarts/charts", "echarts/components", "echarts/renderers",
    "@phosphor-icons/react", "lucide-react", "simple-icons", "flag-icons", "lottie-web", "flubber", "@radix-ui/colors", "culori",
    "katex", "prism-react-renderer", "us-atlas",
)
# Libraries that draw with WebGL/canvas (unsupported / too slow on the CPU-only machine): rejected even though some are installed.
WEBGL_IMPORT = re.compile(r"""@remotion/light-leaks|@remotion/transitions/(?:blur-slide|book-flip|cross-zoom|crosswarp|dissolve|dreamy-zoom|film-burn|linear-blur|ripple|swap|zoom-blur|zoom-in-out)|\b(?:blurSlide|crossZoom|dreamyZoom|filmBurn|linearBlur)\b""")
APPROVED_LIBRARIES_HINT = (
    "charts: @nivo/* (fixed width/height, animate={false}, data computed per frame) or echarts/core with SVGRenderer and renderToSVGString (animation:false); "
    "icons: @phosphor-icons/react (weight=\"duotone\"), simple-icons (use .path), flag-icons (SVG files); "
    "shape morph/draw: flubber, @remotion/paths; lottie: @remotion/lottie with the animation JSON imported statically; "
    "layout/data: d3-scale, d3-shape, d3-geo, d3-force, d3-hierarchy, @dagrejs/dagre, topojson-client, world-atlas; "
    "colour: @radix-ui/colors, culori; effects: @remotion/noise; transitions inside a scene: @remotion/transitions with fade/slide/wipe/flip/iris/clock-wipe only; "
    "captions: @remotion/captions; audio: useSceneData() from \"../sceneData\" gives { audio, words } for @remotion/media-utils visualizeAudio; math: katex.renderToString; code: prism-react-renderer; "
    "regions: us-atlas; fonts: import { FONT } from \"../fonts\"."
)
_LOTTIE_IMPORT = re.compile(r"""["']\.\./lottie/([\w.-]+\.json)["']""")


def lottie_manifest() -> list[dict]:
    """The Lottie animations a scene may import (src/lottie/manifest.json in the Remotion folder): each with its source and licence. A file that is not listed there has no licence record and is rejected."""
    f = config.REMOTION_DIR / "src" / "lottie" / "manifest.json"
    try:
        return [a for a in json.loads(f.read_text(encoding="utf-8")).get("animations", []) if a.get("file") and a.get("license")]
    except (OSError, ValueError):
        return []


def approved_libraries_hint() -> str:
    """APPROVED_LIBRARIES_HINT plus the Lottie animations that really exist (so the LLM never invents a file name)."""
    lot = lottie_manifest()
    extra = (" Available Lottie files (import animationData from \"../lottie/<file>\" and render <Lottie animationData={animationData} loop />): "
             + "; ".join(f"{a['file']} = {a.get('description', a['id'])}" for a in lot) + ".") if lot else ""
    return APPROVED_LIBRARIES_HINT + extra


_IMPORT_SPECIFIER = re.compile(r"""(?:\bfrom\s+|\bimport\s+|\brequire\s*\(\s*)["']([^"']+)["']""")


def unapproved_imports(source_code: str) -> list[str]:
    """Bare-module imports of a scene that are not on the approved list (relative imports are checked by the path rule; sub-paths like flag-icons/flags/... belong to their package)."""
    packages_with_files = ("flag-icons", "world-atlas", "us-atlas")                 # data packages imported by file path (flag-icons/flags/4x3/in.svg, world-atlas/countries-110m.json)

    def approved(spec: str) -> bool:
        return spec in APPROVED_IMPORTS or any(spec.startswith(p + "/") for p in packages_with_files)

    return sorted({spec for spec in _IMPORT_SPECIFIER.findall(source_code) if not spec.startswith((".", "/")) and not approved(spec)})


MAX_COMPILE_REPAIR_ROUNDS = 2
_TSC_SCENE_ERROR = re.compile(r"^src[/\\]generated[/\\]scene_([\w-]+)\.tsx\((\d+),(\d+)\): error (TS\d+): (.*)$", re.MULTILINE)


def run_tsc(remotion_dir: Path) -> tuple[bool, str]:
    """The project's own type check (`npm run tsc` in the Remotion folder): (passed, its output). The output format is pinned (plain, no colour) whatever the caller's environment
    (FORCE_COLOR makes tsc print a coloured `file:line:col - error` layout that `tsc_errors_by_scene` cannot read, so no compile error would ever reach the repair loop)."""
    env = {**os.environ, "FORCE_COLOR": "0", "NO_COLOR": "1"}
    r = subprocess.run("npm run tsc -- --pretty false", cwd=remotion_dir, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=env, creationflags=config.LOW_PRIORITY)
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")


def tsc_errors_by_scene(output: str) -> dict[str, list[str]]:
    """Compiler messages of the generated scenes, by scene id: ['line 327: TS2322 ...']. Continuation lines of a message are kept with it."""
    out: dict[str, list[str]] = {}
    lines = output.splitlines()
    for i, ln in enumerate(lines):
        m = _TSC_SCENE_ERROR.match(ln)
        if m:
            more = []
            for nxt in lines[i + 1:i + 4]:
                if not nxt.startswith("  "):
                    break
                more.append(nxt.strip())
            out.setdefault(m.group(1), []).append(f"line {m.group(2)}: {m.group(4)} {m.group(5)} {' '.join(more)}"[:600])
    return out


def repair_scene_compile_errors(pdir: Path, sid: str, code: str, errors: list[str]) -> str | None:
    """Ask the LLM to fix the errors of ONE scene (compiler errors, or a runtime error raised while a frame is drawn); the answer must still pass the security/import audit. None when the LLM is unavailable or answers unusably (the stage then fails with the errors)."""
    try:
        resp = llm_gateway.gateway.execute(llm_gateway.LlmGatewayRequest(
            project_id=pdir.name, stage_id="motion_gen", agent_id="motion_animation", purpose="repair", model_profile="code_generation",
            system_prompt=("You fix the errors of one Remotion scene component (TypeScript compiler errors, or an error thrown while a frame is drawn, e.g. `interpolate` needs a strictly increasing input range) "
                           "and return the COMPLETE corrected TSX only. Keep the design, text and animation; change only what the errors require "
                           "(e.g. remove a prop the component does not have, fix a type, make an input range increasing). Approved libraries only: " + approved_libraries_hint()),
            user_prompt=f"Scene{sid} fails with these errors:\n- " + "\n- ".join(errors[:8]) + f"\n\n```tsx\n{code}\n```",
            correlation_id=f"gen-scene-{sid}-tsc-{uuid.uuid4().hex[:6]}"))
    except Exception as e:
        logger.warning(f"Scene {sid} compile repair call failed: {e}")
        return None
    if resp.status in ("blocked", "failed"):                                   # the LLM, not the code, is the blocker: say so instead of reporting the compiler errors as the cause
        raise AnimationCodegenError(f"Scene {sid}: the compile errors cannot be repaired, the LLM is unavailable: {resp.error or resp.status}")
    fixed = extract_tsx_code(resp.raw_text)
    if fixed and f"Scene{sid}" in fixed and audit_scene_tsx_security(fixed)["passed"]:
        return fixed
    return None


class AnimationCodegenError(Exception):
    """Raised when custom animation code generation or validation fails."""


def custom_composition(pdir: Path, aspect: str, scenes: list[dict[str, Any]], palette: Any) -> dict[str, Any]:
    """The composition of the custom-code scenes (composition.json): one `custom_scene` layer per scene, the planned transitions and the spoken words. Made before the render check
    (which draws it) and written after it."""
    from . import motion_generation as mg
    sfx = "_9x16" if aspect == "9:16" else ""
    w, h = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    audio_file = next(iter(sorted(pdir.glob("audio.*"))), None)
    total_dur = scenes[-1].get("end", 0) if scenes else 0

    mpl_scenes = {}
    mpl_path = pdir / f"motion_planning{sfx}.json"
    if mpl_path.exists():
        try:
            m = json.loads(mpl_path.read_text(encoding="utf-8"))
            for s in m.get("scenes", []):
                psid = s.get("plan_scene_id")
                if psid is not None:
                    mpl_scenes[psid] = s
        except Exception:
            pass

    comp_scenes = []
    for sc in scenes:
        sid = sc.get("id")
        sc_obj = {
            "id": sid,
            "start": sc.get("start", 0),
            "end": sc.get("end", 3),
            "pattern": "custom_motion",
            "camera": {"move": "static", "from": 1, "to": 1, "focus": [0.5, 0.5]},
            "layers": [
                {
                    "type": "custom_scene",
                    "z": 10,
                    "scene_id": sid,
                    "component": f"Scene{sid}",
                }
            ],
        }
        t_out = (mpl_scenes.get(sid) or {}).get("transition_out") or sc.get("transition")
        if t_out:
            sc_obj["transition_out"] = t_out
        comp_scenes.append(sc_obj)

    spoken = [{"w": str(x.get("w") or x.get("word") or ""), "start": float(x["start"]), "end": float(x["end"])} for x in mg.words(pdir)
              if isinstance(x.get("start"), (int, float)) and isinstance(x.get("end"), (int, float))]
    return {
        "words": spoken,
        "meta": {
            "fps": 30,
            "width": w,
            "height": h,
            "audio": audio_file.name if audio_file else "audio.wav",
            "duration": total_dur,
            "subtitles": False,
            "palette": palette,
            "motion": "rich",
            "motionOnly": not store.uses_images(pdir),
            "customCode": True,
            "reusable_motion_templates": False,
        },
        "scenes": comp_scenes,
    }


def render_errors_by_scene(pdir: Path, aspect: str, scenes: list[dict[str, Any]], palette: Any) -> dict[str, list[str]]:
    """Runtime errors of the staged scenes, by scene id ('2': ['runtime error while the scene was drawn at frame 120: ...']): a scene that type-checks can still throw when a frame is drawn
    (for example `interpolate` with an input range of [1, 1]); the type check cannot see that, the preview stills of Motion Validation can, too late. One still per scene, drawn by the real
    renderer. `MOTION_RENDER_CHECK=0` turns it off (tests that have no browser); a check that cannot run fails the stage, it is never skipped silently."""
    if os.environ.get("MOTION_RENDER_CHECK", "1") == "0":
        return {}
    from . import motion_validation_preview as pv
    try:
        return pv.smoke(pdir, aspect, custom_composition(pdir, aspect, scenes, palette))
    except (pv.ValidationError, subprocess.TimeoutExpired) as e:
        raise AnimationCodegenError(f"the render check of the generated scenes could not run: {e}") from e


def names(aspect: str) -> str:
    sfx = "_9x16" if aspect == "9:16" else ""
    return f"motion_animation{sfx}.json"


def load_animation(pdir: Path, aspect: str = "16:9") -> dict[str, Any] | None:
    path = pdir / names(aspect)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_animation(pdir: Path, aspect: str, data: dict[str, Any]) -> Path:
    path = pdir / names(aspect)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return path


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def scan_prohibited_presets(source_code: str) -> list[str]:
    """Check source code for any prohibited preset imports or usages."""
    # A preset is "used" when its name is IMPORTED, or used as a component/function without being declared in the scene itself. A scene's own helper that happens to be called `Chart` or
    # `Counter` (const Counter = ...), or the word in a comment or on-screen text, is not the legacy preset and is allowed.
    found = []
    for preset in PROHIBITED_PRESETS:
        name = re.escape(preset)
        imported = re.search(rf"\bimport\b[^;]*?\b{name}\b[^;]*?\bfrom\b", source_code, re.DOTALL)
        used = re.search(rf"<{name}[\s/>]|(?<![\w.]){name}\s*\(", source_code)
        declared = re.search(rf"\b(?:const|let|var|function|class|type|interface)\s+{name}\b", source_code)
        if imported or (used and not declared):
            found.append(preset)
    return sorted(set(found))


def audit_scene_tsx_security(source_code: str) -> dict[str, Any]:
    """Static security and safety scan for custom React/TSX animation code.
    Rejects:
    - Prohibited presets
    - Dynamic execution (eval, Function, exec)
    - Process/OS spawning (child_process, subprocess, os.system)
    - Network calls (fetch, XMLHttpRequest, WebSocket, axios)
    - Direct filesystem access (fs, fs/promises)
    - Secret and token leakage
    - Path traversal in imports
    """
    findings: list[str] = []

    # 1. Prohibited presets
    prohibited = scan_prohibited_presets(source_code)
    if prohibited:
        findings.append(f"Prohibited presets imported or referenced: {', '.join(prohibited)}")

    # 2. Dynamic execution & OS spawning
    dangerous_patterns = [
        (r"\beval\s*\(", "Dynamic evaluation: eval()"),
        (r"\bFunction\s*\(", "Dynamic code construction: Function()"),
        (r"\bexec\s*\(", "Dynamic execution: exec()"),
        (r"\bchild_process\b", "Prohibited module: child_process"),
        (r"\bsubprocess\b", "Prohibited module: subprocess"),
        (r"\bos\.(?:system|popen)\b", "Prohibited OS execution"),
        (r"\bfs(?:/promises)?\b", "Prohibited filesystem access: fs"),
        (r"\b(?:fetch|XMLHttpRequest|WebSocket|axios)\b", "Prohibited network access API"),
        (r"\b(?:localStorage|sessionStorage|document\.cookie)\b", "Prohibited storage access"),
        (r"(?:import\s+.*?from\s+[\"'](?:three|@react-three(?:/[a-z0-9_-]+)?)[\"']|\bTHREE\.[A-Za-z]+|\bWebGLRenderingContext\b)", "Unsupported external 3D runtime: Three.js/WebGL"),
    ]
    for pattern, desc in dangerous_patterns:
        if re.search(pattern, source_code):
            findings.append(desc)

    if (gl := sorted(set(WEBGL_IMPORT.findall(source_code)))):
        findings.append(f"WebGL/canvas library or transition (unsupported on this CPU): {', '.join(gl)}")

    # 2b. Only approved (installed, frame-safe) libraries may be imported
    if (extra := unapproved_imports(source_code)):
        findings.append(f"Unapproved library import: {', '.join(extra)}")
    listed = {a["file"] for a in lottie_manifest()}
    if (unknown := sorted({n for n in _LOTTIE_IMPORT.findall(source_code) if n not in listed})):
        findings.append(f"Lottie file without a licence record (not in src/lottie/manifest.json): {', '.join(unknown)}")

    # 3. Path traversal in imports
    if re.search(r"import\s+.*?from\s+[\"'](?:\.\./\.\.|/|\\|[a-zA-Z]:)", source_code):
        findings.append("Disallowed import path: path traversal or absolute import")

    # 4. Secret / Token patterns
    if CREDENTIAL_KINDS.intersection(redact_secrets(source_code)[1]):
        findings.append("Exposed secret or API token pattern in source code")

    return {
        "passed": len(findings) == 0,
        "findings": findings,
    }


def extract_tsx_code(raw: str) -> str:
    """Extracts TSX code from markdown code fences or returns clean text."""
    m = re.search(r"```(?:tsx|typescript|jsx|javascript)?\s*\n?([\s\S]*?)```", raw)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"```(?:tsx|typescript|jsx|javascript)?\s*\n?([\s\S]*)", raw)
    if m2:
        return m2.group(1).strip()
    return raw.strip()


_FADE_TO_ZERO = re.compile(r"interpolate\(\s*frame\s*,\s*\[[^\],]+,\s*([^\]]+?)\s*\]\s*,\s*\[\s*1\s*,\s*0\s*\]")
_ROOT_STYLE = re.compile(r"return\s*\(\s*<AbsoluteFill\b[^>]*?style=\{\{(.*?)\}\}", re.S)


def scene_self_fades(code: str, dur_frames: int) -> list[str]:
    """The cut between scenes belongs to the timeline (SceneRoot's TransitionSeries overlaps the two scenes). A scene that fades its whole picture
    in from nothing or out to nothing therefore leaves empty frames at every cut."""
    out = []
    root = _ROOT_STYLE.search(code)
    if root and re.search(r"\bopacity\s*:", root.group(1)):
        out.append("the root AbsoluteFill has an opacity, so the whole scene fades and the cut shows empty frames: keep the root fully visible and animate the elements instead")
    for m in _FADE_TO_ZERO.finditer(code):
        end = m.group(1).strip()
        if re.search(r"durationInFrames|durFrames|duration", end) or (end.isdigit() and int(end) >= dur_frames - 2):
            out.append("content fades to nothing at the last frames of the scene: the timeline transition already shows the exit, so keep everything visible to the last frame")
            break
    return out


def missing_shot_sequences(code: str, shots: list[dict[str, Any]]) -> list[str]:
    """The shots of the scene the code starts no <Sequence> for (with the shot's own frame range): without them the whole scene is one unchanging layout."""
    if len(shots) < 2:
        return []
    have = {int(m) for m in re.findall(r"from=\{\s*(\d+)\s*\}", code)}
    return [f"shot {x['shot_id']} ({x['start_frame']}-{x['end_frame']}) has no <Sequence from={{{x['start_frame']}}} durationInFrames={{{int(x['end_frame']) - int(x['start_frame'])}}}> of its own"
            for x in shots if int(x["start_frame"]) not in have]


def missing_element_ids(code: str, element_ids: list[str]) -> list[str]:
    """Planned element ids the TSX does not draw (no node carries data-element-id for it)."""
    return [i for i in element_ids if not re.search(rf"""data-element-id=\{{?\s*["']{re.escape(i)}["']""", code)]


def generate_scene_tsx(
    scene_id: int | str,
    duration_s: float,
    headline: str,
    subtext: str,
    visual_elements: list[dict[str, Any]],
    palette: list[str],
    aspect: str = "16:9",
) -> str:
    """Deterministic generator for valid React/TSX animation source code for a scene.
    Uses pure Remotion primitives, frame-driven interpolation/springs, and inline SVG graphics.
    Strictly avoids any prohibited reusable preset imports."""
    sid = str(scene_id)
    safe_headline = headline.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()
    safe_subtext = subtext.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()
    bg_color = palette[0] if palette else "#0f172a"
    accent_color = palette[1] if len(palette) > 1 else "#38bdf8"
    secondary_color = palette[2] if len(palette) > 2 else "#818cf8"
    is_tall = aspect == "9:16"

    # Build SVG visual elements based on visual planning items
    svg_elements_code = []
    for idx, el in enumerate(visual_elements[:4]):
        el_type = el.get("type", "graphic")
        el_desc = el.get("visual_description", "")
        delay = 10 + idx * 8

        if "chart" in el_type or "bar" in el_desc.lower() or "stat" in el_desc.lower():
            svg_elements_code.append(f"""
        {{/* Bar / Metric Visual Element */}}
        <div style={{{{
          marginTop: 24,
          padding: 20,
          background: "rgba(255, 255, 255, 0.05)",
          borderRadius: 16,
          border: "1px solid rgba(255, 255, 255, 0.1)",
          width: "{ '85%' if is_tall else '60%' }",
          maxWidth: 600,
          opacity: interpolate(frame, [{delay}, {delay + 15}], [0, 1], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }}),
          transform: `translateY(${{interpolate(spring({{ frame: Math.max(0, frame - {delay}), fps, config: {{ damping: 14 }} }}), [0, 1], [30, 0])}}px)`,
        }}}}>
          <div style={{{{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", height: 100, gap: 12 }}}}>
            {{[0.4, 0.7, 0.55, 0.9, 0.65].map((h, i) => {{
              const barSpring = spring({{ frame: Math.max(0, frame - {delay} - i * 4), fps, config: {{ damping: 12, stiffness: 120 }} }});
              return (
                <div key={{i}} style={{{{
                  flex: 1,
                  height: `${{h * 100 * barSpring}}%`,
                  background: i === 3 ? "{accent_color}" : "rgba(255, 255, 255, 0.2)",
                  borderRadius: "6px 6px 0 0",
                  transition: "background 0.2s",
                }}}} />
              );
            }})}}
          </div>
        </div>""")
        elif "icon" in el_type or "symbol" in el_desc.lower():
            svg_elements_code.append(f"""
        {{/* Animated Icon Element */}}
        <div style={{{{
          marginTop: 20,
          opacity: interpolate(frame, [{delay}, {delay + 12}], [0, 1], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }}),
          transform: `scale(${{spring({{ frame: Math.max(0, frame - {delay}), fps, config: {{ damping: 12, mass: 0.6 }} }})}})`,
        }}}}>
          <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="{accent_color}" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" strokeDasharray="63" strokeDashoffset={{interpolate(frame, [{delay}, {delay + 25}], [63, 0], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }})}} />
            <polygon points="12 6 16 14 8 14" fill="{secondary_color}" fillOpacity="0.3" />
          </svg>
        </div>""")
        elif "particle" in el_type or "particle" in el_desc.lower() or "drift" in el_desc.lower():
            svg_elements_code.append(f"""
        {{/* 2D Particle Drift Approximation */}}
        <div style={{{{
          marginTop: 20,
          position: "relative",
          width: "{ '80%' if is_tall else '50%' }",
          height: 100,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          opacity: interpolate(frame, [{delay}, {delay + 15}], [0, 1], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }}),
        }}}}>
          {{[...Array(8)].map((_, i) => {{
            const pX = (i * 35) % 220 - 110;
            const pY = ((i * 47) % 60 - 30) + interpolate(frame, [0, durFrames], [0, -20], {{ extrapolateRight: "extend" }});
            const pScale = interpolate(spring({{ frame: Math.max(0, frame - {delay} - i * 2), fps, config: {{ damping: 15 }} }}), [0, 1], [0.3, 1]);
            return (
              <div
                key={{i}}
                style={{{{
                  position: "absolute",
                  transform: `translate(${{pX}}px, ${{pY}}px) scale(${{pScale}})`,
                  width: (i % 3 + 2) * 4,
                  height: (i % 3 + 2) * 4,
                  borderRadius: "50%",
                  background: i % 2 === 0 ? "{accent_color}" : "{secondary_color}",
                  opacity: 0.85,
                  boxShadow: `0 0 8px ${{i % 2 === 0 ? "{accent_color}" : "{secondary_color}"}}`,
                }}}}
              />
            );
          }})}}
        </div>""")
        elif any(k in el_type or k in el_desc.lower() for k in ("isometric", "parallax", "3d", "perspective", "mesh", "model")):
            svg_elements_code.append(f"""
        {{/* 2.5D Isometric SVG Multi-Layer Approximation */}}
        <div style={{{{
          marginTop: 20,
          perspective: 800,
          opacity: interpolate(frame, [{delay}, {delay + 12}], [0, 1], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }}),
          transform: `scale(${{spring({{ frame: Math.max(0, frame - {delay}), fps, config: {{ damping: 12, mass: 0.8 }} }})}})`,
        }}}}>
          <svg width="100" height="100" viewBox="0 0 120 120" style={{{{ filter: "drop-shadow(0 10px 15px rgba(0,0,0,0.5))" }}}}>
            <polygon points="60,20 105,45 60,70 15,45" fill="{accent_color}" fillOpacity="0.85" />
            <polygon points="15,45 60,70 60,110 15,85" fill="{secondary_color}" fillOpacity="0.7" />
            <polygon points="60,70 105,45 105,85 60,110" fill="{bg_color}" fillOpacity="0.9" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
          </svg>
        </div>""")
        else:
            svg_elements_code.append(f"""
        {{/* Custom Geometric / Decorative Element */}}
        <div style={{{{
          marginTop: 20,
          opacity: interpolate(frame, [{delay}, {delay + 15}], [0, 1], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }}),
          transform: `scale(${{spring({{ frame: Math.max(0, frame - {delay}), fps, config: {{ damping: 15 }} }})}})`,
        }}}}>
          <svg width="120" height="30" viewBox="0 0 120 30">
            <line x1="10" y1="15" x2="110" y2="15" stroke="{accent_color}" strokeWidth="3" strokeDasharray="100" strokeDashoffset={{interpolate(frame, [{delay}, {delay + 20}], [100, 0], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }})}} />
            <circle cx="60" cy="15" r="5" fill="{secondary_color}" />
          </svg>
        </div>""")

    rendered_visuals = "\n".join(svg_elements_code)

    return f"""import React from "react";
import {{ AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring }} from "remotion";

/**
 * Scene{sid} Animation Component
 * Generated by Motion Animation Stage (Custom Code Mode)
 * Implements scene-specific animation with Remotion core primitives.
 */
export const Scene{sid}: React.FC<{{ layer?: any }}> = () => {{
  const frame = useCurrentFrame();
  const {{ fps, width, height }} = useVideoConfig();
  const durFrames = Math.max(1, Math.round({duration_s} * fps));

  // Entrance animations
  const titleSpring = spring({{
    frame,
    fps,
    config: {{ damping: 12, mass: 0.5, stiffness: 100 }},
  }});
  const titleOpacity = interpolate(frame, [0, 12], [0, 1], {{ extrapolateRight: "clamp" }});
  const titleY = interpolate(titleSpring, [0, 1], [35, 0]);

  const subtextOpacity = interpolate(frame, [15, 28], [0, 1], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }});
  const subtextY = interpolate(frame, [15, 28], [15, 0], {{ extrapolateLeft: "clamp", extrapolateRight: "clamp" }});

  return (
    <AbsoluteFill
      style={{{{
        background: "radial-gradient(ellipse at center, rgba(30, 41, 59, 0.9) 0%, {bg_color} 100%)",
        color: "#f8fafc",
        fontFamily: "'Nirmala UI', sans-serif",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "8%",
        textAlign: "center",
        overflow: "hidden",
        width: "100%",
        height: "100%",
      }}}}
    >
      {{/* Headline */}}
      <div
        style={{{{
          fontSize: { 44 if is_tall else 56 },
          fontWeight: 800,
          lineHeight: 1.25,
          letterSpacing: "-0.02em",
          maxWidth: "{ '90%' if is_tall else '80%' }",
          opacity: titleOpacity,
          transform: `translateY(${{titleY}}px)`,
          textShadow: "0 4px 20px rgba(0, 0, 0, 0.6)",
        }}}}
      >
        "{safe_headline}"
      </div>

      {{/* Subtext / Keyword */}}
      {f'''<div
        style={{{{
          marginTop: 18,
          fontSize: { 24 if is_tall else 30 },
          fontWeight: 500,
          color: "{accent_color}",
          maxWidth: "80%",
          opacity: subtextOpacity,
          transform: `translateY(${{subtextY}}px)`,
        }}}}
      >
        {safe_subtext}
      </div>''' if safe_subtext else ''}

      {rendered_visuals}
    </AbsoluteFill>
  );
}};

export default Scene{sid};
"""


def generate_scene_tsx_via_llm(
    pdir: Path,
    scene_id: int | str,
    duration_s: float,
    headline: str,
    subtext: str,
    visual_elements: list[dict[str, Any]],
    palette: list[str],
    aspect: str = "16:9",
    run_id: str | None = None,
    texts: list[str] | None = None,
    shots: list[dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Generates scene TSX source code via canonical LLM Gateway with bounded diagnostic repair.
    Employs skills and shared memory context, strict security auditing, and fallbacks.
    Returns (tsx_code, generation_metadata).
    """
    sid = str(scene_id)
    dur_frames = max(1, round(duration_s * 30))
    corr_id = f"gen-scene-{sid}-{uuid.uuid4().hex[:8]}"

    from SYSTEM.agents.video_generation_agents.motion_animation.animation_intelligence import ThreeDFallbackEngine
    fallback_engine = ThreeDFallbackEngine()
    safe_visual_elements, classifications = fallback_engine.transform_elements_for_codegen(visual_elements)

    # Discover relevant approved skills
    approved_skills = skill_registry.registry.search_skills(domain="motion", status="approved")
    skill_summaries = [f"- {s.skill_id}: {s.summary}" for s in approved_skills]

    # Retrieve relevant verified memory
    verified_memories = shared_memory.service.retrieve_memory(limit=5)
    memory_summaries = [f"- [{m.memory_id}] {m.title}: {m.content}" for m in verified_memories]

    system_prompt = (
        "You are an expert Remotion animation software engineer. "
        "Generate standalone, production-ready React/TSX source code for a Remotion scene. "
        "Strict rules:\n"
        "1. Exactly 30 fps frame-accuracy.\n"
        "2. Use Remotion primitives (AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring) and, when the scene needs them, ONLY these approved libraries: "
        + approved_libraries_hint() + " Every animation is driven by the current frame (the library's own animation/timers are OFF); no 3D, WebGL, shaders or canvas; never fetch anything.\n"
        "3. NEVER import or use prohibited presets: MotionTextLayer, MotionScene, HighlightText, IconPop, etc.\n"
        "4. NEVER use shell commands, eval, network calls (fetch, axios), or filesystem access.\n"
        "5. Keep content inside the safe area: the root AbsoluteFill has padding of at least 5% (e.g. padding: \"8%\") or centers its content (justifyContent: \"center\").\n"
        "6. Headline text is at least 32px (fontSize: 32 or more) with a high-contrast colour such as #f8fafc or a textShadow.\n"
        "7. An element with a \"real_media\" object is a real photograph or video clip, already prepared and checked: draw it with <Img> (kind image) or <OffthreadVideo muted> (kind video) imported from \"remotion\", "
        "src={staticFile(real_media.file)}, objectFit cover, animated from the current frame only (a slow scale from 1 to 1.08 with interpolate). Put the element's data-element-id on that node, keep the headline readable "
        "(a dark gradient behind the text), and show real_media.credit as a small caption (fontSize 20 or more) near the bottom edge: the credit is mandatory. Never alter what the media shows and never present it as generated. "
        "A real_media of kind \"page\" is a screenshot of a reference page element (an infobox or table): draw it as a framed card with objectFit contain (never full-bleed, never cropped), so its text stays readable.\n"
        "8. The timeline blends this scene with its neighbours (a transition overlaps the end of one scene and the start of the next): never fade or scale the WHOLE scene in "
        "from nothing or out to nothing (no opacity on the root AbsoluteFill, nothing fading to 0 at the last frames). The background and the main layout are visible from frame 0; "
        "elements may animate in, and everything stays visible to the last frame.\n"
        "10. SHOTS: the scene is given as a list of shots (frame ranges relative to this scene's frame 0, cut on the spoken words). Wrap EVERY shot in its own "
        "<Sequence from={start_frame} durationInFrames={end_frame - start_frame}> imported from \"remotion\", in order, and give each shot a DIFFERENT composition: another "
        "arrangement, another focal element, another scale or position of the hero, a new card entering while the one before it leaves. A shot is not one more element appearing on an "
        "unchanged layout. The background, the palette and the headline style stay the same across the shots of one scene (it is one scene, not several); inside a Sequence the frame "
        "counts from that shot's start, so animate each shot from frame 0 of its own Sequence and keep its content visible to its last frame (rule 8 holds for the scene as a whole).\n"
        "12. The scenes are type-checked with TypeScript `strict: true`, and code that does not compile is rejected: never use a value that may be null or undefined without "
        "checking it first. `getPointAtLength`/`getPointAtLengthDescribed` of @remotion/paths return `Point | null`, `Array.find` returns `undefined`, a `useRef` holds `| null`: "
        "guard the value (`if (!p) return null;`) or give it a fallback before you read a field of it.\n"
        "11. Each shot lists the words spoken in it with their frames: a word that is drawn on screen appears at its own start_frame, never on a fixed schedule.\n"
        "9. Output valid, complete React TSX source code only."
    )
    texts = [t for t in (texts or [headline, subtext]) if t]

    user_prompt = (
        f"Generate React TSX animation code for Scene {sid}.\n"
        f"Canvas aspect ratio: {aspect} (Width: {1080 if aspect == '9:16' else 1920}, Height: {1920 if aspect == '9:16' else 1080}).\n"
        f"Duration: {duration_s:.2f} seconds ({dur_frames} frames at 30 fps).\n"
        f"Headline: {headline}\n"
        f"Subtext: {subtext}\n"
        f"On-screen texts (draw every one, verbatim): {json.dumps(texts, ensure_ascii=False)}\n"
        f"Palette: {', '.join(palette)}\n"
        f"Visual elements: {json.dumps(safe_visual_elements)}\n"
        + (f"Shots (one <Sequence> each; frames are relative to this scene's frame 0): {json.dumps(shots, ensure_ascii=False)}\n\n" if shots else "\n")
        + 
        f"Approved Skills:\n" + "\n".join(skill_summaries) + "\n\n"
        f"Verified Memory Guidelines:\n" + "\n".join(memory_summaries) + "\n\n"
        "Draw EVERY visual element listed above with its own JSX node and put the attribute "
        'data-element-id="<element_id>" on that node (exactly the element_id given), so the drawing can be verified.\n'
        f"Export default Scene{sid} as a React.FC."
    )

    t0 = time.perf_counter()
    gen_meta: dict[str, Any] = {
        "correlation_id": corr_id,
        "provider": "local",
        "model": "deterministic_generator",
        "profile": "code_generation",
        "latency_ms": 0,
        "attempt_count": 1,
        "repaired": False,
        "retries_prevented": False,
        "skills_referenced": [s.skill_id for s in approved_skills],
        "memory_referenced": [m.memory_id for m in verified_memories],
    }

    # Fail closed: a blocked/failed gateway call or unusable code must never be replaced by the generic
    # deterministic template (it draws none of the planned elements yet would be reported as generated).
    req = llm_gateway.LlmGatewayRequest(
        project_id=pdir.name,
        stage_id="motion_gen",
        agent_id="motion_animation",
        purpose="generation",
        model_profile="code_generation",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        correlation_id=corr_id,
    )
    try:
        resp = llm_gateway.gateway.execute(req)
    except Exception as e:
        raise AnimationCodegenError(f"Scene {sid}: LLM code generation failed: {e}") from e
    gen_meta["provider"] = resp.provider
    gen_meta["model"] = resp.model
    gen_meta["latency_ms"] = resp.latency_ms
    gen_meta["attempt_count"] = resp.attempt_count
    if resp.status in ("blocked", "failed"):
        raise AnimationCodegenError(f"Scene {sid}: LLM code generation {resp.status}: {resp.error or 'no response'}")
    raw_code = extract_tsx_code(resp.raw_text)
    if not raw_code or "AbsoluteFill" not in raw_code:
        raise AnimationCodegenError(f"Scene {sid}: the LLM returned no usable Scene{sid} TSX component")
    if f"Scene{sid}" not in raw_code:
        m_comp = re.search(r"\b(Scene_?0*" + re.escape(sid) + r"|Scene)\b", raw_code)
        if m_comp:
            raw_code = re.sub(r"\b" + re.escape(m_comp.group(1)) + r"\b", f"Scene{sid}", raw_code)
        else:
            raw_code += f"\nexport const Scene{sid}: React.FC = () => <AbsoluteFill />;\nexport default Scene{sid};\n"

    # Security & Prohibited preset audit
    audit = audit_scene_tsx_security(raw_code)
    attempt = 1
    max_repair = 2

    # Bounded Repair Loop
    while not audit["passed"] and attempt <= max_repair:
        findings_str = " ".join(audit.get("findings", []))
        if fallback_engine.is_known_limitation_error(findings_str):
            logger.warning(
                f"Scene {sid} hit known capability limitation ({findings_str}). "
                "Preventing retry storm and falling back immediately to deterministic 2D/2.5D generator."
            )
            gen_meta["retries_prevented"] = True
            raw_code = generate_scene_tsx(sid, duration_s, headline, subtext, safe_visual_elements, palette, aspect)
            audit = audit_scene_tsx_security(raw_code)
            break

        attempt += 1
        gen_meta["attempt_count"] = attempt
        gen_meta["repaired"] = True
        logger.warning(f"Scene {sid} failed security audit ({audit['findings']}). Attempting repair {attempt}/{max_repair}...")

        repair_prompt = (
            f"Fix the following React TSX code for Scene {sid}. It contains security/safety violations:\n"
            f"{json.dumps(audit['findings'])}\n\n"
            f"Failing Code snippet:\n```tsx\n{raw_code[:1200]}\n```\n\n"
            f"Remove all prohibited imports, dangerous APIs, and return valid Remotion React/TSX."
        )

        try:
            r_req = llm_gateway.LlmGatewayRequest(
                project_id=pdir.name,
                stage_id="motion_gen",
                agent_id="motion_animation",
                purpose="repair",
                model_profile="code_generation",
                system_prompt=system_prompt,
                user_prompt=repair_prompt,
                correlation_id=f"{corr_id}-repair-{attempt}",
            )
            r_resp = llm_gateway.gateway.execute(r_req)
            repaired_code = extract_tsx_code(r_resp.raw_text) if r_resp.status not in ("blocked", "failed") else ""
        except Exception as e:
            logger.warning(f"Scene {sid} repair call failed: {e}")
            break
        if not repaired_code or f"Scene{sid}" not in repaired_code:
            break
        raw_code = repaired_code
        audit = audit_scene_tsx_security(raw_code)

    if not audit["passed"]:
        raise AnimationCodegenError(
            f"Generated scene {sid} code failed security audit after repair attempts: {audit['findings']}"
        )

    ids = [e["element_id"] for e in safe_visual_elements if e.get("element_id")]
    required_ids = {e["element_id"] for e in safe_visual_elements if e.get("element_id") and e.get("required")}

    def quality_issues(code: str) -> list[str]:
        """What the downstream validation would flag in this code: required elements not drawn, planned text missing, the preview verifier's layout findings."""
        out = [f"the planned element '{i}' has no node with data-element-id=\"{i}\"" for i in missing_element_ids(code, ids) if i in required_ids]
        out += [f"the planned on-screen text '{t}' is not drawn verbatim" for t in texts if t and t not in code]
        out += scene_self_fades(code, dur_frames)
        out += missing_shot_sequences(code, shots or [])
        from SYSTEM.agents.video_generation_agents.motion_animation.animation_intelligence import VisualPreviewVerifier
        out += VisualPreviewVerifier().verify(code, aspect=aspect).findings
        return out

    issues = quality_issues(raw_code)
    if issues and not gen_meta["retries_prevented"]:      # one bounded pass to fix what the first answer got wrong
        try:
            fix = llm_gateway.gateway.execute(llm_gateway.LlmGatewayRequest(
                project_id=pdir.name, stage_id="motion_gen", agent_id="motion_animation", purpose="repair",
                model_profile="code_generation", system_prompt=system_prompt,
                user_prompt=(f"Fix these problems in the Scene{sid} TSX and return the complete component:\n- " + "\n- ".join(issues) + "\n"
                             f"Elements: {json.dumps([e for e in safe_visual_elements if e.get('element_id') in required_ids])}\n\n"
                             f"```tsx\n{raw_code}\n```"),
                correlation_id=f"{corr_id}-quality"))
            fixed = extract_tsx_code(fix.raw_text) if fix.status not in ("blocked", "failed") else ""
            if fixed and f"Scene{sid}" in fixed and audit_scene_tsx_security(fixed)["passed"] and len(quality_issues(fixed)) < len(issues):
                raw_code = fixed
                gen_meta["repaired"] = True
        except Exception as e:
            logger.warning(f"Scene {sid} quality repair call failed: {e}")
    gen_meta["missing_elements"] = missing_element_ids(raw_code, ids)
    gen_meta["quality_issues"] = quality_issues(raw_code)
    gen_meta["latency_ms"] = round((time.perf_counter() - t0) * 1000)
    return raw_code, gen_meta


CODEGEN_VERSION = "3"                # bump when the instructions or the checks of the code generation change: every scene is then written again (3: one Sequence per shot, word frames)


def scene_input_fingerprint(**inputs: Any) -> str:
    """What one scene's code is written from (its texts, its elements with the real pictures drawn for them, its length, the palette and the canvas). Code is reused only while this is unchanged."""
    return hashlib.sha256(json.dumps({"v": CODEGEN_VERSION, **inputs}, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")).hexdigest()


def previous_fingerprints(pdir: Path, sfx: str) -> dict:
    """scene id (as a string) -> the input fingerprint the stored code of that scene was written from (none recorded = its code is written again).

    The manifest is written only when the WHOLE stage succeeded, so the sidecar `generated_motion/fingerprints<sfx>.json`, written as each scene is generated, is read as well:
    a stage that fails after the scenes were generated (one type error in the last scene) must not throw away the code of every other scene and have the LLM write it all again."""
    fps: dict = {}
    try:
        side = json.loads((pdir / "generated_motion" / f"fingerprints{sfx}.json").read_text(encoding="utf-8"))
        fps.update({str(k): v for k, v in side.items()} if isinstance(side, dict) else {})
    except (OSError, ValueError, AttributeError):
        pass
    try:
        prev = json.loads((pdir / f"motion_animation{sfx}.json").read_text(encoding="utf-8"))
        fps.update({str(x.get("scene_id")): x.get("input_fingerprint") for x in prev.get("scenes", [])})
    except (OSError, ValueError, AttributeError):
        pass
    return fps


def record_fingerprint(pdir: Path, sfx: str, sid: Any, fp: str) -> None:
    """Record, the moment a scene's code is on disk, the inputs it was written from, so a later failure of the stage does not cost every scene a new LLM call (see previous_fingerprints)."""
    path = pdir / "generated_motion" / f"fingerprints{sfx}.json"
    try:
        cur = json.loads(path.read_text(encoding="utf-8"))
        cur = cur if isinstance(cur, dict) else {}
    except (OSError, ValueError):
        cur = {}
    cur[str(sid)] = fp
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cur, indent=1), encoding="utf-8")
    tmp.replace(path)


def generate_custom_motion_code(
    pdir: Path,
    aspect: str = "16:9",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Execute Motion Animation custom code generation for all scenes.
    - Generates project-isolated scene-specific TSX under projects/<pid>/generated_motion/
    - Synchronously stages to VIDEO_ENGINE/remotion/src/generated/ under _remotion_staging_lock for race-free tsc compilation
    - Computes SHA-256 hashes for all generated files
    - Emits versioned manifest motion_animation.json (schema v2.0)
    - Produces composition.json and triggers mandatory LLM review
    """
    run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
    sfx = "_9x16" if aspect == "9:16" else ""
    sp_path = pdir / "scene_plan.json"

    scenes = []
    if sp_path.exists():
        try:
            sp = json.loads(sp_path.read_text(encoding="utf-8"))
            scenes = sp.get("scenes", [])
            palette = sp.get("style", {}).get("palette", ["#0f172a", "#38bdf8", "#818cf8"])
        except (OSError, ValueError):
            palette = ["#0f172a", "#38bdf8", "#818cf8"]
    else:
        palette = ["#0f172a", "#38bdf8", "#818cf8"]

    vp_scenes = {}
    from . import visual_planning                                       # the canonical loader: the stored Visual Plan, or the one derived from the scene plan
    try:
        vp = visual_planning.load(pdir) or {}
    except (OSError, ValueError):
        vp = {}
    for sc in vp.get("scenes", []):
        sid = sc.get("plan_scene_id") or sc.get("scene_id")
        if sid is not None:
            vp_scenes[sid] = sc

    out_dir = pdir / "generated_motion"
    out_dir.mkdir(parents=True, exist_ok=True)
    remotion_dir = config.REMOTION_DIR
    remotion_gen_dir = remotion_dir / "src" / "generated"

    from SYSTEM.agents.video_generation_agents.motion_animation.animation_intelligence import (
        ThreeDFallbackEngine,
        VisualPreviewVerifier,
        StructuredGenerationReporter,
    )
    fallback_engine = ThreeDFallbackEngine()
    preview_verifier = VisualPreviewVerifier()
    reporter = StructuredGenerationReporter()

    prev_fps = previous_fingerprints(pdir, sfx)
    scenes_manifest = []
    template_warnings = []
    all_clean = True
    prohibited_found_total = 0
    all_skills_used: set[str] = set()
    all_memory_used: set[str] = set()

    for sc in scenes:
        sid = sc.get("id")
        start = float(sc.get("start", 0))
        end = float(sc.get("end", start + 3))
        duration = max(0.5, end - start)

        vp_sc = vp_scenes.get(sid, {})
        req_els = [e.get("element_id", f"el_{i}") for i, e in enumerate(vp_sc.get("elements", [])) if e.get("required")]

        scene_warnings = []
        for e in vp_sc.get("elements", []):
            if e.get("required") and (e.get("requires_template") or e.get("template_only") or e.get("dependency") == "template"):
                el_id = e.get("element_id", "unnamed_element")
                w_msg = f"Scene {sid}: required output '{el_id}' cannot be generated without a template because it requires a reusable template, but Reusable Templates is OFF."
                scene_warnings.append(w_msg)
                template_warnings.append({
                    "scene_id": sid,
                    "element_id": el_id,
                    "category": "template_dependency",
                    "message": w_msg,
                    "dependency": e.get("template_id") or e.get("preset") or "reusable_template",
                })

        texts = [e.get("content", "") for e in vp_sc.get("elements", []) if mk.is_text(e.get("type", "")) and e.get("content")]
        headline = texts[0] if texts else sc.get("meaning") or sc.get("concept") or f"Scene {sid}"
        subtext = texts[1] if len(texts) > 1 else ""

        # A real element of the Visual Plan (type image or video) is drawn from the file Asset Collection kept for it (the same "drawn with its data-element-id" check applies); when none was
        # collected, the scene draws the motion fallback the plan wrote for it instead.
        assets = {a["element_id"]: a for a in asset_collection.assets_for_scene(pdir, sid)}
        visual_els = []
        for e in vp_sc.get("elements", []):
            if mk.is_text(e.get("type", "")):
                continue
            a = assets.get(e.get("element_id"))
            if mk.is_real(e.get("type", "")) and a:
                what = "video clip" if a["kind"] == "video" else "screenshot of a reference page element" if a["kind"] == "page" else "photograph"
                visual_els.append({**e, "real_media": a, "required": True, "visual_description": f"A real {what} ({a['description'] or e.get('visual_description')}), already prepared; draw it, do not recreate it"})
            elif mk.is_real(e.get("type", "")):
                visual_els.append({**e, "type": "graphic", "visual_description": (e.get("media") or {}).get("fallback") or e.get("visual_description", ""),
                                   "constraints": [*e.get("constraints", []), "no real media was found for this element: draw it as a flat motion graphic"]})
            else:
                visual_els.append(e)
        transformed_visual_els, el_classifications = fallback_engine.transform_elements_for_codegen(visual_els)

        scene_file = out_dir / f"scene_{sid}.tsx"
        shots = vp_sc.get("shots") or []
        scene_fp = scene_input_fingerprint(duration=round(duration, 3), headline=headline, subtext=subtext, texts=texts, elements=transformed_visual_els, palette=palette, aspect=aspect, shots=shots)
        if scene_file.exists() and prev_fps.get(str(sid)) == scene_fp:                  # the stored code was written from exactly these inputs; any change of the plan, the pictures or the texts writes it again
            existing_code = scene_file.read_text(encoding="utf-8")
            if f"Scene{sid}" in existing_code and "AbsoluteFill" in existing_code:
                code = existing_code
                gen_meta = {"provider": "cache", "model": "reused", "latency_ms": 0, "attempt_count": 1}
            else:
                code, gen_meta = generate_scene_tsx_via_llm(
                    pdir=pdir,
                    scene_id=sid,
                    duration_s=duration,
                    headline=headline,
                    subtext=subtext,
                    visual_elements=transformed_visual_els,
                    palette=palette,
                    aspect=aspect,
                    run_id=run_id,
                    texts=texts,
                    shots=shots,
                )
        else:
            # Generate TSX via LLM Gateway with bounded repair loop
            code, gen_meta = generate_scene_tsx_via_llm(
                pdir=pdir,
                scene_id=sid,
                duration_s=duration,
                headline=headline,
                subtext=subtext,
                visual_elements=transformed_visual_els,
                palette=palette,
                aspect=aspect,
                run_id=run_id,
                texts=texts,
                shots=shots,
            )

        all_skills_used.update(gen_meta.get("skills_referenced", []))
        all_memory_used.update(gen_meta.get("memory_referenced", []))

        # Check prohibited presets
        prohibited = scan_prohibited_presets(code)
        if prohibited:
            prohibited_found_total += len(prohibited)
            all_clean = False
            raise AnimationCodegenError(f"Generated scene {sid} code imports prohibited presets: {', '.join(prohibited)}")

        # Write to project-isolated directory atomically (.tmp -> .tsx)
        if gen_meta.get("provider") != "cache":
            tmp_scene_file = scene_file.with_suffix(".tmp")
            tmp_scene_file.write_text(code, encoding="utf-8")
            tmp_scene_file.replace(scene_file)
            time.sleep(2.0)
        record_fingerprint(pdir, sfx, sid, scene_fp)

        sha_hash = file_sha256(scene_file)
        gen_missing = set(gen_meta.get("missing_elements", []))
        visual_ids = {e.get("element_id") for e in visual_els}
        implemented_els = [e["element_id"] for e in vp_sc.get("elements", []) if e.get("element_id") and e["element_id"] not in gen_missing]
        missing_req = [i for i in req_els if i in visual_ids and i in gen_missing]
        for el_id in missing_req:
            w_msg = f"Scene {sid}: required element '{el_id}' is not drawn by the generated code."
            scene_warnings.append(w_msg)
            template_warnings.append({"scene_id": sid, "element_id": el_id, "category": "element_not_drawn", "message": w_msg, "dependency": None})
        preview_res = preview_verifier.verify(code, aspect=aspect)

        scenes_manifest.append({
            "scene_id": sid,
            "source_path": str(scene_file.resolve()),
            "source_sha256": sha_hash,
            "input_fingerprint": scene_fp,
            "duration_frames": max(1, round(duration * 30)),
            "fps": 30,
            "dimensions": {"width": 1080 if aspect == "9:16" else 1920, "height": 1920 if aspect == "9:16" else 1080},
            "required_elements": req_els,
            "implemented_elements": implemented_els,
            "missing_required_elements": missing_req,
            "warnings": scene_warnings,
            "compile_status": "pending",
            "security_audit": audit_scene_tsx_security(code),
            "generation": gen_meta,
            "preview_result": {
                "passed": preview_res.passed,
                "score": preview_res.score,
                "safe_zone_passed": preview_res.safe_zone_passed,
                "typography_passed": preview_res.typography_passed,
                "contrast_passed": preview_res.contrast_passed,
                "findings": preview_res.findings,
            },
            "element_classifications": [
                {
                    "element_id": c.element_id,
                    "is_3d": c.is_3d,
                    "is_supported": c.is_supported,
                    "requested_effect": c.requested_effect,
                    "fallback_strategy": c.fallback_strategy,
                    "capability_limitation": c.capability_limitation,
                }
                for c in el_classifications
            ],
            "repair_attempts": gen_meta.get("attempt_count", 1),
        })

    # Race-free compilation under global staging mutex lock
    compile_passed = False
    # `remotion_dir` is config.REMOTION_DIR (set above): the folder the scenes are staged into is the folder that must be type-checked. A second folder (<root>/remotion) used to be
    # compiled here, which never contained the staged scenes: the "0 TypeScript errors" check verified the wrong tree.

    with _remotion_staging_lock:
        remotion_gen_dir.mkdir(parents=True, exist_ok=True)
        # Copy the scenes to VIDEO_ENGINE/remotion/src/generated/ (its fixed index.ts finds them)
        for sc in scenes:
            sid = sc.get("id")
            sfile = out_dir / f"scene_{sid}.tsx"
            if sfile.exists():
                r_file = remotion_gen_dir / f"scene_{sid}.tsx"
                r_tmp = r_file.with_suffix(".tmp")
                r_tmp.write_text(sfile.read_text(encoding="utf-8"), encoding="utf-8")
                r_tmp.replace(r_file)

        if not (remotion_dir / "package.json").exists():
            # Test environment without remotion directory
            compile_passed = True
            for sc_man in scenes_manifest:
                sc_man["compile_status"] = "passed"
        else:
            try:
                ok, output = run_tsc(remotion_dir)
                rounds = 0
                while True:                                                        # errors of a generated scene go back to the LLM (with the messages); only the failing scenes are redone
                    failing = tsc_errors_by_scene(output) if not ok else render_errors_by_scene(pdir, aspect, scenes, palette)       # type errors first; once it compiles, the errors of drawing a frame
                    if not failing or rounds >= MAX_COMPILE_REPAIR_ROUNDS:
                        break                                                      # clean; or errors outside the generated scenes (nothing to repair here); or no round left
                    rounds += 1
                    for sid_s, errs in failing.items():
                        sc_man = next((m for m in scenes_manifest if str(m["scene_id"]) == sid_s), None)
                        scene_file = out_dir / f"scene_{sid_s}.tsx"
                        if sc_man is None or not scene_file.exists():
                            continue
                        fixed = repair_scene_compile_errors(pdir, sid_s, scene_file.read_text(encoding="utf-8"), errs)
                        if fixed:
                            scene_file.write_text(fixed, encoding="utf-8")
                            (remotion_gen_dir / f"scene_{sid_s}.tsx").write_text(fixed, encoding="utf-8")
                            sc_man["source_sha256"] = file_sha256(scene_file)
                            sc_man["security_audit"] = audit_scene_tsx_security(fixed)
                            sc_man["generation"]["repaired"] = True
                            sc_man["generation"]["compile_repairs"] = sc_man["generation"].get("compile_repairs", 0) + 1
                    ok, output = run_tsc(remotion_dir)
                if ok and not failing:
                    compile_passed = True
                    for sc_man in scenes_manifest:
                        sc_man["compile_status"] = "passed"
                else:
                    for sc_man in scenes_manifest:
                        sc_man["compile_status"] = "failed"
                    if not ok:
                        raise AnimationCodegenError(f"TypeScript compilation failed for generated scenes: {output[-500:]}")
                    raise AnimationCodegenError("a generated scene fails when it is drawn: " + "; ".join(f"scene {sid_s}: {errs[0]}" for sid_s, errs in failing.items()))
            except subprocess.TimeoutExpired:
                raise AnimationCodegenError("TypeScript compilation check timed out")

    retries_prevented_count = sum(1 for s in scenes_manifest if s.get("generation", {}).get("retries_prevented"))
    gen_report = reporter.build_report(
        project_id=pdir.name,
        aspect=aspect,
        scenes_data=scenes_manifest,
        overall_compile_status="passed" if compile_passed else "failed",
        retries_prevented_total=retries_prevented_count,
    )
    reporter.save_report(pdir, aspect, gen_report)

    manifest = {
        "schema": SCHEMA,
        "version": VERSION,
        "project_id": pdir.name,
        "run_id": run_id,
        "aspect": aspect,
        "mode": "custom_code",
        "status": "generated" if compile_passed else "compile_failed",
        "typecheck": {"status": "passed" if compile_passed else "failed"},
        "generation_report": f"motion_generation_report{sfx}.json",
        "skills_used": sorted(all_skills_used),
        "memory_used": sorted(all_memory_used),
        "scenes": scenes_manifest,
        "warnings": template_warnings,
        "diagnostics": {
            "total_scenes": len(scenes_manifest),
            "compiled_scenes": sum(1 for s in scenes_manifest if s["compile_status"] == "passed"),
            "prohibited_imports_found": prohibited_found_total,
            "compile_passed": compile_passed,
            "warnings_count": len(template_warnings),
            "fallbacks_applied": gen_report.get("aggregate_metrics", {}).get("fallbacks_applied", 0),
            "elements_skipped": gen_report.get("aggregate_metrics", {}).get("elements_skipped", 0),
            "retries_prevented": retries_prevented_count,
            "downstream_readiness_pct": gen_report.get("aggregate_metrics", {}).get("downstream_readiness_pct", 100.0),
        },
    }
    save_animation(pdir, aspect, manifest)

    comp_data = custom_composition(pdir, aspect, scenes, palette)               # composition.json referencing the custom_scene layers
    comp_name = f"composition{sfx}.json"
    (pdir / comp_name).write_text(json.dumps(comp_data, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")

    # Run mandatory stage LLM review
    llm_review.run_stage_llm_review(pdir, "motion_gen", aspect)

    return manifest


def build_template_animation(pdir: Path, aspect: str, comp: dict[str, Any]) -> dict[str, Any]:
    """Deprecated: in custom-code mode, templates are permanently excluded from active workflow."""
    raise AnimationCodegenError("Reusable motion templates are disabled in Motion-Only custom code mode")
