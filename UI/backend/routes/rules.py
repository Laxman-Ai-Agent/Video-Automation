"""The rules page: every deterministic rule of the stages with its switch (ON = the rule is checked, OFF = it is never evaluated, so it cannot block or warn)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from SYSTEM.policies import rule_catalog, rule_switches

from ..errors import ApiError

router = APIRouter(prefix="/rules", tags=["rules"])


class SwitchBody(BaseModel):
    on: bool
    stage: str | None = None                  # with `rule`: that rule; without `rule`: every rule of the stage; without both: every rule
    rule: str | None = None
    note: str = ""                            # why it was switched off (kept next to the switch)


def _view() -> dict:
    off = rule_switches.off()
    stages: dict[str, dict] = {}
    for r in rule_catalog.catalog():
        s = stages.setdefault(r["stage"], {"stage": r["stage"], "label": r["stage_label"], "total": 0, "off": 0, "rules": []})
        sw = off.get(f"{r['stage']}:{r['rule']}")
        s["total"] += 1
        s["off"] += bool(sw)
        s["rules"].append({**r, "on": sw is None, "off_note": (sw or {}).get("note"), "off_at": (sw or {}).get("at")})
    return {"total": sum(s["total"] for s in stages.values()), "off": sum(s["off"] for s in stages.values()), "stages": list(stages.values())}


@router.get("")
def list_rules():
    """All rules by stage, each with `on`. A rule that is OFF is told to the LLM reviewers of its stage."""
    return _view()


@router.post("/switch")
def switch_rules(body: SwitchBody):
    cat = [(r["stage"], r["rule"]) for r in rule_catalog.catalog()]
    if body.rule and not body.stage:
        raise ApiError(422, "invalid_request", "a rule needs its stage")
    picked = [(s, r) for s, r in cat if (body.stage is None or s == body.stage) and (body.rule is None or r == body.rule)]
    if not picked:
        raise ApiError(404, "no_such_rule", f"there is no rule '{body.stage}:{body.rule}'" if body.rule else f"there is no stage '{body.stage}' with rules")
    rule_switches.set_many(picked, body.on, body.note)
    return _view()
