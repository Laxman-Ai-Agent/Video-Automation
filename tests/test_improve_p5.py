"""Phase 5 (lite) of improvement/MASTER_PLAN.md: video icons and number callouts stay readable on a photo, the lower-third / label / caption stay inside the
safe areas with enough contrast, Telugu text really draws glyphs, and the layer order is right. Measured in the REAL Remotion renderer (stills of
960x540 / 540x960) on a pure white worst-case photo and on the sample photos."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend import config, graphics, palette as pal
from backend.telugu import glen
from backend.theme import THEME

ROOT = config.PROJECT_ROOT
ACCENT = np.array([0xF2, 0xA5, 0x41], float)


# ---------- pure parts (no renderer) ----------
def test_backing_token_gives_the_accent_enough_contrast_over_the_worst_case_photo():
    b = THEME["backing"]
    base = np.array([int(b["color"][i:i + 2], 16) for i in (1, 3, 5)], float)
    on_white = np.round(b["opacity"] * base + (1 - b["opacity"]) * 255)                      # the backing over a pure white photo
    assert pal.contrast("#F2A541", "#" + "".join(f"{int(v):02x}" for v in on_white)) >= THEME["minContrast"]
    weak = np.round(0.45 * base + 0.55 * 255)
    assert pal.contrast("#F2A541", "#" + "".join(f"{int(v):02x}" for v in weak)) < THEME["minContrast"]    # the check can fail: the text scrim alone is not enough for an accent icon


def test_apply_graphics_marks_icons_and_counters_on_photos_only_and_is_idempotent():
    comp = {"scenes": [
        {"id": 1, "layers": [{"type": "image", "file": "a.png"}, {"type": "icon", "lucide": "star"}, {"type": "counter", "to": 5}]},
        {"id": 2, "layers": [{"type": "background"}, {"type": "icon", "lucide": "star"}, {"type": "counter", "to": 5}]},
        {"id": 3, "layers": [{"type": "image", "file": None}, {"type": "counter", "to": 5}, {"type": "icon", "lucide": "x", "enabled": False}]},
    ]}
    assert graphics.apply_graphics(comp) == 3
    got = [[bool(l.get("backing")) for l in s["layers"]] for s in comp["scenes"]]
    assert got == [[False, True, True], [False, True, False], [False, False, False]]           # a counter on a plain background and a disabled icon are left alone
    assert graphics.apply_graphics(comp) == 0


# ---------- the real renderer ----------
def _render_ready() -> str | None:
    import socket
    if not shutil.which("node") or not shutil.which("npx"):
        return "node/npx not on PATH"
    if not (ROOT / "VIDEO_ENGINE" / "remotion" / "node_modules" / "@remotion" / "renderer").exists():
        return "remotion dependencies are not installed"
    try:
        [socket.create_connection((h, 443), timeout=4).close() for h in ("fonts.googleapis.com", "fonts.gstatic.com")]
    except OSError:
        return "Google Fonts unreachable (the renderer fetches Poppins/Noto Sans Telugu at render time)"
    return None


def _lin(c):
    c = np.asarray(c, float) / 255
    return np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _lum(rgb):
    rgb = np.asarray(rgb, float)
    return 0.2126 * _lin(rgb[..., 0]) + 0.7152 * _lin(rgb[..., 1]) + 0.0722 * _lin(rgb[..., 2])


def _ratio(a, b):
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def comp(layers, w=1920, h=1080):
    return {"meta": {"fps": 15, "width": w, "height": h, "audio": "audio_test.wav", "duration": 4.0, "subtitles": False, "palette": ["#0B1D26", "#F2A541", "#2A9D8F"]},
            "scenes": [{"id": 1, "start": 0, "end": 4, "camera": {"move": "static", "from": 1, "to": 1, "focus": [0.5, 0.5]},
                        "layers": [{"type": "background", "kind": "gradient", "colors": ["#0B1D26", "#2A9D8F"], "z": 0}, *layers]}]}


def photo(name):
    return {"type": "image", "slot": "s01_0", "file": name, "z": 1, "pos": "full"}


def icon(**kw):
    return {"type": "icon", "lucide": "droplet", "pos": [960, 300], "size": 160, "z": 10, **kw}


def counter(**kw):
    return {"type": "counter", "from": 0, "to": 1400, "unit": "km", "at": 0, "dur": 0.2, "pos": [960, 700], "z": 5, **kw}


def text(style, t, z=10, **kw):
    return {"type": "text", "style": style, "text": t, "at": 0.0, "z": z, **kw}


TE_A, TE_B = "తెలుగు భాష", "కార్యక్రమం"


@pytest.fixture(scope="module")
def stills(tmp_path_factory):
    why = _render_ready()
    if why:
        pytest.skip(why)
    base = tmp_path_factory.mktemp("p5")
    pub = base / "public"
    pub.mkdir()
    for f in ("audio_test.wav", "img_01.png", "img_02.png", "img_03.png"):
        shutil.copy(ROOT / "VIDEO_ENGINE" / "remotion" / "public" / f, pub / f)
    Image.fromarray(np.full((1080, 1920, 3), 255, np.uint8)).save(pub / "white.png")             # the worst case: a pure white photo
    assert glen(TE_A) > 0 and glen(TE_B) > 0
    P = (1080, 1920)
    cases = {
        "icon_plain_white": comp([photo("white.png"), icon()]),
        "icon_back_white": comp([photo("white.png"), icon(backing=True)]),
        "icon_plain_img1": comp([photo("img_01.png"), icon()]),
        "icon_back_img1": comp([photo("img_01.png"), icon(backing=True)]),
        "icon_back_img2": comp([photo("img_02.png"), icon(backing=True)]),
        "icon_back_img3": comp([photo("img_03.png"), icon(backing=True)]),
        "counter_plain_white": comp([photo("white.png"), counter()]),
        "counter_back_white": comp([photo("white.png"), counter(backing=True)]),
        "lower_white": comp([photo("white.png"), text("lower-third", "Krishna River basin")]),
        "label_white": comp([photo("white.png"), text("label", "1,400 km long")]),
        "caption_white": comp([photo("white.png"), text("caption", "Water is life")]),
        "lower_white_p": comp([photo("white.png"), text("lower-third", "Krishna River basin")], *P),
        "label_white_p": comp([photo("white.png"), text("label", "1,400 km long")], *P),
        "caption_white_p": comp([photo("white.png"), text("caption", "Water is life")], *P),
        "base_white": comp([photo("white.png")]),
        "base_white_p": comp([photo("white.png")], *P),
        "te_a": comp([text("label", TE_A)]),
        "te_b": comp([text("label", TE_B)]),
        "order": comp([photo("img_01.png"), icon(backing=True), text("big-highlight", "TOP", z=12, pos=[800, 270])]),
        "order_icon_only": comp([photo("img_01.png"), icon(backing=True)]),
    }
    (base / "cases.json").write_text(json.dumps({"scale": 0.5, "publicDir": str(pub), "cases": [{"name": n, "frame": 30, "props": c} for n, c in cases.items()]}, ensure_ascii=False), encoding="utf-8")
    cmd = f'npx tsx scripts/caption_probe.ts "{base / "cases.json"}" "{base / "out"}"'
    for attempt in range(2):                                                                      # the renderer start can fail once on a locked temp file (Windows): one retry
        r = subprocess.run(cmd, cwd=ROOT / "VIDEO_ENGINE" / "remotion", shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        if r.returncode == 0:
            break
    if r.returncode != 0 and "fetchFontData" in (r.stderr + r.stdout):
        pytest.skip("the web fonts could not be downloaded at render time (network): not a code failure")
    assert r.returncode == 0, (r.stderr or r.stdout)[-800:]
    return base / "out"


def load(stills, name):
    return np.array(Image.open(stills / f"{name}.png").convert("RGB")).astype(float)


def icon_contrast(im):
    h, w, _ = im.shape
    x, y, r = w // 2, int(300 / 1080 * h), int(80 / 1080 * h)
    reg = im[y - r:y + r, x - r:x + r]
    ink = np.linalg.norm(reg - ACCENT, axis=2) < 70
    assert ink.sum() > 100, "the icon did not draw"
    return _ratio(float(_lum(ACCENT)), float(np.median(_lum(reg[~ink]))))


def text_ink(im, base=None, floor=180):
    """Pixels of the text: bright pixels inside the box of the dark panel that appeared when the text layer was added (found by comparing with the same
    picture without it). Brightness alone cannot tell white text from a white photo, and the film look dims every white to about 242."""
    mask = im.min(axis=2) >= floor
    if base is not None:
        panel = (base.mean(axis=2) - im.mean(axis=2)) > 40
        if panel.sum() > 200:
            ys, xs = np.where(panel)
            box = np.zeros_like(mask)
            box[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = True
            mask &= box
    return mask


def ink_box(im, base=None):
    mask = text_ink(im, base)
    ys, xs = np.where(mask)
    assert len(xs) > 40, "no text ink"
    h, w, _ = im.shape
    return xs.min() / w, xs.max() / w, ys.min() / h, ys.max() / h, mask


def text_contrast(im, base=None):
    """WCAG contrast between the text colour and the panel it sits on (median colours). With a baseline the panel is exactly the area that was darkened
    by adding the text layer; without one (text on a plain background) it is the neighbourhood of the text."""
    x0, x1, y0, y1, mask = ink_box(im, base)
    h, w, _ = im.shape
    sl = (slice(max(int(y0 * h) - 8, 0), int(y1 * h) + 8), slice(max(int(x0 * w) - 8, 0), int(x1 * w) + 8))
    reg, m = im[sl], mask[sl]
    around = ~m
    if base is not None:
        around &= (base[sl].mean(axis=2) - reg.mean(axis=2)) > 40
    return _ratio(float(np.median(_lum(reg[m]))), float(np.median(_lum(reg[around]))))


def test_icon_on_a_white_photo_needs_the_backing(stills):
    plain, backed = icon_contrast(load(stills, "icon_plain_white")), icon_contrast(load(stills, "icon_back_white"))
    assert plain < THEME["minContrast"]                                      # the defect: an amber icon on a bright photo is hard to see
    assert backed >= THEME["minContrast"] and backed > 1.5 * plain


def test_icon_on_the_sample_photos(stills):
    assert icon_contrast(load(stills, "icon_plain_img1")) < THEME["minContrast"]          # even the dark sample photo is below 3:1 without the backing
    for n in ("icon_back_img1", "icon_back_img2", "icon_back_img3"):
        assert icon_contrast(load(stills, n)) >= THEME["minContrast"], n


def test_number_callout_on_a_white_photo(stills):
    base, plain, backed = load(stills, "base_white"), load(stills, "counter_plain_white"), load(stills, "counter_back_white")
    assert (plain - base).max() <= 3                                           # the bare callout adds NO brightness over a white photo: only its shadow shows
    assert text_contrast(backed, base) >= 4.5                                  # on its dark panel the number is clearly readable
    assert text_ink(backed, base).sum() > 300


@pytest.mark.parametrize("name,portrait", [("lower_white", False), ("label_white", False), ("caption_white", False), ("lower_white_p", True), ("label_white_p", True), ("caption_white_p", True)])
def test_lower_third_label_caption_safe_area_and_contrast(stills, name, portrait):
    im, base = load(stills, name), load(stills, "base_white_p" if portrait else "base_white")
    x0, x1, y0, y1, _ = ink_box(im, base)
    m, tol = config.SAFE_AREA["margin"], 0.012
    assert x0 >= m - tol and x1 <= 1 - m + tol, f"{name}: text spans {x0:.3f}-{x1:.3f}"
    assert y0 >= m - tol, f"{name}: text top {y0:.3f}"
    assert y1 <= 1 - (config.SAFE_AREA["portrait_ui_bottom"] if portrait else m) + tol, f"{name}: text bottom {y1:.3f}"
    assert text_contrast(im, base) >= THEME["minContrast"], f"{name}: text contrast {text_contrast(im, base):.2f}"


def test_telugu_text_draws_real_glyphs_not_placeholder_boxes(stills):
    """Two different Telugu words must draw different shapes; a missing font draws the same box for every letter."""
    a, b = (text_ink(load(stills, n)) for n in ("te_a", "te_b"))
    assert a.sum() > 100 and b.sum() > 100

    def crop(m):
        ys, xs = np.where(m)
        return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    size = (160, 40)
    ra, rb = (np.array(Image.fromarray((crop(m) * 255).astype(np.uint8)).resize(size)) > 127 for m in (a, b))
    iou = (ra & rb).sum() / max((ra | rb).sum(), 1)
    assert iou < 0.8, f"the two Telugu words look the same (overlap {iou:.2f}): the glyphs are probably not drawn"


def test_layer_order_text_above_icon_above_photo(stills):
    with_text, only_icon = load(stills, "order"), load(stills, "order_icon_only")
    h, w, _ = with_text.shape
    x, y, r = w // 2, int(300 / 1080 * h), int(110 / 1080 * h)
    box = (slice(y - r, y + r), slice(x - r, x + r))
    assert text_ink(only_icon)[box].sum() < 40                              # the icon alone has (almost) no white pixels there
    assert text_ink(with_text)[box].sum() > 150                              # with the text layer on top, white text covers the icon area
    assert icon_contrast(only_icon) >= THEME["minContrast"]                              # and the icon itself is drawn above the photo
