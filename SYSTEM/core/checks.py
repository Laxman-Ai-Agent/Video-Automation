"""Per-image quality checks (Pillow/OpenCV/imagehash). No LLM, no network."""
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image

from . import config

RATIOS = {"16:9": 16 / 9, "4:3": 4 / 3, "1:1": 1.0, "9:16": 9 / 16, "3:4": 3 / 4}


def has_alpha(path: Path) -> bool:
    with Image.open(path) as im:
        return "A" in im.getbands()


def white_background_score(path: Path) -> float:
    """Share of border pixels that are near-white (1.0 = plain white background)."""
    with Image.open(path) as im:
        a = np.asarray(im.convert("RGB").resize((128, 128)))
    border = np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3), a[:, :4].reshape(-1, 3), a[:, -4:].reshape(-1, 3)])
    return float((border.min(axis=1) > 235).mean())


def image_checks(path: Path, role: str, ratio: str) -> list[str]:
    """Warning types for one image: low_res | bad_ratio | blurry."""
    out: list[str] = []
    with Image.open(path) as im:
        w, h = im.size
        gray = cv2.cvtColor(np.asarray(im.convert("RGB")), cv2.COLOR_RGB2GRAY)
    if role in ("main", "background") and w < config.HERO_MIN_WIDTH:
        out.append("low_res")
    if abs((w / h) / RATIOS[ratio] - 1) > config.RATIO_TOLERANCE:
        out.append("bad_ratio")
    if cv2.Laplacian(gray, cv2.CV_64F).var() < config.BLUR_MIN_VAR:
        out.append("blurry")
    return out


def duplicates(paths: list[Path]) -> list[list[str]]:
    """Groups of near-identical images (perceptual hash distance <= DUP_HASH_DISTANCE)."""
    hashes = []
    for p in paths:
        with Image.open(p) as im:
            hashes.append((p.name, imagehash.phash(im.convert("RGB"))))
    out = []
    for i, (a, ha) in enumerate(hashes):
        for b, hb in hashes[i + 1:]:
            if ha - hb <= config.DUP_HASH_DISTANCE:
                out.append([a, b])
    return out
