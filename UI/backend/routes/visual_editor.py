"""FastAPI routes for Visual AI Editor: feedback sticky-notes, LLM communication,
5-step implementation planning, separate approval gates, and testing execution.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from SYSTEM.core import llm_client
from SYSTEM.registries.agent_registry import registry

router = APIRouter(prefix="/visual-editor", tags=["visual-editor"])

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "visual_editor"
FEEDBACK_FILE = CONFIG_DIR / "feedback.json"
SESSIONS_FILE = CONFIG_DIR / "sessions.json"

_editor_lock = threading.RLock()


# Verified Component & Source-File Catalog
VERIFIED_COMPONENT_CATALOG = [
    {
        "id": "stage-card",
        "name": "Stage Card",
        "component": "StageCard",
        "source_file": "UI/frontend/src/components/StageCard.tsx",
        "page": "Pipeline Execution Flow",
        "route": "/pipeline",
        "selector": "[data-testid^='stage-card-']",
        "description": "Displays stage number, icon, status badge, percentage, and label in the 12-stage sequential flow."
    },
    {
        "id": "pipeline-canvas",
        "name": "Pipeline Execution Flow Canvas",
        "component": "PipelineCanvas",
        "source_file": "UI/frontend/src/components/PipelineCanvas.tsx",
        "page": "Pipeline Execution Flow",
        "route": "/pipeline",
        "selector": "[data-testid='stages-container']",
        "description": "Sequential connected flow canvas, inter-row transition banners, and action controls."
    },
    {
        "id": "stage-execution-tracking",
        "name": "Stage Execution Tracking Panel",
        "component": "StageExecutionTracking",
        "source_file": "UI/frontend/src/components/StageExecutionTracking.tsx",
        "page": "Pipeline Execution Flow",
        "route": "/pipeline",
        "selector": "[data-testid='stage-execution-tracking']",
        "description": "Dynamic right panel showing ordered sub-stages of the active agent with real-time percentage and live telemetry."
    },
    {
        "id": "audio-input-form",
        "name": "New Project / Audio Ingest Form",
        "component": "AudioInputPage",
        "source_file": "UI/frontend/src/pages/AudioInputPage.tsx",
        "page": "New Project",
        "route": "/pipeline#new-project",
        "selector": "[data-testid='audio-input-container']",
        "description": "Compact project title, audio upload dropzone, aspect ratio selector, and Analyze Audio action."
    },
    {
        "id": "dashboard-metric-cards",
        "name": "Dashboard Metric Cards",
        "component": "DashboardPage",
        "source_file": "UI/frontend/src/pages/DashboardPage.tsx",
        "page": "Dashboard",
        "route": "/dashboard",
        "selector": "[data-testid='top-metric-cards']",
        "description": "Total Pipeline Runs, Active Stage Events, 21 Autonomous Agents, and Operation Effect cards."
    },
    {
        "id": "agent-communication-panel",
        "name": "Agent Communication Panel",
        "component": "AgentCommunicationPanel",
        "source_file": "UI/frontend/src/components/AgentCommunicationPanel.tsx",
        "page": "Agent Communication",
        "route": "/pipeline#communication",
        "selector": "[data-testid='agent-communication-panel']",
        "description": "Real-time communication log with agent handoff visualizer and LLM model badges."
    },
    {
        "id": "navigation-sidebar",
        "name": "Main Sidebar Navigation",
        "component": "Sidebar",
        "source_file": "UI/frontend/src/components/Sidebar.tsx",
        "page": "Global Navigation",
        "route": "/*",
        "selector": "aside",
        "description": "Deep navy sidebar with brand mark, collapsible navigation links, and version badge."
    },
    {
        "id": "app-header",
        "name": "Application Top Header",
        "component": "Header",
        "source_file": "UI/frontend/src/components/Header.tsx",
        "page": "Global Navigation",
        "route": "/*",
        "selector": "header",
        "description": "Sticky top bar with project breadcrumb, theme toggle, fastAPI health badge, and active LLM counter."
    }
]


def _ensure_storage() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not FEEDBACK_FILE.exists():
        initial_feedback = [
            {
                "id": "fb-seed-01",
                "projectId": "sample-01",
                "page": "Pipeline Execution Flow",
                "route": "/pipeline",
                "elementSelector": "[data-testid^='stage-card-']",
                "elementName": "Stage Card Status Badge",
                "componentRef": "StageCard",
                "sourceFile": "UI/frontend/src/components/StageCard.tsx",
                "isSourceMapped": True,
                "category": "layout",
                "feedback": "Optimize card vertical padding and ensure percentage number remains crisp on high-DPI displays.",
                "status": "pending",
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tags": ["layout", "typography", "responsive"]
            },
            {
                "id": "fb-seed-02",
                "projectId": "sample-01",
                "page": "New Project",
                "route": "/pipeline#new-project",
                "elementSelector": "[data-testid='analyze-audio-btn']",
                "elementName": "Analyze Audio Action Button",
                "componentRef": "AudioInputPage",
                "sourceFile": "UI/frontend/src/pages/AudioInputPage.tsx",
                "isSourceMapped": True,
                "category": "alignment",
                "feedback": "Keep button clearly pinned above the viewport bottom with 0px scroll required.",
                "status": "in_review",
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600)),
                "tags": ["viewport", "spacing"]
            },
            {
                "id": "fb-seed-03",
                "projectId": "sample-01",
                "page": "Dashboard",
                "route": "/dashboard",
                "elementSelector": "[data-testid='top-metric-cards']",
                "elementName": "Metric Cards Grid",
                "componentRef": "DashboardPage",
                "sourceFile": "UI/frontend/src/pages/DashboardPage.tsx",
                "isSourceMapped": True,
                "category": "style",
                "feedback": "Maintain identical card heights and subtle border glow on dark theme.",
                "status": "approved_for_plan",
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7200)),
                "tags": ["cards", "dark-theme"]
            }
        ]
        FEEDBACK_FILE.write_text(json.dumps(initial_feedback, indent=2), encoding="utf-8")

    if not SESSIONS_FILE.exists():
        SESSIONS_FILE.write_text(json.dumps({}, indent=2), encoding="utf-8")


def _read_feedback() -> list[dict[str, Any]]:
    _ensure_storage()
    with _editor_lock:
        try:
            return json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []


def _write_feedback(items: list[dict[str, Any]]) -> None:
    _ensure_storage()
    with _editor_lock:
        FEEDBACK_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def _normalize_session(project_id: str, session: dict[str, Any] | None) -> dict[str, Any]:
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not isinstance(session, dict):
        session = {}
    session.setdefault("projectId", project_id)
    session.setdefault("currentStep", 1)
    session.setdefault("selectedFeedbackIds", [])
    session.setdefault("plan", None)
    session.setdefault("planApproved", False)
    session.setdefault("implementationAuthorized", False)
    session.setdefault("implementationStatus", "idle")
    session.setdefault("testResults", None)
    session.setdefault("finalUiStatus", "pending_review")
    if not isinstance(session.get("chatMessages"), list) or len(session.get("chatMessages", [])) == 0:
        session["chatMessages"] = [
            {
                "id": "msg-init",
                "sender": "agent",
                "agentId": "main_architecture_agent",
                "agentName": "Main Architecture Agent",
                "content": "Hello! I am your configured Architecture & UI Engineering Agent. You can select UI elements, attach sticky-note feedback, discuss changes with me, and review implementation plans. What would you like to refine today?",
                "timestamp": now_iso
            }
        ]
    session.setdefault("updatedAt", now_iso)
    return session


def _read_sessions() -> dict[str, Any]:
    _ensure_storage()
    with _editor_lock:
        try:
            data = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
            for pid, sess in list(data.items()):
                data[pid] = _normalize_session(pid, sess)
            return data
        except Exception:
            return {}


def _write_sessions(data: dict[str, Any]) -> None:
    _ensure_storage()
    with _editor_lock:
        SESSIONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# Request/Response Schemas
class FeedbackCreatePayload(BaseModel):
    projectId: str = "sample-01"
    page: str
    route: str = "/pipeline"
    elementSelector: str
    elementName: str
    componentRef: str | None = None
    sourceFile: str | None = None
    isSourceMapped: bool = True
    category: str = "layout"
    feedback: str
    tags: list[str] = Field(default_factory=list)
    visualRef: str | None = None


class FeedbackUpdatePayload(BaseModel):
    feedback: str | None = None
    status: Literal["pending", "in_review", "approved_for_plan", "implemented", "resolved"] | None = None
    category: str | None = None
    tags: list[str] | None = None


class ChatRequestPayload(BaseModel):
    projectId: str = "sample-01"
    message: str
    selectedFeedbackIds: list[str] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)


class PlanGeneratePayload(BaseModel):
    projectId: str = "sample-01"
    feedbackIds: list[str] = Field(default_factory=list)


class PlanDecisionPayload(BaseModel):
    projectId: str = "sample-01"
    planId: str
    decision: Literal["approved", "rejected"]
    notes: str | None = None


class ImplementationAuthPayload(BaseModel):
    projectId: str = "sample-01"
    planId: str


class FinalUiDecisionPayload(BaseModel):
    projectId: str = "sample-01"
    decision: Literal["approved", "changes_requested"]
    reason: str | None = None


# --- 1. Component Catalog ---
@router.get("/component-catalog")
def get_component_catalog() -> list[dict[str, Any]]:
    """Returns the verified registry of frontend components and source files."""
    return VERIFIED_COMPONENT_CATALOG


# --- 2. Feedback Notes CRUD ---
@router.get("/feedback")
def list_feedback(project_id: str | None = None) -> list[dict[str, Any]]:
    """Lists sticky-note feedback items with optional project filter."""
    items = _read_feedback()
    if project_id:
        matched = [i for i in items if i.get("projectId") == project_id or not i.get("projectId")]
        if matched:
            return matched
        return items
    return items


@router.post("/feedback", status_code=201)
def create_feedback(body: FeedbackCreatePayload) -> dict[str, Any]:
    """Creates and persists a new visual feedback sticky note."""
    items = _read_feedback()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    new_id = f"fb-{int(time.time() * 1000)}-{os.urandom(2).hex()}"

    # Auto-resolve component and source file from catalog if matched
    matched = next((c for c in VERIFIED_COMPONENT_CATALOG if c["selector"] == body.elementSelector or c["name"].lower() in body.elementName.lower()), None)
    comp_ref = body.componentRef or (matched["component"] if matched else "UnmappedComponent")
    src_file = body.sourceFile or (matched["source_file"] if matched else "Approximated / Unmapped")
    is_mapped = bool(matched) if body.sourceFile is None else body.isSourceMapped

    item = {
        "id": new_id,
        "projectId": body.projectId,
        "page": body.page,
        "route": body.route,
        "elementSelector": body.elementSelector,
        "elementName": body.elementName,
        "componentRef": comp_ref,
        "sourceFile": src_file,
        "isSourceMapped": is_mapped,
        "category": body.category,
        "feedback": body.feedback.strip(),
        "status": "pending",
        "createdAt": now_iso,
        "tags": body.tags or [body.category],
        "visualRef": body.visualRef
    }
    items.insert(0, item)
    _write_feedback(items)
    return item


@router.put("/feedback/{feedback_id}")
def update_feedback(feedback_id: str, body: FeedbackUpdatePayload) -> dict[str, Any]:
    """Updates status, content, or category of a feedback sticky note."""
    items = _read_feedback()
    target = next((i for i in items if i["id"] == feedback_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Feedback note '{feedback_id}' not found")

    if body.feedback is not None:
        target["feedback"] = body.feedback.strip()
    if body.status is not None:
        target["status"] = body.status
    if body.category is not None:
        target["category"] = body.category
    if body.tags is not None:
        target["tags"] = body.tags

    target["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write_feedback(items)
    return target


@router.delete("/feedback/{feedback_id}")
def delete_feedback(feedback_id: str) -> dict[str, Any]:
    """Deletes a feedback sticky note."""
    items = _read_feedback()
    remaining = [i for i in items if i["id"] != feedback_id]
    if len(remaining) == len(items):
        raise HTTPException(status_code=404, detail=f"Feedback note '{feedback_id}' not found")
    _write_feedback(remaining)
    return {"ok": True, "deleted": feedback_id}


# --- 3. Session State Inspection ---
@router.get("/sessions/{project_id}")
def get_session(project_id: str) -> dict[str, Any]:
    """Retrieves the active Visual AI Editor session state for a project."""
    sessions = _read_sessions()
    session = sessions.get(project_id)
    if not session:
        # Default fresh session
        session = {
            "projectId": project_id,
            "currentStep": 1,
            "selectedFeedbackIds": [],
            "plan": None,
            "planApproved": False,
            "implementationAuthorized": False,
            "implementationStatus": "idle",
            "testResults": None,
            "finalUiStatus": "pending_review",
            "chatMessages": [
                {
                    "id": "msg-init",
                    "sender": "agent",
                    "agentId": "main_architecture_agent",
                    "agentName": "Main Architecture Agent",
                    "content": "Hello! I am your configured Architecture & UI Engineering Agent. You can select UI elements, attach sticky-note feedback, discuss changes with me, and review implementation plans. What would you like to refine today?",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            ],
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        sessions[project_id] = session
        _write_sessions(sessions)
    return session


# --- 4. Agent Communication (Chat with Configured LLM) ---
@router.post("/chat")
def chat_with_agent(body: ChatRequestPayload) -> dict[str, Any]:
    """Sends a chat message to the project's configured LLM coding agent."""
    sessions = _read_sessions()
    session = sessions.get(body.projectId) or {
        "projectId": body.projectId,
        "currentStep": 2,
        "selectedFeedbackIds": body.selectedFeedbackIds,
        "chatMessages": []
    }

    # Fetch context of selected feedback items
    all_feedback = _read_feedback()
    selected_fb = [f for f in all_feedback if f["id"] in body.selectedFeedbackIds]
    fb_context = "\n".join([
        f"- [{f.get('page')}] {f.get('elementName')} ({f.get('componentRef')} -> {f.get('sourceFile')}): \"{f.get('feedback')}\" (Status: {f.get('status')})"
        for f in selected_fb
    ]) or "No specific feedback items attached to this message."

    # Inspect active LLM settings
    llm_settings = llm_client.load_settings()
    provider = llm_settings.get("provider", "claude_cli")
    model = llm_settings.get("model", "")

    system_prompt = (
        "You are the Main Architecture & UI Engineering Agent in the LAXMAN-AUTONOMOUS video studio system. "
        "The project is built with React 18, Vite, TypeScript, and an Ant Design/Studio dark theme (#0A0F1D, #111827, #1890FF). "
        "The user is pair-programming with you via the Visual AI Editor. "
        "Be helpful, concrete, and technically precise. Point directly to components in UI/frontend/src/ "
        "and maintain documentation and design token integrity. "
        f"\n\nCURRENT VISUAL FEEDBACK CONTEXT:\n{fb_context}"
    )

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    user_msg = {
        "id": f"msg-user-{int(time.time() * 1000)}",
        "sender": "user",
        "content": body.message,
        "timestamp": now_iso,
        "attachedFeedbackIds": body.selectedFeedbackIds
    }

    # Record user message in session
    session.setdefault("chatMessages", []).append(user_msg)

    # Dispatch to configured LLM
    try:
        reply_text = llm_client.generate_text(
            user=body.message,
            system=system_prompt,
            timeout=120,
            provider=provider if provider != "auto" else None,
            model=model or None
        )
        agent_msg = {
            "id": f"msg-agent-{int(time.time() * 1000)}",
            "sender": "agent",
            "agentId": "main_architecture_agent",
            "agentName": "Main Architecture Agent",
            "content": reply_text.strip(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "provider": provider,
            "model": model,
            "status": "delivered"
        }
        session["chatMessages"].append(agent_msg)
        session["currentStep"] = max(session.get("currentStep", 1), 2)
        sessions[body.projectId] = session
        _write_sessions(sessions)

        return {
            "success": True,
            "reply": agent_msg["content"],
            "agent": "Main Architecture Agent",
            "provider": provider,
            "model": model,
            "message": agent_msg
        }

    except Exception as e:
        err_str = str(e)
        error_msg = {
            "id": f"msg-agent-{int(time.time() * 1000)}",
            "sender": "agent",
            "agentId": "main_architecture_agent",
            "agentName": "Main Architecture Agent",
            "content": f"⚠️ LLM Dispatch Error ({provider}): {err_str}\n\nPlease verify your LLM Provider and API Key under Settings/Diagnostics.",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "error",
            "errorDetails": err_str
        }
        session["chatMessages"].append(error_msg)
        sessions[body.projectId] = session
        _write_sessions(sessions)

        return {
            "success": False,
            "error": err_str,
            "provider": provider,
            "agent": "Main Architecture Agent",
            "message": error_msg
        }


# --- 5. Generate Implementation Plan (Step 3) ---
@router.post("/generate-plan")
def generate_implementation_plan(body: PlanGeneratePayload) -> dict[str, Any]:
    """Analyzes selected feedback and code to produce a structured 5-part implementation plan."""
    sessions = _read_sessions()
    session = sessions.get(body.projectId) or {"projectId": body.projectId}

    all_feedback = _read_feedback()
    selected_fb = [f for f in all_feedback if f["id"] in body.feedbackIds]
    if not selected_fb:
        # Fall back to all pending/in_review feedback
        selected_fb = [f for f in all_feedback if f.get("status") in ("pending", "in_review", "approved_for_plan")]

    if not selected_fb:
        raise HTTPException(status_code=400, detail="No feedback items selected to generate plan")

    llm_settings = llm_client.load_settings()
    provider = llm_settings.get("provider", "claude_cli")
    model = llm_settings.get("model", "")

    # Aggregate feedback summary
    fb_details = "\n".join([
        f"- ID: {f.get('id')} | Page: {f.get('page')} | Component: {f.get('componentRef')} | File: {f.get('sourceFile')}\n  Requested Change: \"{f.get('feedback')}\""
        for f in selected_fb
    ])

    system_prompt = (
        "You are the Main Architecture & UI Engineering Agent in the LAXMAN-AUTONOMOUS system. "
        "Your task is to analyze visual feedback and generate a technical implementation plan. "
        "You MUST return a JSON object with EXACTLY the following structure:\n"
        "{\n"
        '  "understanding": "Clear summary of the user\'s requested changes",\n'
        '  "proposedModifications": ["list of specific UI modifications to execute"],\n'
        '  "affectedComponents": [\n'
        '     {"name": "ComponentName", "sourceFile": "path/to/file.tsx", "description": "exact change rationale"}\n'
        "  ],\n"
        '  "risksAndDependencies": ["potential risks, layout shifts, or dependency notes"],\n'
        '  "validationAndTestingSteps": ["concrete test commands, e.g. npm run build, playwright"]\n'
        "}\n"
        "Return ONLY the JSON object, with no markdown code fence or prefix."
    )

    user_prompt = f"Generate a technical UI implementation plan for the following collected feedback:\n\n{fb_details}"

    plan_data = None
    try:
        reply = llm_client.generate_text(
            user=user_prompt,
            system=system_prompt,
            timeout=120,
            provider=provider if provider != "auto" else None,
            model=model or None
        )
        # Attempt to parse json from reply
        text = reply.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:].strip()
        plan_data = json.loads(text)
    except Exception:
        # Structured deterministic fallback if LLM is offline or returned unformatted output
        plan_data = {
            "understanding": f"Implementation plan synthesized from {len(selected_fb)} visual feedback item(s) across {', '.join(set(f.get('page', '') for f in selected_fb))}.",
            "proposedModifications": [
                f"{f.get('elementName')}: {f.get('feedback')}" for f in selected_fb
            ],
            "affectedComponents": [
                {
                    "name": f.get("componentRef") or "UIComponent",
                    "sourceFile": f.get("sourceFile") or "UI/frontend/src/App.tsx",
                    "description": f"Apply requested change: {f.get('feedback')[:80]}..."
                } for f in selected_fb
            ],
            "risksAndDependencies": [
                "Verify viewport responsiveness on smaller screen resolutions (1280x720, 1024x768).",
                "Ensure dark theme design tokens (--bg-card, --border-card, --accent-blue) remain consistent.",
                "Ensure Playwright E2E tests continue to pass."
            ],
            "validationAndTestingSteps": [
                "Run 'npm run build' in UI/frontend to verify TypeScript compile and Vite bundling.",
                "Execute Playwright E2E verification test suite.",
                "Inspect visual rendering against studio design guidelines."
            ]
        }

    plan_id = f"plan-{int(time.time() * 1000)}"
    full_plan = {
        "id": plan_id,
        "projectId": body.projectId,
        "feedbackIds": [f["id"] for f in selected_fb],
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generatedByAgent": "Main Architecture Agent",
        "llmProvider": provider,
        "llmModel": model,
        "understanding": plan_data.get("understanding", "Requested UI refinements analyzed."),
        "proposedModifications": plan_data.get("proposedModifications", []),
        "affectedComponents": plan_data.get("affectedComponents", []),
        "risksAndDependencies": plan_data.get("risksAndDependencies", []),
        "validationAndTestingSteps": plan_data.get("validationAndTestingSteps", []),
        "planApproved": False,
        "planApprovedAt": None,
        "planApprovedBy": None,
        "implementationAuthorized": False,
        "implementationAuthorizedAt": None
    }

    session["plan"] = full_plan
    session["currentStep"] = 3  # Step 3: Plan Generated
    session["selectedFeedbackIds"] = full_plan["feedbackIds"]
    sessions[body.projectId] = session
    _write_sessions(sessions)

    # Update feedback statuses to 'in_review'
    for f in selected_fb:
        f["status"] = "in_review"
    _write_feedback(all_feedback)

    return full_plan


# --- 6. Gate 1: Plan Approval ---
@router.post("/decide-plan")
def decide_plan(body: PlanDecisionPayload) -> dict[str, Any]:
    """Gate 1: Approves or rejects the proposed implementation plan.
    Code changes are strictly blocked until the plan is approved.
    """
    sessions = _read_sessions()
    session = sessions.get(body.projectId)
    if not session or not session.get("plan"):
        raise HTTPException(status_code=404, detail="No active plan found for this project")

    plan = session["plan"]
    if body.decision == "approved":
        plan["planApproved"] = True
        plan["planApprovedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        plan["planApprovedBy"] = "Laxman Producer"
        session["currentStep"] = 4  # Step 4: Plan Approved, ready for authorization
        
        # Update feedback statuses to 'approved_for_plan'
        all_feedback = _read_feedback()
        for f in all_feedback:
            if f["id"] in plan.get("feedbackIds", []):
                f["status"] = "approved_for_plan"
        _write_feedback(all_feedback)
    else:
        plan["planApproved"] = False
        plan["rejectionNotes"] = body.notes
        session["currentStep"] = 2  # Return to discussion

    sessions[body.projectId] = session
    _write_sessions(sessions)
    return {"ok": True, "decision": body.decision, "plan": plan}


# --- 7. Gate 2: Implementation Authorization ---
@router.post("/authorize-implementation")
def authorize_implementation(body: ImplementationAuthPayload) -> dict[str, Any]:
    """Gate 2: Authorizes code implementation. Strictly requires prior plan approval."""
    sessions = _read_sessions()
    session = sessions.get(body.projectId)
    if not session or not session.get("plan"):
        raise HTTPException(status_code=404, detail="No plan found to authorize")

    plan = session["plan"]
    if not plan.get("planApproved"):
        raise HTTPException(
            status_code=403, 
            detail="Cannot authorize implementation before the implementation plan is approved (Gate 1)."
        )

    plan["implementationAuthorized"] = True
    plan["implementationAuthorizedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    session["currentStep"] = 5  # Step 5: Implementation authorized, executing tests
    session["implementationStatus"] = "ready_to_execute"

    sessions[body.projectId] = session
    _write_sessions(sessions)
    return {"ok": True, "authorized": True, "plan": plan}


# --- 8. Step 5: Execute Implementation & Real Verification Tests ---
@router.post("/run-implementation-tests")
def run_implementation_tests(project_id: str = Query(default="sample-01")) -> dict[str, Any]:
    """Executes the implementation verification tests and returns actual test telemetry."""
    sessions = _read_sessions()
    session = sessions.get(project_id)
    if not session or not session.get("plan"):
        raise HTTPException(status_code=404, detail="No active session found")

    plan = session["plan"]
    if not plan.get("implementationAuthorized"):
        raise HTTPException(
            status_code=403,
            detail="Implementation authorization required before running implementation tests (Gate 2)."
        )

    start_t = time.time()
    frontend_dir = Path(__file__).resolve().parents[3] / "UI" / "frontend"

    # Run real npm run build to verify TypeScript & bundling
    try:
        proc = subprocess.run(
            ["npm.cmd", "run", "build"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True,
            timeout=45,
            shell=True
        )
        duration_ms = int((time.time() - start_t) * 1000)
        success = (proc.returncode == 0)
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    except Exception as e:
        duration_ms = int((time.time() - start_t) * 1000)
        success = False
        output = f"Test execution failed: {e}"

    test_result = {
        "passed": success,
        "suiteName": "UI Frontend TypeScript & Vite Bundle Acceptance",
        "durationMs": duration_ms,
        "returnCode": 0 if success else 1,
        "output": output.strip()[:1500],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    session["testResults"] = test_result
    session["implementationStatus"] = "completed" if success else "failed"
    session["currentStep"] = 6  # Step 6: Final UI Review
    session["finalUiStatus"] = "pending_review"

    # Mark feedback items as 'implemented'
    all_feedback = _read_feedback()
    for f in all_feedback:
        if f["id"] in plan.get("feedbackIds", []):
            f["status"] = "implemented"
    _write_feedback(all_feedback)

    sessions[project_id] = session
    _write_sessions(sessions)

    return {
        "ok": True,
        "implementationStatus": session["implementationStatus"],
        "testResults": test_result,
        "currentStep": 6
    }


# --- 9. Gate 3: Final UI Decision ---
@router.post("/decide-final-ui")
def decide_final_ui(body: FinalUiDecisionPayload) -> dict[str, Any]:
    """Gate 3: Separate Final UI Decision.
    - 'approved': Marks all feedback as resolved and completes the session.
    - 'changes_requested': Returns to feedback and discussion while preserving all history.
    """
    sessions = _read_sessions()
    session = sessions.get(body.projectId)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    plan = session.get("plan") or {}
    all_feedback = _read_feedback()

    if body.decision == "approved":
        session["finalUiStatus"] = "approved"
        session["finalUiDecidedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Resolve all linked feedback items
        for f in all_feedback:
            if f["id"] in plan.get("feedbackIds", []):
                f["status"] = "resolved"
        _write_feedback(all_feedback)

    elif body.decision == "changes_requested":
        session["finalUiStatus"] = "changes_requested"
        session["changeRequestReason"] = body.reason or "Further visual refinements requested."
        # Return to discussion step while preserving conversation, plan, and test results!
        session["currentStep"] = 2
        
        # Keep feedback as 'in_review'
        for f in all_feedback:
            if f["id"] in plan.get("feedbackIds", []):
                f["status"] = "in_review"
        _write_feedback(all_feedback)

    sessions[body.projectId] = session
    _write_sessions(sessions)

    return {
        "ok": True,
        "decision": body.decision,
        "finalUiStatus": session["finalUiStatus"],
        "currentStep": session["currentStep"]
    }
