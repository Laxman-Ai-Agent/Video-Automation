"""The catalog of every deterministic rule of the stages, read from the stages' own source (so it can never list a rule that is not there, or miss one that is added): each place where a stage
records a rule is found with `ast` and its name, severity and what it says are taken from that call. A rule is `(stage_id, name)`, the same pair `rule_switches` is keyed by.

Where a stage records its rules (the ONE place each, where it also asks `rule_switches.is_off`):
  planning           visual_planning_rules.check()        rule(name, scene, bad, step, severity, code, message)
  motion_plan        motion_planning.Run.rule              rule(name, step, scene, bad, severity, code, message)
  motion_gen         motion_gen_rules (a motion_planning.Run) the same call
  motion_validation  motion_validation.Validator.check     check(stage, rule, ok, severity, message, ...)
  timeline           timeline_build.Validator.check        the same call
  render             render_video.verify_output add()      add(id, ok, message, want, got, severity)
  qc                 final_qc.Q.add                        add("QC_...", status, severity, message, ...)
  assets             asset_collection.check_assets         findings with a code
"""
from __future__ import annotations

import ast
import functools
from pathlib import Path

from SYSTEM.core import config

STAGES_DIR = config.PROJECT_ROOT / "VIDEO_ENGINE" / "stages"
SEVERITIES = ("blocker", "error", "warning", "review", "info")

# stage -> (label, [(file, call names, index of the rule name, index of the severity, index of the message)])
SOURCES: dict[str, tuple[str, list[tuple[str, tuple[str, ...], int, int, int]]]] = {
    "planning": ("Visual Planning", [("visual_planning_rules.py", ("rule",), 0, 4, 6)]),
    "motion_plan": ("Motion Planning", [("motion_planning.py", ("rule", "run_rule"), 0, 4, 6)]),
    "motion_gen": ("Motion Generation", [("motion_gen_rules.py", ("rule",), 0, 4, 6), ("motion_gen_report.py", ("rule",), 0, 4, 6)]),
    "motion_validation": ("Motion & Timeline Validation", [("motion_validation_rules.py", ("check",), 1, 3, 4)]),
    "timeline": ("Timeline Build", [("timeline_build.py", ("check",), 1, 3, 4)]),
    "render": ("Render Video", [("render_video.py", ("add",), 0, 5, 2)]),
    "qc": ("Final QC", [("final_qc.py", ("add",), 0, 2, 3), ("final_qc.py", ("ok",), 0, -1, 1)]),
}
DEFAULT_SEVERITY = {"render_video.py": "error", "final_qc.py": ""}               # render_video's add() defaults to "error"
ASSET_RULES = {                                            # asset_collection.check_assets: its findings have codes, not calls
    "asset_file": ("error", "a collected file is missing or changed since it was collected"),
    "asset_provenance": ("error", "an asset has no source or no licence (a hand upload counts the user as its source)"),
    "asset_rights": ("error", "an asset has rights class D: no licence information, it must not be used"),
    "asset_rights_review": ("review", "an asset's rights are not established (class C): a person must confirm the use"),
    "asset_authenticity": ("error", "an asset's authenticity is neither real nor user_provided"),
}


def _text(node: ast.AST | None) -> str:
    """What a message argument says: a string as it is, an f-string with its values left out."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "…" for v in node.values)
    return ""


def _arg(call: ast.Call, i: int) -> ast.AST | None:
    return call.args[i] if 0 <= i < len(call.args) else None


def _scan(path: Path, names: tuple[str, ...], i_name: int, i_sev: int, i_msg: int, qc: bool) -> list[dict]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    found: list[dict] = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        fn = n.func.id if isinstance(n.func, ast.Name) else n.func.attr if isinstance(n.func, ast.Attribute) else None
        if fn not in names:
            continue
        rule = _text(_arg(n, i_name)).strip()
        if not rule or " " in rule or len(rule) > 60 or (qc and not rule.startswith("QC_")):
            continue
        sev = _text(_arg(n, i_sev)) or next((_text(k.value) for k in n.keywords if k.arg == "severity"), "") or DEFAULT_SEVERITY.get(path.name, "")
        found.append({"rule": rule, "severity": sev if sev in SEVERITIES else "", "says": _text(_arg(n, i_msg))[:200]})
    return found


@functools.lru_cache(maxsize=1)
def catalog() -> list[dict]:
    """Every rule once: {stage, stage_label, rule, severity (the worst a call of it can have), says (one example of its message), calls (how many places record it)}."""
    out: list[dict] = []
    for stage, (label, sources) in SOURCES.items():
        merged: dict[str, dict] = {}
        for fname, names, i_name, i_sev, i_msg in sources:
            for f in _scan(STAGES_DIR / fname, names, i_name, i_sev, i_msg, qc=(stage == "qc")):
                m = merged.setdefault(f["rule"], {"stage": stage, "stage_label": label, "rule": f["rule"], "severity": "", "says": "", "calls": 0})
                m["calls"] += 1
                if f["severity"] and (not m["severity"] or SEVERITIES.index(f["severity"]) < SEVERITIES.index(m["severity"])):
                    m["severity"] = f["severity"]
                m["says"] = m["says"] or f["says"]
        for m in merged.values():
            m["says"] = m["says"] or m["rule"].replace("_", " ").replace(".", ": ")          # a message that is built at run time: the rule's own name says it
        out += sorted(merged.values(), key=lambda r: r["rule"])
    out += [{"stage": "assets", "stage_label": "Asset Collection", "rule": code, "severity": sev, "says": says, "calls": 1} for code, (sev, says) in ASSET_RULES.items()]
    return out
