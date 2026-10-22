"""Visual Planning endpoints (an extension of the API; the original M7 endpoints are unchanged): read visual_plan.json, save the edited fields of one scene,
regenerate one scene, approve or reopen one scene. Every answer carries the real JSON of the scene(s), never a separate representation."""
from fastapi import APIRouter

from .. import store, visual_plan
from ..api_models import SceneApproval, SceneRegenerate, SceneSave, VisualPlanState, VisualSceneState
from ..errors import ApiError

router = APIRouter(prefix="/projects/{pid}/visual-plan", tags=["visual-plan"])


def _run(fn, *args):
    try:
        return fn(*args)
    except visual_plan.PlanError as e:
        raise ApiError(e.status, e.code, e.message, e.hint) from e


def _scene(pid: str, fn, *args) -> VisualSceneState:
    pdir = store.project_dir(pid)
    scene = _run(fn, pdir, pid, *args)
    plan = _run(visual_plan.ensure, pdir, pid)
    return VisualSceneState(scene=scene, all_approved=visual_plan.all_approved(plan), issues=visual_plan.scene_issues(scene, visual_plan.analysis_issues(pdir)))


@router.get("", response_model=VisualPlanState)
def get_visual_plan(pid: str):
    pdir = store.project_dir(pid)
    plan = _run(visual_plan.ensure, pdir, pid)
    return VisualPlanState(plan=plan, all_approved=visual_plan.all_approved(plan), issues=visual_plan.plan_issues(pdir, plan))


@router.put("/scenes/{sid}", response_model=VisualSceneState)
def save_scene(pid: str, sid: str, body: SceneSave):
    return _scene(pid, visual_plan.save_scene, sid, body.revision, [c.model_dump() for c in body.changes])


@router.post("/scenes/{sid}/regenerate", response_model=VisualSceneState)
def regenerate_scene(pid: str, sid: str, body: SceneRegenerate):
    return _scene(pid, visual_plan.regenerate_scene, sid, body.confirm_overwrite)


@router.post("/scenes/{sid}/approval", response_model=VisualSceneState)
def scene_approval(pid: str, sid: str, body: SceneApproval):
    return _scene(pid, visual_plan.set_approval, sid, body.action)
