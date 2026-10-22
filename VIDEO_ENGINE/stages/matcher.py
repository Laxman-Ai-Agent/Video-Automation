"""Match uploaded images to prompts. Filename number first, then CLIP + Hungarian. Never guesses silently.
  python -m backend.matcher projects/demo [folder-or-files...]      (uploads optional; scans assets/raw)"""
import gc
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")   # CLIP weights come from the local HF cache only

import numpy as np

from . import config
from .assets import number_from_name, raw_dir, save_uploads, work_dir
from .checks import duplicates, image_checks, white_background_score
from .contracts import band, locked_numbers
from .models import MatchItem, MatchReport, PromptsMap

WHITE_ROLES = ("icon", "object")


def _clip_scores(images: list[Path], texts: list[str]) -> np.ndarray:
    """Cosine similarity matrix [n_images, n_texts]. CLIP is loaded once and freed."""
    import open_clip
    import torch
    from PIL import Image

    model, _, pre = open_clip.create_model_and_transforms(config.CLIP_MODEL, pretrained=config.CLIP_PRETRAINED)
    tok = open_clip.get_tokenizer(config.CLIP_MODEL)
    model.eval()
    with torch.no_grad():
        t = model.encode_text(tok(texts))
        t = t / t.norm(dim=-1, keepdim=True)
        embs = []
        for i in range(0, len(images), 8):
            batch = torch.stack([pre(Image.open(p).convert("RGB")) for p in images[i:i + 8]])
            e = model.encode_image(batch)
            embs.append(e / e.norm(dim=-1, keepdim=True))
        s = (torch.cat(embs) @ t.T).numpy()
    del model
    gc.collect()
    return s


def _cue_texts(pdir: Path) -> dict[int, str]:
    """prompt number -> the narration phrase (English) it illustrates; empty when there is no translation or no overlap (scene-level fallback)."""
    from . import cues
    try:
        c = cues.build(pdir)
    except (OSError, ValueError, KeyError):
        return {}
    text = {x["id"]: x["text"] for x in c["cues"]}
    return {int(n): text[cid] for n, cid in c["links"].items() if cid}


def match(pdir: Path) -> MatchReport:
    from scipy.optimize import linear_sum_assignment

    prompts = sorted(PromptsMap.model_validate_json((pdir / "prompts_map.json").read_text(encoding="utf-8")).prompts, key=lambda p: p.n)
    raw = {f.stem: f for f in sorted(raw_dir(pdir).iterdir()) if f.suffix.lower() in config.IMAGE_EXTS} if raw_dir(pdir).exists() else {}
    work = {s: work_dir(pdir) / f"{s}.png" for s in raw if (work_dir(pdir) / f"{s}.png").exists()}
    stems = list(work)
    idx = {p.n: j for j, p in enumerate(prompts)}
    items: dict[int, MatchItem] = {}

    improve = config.improve("match_detail")      # A2V_MATCH_DETAIL=1: bands, cue agreement, locks, duplicate warning (off: behavior unchanged)
    cue_text = _cue_texts(pdir) if improve else {}
    S = np.zeros((len(stems), len(prompts)))
    S_cue = np.zeros((len(stems), 0))
    cue_col = {n: k for k, n in enumerate(sorted(cue_text))}
    if stems and prompts:
        full = _clip_scores([work[s] for s in stems], [p.text for p in prompts] + [cue_text[n] for n in sorted(cue_text)])
        S, S_cue = full[:, :len(prompts)], full[:, len(prompts):]
        for i, s in enumerate(stems):   # role-aware soft penalty (never a hard reject)
            white = white_background_score(work[s]) >= config.WHITE_BORDER_FRACTION
            for j, p in enumerate(prompts):
                if (p.role in WHITE_ROLES) != white:
                    S[i, j] -= config.ROLE_PENALTY

    taken: set[int] = set()
    if improve:      # 0) images the user locked (locks.json, or chosen by hand) keep their prompt: nothing below may change or reuse them
        rf = pdir / "match_report.json"
        old = MatchReport.model_validate_json(rf.read_text(encoding="utf-8")) if rf.exists() else None
        if old:
            for m in old.matches:
                if m.n in idx and m.file and m.n in locked_numbers(pdir, old.matches) and Path(m.file).stem in work:
                    items[m.n] = m
                    taken.add(stems.index(Path(m.file).stem))

    # 1) filename numbers (duplicate claims are NOT guessed)
    by_num: dict[int, list[int]] = {}
    for i, s in enumerate(stems):
        n = number_from_name(raw[s].name)
        if n in idx and n not in items:
            by_num.setdefault(n, []).append(i)
    for n, ims in by_num.items():
        if len(ims) > 1:
            names = ", ".join(raw[stems[i]].name for i in ims)
            items[n] = MatchItem(n=n, file=None, method="none", status="review", note="several files claim this number: " + names)
            taken.update(ims)
            continue
        i, j = ims[0], idx[n]
        other = np.delete(S[i], j)
        margin = float(S[i, j] - other.max()) if other.size else float(S[i, j])
        bad = margin < -config.CLIP_MIN_MARGIN       # file name says n, but the content fits another prompt better
        alt = prompts[int(np.argmax(S[i]))].n
        items[n] = MatchItem(n=n, file=raw[stems[i]].name, method="filename", score=round(float(S[i, j]), 3),
                             margin=round(margin, 3), status="review" if bad else "ok",
                             note=f"content fits prompt {alt} better than {n}" if bad else None)
        taken.add(i)

    # 2) CLIP + Hungarian on what is left
    pool_i = [i for i in range(len(stems)) if i not in taken]
    pool_j = [j for j, p in enumerate(prompts) if p.n not in items]
    if pool_i and pool_j:
        sub = S[np.ix_(pool_i, pool_j)]
        for a, b in zip(*linear_sum_assignment(-sub)):
            i, j = pool_i[a], pool_j[b]
            others = np.delete(sub[a], b)
            margin = float(sub[a, b] - others.max()) if others.size else float(sub[a, b])
            ok = sub[a, b] >= config.CLIP_MIN_SCORE and margin >= config.CLIP_MIN_MARGIN
            alt = prompts[pool_j[int(np.argmax(sub[a]))]].n
            medium = improve and ok and band(float(sub[a, b]), margin) != "high"      # medium confidence goes to review, only high is used without a look
            items[prompts[j].n] = MatchItem(
                n=prompts[j].n, file=raw[stems[i]].name, method="clip", score=round(float(sub[a, b]), 3),
                margin=round(margin, 3), status="ok" if ok and not medium else "review",
                note=("medium confidence - please confirm" if medium else None) if ok else f"low confidence (closest other prompt: {alt})")
            taken.add(i)
    unused = [raw[stems[i]].name for i in range(len(stems)) if i not in taken]
    for p in prompts:
        items.setdefault(p.n, MatchItem(n=p.n, file=None, method="none", status="missing",
                                        note=None if p.required else "optional"))
    matches = [items[p.n] for p in prompts]

    warnings = []
    role = {p.n: p for p in prompts}
    for m in matches:
        if m.file:
            for w in image_checks(work[Path(m.file).stem], role[m.n].role, role[m.n].ratio):
                warnings.append({"file": m.file, "n": m.n, "type": w})
    # duplicates() reports work-copy file names ("01.png"); raw is keyed by stem ("01"), so normalize before lookup
    dups = [[raw[Path(a).stem].name, raw[Path(b).stem].name] for a, b in duplicates([work[s] for s in stems])] if stems else []
    if improve:
        locked = locked_numbers(pdir, matches)
        file_row = {m.file: i for i, m in enumerate(matches) if m.file}
        for n_of, m in ((m.n, m) for m in matches if m.file and m.status == "ok" and m.n not in locked and cue_col.get(m.n) is not None):
            # the image should fit the narration of ITS prompt at least as well as the narration of the other prompts (a cue-level check on top of the prompt-level one)
            i = stems.index(Path(m.file).stem)
            own = S_cue[i, cue_col[n_of]]
            rivals = [(S_cue[i, c], k) for k, c in cue_col.items() if k != n_of and cue_text[k] != cue_text[n_of]]
            if rivals and own - max(rivals)[0] < -config.CLIP_MIN_MARGIN:
                m.status, m.note = "review", f"image fits the narration of prompt {max(rivals)[1]} better"
        for a, b in dups:      # two prompts showing the same picture is repetition, not variety
            ma, mb = (matches[file_row[x]] if x in file_row else None for x in (a, b))
            if ma and mb and mb.status == "ok" and mb.n not in locked:
                mb.status, mb.note = "review", f"looks the same as the image of prompt {ma.n}"
    return MatchReport(matches=matches, unused=unused, duplicates=dups, warnings=warnings)


def save_report(pdir: Path, rep: MatchReport) -> None:
    (pdir / "match_report.json").write_text(rep.model_dump_json(indent=1), encoding="utf-8")
    if config.improve("match_detail"):
        from .match_detail import write
        write(pdir, rep)


def print_table(rep: MatchReport) -> None:
    print(f"{'n':>3} {'file':24} {'method':8} {'score':>6} {'margin':>7}  status")
    for m in rep.matches:
        sc = "" if m.score is None else m.score
        mg = "" if m.margin is None else m.margin
        print(f"{m.n:>3} {(m.file or '-'):24} {m.method:8} {sc:>6} {mg:>7}  {m.status}" + (f"  ({m.note})" if m.note else ""))
    print(f"unused={rep.unused} duplicates={rep.duplicates} warnings={len(rep.warnings)}")


def apply_fix(project: str | Path, fix: dict) -> MatchReport:
    """Manual correction, e.g. apply_fix("demo", {"file": "x.png", "n": 7}). Updates the report (and composition if present)."""
    pdir = config.project_dir(project)
    rep = MatchReport.model_validate_json((pdir / "match_report.json").read_text(encoding="utf-8"))
    n, f = int(fix["n"]), fix["file"]
    if not (raw_dir(pdir) / f).exists():
        raise FileNotFoundError(f"{f} is not in assets/raw")
    for m in rep.matches:
        if m.file == f and m.n != n:        # the file leaves its old prompt
            m.file, m.method, m.score, m.margin, m.status, m.note = None, "none", None, None, "missing", f"{f} moved to {n}"
        if m.n == n:                         # whoever held n is released
            if m.file and m.file != f:
                rep.unused.append(m.file)
            m.file, m.method, m.score, m.margin, m.status, m.note = f, "manual", None, None, "ok", "manual fix"
    rep.unused = [u for u in rep.unused if u != f]
    # image-specific checks belong to the image: drop stale ones, recompute for the newly selected file
    prompt = next((p for p in PromptsMap.model_validate_json((pdir / "prompts_map.json").read_text(encoding="utf-8")).prompts if p.n == n), None)
    if prompt is None:
        raise ValueError(f"prompt {n} does not exist")
    rep.warnings = [w for w in rep.warnings if w.get("n") != n and w.get("file") != f]
    rep.warnings += [{"file": f, "n": n, "type": t} for t in image_checks(work_dir(pdir) / (Path(f).stem + ".png"), prompt.role, prompt.ratio)]
    save_report(pdir, rep)
    # Note: fill_slots was removed in Motion-Only architecture
    return rep


def run(pdir: Path, uploads: list[Path] | None = None) -> MatchReport:
    if uploads:
        r = save_uploads(pdir, uploads)
        print(f"uploads: saved={len(r['saved'])} ignored={len(r['ignored'])} broken={len(r['broken'])}")
    rep = match(pdir)
    save_report(pdir, rep)
    return rep


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    print_table(run(pdir, [Path(a) for a in sys.argv[2:]] or None))
