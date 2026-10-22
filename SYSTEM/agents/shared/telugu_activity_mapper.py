"""Natural Telugu Activity Mapper for Agent-to-Agent Communication.

Provides deterministic, lightweight, Unicode-compliant mapping of:
1. Canonical pipeline milestones
2. 21 canonical registered agents' operations (started, running, completed, blocked, failed)
3. Inter-agent handoffs and delegations
4. Truthful progress percentages and stage weightings
5. Safe secret redaction and graceful fallback without fabricating completed work
"""
from __future__ import annotations

from typing import Any

from SYSTEM.core.resilience import sanitize_secrets

# Canonical stage weights for progress calculation
STAGE_WEIGHTS: dict[str, tuple[float, float]] = {
    # stage_id: (start_percent, completed_percent)
    "audio": (0.0, 5.0),
    "analyzer": (5.0, 15.0),
    "segmentation": (15.0, 25.0),
    "planning": (25.0, 38.0),
    "assets": (38.0, 42.0),
    "motion_plan": (42.0, 50.0),
    "motion_gen": (50.0, 65.0),
    "motion_validation": (65.0, 75.0),
    "timeline": (75.0, 82.0),
    "approval": (82.0, 88.0),
    "render": (88.0, 95.0),
    "qc": (95.0, 98.0),
    "final": (98.0, 100.0),
}

# Canonical user-friendly Telugu names for agents
AGENT_TELUGU_NAMES: dict[str, str] = {
    "main_architecture_agent": "ఆర్కిటెక్చర్ ఏజెంట్",
    "capability_finder": "స్కిల్ అన్వేషణ ఏజెంట్",
    "skill_factory": "స్కిల్ తయారీ ఏజెంట్",
    "audio_input": "ఆడియో ఇన్‌పుట్ ఏజెంట్",
    "audio_analyzer": "ఆడియో విశ్లేషణ ఏజెంట్",
    "scene_segmentation": "దృశ్య విభజన ఏజెంట్",
    "visual_planning": "విజువల్ ప్లానింగ్ ఏజెంట్",
    "asset_collection": "అసెట్ సేకరణ ఏజెంట్",
    "image_generator": "చిత్ర రూపకల్పన ఏజెంట్",
    "motion_planning": "మోషన్ ప్లానింగ్ ఏజెంట్",
    "motion_animation": "యానిమేషన్ కోడ్ ఏజెంట్",
    "motion_timeline_validation": "మోషన్ సమన్వయ ఏజెంట్",
    "timeline_build": "టైమ్‌లైన్ నిర్మాణ ఏజెంట్",
    "timeline_approval": "టైమ్‌లైన్ ఆమోద ఏజెంట్",
    "render_video": "వీడియో రెండరింగ్ ఏజెంట్",
    "final_qc": "నాణ్యతా నియంత్రణ ఏజెంట్",
    "final_video_delivery": "వీడియో డెలివరీ ఏజెంట్",
    "verification_and_test": "ధృవీకరణ మరియు పరీక్ష ఏజెంట్",
    "security_policy": "భద్రతా విధాన ఏజెంట్",
    "autonomous_execution": "స్వయంప్రతిపత్తి నిర్వహణ ఏజెంట్",
    "video_pipeline_orchestrator": "పైప్‌లైన్ ఆర్కెస్ట్రేటర్",
    "resource_manager": "వనరుల నిర్వహణ ఏజెంట్",
}

# Explicit canonical milestone phrases requested in Stage 4 specification
MILESTONE_MESSAGES: dict[str, str] = {
    "audio_accepted": "ఆడియో అందింది. వీడియో తయారీ ప్రారంభిస్తున్నాను.",
    "audio_analysis": "ఆడియోలోని మాటలను, సమయ వివరాలను పరిశీలిస్తున్నాను.",
    "transcript_processing": "ఆడియో మాటలు, వాటి సమయాలను సిద్ధం చేస్తున్నాను.",
    "scene_segmentation": "ఆడియో ఆధారంగా వీడియో దృశ్యాలను విభజిస్తున్నాను.",
    "skill_lookup": "ఈ పనికి సరిపోయే skill కోసం వెతుకుతున్నాను.",
    "github_discovery": "అవసరమైన skill కోసం బయటి repositoriesను పరిశీలిస్తున్నాను.",
    "skill_validation": "కొత్త skill సరిగ్గా పనిచేస్తుందో పరీక్షిస్తున్నాను.",
    "visual_planning": "ప్రతి దృశ్యానికి సరిపోయే visualsను ప్లాన్ చేస్తున్నాను.",
    "motion_planning": "దృశ్యాలకు తగిన animationsను సిద్ధం చేస్తున్నాను.",
    "timeline_building": "అన్ని దృశ్యాలను సరైన క్రమంలో అమర్చుతున్నాను.",
    "rendering": "వీడియోను తయారు చేస్తున్నాను.",
    "technical_qc": "వీడియో నాణ్యతను పరీక్షిస్తున్నాను.",
    "recovery": "వచ్చిన సమస్యను పరిష్కరించి మళ్లీ ప్రయత్నిస్తున్నాను.",
    "recovery_detected": "సమస్యను గుర్తించాను. కారణాన్ని పరిశీలిస్తున్నాను.",
    "recovery_safe_to_retry": "మళ్లీ ప్రయత్నించడం సురక్షితమని నిర్ధారించాను.",
    "recovery_retrying": "మళ్లీ ప్రయత్నిస్తున్నాను.",
    "recovery_resume_checkpoint": "చివరిగా ధృవీకరించిన దశ నుంచి పనిని కొనసాగిస్తున్నాను.",
    "recovery_verified_previous": "మునుపటి పని విజయవంతంగా పూర్తైందని నిర్ధారించాను.",
    "recovery_unresolvable": "సమస్యను స్వయంగా పరిష్కరించలేకపోయాను. అదనపు పరిశీలన అవసరం.",
    "recovery_needs_review": "ఈ పనిని సురక్షితంగా కొనసాగించలేను. అదనపు పరిశీలన అవసరం.",
    "waiting_for_approval": "ఈ పనిని కొనసాగించడానికి అవసరమైన అనుమతి కోసం వేచి ఉన్నాను.",
    "task_blocked": "ఒక సమస్య వల్ల పని ముందుకు సాగడం లేదు. వివరాలు పరిశీలిస్తున్నాను.",
    "desktop_delivery": "పూర్తయిన వీడియోను మీ డెస్క్టాప్లో భద్రపరుస్తున్నాను.",
    "completion": "వీడియో తయారైంది. అవసరమైన పరీక్షలు పూర్తయ్యాయి.",
}

# Operations per agent: (started/running, completed)
AGENT_ACTIVITIES: dict[str, dict[str, str]] = {
    "audio_input": {
        "started": "ఆడియో అందింది. ప్రాథమిక పరిశీలన చేస్తున్నాను.",
        "completed": "ఆడియో విజయవంతంగా లోడ్ అయింది.",
    },
    "audio_analyzer": {
        "started": "ఆడియోలోని మాటలను, సమయ వివరాలను పరిశీలిస్తున్నాను.",
        "completed": "ఆడియో విశ్లేషణ పూర్తయింది.",
    },
    "scene_segmentation": {
        "started": "ఆడియో ఆధారంగా వీడియో దృశ్యాలను విభజిస్తున్నాను.",
        "completed": "దృశ్యాల విభజన విజయవంతంగా పూర్తయింది.",
    },
    "visual_planning": {
        "started": "ప్రతి దృశ్యానికి సరిపోయే visualsను ప్లాన్ చేస్తున్నాను.",
        "completed": "విజువల్ ప్లానింగ్ పూర్తయింది.",
    },
    "asset_collection": {
        "started": "అవసరమైన నిజమైన ఫోటోలు, వీడియో క్లిప్‌లను సేకరిస్తున్నాను.",
        "completed": "నిజమైన ఫోటోలు, క్లిప్‌ల సేకరణ పూర్తయింది.",
    },
    "image_generator": {
        "started": "దృశ్యాల కోసం చిత్రాలను రూపొందిస్తున్నాను.",
        "completed": "చిత్రాల రూపకల్పన పూర్తయింది.",
    },
    "motion_planning": {
        "started": "దృశ్యాలకు తగిన animationsను సిద్ధం చేస్తున్నాను.",
        "completed": "మోషన్ ప్లాన్ సిద్ధమైంది.",
    },
    "motion_animation": {
        "started": "Remotion కాంపోజిషన్ కోడ్ తయారు చేస్తున్నాను.",
        "completed": "యానిమేషన్ కోడ్ సిద్ధమైంది.",
    },
    "motion_timeline_validation": {
        "started": "యానిమేషన్ మరియు టైమ్‌లైన్ సమన్వయాన్ని పరీక్షిస్తున్నాను.",
        "completed": "మోషన్ సమన్వయ పరీక్ష విజయవంతమైంది.",
    },
    "timeline_build": {
        "started": "అన్ని దృశ్యాలను సరైన క్రమంలో అమర్చుతున్నాను.",
        "completed": "టైమ్‌లైన్ నిర్మాణం పూర్తయింది.",
    },
    "timeline_approval": {
        "started": "ఈ పనిని కొనసాగించడానికి అవసరమైన అనుమతి కోసం వేచి ఉన్నాను.",
        "completed": "టైమ్‌లైన్ ఆమోదం లభించింది.",
    },
    "render_video": {
        "started": "వీడియోను తయారు చేస్తున్నాను.",
        "completed": "వీడియో రెండరింగ్ పూర్తయింది.",
    },
    "final_qc": {
        "started": "వీడియో నాణ్యతను పరీక్షిస్తున్నాను.",
        "completed": "నాణ్యతా పరీక్షలు విజయవంతంగా పూర్తయ్యాయి.",
    },
    "final_video_delivery": {
        "started": "పూర్తయిన వీడియోను మీ డెస్క్టాప్లో భద్రపరుస్తున్నాను.",
        "completed": "వీడియో తయారైంది. అవసరమైన పరీక్షలు పూర్తయ్యాయి.",
    },
    "capability_finder": {
        "started": "ఈ పనికి సరిపోయే skill కోసం వెతుకుతున్నాను.",
        "completed": "అవసరమైన సామర్థ్యాలు గుర్తించబడ్డాయి.",
    },
    "skill_factory": {
        "started": "కొత్త skill సరిగ్గా పనిచేస్తుందో పరీక్షిస్తున్నాను.",
        "completed": "కొత్త skill విజయవంతంగా రూపొందించబడింది.",
    },
    "verification_and_test": {
        "started": "సిస్టమ్ ఖచ్చితత్వాన్ని పరీక్షిస్తున్నాను.",
        "completed": "పరీక్షలు విజయవంతంగా ముగిశాయి.",
    },
    "security_policy": {
        "started": "భద్రతా నిబంధనలను తనిఖీ చేస్తున్నాను.",
        "completed": "భద్రతా అనుమతి ధృవీకరించబడింది.",
    },
    "autonomous_execution": {
        "started": "పనిని స్వయంచాలకంగా కొనసాగిస్తున్నాను.",
        "completed": "స్వయంప్రతిపత్తితో కూడిన పని పూర్తయింది.",
    },
    "main_architecture_agent": {
        "started": "సిస్టమ్ ఆర్కిటెక్చర్‌ను సమన్వయం చేస్తున్నాను.",
        "completed": "ఆర్కిటెక్చర్ టాస్క్ పూర్తయింది.",
    },
    "video_pipeline_orchestrator": {
        "started": "వీడియో ప్రాసెస్ క్రమాన్ని పర్యవేక్షిస్తున్నాను.",
        "completed": "వీడియో ప్రాసెస్ క్రమం పూర్తయింది.",
    },
    "resource_manager": {
        "started": "సిస్టమ్ వనరులను సమన్వయం చేస్తున్నాను.",
        "completed": "వనరుల నిర్వహణ విజయవంతమైంది.",
    },
}

class TeluguActivityMapper:
    """Maps structured agent messages, lifecycle events, and handoffs to natural Telugu."""

    def calculate_progress(
        self,
        stage_id: str,
        status: str,
        explicit_progress: float | None = None,
    ) -> float:
        """Computes truthful progress percentage based on stage weighting and status.
        Never reports 100% on failed, blocked, or intermediate stages.
        """
        weights = STAGE_WEIGHTS.get(stage_id)
        if explicit_progress is not None:
            pct = round(float(explicit_progress), 1)
            if weights:
                start_pct, comp_pct = weights
                pct = max(start_pct, min(comp_pct, pct))
            elif pct >= 100.0 and (stage_id != "final" or status not in ("completed", "succeeded")):
                pct = 99.0
            return max(0.0, min(100.0, pct))

        if not weights:
            if status in ("completed", "succeeded") and stage_id in ("final", "delivery"):
                return 100.0
            return 50.0 if status in ("started", "running") else 0.0

        start_pct, comp_pct = weights
        if status in ("completed", "succeeded"):
            return comp_pct
        elif status in ("failed", "blocked"):
            # Progress remains truthfully at the start of this stage
            return start_pct
        elif status in ("started", "running"):
            # Midway inside the stage range
            return round(start_pct + (comp_pct - start_pct) * 0.5, 1)
        elif status == "waiting_for_approval":
            return round(start_pct + (comp_pct - start_pct) * 0.9, 1)
        return start_pct

    def sanitize_text(self, text: str) -> str:
        """Sanitizes sensitive tokens, API keys, and credentials."""
        return sanitize_secrets(text)

    def format_handoff(self, sender: str, recipient: Any, reason: str = "") -> str:
        """Formats natural Telugu message for agent-to-agent delegation."""
        if isinstance(recipient, list):
            recip_names = [AGENT_TELUGU_NAMES.get(r, str(r)) for r in recipient]
            recipient_str = ", ".join(recip_names)
        else:
            recipient_str = AGENT_TELUGU_NAMES.get(str(recipient), str(recipient))
        sender_name = AGENT_TELUGU_NAMES.get(sender, sender)
        return f"{sender_name} నుండి {recipient_str}కు పని అప్పగించబడింది."

    map_handoff = format_handoff

    def format_review_feedback(self, verdict: str, score: float | None = None, summary: str = "") -> str:
        """Formats review feedback into natural Telugu."""
        v_lower = str(verdict).lower()
        if v_lower in ("approved", "success", "pass"):
            v_text = "ఆమోదించబడింది"
        elif v_lower in ("changes_requested", "needs_work", "failed"):
            v_text = "మార్పులు సూచించబడ్డాయి"
        else:
            v_text = "సమీక్షించబడింది"
        score_str = f" ({score:.1f}%)" if score is not None else ""
        return f"సమీక్ష పూర్తయింది. నిర్ణయం: {v_text}{score_str}."

    map_review_feedback = format_review_feedback

    def map_event(
        self,
        stage_id: str = "",
        agent_id: str = "",
        message_type: str = "agent_message",
        status: str = "sent",
        content: str = "",
        metadata: dict[str, Any] | None = None,
        recipient_agent_ids: list[str] | None = None,
    ) -> str:
        """Determines natural Telugu activity text based on actual operation details."""
        metadata = metadata or {}
        event_name = str(metadata.get("event") or "").lower()
        content_lower = content.lower()
        clean_status = status.lower()

        # 1. Recovery milestones check
        if event_name in MILESTONE_MESSAGES and event_name.startswith("recovery"):
            return MILESTONE_MESSAGES[event_name]

        # 2. Handoff check
        if message_type == "handoff" or "handoff" in event_name or "handoff" in content_lower:
            recipients = recipient_agent_ids or []
            recipient = recipients[0] if recipients else (metadata.get("recipient_agent_id") or "ఇతర ఏజెంట్")
            return self.map_handoff(agent_id or "ఏజెంట్", str(recipient), content)

        # 3. Review feedback check
        if (
            str(message_type).lower() in ("review_feedback", "messagetype.review_feedback")
            or event_name in ("review", "review_feedback", "review_verdict")
            or "review verdict" in content_lower
        ):
            score = metadata.get("score")
            return self.format_review_feedback(verdict=clean_status, score=score, summary=content)

        # 4. Blocked check
        if clean_status == "blocked" or "blocked" in event_name or "blocked" in content_lower:
            return MILESTONE_MESSAGES["task_blocked"]

        # 5. Approval check
        if (
            clean_status in ("needs_review", "awaiting_approval")
            or "approval" in event_name
            or "waiting for approval" in content_lower
            or stage_id == "approval"
            and clean_status == "running"
        ):
            return MILESTONE_MESSAGES["waiting_for_approval"]

        # 6. Failure & Recovery fallback checks

        if clean_status == "failed" or "failed" in event_name:
            if "retry" in content_lower or "recovering" in content_lower or "recover" in content_lower:
                return MILESTONE_MESSAGES["recovery"]
            return "పనిలో లోపం ఏర్పడింది. కారణాన్ని పరిశీలిస్తున్నాను."

        if "retry" in event_name or "recovering" in content_lower:
            return MILESTONE_MESSAGES["recovery"]

        # 5. Explicit milestone keywords in content or metadata
        if "github" in content_lower or "github" in event_name:
            return MILESTONE_MESSAGES["github_discovery"]
        if "skill lookup" in content_lower or "lookup" in event_name:
            return MILESTONE_MESSAGES["skill_lookup"]
        if "skill validat" in content_lower:
            return MILESTONE_MESSAGES["skill_validation"]
        if "desktop" in content_lower and ("deliver" in content_lower or "save" in content_lower):
            return MILESTONE_MESSAGES["desktop_delivery"]

        # 6. Final completion check (strictly requires terminal success)
        if (
            (stage_id in ("final", "delivery") or agent_id == "final_video_delivery")
            and clean_status in ("succeeded", "completed")
            and "complete" in (event_name or content_lower or clean_status)
        ):
            return MILESTONE_MESSAGES["completion"]

        # 7. Agent-specific activity mapping
        agent_key = agent_id or metadata.get("sender_agent_id") or ""
        agent_acts = AGENT_ACTIVITIES.get(agent_key)
        if agent_acts:
            if clean_status in ("completed", "succeeded") or event_name == "completed":
                return agent_acts["completed"]
            elif clean_status in ("started", "running", "sent") or event_name == "started":
                return agent_acts["started"]

        # 8. Stage-specific activity mapping
        stage_acts = {
            "audio": ("audio_input", MILESTONE_MESSAGES["audio_accepted"]),
            "analyzer": ("audio_analyzer", MILESTONE_MESSAGES["audio_analysis"]),
            "segmentation": ("scene_segmentation", MILESTONE_MESSAGES["scene_segmentation"]),
            "planning": ("visual_planning", MILESTONE_MESSAGES["visual_planning"]),
            "assets": ("asset_collection", "అవసరమైన నిజమైన ఫోటోలు, వీడియో క్లిప్‌లను సేకరిస్తున్నాను."),
            "motion_plan": ("motion_planning", MILESTONE_MESSAGES["motion_planning"]),
            "motion_gen": ("motion_animation", "Remotion కాంపోజిషన్ కోడ్ తయారు చేస్తున్నాను."),
            "motion_validation": ("motion_timeline_validation", "యానిమేషన్ మరియు టైమ్‌లైన్ సమన్వయాన్ని పరీక్షిస్తున్నాను."),
            "timeline": ("timeline_build", MILESTONE_MESSAGES["timeline_building"]),
            "approval": ("timeline_approval", MILESTONE_MESSAGES["waiting_for_approval"]),
            "render": ("render_video", MILESTONE_MESSAGES["rendering"]),
            "qc": ("final_qc", MILESTONE_MESSAGES["technical_qc"]),
            "final": ("final_video_delivery", MILESTONE_MESSAGES["desktop_delivery"]),
        }
        if stage_id in stage_acts:
            _, phrase = stage_acts[stage_id]
            if clean_status in ("completed", "succeeded") or event_name == "completed":
                return f"{phrase.split('.')[0]} పూర్తయింది."
            return phrase

        # 9. Truthful fallback
        if clean_status in ("completed", "succeeded"):
            return "పని విజయవంతంగా పూర్తయింది."
        elif clean_status in ("running", "started"):
            return "పని కొనసాగుతోంది."
        return "పని పురోగతిలో ఉంది."

    def map_message_to_telugu(self, message: Any) -> tuple[str, float]:
        """Processes an AgentMessage object, returns (telugu_activity, progress_percent)."""
        stage_id = getattr(message, "stage_id", "") or ""
        agent_id = getattr(message, "sender_agent_id", "") or getattr(message, "agent_id", "") or ""
        msg_type = getattr(message, "message_type", "agent_message")
        status = getattr(message, "status", "sent")
        content = getattr(message, "content", "") or ""
        metadata = getattr(message, "metadata", {}) or {}
        recipients = getattr(message, "recipient_agent_ids", []) or []
        explicit_prog = getattr(message, "progress_percent", None)

        telugu_text = self.map_event(
            stage_id=stage_id,
            agent_id=agent_id,
            message_type=msg_type,
            status=status,
            content=content,
            metadata=metadata,
            recipient_agent_ids=recipients,
        )

        progress = self.calculate_progress(
            stage_id=stage_id,
            status=status,
            explicit_progress=explicit_prog,
        )

        return telugu_text, progress


# Global singleton mapper instance
telugu_activity_mapper = TeluguActivityMapper()


def map_activity(
    stage_id: str = "",
    agent_id: str = "",
    message_type: str = "agent_message",
    status: str = "sent",
    content: str = "",
    metadata: dict[str, Any] | None = None,
    recipient_agent_ids: list[str] | None = None,
) -> str:
    """Convenience helper to map an event to natural Telugu."""
    return telugu_activity_mapper.map_event(
        stage_id=stage_id,
        agent_id=agent_id,
        message_type=message_type,
        status=status,
        content=content,
        metadata=metadata or {},
        recipient_agent_ids=recipient_agent_ids or [],
    )


def map_handoff(from_agent: str, to_agents: list[str] | str, reason: str = "") -> str:
    """Convenience helper to format an inter-agent handoff in Telugu."""
    return telugu_activity_mapper.format_handoff(from_agent, to_agents, reason)


def map_review_feedback(verdict: str, score: float | None = None, summary: str = "") -> str:
    """Convenience helper to format review feedback in Telugu."""
    return telugu_activity_mapper.format_review_feedback(verdict, score, summary)


def calculate_progress(stage_id: str, status: str = "running", explicit_progress: float | None = None) -> float:
    """Convenience helper to calculate truthful progress."""
    return telugu_activity_mapper.calculate_progress(stage_id, status, explicit_progress)
