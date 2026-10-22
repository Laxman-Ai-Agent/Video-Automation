"""Static AST-based Source Code Discovery Engine for Capability Finder.

Safely inspects Python source files without executing code or importing modules.
Extracts:
1. Class and function definitions with line ranges.
2. Docstrings and signatures (arguments, type annotations, return types).
3. Advertised capabilities, attributes, and tool references.
4. Cryptographic file hashes and incremental mtime caching.
"""
from __future__ import annotations

import ast
import hashlib
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("ast_scanner")


@dataclass
class AstDiscoveredItem:
    """Represents a code element (class, function, or method) discovered via AST."""
    item_id: str
    name: str
    kind: Literal["class", "function", "method"]
    file_path: str
    line_start: int
    line_end: int
    docstring: str = ""
    args: list[str] = field(default_factory=list)
    return_type: str = ""
    advertised_capabilities: list[str] = field(default_factory=list)
    imported_tools: list[str] = field(default_factory=list)
    file_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AstScanner:
    """Thread-safe static AST inspector with incremental mtime caching."""

    def __init__(self) -> None:
        # Cache keyed by (file_path_str, mtime, size) -> list[AstDiscoveredItem]
        self._cache: dict[tuple[str, float, int], list[AstDiscoveredItem]] = {}

    def scan_file(self, file_path: Path) -> list[AstDiscoveredItem]:
        """Safely parses a single Python file into discovered AST items."""
        if not file_path.exists() or not file_path.suffix == ".py":
            return []

        stat = file_path.stat()
        cache_key = (str(file_path), stat.st_mtime, stat.st_size)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            raw_bytes = file_path.read_bytes()
            file_hash = hashlib.sha256(raw_bytes).hexdigest()
            content = raw_bytes.decode("utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            logger.warning(f"Failed to parse AST for {file_path}: {e}")
            return []

        items: list[AstDiscoveredItem] = []
        imports_found: list[str] = []

        # First pass: collect top-level imports
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports_found.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports_found.append(node.module)

        # Second pass: collect classes and functions
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cls_caps = self._extract_class_capabilities(node)
                doc = ast.get_docstring(node) or ""
                item = AstDiscoveredItem(
                    item_id=f"{file_path.stem}.{node.name}",
                    name=node.name,
                    kind="class",
                    file_path=str(file_path),
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    docstring=doc,
                    advertised_capabilities=cls_caps,
                    imported_tools=list(set(imports_found)),
                    file_hash=file_hash,
                )
                items.append(item)

                # Scan methods
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_args = [a.arg for a in member.args.args if a.arg != "self"]
                        ret_type = self._format_annotation(member.returns)
                        method_doc = ast.get_docstring(member) or ""
                        m_item = AstDiscoveredItem(
                            item_id=f"{file_path.stem}.{node.name}.{member.name}",
                            name=f"{node.name}.{member.name}",
                            kind="method",
                            file_path=str(file_path),
                            line_start=member.lineno,
                            line_end=getattr(member, "end_lineno", member.lineno),
                            docstring=method_doc,
                            args=method_args,
                            return_type=ret_type,
                            file_hash=file_hash,
                        )
                        items.append(m_item)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_args = [a.arg for a in node.args.args]
                ret_type = self._format_annotation(node.returns)
                fn_doc = ast.get_docstring(node) or ""
                fn_caps = self._extract_docstring_capabilities(fn_doc)
                item = AstDiscoveredItem(
                    item_id=f"{file_path.stem}.{node.name}",
                    name=node.name,
                    kind="function",
                    file_path=str(file_path),
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    docstring=fn_doc,
                    args=fn_args,
                    return_type=ret_type,
                    advertised_capabilities=fn_caps,
                    imported_tools=list(set(imports_found)),
                    file_hash=file_hash,
                )
                items.append(item)

        self._cache[cache_key] = items
        return items

    def scan_directory(self, root_dir: Path, max_depth: int = 4) -> list[AstDiscoveredItem]:
        """Recursively scans Python files in a directory up to max_depth."""
        if not root_dir.exists() or not root_dir.is_dir():
            return []

        all_items: list[AstDiscoveredItem] = []
        for path in root_dir.rglob("*.py"):
            # Exclude tests, pycache, .venv
            rel_parts = path.relative_to(root_dir).parts
            if any(p in (".venv", "__pycache__", ".git") for p in rel_parts):
                continue
            if len(rel_parts) > max_depth + 1:
                continue
            all_items.extend(self.scan_file(path))
        return all_items

    def _extract_class_capabilities(self, node: ast.ClassDef) -> list[str]:
        """Extracts advertised capabilities from class attributes or init assignments."""
        caps: list[str] = []
        for item in node.body:
            # Check class-level attributes like capabilities = ["...", "..."]
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id in ("capabilities", "skills"):
                        if isinstance(item.value, (ast.List, ast.Tuple)):
                            for el in item.value.elts:
                                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                                    caps.append(el.value)

            # Check inside __init__ metadata assignment
            elif isinstance(item, ast.FunctionDef) and item.name == "__init__":
                for stmt in item.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name) and target.id == "metadata":
                                if isinstance(stmt.value, ast.Call):
                                    for kw in stmt.value.keywords:
                                        if kw.arg in ("capabilities", "skills") and isinstance(kw.value, (ast.List, ast.Tuple)):
                                            for el in kw.value.elts:
                                                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                                                    caps.append(el.value)
        return caps

    def _extract_docstring_capabilities(self, doc: str) -> list[str]:
        """Heuristically extracts key tags from docstrings."""
        if not doc:
            return []
        caps = []
        lines = doc.splitlines()
        for line in lines:
            line_str = line.strip().lower()
            if line_str.startswith("capabilities:") or line_str.startswith("skills:"):
                raw_caps = line_str.split(":", 1)[1]
                caps.extend([c.strip().strip('"\'') for c in raw_caps.split(",") if c.strip()])
        return caps

    def _format_annotation(self, node: ast.AST | None) -> str:
        """Converts an AST type annotation node to readable string."""
        if node is None:
            return ""
        try:
            return ast.unparse(node)
        except Exception:
            return ""


ast_scanner = AstScanner()
