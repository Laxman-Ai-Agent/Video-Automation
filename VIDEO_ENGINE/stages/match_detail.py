"""match_detail.json: for every prompt, which image, how sure (band), why (reason), whether the user locked it and which narration cue it belongs to.
A sidecar next to match_report.json (the report and the API that serves it are unchanged). Written by matcher.save_report when A2V_MATCH_DETAIL=1."""
import json
from pathlib import Path

from .contracts import MatchDetail, Reason, band, locked_numbers
from .models import MatchReport, PromptsMap

RULES = {"filename": "filename_number", "manual": "user_choice", "clip": "clip_margin"}


def detail_for(p, m, locked: set[int], cue: str | None = None) -> MatchDetail:
    """p = PromptItem, m = MatchItem or None. A missing image is never "ok"; a manual choice has no score (band none) but is locked."""
    if m is None or not m.file:
        return MatchDetail(n=p.n, slot=p.slot, file=None, status="missing", band="none", locked=p.n in locked,
                           reason=Reason(rule="no_image", source_cue=cue, detail="no match report yet" if m is None else (m.note or "no image for this prompt")))
    return MatchDetail(n=p.n, slot=p.slot, file=m.file, status=m.status, band=band(m.score, m.margin), score=m.score, margin=m.margin, locked=p.n in locked,
                       reason=Reason(rule=RULES.get(m.method, m.method), score=m.score, source_cue=cue, detail=m.note or ""))


def details(pdir: Path, rep: MatchReport | None, cue_links: dict | None = None) -> list[MatchDetail]:
    prompts = PromptsMap.model_validate_json((pdir / "prompts_map.json").read_text(encoding="utf-8")).prompts
    by_n = {m.n: m for m in rep.matches} if rep else {}
    locked = locked_numbers(pdir, rep.matches if rep else None)
    return [detail_for(p, by_n.get(p.n), locked, (cue_links or {}).get(str(p.n))) for p in prompts]


def write(pdir: Path, rep: MatchReport) -> Path:
    from . import cues
    links = {}
    if (pdir / "scene_plan.json").exists():
        try:
            links = cues.build(pdir)["links"]
        except (OSError, ValueError, KeyError):      # a missing/odd translation must never stop matching: the detail then has no cue links
            links = {}
    out = pdir / "match_detail.json"
    out.write_text(json.dumps([d.model_dump() for d in details(pdir, rep, links)], indent=1, ensure_ascii=False), encoding="utf-8")
    return out
