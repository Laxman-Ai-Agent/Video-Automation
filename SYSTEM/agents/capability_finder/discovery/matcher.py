"""Capability Normalization, Matching, and Deduplication Engine.

Matches a ParsedRequirement against:
1. Canonical CapabilityRegistry records.
2. Static AST-discovered elements.
Evaluates domain alignment, keyword/tag overlap, contract compatibility, and constraint coverage.
Computes deterministic confidence scores (0.0 to 1.0).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from SYSTEM.registries.capability_registry import CapabilityRecord
from .ast_scanner import AstDiscoveredItem
from .requirement_parser import ParsedRequirement
from .semantic_index import expand_synonyms, semantic_index, tokenize

MatchType = Literal[
    "exact",
    "strong_semantic",
    "partial",
    "related_alternative",
    "unverified_candidate",
    "weak",
    "no_match",
]


@dataclass
class CapabilityMatch:
    """Represents a scored match between a requirement and a system capability."""
    capability_id: str
    score: float
    match_type: MatchType
    matched_by: list[str] = field(default_factory=list)
    source_type: str = "unknown"
    source_id: str = ""
    source_path: str = ""
    constraints_satisfied: list[str] = field(default_factory=list)
    constraints_unmet: list[str] = field(default_factory=list)
    record: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    semantic_score: float = 0.0
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CapabilityMatcher:
    """Matches ParsedRequirement instances against CapabilityRecords and AstDiscoveredItems."""

    def match(
        self,
        req: ParsedRequirement,
        candidates: list[CapabilityRecord],
        ast_items: list[AstDiscoveredItem] | None = None,
        min_score: float = 0.2,
    ) -> list[CapabilityMatch]:
        """Matches requirement against candidates, returning ranked matches above min_score."""
        matches: list[CapabilityMatch] = []
        seen_keys: set[str] = set()

        req_tags = {t.lower() for t in req.tags}
        req_keywords = {k.lower() for k in req.keywords}
        req_domain = req.domain.lower()

        # Precompute semantic similarities using SemanticCapabilityIndex if populated
        semantic_scores: dict[str, float] = {}
        query_text = f"{req.raw_query} {req.primary_capability} {' '.join(req.keywords)}"
        raw_semantic_hits = semantic_index.search_semantic(
            query=query_text,
            domain=req_domain if req_domain != "general" else None,
            top_k=50,
            min_similarity=0.05,
        )
        for doc_id, sim in raw_semantic_hits:
            semantic_scores[doc_id] = sim

        # 1. Match against Registry CapabilityRecords
        for c in candidates:
            score = 0.0
            matched_by: list[str] = []
            satisfied_constraints: list[str] = []
            unmet_constraints: list[str] = []

            # Domain alignment (weight: 0.25)
            if c.domain.lower() == req_domain:
                score += 0.25
                matched_by.append("domain")
            elif c.domain.lower() == "general":
                score += 0.10

            # Direct primary capability match (weight: 0.35)
            c_name_lower = f"{c.capability_id} {c.name}".lower()
            stop_words = {"agent", "tool", "skill", "system", "stage"}
            cap_tokens = [p for p in req.primary_capability.split("_") if len(p) > 3 and p not in stop_words]
            if req.primary_capability in c_name_lower or (cap_tokens and any(p in c_name_lower for p in cap_tokens)):
                score += 0.35
                matched_by.append("primary_capability")

            # Semantic similarity score (weight: 0.20)
            candidate_sem_score = semantic_scores.get(c.capability_id, 0.0)
            if candidate_sem_score == 0.0:
                # On-the-fly token + synonym overlap if not in semantic index
                c_text = f"{c.capability_id} {c.name} {c.description} {' '.join(c.tags)} {' '.join(c.keywords)}"
                q_tokens = set(expand_synonyms(tokenize(query_text)))
                c_tokens = set(expand_synonyms(tokenize(c_text)))
                if q_tokens and c_tokens:
                    inter = q_tokens.intersection(c_tokens)
                    union = q_tokens.union(c_tokens)
                    candidate_sem_score = round(len(inter) / max(1, len(union)), 3)

            if candidate_sem_score >= 0.20:
                sem_weight = min(0.20, candidate_sem_score * 0.25)
                score += sem_weight
                matched_by.append(f"semantic_similarity({candidate_sem_score:.2f})")

            # Tag overlap (weight: 0.15)
            c_tags = {t.lower() for t in c.tags}
            tag_overlap = req_tags.intersection(c_tags)
            if tag_overlap:
                tag_weight = min(0.15, len(tag_overlap) * 0.06)
                score += tag_weight
                matched_by.append(f"tags({','.join(sorted(tag_overlap)[:3])})")

            # Keyword overlap (weight: 0.10)
            c_keywords = {k.lower() for k in c.keywords}
            keyword_overlap = req_keywords.intersection(c_keywords)
            if keyword_overlap:
                kw_weight = min(0.10, len(keyword_overlap) * 0.03)
                score += kw_weight
                matched_by.append("keywords")

            # Constraint validation (weight: 0.10)
            for k, v in req.constraints.items():
                c_str = f"{c.description} {' '.join(c.tags)} {' '.join(c.keywords)}".lower()
                val_str = str(v).lower()
                if val_str in c_str or k.lower() in c_str:
                    satisfied_constraints.append(f"{k}={v}")
                else:
                    unmet_constraints.append(f"{k}={v}")

            if satisfied_constraints and not unmet_constraints:
                score += 0.10
                matched_by.append("constraints_fully_met")
            elif satisfied_constraints:
                score += 0.05
                matched_by.append("constraints_partially_met")

            if "domain" in matched_by and "primary_capability" in matched_by and not unmet_constraints:
                score = max(score, 0.90)
            elif "primary_capability" in matched_by and not unmet_constraints and c.source_id.lower() == req.primary_capability.lower():
                score = max(score, 0.85)

            score = min(1.0, round(score, 3))

            if score >= min_score:
                if score >= 0.80 and not unmet_constraints:
                    m_type: MatchType = "exact"
                elif candidate_sem_score >= 0.50 or (score >= 0.65 and any("semantic_similarity" in mb for mb in matched_by)):
                    m_type = "strong_semantic"
                elif score >= 0.45:
                    m_type = "partial"
                elif score >= 0.30:
                    m_type = "related_alternative"
                else:
                    m_type = "weak"

                explanation = (
                    f"Candidate '{c.capability_id}' ({c.source_type}) scored {score:.2f} ({m_type}). "
                    f"Matched criteria: {', '.join(matched_by)}. "
                    f"Semantic score: {candidate_sem_score:.2f}. "
                    + (f"Satisfied constraints: {', '.join(satisfied_constraints)}. " if satisfied_constraints else "")
                    + (f"Unmet constraints: {', '.join(unmet_constraints)}." if unmet_constraints else "Constraints verified.")
                )

                evidence = list(c.evidence_refs) if c.evidence_refs else []
                evidence.append({
                    "evidence_type": "registry_record",
                    "capability_id": c.capability_id,
                    "source_type": c.source_type,
                    "source_id": c.source_id,
                    "source_path": c.source_path,
                    "matched_by": matched_by,
                    "score": score,
                    "semantic_score": candidate_sem_score,
                })

                dedup_key = f"{c.source_type}:{c.source_id}:{c.capability_id}"
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    matches.append(
                        CapabilityMatch(
                            capability_id=c.capability_id,
                            score=score,
                            match_type=m_type,
                            matched_by=matched_by,
                            source_type=c.source_type,
                            source_id=c.source_id,
                            source_path=c.source_path,
                            constraints_satisfied=satisfied_constraints,
                            constraints_unmet=unmet_constraints,
                            record=c.to_dict(),
                            evidence_refs=evidence,
                            semantic_score=candidate_sem_score,
                            explanation=explanation,
                        )
                    )

        # 2. Match against AST items if provided
        if ast_items:
            for item in ast_items:
                score = 0.0
                matched_by = []
                c_text = f"{item.name} {item.docstring} {' '.join(item.advertised_capabilities)}".lower()

                if req_domain in c_text or req_domain in item.file_path.lower():
                    score += 0.20
                    matched_by.append("domain_path")

                if req.primary_capability in c_text or any(p in c_text for p in req.primary_capability.split("_")):
                    score += 0.35
                    matched_by.append("ast_symbol_match")

                cap_overlap = req_tags.intersection({c.lower() for c in item.advertised_capabilities})
                if cap_overlap:
                    score += 0.25
                    matched_by.append("advertised_capabilities")

                # Semantic token overlap
                q_tokens = set(expand_synonyms(tokenize(query_text)))
                ast_tokens = set(expand_synonyms(tokenize(c_text)))
                ast_sem_score = 0.0
                if q_tokens and ast_tokens:
                    ast_sem_score = round(len(q_tokens.intersection(ast_tokens)) / max(1, len(q_tokens.union(ast_tokens))), 3)
                    if ast_sem_score >= 0.20:
                        score += min(0.15, ast_sem_score * 0.20)
                        matched_by.append(f"ast_semantic({ast_sem_score:.2f})")

                score = min(1.0, round(score, 3))
                if score >= min_score:
                    if score >= 0.50:
                        m_type = "unverified_candidate"
                    elif score >= 0.35:
                        m_type = "partial"
                    else:
                        m_type = "weak"

                    explanation = (
                        f"AST static symbol '{item.name}' ({item.kind}) at {item.file_path}:{item.line_start} "
                        f"scored {score:.2f} ({m_type}). Unregistered code candidate."
                    )

                    dedup_key = f"ast:{item.file_path}:{item.item_id}"
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        matches.append(
                            CapabilityMatch(
                                capability_id=f"ast.{item.item_id}",
                                score=score,
                                match_type=m_type,
                                matched_by=matched_by,
                                source_type="ast_discovered",
                                source_id=item.name,
                                source_path=item.file_path,
                                constraints_satisfied=[],
                                constraints_unmet=[f"{k}={v}" for k, v in req.constraints.items()],
                                record=item.to_dict(),
                                evidence_refs=[{
                                    "evidence_type": "ast_symbol",
                                    "file_path": item.file_path,
                                    "line_start": item.line_start,
                                    "line_end": item.line_end,
                                    "symbol_type": item.kind,
                                    "file_hash": item.file_hash,
                                }],
                                semantic_score=ast_sem_score,
                                explanation=explanation,
                            )
                        )

        # Sort matches descending by score
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches


capability_matcher = CapabilityMatcher()
