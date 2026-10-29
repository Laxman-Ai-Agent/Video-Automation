"""What the Final QC LLM review LOOKS at (Phase 5, QC that sees): contact sheets of the frames Final QC already sampled from the rendered video, and measurements per scene.

No new frame is cut from the video: the sheets are drawn from `final_qc_frames/` (the files the media checks decoded) and the motion numbers from the timeline thumbnail sheet
(`timeline_media.thumbnails`, one picture per second, also used by the Timeline page). Two kinds of sheet, one row per scene / per cut, so a finding can name its scene:
  scenes: the scene's entry, middle and pre-exit frame      cuts: the frame before the cut, the middle of its transition and the frame after the cut
Cells are phone-width (about 320 px; the label sits in a 40 px strip above the frame, so no corner of the frame is hidden), so text that cannot be read in a cell cannot be read on a phone either. Cached by the video's hash and the sampled frames."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

from . import contact_grid, final_qc as fq, render_video as rv, timeline_media

VERSION = 2                                  # 2: the label sits in a strip above each frame (it covered the top-left corner); part of the qc review's fingerprint (llm_review._stage_logic_tag): a change of what the reviewer is shown makes its verdict stale
CELL_LONG, COLUMNS, SHEET_MAX_PX = 320, 3, 1500      # the long edge of a cell; a sheet taller than ~1500 px is shrunk by the model, which defeats the phone-size cells
CHANGE_MIN = 8.0                             # mean grey difference (0-255) between two pictures one second apart that counts as the picture changing (a new layout, not a fade-in of one element)
USAGE_EDGE, USAGE_BLOCK = 12, 0.015          # a pixel is "content" when its edge step exceeds USAGE_EDGE; a block of the 16x9 grid has content when more than USAGE_BLOCK of its pixels do
SCENE_KINDS = (("entry", "entry"), ("mid", "mid"), ("pre_exit", "exit"))


def _folder(pdir: Path, aspect: str) -> Path:
    return pdir / ("final_qc_sheets_9x16" if aspect == "9:16" else "final_qc_sheets")


def _tag(scene_id: str) -> str:
    return re.sub(r"^scene_0*", "s", scene_id)


def _rows(clips: list[dict], transitions: list[dict], samples: list[dict]) -> tuple[list[tuple[str, int | None]], list[tuple[str, int | None]]]:
    """(label, frame) cells of the scenes sheet and of the cuts sheet, three per row; a frame that was not sampled is None (the cell says so)."""
    by_frame = {s["frame"]: s for s in samples}
    scenes, cuts = [], []
    for c in clips:
        for kind, word in SCENE_KINDS:
            s = next((x for x in samples if x["scene_id"] == c["scene_id"] and x["kind"] == kind), None)
            scenes.append((f"{_tag(c['scene_id'])} {word} {s['time_s']:.1f}s" if s else f"{_tag(c['scene_id'])} {word}", s["frame"] if s else None))
    for c, nxt in zip(clips, clips[1:]):
        t = next((t for t in transitions if t["from_scene"] == c["scene_id"]), None)
        for word, frame in (("before", c["end_frame"] - 2), ("mid", (t["start_frame"] + t["end_frame"]) // 2 if t else None), ("after", c["end_frame"] + 1)):
            s = by_frame.get(frame) if frame is not None else None
            cuts.append((f"cut {_tag(c['scene_id'])}>{_tag(nxt['scene_id'])} {word} {s['time_s']:.1f}s" if s else f"cut {_tag(c['scene_id'])}>{_tag(nxt['scene_id'])} {word}", s["frame"] if s else None))
    return scenes, cuts


def _sheets(folder: Path, files: dict[int, Path], sha: str, name: str, cells: list[tuple[str, int | None]]) -> list[str]:
    pics = [Image.open(files[f]).convert("RGB") if f in files else None for _, f in cells]
    first = next((p for p in pics if p), None)
    w, h = first.size if first else (16, 9)
    cell = (CELL_LONG, round(CELL_LONG * h / w)) if w >= h else (round(CELL_LONG * w / h), CELL_LONG)
    cell = (cell[0], cell[1] + contact_grid.STRIP)                                           # the label has its own strip above the picture: it never covers a corner of the frame
    per_sheet = max(1, SHEET_MAX_PX // cell[1]) * COLUMNS
    out = []
    for n, i in enumerate(range(0, len(cells), per_sheet), 1):
        file = f"{sha[:12]}_{name}_{n}.jpg"
        contact_grid.grid(pics[i:i + per_sheet], [lab for lab, _ in cells[i:i + per_sheet]], cell, COLUMNS, empty="no frame", strip=True).save(folder / file, "JPEG", quality=82)
        out.append(file)
    return out


def _usage(path: Path) -> float:
    """% of the frame (16x9 grid of blocks) that holds drawn content: a small card in a big empty background scores low."""
    g = np.asarray(Image.open(path).convert("L"), dtype="float32")
    edge = np.maximum(np.abs(np.diff(g, axis=1))[:-1, :], np.abs(np.diff(g, axis=0))[:, :-1]) > USAGE_EDGE
    bx, by = (16, 9) if g.shape[1] >= g.shape[0] else (9, 16)
    h, w = edge.shape[0] // by, edge.shape[1] // bx
    return round(float((edge[:by * h, :bx * w].reshape(by, h, bx, w).mean(axis=(1, 3)) > USAGE_BLOCK).mean() * 100), 1)


def _seconds(pdir: Path, cand: dict) -> tuple[list[np.ndarray], int] | None:
    """A small grey picture per sampled second of the video, cut out of the timeline thumbnail sheet; None when ffmpeg could not make it."""
    meta = timeline_media.thumbnails(pdir, cand["path"], cand["sha256"], float((cand["report"].get("observed") or {}).get("duration_seconds") or 0))
    if not meta:
        return None
    with Image.open(pdir / timeline_media.THUMBS) as sheet:
        sheet = sheet.convert("L")
        tw, th = meta["tile_w"], meta["tile_h"]
        return [np.asarray(sheet.crop((i % meta["cols"] * tw, i // meta["cols"] * th, (i % meta["cols"] + 1) * tw, (i // meta["cols"] + 1) * th)).resize((32, 18)), dtype="float32")
                for i in range(meta["count"])], meta["interval_s"]


def _metrics(pdir: Path, cand: dict, clips: list[dict], fps: int, samples: list[dict], folder: Path) -> dict:
    secs = _seconds(pdir, cand)
    rows = []
    for c in clips:
        a, b = c["start_frame"] / fps, c["end_frame"] / fps
        used = [_usage(folder / s["file"]) for s in samples if s["scene_id"] == c["scene_id"] and s["kind"] in ("entry", "mid", "pre_exit") and s["decode_ok"]]
        row = {"scene_id": c["scene_id"], "seconds": round(b - a, 1), "frame_usage_pct": round(sum(used) / len(used), 1) if used else None, "motion_energy": None, "big_changes_per_10s": None}
        if secs:
            tiles, step = secs
            inside = [tiles[i] for i in range(len(tiles)) if a <= i * step < b]
            diffs = [float(np.abs(x - y).mean()) for x, y in zip(inside, inside[1:])]
            if diffs:
                row["motion_energy"] = round(sum(diffs) / len(diffs), 1)
                row["big_changes_per_10s"] = round(sum(d >= CHANGE_MIN for d in diffs) / (len(diffs) * step) * 10, 1)
        rows.append(row)
    return {"how": ("frame_usage_pct = % of a 16x9 grid of the frame that holds drawn content (entry, middle and pre-exit frames); motion_energy = mean grey difference (0-255) between pictures one second apart "
                    f"inside the scene; big_changes_per_10s = how often that difference reaches {CHANGE_MIN:g} (the picture really changes, not one more element appearing)"), "scenes": rows}


def build(pdir: Path, aspect: str) -> dict:
    """{"sheets": [Path], "metrics": {...}} for the current candidate and its Final QC report; no sheets and no metrics when there is no report or no sampled frame."""
    cand, rep = rv.candidate(pdir, aspect), fq._rw_read(pdir, "report", aspect)
    samples = [s for s in ((rep or {}).get("evidence", {}).get("frame_quality", {}).get("data", {}).get("samples") or []) if s.get("file")]
    if not cand or not samples or rep["candidate"]["sha256"] != cand["sha256"]:
        return {"sheets": [], "metrics": None}
    key = fq.sha(fq.canon([VERSION, cand["sha256"], [(s["frame"], s["file"]) for s in samples]]))
    folder, memo = _folder(pdir, aspect), _folder(pdir, aspect) / "sight.json"
    try:
        old = json.loads(memo.read_text(encoding="utf-8"))
        if old["key"] == key and all((folder / n).is_file() for n in old["sheets"]):
            return {"sheets": [folder / n for n in old["sheets"]], "metrics": old["metrics"]}
    except (OSError, ValueError, KeyError):
        pass
    folder.mkdir(exist_ok=True)
    clips, transitions, fps = fq.scenes_of(pdir, aspect)
    frames = pdir / fq.names(aspect)["frames"]
    files = {s["frame"]: frames / s["file"] for s in samples if (frames / s["file"]).is_file()}
    scenes, cuts = _rows(clips, transitions, samples)
    sheets = _sheets(folder, files, cand["sha256"], "scenes", scenes) + _sheets(folder, files, cand["sha256"], "cuts", cuts)
    metrics = _metrics(pdir, cand, clips, fps, samples, frames)
    for f in folder.glob("*.jpg"):
        if f.name not in sheets:
            f.unlink(missing_ok=True)
    memo.write_text(json.dumps({"key": key, "sheets": sheets, "metrics": metrics}, ensure_ascii=False), encoding="utf-8")
    return {"sheets": [folder / n for n in sheets], "metrics": metrics}
