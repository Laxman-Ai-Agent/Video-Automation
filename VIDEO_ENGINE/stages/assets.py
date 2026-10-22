"""Save uploaded images, keep original names, make RGB/RGBA PNG work copies.
python -m backend.assets projects/demo <folder-or-files...>"""
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

from . import config


def raw_dir(pdir: Path) -> Path:
    return pdir / "assets" / "raw"


def work_dir(pdir: Path) -> Path:
    return pdir / "assets" / "work"


def number_from_name(name: str) -> int | None:
    """`07.png`, `7-river.jpg`, `012_x.webp` -> prompt number (leading digits only)."""
    m = re.match(r"^(\d{1,3})(?!\d)", Path(name).stem)
    return int(m.group(1)) if m else None


def save_uploads(pdir: Path, sources: list[Path]) -> dict:
    """Copy images from files/folders into assets/raw (original names) and assets/work (PNG, max width)."""
    files: list[Path] = []
    for s in sources:
        files += [f for f in sorted(s.iterdir()) if f.is_file()] if s.is_dir() else [s]
    raw, work = raw_dir(pdir), work_dir(pdir)
    raw.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    saved, ignored, broken = [], [], []
    for f in files:
        if f.suffix.lower() not in config.IMAGE_EXTS:
            ignored.append(f.name)
            continue
        dst = raw / f.name
        if f.resolve() != dst.resolve():
            shutil.copyfile(f, dst)
        try:
            with Image.open(dst) as im:
                im.load()
                im = im.convert("RGBA" if "A" in im.getbands() or im.mode == "P" and "transparency" in im.info else "RGB")
                if im.width > config.MAX_IMAGE_WIDTH:
                    im = im.resize((config.MAX_IMAGE_WIDTH, round(im.height * config.MAX_IMAGE_WIDTH / im.width)), Image.LANCZOS)
                im.save(work / (dst.stem + ".png"))
            saved.append(f.name)
        except Exception as e:  # corrupt/unreadable image: report, never crash
            broken.append(f"{f.name}: {e}")
    return {"saved": saved, "ignored": ignored, "broken": broken}


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    r = save_uploads(pdir, [Path(a) for a in sys.argv[2:]] or [raw_dir(pdir)])
    print(f"saved={len(r['saved'])} ignored={len(r['ignored'])} broken={len(r['broken'])}", *r["broken"], sep="\n")
