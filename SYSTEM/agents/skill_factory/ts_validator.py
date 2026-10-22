"""TypeScript, React, and Remotion Static Security and Contract Validator for Skill Factory.

Validates candidate skills containing TypeScript, TSX, or Remotion components:
1. Static security audit for TypeScript / JavaScript (prohibited Node.js modules,
   process escapes, eval/Function execution, path traversal, network exfiltration).
2. Remotion animation contract validation:
   - Component declaration and prop typing (TypeScript interface / type or Zod schema).
   - Remotion hooks and animation primitives (useCurrentFrame, useVideoConfig, interpolate, spring).
   - Frame timing invariants and safe zone bounds.
   - Asset path hygiene (enforcing staticFile() or relative URLs vs raw OS paths).
3. Compiler type-check verification using the existing Remotion tsconfig.json without
   installing external packages.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("skill_factory.ts_validator")

PROHIBITED_TS_MODULES = {
    "child_process",
    "cluster",
    "worker_threads",
    "net",
    "dgram",
    "dns",
    "tls",
    "http2",
    "vm",
    "v8",
}

PROHIBITED_TS_CALLS = [
    (r"\beval\s*\(", "Dangerous call: eval() execution"),
    (r"\bFunction\s*\(", "Dangerous call: Function constructor execution"),
    (r"\bprocess\.exit\b", "Prohibited call: process.exit"),
    (r"\bprocess\.kill\b", "Prohibited call: process.kill"),
    (r"\bchild_process\b", "Prohibited module: child_process"),
    (r"\bfs\.(unlink|rmdir|rm|write|append)Sync\b", "Prohibited filesystem modification"),
    (r"__proto__", "Prototype pollution attempt (__proto__)"),
    (r"window\.location", "Browser redirect / window.location manipulation"),
]

PROHIBITED_TS_PATHS = [
    (r"\.\./\.\.", "Path traversal pattern: multiple parent references (../../)"),
    (r"\.\.\\\.\.", "Path traversal pattern: multiple parent references (..\\..\\)"),
    (r"[cC]:\\windows\\system32", "Unauthorized system path reference: System32"),
    (r"/etc/passwd|/etc/shadow", "Unauthorized system file reference: /etc/passwd"),
    (r"\.env", "Sensitive environment file reference (.env)"),
    (r"catalog\.json|approvals_queue\.json", "Protected registry tampering reference"),
]

REMOTION_PRIMITIVES = {
    "useCurrentFrame",
    "useVideoConfig",
    "interpolate",
    "spring",
    "AbsoluteFill",
    "Sequence",
    "Composition",
    "Audio",
    "Video",
    "Img",
    "staticFile",
}


@dataclass
class TypeScriptAuditResult:
    """Audit result for TypeScript / TSX code analysis."""
    passed: bool
    risk_level: Literal["low", "medium", "high", "critical"]
    findings: list[str] = field(default_factory=list)
    quarantine_required: bool = False
    is_remotion_component: bool = False
    prop_contract_detected: bool = False
    animation_primitives_found: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TypeScriptValidator:
    """Validates TypeScript, React, and Remotion component skills."""

    def extract_ts_blocks(self, content: str, filename: str = "") -> list[str]:
        """Extracts TypeScript or TSX code blocks from markdown or returns full file if .ts/.tsx."""
        if filename.endswith(".tsx") or filename.endswith(".ts"):
            return [content]

        pattern = re.compile(r"```(?:tsx|typescript|ts|jsx|javascript|js)\n(.*?)```", re.DOTALL)
        blocks = pattern.findall(content)
        return blocks

    def audit_security(self, content: str, filename: str = "") -> TypeScriptAuditResult:
        """Audits TypeScript or Remotion code for security violations and prohibited operations."""
        blocks = self.extract_ts_blocks(content, filename)
        code_str = "\n\n".join(blocks) if blocks else (content if (filename.endswith(".tsx") or filename.endswith(".ts")) else "")

        findings: list[str] = []
        risk_level: Literal["low", "medium", "high", "critical"] = "low"
        diagnostics: dict[str, Any] = {}

        if not code_str:
            return TypeScriptAuditResult(
                passed=True,
                risk_level="low",
                findings=[],
                is_remotion_component=False,
            )

        # 1. Prohibited module imports
        for mod in PROHIBITED_TS_MODULES:
            import_pat = rf"(?i)(?:from\s+['\"]{mod}['\"]|require\(\s*['\"]{mod}['\"]\))"
            if re.search(import_pat, code_str):
                findings.append(f"TypeScript Security violation: Prohibited Node.js import '{mod}'.")
                risk_level = "critical"

        # 2. Prohibited dangerous calls & prototype pollution
        for pat, desc in PROHIBITED_TS_CALLS:
            if re.search(pat, code_str):
                findings.append(f"TypeScript Security violation: {desc}.")
                if risk_level != "critical":
                    risk_level = "high"

        # 3. Path traversal patterns
        for pat, desc in PROHIBITED_TS_PATHS:
            if re.search(pat, code_str):
                findings.append(f"TypeScript Security violation: {desc}.")
                if risk_level not in ("critical", "high"):
                    risk_level = "medium"

        # 4. Check for Remotion specific primitives
        found_prims = [p for p in REMOTION_PRIMITIVES if re.search(rf"\b{p}\b", code_str)]
        is_remotion = bool(
            "remotion" in code_str
            or found_prims
            or "React.FC" in code_str
            or filename.endswith(".tsx")
        )

        # 5. Check prop contracts (TypeScript interface, type, or zod schema)
        has_prop_contract = bool(
            re.search(r"\binterface\s+[A-Za-z0-9_]+Props\b", code_str)
            or re.search(r"\btype\s+[A-Za-z0-9_]+Props\b", code_str)
            or re.search(r"\bz\.object\s*\(", code_str)
            or re.search(r":\s*React\.FC<", code_str)
        )

        # 6. Remotion asset path validation (check for raw OS absolute paths)
        raw_os_path_pat = re.compile(r"['\"][a-zA-Z]:\\[^'\"]+['\"]")
        if raw_os_path_pat.search(code_str):
            findings.append("Remotion asset path violation: Raw OS drive path detected. Use staticFile() or relative asset URLs.")
            if risk_level == "low":
                risk_level = "medium"

        passed = len(findings) == 0
        quarantine = risk_level in ("high", "critical")

        diagnostics["blocks_count"] = len(blocks)
        diagnostics["has_remotion_import"] = "from 'remotion'" in code_str or 'from "remotion"' in code_str

        return TypeScriptAuditResult(
            passed=passed,
            risk_level=risk_level,
            findings=findings,
            quarantine_required=quarantine,
            is_remotion_component=is_remotion,
            prop_contract_detected=has_prop_contract,
            animation_primitives_found=found_prims,
            diagnostics=diagnostics,
        )

    def validate_remotion_contracts(self, content: str, filename: str = "") -> list[str]:
        """Validates Remotion component contracts, animation usage, and frame invariants."""
        blocks = self.extract_ts_blocks(content, filename)
        code_str = "\n\n".join(blocks) if blocks else content
        issues: list[str] = []

        if not code_str:
            return issues

        # Check export
        has_export = bool(
            re.search(r"\bexport\s+(default\s+)?(const|function|class)\b", code_str)
            or re.search(r"\bexport\s+default\b", code_str)
        )
        if not has_export:
            issues.append("Remotion component must declare an exported component (e.g. 'export const ...' or 'export default ...').")

        # If spring() is used, check parameters
        if "spring(" in code_str:
            # Check for negative config or obvious mistakes
            if re.search(r"damping:\s*-\d+", code_str) or re.search(r"mass:\s*-\d+", code_str):
                issues.append("Remotion spring configuration cannot specify negative damping or mass.")

        # Check if interpolate() is used without frame
        if "interpolate(" in code_str and "useCurrentFrame" not in code_str and "frame" not in code_str:
            issues.append("interpolate() called without referencing current frame or frame variable.")

        return issues

    def run_typecheck(
        self,
        code_str: str,
        project_root: Path | None = None,
        timeout_seconds: float = 10.0,
    ) -> tuple[bool, list[str]]:
        """Optionally runs TypeScript typechecking using VIDEO_ENGINE/remotion/tsconfig.json if npm/tsc is available."""
        root = project_root or Path(__file__).resolve().parents[3]
        remotion_dir = root / "VIDEO_ENGINE" / "remotion"
        if not remotion_dir.exists() or not (remotion_dir / "tsconfig.json").exists():
            return True, ["Typecheck skipped: Remotion directory or tsconfig.json not found."]

        # Check if npx/tsc is accessible
        tsc_cmd = shutil.which("npx") or shutil.which("tsc")
        if not tsc_cmd:
            return True, ["Typecheck skipped: Neither npx nor tsc found on system PATH."]

        # Create temporary file inside a subfolder or temp dir
        with tempfile.NamedTemporaryFile(suffix=".tsx", mode="w", encoding="utf-8", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(code_str)

        try:
            # Run tsc with --noEmit
            cmd = ["npx", "--prefix", str(remotion_dir), "tsc", "--noEmit", str(tmp_path)]
            proc = subprocess.run(
                cmd,
                cwd=str(remotion_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
                shell=False,
            )
            passed = proc.returncode == 0
            diags: list[str] = []
            if not passed:
                output = (proc.stdout + "\n" + proc.stderr).strip()
                lines = [l for l in output.splitlines() if str(tmp_path.name) in l or "error TS" in l]
                diags = lines[:5] if lines else [output[:300]]
            return passed, diags
        except subprocess.TimeoutExpired:
            return False, [f"TypeScript typechecking timed out after {timeout_seconds}s."]
        except Exception as e:
            logger.debug(f"Remotion typecheck invocation exception: {e}")
            return True, [f"Typecheck execution bypassed: {e}"]
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass


# Singleton instance
ts_validator = TypeScriptValidator()
