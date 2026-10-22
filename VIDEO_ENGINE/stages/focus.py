"""Focus point [x, y] in 0..1 via OpenCV spectral-residual saliency (centroid of the salient mass)."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .theme import THEME

FRAME = (1920, 1080)
PORTRAIT_FRAME = (1080, 1920)
KEEP_INSIDE = 0.15    # the zoom aims no closer than this share of the visible photo to its edge


def frame_focus(focus: list[float], image_size: tuple[int, int], pos="full", frame=FRAME, crop=False) -> list[float]:
    """Where a photo's focus point (0..1 of the photo) lands on screen (0..1 of the frame).

    ImageLayer fills its box with object-fit: cover, so a photo that is not the box's shape is cropped and shifted; the
    camera zooms around a FRAME coordinate, so the photo's own coordinate must be converted. `pos` is a named box from
    theme.json or [x, y, w, h] in pixels. The result stays inside the visible part of the box.

    A taller-than-wide frame (9:16) has its own box table. With `crop` the layer sets object-position to the focus point
    (ImageLayer `crop`), so the point sits at the same relative place in the box: box x + focus x * box width."""
    fw, fh = frame
    boxes = THEME["portrait"]["boxes"] if fh > fw else THEME["boxes"]
    if isinstance(pos, (list, tuple)):
        bx, by, bw, bh = pos
    else:
        x, y, w, h = boxes.get(pos, boxes["full"])
        bx, by, bw, bh = x * fw, y * fh, w * fw, h * fh
    iw, ih = image_size
    s = max(bw / iw, bh / ih)                                  # object-fit: cover
    dw, dh = iw * s, ih * s
    if crop:
        px, py = bx + focus[0] * bw, by + focus[1] * bh
    else:
        px = bx + (bw - dw) / 2 + focus[0] * dw
        py = by + (bh - dh) / 2 + focus[1] * dh
    px = min(max(px, bx + KEEP_INSIDE * bw), bx + (1 - KEEP_INSIDE) * bw)
    py = min(max(py, by + KEEP_INSIDE * bh), by + (1 - KEEP_INSIDE) * bh)
    return [round(px / fw, 3), round(py / fh, 3)]


def focus_point(path: Path) -> list[float]:
    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB").resize((256, 144)))
    try:
        ok, sal = cv2.saliency.StaticSaliencySpectralResidual_create().computeSaliency(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    except AttributeError:  # opencv-python without contrib: simple spectral residual in numpy
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        f = np.fft.fft2(g)
        log = np.log(np.abs(f) + 1e-6)
        res = log - cv2.blur(log, (3, 3))
        sal = cv2.GaussianBlur(np.abs(np.fft.ifft2(np.exp(res + 1j * np.angle(f)))) ** 2, (0, 0), 3)
        ok = True
    if not ok or sal.max() <= 0:
        return [0.5, 0.5]
    sal = np.clip(sal - np.percentile(sal, 70), 0, None)
    if sal.sum() <= 0:
        return [0.5, 0.5]
    ys, xs = np.mgrid[0:sal.shape[0], 0:sal.shape[1]]
    x, y = (xs * sal).sum() / sal.sum() / sal.shape[1], (ys * sal).sum() / sal.sum() / sal.shape[0]
    return [round(float(np.clip(x, 0.2, 0.8)), 3), round(float(np.clip(y, 0.2, 0.8)), 3)]  # keep zoom targets near center
