"""Static Security and Code Safety Validator for Skill Factory.

Performs:
1. Multi-tier pattern inspection (prompt injection, token exfiltration, shell commands).
2. Deep AST structural analysis for embedded Python blocks and standalone code.
3. Frozen pipeline file tampering detection.
4. Direct approval/registry bypass detection.
5. Path traversal and unauthorized filesystem access detection.
"""
from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from SYSTEM.core.resilience import CREDENTIAL_KINDS, redact_secrets

SkillRiskLevel = Literal["low", "medium", "high", "critical"]

FROZEN_PIPELINE_FILES = {
    "transcribe.py",
    "transcript_review.py",
    "scene_segmentation.py",
    "VIDEO_ENGINE/stages/transcribe.py",
    "VIDEO_ENGINE/stages/transcript_review.py",
    "VIDEO_ENGINE/stages/scene_segmentation.py",
}

DISALLOWED_IMPORTS = {
    "ctypes",
    "socket",
    "paramiko",
    "winreg",
    "pty",
    "multiprocessing",
    "signal",
}

DANGEROUS_CALLS = {
    "os.system",
    "os.popen",
    "os.spawn",
    "subprocess.Popen",
    "subprocess.run",
    "subprocess.call",
    "eval",
    "exec",
    "__import__",
    "compile",
}


@dataclass
class SecurityAuditResult:
    """Detailed audit report produced by SecurityValidator."""
    passed: bool
    risk_level: SkillRiskLevel
    findings: list[str] = field(default_factory=list)
    quarantine_required: bool = False
    ast_checked: bool = False
    audited_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    filename: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SecurityValidator:
    """Authoritative static security validator for candidate skills."""

    def audit(
        self,
        content: str,
        filename: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SecurityAuditResult:
        """Audits skill markdown or python code for security violations."""
        findings: list[str] = []
        risk_level: SkillRiskLevel = "low"
        ast_inspected = False
        diagnostics: dict[str, Any] = {}

        # -------------------------------------------------------------
        # 1. Prompt Injection Checks
        # -------------------------------------------------------------
        injection_patterns = [
            (r"(?i)ignore\s+all\s+(previous|prior)\s+instructions", "Prompt injection: ignore previous instructions"),
            (r"(?i)system\s+prompt\s+override", "Prompt injection: system prompt override attempt"),
            (r"(?i)you\s+are\s+now\s+in\s+developer\s+mode", "Prompt injection: developer mode escape"),
            (r"(?i)disregard\s+(system\s+)?rules", "Prompt injection: disregard rules"),
            (r"(?i)jailbreak\s+instruction", "Prompt injection: explicit jailbreak attempt"),
        ]
        for pattern, desc in injection_patterns:
            if re.search(pattern, content):
                findings.append(desc)
                risk_level = "critical"

        # -------------------------------------------------------------
        # 2. Frozen Pipeline Tampering Checks
        # -------------------------------------------------------------
        for f in FROZEN_PIPELINE_FILES:
            if f.lower() in content.lower():
                # Check if referenced with intent to modify
                tamper_pattern = re.compile(
                    rf"(?i)(modify|alter|overwrite|patch|rewrite|delete|remove|replace)\s+.*{re.escape(f)}"
                )
                if tamper_pattern.search(content) or "open(" in content:
                    findings.append(f"Security violation: Attempt to tamper with frozen pipeline file '{f}'.")
                    risk_level = "critical"

        # -------------------------------------------------------------
        # 3. Direct Registry & Approval Bypass Checks
        # -------------------------------------------------------------
        bypass_targets = ["catalog.json", "approvals_queue.json", "approvals_audit.jsonl"]
        for target in bypass_targets:
            if target in content and any(w in content.lower() for w in ["write", "replace", "unlink", "delete", "dump"]):
                findings.append(f"Security violation: Attempt to directly bypass/alter protected registry '{target}'.")
                risk_level = "critical"

        # -------------------------------------------------------------
        # 4. Dangerous Execution / Shell Commands (Pattern)
        # -------------------------------------------------------------
        dangerous_patterns = [
            (r"(?i)\bos\.system\s*\(", "Dangerous call: os.system execution"),
            (r"(?i)\bsubprocess\.(Popen|run|call)\b.*shell\s*=\s*True", "Dangerous call: subprocess with shell=True"),
            (r"(?i)\beval\s*\(", "Dangerous call: eval() execution"),
            (r"(?i)\bexec\s*\(", "Dangerous call: exec() execution"),
            (r"(?i)\brm\s+-rf\b", "Dangerous command: rm -rf"),
            (r"(?i)\bformat\s+[a-zA-Z]:", "Dangerous command: drive formatting"),
            (r"(?i)\bmkfs\b", "Dangerous command: filesystem format (mkfs)"),
            (r"(?i)\bcurl\s+.*\|\s*(bash|sh)\b", "Dangerous pattern: piping remote curl into shell"),
            (r"(?i)\bwget\s+.*\|\s*(bash|sh)\b", "Dangerous pattern: piping remote wget into shell"),
        ]
        for pattern, desc in dangerous_patterns:
            if re.search(pattern, content):
                findings.append(desc)
                if risk_level != "critical":
                    risk_level = "high"

        # -------------------------------------------------------------
        # 5. Secret / Token Exposure Patterns
        # -------------------------------------------------------------
        for kind in sorted(CREDENTIAL_KINDS.intersection(redact_secrets(content)[1])):
            findings.append(f"Exposed secret: {kind} pattern")
            risk_level = "critical"

        # -------------------------------------------------------------
        # 6. Path Traversal & System Escape Patterns
        # -------------------------------------------------------------
        traversal_patterns = [
            (r"\.\./\.\.", "Path traversal pattern: multiple parent references (../../)"),
            (r"\.\.\\\.\.", "Path traversal pattern: multiple parent references (..\\..\\)"),
            (r"(?i)c:\\windows\\system32", "Unauthorized system path reference: System32"),
            (r"/etc/passwd|/etc/shadow", "Unauthorized system file reference: /etc/passwd"),
            (r"\.env|\.git/config", "Sensitive configuration file reference"),
        ]
        for pattern, desc in traversal_patterns:
            if re.search(pattern, content):
                findings.append(desc)
                if risk_level not in ("critical", "high"):
                    risk_level = "medium"

        # -------------------------------------------------------------
        # 7. Structural AST Analysis (Python)
        # -------------------------------------------------------------
        code_blocks = self._extract_python_blocks(content, filename)
        if code_blocks:
            ast_inspected = True
            for idx, block in enumerate(code_blocks):
                ast_findings = self._inspect_ast(block)
                if ast_findings:
                    findings.extend(ast_findings)
                    if risk_level != "critical":
                        risk_level = "high"

        # -------------------------------------------------------------
        # 8. Structural & Security Analysis (TypeScript / Remotion TSX)
        # -------------------------------------------------------------
        from SYSTEM.agents.skill_factory.ts_validator import ts_validator
        ts_blocks = ts_validator.extract_ts_blocks(content, filename)
        if ts_blocks or filename.endswith(".tsx") or filename.endswith(".ts"):
            ts_res = ts_validator.audit_security(content, filename=filename)
            if ts_res.findings:
                findings.extend(ts_res.findings)
                if ts_res.risk_level == "critical" or risk_level == "critical":
                    risk_level = "critical"
                elif ts_res.risk_level == "high" or risk_level == "high":
                    risk_level = "high"
                elif ts_res.risk_level == "medium" and risk_level == "low":
                    risk_level = "medium"
            diagnostics["typescript_audit"] = ts_res.to_dict()

        quarantine = risk_level in ("high", "critical")
        passed = len(findings) == 0

        return SecurityAuditResult(
            passed=passed,
            risk_level=risk_level,
            findings=findings,
            quarantine_required=quarantine,
            ast_checked=ast_inspected or bool(ts_blocks),
            filename=filename,
            diagnostics=diagnostics,
        )

    def _extract_python_blocks(self, content: str, filename: str) -> list[str]:
        """Extracts python code blocks from markdown or treats whole file as python if .py."""
        if filename.endswith(".py"):
            return [content]

        # Extract ```python ... ``` blocks
        pattern = re.compile(r"```(?:python|py)\n(.*?)```", re.DOTALL)
        return pattern.findall(content)

    def _inspect_ast(self, code_str: str) -> list[str]:
        """Performs structural AST traversal to detect forbidden imports and calls."""
        findings: list[str] = []
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            findings.append(f"AST syntax error in embedded code block: {e}")
            return findings

        for node in ast.walk(tree):
            # Check Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod in DISALLOWED_IMPORTS:
                        findings.append(f"AST Security violation: Disallowed import '{alias.name}'.")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_mod = node.module.split(".")[0]
                    if root_mod in DISALLOWED_IMPORTS:
                        findings.append(f"AST Security violation: Disallowed import from '{node.module}'.")

            # Check Function Calls
            elif isinstance(node, ast.Call):
                func_name = self._resolve_call_name(node.func)
                if func_name in DANGEROUS_CALLS:
                    findings.append(f"AST Security violation: Dangerous function call '{func_name}()'.")

                # Check subprocess with shell=True
                if "subprocess" in func_name:
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            findings.append("AST Security violation: subprocess execution with shell=True.")

            # Check Sandbox escape reflection attributes
            elif isinstance(node, ast.Attribute):
                if node.attr in ("__subclasses__", "__globals__", "__code__"):
                    findings.append(f"AST Security violation: Sandbox escape reflection attribute '{node.attr}'.")

        return findings

    def _resolve_call_name(self, node: ast.AST) -> str:
        """Resolves dotted call name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            base = self._resolve_call_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""


# Authoritative singleton instance
security_validator = SecurityValidator()
