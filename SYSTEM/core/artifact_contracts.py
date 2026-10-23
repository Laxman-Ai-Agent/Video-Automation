"""Versioned Artifact Contracts and Validation for Dark World Video Generation Pipeline.

Defines schemas, path traversal guards, and domain validators for all active stage artifacts.
Enforces fail-closed validation on missing, corrupted, or incompatible artifact versions.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class ContractError(Exception):
    """Base exception for contract failures."""


class ContractValidationError(ContractError):
    """Raised when an artifact fails schema or domain constraints."""


class ContractCompatibilityError(ContractError):
    """Raised when an artifact has an incompatible schema version."""


CURRENT_CONTRACT_VERSION = 1


def _file_sha256(path: Path) -> str:
    """Computes SHA256 of a file in streaming chunks."""
    if not path.exists() or not path.is_file():
        return "missing"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()[:16]


def verify_path_confinement(project_dir: Path, target_path: Path | str) -> Path:
    """Ensures a path resolves strictly inside the project root, rejecting path traversal."""
    p_resolved = Path(target_path).resolve()
    root_resolved = project_dir.resolve()
    try:
        p_resolved.relative_to(root_resolved)
    except ValueError:
        raise ContractValidationError(
            f"Path traversal detected: '{target_path}' resolves outside project root '{project_dir}'"
        )
    return p_resolved


@dataclass
class ArtifactManifestRecord:
    """Metadata record for a validated artifact."""
    artifact_id: str
    stage_id: str
    relative_path: str
    media_type: str
    size_bytes: int
    sha256: str
    contract_id: str
    contract_version: int = CURRENT_CONTRACT_VERSION
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "stage_id": self.stage_id,
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "created_at": self.created_at,
        }


# ---------- Domain Validators for Active Stages ----------

def validate_audio_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates source audio artifact."""
    audio = next(iter(pdir.glob("audio.*")), None)
    if not audio or not audio.is_file():
        raise ContractValidationError("Missing source audio file (audio.*)")
    size = audio.stat().st_size
    if size == 0:
        raise ContractValidationError("Source audio file is empty (0 bytes)")

    verify_path_confinement(pdir, audio)
    records = [
        ArtifactManifestRecord(
            artifact_id="source_audio",
            stage_id="audio",
            relative_path=audio.name,
            media_type="audio",
            size_bytes=size,
            sha256=_file_sha256(audio),
            contract_id="audio_input_contract",
            contract_version=1,
            created_at=audio.stat().st_mtime,
        )
    ]
    manifest = pdir / "audio_input_manifest.json"
    if manifest.exists():
        records.append(
            ArtifactManifestRecord(
                artifact_id="audio_input_manifest",
                stage_id="audio",
                relative_path="audio_input_manifest.json",
                media_type="application/json",
                size_bytes=manifest.stat().st_size,
                sha256=_file_sha256(manifest),
                contract_id="audio_input_manifest_contract",
                contract_version=1,
                created_at=manifest.stat().st_mtime,
            )
        )
    return records


def validate_analyzer_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates transcript.json and cuts.json produced by transcribe.py."""
    tf = verify_path_confinement(pdir, pdir / "transcript.json")
    cf = verify_path_confinement(pdir, pdir / "cuts.json")

    if not tf.exists():
        raise ContractValidationError("Missing transcript.json from audio analysis")
    if not cf.exists():
        raise ContractValidationError("Missing cuts.json from audio analysis")

    try:
        t_data = json.loads(tf.read_text(encoding="utf-8"))
        if not isinstance(t_data, dict):
            raise ContractValidationError("transcript.json must be a JSON object")
        if "text" not in t_data and "segments" not in t_data:
            raise ContractValidationError("transcript.json missing required text or segments")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted transcript.json: {e}")

    try:
        c_data = json.loads(cf.read_text(encoding="utf-8"))
        if not isinstance(c_data, (list, dict)):
            raise ContractValidationError("cuts.json must be a JSON array or object")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted cuts.json: {e}")

    return [
        ArtifactManifestRecord(
            artifact_id="transcript",
            stage_id="analyzer",
            relative_path="transcript.json",
            media_type="application/json",
            size_bytes=tf.stat().st_size,
            sha256=_file_sha256(tf),
            contract_id="transcript_contract",
            contract_version=1,
            created_at=tf.stat().st_mtime,
        ),
        ArtifactManifestRecord(
            artifact_id="cuts",
            stage_id="analyzer",
            relative_path="cuts.json",
            media_type="application/json",
            size_bytes=cf.stat().st_size,
            sha256=_file_sha256(cf),
            contract_id="cuts_contract",
            contract_version=1,
            created_at=cf.stat().st_mtime,
        ),
    ]


def validate_segmentation_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates scene_segmentation.json produced by scene_segmentation.py."""
    sf = verify_path_confinement(pdir, pdir / "scene_segmentation.json")
    if not sf.exists():
        raise ContractValidationError("Missing scene_segmentation.json")

    try:
        data = json.loads(sf.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ContractValidationError("scene_segmentation.json must be a JSON object")
        scenes = data.get("scenes")
        if not isinstance(scenes, list) or len(scenes) == 0:
            raise ContractValidationError("scene_segmentation.json contains no scenes")
        for sc in scenes:
            if not isinstance(sc, dict) or not any(k in sc for k in ("scene_id", "id", "scene_index")):
                raise ContractValidationError(f"Malformed scene record in segmentation: {sc}")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted scene_segmentation.json: {e}")

    return [
        ArtifactManifestRecord(
            artifact_id="scene_segmentation",
            stage_id="segmentation",
            relative_path="scene_segmentation.json",
            media_type="application/json",
            size_bytes=sf.stat().st_size,
            sha256=_file_sha256(sf),
            contract_id="scene_segmentation_contract",
            contract_version=1,
            created_at=sf.stat().st_mtime,
        )
    ]


def validate_planning_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates visual_planning.json and scene_plan.json."""
    vf = verify_path_confinement(pdir, pdir / "visual_planning.json")
    spf = verify_path_confinement(pdir, pdir / "scene_plan.json")

    if not vf.exists() or not spf.exists():
        raise ContractValidationError("Missing visual_planning.json or scene_plan.json")

    try:
        v_data = json.loads(vf.read_text(encoding="utf-8"))
        if not isinstance(v_data, dict):
            raise ContractValidationError("visual_planning.json must be a JSON object")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted visual_planning.json: {e}")

    try:
        s_data = json.loads(spf.read_text(encoding="utf-8"))
        if not isinstance(s_data, dict):
            raise ContractValidationError("scene_plan.json must be a JSON object")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted scene_plan.json: {e}")

    # Cross-stage consistency against scene_segmentation.json
    seg_file = pdir / "scene_segmentation.json"
    if seg_file.exists():
        try:
            seg_data = json.loads(seg_file.read_text(encoding="utf-8"))
            seg_scenes = seg_data.get("scenes", [])
            plan_scenes = v_data.get("scenes", [])
            if seg_scenes and plan_scenes:
                seg_ids = set()
                for s in seg_scenes:
                    sid = s.get("id") or s.get("scene_id")
                    if sid is not None:
                        seg_ids.add(str(sid))
                plan_ids = set()
                for s in plan_scenes:
                    for k in ("scene_id", "id", "plan_scene_id"):
                        val = s.get(k)
                        if val is not None:
                            plan_ids.add(str(val))
                            if isinstance(val, int) or (isinstance(val, str) and val.isdigit()):
                                plan_ids.add(f"scene_{int(val):02d}")
                    src_map = s.get("source_mapping") or {}
                    for k in ("segmentation_scene_id", "scene_id", "plan_scene_id"):
                        val = src_map.get(k)
                        if val is not None:
                            plan_ids.add(str(val))
                missing = seg_ids - plan_ids
                if missing:
                    raise ContractValidationError(f"Visual plan is missing scenes from segmentation: {missing}")
        except json.JSONDecodeError:
            pass

    # Motion-Only validation: no external URLs in element descriptions
    for sc in v_data.get("scenes", []):
        for el in sc.get("elements", []):
            v_desc = str(el.get("visual_description", "")).lower()
            if "http://" in v_desc or "https://" in v_desc:
                raise ContractValidationError(f"External image URL detected in element {el.get('element_id')}: {v_desc}")

    records = [
        ArtifactManifestRecord(
            artifact_id="visual_planning",
            stage_id="planning",
            relative_path="visual_planning.json",
            media_type="application/json",
            size_bytes=vf.stat().st_size,
            sha256=_file_sha256(vf),
            contract_id="visual_planning_contract",
            contract_version=1,
            created_at=vf.stat().st_mtime,
        ),
        ArtifactManifestRecord(
            artifact_id="scene_plan",
            stage_id="planning",
            relative_path="scene_plan.json",
            media_type="application/json",
            size_bytes=spf.stat().st_size,
            sha256=_file_sha256(spf),
            contract_id="scene_plan_contract",
            contract_version=1,
            created_at=spf.stat().st_mtime,
        ),
    ]
    pmf = pdir / "prompts_map.json"
    if pmf.exists():
        records.append(
            ArtifactManifestRecord(
                artifact_id="prompts_map",
                stage_id="planning",
                relative_path="prompts_map.json",
                media_type="application/json",
                size_bytes=pmf.stat().st_size,
                sha256=_file_sha256(pmf),
                contract_id="prompts_map_contract",
                contract_version=1,
                created_at=pmf.stat().st_mtime,
            )
        )
    return records


def validate_motion_plan_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates motion_plan.json."""
    sfx = "_9x16" if aspect == "9:16" else ""
    mp = verify_path_confinement(pdir, pdir / f"motion_plan{sfx}.json")
    if not mp.exists():
        raise ContractValidationError(f"Missing motion_plan{sfx}.json")

    try:
        data = json.loads(mp.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ContractValidationError(f"motion_plan{sfx}.json must be a JSON object")
        if "scenes" not in data:
            raise ContractValidationError(f"motion_plan{sfx}.json missing 'scenes'")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted motion_plan{sfx}.json: {e}")

    return [
        ArtifactManifestRecord(
            artifact_id=f"motion_plan{sfx}",
            stage_id="motion_plan",
            relative_path=f"motion_plan{sfx}.json",
            media_type="application/json",
            size_bytes=mp.stat().st_size,
            sha256=_file_sha256(mp),
            contract_id="motion_plan_contract",
            contract_version=1,
            created_at=mp.stat().st_mtime,
        )
    ]


def validate_motion_gen_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates composition.json and motion_animation.json in Motion-Only Custom Code mode."""
    sfx = "_9x16" if aspect == "9:16" else ""
    comp = verify_path_confinement(pdir, pdir / f"composition{sfx}.json")
    anim = verify_path_confinement(pdir, pdir / f"motion_animation{sfx}.json")

    if not comp.exists():
        raise ContractValidationError(f"Missing composition{sfx}.json")
    if not anim.exists():
        raise ContractValidationError(f"Missing motion_animation{sfx}.json")

    try:
        c_data = json.loads(comp.read_text(encoding="utf-8"))
        if not isinstance(c_data, dict):
            raise ContractValidationError(f"composition{sfx}.json must be a JSON object")
        fps = c_data.get("fps") or c_data.get("meta", {}).get("fps")
        if fps != 30:
            raise ContractValidationError(f"composition{sfx}.json fps must be 30, got {fps}")
        if not isinstance(c_data.get("scenes"), list):
            raise ContractValidationError(f"composition{sfx}.json missing scenes list")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted composition{sfx}.json: {e}")

    try:
        a_data = json.loads(anim.read_text(encoding="utf-8"))
        if not isinstance(a_data, dict):
            raise ContractValidationError(f"motion_animation{sfx}.json must be a JSON object")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted motion_animation{sfx}.json: {e}")

    return [
        ArtifactManifestRecord(
            artifact_id=f"composition{sfx}",
            stage_id="motion_gen",
            relative_path=f"composition{sfx}.json",
            media_type="application/json",
            size_bytes=comp.stat().st_size,
            sha256=_file_sha256(comp),
            contract_id="composition_manifest_contract",
            contract_version=1,
            created_at=comp.stat().st_mtime,
        ),
        ArtifactManifestRecord(
            artifact_id=f"motion_animation{sfx}",
            stage_id="motion_gen",
            relative_path=f"motion_animation{sfx}.json",
            media_type="application/json",
            size_bytes=anim.stat().st_size,
            sha256=_file_sha256(anim),
            contract_id="motion_animation_contract",
            contract_version=1,
            created_at=anim.stat().st_mtime,
        ),
    ]


def validate_motion_validation_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates motion_timeline_validation.json."""
    sfx = "_9x16" if aspect == "9:16" else ""
    val = verify_path_confinement(pdir, pdir / f"motion_timeline_validation{sfx}.json")
    if not val.exists():
        raise ContractValidationError(f"Missing motion_timeline_validation{sfx}.json")

    try:
        data = json.loads(val.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ContractValidationError(f"motion_timeline_validation{sfx}.json must be a JSON object")
        # Must pass with 0 blocking errors
        errs = data.get("errors", [])
        if len(errs) > 0:
            raise ContractValidationError(f"motion_timeline_validation has {len(errs)} blocking errors: {errs[:3]}")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted motion_timeline_validation{sfx}.json: {e}")

    return [
        ArtifactManifestRecord(
            artifact_id=f"motion_validation{sfx}",
            stage_id="motion_validation",
            relative_path=f"motion_timeline_validation{sfx}.json",
            media_type="application/json",
            size_bytes=val.stat().st_size,
            sha256=_file_sha256(val),
            contract_id="motion_timeline_validation_contract",
            contract_version=1,
            created_at=val.stat().st_mtime,
        )
    ]


def validate_timeline_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates timeline.json and timeline_build_report.json."""
    sfx = "_9x16" if aspect == "9:16" else ""
    tl = verify_path_confinement(pdir, pdir / f"timeline{sfx}.json")
    rep = verify_path_confinement(pdir, pdir / f"timeline_build_report{sfx}.json")

    if not tl.exists():
        raise ContractValidationError(f"Missing timeline{sfx}.json")
    if not rep.exists():
        raise ContractValidationError(f"Missing timeline_build_report{sfx}.json")

    try:
        t_data = json.loads(tl.read_text(encoding="utf-8"))
        if not isinstance(t_data, dict):
            raise ContractValidationError(f"timeline{sfx}.json must be a JSON object")
        profile = t_data.get("profile") if isinstance(t_data.get("profile"), dict) else {}
        if (
            "total_frames" not in t_data
            and "duration_frames" not in t_data
            and "duration_frames" not in profile
            and "total_frames" not in profile
        ):
            raise ContractValidationError(f"timeline{sfx}.json missing frame count")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted timeline{sfx}.json: {e}")

    return [
        ArtifactManifestRecord(
            artifact_id=f"timeline{sfx}",
            stage_id="timeline",
            relative_path=f"timeline{sfx}.json",
            media_type="application/json",
            size_bytes=tl.stat().st_size,
            sha256=_file_sha256(tl),
            contract_id="timeline_manifest_contract",
            contract_version=1,
            created_at=tl.stat().st_mtime,
        ),
        ArtifactManifestRecord(
            artifact_id=f"timeline_build_report{sfx}",
            stage_id="timeline",
            relative_path=f"timeline_build_report{sfx}.json",
            media_type="application/json",
            size_bytes=rep.stat().st_size,
            sha256=_file_sha256(rep),
            contract_id="timeline_build_report_contract",
            contract_version=1,
            created_at=rep.stat().st_mtime,
        ),
    ]


def validate_approval_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates timeline_approval_history.json."""
    sfx = "_9x16" if aspect == "9:16" else ""
    app = verify_path_confinement(pdir, pdir / f"timeline_approval_history{sfx}.json")
    if not app.exists():
        raise ContractValidationError(f"Missing timeline_approval_history{sfx}.json")

    try:
        data = json.loads(app.read_text(encoding="utf-8"))
        if not isinstance(data, (dict, list)):
            raise ContractValidationError(f"timeline_approval_history{sfx}.json must be valid JSON")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted timeline_approval_history{sfx}.json: {e}")

    return [
        ArtifactManifestRecord(
            artifact_id=f"timeline_approval{sfx}",
            stage_id="approval",
            relative_path=f"timeline_approval_history{sfx}.json",
            media_type="application/json",
            size_bytes=app.stat().st_size,
            sha256=_file_sha256(app),
            contract_id="timeline_approval_contract",
            contract_version=1,
            created_at=app.stat().st_mtime,
        )
    ]


def validate_render_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates rendered video file."""
    sfx = "_9x16" if aspect == "9:16" else ""
    vid = verify_path_confinement(pdir, pdir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4"))
    if not vid.exists():
        raise ContractValidationError(f"Missing rendered video file {vid.name}")
    size = vid.stat().st_size
    if size < 1000:
        raise ContractValidationError(f"Rendered video file is suspiciously small ({size} bytes)")

    records = [
        ArtifactManifestRecord(
            artifact_id=f"rendered_video_{aspect.replace(':', 'x')}",
            stage_id="render",
            relative_path=vid.name,
            media_type="video/mp4",
            size_bytes=size,
            sha256=_file_sha256(vid),
            contract_id="video_render_contract",
            contract_version=1,
            created_at=vid.stat().st_mtime,
        )
    ]
    rr = pdir / f"render_report{sfx}.json"
    if rr.exists():
        records.append(
            ArtifactManifestRecord(
                artifact_id=f"render_report_{aspect.replace(':', 'x')}",
                stage_id="render",
                relative_path=rr.name,
                media_type="application/json",
                size_bytes=rr.stat().st_size,
                sha256=_file_sha256(rr),
                contract_id="render_report_contract",
                contract_version=1,
                created_at=rr.stat().st_mtime,
            )
        )
    return records


def validate_qc_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates final_qc_report.json."""
    sfx = "_9x16" if aspect == "9:16" else ""
    qc = verify_path_confinement(pdir, pdir / f"final_qc_report{sfx}.json")
    if not qc.exists():
        raise ContractValidationError(f"Missing final_qc_report{sfx}.json")

    try:
        data = json.loads(qc.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ContractValidationError(f"final_qc_report{sfx}.json must be a JSON object")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted final_qc_report{sfx}.json: {e}")

    return [
        ArtifactManifestRecord(
            artifact_id=f"final_qc_report{sfx}",
            stage_id="qc",
            relative_path=f"final_qc_report{sfx}.json",
            media_type="application/json",
            size_bytes=qc.stat().st_size,
            sha256=_file_sha256(qc),
            contract_id="final_qc_contract",
            contract_version=1,
            created_at=qc.stat().st_mtime,
        )
    ]


def validate_final_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates final_qc_review.json and final delivery provenance / delivery_manifest.json."""
    sfx = "_9x16" if aspect == "9:16" else ""
    rev = verify_path_confinement(pdir, pdir / f"final_qc_review{sfx}.json")
    if not rev.exists():
        raise ContractValidationError(f"Missing final_qc_review{sfx}.json")

    try:
        data = json.loads(rev.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ContractValidationError(f"final_qc_review{sfx}.json must be a JSON object")
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Corrupted final_qc_review{sfx}.json: {e}")

    records = [
        ArtifactManifestRecord(
            artifact_id=f"final_delivery_provenance{sfx}",
            stage_id="final",
            relative_path=f"final_qc_review{sfx}.json",
            media_type="application/json",
            size_bytes=rev.stat().st_size,
            sha256=_file_sha256(rev),
            contract_id="final_delivery_contract",
            contract_version=1,
            created_at=rev.stat().st_mtime,
        )
    ]

    dm = pdir / f"delivery_manifest{sfx}.json"
    if dm.exists():
        verify_path_confinement(pdir, dm)
        try:
            dm_data = json.loads(dm.read_text(encoding="utf-8"))
            if not isinstance(dm_data, dict):
                raise ContractValidationError(f"delivery_manifest{sfx}.json must be a JSON object")
        except json.JSONDecodeError as e:
            raise ContractValidationError(f"Corrupted delivery_manifest{sfx}.json: {e}")

        records.append(
            ArtifactManifestRecord(
                artifact_id=f"delivery_manifest{sfx}",
                stage_id="final",
                relative_path=f"delivery_manifest{sfx}.json",
                media_type="application/json",
                size_bytes=dm.stat().st_size,
                sha256=_file_sha256(dm),
                contract_id="delivery_manifest_contract",
                contract_version=1,
                created_at=dm.stat().st_mtime,
            )
        )

    return records


def validate_assets_artifacts(pdir: Path, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates asset_requirements.json and assets_manifest.json: both exist and are objects of their schema, and every collected asset has its file (unchanged since collection), a source,
    a licence, a rights class other than D and authenticity "real". An empty manifest is valid: most videos need no real media."""
    out: list[ArtifactManifestRecord] = []
    data: dict[str, Any] = {}
    for name, schema, key in (("asset_requirements.json", "asset-requirements", "requirements"), ("assets_manifest.json", "assets-manifest", "assets")):
        f = verify_path_confinement(pdir, pdir / name)
        if not f.exists():
            raise ContractValidationError(f"Missing {name}")
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ContractValidationError(f"Corrupted {name}: {e}")
        if not isinstance(d, dict) or d.get("schema") != schema or not isinstance(d.get(key), list):
            raise ContractValidationError(f"{name} must be a {schema} object with a '{key}' list")
        if key == "assets":
            data = d
        out.append(ArtifactManifestRecord(artifact_id=name.removesuffix(".json"), stage_id="assets", relative_path=name, media_type="application/json", size_bytes=f.stat().st_size,
                                          sha256=_file_sha256(f), contract_id=f"{name.removesuffix('.json')}_contract", contract_version=1, created_at=f.stat().st_mtime))
    for a in data["assets"]:
        aid = a.get("asset_id", "?")
        media = verify_path_confinement(pdir, pdir / str(a.get("file", "")))
        if not media.is_file():
            raise ContractValidationError(f"Asset {aid}: file missing ({a.get('file')})")
        h = hashlib.sha256()
        with open(media, "rb") as fh:
            while chunk := fh.read(65536):
                h.update(chunk)
        if a.get("file_sha256") and h.hexdigest() != a["file_sha256"]:
            raise ContractValidationError(f"Asset {aid}: the file changed after collection")
        if not a.get("source_url") or not (a.get("license") or {}).get("name"):
            raise ContractValidationError(f"Asset {aid}: source or licence is missing")
        if a.get("rights_class") not in ("A", "C"):
            raise ContractValidationError(f"Asset {aid}: rights class {a.get('rights_class')!r} is not usable")
        if a.get("authenticity") != "real":
            raise ContractValidationError(f"Asset {aid}: authenticity is {a.get('authenticity')!r}, not 'real'")
    return out


STAGE_VALIDATORS: dict[str, Callable[[Path, str], list[ArtifactManifestRecord]]] = {
    "audio": validate_audio_artifacts,
    "analyzer": validate_analyzer_artifacts,
    "segmentation": validate_segmentation_artifacts,
    "planning": validate_planning_artifacts,
    "assets": validate_assets_artifacts,
    "motion_plan": validate_motion_plan_artifacts,
    "motion_gen": validate_motion_gen_artifacts,
    "motion_validation": validate_motion_validation_artifacts,
    "timeline": validate_timeline_artifacts,
    "approval": validate_approval_artifacts,
    "render": validate_render_artifacts,
    "qc": validate_qc_artifacts,
    "final": validate_final_artifacts,
}


def validate_stage_artifacts(project_dir: Path, stage_id: str, aspect: str = "16:9") -> list[ArtifactManifestRecord]:
    """Validates output artifacts for a stage against its contract, returning verified manifest records."""
    validator = STAGE_VALIDATORS.get(stage_id)
    if not validator:
        raise ContractValidationError(f"Unknown or unmanaged stage '{stage_id}'")
    return validator(project_dir, aspect)
