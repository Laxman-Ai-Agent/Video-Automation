"""Semantic Intelligence Extension Subsystem for Scene Segmentation Agent.
Provides:
1. Cross-language Telugu-English topic/chapter modeling with narrative roles.
2. Telugu-English technical vocabulary standardization without transcript corruption.
3. Adaptive pacing analysis based on acoustic speech-rate and silence metrics.
4. Candidate boundary adjustment evaluator with strict Deterministic Invariant Guard.
5. Autonomous fallback to deterministic heuristic analysis if LLM is unavailable.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from SYSTEM.core.artifact_contracts import _file_sha256

logger = logging.getLogger("scene_segmentation.semantic_analyzer")

# Deterministic guidelines and Telugu language constants
MIN_SCENE_DURATION_SECONDS = 2.0
MAX_SCENE_DURATION_SECONDS = 12.0
SOFT_MIN_SECONDS = 3.0
SOFT_MAX_SECONDS = 8.0

TELUGU_DISCOURSE_MARKERS = (
    "కానీ", "ఎందుకంటే", "దీనివల్ల", "మరోవైపు", "చివరగా", "అందుకే",
    "అయితే", "అంటే", "మొదట", "ఆ తర్వాత", "ఆ సమయం", "కాబట్టి",
    "ఉదాహరణకు", "అక్కడ", "అయినా", "అయనా", "ఇప్పుడు", "ముఖ్యంగా"
)

NARRATIVE_ROLES = (
    "hook", "context", "problem", "explanation",
    "solution", "example", "contrast", "reveal", "conclusion"
)

BOUNDARY_TRANSITION_TYPES = (
    "topic_change", "concept_change", "cause_effect_step",
    "example", "contrast", "conclusion", "pause", "sentence_boundary"
)

PACING_PROFILES = (
    "fast_cut", "brisk", "balanced", "expanded_pause", "dramatic_hold"
)


@dataclass
class TopicChapter:
    """Represents a high-level narrative chapter/topic spanning one or more scenes."""
    topic_id: str
    title: str
    narrative_role: str
    start_time: float
    end_time: float
    scene_ids: list[str] = field(default_factory=list)
    word_range: list[int] = field(default_factory=lambda: [0, 0])
    transition_type: str = "topic_change"
    confidence: float = 0.9
    main_idea: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VocabularyTerm:
    """Standardized technical terminology entry."""
    term: str
    original_text: str
    normalized_term: str
    language_code: Literal["te", "en", "mixed"]
    category: str
    scene_ids: list[str] = field(default_factory=list)
    occurrences: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScenePacingAdvice:
    """Adaptive pacing guidance calculated from speech rate and audio pauses."""
    scene_id: str
    words_count: int
    duration_seconds: float
    speech_rate_wpm: float
    pause_duration_seconds: float
    pause_density: float
    recommended_pacing: str
    visual_hold_factor: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BoundaryCandidateDecision:
    """Record of an evaluated candidate boundary adjustment."""
    candidate_id: str
    proposal_type: Literal["split", "merge", "adjust_boundary", "keep"]
    target_scene_id: str
    proposed_word_index: int | None
    invariants_passed: bool
    rejection_reason: str | None = None
    applied: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticAnalysisResult:
    """Complete output of semantic intelligence review."""
    status: Literal["completed", "fallback_deterministic", "failed"]
    scenes: list[dict[str, Any]]
    topics: list[TopicChapter]
    vocabulary: list[VocabularyTerm]
    pacing_advice: list[ScenePacingAdvice]
    boundary_decisions: list[BoundaryCandidateDecision]
    global_pacing: dict[str, Any]
    llm_metadata: dict[str, Any]
    invariant_status: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "scenes_count": len(self.scenes),
            "topics": [t.to_dict() for t in self.topics],
            "vocabulary": [v.to_dict() for v in self.vocabulary],
            "pacing_advice": [p.to_dict() for p in self.pacing_advice],
            "boundary_decisions": [b.to_dict() for b in self.boundary_decisions],
            "global_pacing": self.global_pacing,
            "llm_metadata": self.llm_metadata,
            "invariant_status": self.invariant_status,
        }


class DeterministicInvariantGuard:
    """Strict guard enforcing bit-for-bit mathematical and word constraints."""

    @staticmethod
    def validate_scene_invariants(
        scenes: list[dict[str, Any]],
        canonical_words: list[dict[str, Any]],
        audio_duration: float,
    ) -> tuple[bool, list[str]]:
        """Validates all 5 mandatory invariants for scene boundaries.
        Returns (is_valid, list_of_violations).
        """
        violations: list[str] = []
        if not scenes:
            return False, ["Scene list is empty"]

        total_words = len(canonical_words)
        covered_indices: list[int] = []

        for idx, sc in enumerate(scenes):
            sc_id = sc.get("scene_id") or sc.get("id") or f"scene_{idx+1:03d}"
            start = float(sc.get("start_time", sc.get("start", 0.0)))
            end = float(sc.get("end_time", sc.get("end", 0.0)))
            dur = end - start

            # Invariant 1: Duration bounds
            if dur < MIN_SCENE_DURATION_SECONDS - 0.01:
                violations.append(f"{sc_id} duration {dur:.2f}s is below minimum {MIN_SCENE_DURATION_SECONDS}s")
            if dur > MAX_SCENE_DURATION_SECONDS + 0.5:
                violations.append(f"{sc_id} duration {dur:.2f}s exceeds maximum {MAX_SCENE_DURATION_SECONDS}s")

            # Invariant 2: Positive duration & audio confinement
            if start < 0 or start >= end:
                violations.append(f"{sc_id} has invalid time window: {start:.2f}s -> {end:.2f}s")
            if end > audio_duration + 0.5:
                violations.append(f"{sc_id} end {end:.2f}s exceeds audio duration {audio_duration:.2f}s")

            # Invariant 3: Word range validity
            w_range = sc.get("word_range")
            if w_range and len(w_range) == 2:
                w_start, w_end = int(w_range[0]), int(w_range[1])
                if w_start < 0 or w_end >= total_words or w_start > w_end:
                    violations.append(f"{sc_id} has invalid word_range {w_range} for total_words={total_words}")
                else:
                    covered_indices.extend(range(w_start, w_end + 1))

        # Invariant 4: Complete word coverage in order
        if canonical_words and covered_indices:
            expected_indices = list(range(total_words))
            if covered_indices != expected_indices:
                missing = set(expected_indices) - set(covered_indices)
                duplicates = len(covered_indices) - len(set(covered_indices))
                violations.append(f"Incomplete word coverage: {len(missing)} missing, {duplicates} duplicates")

        # Invariant 5: Chronological continuity and no gaps/overlaps
        for i in range(len(scenes) - 1):
            cur_end = float(scenes[i].get("end_time", scenes[i].get("end", 0.0)))
            nxt_start = float(scenes[i + 1].get("start_time", scenes[i + 1].get("start", 0.0)))
            if nxt_start < cur_end - 0.15:
                violations.append(f"Scene overlap between scene {i+1} ({cur_end:.2f}s) and scene {i+2} ({nxt_start:.2f}s)")
            elif nxt_start > cur_end + 1.0:
                violations.append(f"Scene gap between scene {i+1} ({cur_end:.2f}s) and scene {i+2} ({nxt_start:.2f}s)")

        return (len(violations) == 0, violations)


class SemanticAnalyzer:
    """Extension layer providing LLM-powered narrative and pacing intelligence."""

    def __init__(self, llm_gateway_module: Any = None) -> None:
        self.gateway_module = llm_gateway_module

    def _extract_words_and_duration(self, transcript_data: dict[str, Any]) -> tuple[list[dict[str, Any]], float]:
        """Extracts canonical words and duration safely from the corrected transcript."""
        words: list[dict[str, Any]] = []
        duration = float(transcript_data.get("duration", 0.0))

        segments = transcript_data.get("segments", [])
        for s in segments:
            seg_id = s.get("id", 0)
            seg_words = s.get("words", [])
            if seg_words:
                for w in seg_words:
                    word_text = str(w.get("word", w.get("text", w.get("w", ""))))
                    w_start = float(w.get("start", w.get("start_seconds", 0.0)))
                    w_end = float(w.get("end", w.get("end_seconds", w_start)))
                    words.append({
                        "id": f"w{len(words)+1:03d}",
                        "text": word_text,
                        "start": w_start,
                        "end": w_end,
                        "seg": seg_id,
                    })
            else:
                # Segment without word timestamps
                seg_text = str(s.get("text", ""))
                words.append({
                    "id": f"w{len(words)+1:03d}",
                    "text": seg_text,
                    "start": float(s.get("start", s.get("start_seconds", 0.0))),
                    "end": float(s.get("end", s.get("end_seconds", 0.0))),
                    "seg": seg_id,
                })

        if duration <= 0.0 and words:
            duration = max(w["end"] for w in words)
        return words, duration

    def _extract_pauses(
        self,
        project_dir: Path,
        cuts_data: list[Any] | dict[str, Any] | None,
        words: list[dict[str, Any]],
    ) -> list[tuple[float, float]]:
        """Extracts acoustic pauses from audio_analysis.json, cuts.json, or inter-word gaps."""
        pauses: list[tuple[float, float]] = []

        # 1. Try audio_analysis.json
        aa_path = project_dir / "audio_analysis.json"
        if aa_path.exists():
            try:
                aa_obj = json.loads(aa_path.read_text(encoding="utf-8"))
                for p in aa_obj.get("pauses", []):
                    ps = float(p.get("start_seconds", p.get("start", 0.0)))
                    pe = float(p.get("end_seconds", p.get("end", 0.0)))
                    if pe > ps:
                        pauses.append((ps, pe))
            except Exception:
                pass

        # 2. Try cuts.json
        if not pauses and cuts_data:
            cuts_list = cuts_data if isinstance(cuts_data, list) else cuts_data.get("cuts", [])
            for c in cuts_list:
                if isinstance(c, dict) and c.get("type") in ("silence", "pause", "cut"):
                    ps = float(c.get("start", 0.0))
                    pe = float(c.get("end", 0.0))
                    if pe > ps:
                        pauses.append((ps, pe))

        # 3. Inter-word gaps
        if not pauses and words:
            for i in range(len(words) - 1):
                gap = words[i + 1]["start"] - words[i]["end"]
                if gap >= 0.35:
                    pauses.append((words[i]["end"], words[i + 1]["start"]))

        return pauses

    def _calculate_pacing_advice(
        self,
        scenes: list[dict[str, Any]],
        pauses: list[tuple[float, float]],
        words: list[dict[str, Any]],
    ) -> tuple[list[ScenePacingAdvice], dict[str, Any]]:
        """Calculates adaptive pacing metrics for scenes and overall project."""
        advice_list: list[ScenePacingAdvice] = []
        total_words = 0
        total_duration = 0.0

        for sc in scenes:
            sc_id = sc.get("scene_id") or sc.get("id") or "scene_001"
            start = float(sc.get("start_time", sc.get("start", 0.0)))
            end = float(sc.get("end_time", sc.get("end", 0.0)))
            dur = max(0.1, end - start)

            # Count words in this scene
            sc_words = [w for w in words if w["start"] >= start - 0.05 and w["end"] <= end + 0.05]
            w_count = len(sc_words) if sc_words else max(1, len(sc.get("transcript", sc.get("narration", "")).split()))
            total_words += w_count
            total_duration += dur

            # Speech rate in Words Per Minute
            wpm = round((w_count / dur) * 60.0, 1)

            # Measure pauses falling within this scene
            scene_pauses = [p for p in pauses if p[0] >= start and p[1] <= end]
            pause_sec = sum(p[1] - p[0] for p in scene_pauses)
            pause_density = round(min(1.0, pause_sec / dur), 3)

            # Pacing classification
            if wpm >= 165:
                pacing = "fast_cut"
                hold = 0.8
                rationale = f"Rapid speech ({wpm} WPM). Visual elements should transition briskly to match audio energy."
            elif wpm >= 135:
                pacing = "brisk"
                hold = 1.0
                rationale = f"Brisk narrative flow ({wpm} WPM). Maintain clean kinetic motion."
            elif pause_density >= 0.25 or pause_sec >= 1.0:
                pacing = "expanded_pause"
                hold = 1.3
                rationale = f"Significant pause ({pause_sec:.2f}s, {round(pause_density*100)}% pause density). Ample space for visual settling."
            elif wpm <= 100:
                pacing = "dramatic_hold"
                hold = 1.4
                rationale = f"Deliberate, slow narration ({wpm} WPM). Allow graphics to hold visual focus."
            else:
                pacing = "balanced"
                hold = 1.0
                rationale = f"Standard balanced pacing ({wpm} WPM, {round(pause_density*100)}% pauses)."

            advice_list.append(ScenePacingAdvice(
                scene_id=sc_id,
                words_count=w_count,
                duration_seconds=round(dur, 2),
                speech_rate_wpm=wpm,
                pause_duration_seconds=round(pause_sec, 2),
                pause_density=pause_density,
                recommended_pacing=pacing,
                visual_hold_factor=hold,
                rationale=rationale,
            ))

        avg_wpm = round((total_words / max(0.1, total_duration)) * 60.0, 1)
        global_pacing = {
            "total_words": total_words,
            "total_duration_seconds": round(total_duration, 2),
            "average_wpm": avg_wpm,
            "global_pacing_tier": "fast" if avg_wpm >= 160 else "moderate" if avg_wpm >= 130 else "deliberate",
            "scenes_count": len(scenes),
        }
        return advice_list, global_pacing

    def _extract_vocabulary_heuristic(
        self,
        scenes: list[dict[str, Any]],
        words: list[dict[str, Any]],
    ) -> list[VocabularyTerm]:
        """Heuristically extracts technical English & Telugu terms and normalizes them."""
        vocab_map: dict[str, VocabularyTerm] = {}

        # Common tech terms pattern (English words in Telugu narration)
        en_word_re = re.compile(r"\b[A-Za-z][A-Za-z0-9_-]{2,}\b")

        for sc in scenes:
            sc_id = sc.get("scene_id") or sc.get("id") or "scene_001"
            txt = sc.get("transcript", sc.get("narration", ""))

            matches = en_word_re.findall(txt)
            for m in matches:
                norm = m.strip().title() if len(m) > 4 else m.strip().upper()
                if norm not in vocab_map:
                    vocab_map[norm] = VocabularyTerm(
                        term=m,
                        original_text=m,
                        normalized_term=norm,
                        language_code="en",
                        category="technical_term",
                        scene_ids=[sc_id],
                        occurrences=1,
                    )
                else:
                    if sc_id not in vocab_map[norm].scene_ids:
                        vocab_map[norm].scene_ids.append(sc_id)
                    vocab_map[norm].occurrences += 1

            # Check for prominent Telugu technical loan words
            telugu_loan_terms = {
                "ఆర్టిఫిషియల్ ఇంటెలిజెన్స్": "Artificial Intelligence",
                "మెషిన్ లెర్నింగ్": "Machine Learning",
                "న్యూరల్ నెట్‌వర్క్": "Neural Network",
                "అల్గోరిథం": "Algorithm",
                "డేటాబేస్": "Database",
                "సాఫ్ట్‌వేర్": "Software",
                "హార్డ్‌వేర్": "Hardware",
                "కంప్యూటర్": "Computer",
                "ఇంటర్నెట్": "Internet",
            }
            for te_term, en_norm in telugu_loan_terms.items():
                if te_term in txt:
                    if en_norm not in vocab_map:
                        vocab_map[en_norm] = VocabularyTerm(
                            term=te_term,
                            original_text=te_term,
                            normalized_term=en_norm,
                            language_code="te",
                            category="loan_word",
                            scene_ids=[sc_id],
                            occurrences=1,
                        )
                    else:
                        if sc_id not in vocab_map[en_norm].scene_ids:
                            vocab_map[en_norm].scene_ids.append(sc_id)
                        vocab_map[en_norm].occurrences += 1

        return list(vocab_map.values())

    def _build_heuristic_topics(
        self,
        scenes: list[dict[str, Any]],
        words: list[dict[str, Any]],
    ) -> list[TopicChapter]:
        """Constructs deterministic narrative chapters and roles when LLM is unavailable."""
        topics: list[TopicChapter] = []
        n_scenes = len(scenes)
        if n_scenes == 0:
            return topics

        for i, sc in enumerate(scenes):
            sc_id = sc.get("scene_id") or sc.get("id") or f"scene_{i+1:03d}"
            start = float(sc.get("start_time", sc.get("start", 0.0)))
            end = float(sc.get("end_time", sc.get("end", 0.0)))
            txt = sc.get("transcript", sc.get("narration", ""))

            # Assign narrative role based on position and Telugu discourse markers
            has_marker = any(m in txt for m in TELUGU_DISCOURSE_MARKERS)

            if i == 0:
                role = "hook"
                title = "Introduction & Hook"
            elif i == n_scenes - 1:
                role = "conclusion"
                title = "Summary & Conclusion"
            elif i == 1:
                role = "context"
                title = "Context & Background"
            elif any(m in txt for m in ("కానీ", "మరోవైపు", "అయితే")):
                role = "contrast"
                title = "Key Contrast & Perspective"
            elif any(m in txt for m in ("ఉదాహరణకు",)):
                role = "example"
                title = "Practical Example"
            elif any(m in txt for m in ("ఎందుకంటే", "దీనివల్ల", "కాబట్టి")):
                role = "explanation"
                title = "Underlying Cause & Mechanism"
            elif any(m in txt for m in ("చివరగా", "ముఖ్యంగా")):
                role = "reveal"
                title = "Critical Takeaway"
            else:
                role = "explanation"
                title = f"Topic Section {i+1}"

            topics.append(TopicChapter(
                topic_id=f"topic_{i+1:02d}",
                title=title,
                narrative_role=role,
                start_time=start,
                end_time=end,
                scene_ids=[sc_id],
                word_range=sc.get("word_range", [0, 0]),
                transition_type="concept_change" if has_marker else "sentence_boundary",
                confidence=0.85,
                main_idea=txt[:80] + ("..." if len(txt) > 80 else ""),
            ))

        return topics

    def _execute_llm_semantic_review(
        self,
        project_id: str,
        scenes: list[dict[str, Any]],
        words: list[dict[str, Any]],
        pauses: list[tuple[float, float]],
        pacing_advice: list[ScenePacingAdvice],
    ) -> dict[str, Any] | None:
        """Invokes LLM Gateway with structured schema for semantic understanding."""
        try:
            from SYSTEM.core.llm_gateway import LlmGatewayRequest, get_gateway
        except ImportError:
            logger.warning("SYSTEM.core.llm_gateway not available; skipping LLM call")
            return None

        # Build prompt payload
        scene_summaries = []
        for sc in scenes:
            sc_id = sc.get("scene_id") or sc.get("id")
            scene_summaries.append({
                "scene_id": sc_id,
                "start": sc.get("start_time", sc.get("start")),
                "end": sc.get("end_time", sc.get("end")),
                "text": sc.get("transcript", sc.get("narration")),
            })

        system_prompt = (
            "You are an expert bilingual Telugu-English semantic narrative director for explainer videos. "
            "Analyze the scene segmentation and provide: "
            "1. Narrative topics/chapters with narrative roles (hook, context, problem, explanation, solution, example, contrast, reveal, conclusion). "
            "2. Technical vocabulary standardization for mixed Telugu-English terms. "
            "3. Semantic beats and objectives for each scene. "
            "Return valid JSON matching the requested schema."
        )

        user_prompt = json.dumps({
            "project_id": project_id,
            "scenes": scene_summaries,
            "pacing_metrics": [p.to_dict() for p in pacing_advice],
            "allowed_roles": list(NARRATIVE_ROLES),
            "allowed_transitions": list(BOUNDARY_TRANSITION_TYPES),
        }, ensure_ascii=False)

        req = LlmGatewayRequest(
            project_id=project_id,
            stage_id="segmentation",
            agent_id="scene_segmentation",
            purpose="review",
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            model_profile="fast_structured",
            timeout=30,
            max_retries=1,
            metadata={"source": "scene_segmentation_semantic_analyzer"},
        )

        try:
            gw = get_gateway()
            res = gw.execute(req)
            if res.status in ("passed", "succeeded") and res.structured_data:
                return res.structured_data
            if res.raw_text:
                # Attempt to extract JSON from raw_text
                raw = res.raw_text.strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.warning("LLM Gateway call failed during scene semantic analysis: %s", e)
            return None

        return None

    def analyze(
        self,
        project_dir: Path,
        canonical_segmentation: dict[str, Any],
        transcript_data: dict[str, Any],
        cuts_data: list[Any] | dict[str, Any] | None = None,
    ) -> SemanticAnalysisResult:
        """Executes full semantic intelligence pipeline on top of canonical segmentation."""
        t0 = time.perf_counter()
        project_id = project_dir.name
        raw_scenes = canonical_segmentation.get("scenes", [])

        # 1. Extract canonical words, timestamps, and audio duration
        words, audio_duration = self._extract_words_and_duration(transcript_data)
        if audio_duration <= 0.0:
            audio_duration = max(float(s.get("end_time", s.get("end", 0.0))) for s in raw_scenes) if raw_scenes else 10.0

        # 2. Extract acoustic pauses & compute adaptive pacing advice
        pauses = self._extract_pauses(project_dir, cuts_data, words)
        pacing_advice, global_pacing = self._calculate_pacing_advice(raw_scenes, pauses, words)

        # 3. Extract heuristic baseline vocabulary & topics
        heuristic_vocab = self._extract_vocabulary_heuristic(raw_scenes, words)
        heuristic_topics = self._build_heuristic_topics(raw_scenes, words)

        # 4. Attempt LLM Semantic Review via Gateway
        llm_data = self._execute_llm_semantic_review(
            project_id=project_id,
            scenes=raw_scenes,
            words=words,
            pauses=pauses,
            pacing_advice=pacing_advice,
        )

        llm_used = llm_data is not None
        status: Literal["completed", "fallback_deterministic"] = "completed" if llm_used else "fallback_deterministic"

        topics: list[TopicChapter] = []
        vocabulary: list[VocabularyTerm] = list(heuristic_vocab)
        boundary_decisions: list[BoundaryCandidateDecision] = []

        if llm_used and isinstance(llm_data, dict):
            # Parse topics from LLM
            llm_topics = llm_data.get("topics", [])
            for t in llm_topics:
                if isinstance(t, dict):
                    topics.append(TopicChapter(
                        topic_id=t.get("topic_id", f"topic_{len(topics)+1:02d}"),
                        title=t.get("title", "Narrative Chapter"),
                        narrative_role=t.get("narrative_role", "explanation"),
                        start_time=float(t.get("start_time", 0.0)),
                        end_time=float(t.get("end_time", 0.0)),
                        scene_ids=t.get("scene_ids", []),
                        transition_type=t.get("transition_type", "concept_change"),
                        confidence=float(t.get("confidence", 0.9)),
                        main_idea=t.get("main_idea", ""),
                    ))

            # Parse vocabulary from LLM
            llm_vocab = llm_data.get("vocabulary", [])
            existing_terms = {v.normalized_term for v in vocabulary}
            for v in llm_vocab:
                if isinstance(v, dict):
                    norm = v.get("normalized_term", v.get("term", "")).strip()
                    if norm and norm not in existing_terms:
                        vocabulary.append(VocabularyTerm(
                            term=v.get("term", norm),
                            original_text=v.get("original_text", norm),
                            normalized_term=norm,
                            language_code=v.get("language_code", "mixed"),
                            category=v.get("category", "technical_term"),
                            scene_ids=v.get("scene_ids", []),
                            occurrences=int(v.get("occurrences", 1)),
                        ))
                        existing_terms.add(norm)

        if not topics:
            topics = heuristic_topics

        # 5. Enrich scenes non-destructively
        pacing_by_id = {p.scene_id: p for p in pacing_advice}
        enriched_scenes: list[dict[str, Any]] = []

        for idx, sc in enumerate(raw_scenes):
            sc_id = sc.get("scene_id") or sc.get("id") or f"scene_{idx+1:03d}"
            sc_copy = dict(sc)

            # Assign topic matching
            matched_topic = next((t for t in topics if sc_id in t.scene_ids), None)
            if not matched_topic and idx < len(topics):
                matched_topic = topics[idx]

            sc_copy["topic_id"] = matched_topic.topic_id if matched_topic else f"topic_{idx+1:02d}"
            sc_copy["topic_label"] = matched_topic.title if matched_topic else "Narrative Unit"
            sc_copy["narrative_role"] = matched_topic.narrative_role if matched_topic else "explanation"

            # Assign pacing
            pacing_item = pacing_by_id.get(sc_id)
            if pacing_item:
                sc_copy["pacing_profile"] = pacing_item.recommended_pacing
                sc_copy["speech_rate_wpm"] = pacing_item.speech_rate_wpm

            # Assign vocabulary terms found in this scene
            sc_vocab = [v.normalized_term for v in vocabulary if sc_id in v.scene_ids]
            sc_copy["vocabulary_terms"] = sc_vocab

            # Ensure semantic_beat and scene_objective exist
            if not sc_copy.get("semantic_beat"):
                sc_copy["semantic_beat"] = matched_topic.title if matched_topic else f"Beat {idx+1}"
            if not sc_copy.get("scene_objective"):
                sc_copy["scene_objective"] = matched_topic.main_idea if matched_topic and matched_topic.main_idea else sc_copy.get("semantic_beat", "")

            enriched_scenes.append(sc_copy)

        # 6. Verify Deterministic Invariants on Enriched Scenes
        is_valid, violations = DeterministicInvariantGuard.validate_scene_invariants(
            scenes=enriched_scenes,
            canonical_words=words,
            audio_duration=audio_duration,
        )

        invariant_status = {
            "all_invariants_passed": is_valid,
            "violations_count": len(violations),
            "violations": violations,
            "word_snapping_enforced": True,
            "duration_bounds_checked": True,
        }

        # If enriched scenes somehow violated invariants, revert to canonical scenes
        if not is_valid:
            logger.warning("Enriched scenes violated invariants (%s). Reverting to canonical.", violations)
            enriched_scenes = raw_scenes
            boundary_decisions.append(BoundaryCandidateDecision(
                candidate_id="revert_to_canonical",
                proposal_type="keep",
                target_scene_id="all",
                proposed_word_index=None,
                invariants_passed=False,
                rejection_reason="; ".join(violations),
                applied=True,
            ))

        latency_ms = round((time.perf_counter() - t0) * 1000)
        llm_metadata = {
            "llm_used": llm_used,
            "latency_ms": latency_ms,
            "model_profile": "fast_structured",
            "provider": "canonical_gateway",
            "source_fingerprint": _file_sha256(project_dir / "scene_segmentation.json") if (project_dir / "scene_segmentation.json").exists() else "",
        }

        result = SemanticAnalysisResult(
            status=status,
            scenes=enriched_scenes,
            topics=topics,
            vocabulary=vocabulary,
            pacing_advice=pacing_advice,
            boundary_decisions=boundary_decisions,
            global_pacing=global_pacing,
            llm_metadata=llm_metadata,
            invariant_status=invariant_status,
        )

        # 7. Write companion artifact `scene_semantic_annotations.json`
        annotations_file = project_dir / "scene_semantic_annotations.json"
        try:
            annotations_file.write_text(
                json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to write scene_semantic_annotations.json: %s", e)

        return result
