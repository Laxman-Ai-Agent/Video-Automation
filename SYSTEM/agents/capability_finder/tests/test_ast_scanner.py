"""Unit tests for AstScanner."""
from __future__ import annotations

from pathlib import Path
from SYSTEM.agents.capability_finder.discovery.ast_scanner import AstScanner


def test_ast_scanner_file_extraction(tmp_path: Path):
    scanner = AstScanner()
    code = '''"""Sample module docstring."""
import os
from SYSTEM.registries import tool_registry

class SampleAgent:
    """Sample agent class."""
    capabilities = ["audio-processing", "speech-filter"]

    def __init__(self):
        pass

    def process(self, audio_data: bytes) -> str:
        """Process audio method."""
        return "processed"

def standalone_func(x: int) -> bool:
    """Capabilities: math-operation, calculation"""
    return x > 0
'''
    py_file = tmp_path / "sample_module.py"
    py_file.write_text(code, encoding="utf-8")

    items = scanner.scan_file(py_file)
    assert len(items) >= 3  # class, method, function

    # Check class item
    cls_item = next(i for i in items if i.kind == "class")
    assert cls_item.name == "SampleAgent"
    assert "audio-processing" in cls_item.advertised_capabilities
    assert "SYSTEM.registries" in cls_item.imported_tools
    assert len(cls_item.file_hash) == 64

    # Check method item
    m_item = next(i for i in items if i.name == "SampleAgent.process")
    assert m_item.name == "SampleAgent.process"
    assert "audio_data" in m_item.args
    assert m_item.return_type == "str"

    # Check function item
    fn_item = next(i for i in items if i.kind == "function")
    assert fn_item.name == "standalone_func"
    assert "math-operation" in fn_item.advertised_capabilities


def test_ast_scanner_incremental_cache(tmp_path: Path):
    scanner = AstScanner()
    py_file = tmp_path / "cached_module.py"
    py_file.write_text("class CachedClass:\n    pass\n", encoding="utf-8")

    items1 = scanner.scan_file(py_file)
    items2 = scanner.scan_file(py_file)
    assert items1 is items2  # Exact cached object returned


def test_ast_scanner_directory(tmp_path: Path):
    scanner = AstScanner()
    sub_dir = tmp_path / "pkg"
    sub_dir.mkdir()
    (sub_dir / "mod1.py").write_text("def f1(): pass\n", encoding="utf-8")
    (sub_dir / "mod2.py").write_text("def f2(): pass\n", encoding="utf-8")

    items = scanner.scan_directory(sub_dir)
    assert len(items) == 2
    names = {i.name for i in items}
    assert names == {"f1", "f2"}
