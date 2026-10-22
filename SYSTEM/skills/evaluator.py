"""Multi-Criteria Skill Candidate Evaluation and Selection Engine.

Evaluates candidate skills and repository artifacts using evidence-based criteria:
1. Capability relevance and demonstrated usefulness (0-30 pts).
2. Source authenticity and repository quality (0-20 pts).
3. Maintenance and available version information (0-15 pts).
4. License compatibility (0-15 pts; flags copyleft/unclear for operator approval).
5. Security and untrusted-code risks (0-20 pts; AST audit for shell injection, secrets, prompt injection).
6. Technology stack compatibility (Remotion, React, TypeScript, FFmpeg).
7. Duplication detection against existing installed skills.
8. Testability and execution evidence.
"""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from SYSTEM.registries.skill_registry import SkillRecord, audit_skill_content, get_skill_registry

logger = logging.getLogger("skill_library.evaluator")

EvaluationVerdict = Literal["RECOMMENDED", "ADAPT_REQUIRED", "REJECTED", "REQUIRES_APPROVAL"]

PERMISSIVE_LICENSES = {
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "isc": "ISC",
    "cc-by-4.0": "CC-BY-4.0",
    "ofl-1.1": "OFL-1.1",
    "licenseref-project": "LicenseRef-project",
}

RESTRICTIVE_LICENSES = {
    "gpl-2.0": "GPL-2.0 (Copyleft)",
    "gpl-3.0": "GPL-3.0 (Copyleft)",
    "agpl-3.0": "AGPL-3.0 (Network Copyleft)",
    "lgpl-3.0": "LGPL-3.0 (Weak Copyleft)",
    "commercial": "Proprietary Commercial",
}


@dataclass
class CriterionScore:
    name: str
    score: float
    max_score: float
    passed: bool
    evidence: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SkillEvaluationReport:
    """Comprehensive, evidence-based evaluation report for a candidate skill."""
    candidate_id: str
    candidate_name: str
    category_id: str
    composite_score: float  # 0.0 to 100.0
    verdict: EvaluationVerdict
    summary: str
    criteria: dict[str, CriterionScore]
    license_status: dict[str, Any]
    security_audit: dict[str, Any]
    compatibility: dict[str, Any]
    duplication_analysis: dict[str, Any]
    actionable_reasons: list[str]
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CandidateEvaluator:
    """Evaluates candidate skills against the 8 multi-criteria requirements."""

    def __init__(self) -> None:
        self._registry = get_skill_registry()

    def evaluate_candidate(
        self,
        candidate_data: dict[str, Any],
        target_category: str,
        target_capability: str = "",
        code_files: dict[str, str] | None = None,
        current_skill_id: str | None = None,
    ) -> SkillEvaluationReport:
        """Evaluates candidate skill metadata and source code against multi-criteria rubrics."""
        self._registry.initialize()
        code_files = code_files or {}

        cid = candidate_data.get("id") or candidate_data.get("name") or "unknown_candidate"
        cname = candidate_data.get("name") or candidate_data.get("full_name") or cid

        criteria: dict[str, CriterionScore] = {}
        actionable_reasons: list[str] = []

        # -------------------------------------------------------------
        # 1. Capability Relevance & Demonstrated Usefulness (30 pts)
        # -------------------------------------------------------------
        relevance_score, rel_passed, rel_evidence, rel_details = self._evaluate_relevance(
            candidate_data, target_category, target_capability, code_files
        )
        criteria["capability_relevance"] = CriterionScore(
            name="Capability Relevance",
            score=relevance_score,
            max_score=30.0,
            passed=rel_passed,
            evidence=rel_evidence,
            details=rel_details,
        )
        if not rel_passed:
            actionable_reasons.append(f"Relevance deficit: {rel_evidence}")

        # -------------------------------------------------------------
        # 2. Source Authenticity & Repository Quality (20 pts)
        # -------------------------------------------------------------
        auth_score, auth_passed, auth_evidence, auth_details = self._evaluate_authenticity(candidate_data)
        criteria["source_authenticity"] = CriterionScore(
            name="Source Authenticity & Quality",
            score=auth_score,
            max_score=20.0,
            passed=auth_passed,
            evidence=auth_evidence,
            details=auth_details,
        )
        if not auth_passed:
            actionable_reasons.append(f"Source quality risk: {auth_evidence}")

        # -------------------------------------------------------------
        # 3. Maintenance & Version Information (15 pts)
        # -------------------------------------------------------------
        maint_score, maint_passed, maint_evidence, maint_details = self._evaluate_maintenance(candidate_data)
        criteria["maintenance_and_version"] = CriterionScore(
            name="Maintenance & Version Freshness",
            score=maint_score,
            max_score=15.0,
            passed=maint_passed,
            evidence=maint_evidence,
            details=maint_details,
        )

        # -------------------------------------------------------------
        # 4. License Compatibility (15 pts)
        # -------------------------------------------------------------
        lic_score, lic_passed, lic_evidence, lic_status = self._evaluate_license(candidate_data)
        criteria["license_compatibility"] = CriterionScore(
            name="License Compatibility",
            score=lic_score,
            max_score=15.0,
            passed=lic_passed,
            evidence=lic_evidence,
            details=lic_status,
        )
        if not lic_passed:
            actionable_reasons.append(f"License limitation: {lic_evidence}")

        # -------------------------------------------------------------
        # 5. Security & Untrusted-Code Risks (20 pts)
        # -------------------------------------------------------------
        sec_score, sec_passed, sec_evidence, sec_audit = self._evaluate_security(candidate_data, code_files)
        criteria["security_and_safety"] = CriterionScore(
            name="Security & Safe Execution",
            score=sec_score,
            max_score=20.0,
            passed=sec_passed,
            evidence=sec_evidence,
            details=sec_audit,
        )
        if not sec_passed:
            actionable_reasons.append(f"Security findings: {sec_evidence}")

        # -------------------------------------------------------------
        # 6. Technology Stack Compatibility
        # -------------------------------------------------------------
        compat_info = self._evaluate_tech_stack_compatibility(candidate_data, code_files, target_category)

        # -------------------------------------------------------------
        # 7. Duplication Detection
        # -------------------------------------------------------------
        dup_info = self._evaluate_duplication(candidate_data, target_category, target_capability, current_skill_id=current_skill_id)
        if dup_info["is_duplicate"]:
            actionable_reasons.append(
                f"Duplicate detected: functionally identical skill '{dup_info['existing_skill_id']}' already installed."
            )

        # -------------------------------------------------------------
        # Composite Scoring and Recommendation Verdict
        # -------------------------------------------------------------
        composite = sum(c.score for c in criteria.values())
        composite = round(min(100.0, max(0.0, composite)), 1)

        # Verdict calculation
        verdict: EvaluationVerdict
        summary: str

        if not sec_passed or sec_audit.get("risk_level") in ("critical", "high"):
            verdict = "REJECTED"
            summary = "Candidate rejected due to security or untrusted code risks."
        elif dup_info["is_duplicate"]:
            verdict = "REJECTED"
            summary = f"Candidate rejected as duplicate of existing approved skill '{dup_info['existing_skill_id']}'."
        elif not lic_passed or lic_status.get("requires_approval"):
            verdict = "REQUIRES_APPROVAL"
            summary = f"Candidate requires operator approval: license is {lic_status.get('license', 'unknown')}."
        elif not compat_info["is_compatible"]:
            verdict = "ADAPT_REQUIRED"
            summary = "Candidate requires code adaptation to conform with Remotion/React stack."
        elif composite >= 75.0 and rel_passed and auth_passed:
            verdict = "RECOMMENDED"
            summary = f"High-confidence candidate ({composite}/100) recommended for automated installation."
        elif composite >= 50.0:
            verdict = "ADAPT_REQUIRED"
            summary = f"Moderate-confidence candidate ({composite}/100) suitable for adaptation via Skill Factory."
        else:
            verdict = "REJECTED"
            summary = f"Low score ({composite}/100); insufficient evidence of relevance or quality."

        return SkillEvaluationReport(
            candidate_id=cid,
            candidate_name=cname,
            category_id=target_category,
            composite_score=composite,
            verdict=verdict,
            summary=summary,
            criteria=criteria,
            license_status=lic_status,
            security_audit=sec_audit,
            compatibility=compat_info,
            duplication_analysis=dup_info,
            actionable_reasons=actionable_reasons,
        )

    def _evaluate_relevance(
        self,
        candidate_data: dict[str, Any],
        target_category: str,
        target_capability: str,
        code_files: dict[str, str],
    ) -> tuple[float, bool, str, dict[str, Any]]:
        text_corpus = (
            f"{candidate_data.get('name', '')} {candidate_data.get('description', '')} "
            f"{' '.join(candidate_data.get('topics', []))} {' '.join(candidate_data.get('capabilities', []))}"
        ).lower()

        cap_clean = target_capability.lower().replace("-", " ").replace("_", " ")
        cat_clean = target_category.lower().replace("_", " ")

        score = 0.0
        matches = []

        if target_capability and (target_capability.lower() in text_corpus or cap_clean in text_corpus):
            score += 15.0
            matches.append(f"capability '{target_capability}'")
        else:
            # Token-based capability matching
            cap_tokens = [t for t in re.findall(r"\b[a-z0-9]+\b", cap_clean) if len(t) > 2]
            token_matches = [t for t in cap_tokens if t in text_corpus]
            if token_matches:
                tok_score = min(15.0, round((len(token_matches) / max(1, len(cap_tokens))) * 15.0, 1))
                score += tok_score
                matches.append(f"tokens ({', '.join(token_matches)})")

        cat_stem = cat_clean.rstrip("s")
        if target_category and (target_category.lower() in text_corpus or cat_clean in text_corpus or (len(cat_stem) > 3 and cat_stem in text_corpus)):
            score += 10.0
            matches.append(f"category '{target_category}'")

        # Code files inspection
        for fname, content in code_files.items():
            if target_capability and target_capability.lower() in content.lower():
                score += 5.0
                matches.append(f"code match in {fname}")
                break

        passed = score >= 10.0
        evidence = f"Matches: {', '.join(matches)}" if matches else "No direct capability/category matches found."
        return min(30.0, score), passed, evidence, {"matches": matches}

    def _evaluate_authenticity(self, candidate_data: dict[str, Any]) -> tuple[float, bool, str, dict[str, Any]]:
        # Distinguish local/internal from external GitHub candidates
        source = candidate_data.get("source", "github")
        if source in ("local", "internal"):
            return 20.0, True, "Verified internal system artifact.", {"source": source, "internal": True}

        score = 5.0  # Base score for valid metadata
        stars = candidate_data.get("stargazers_count", 0)
        forks = candidate_data.get("forks_count", 0)
        archived = candidate_data.get("archived", False)

        if archived:
            return 2.0, False, "Repository is archived / abandoned.", {"archived": True}

        if stars >= 50:
            score += 10.0
        elif stars >= 10:
            score += 6.0
        elif stars >= 2:
            score += 3.0

        if forks >= 5:
            score += 5.0
        elif forks >= 1:
            score += 2.0

        passed = score >= 8.0
        evidence = f"Stars: {stars}, Forks: {forks}, Active: {not archived}"
        return min(20.0, score), passed, evidence, {"stars": stars, "forks": forks, "archived": archived}

    def _evaluate_maintenance(self, candidate_data: dict[str, Any]) -> tuple[float, bool, str, dict[str, Any]]:
        source = candidate_data.get("source", "github")
        if source in ("local", "internal"):
            return 15.0, True, "Internal component actively maintained.", {"maintained": True}

        version = candidate_data.get("version") or candidate_data.get("default_branch") or "main"
        updated_at = candidate_data.get("updated_at") or candidate_data.get("pushed_at")

        score = 8.0
        if version and version != "unknown":
            score += 4.0
        if updated_at:
            score += 3.0

        passed = score >= 8.0
        evidence = f"Version: {version}, Last updated: {updated_at or 'available'}"
        return min(15.0, score), passed, evidence, {"version": version, "updated_at": updated_at}

    def _evaluate_license(self, candidate_data: dict[str, Any]) -> tuple[float, bool, str, dict[str, Any]]:
        raw_lic = candidate_data.get("license")
        spdx = ""
        if isinstance(raw_lic, dict):
            spdx = raw_lic.get("spdx_id") or raw_lic.get("key") or ""
        elif isinstance(raw_lic, str):
            spdx = raw_lic

        spdx_clean = spdx.lower().strip()
        if not spdx_clean or spdx_clean in ("none", "null", "unknown"):
            return 4.0, False, "License not specified or unknown. Requires human operator approval.", {
                "license": "Unknown",
                "is_permissive": False,
                "requires_approval": True,
            }

        # Permissive licenses
        if spdx_clean in PERMISSIVE_LICENSES:
            canonical = PERMISSIVE_LICENSES[spdx_clean]
            return 15.0, True, f"Permissive open source license ({canonical}). Fully compatible.", {
                "license": canonical,
                "is_permissive": True,
                "requires_approval": False,
            }

        # Restrictive / Copyleft licenses
        if spdx_clean in RESTRICTIVE_LICENSES:
            desc = RESTRICTIVE_LICENSES[spdx_clean]
            return 3.0, False, f"Copyleft/restrictive license ({desc}). Requires approval before use.", {
                "license": spdx,
                "is_permissive": False,
                "requires_approval": True,
            }

        # Fallback permissive match check
        for perm in ("mit", "apache", "bsd", "isc"):
            if perm in spdx_clean:
                return 12.0, True, f"Permissive license matched ({spdx}).", {
                    "license": spdx,
                    "is_permissive": True,
                    "requires_approval": False,
                }

        return 5.0, False, f"Unrecognized license '{spdx}'. Requires approval.", {
            "license": spdx,
            "is_permissive": False,
            "requires_approval": True,
        }

    def _evaluate_security(
        self,
        candidate_data: dict[str, Any],
        code_files: dict[str, str],
    ) -> tuple[float, bool, str, dict[str, Any]]:
        findings: list[str] = []
        risk_level = "low"

        # Check metadata description / readme
        meta_text = f"{candidate_data.get('description', '')} {candidate_data.get('name', '')}"
        meta_audit = audit_skill_content(meta_text, filename="metadata")
        if not meta_audit["passed"]:
            findings.extend(meta_audit["findings"])
            risk_level = meta_audit["risk_level"]

        # Check all code files statically
        for fname, content in code_files.items():
            audit = audit_skill_content(content, filename=fname)
            if not audit["passed"]:
                findings.extend(audit["findings"])
                if audit["risk_level"] in ("critical", "high"):
                    risk_level = audit["risk_level"]

            # Additional AST static inspection for Python files
            if fname.endswith(".py"):
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if alias.name in ("os", "subprocess", "socket", "urllib"):
                                    findings.append(f"Suspicious import '{alias.name}' in {fname}")
                                    if risk_level == "low":
                                        risk_level = "medium"
                        elif isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                                findings.append(f"Dangerous call '{node.func.id}()' in {fname}")
                                risk_level = "critical"
                except SyntaxError:
                    findings.append(f"Syntax error in candidate file {fname}")
                    if risk_level == "low":
                        risk_level = "medium"

        passed = (len(findings) == 0) or (risk_level in ("low", "medium"))
        score = 20.0 if not findings else (10.0 if risk_level == "medium" else 0.0)
        evidence = "Clean static security audit." if not findings else f"Security warnings: {'; '.join(findings[:3])}"

        return score, passed, evidence, {
            "passed": passed,
            "risk_level": risk_level,
            "findings": findings,
            "inspected_files": list(code_files.keys()),
        }

    def _evaluate_tech_stack_compatibility(
        self,
        candidate_data: dict[str, Any],
        code_files: dict[str, str],
        target_category: str,
    ) -> dict[str, Any]:
        """Validates compatibility with Remotion, React, TypeScript, and FFmpeg."""
        has_react_remotion = False
        has_ffmpeg = False
        has_ts = False

        langs = candidate_data.get("languages", [])
        if isinstance(langs, dict):
            langs = list(langs.keys())

        # Check languages & extensions
        all_exts = {f.split(".")[-1].lower() for f in code_files.keys()}
        if {"tsx", "jsx", "ts", "js"}.intersection(all_exts) or any(l.lower() in ("typescript", "javascript") for l in langs):
            has_react_remotion = True
            has_ts = True

        for fname, content in code_files.items():
            if "from 'remotion'" in content or "from \"remotion\"" in content or "from 'react'" in content:
                has_react_remotion = True
            if "ffmpeg" in content.lower() or "ffprobe" in content.lower():
                has_ffmpeg = True

        category_requires_ffmpeg = target_category in ("audio_editing", "render_qa", "color_grading", "time_effects")
        category_requires_remotion = target_category in (
            "graphics", "charts", "maps", "typography", "motion_animation", "transitions", "vfx",
            "infographics", "2d_graphics", "3d_graphics", "ui_hud", "layouts", "captions", "templates"
        )

        is_compatible = True
        notes = []

        if category_requires_remotion and not has_react_remotion:
            notes.append("Category expects Remotion/React components; candidate may require adaptation.")
        if category_requires_ffmpeg and not has_ffmpeg:
            notes.append("Category expects FFmpeg pipeline execution.")

        return {
            "is_compatible": is_compatible,
            "has_react_remotion": has_react_remotion,
            "has_ffmpeg": has_ffmpeg,
            "has_typescript": has_ts,
            "notes": notes,
        }

    def _evaluate_duplication(
        self,
        candidate_data: dict[str, Any],
        target_category: str,
        target_capability: str,
        current_skill_id: str | None = None,
    ) -> dict[str, Any]:
        """Detects whether an equivalent skill is already registered in this category."""
        approved_skills = self._registry.list_skills(status="approved")
        target_id = (candidate_data.get("id") or candidate_data.get("name") or "").lower().strip()

        for s in approved_skills:
            if current_skill_id and s.skill_id.lower() == current_skill_id.lower():
                continue
            if s.domain == target_category:
                if s.skill_id.lower() == target_id:
                    return {"is_duplicate": True, "existing_skill_id": s.skill_id, "reason": "exact_id_match"}
                if target_capability and target_capability.lower() in [c.lower() for c in s.capabilities]:
                    return {"is_duplicate": True, "existing_skill_id": s.skill_id, "reason": "exact_capability_overlap"}

        return {"is_duplicate": False, "existing_skill_id": None}


# Singleton instance
_evaluator_singleton: CandidateEvaluator | None = None


def get_candidate_evaluator() -> CandidateEvaluator:
    """Returns the singleton CandidateEvaluator instance."""
    global _evaluator_singleton
    if _evaluator_singleton is None:
        _evaluator_singleton = CandidateEvaluator()
    return _evaluator_singleton
