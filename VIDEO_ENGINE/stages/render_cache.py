"""Scene-by-scene render cache (docs/ROADMAP.md Phase 7). render.py renders the video as one muted chunk per scene (`--frames`), and joins the chunks.

A chunk is the frames of ONE scene's window in the timeline (the scenes are laid out like SceneRoot.tsx lays them out: the sum of their lengths, each scene's outgoing
transition overlaps the start of the next window). Its pixels depend on that scene and, in the first frames, on the PREVIOUS scene's tail: so a chunk is keyed by
both, by everything global (composition meta, the Remotion source, the public files, the collected assets, the render mode) and by its frame range. One rewritten
scene therefore costs two chunks (its own and the next one), not the whole video. Frames are a pure function of the frame number (FilmLook is seeded), so a chunk
is identical in a cache hit and in a full render. The audio is not part of a chunk: it is muxed once, after the join."""
import subprocess
from pathlib import Path

from . import config
from . import motion_validation as mv
from .motion_planning import fr


def windows(comp: dict) -> list[dict]:
    """[{"scene", "prev", "from", "to", "out_frames"}] in the frame positions Remotion gives the scenes (`to` is exclusive; the last window runs to the end of the video)."""
    meta, scenes = comp["meta"], comp["scenes"]
    fps, total = meta["fps"], fr(meta["duration"], meta["fps"])
    rows, pos = [], 0
    for i, s in enumerate(scenes):
        base = fr(s["end"], fps) - fr(s["start"], fps)
        t = s.get("transition_out") if i < len(scenes) - 1 else None
        rows.append({"scene": s, "from": pos, "out_frames": min(fr(t["dur"], fps), base - 1) if t else 0})
        pos += base
    rows = [r for r in rows if r["from"] < total]
    if not rows:
        raise ValueError("the composition has no scene inside its duration")
    for r, nxt in zip(rows, rows[1:] + [{"from": total}]):
        r["to"] = nxt["from"]
    for prev, r in zip([None] + rows, rows[:]):
        r["prev"] = prev                                           # the scene whose tail is blended into the first frames of this window
    return rows


def _scene_material(pdir: Path, scene: dict, public: Path) -> dict:
    """What a scene draws that is NOT in its JSON: its generated code, and the files its layers name."""
    code, files = {}, {}
    for layer in scene.get("layers", []):
        if layer.get("type") == "custom_scene":
            sid = layer.get("scene_id", layer.get("id"))
            code[str(sid)] = mv._file_sha(pdir / "generated_motion" / f"scene_{sid}.tsx")
        if layer.get("file"):
            files[layer["file"]] = mv._file_sha(public / layer["file"])
    return {"scene": scene, "code": code, "files": files}


def global_part(pdir: Path, comp: dict, preview: bool, flags: list[str]) -> str:
    """Everything that changes the pixels of every scene: the composition's own settings, the Remotion code (not the generated scenes: those are per scene), the files
    in public/ (fonts, maps, ...; the staged audio is not part of a muted chunk), the collected assets and the render mode."""
    root, meta = config.REMOTION_DIR, comp["meta"]
    src = {p.relative_to(root).as_posix(): mv._file_sha(p) for p in sorted((root / "src").rglob("*"))
           if p.is_file() and not (p.parent.name == "generated" and p.name.startswith("scene_"))}
    public = root / "public"
    pub = {p.relative_to(public).as_posix(): p.stat().st_size for p in sorted(public.rglob("*"))
           if p.is_file() and p.name != meta.get("audio") and "projects" not in p.relative_to(public).parts}
    return mv.sha(mv.canon({"meta": {k: v for k, v in meta.items() if k not in ("duration", "audio")},
                            "words": comp.get("words") if meta.get("subtitles") else None, "src": src, "public": pub,
                            "config": [mv._file_sha(root / "remotion.config.ts"), mv._file_sha(root / "package.json")],
                            "assets": mv._file_sha(pdir / "assets_manifest.json"), "preview": preview, "flags": flags}))


def plan(pdir: Path, comp: dict, preview: bool, flags: list[str], cache: Path) -> list[dict]:
    """One entry per scene window: its frame range, its cache key and the file that holds (or will hold) the chunk."""
    public, g = config.REMOTION_DIR / "public", global_part(pdir, comp, preview, flags)
    chunks = []
    for w in windows(comp):
        prev = w["prev"]
        tail = {"material": _scene_material(pdir, prev["scene"], public), "frames": prev["out_frames"]} if prev and prev["out_frames"] else None
        key = mv.sha(mv.canon({"g": g, "range": [w["from"], w["to"]], "out_frames": w["out_frames"], "tail": tail,
                               "material": _scene_material(pdir, w["scene"], public)}))
        chunks.append({"scene": w["scene"]["id"], "from": w["from"], "to": w["to"], "key": key, "path": cache / f"{key}.mp4"})
    return chunks


def prune(cache: Path, chunks: list[dict]) -> None:
    """Chunks no scene of the current plan uses (a rewritten scene's old clip) are removed, so the cache never outgrows one render."""
    keep = {c["path"].name for c in chunks}
    for f in cache.glob("*.mp4"):
        if f.name not in keep:
            f.unlink(missing_ok=True)


def assemble(chunks: list[dict], audio: Path | None, fps: int, out: Path, work: Path) -> None:
    """Join the chunks (stream copy: every chunk starts on its own keyframe) and mux the audio in one ffmpeg call; the audio is cut where the picture ends."""
    frames = chunks[-1]["to"]
    lst = work / "chunks.txt"
    lst.write_text("".join(f"file '{c['path'].resolve().as_posix()}'\n" for c in chunks), encoding="utf-8")      # absolute: ffmpeg reads a relative entry from the folder of the list, not from the working folder
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst)]
    cmd += (["-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{frames / fps:.6f}"] if audio else ["-c", "copy"])
    r = subprocess.run(cmd + [str(out)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    lst.unlink(missing_ok=True)
    if r.returncode:
        out.unlink(missing_ok=True)
        raise RuntimeError("joining the scene chunks failed: " + (r.stderr or r.stdout).strip()[-300:])
