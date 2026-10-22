"""Semantic Search and Similarity Index for Capability Finder.

Provides a lightweight, zero-external-dependency semantic indexing layer for
CapabilityRecord objects and AST-discovered items. Combines:
1. Normalized TF-IDF (Term Frequency - Inverse Document Frequency) vectorization.
2. N-gram sub-token matching and domain-specific semantic expansions.
3. Fast in-memory cosine similarity calculation.
4. Incremental indexing, removal, and complete rebuild from CapabilityRegistry.
"""
from __future__ import annotations

import collections
import math
import re
import threading
from dataclasses import asdict, dataclass, field
from typing import Any

from SYSTEM.registries.capability_registry import CapabilityRecord

# Domain semantic expansion dictionaries for synonyms and conceptual equivalents
SEMANTIC_SYNONYMS: dict[str, list[str]] = {
    # Audio domain
    "audio": ["sound", "speech", "voice", "acoustic", "narration"],
    "transcribe": ["transcription", "speech_to_text", "asr", "subtitles", "captions", "whisper", "phonetics"],
    "synchronization": ["sync", "forced_alignment", "alignment", "token_timestamps", "word_level", "timestamp_alignment"],
    "silence": ["pause", "vad", "silencedetect", "speech_pause", "energy_threshold"],
    "bilingual": ["multilingual", "telugu", "english", "orthography", "code_switching", "phonetic_preservation"],

    # Motion & Animation domain
    "motion": ["animation", "animate", "movement", "kinetic", "transition", "dynamics"],
    "kinetic_typography": ["text_animation", "animated_text", "kinetic_text", "typography_motion", "word_highlight", "typography_layout", "readability_optimization"],
    "data_visualization": ["chart", "plot", "graph", "bar_chart", "stacked_bar", "metric_card", "pie_chart"],
    "spring": ["easing", "bounce", "smooth_curve", "damping", "physics_motion", "interpolation"],
    "layout": ["safe_area", "collision_avoidance", "bounding_box", "spatial_arrangement", "z_index"],

    # Visual & Scene domain
    "visual": ["scene", "artwork", "composition", "image", "asset", "visual_concept"],
    "segmentation": ["chunking", "scene_boundary", "semantic_split", "topic_shift", "beat_division"],
    "theme": ["palette", "color_scheme", "dark_mode", "aesthetic", "visual_style", "cinematography"],

    # Timeline & Rendering domain
    "timeline": ["sequencing", "assembly", "track", "cut", "transition_timing", "muxing"],
    "render": ["video_render", "remotion", "mp4_export", "encoding", "ffmpeg", "compositing"],
    "qc": ["quality_control", "validation", "audit", "verification", "frame_check", "black_frame", "audio_drift"],
}


def tokenize(text: str) -> list[str]:
    """Tokenizes text into normalized lowercase alphanumeric words and sub-tokens."""
    if not text:
        return []
    words = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower())
    tokens: list[str] = []
    for w in words:
        clean_w = w.replace("-", "_")
        tokens.append(clean_w)
        # Split snake_case into individual component tokens
        if "_" in clean_w:
            tokens.extend([part for part in clean_w.split("_") if len(part) >= 2])
    return tokens


def expand_synonyms(tokens: list[str]) -> list[str]:
    """Appends domain-specific synonyms and conceptual equivalents to token list."""
    expanded = list(tokens)
    for tok in tokens:
        for key, syns in SEMANTIC_SYNONYMS.items():
            if tok == key or key in tok:
                expanded.extend(syns)
            elif tok in syns:
                expanded.append(key)
    return expanded


@dataclass
class IndexedDocument:
    doc_id: str
    source_type: str
    source_id: str
    domain: str
    raw_text: str
    term_frequencies: dict[str, float] = field(default_factory=dict)
    vector_norm: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class SemanticCapabilityIndex:
    """In-memory semantic TF-IDF and synonym vector retrieval index."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._docs: dict[str, IndexedDocument] = {}
        self._doc_frequencies: dict[str, int] = collections.defaultdict(int)
        self._total_docs: int = 0
        self._revision: int = 0

    def index_capability(self, record: CapabilityRecord) -> None:
        """Indexes a single CapabilityRecord incrementally."""
        with self._lock:
            doc_id = record.capability_id
            # Remove previous version if present
            if doc_id in self._docs:
                self.remove_capability(doc_id)

            # Build rich document representation
            doc_text = " ".join([
                record.capability_id,
                record.name,
                record.description,
                record.domain,
                record.source_type,
                record.source_id,
                " ".join(record.tags),
                " ".join(record.keywords),
                " ".join(record.dependencies),
                json.dumps(record.input_contract) if record.input_contract else "",
                json.dumps(record.output_contract) if record.output_contract else "",
            ])

            tokens = expand_synonyms(tokenize(doc_text))
            if not tokens:
                return

            tf: dict[str, float] = collections.defaultdict(float)
            for t in tokens:
                tf[t] += 1.0

            # Normalize term frequencies
            max_tf = max(tf.values())
            for t in tf:
                tf[t] = 0.5 + 0.5 * (tf[t] / max_tf)
                self._doc_frequencies[t] += 1

            self._total_docs += 1
            doc = IndexedDocument(
                doc_id=doc_id,
                source_type=record.source_type,
                source_id=record.source_id,
                domain=record.domain,
                raw_text=doc_text,
                term_frequencies=dict(tf),
                metadata=record.to_dict(),
            )
            self._docs[doc_id] = doc
            self._update_vector_norms()
            self._revision += 1

    def remove_capability(self, doc_id: str) -> None:
        """Removes a capability from the semantic index."""
        with self._lock:
            if doc_id not in self._docs:
                return
            old_doc = self._docs.pop(doc_id)
            for t in old_doc.term_frequencies:
                self._doc_frequencies[t] = max(0, self._doc_frequencies[t] - 1)
                if self._doc_frequencies[t] == 0:
                    del self._doc_frequencies[t]
            self._total_docs = max(0, self._total_docs - 1)
            self._update_vector_norms()
            self._revision += 1

    def rebuild_index(self, records: list[CapabilityRecord]) -> None:
        """Rebuilds the entire index from a list of CapabilityRecord records."""
        with self._lock:
            self._docs.clear()
            self._doc_frequencies.clear()
            self._total_docs = 0

            for rec in records:
                doc_text = " ".join([
                    rec.capability_id,
                    rec.name,
                    rec.description,
                    rec.domain,
                    rec.source_type,
                    rec.source_id,
                    " ".join(rec.tags),
                    " ".join(rec.keywords),
                    " ".join(rec.dependencies),
                ])
                tokens = expand_synonyms(tokenize(doc_text))
                if not tokens:
                    continue

                tf: dict[str, float] = collections.defaultdict(float)
                for t in tokens:
                    tf[t] += 1.0

                max_tf = max(tf.values())
                for t in tf:
                    tf[t] = 0.5 + 0.5 * (tf[t] / max_tf)
                    self._doc_frequencies[t] += 1

                self._total_docs += 1
                self._docs[rec.capability_id] = IndexedDocument(
                    doc_id=rec.capability_id,
                    source_type=rec.source_type,
                    source_id=rec.source_id,
                    domain=rec.domain,
                    raw_text=doc_text,
                    term_frequencies=dict(tf),
                    metadata=rec.to_dict(),
                )

            self._update_vector_norms()
            self._revision += 1

    def _update_vector_norms(self) -> None:
        """Precomputes vector norms for cosine similarity."""
        n_docs = max(1, self._total_docs)
        for doc in self._docs.values():
            sum_sq = 0.0
            for term, tf_val in doc.term_frequencies.items():
                df_val = self._doc_frequencies.get(term, 1)
                idf = math.log((n_docs + 1) / (df_val + 0.5)) + 1.0
                weight = tf_val * idf
                sum_sq += weight * weight
            doc.vector_norm = math.sqrt(sum_sq) if sum_sq > 0 else 1.0

    def search_semantic(
        self,
        query: str,
        domain: str | None = None,
        top_k: int = 10,
        min_similarity: float = 0.15,
    ) -> list[tuple[str, float]]:
        """Searches the index using semantic cosine similarity.
        
        Returns:
            list of (capability_id, similarity_score) sorted descending by score.
        """
        with self._lock:
            if not self._docs or not query:
                return []

            query_tokens = expand_synonyms(tokenize(query))
            if not query_tokens:
                return []

            # Compute query vector
            q_tf: dict[str, float] = collections.defaultdict(float)
            for t in query_tokens:
                q_tf[t] += 1.0

            max_q_tf = max(q_tf.values())
            n_docs = max(1, self._total_docs)
            q_weights: dict[str, float] = {}
            q_norm_sq = 0.0

            for t, count in q_tf.items():
                norm_tf = 0.5 + 0.5 * (count / max_q_tf)
                df_val = self._doc_frequencies.get(t, 1)
                idf = math.log((n_docs + 1) / (df_val + 0.5)) + 1.0
                w = norm_tf * idf
                q_weights[t] = w
                q_norm_sq += w * w

            q_norm = math.sqrt(q_norm_sq) if q_norm_sq > 0 else 1.0

            # Score documents
            scored: list[tuple[str, float]] = []
            for doc_id, doc in self._docs.items():
                if domain:
                    d_clean = domain.lower()
                    doc_d = doc.domain.lower()
                    tags = {str(t).lower() for t in doc.metadata.get("tags", [])}
                    if (
                        doc_d != d_clean
                        and doc_d != "general"
                        and d_clean not in doc_d
                        and d_clean not in tags
                        and d_clean not in doc.raw_text.lower()
                    ):
                        continue

                dot_product = 0.0
                for t, qw in q_weights.items():
                    if t in doc.term_frequencies:
                        df_val = self._doc_frequencies.get(t, 1)
                        idf = math.log((n_docs + 1) / (df_val + 0.5)) + 1.0
                        doc_w = doc.term_frequencies[t] * idf
                        dot_product += qw * doc_w

                if dot_product > 0 and doc.vector_norm > 0:
                    similarity = dot_product / (q_norm * doc.vector_norm)
                    # Scale to 0.0 - 1.0 range
                    similarity = min(1.0, round(similarity, 3))
                    if similarity >= min_similarity:
                        scored.append((doc_id, similarity))

            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:top_k]

    def get_stats(self) -> dict[str, Any]:
        """Returns diagnostic statistics of the semantic index."""
        with self._lock:
            return {
                "total_documents": self._total_docs,
                "vocabulary_size": len(self._doc_frequencies),
                "index_revision": self._revision,
            }


# Singleton instance
semantic_index = SemanticCapabilityIndex()
