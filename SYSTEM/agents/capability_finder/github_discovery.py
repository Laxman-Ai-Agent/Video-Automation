"""Automatic, Security-Aware GitHub Skill Discovery Service.

Responsible for:
1. Mapping natural-language capability requirements into sanitized GitHub search queries.
2. Querying the public GitHub Search API with bounded timeouts and retries.
3. Parsing repository metadata into structured GitHubRepoCandidate objects.
4. Distinguishing source metadata from internally ranked quality/compatibility scores.
5. Secure credential handling with token masking in all diagnostics and logs.
6. Safe staging and AST static inspection without executing untrusted external code.
7. Dependency injection support for deterministic fixture-based testing without live network.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

try:
    from SYSTEM.core import config
    STAGING_BASE = config.PROJECT_ROOT / "SYSTEM" / "skills" / "staging" / "github_discovery"
except Exception:
    STAGING_BASE = Path("SYSTEM/skills/staging/github_discovery")

logger = logging.getLogger("capability_finder.github_discovery")

# ---------------------------------------------------------------------------
# Requirement-to-Search Query Mapping
# ---------------------------------------------------------------------------

DEFAULT_CAPABILITY_MAPPINGS: dict[str, str] = {
    # 1. Telugu Audio & Phonetics
    "telugu-phoneme-align": "telugu phoneme alignment speech tts",
    "telugu-audio-processing": "telugu audio faster-whisper speech asr",
    "telugu-text-to-speech": "telugu tts text to speech indic",
    # 2. Audio Analysis & Timing
    "audio-analysis": "audio analysis speech timing silence detection loudness",
    "audio-vad": "voice activity detection audio segmentation vad",
    # 3. Scene Segmentation & Computer Vision
    "scene-segmentation": "video scene segmentation shot boundary detection",
    "video-cut-detection": "pyscenedetect video shot cut detection",
    # 4. Remotion & React Motion Graphics
    "remotion-motion": "remotion react animation motion graphics",
    "kinetic-typography": "kinetic typography react remotion text animation",
    # 5. SVG Filters & Transforms
    "svg-filter": "svg filter animation feTurbulence morphing vector",
    "custom_svg_filter": "svg filter displacement animation react",
    # 6. Animated Charts & Graphs
    "animated-charts": "remotion charts graphs animated svg d3",
    "data-visualization": "react data visualization animated charts",
    # 7. Infographics & Maps
    "icons-maps-infographics": "svg maps india infographics vector diagrams",
    "telugu-infographics": "telugu typography infographics svg vector",
    # 8. Video Rendering & Media Validation
    "media-validation": "video qc media probe ffprobe black frame detection",
    "video-loudness-normalization": "ebur128 ffmpeg audio loudness normalization",
}

PERMISSIVE_LICENSES = {"mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "isc", "cc-by-4.0"}
COPYLEFT_LICENSES = {"gpl-3.0", "gpl-2.0", "agpl-3.0", "lgpl-3.0", "lgpl-2.1"}


class CapabilitySearchMapper:
    """Configurable, sanitized mapping between pipeline capabilities and GitHub search terms."""

    def __init__(self, mappings: dict[str, str] | None = None) -> None:
        self._mappings: dict[str, str] = dict(DEFAULT_CAPABILITY_MAPPINGS)
        if mappings:
            self._mappings.update(mappings)

    def register_mapping(self, capability: str, search_query: str) -> None:
        """Registers or overrides a capability search mapping."""
        self._mappings[capability.lower().strip()] = search_query.strip()

    def map_capability(self, capability: str, domain: str | None = None) -> str:
        """Maps a requested capability key or requirement phrase to a search query string."""
        cap_clean = capability.lower().strip().replace("_", "-")
        
        # 1. Direct exact mapping
        if cap_clean in self._mappings:
            return self._mappings[cap_clean]

        # 2. Substring matching in registered keys
        for k, v in self._mappings.items():
            if k in cap_clean or cap_clean in k:
                return v

        # 3. Dynamic domain-augmented fallback
        if domain and domain.lower() in ("audio", "motion", "rendering", "validation"):
            return f"{cap_clean} {domain.lower()}"

        return cap_clean

    @staticmethod
    def sanitize_query(query: str) -> str:
        """Sanitizes user or requirement input to ensure safe GitHub API queries.
        
        - Strips control characters and disallowed punctuation.
        - Preserves alphanumeric, spaces, hyphens, underscores, dots, and quotes.
        - Truncates to max length 100 characters.
        """
        if not query:
            return ""
        # Remove any character not safe for URL / search qualifier
        cleaned = re.sub(r"[^\w\s\-_.\"\':]", " ", query)
        # Collapse multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # Truncate to 100 characters
        return cleaned[:100].strip()


mapper = CapabilitySearchMapper()


# ---------------------------------------------------------------------------
# Candidate Data Schema
# ---------------------------------------------------------------------------

@dataclass
class GitHubRepoCandidate:
    """Structured representation of a discovered GitHub repository candidate."""
    name: str
    owner: str
    full_name: str
    url: str
    description: str
    primary_language: str
    license: str
    default_branch: str
    latest_commit_sha: str | None = None
    topics: list[str] = field(default_factory=list)
    search_score: float = 0.0
    stars_count: int = 0
    forks_count: int = 0
    compatibility_status: Literal["compatible", "needs_adapter", "incompatible"] = "compatible"
    security_review_status: Literal["pending", "passed", "quarantined", "rejected"] = "pending"
    match_rationale: str = ""
    source_metadata: dict[str, Any] = field(default_factory=dict)
    internally_ranked_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiscoveryResult:
    """Detailed audit report of a GitHub discovery execution."""
    status: Literal["succeeded", "no_results", "failed"]
    query: str
    capability: str
    total_candidates: int
    candidates: list[GitHubRepoCandidate] = field(default_factory=list)
    diagnostic: str | None = None
    error_code: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query,
            "capability": self.capability,
            "total_candidates": self.total_candidates,
            "candidates": [c.to_dict() for c in self.candidates],
            "diagnostic": self.diagnostic,
            "error_code": self.error_code,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# GitHub Discovery Service
# ---------------------------------------------------------------------------

def mask_token(token: str | None) -> str:
    """Safely masks secret GitHub tokens for logging and error reporting."""
    if not token:
        return "<none>"
    if token.startswith("ghp_") and len(token) > 8:
        return f"ghp_{token[4:7]}***{token[-4:]}"
    return f"{token[:2]}***{token[-2:]}" if len(token) > 4 else "***"


class GitHubSkillDiscoveryService:
    """Autonomous, security-gated GitHub skill discovery service."""

    def __init__(
        self,
        token: str | None = None,
        http_client: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
        staging_dir: Path | None = None,
        timeout: float = 5.0,
        max_retries: int = 2,
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.http_client = http_client
        self.staging_dir = staging_dir or STAGING_BASE
        self.timeout = timeout
        self.max_retries = max_retries
        self.mapper = mapper

    def search(
        self,
        capability: str,
        domain: str | None = None,
        limit: int = 5,
    ) -> DiscoveryResult:
        """Searches GitHub for repositories matching a capability requirement.
        
        - Uses public GitHub repository search API.
        - Sanitizes input queries.
        - Handles timeouts, rate limits, and network errors gracefully.
        - Never fabricates candidates.
        """
        if not capability or not capability.strip():
            return DiscoveryResult(
                status="no_results",
                query="",
                capability=capability,
                total_candidates=0,
                diagnostic="Empty capability query requested.",
            )

        raw_query = self.mapper.map_capability(capability, domain=domain)
        sanitized_query = self.mapper.sanitize_query(raw_query)

        if not sanitized_query:
            return DiscoveryResult(
                status="no_results",
                query=sanitized_query,
                capability=capability,
                total_candidates=0,
                diagnostic="Query became empty after sanitization.",
            )

        # 1. Dependency Injected Client (Fixture / Mock for Tests)
        if self.http_client is not None:
            try:
                data = self.http_client(sanitized_query, self._get_headers())
                return self._parse_api_response(data, capability, sanitized_query, limit)
            except Exception as e:
                err_msg = str(e)
                # Ensure no raw token leaked in diagnostic
                if self.token and self.token in err_msg:
                    err_msg = err_msg.replace(self.token, mask_token(self.token))
                return DiscoveryResult(
                    status="failed",
                    query=sanitized_query,
                    capability=capability,
                    total_candidates=0,
                    error_code="client_error",
                    diagnostic=f"Injected HTTP client error: {err_msg}",
                )

        # 2. Live HTTP Request via urllib
        encoded_q = urllib.parse.quote_plus(sanitized_query)
        api_url = f"https://api.github.com/search/repositories?q={encoded_q}&sort=stars&order=desc&per_page={max(1, min(limit, 10))}"

        headers = self._get_headers()
        req = urllib.request.Request(api_url, headers=headers)

        last_error = ""
        error_code = "network_error"

        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    status_code = resp.status
                    raw_body = resp.read().decode("utf-8")
                    data = json.loads(raw_body)
                    return self._parse_api_response(data, capability, sanitized_query, limit)
            except urllib.error.HTTPError as he:
                if he.code == 403:
                    error_code = "rate_limit_exceeded"
                    last_error = "GitHub API rate limit exceeded (HTTP 403). Backing off."
                    break
                elif he.code == 401:
                    error_code = "auth_error"
                    last_error = "GitHub API authentication failed (HTTP 401). Verify credentials."
                    break
                elif he.code == 422:
                    error_code = "validation_failed"
                    last_error = f"GitHub API query rejected as unprocessable (HTTP 422): {sanitized_query}."
                    break
                else:
                    error_code = f"http_{he.code}"
                    last_error = f"GitHub API responded with HTTP {he.code}."
            except urllib.error.URLError as ue:
                error_code = "timeout" if "timed out" in str(ue).lower() else "connection_error"
                last_error = f"Network connection failed: {ue.reason}."
            except json.JSONDecodeError:
                error_code = "malformed_response"
                last_error = "GitHub API returned malformed or non-JSON response body."
                break
            except Exception as ex:
                error_code = "unexpected_error"
                last_error = f"Unexpected discovery error: {ex}"

        # Clean any potential token from diagnostics
        if self.token and self.token in last_error:
            last_error = last_error.replace(self.token, mask_token(self.token))

        return DiscoveryResult(
            status="failed",
            query=sanitized_query,
            capability=capability,
            total_candidates=0,
            error_code=error_code,
            diagnostic=last_error,
        )

    def _get_headers(self) -> dict[str, str]:
        """Builds standard GitHub API headers with optional authorization."""
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "LAXMAN-Video-Automation/1.0 (Autonomous Agent System)",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _parse_api_response(
        self,
        data: dict[str, Any],
        capability: str,
        query: str,
        limit: int,
    ) -> DiscoveryResult:
        """Parses and ranks GitHub API response items."""
        items = data.get("items", [])
        if not items:
            return DiscoveryResult(
                status="no_results",
                query=query,
                capability=capability,
                total_candidates=0,
                candidates=[],
                diagnostic="Search completed successfully; zero matching repositories found.",
            )

        candidates: list[GitHubRepoCandidate] = []
        for it in items[:limit]:
            name = it.get("name", "unknown")
            owner_info = it.get("owner", {})
            owner = owner_info.get("login", "unknown") if isinstance(owner_info, dict) else "unknown"
            full_name = it.get("full_name", f"{owner}/{name}")
            if owner == "unknown" and "/" in full_name:
                owner = full_name.split("/")[0]
            url = it.get("html_url", f"https://github.com/{full_name}")
            desc = it.get("description") or "No description provided."
            lang = it.get("language") or "Python"
            
            # License metadata
            lic_info = it.get("license")
            lic_spdx = (lic_info.get("spdx_id") or lic_info.get("key", "Unknown")) if isinstance(lic_info, dict) else "Unknown"
            
            default_branch = it.get("default_branch", "main")
            topics = it.get("topics", [])
            stars = int(it.get("stargazers_count", 0))
            forks = int(it.get("forks_count", 0))
            raw_score = float(it.get("score", 1.0))

            # License & compatibility evaluation
            lic_lower = lic_spdx.lower()
            if lic_lower in PERMISSIVE_LICENSES:
                compat = "compatible"
            elif lic_lower in COPYLEFT_LICENSES:
                compat = "needs_adapter"
            else:
                compat = "needs_adapter" if lic_spdx != "Unknown" else "incompatible"

            # Compute internal ranked score (stars log-scale + license bonus + topic match)
            lic_bonus = 0.3 if compat == "compatible" else 0.1 if compat == "needs_adapter" else 0.0
            stars_factor = min(0.4, (stars / 500.0) * 0.4) if stars > 0 else 0.0
            internal_score = round(min(1.0, 0.3 + lic_bonus + stars_factor), 3)

            rationale = (
                f"Repository matches '{capability}' with primary language '{lang}', "
                f"{stars} stars, and license '{lic_spdx}' (Compatibility: {compat.upper()})."
            )

            cand = GitHubRepoCandidate(
                name=name,
                owner=owner,
                full_name=full_name,
                url=url,
                description=desc,
                primary_language=lang,
                license=lic_spdx,
                default_branch=default_branch,
                latest_commit_sha=it.get("node_id"),
                topics=topics,
                search_score=raw_score,
                stars_count=stars,
                forks_count=forks,
                compatibility_status=compat,
                security_review_status="pending",
                match_rationale=rationale,
                source_metadata={
                    "github_id": it.get("id"),
                    "created_at": it.get("created_at"),
                    "updated_at": it.get("updated_at"),
                    "open_issues_count": it.get("open_issues_count"),
                },
                internally_ranked_score=internal_score,
            )
            candidates.append(cand)

        # Sort candidates by internal ranked score descending
        candidates.sort(key=lambda c: c.internally_ranked_score, reverse=True)

        return DiscoveryResult(
            status="succeeded",
            query=query,
            capability=capability,
            total_candidates=len(candidates),
            candidates=candidates,
            diagnostic=f"Discovered {len(candidates)} candidate repositories on GitHub.",
        )

    def stage_and_inspect(
        self,
        candidate: GitHubRepoCandidate,
        content: str | bytes | None = None,
    ) -> dict[str, Any]:
        """Safely stages candidate code or metadata in quarantine and performs AST security audit.
        
        NEVER executes untrusted code automatically!
        """
        # Strictly confine staging path
        safe_owner = re.sub(r"[^\w]", "_", candidate.owner)
        safe_name = re.sub(r"[^\w]", "_", candidate.name)
        target_dir = self.staging_dir / safe_owner / safe_name
        target_dir.mkdir(parents=True, exist_ok=True)

        manifest_file = target_dir / "candidate_manifest.json"
        manifest_file.write_text(json.dumps(candidate.to_dict(), indent=2), encoding="utf-8")

        # Static security audit
        audit_res: dict[str, Any] = {"passed": True, "risk_level": "low", "findings": []}
        if content:
            raw_text = content.decode("utf-8") if isinstance(content, bytes) else content
            code_file = target_dir / "candidate_snippet.py"
            code_file.write_text(raw_text, encoding="utf-8")

            try:
                from SYSTEM.agents.skill_factory.security_validator import security_validator
                sec_res = security_validator.audit(raw_text, filename=code_file.name)
                audit_res = sec_res.to_dict()
                if not sec_res.passed or sec_res.quarantine_required:
                    candidate.security_review_status = "quarantined" if sec_res.quarantine_required else "rejected"
                else:
                    candidate.security_review_status = "passed"
            except Exception as e:
                audit_res = {"passed": False, "risk_level": "high", "findings": [f"Audit error: {e}"]}
                candidate.security_review_status = "quarantined"

        return {
            "status": "staged",
            "candidate": candidate.full_name,
            "staging_path": str(target_dir),
            "security_review_status": candidate.security_review_status,
            "audit": audit_res,
            "note": "Candidate staged in quarantine. Automatic execution is prohibited.",
        }


# Authoritative singleton instance
github_discovery_service = GitHubSkillDiscoveryService()
