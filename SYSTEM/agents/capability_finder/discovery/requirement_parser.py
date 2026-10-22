"""Natural Language and Structured Requirement Parser for Capability Discovery.

Extracts:
1. Primary capability needed and target domain.
2. Structured constraints (aspect ratio, language, resolution, fps, deterministic rendering).
3. Runtime tool and model dependencies.
4. Input and output contracts.
5. Functional requirements, performance criteria, and acceptance criteria.
6. Ambiguities requiring operator clarification.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger("capability_finder.requirement_parser")


@dataclass
class ParsedRequirement:
    """Structured representation of parsed task goals and capability requirements."""
    raw_query: str
    primary_capability: str = "general_processing"
    domain: str = "general"
    intent: str = "execute"
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    required_inputs: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    runtime_dependencies: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    functional_requirements: list[str] = field(default_factory=list)
    performance_constraints: dict[str, Any] = field(default_factory=dict)
    acceptance_criteria: list[str] = field(default_factory=list)
    explanation: str = ""
    is_llm_interpreted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParsedRequirement:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


class RequirementParser:
    """Natural language and structured contract requirement parser with LLM intelligence and deterministic fallback."""

    # Domain keyword patterns
    DOMAIN_PATTERNS = {
        "audio": [r"\baudio\b", r"\bspeech\b", r"\btranscrib", r"\bvoice\b", r"\bwhisper\b", r"\bsound\b", r"\bwav\b", r"\bmp3\b"],
        "motion": [r"\bmotion\b", r"\banimat", r"\bkinetic\b", r"\btypograph", r"\bspring\b", r"\beasing\b", r"\btransition\b"],
        "visual": [r"\bvisual\b", r"\bscene\b", r"\blayout\b", r"\bpalette\b", r"\btheme\b", r"\bimage\b", r"\bgraphic\b"],
        "timeline": [r"\btimeline\b", r"\bsequenc", r"\bsync\b", r"\bcompos", r"\brender\b", r"\bmux\b", r"\bremotion\b"],
        "qc": [r"\bqc\b", r"\bquality\b", r"\bvalidat", r"\baudit\b", r"\bcheck\b", r"\btest\b", r"\binspect\b"],
    }

    # Primary capability heuristics with word boundaries
    CAPABILITY_HEURISTICS = [
        (r"\b(kinetic typograph\w*|typograph\w*|text animat\w*|animated text)\b", "kinetic_typography", "motion"),
        (r"\b(stacked bar|bar chart|pie chart|chart\w*|plot\w*|\bgraph\b)\b", "data_visualization", "motion"),
        (r"\b(transcrib\w*|speech to text|asr|subtitles)\b", "speech_to_text", "audio"),
        (r"\b(scene segment\w*|segment audio|detect scenes)\b", "scene_segmentation", "visual"),
        (r"\b(visual plan\w*|scene plan\w*|theme adapt\w*)\b", "visual_planning", "visual"),
        (r"\b(motion plan\w*|layout collision|safe area)\b", "motion_planning", "motion"),
        (r"\b(render video|mux|mp4 export)\b", "render_video", "timeline"),
        (r"\b(audio analys\w*|silence detect\w*|energy detect\w*)\b", "audio_analysis", "audio"),
        (r"\b(bilingual|orthograph\w*|telugu script)\b", "bilingual_preservation", "audio"),
        (r"\b(qc|quality check|validation)\b", "final_qc", "qc"),
    ]

    def parse_deterministic(self, text: str, extra_params: dict[str, Any] | None = None) -> ParsedRequirement:
        """Deterministic, rule-based natural language parser."""
        extra = extra_params or {}
        raw_text = (text or "").strip()
        text_lower = raw_text.lower()

        # 1. Identify primary capability and domain
        primary_cap = extra.get("primary_capability", "")
        domain = extra.get("domain", "")

        if not primary_cap or not domain:
            for pattern, cap_name, dom_name in self.CAPABILITY_HEURISTICS:
                if re.search(pattern, text_lower):
                    if not primary_cap:
                        primary_cap = cap_name
                    if not domain:
                        domain = dom_name
                    break

        if not domain:
            for dom_name, patterns in self.DOMAIN_PATTERNS.items():
                if any(re.search(p, text_lower) for p in patterns):
                    domain = dom_name
                    break

        if not domain:
            domain = "general"
        if not primary_cap:
            primary_cap = "general_processing"

        # 2. Extract structured constraints
        constraints: dict[str, Any] = {}

        # Aspect Ratio
        ar_match = re.search(r"\b(9:16|16:9|1:1|4:5|21:9)\b", text_lower)
        if ar_match:
            constraints["aspect_ratio"] = ar_match.group(1)
        elif "portrait" in text_lower or "reel" in text_lower or "shorts" in text_lower or "tiktok" in text_lower:
            constraints["aspect_ratio"] = "9:16"
        elif "landscape" in text_lower or "youtube" in text_lower:
            constraints["aspect_ratio"] = "16:9"

        # Language
        lang_match = re.search(r"\b(telugu|english|hindi|tamil|kannada|spanish|french|german)\b", text_lower)
        if lang_match:
            constraints["language"] = lang_match.group(1)
        elif "bilingual" in text_lower:
            constraints["language"] = "bilingual_telugu_english"

        # Determinism
        if "deterministic" in text_lower or "reproducible" in text_lower:
            constraints["deterministic_rendering"] = True

        # Smooth Transitions / Animation style
        if "smooth transition" in text_lower or "smooth" in text_lower:
            constraints["smooth_transitions"] = True
        if "spring" in text_lower:
            constraints["motion_curve"] = "spring"

        # FPS
        fps_match = re.search(r"\b(\d{2,3})\s*fps\b", text_lower)
        if fps_match:
            constraints["fps"] = fps_match.group(1)

        # Resolution
        res_match = re.search(r"\b(1080p|720p|4k|1920x1080|1080x1920)\b", text_lower)
        if res_match:
            constraints["resolution"] = res_match.group(1)

        # Chart specific
        if "stacked bar" in text_lower:
            constraints["chart_type"] = "stacked_bar_chart"
        elif "bar chart" in text_lower:
            constraints["chart_type"] = "bar_chart"

        # Overlay any explicitly passed constraints
        if "constraints" in extra and isinstance(extra["constraints"], dict):
            constraints.update(extra["constraints"])

        # 3. Tags and keywords extraction
        keywords = list({word for word in re.findall(r"\b[a-zA-Z]{3,}\b", text_lower)})
        tags = [domain, primary_cap]

        # 4. Inputs and outputs contracts derivation
        req_inputs = []
        exp_outputs = []
        if domain == "audio":
            req_inputs.extend(["audio_file", "audio_narration"])
            if "speech_to_text" in primary_cap or "transcrib" in primary_cap or "transcrib" in text_lower or "subtitles" in text_lower:
                exp_outputs.append("transcript_json")
        elif domain == "motion":
            req_inputs.append("scene_composition")
            exp_outputs.append("motion_specs")
        elif domain == "timeline":
            req_inputs.append("timeline_definition")
            exp_outputs.append("rendered_mp4")
        elif domain == "qc":
            req_inputs.append("rendered_media")
            exp_outputs.append("qc_report")

        # 5. Runtime dependencies
        dependencies = list(extra.get("runtime_dependencies") or [])
        if "render" in primary_cap or "timeline" in domain or "video" in text_lower:
            dependencies.append("ffmpeg")
        if "transcrib" in primary_cap or "whisper" in text_lower:
            dependencies.append("faster_whisper")
        if "kinetic" in primary_cap or "motion" in domain:
            dependencies.append("remotion")
        dependencies = list(dict.fromkeys(dependencies))

        # 6. Ambiguities identification
        ambiguities = list(extra.get("ambiguities") or [])
        if primary_cap == "general_processing":
            ambiguities.append("No specific functional capability pattern matched the request.")
        if primary_cap == "data_visualization" and "chart_type" not in constraints:
            ambiguities.append("Chart type not specified (e.g. bar, line, stacked).")
        if "aspect_ratio" not in constraints and domain in ("motion", "visual", "timeline"):
            ambiguities.append("Target aspect ratio not specified (defaulting to 16:9).")

        return ParsedRequirement(
            raw_query=raw_text,
            primary_capability=primary_cap,
            domain=domain,
            intent=str(extra.get("intent", "execute")),
            tags=list(extra.get("tags") or tags),
            keywords=list(extra.get("keywords") or keywords),
            constraints=constraints,
            required_inputs=list(extra.get("required_inputs") or req_inputs),
            expected_outputs=list(extra.get("expected_outputs") or exp_outputs),
            runtime_dependencies=dependencies,
            preferences=list(extra.get("preferences") or []),
            ambiguities=ambiguities,
            functional_requirements=list(extra.get("functional_requirements") or [f"Execute {primary_cap} in domain {domain}"]),
            performance_constraints=extra.get("performance_constraints") or {},
            acceptance_criteria=list(extra.get("acceptance_criteria") or [f"Verify {primary_cap} completion"]),
            explanation="Deterministic rule-based requirement parsing applied.",
            is_llm_interpreted=False,
        )

    def parse_llm(self, text: str, extra_params: dict[str, Any] | None = None) -> ParsedRequirement | None:
        """Parses complex or ambiguous queries via LLM Gateway with schema validation."""
        try:
            from SYSTEM.core import llm_gateway
        except ImportError:
            return None

        extra = extra_params or {}
        raw_text = (text or "").strip()

        sys_prompt = (
            "You are the Capability Discovery Specialist in the LAXMAN-AUTONOMOUS multi-agent system. "
            "Analyze the user requirement and return valid JSON adhering to the following schema:\n"
            "{\n"
            '  "primary_capability": "snake_case_name",\n'
            '  "domain": "audio|motion|visual|timeline|qc|general",\n'
            '  "intent": "execute|discover|create_skill|inspect|validate",\n'
            '  "functional_requirements": ["string"],\n'
            '  "constraints": {"aspect_ratio": "16:9|9:16", "language": "telugu|english|bilingual", ...},\n'
            '  "required_inputs": ["string"],\n'
            '  "expected_outputs": ["string"],\n'
            '  "runtime_dependencies": ["ffmpeg", "faster_whisper", "remotion", ...],\n'
            '  "ambiguities": ["string"],\n'
            '  "acceptance_criteria": ["string"],\n'
            '  "keywords": ["string"],\n'
            '  "tags": ["string"],\n'
            '  "explanation": "brief 1-sentence rationale"\n'
            "}"
        )

        user_prompt = f"Requirement query: {raw_text}\nContext parameters: {json.dumps(extra)}"

        req = llm_gateway.LlmGatewayRequest(
            project_id="capability_finder",
            stage_id="discovery",
            agent_id="capability_finder",
            purpose="decision",
            model_profile="fast_structured",
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            timeout=15,
            max_retries=1,
        )

        try:
            gw = llm_gateway.get_gateway()
            resp = gw.execute(req)
            if resp.status not in ("passed", "succeeded"):
                logger.info(f"LLM requirement parsing gateway returned non-pass status '{resp.status}'. Falling back.")
                return None

            data = resp.structured_data
            if data is None and resp.raw_text:
                try:
                    data = json.loads(resp.raw_text)
                except Exception:
                    pass

            if not isinstance(data, dict):
                return None

            primary_cap = str(data.get("primary_capability") or extra.get("primary_capability") or "general_processing")
            domain = str(data.get("domain") or extra.get("domain") or "general")
            if domain not in ("audio", "motion", "visual", "timeline", "qc", "general"):
                domain = "general"

            constraints = data.get("constraints") or {}
            if not isinstance(constraints, dict):
                constraints = {}
            if "constraints" in extra and isinstance(extra["constraints"], dict):
                constraints.update(extra["constraints"])

            return ParsedRequirement(
                raw_query=raw_text,
                primary_capability=primary_cap,
                domain=domain,
                intent=str(data.get("intent", "execute")),
                tags=list(data.get("tags") or [domain, primary_cap]),
                keywords=list(data.get("keywords") or [primary_cap]),
                constraints=constraints,
                required_inputs=list(data.get("required_inputs") or []),
                expected_outputs=list(data.get("expected_outputs") or []),
                runtime_dependencies=list(data.get("runtime_dependencies") or []),
                preferences=list(data.get("preferences") or []),
                ambiguities=list(data.get("ambiguities") or []),
                functional_requirements=list(data.get("functional_requirements") or []),
                performance_constraints=data.get("performance_constraints") or {},
                acceptance_criteria=list(data.get("acceptance_criteria") or []),
                explanation=str(data.get("explanation", "LLM-assisted requirement understanding")),
                is_llm_interpreted=True,
            )

        except Exception as e:
            logger.info(f"LLM requirement parsing unavailable ({e}). Using deterministic fallback.")
            return None

    def parse(
        self,
        query_or_spec: str | dict[str, Any],
        extra_params: dict[str, Any] | None = None,
        use_llm: bool = True,
    ) -> ParsedRequirement:
        """Parses a natural-language query or parameter set into a structured ParsedRequirement.
        
        Attempts LLM semantic interpretation first for substantive natural-language requests,
        falling back seamlessly to deterministic rule-based parsing.
        """
        extra = dict(extra_params or {})

        if isinstance(query_or_spec, dict):
            # Extract query text and overlay explicit parameters
            text = str(query_or_spec.get("query") or query_or_spec.get("raw_query") or query_or_spec.get("requirement") or "")
            extra.update({k: v for k, v in query_or_spec.items() if k not in ("query", "raw_query", "requirement")})
        else:
            text = str(query_or_spec or "")

        # Use LLM for queries that are natural-language requests without explicit primary_capability overrides
        if use_llm and not extra.get("primary_capability") and len(text.strip().split()) >= 6:
            llm_result = self.parse_llm(text, extra)
            if llm_result is not None:
                return llm_result

        # Deterministic fallback
        return self.parse_deterministic(text, extra)


requirement_parser = RequirementParser()
