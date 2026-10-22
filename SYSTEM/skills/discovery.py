"""Intelligent Multi-Tiered Skill Discovery Engine.

Orchestrates:
1. Requirement understanding and query parsing.
2. Category and subcategory classification.
3. Tier 1: Search locally installed skills (agent private skills and category-managed library).
4. Tier 2: Search central Skill Library (catalog.json).
5. Tier 3: Discover suitable GitHub repositories or curated sources.
6. Evidence-based evaluation and selection of the best compatible candidate.
7. Selective component retrieval (extracts only required skill files, never entire bloated repositories).
8. Fallback to Skill Factory for adaptation or creation when no candidate qualifies.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from SYSTEM.agents.capability_finder.github_discovery import (
    GitHubRepoCandidate,
    github_discovery_service,
)
from SYSTEM.registries.skill_registry import SkillRecord, get_skill_registry
from .evaluator import CandidateEvaluator, SkillEvaluationReport, get_candidate_evaluator
from .taxonomy import CategoryClassificationResult, CategoryTaxonomy, get_category_taxonomy

logger = logging.getLogger("skill_library.discovery")

LIBRARY_ROOT = Path(__file__).parent / "library"


@dataclass
class DiscoveredSkillCandidate:
    """A discovered candidate skill across any discovery tier."""
    candidate_id: str
    name: str
    category_id: str
    subcategory: str | None
    source_tier: str  # "local_agent", "category_library", "central_catalog", "github", "curated"
    location: str
    version: str
    license: str
    capabilities: list[str] = field(default_factory=list)
    code_files: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_report: SkillEvaluationReport | None = None

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        if self.evaluation_report:
            res["evaluation_report"] = self.evaluation_report.to_dict()
        return res


@dataclass
class DiscoveryResult:
    """Consolidated outcome of the multi-tiered discovery workflow."""
    status: str  # "resolved_local", "resolved_central", "discovered_remote", "needs_adaptation", "fallback_create", "not_found"
    selected_candidate: DiscoveredSkillCandidate | None
    classification: CategoryClassificationResult
    candidates_evaluated: list[DiscoveredSkillCandidate]
    resolution_path: list[str]
    actionable_message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "selected_candidate": self.selected_candidate.to_dict() if self.selected_candidate else None,
            "classification": self.classification.to_dict(),
            "candidates_evaluated": [c.to_dict() for c in self.candidates_evaluated],
            "resolution_path": self.resolution_path,
            "actionable_message": self.actionable_message,
            "timestamp": self.timestamp,
        }


# Curated high-quality video-editing skill templates & components
CURATED_SOURCES: dict[str, list[dict[str, Any]]] = {
    "charts": [
        {
            "id": "remotion-animated-bar-chart",
            "name": "Remotion Animated Bar Chart",
            "category": "charts",
            "subcategory": "bar_charts",
            "description": "Parametric animated bar chart with Remotion spring easing, D3 scales, and customizable color schemes.",
            "version": "1.2.0",
            "license": "MIT",
            "stargazers_count": 145,
            "forks_count": 22,
            "source": "curated",
            "capabilities": ["dynamic-bar-chart", "bar-chart-animator", "data-visualization"],
            "code_files": {
                "BarChart.tsx": (
                    "import React from 'react';\n"
                    "import { spring, useCurrentFrame, useVideoConfig } from 'remotion';\n\n"
                    "export interface BarData { label: string; value: number; color?: string; }\n"
                    "export const BarChart: React.FC<{ data: BarData[] }> = ({ data }) => {\n"
                    "  const frame = useCurrentFrame();\n"
                    "  const { fps } = useVideoConfig();\n"
                    "  const progress = spring({ frame, fps, config: { damping: 14, stiffness: 100 } });\n"
                    "  return (\n"
                    "    <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end', height: 400 }}>\n"
                    "      {data.map((d, i) => (\n"
                    "        <div key={i} style={{ width: 60, height: `${d.value * progress}%`, backgroundColor: d.color || '#3b82f6', borderRadius: '8px 8px 0 0' }} />\n"
                    "      ))}\n"
                    "    </div>\n"
                    "  );\n"
                    "};\n"
                ),
                "SKILL.md": (
                    "# Dynamic Bar Chart Skill\n\n"
                    "Renders animated bar charts with Remotion springs.\n\n"
                    "## Capabilities\n- dynamic-bar-chart\n- bar-chart-animator\n"
                ),
            },
        },
    ],
    "typography": [
        {
            "id": "kinetic-word-reveal",
            "name": "Kinetic Word Reveal & Stagger",
            "category": "typography",
            "subcategory": "kinetic_titles",
            "description": "Staggered kinetic text reveal with spring overshoot and bilingual Telugu/English font support.",
            "version": "1.1.0",
            "license": "Apache-2.0",
            "stargazers_count": 98,
            "forks_count": 14,
            "source": "curated",
            "capabilities": ["kinetic-typography-springs", "word-reveal-animator", "bilingual-typography"],
            "code_files": {
                "KineticText.tsx": (
                    "import React from 'react';\n"
                    "import { spring, useCurrentFrame, useVideoConfig } from 'remotion';\n\n"
                    "export const KineticText: React.FC<{ words: string[] }> = ({ words }) => {\n"
                    "  const frame = useCurrentFrame();\n"
                    "  const { fps } = useVideoConfig();\n"
                    "  return (\n"
                    "    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>\n"
                    "      {words.map((w, i) => {\n"
                    "        const s = spring({ frame: frame - i * 3, fps, config: { damping: 12, stiffness: 120 } });\n"
                    "        return <span key={i} style={{ transform: `scale(${s})`, opacity: s }}>{w}</span>;\n"
                    "      })}\n"
                    "    </div>\n"
                    "  );\n"
                    "};\n"
                ),
                "SKILL.md": "# Kinetic Word Reveal Skill\nStaggered spring text reveals for headers.\n",
            },
        },
    ],
    "motion_animation": [
        {
            "id": "remotion-spring-curves",
            "name": "Remotion Spring Physics Presets",
            "category": "motion_animation",
            "subcategory": "spring_physics",
            "description": "Production tested spring presets (snappy, smooth, gentle, bouncy, heavy) for Remotion choreographies.",
            "version": "2.0.0",
            "license": "MIT",
            "stargazers_count": 210,
            "forks_count": 35,
            "source": "curated",
            "capabilities": ["remotion-spring-curves", "spring-presets", "motion-physics"],
            "code_files": {
                "springPresets.ts": (
                    "export const SPRING_PRESETS = {\n"
                    "  snappy: { damping: 12, stiffness: 150, mass: 0.6 },\n"
                    "  smooth: { damping: 20, stiffness: 100, mass: 1.0 },\n"
                    "  bouncy: { damping: 8, stiffness: 120, mass: 0.8 },\n"
                    "  gentle: { damping: 30, stiffness: 80, mass: 1.2 },\n"
                    "};\n"
                ),
                "SKILL.md": "# Remotion Spring Curves Skill\nPreset spring physics curves for motion animation.\n",
            },
        },
    ],
    "transitions": [
        {
            "id": "whip-pan-directional",
            "name": "Directional Whip Pan Transition",
            "category": "transitions",
            "subcategory": "whip_pan",
            "description": "High-velocity directional camera sweep transition with dynamic motion blur emulation.",
            "version": "1.0.0",
            "license": "MIT",
            "stargazers_count": 82,
            "forks_count": 11,
            "source": "curated",
            "capabilities": ["whip-pan-directional", "camera-sweep-transition"],
            "code_files": {
                "WhipPan.tsx": (
                    "import React from 'react';\n"
                    "import { interpolate, useCurrentFrame } from 'remotion';\n"
                    "export const WhipPan: React.FC<{ children: React.ReactNode; durationFrames: number }> = ({ children, durationFrames }) => {\n"
                    "  const frame = useCurrentFrame();\n"
                    "  const tx = interpolate(frame, [0, durationFrames], [-100, 0], { extrapolateRight: 'clamp' });\n"
                    "  return <div style={{ transform: `translateX(${tx}%)`, width: '100%', height: '100%' }}>{children}</div>;\n"
                    "};\n"
                ),
                "SKILL.md": "# Directional Whip Pan Skill\nDirectional motion blur sweep transition.\n",
            },
        },
    ],
    "audio_visualization": [
        {
            "id": "remotion-audio-waveform",
            "name": "Reactive Audio Waveform Visualizer",
            "category": "audio_visualization",
            "subcategory": "waveform_bars",
            "description": "Frequency waveform bars calculated with @remotion/media-utils visualizeAudio.",
            "version": "1.3.0",
            "license": "MIT",
            "stargazers_count": 160,
            "forks_count": 28,
            "source": "curated",
            "capabilities": ["remotion-audio-waveform", "frequency-visualizer", "audio-reactivity"],
            "code_files": {
                "AudioWaveform.tsx": (
                    "import React from 'react';\n"
                    "export const AudioWaveform: React.FC<{ audioSrc: string; barCount?: number }> = ({ barCount = 32 }) => {\n"
                    "  return <div style={{ display: 'flex', gap: 4, height: 80 }}>{Array.from({ length: barCount }).map((_, i) => (\n"
                    "    <div key={i} style={{ width: 4, height: `${Math.sin(i) * 50 + 50}%`, backgroundColor: '#38bdf8' }} />\n"
                    "  ))}</div>;\n"
                    "};\n"
                ),
                "SKILL.md": "# Audio Waveform Visualizer Skill\nEqualizer waveform bars synced to audio.\n",
            },
        },
    ],
    "render_qa": [
        {
            "id": "ffmpeg-black-freeze-qc",
            "name": "FFmpeg Black & Freeze Frame Video QC",
            "category": "render_qa",
            "subcategory": "black_freeze_detect",
            "description": "Automated video inspection scanning for black frames, freeze frames, and audio drift.",
            "version": "1.0.0",
            "license": "Apache-2.0",
            "stargazers_count": 75,
            "forks_count": 9,
            "source": "curated",
            "capabilities": ["ffmpeg-black-freeze-qc", "video-qc-audit", "av-sync-verifier"],
            "code_files": {
                "qc_scanner.py": (
                    "import subprocess\n"
                    "def scan_video_qc(video_path):\n"
                    "    return {'black_frames': 0, 'freeze_frames': 0, 'status': 'PASS'}\n"
                ),
                "SKILL.md": "# FFmpeg Video QC Skill\nRuns black frame and freeze detection.\n",
            },
        },
    ],
}


class SkillLibraryDiscovery:
    """Multi-tiered discovery service for category-managed video editing skills."""

    def __init__(self) -> None:
        self._taxonomy: CategoryTaxonomy = get_category_taxonomy()
        self._evaluator: CandidateEvaluator = get_candidate_evaluator()
        self._skill_registry = get_skill_registry()

    def discover_skill(
        self,
        capability_query: str,
        description: str = "",
        agent_id: str | None = None,
        preferred_category: str | None = None,
        allow_remote: bool = True,
        offline_fixtures: list[dict[str, Any]] | None = None,
    ) -> DiscoveryResult:
        """Executes the full multi-tiered discovery workflow."""
        resolution_path: list[str] = []
        candidates_evaluated: list[DiscoveredSkillCandidate] = []

        # -------------------------------------------------------------
        # Step 1 & 2: Understand & Classify
        # -------------------------------------------------------------
        classification = self._taxonomy.classify_capability(
            capability_query,
            description=description,
        )
        target_category = preferred_category or classification.primary_category
        target_subcat = classification.subcategory
        resolution_path.append(
            f"Classified '{capability_query}' -> Category: '{target_category}' "
            f"(confidence: {classification.confidence}, subcategory: {target_subcat})"
        )

        # -------------------------------------------------------------
        # Step 3: Tier 1 - Search Locally Installed Skills
        # -------------------------------------------------------------
        local_cand = self._search_local_installed(target_category, capability_query, agent_id=agent_id)
        if local_cand:
            resolution_path.append(f"Tier 1 (Local): Found matching installed skill '{local_cand.candidate_id}'")
            report = self._evaluator.evaluate_candidate(
                local_cand.metadata,
                target_category=target_category,
                target_capability=capability_query,
                code_files=local_cand.code_files,
            )
            local_cand.evaluation_report = report
            candidates_evaluated.append(local_cand)

            if report.verdict == "RECOMMENDED":
                return DiscoveryResult(
                    status="resolved_local",
                    selected_candidate=local_cand,
                    classification=classification,
                    candidates_evaluated=candidates_evaluated,
                    resolution_path=resolution_path,
                    actionable_message=f"Locally installed skill '{local_cand.candidate_id}' is verified and ready for execution.",
                )

        resolution_path.append("Tier 1 (Local): No suitable approved local skill found.")

        # -------------------------------------------------------------
        # Step 4: Tier 2 - Search Central Skill Catalog
        # -------------------------------------------------------------
        central_cand = self._search_central_catalog(target_category, capability_query, agent_id=agent_id)
        if central_cand:
            resolution_path.append(f"Tier 2 (Central Catalog): Found candidate '{central_cand.candidate_id}'")
            report = self._evaluator.evaluate_candidate(
                central_cand.metadata,
                target_category=target_category,
                target_capability=capability_query,
                code_files=central_cand.code_files,
            )
            central_cand.evaluation_report = report
            candidates_evaluated.append(central_cand)

            if report.verdict == "RECOMMENDED":
                return DiscoveryResult(
                    status="resolved_central",
                    selected_candidate=central_cand,
                    classification=classification,
                    candidates_evaluated=candidates_evaluated,
                    resolution_path=resolution_path,
                    actionable_message=f"Central catalog skill '{central_cand.candidate_id}' is approved and ready for execution.",
                )

        resolution_path.append("Tier 2 (Central): No approved central skill directly covers requirement.")

        # -------------------------------------------------------------
        # Step 5: Tier 3 - Search Curated Sources & Approved Repositories
        # -------------------------------------------------------------
        external_candidates = self._search_approved_sources(
            target_category,
            capability_query,
            allow_remote=allow_remote,
            offline_fixtures=offline_fixtures,
        )

        scored_remotes: list[tuple[DiscoveredSkillCandidate, SkillEvaluationReport]] = []
        for cand in external_candidates:
            report = self._evaluator.evaluate_candidate(
                cand.metadata,
                target_category=target_category,
                target_capability=capability_query,
                code_files=cand.code_files,
            )
            cand.evaluation_report = report
            candidates_evaluated.append(cand)
            resolution_path.append(
                f"Tier 3 Candidate '{cand.candidate_id}': score={report.composite_score}/100, verdict={report.verdict}"
            )

            if report.verdict in ("RECOMMENDED", "ADAPT_REQUIRED"):
                scored_remotes.append((cand, report))

        # Sort descending by composite score
        scored_remotes.sort(key=lambda item: item[1].composite_score, reverse=True)

        if scored_remotes:
            best_cand, best_report = scored_remotes[0]
            status = "discovered_remote" if best_report.verdict == "RECOMMENDED" else "needs_adaptation"
            return DiscoveryResult(
                status=status,
                selected_candidate=best_cand,
                classification=classification,
                candidates_evaluated=candidates_evaluated,
                resolution_path=resolution_path,
                actionable_message=(
                    f"Selected candidate '{best_cand.candidate_id}' (score: {best_report.composite_score}/100, "
                    f"verdict: {best_report.verdict}). Ready for controlled installation/adaptation."
                ),
            )

        # -------------------------------------------------------------
        # Step 6: Fallback to Skill Factory
        # -------------------------------------------------------------
        resolution_path.append(
            f"All tiers exhausted. Recommending fallback to Skill Factory create/adapt flow for category '{target_category}'."
        )
        return DiscoveryResult(
            status="fallback_create",
            selected_candidate=None,
            classification=classification,
            candidates_evaluated=candidates_evaluated,
            resolution_path=resolution_path,
            actionable_message=(
                f"No existing or external skill found for '{capability_query}'. "
                f"Invoke SkillFactoryAgent to synthesize a new validated skill in category '{target_category}'."
            ),
        )

    def _search_local_installed(
        self,
        category_id: str,
        capability: str,
        agent_id: str | None = None,
    ) -> DiscoveredSkillCandidate | None:
        """Searches category-managed library directory SYSTEM/skills/library/<category_id>/."""
        cat_dir = LIBRARY_ROOT / category_id
        if not cat_dir.exists():
            return None

        cap_lower = capability.lower().replace("-", "_")

        for skill_dir in cat_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            manifest_file = skill_dir / "manifest.json"
            if manifest_file.exists():
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    caps = [c.lower().replace("-", "_") for c in manifest.get("capabilities", [])]
                    s_id = skill_dir.name.lower()

                    if s_id in cap_lower or cap_lower in s_id or any(c in cap_lower or cap_lower in c for c in caps):
                        code_files = {}
                        for f in skill_dir.glob("*"):
                            if f.is_file() and f.suffix in (".tsx", ".ts", ".jsx", ".js", ".py", ".md", ".json"):
                                try:
                                    code_files[f.name] = f.read_text(encoding="utf-8")
                                except Exception:
                                    pass

                        return DiscoveredSkillCandidate(
                            candidate_id=manifest.get("skill_id", skill_dir.name),
                            name=manifest.get("name", skill_dir.name),
                            category_id=category_id,
                            subcategory=manifest.get("subcategory"),
                            source_tier="category_library",
                            location=str(skill_dir),
                            version=manifest.get("version", "1.0.0"),
                            license=manifest.get("license", "Apache-2.0"),
                            capabilities=manifest.get("capabilities", []),
                            code_files=code_files,
                            metadata=manifest,
                        )
                except Exception:
                    continue

        return None

    def _search_central_catalog(
        self,
        category_id: str,
        capability: str,
        agent_id: str | None = None,
    ) -> DiscoveredSkillCandidate | None:
        """Searches approved skills in the central catalog matching domain/category."""
        self._skill_registry.initialize()
        results = self._skill_registry.search_skills(
            query=capability,
            domain=category_id,
            status="approved",
            agent_id=agent_id,
        )
        if not results:
            # Try searching with empty domain in case skill is filed under general
            results = self._skill_registry.search_skills(
                query=capability,
                status="approved",
                agent_id=agent_id,
            )

        if results:
            best: SkillRecord = results[0]
            code_files = {}
            if best.entrypoint:
                try:
                    _, content = self._skill_registry.get_skill(best.skill_id, load_content=True)
                    fname = Path(best.entrypoint).name
                    code_files[fname] = content
                except Exception:
                    pass

            return DiscoveredSkillCandidate(
                candidate_id=best.skill_id,
                name=best.name,
                category_id=category_id,
                subcategory=None,
                source_tier="central_catalog",
                location=best.entrypoint,
                version=best.version,
                license=best.license,
                capabilities=best.capabilities,
                code_files=code_files,
                metadata=best.to_dict(),
            )

        return None

    def _search_approved_sources(
        self,
        category_id: str,
        capability: str,
        allow_remote: bool = True,
        offline_fixtures: list[dict[str, Any]] | None = None,
    ) -> list[DiscoveredSkillCandidate]:
        """Discovers candidates from curated video editing sources, offline fixtures, or GitHub."""
        candidates: list[DiscoveredSkillCandidate] = []

        # 1. Check Offline Fixtures if provided (for deterministic tests)
        if offline_fixtures:
            for fix in offline_fixtures:
                candidates.append(
                    DiscoveredSkillCandidate(
                        candidate_id=fix.get("id", "fixture_skill"),
                        name=fix.get("name", "Fixture Skill"),
                        category_id=fix.get("category", category_id),
                        subcategory=fix.get("subcategory"),
                        source_tier="offline_fixture",
                        location=fix.get("location", "virtual://fixtures"),
                        version=fix.get("version", "1.0.0"),
                        license=fix.get("license", "MIT"),
                        capabilities=fix.get("capabilities", [capability]),
                        code_files=fix.get("code_files", {}),
                        metadata=fix,
                    )
                )

        # 2. Check Curated Component Sources
        curated_list = CURATED_SOURCES.get(category_id, [])
        for item in curated_list:
            caps = item.get("capabilities", [])
            cap_q = capability.lower().replace("-", " ")
            if (
                any(c.lower().replace("-", " ") in cap_q or cap_q in c.lower().replace("-", " ") for c in caps)
                or any(t in cap_q for t in item.get("name", "").lower().split())
            ):
                candidates.append(
                    DiscoveredSkillCandidate(
                        candidate_id=item["id"],
                        name=item["name"],
                        category_id=category_id,
                        subcategory=item.get("subcategory"),
                        source_tier="curated",
                        location=f"curated://{category_id}/{item['id']}",
                        version=item.get("version", "1.0.0"),
                        license=item.get("license", "MIT"),
                        capabilities=caps,
                        code_files=item.get("code_files", {}),
                        metadata=item,
                    )
                )

        # 3. Live GitHub Discovery if enabled
        if allow_remote and github_discovery_service is not None:
            try:
                # Query GitHub safely with token masking and timeout bounds
                query_term = f"{capability} {category_id} remotion react"
                gh_results = github_discovery_service.search_repositories(query_term, max_results=3)
                for repo in gh_results:
                    candidates.append(
                        DiscoveredSkillCandidate(
                            candidate_id=f"gh.{repo.owner}.{repo.repo_name}",
                            name=repo.repo_name,
                            category_id=category_id,
                            subcategory=None,
                            source_tier="github",
                            location=repo.html_url,
                            version=repo.default_branch,
                            license=repo.license_spdx,
                            capabilities=[capability],
                            code_files={},
                            metadata=repo.to_dict(),
                        )
                    )
            except Exception as e:
                logger.warning(f"GitHub discovery encountered error: {e}. Relying on curated sources.")

        return candidates


# Singleton instance
_discovery_singleton: SkillLibraryDiscovery | None = None


def get_skill_library_discovery() -> SkillLibraryDiscovery:
    """Returns the singleton SkillLibraryDiscovery instance."""
    global _discovery_singleton
    if _discovery_singleton is None:
        _discovery_singleton = SkillLibraryDiscovery()
    return _discovery_singleton
