"""Animation Intelligence Subsystem for Motion Animation Agent v2.0.0.

Provides:
1. ThreeDFallbackEngine:
   - Identifies simple vs complex/unsupported 3D elements.
   - Maps unsupported 3D to high-fidelity 2D/2.5D Remotion primitives.
   - Provides structured skipping for unapproximable elements without failing the scene.
   - Implements Retry Storm Prevention against known capability limitations.
2. VisualPreviewVerifier:
   - Lightweight static visual checks (safe-area margins, typography hierarchy, contrast).
3. StructuredGenerationReporter:
   - Emits comprehensive motion_generation_report.json tracking per-element statuses.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("motion_animation.intelligence")

# Known unsupported 3D runtime markers & modules
UNSUPPORTED_3D_PATTERNS = [
    r"\bthree\b",
    r"\b@react-three\b",
    r"\bthreejs\b",
    r"\bwebgl\b",
    r"\bglsl\b",
    r"\bshader\b",
    r"\bgltf\b",
    r"\bglb\b",
    r"\bobj_?loader\b",
    r"\braymarching\b",
    r"\bvolumetric\b",
    r"\bpoint_?cloud\b",
]

# Simple / Remotion-native 3D patterns (allowed as CSS / 2.5D)
SUPPORTED_3D_PATTERNS = [
    r"\bperspective\b",
    r"\brotate[XYZ]\b",
    r"\bcss_?3d\b",
    r"\bisometric\b",
    r"\bparallax\b",
    r"\bcard_?flip\b",
    r"\b2\.5d\b",
]


@dataclass
class ElementClassification:
    element_id: str
    is_3d: bool
    is_supported: bool
    requested_effect: str
    fallback_strategy: str  # "native", "svg_isometric", "2d_particles", "2.5d_parallax", "skip"
    capability_limitation: str | None = None
    retry_prevented: bool = False


@dataclass
class VisualPreviewResult:
    passed: bool
    score: float  # 0.0 to 1.0
    safe_zone_passed: bool
    typography_passed: bool
    contrast_passed: bool
    findings: list[str] = field(default_factory=list)


class ThreeDFallbackEngine:
    """Classifies 3D visual cues, prevents retry storms on unsupported 3D,

    and maps complex 3D to production Remotion 2D/2.5D primitives.
    """

    def __init__(self) -> None:
        self._unsupported_cache: set[str] = set()

    def classify_element(self, element: dict[str, Any]) -> ElementClassification:
        el_id = str(element.get("element_id") or element.get("id") or "unnamed_element")
        el_type = str(element.get("type", "")).lower()
        if element.get("real_media"):                                   # a collected photo or clip is media, never a 3D request, whatever its title says ("model", "camera" ...)
            return ElementClassification(element_id=el_id, is_3d=False, is_supported=True, requested_effect=el_type or "real_media", fallback_strategy="native")
        desc = str(element.get("visual_description", "")).lower()
        effect = str(element.get("effect", "")).lower()
        combined = f"{el_type} {desc} {effect}"

        # 1. Check if element has explicit unapproximable requirement
        if element.get("unapproximable") is True or "unapproximable" in combined:
            return ElementClassification(
                element_id=el_id,
                is_3d=True,
                is_supported=False,
                requested_effect=el_type or "3d_unapproximable",
                fallback_strategy="skip",
                capability_limitation="unapproximable_3d_element_without_hardware_accelerator",
                retry_prevented=True,
            )

        # 2. Check for complex/unsupported 3D
        is_unsupported = any(re.search(pat, combined) for pat in UNSUPPORTED_3D_PATTERNS)
        is_supported_3d = any(re.search(pat, combined) for pat in SUPPORTED_3D_PATTERNS)

        if is_unsupported:
            # Map to 2D/2.5D approximation strategy
            if "particle" in combined or "vortex" in combined:
                strategy = "2d_particles"
                limitation = "threejs_webgl_particle_system_unsupported"
            elif "parallax" in combined or "fly" in combined or "camera" in combined:
                strategy = "2.5d_parallax"
                limitation = "webgl_camera_flythrough_unsupported"
            elif "mesh" in combined or "gltf" in combined or "glb" in combined or "model" in combined:
                strategy = "svg_isometric"
                limitation = "gltf_3d_mesh_pipeline_not_configured"
            else:
                strategy = "svg_isometric"
                limitation = "complex_webgl_shaders_unsupported_in_remotion_canvas"

            return ElementClassification(
                element_id=el_id,
                is_3d=True,
                is_supported=False,
                requested_effect=el_type or "complex_3d",
                fallback_strategy=strategy,
                capability_limitation=limitation,
                retry_prevented=True,
            )

        if is_supported_3d or "3d" in combined:
            return ElementClassification(
                element_id=el_id,
                is_3d=True,
                is_supported=True,
                requested_effect=el_type or "native_3d",
                fallback_strategy="native",
                capability_limitation=None,
                retry_prevented=False,
            )

        return ElementClassification(
            element_id=el_id,
            is_3d=False,
            is_supported=True,
            requested_effect=el_type or "2d_graphic",
            fallback_strategy="native",
            capability_limitation=None,
            retry_prevented=False,
        )

    def transform_elements_for_codegen(
        self, elements: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[ElementClassification]]:
        """Transforms visual elements before code generation, replacing unsupported

        3D elements with 2D/2.5D approximations or skipping unapproximable ones.
        """
        transformed: list[dict[str, Any]] = []
        classifications: list[ElementClassification] = []

        for el in elements:
            cls = self.classify_element(el)
            classifications.append(cls)

            if cls.fallback_strategy == "skip":
                # Element is deliberately skipped to prevent failing the entire scene
                logger.info(
                    f"Element '{cls.element_id}' is skipped: unapproximable 3D without runtime ({cls.capability_limitation})"
                )
                continue

            if not cls.is_supported and cls.is_3d:
                # Replace with high-quality 2D/2.5D approximation
                copy_el = dict(el)
                if cls.fallback_strategy == "2d_particles":
                    copy_el["type"] = "particle_field_2d"
                    copy_el["visual_description"] = (
                        f"2D Remotion particle drift with radial opacity (approximated from: {el.get('visual_description', '')})"
                    )
                elif cls.fallback_strategy == "2.5d_parallax":
                    copy_el["type"] = "parallax_2_5d"
                    copy_el["visual_description"] = (
                        f"2.5D layered z-index parallax with spring scale (approximated from: {el.get('visual_description', '')})"
                    )
                else:  # svg_isometric
                    copy_el["type"] = "svg_isometric"
                    copy_el["visual_description"] = (
                        f"Multi-layered isometric SVG illustration with dynamic spring rotation (approximated from: {el.get('visual_description', '')})"
                    )
                copy_el["fallback_applied"] = True
                copy_el["original_requested_effect"] = cls.requested_effect
                copy_el["fallback_strategy"] = cls.fallback_strategy
                transformed.append(copy_el)
            else:
                transformed.append(el)

        return transformed, classifications

    def is_known_limitation_error(self, error_message: str) -> bool:
        """Determines if a compile or generation error is due to a known unsupported 3D limitation,

        allowing the repair loop to abort early instead of making wasteful retries.
        """
        lower = error_message.lower()
        return any(
            marker in lower
            for marker in [
                "cannot find module 'three'",
                "cannot find module '@react-three",
                "webgl",
                "webglrenderingcontext",
                "three.js",
                "gltf",
                "shader",
            ]
        )


class VisualPreviewVerifier:
    """Lightweight static inspection of Remotion code and layout to guarantee visual quality."""

    def verify(
        self,
        source_code: str,
        aspect: str = "16:9",
        safe_zones: dict[str, Any] | None = None,
        typography_plan: dict[str, Any] | None = None,
    ) -> VisualPreviewResult:
        findings: list[str] = []
        safe_zone_passed = True
        typography_passed = True
        contrast_passed = True

        # 1. Safe Zone Margin Verification
        # Check that canvas has adequate padding/margins (at least 5% or 40px)
        has_padding = bool(re.search(r"padding:\s*[\"']?([0-9]+%|[4-9][0-9]px|[1-9][0-9]{2,}px)", source_code))
        has_margin = bool(re.search(r"margin:\s*[\"']?([0-9]+%|[4-9][0-9]px|[1-9][0-9]{2,}px)", source_code))
        has_center_layout = "justifyContent: \"center\"" in source_code or "justifyContent: 'center'" in source_code

        if not (has_padding or has_margin or has_center_layout):
            safe_zone_passed = False
            findings.append("Missing safe-zone padding or centering; elements risk bleeding off-screen")

        # 2. Typography Hierarchy Verification
        # Find font sizes in source code
        font_sizes = [int(m) for m in re.findall(r"fontSize:\s*([0-9]{2,3})", source_code)]
        if font_sizes:
            headline_size = max(font_sizes)
            if headline_size < 32:
                typography_passed = False
                findings.append(f"Headline typography too small ({headline_size}px); minimum standard is 32px")
            if len(font_sizes) >= 2:
                # If there are multiple text elements, verify hierarchy (largest > second largest)
                sorted_sizes = sorted(font_sizes, reverse=True)
                if sorted_sizes[0] == sorted_sizes[1] and sorted_sizes[0] < 40:
                    findings.append("Subtext and headline lack visual size hierarchy")

        # 3. Contrast & Visibility Verification
        # Ensure text is not dark-on-dark or invisible
        has_text_color = bool(re.search(r"color:\s*[\"']#(?:fff|faf|f8|f1|e2|cbd|ffffff|f8fafc)", source_code, re.I))
        has_text_shadow = "textShadow" in source_code
        has_contrast = has_text_color or has_text_shadow or "radial-gradient" in source_code

        if not has_contrast:
            contrast_passed = False
            findings.append("Low text contrast: Headline lacks explicit high-contrast foreground color or shadow")

        passed = safe_zone_passed and typography_passed and contrast_passed
        score = 1.0
        if not safe_zone_passed:
            score -= 0.35
        if not typography_passed:
            score -= 0.35
        if not contrast_passed:
            score -= 0.30
        score = max(0.0, round(score, 2))

        return VisualPreviewResult(
            passed=passed,
            score=score,
            safe_zone_passed=safe_zone_passed,
            typography_passed=typography_passed,
            contrast_passed=contrast_passed,
            findings=findings,
        )


class StructuredGenerationReporter:
    """Builds and records motion_generation_report.json tracking per-element statuses."""

    def build_report(
        self,
        project_id: str,
        aspect: str,
        scenes_data: list[dict[str, Any]],
        overall_compile_status: str,
        retries_prevented_total: int = 0,
    ) -> dict[str, Any]:
        total_elements = 0
        fallbacks_applied = 0
        elements_skipped = 0
        elements_generated = 0
        reported_scenes = []

        for sc in scenes_data:
            sid = sc.get("scene_id")
            sc_elements = sc.get("element_classifications", [])
            preview = sc.get("preview_result") or {}
            undrawn = set((sc.get("generation") or {}).get("missing_elements", []))     # planned elements the TSX does not carry a data-element-id node for

            reported_elements = []
            for el in sc_elements:
                total_elements += 1
                if el.get("fallback_strategy") == "skip":
                    status = "element_skipped"
                    elements_skipped += 1
                elif el.get("element_id") in undrawn:
                    status = "not_drawn"
                elif el.get("fallback_strategy") != "native" and not el.get("is_supported", True):
                    status = "fallback_applied"
                    fallbacks_applied += 1
                else:
                    status = "generated"
                    elements_generated += 1

                reported_elements.append({
                    "element_id": el.get("element_id"),
                    "requested_effect": el.get("requested_effect"),
                    "is_3d": el.get("is_3d", False),
                    "supported_3d": el.get("is_supported", True),
                    "implementation_status": status,
                    "fallback_type": el.get("fallback_strategy", "native"),
                    "capability_limitation": el.get("capability_limitation"),
                })

            reported_scenes.append({
                "scene_id": sid,
                "elements": reported_elements,
                "preview_verification": preview,
                "repair_attempts": sc.get("repair_attempts", 1),
                "compile_status": sc.get("compile_status", "passed"),
                "downstream_ready": sc.get("compile_status") == "passed" and preview.get("passed", True) and not sc.get("missing_required_elements"),
            })

        readiness_pct = round(
            (sum(1 for s in reported_scenes if s["downstream_ready"]) / max(1, len(reported_scenes))) * 100, 1
        )

        return {
            "schema_version": "2.0.0",
            "project_id": project_id,
            "aspect": aspect,
            "status": "completed" if overall_compile_status == "passed" else "failed",
            "retries_prevented": retries_prevented_total,
            "scenes": reported_scenes,
            "aggregate_metrics": {
                "total_scenes": len(reported_scenes),
                "total_elements": total_elements,
                "elements_generated": elements_generated,
                "fallbacks_applied": fallbacks_applied,
                "elements_skipped": elements_skipped,
                "downstream_readiness_pct": readiness_pct,
            },
        }

    def save_report(self, project_dir: Path, aspect: str, report: dict[str, Any]) -> Path:
        sfx = "_9x16" if aspect == "9:16" else ""
        report_path = project_dir / f"motion_generation_report{sfx}.json"
        tmp_path = report_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(report_path)
        return report_path
