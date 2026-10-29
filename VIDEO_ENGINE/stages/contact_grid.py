"""The one contact-sheet drawing: pictures in a grid, each cell stamped with a label, so a vision model can see many pictures in ONE file.
Used by Asset Collection (candidate previews, labelled with their index) and by Final QC (frames of the rendered video, labelled with scene, kind and time)."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

BACKGROUND = (24, 24, 24)
TAG = (255, 235, 0)


def grid(cells: list[Image.Image | None], labels: list[str], cell: tuple[int, int], columns: int, empty: str = "no preview") -> Image.Image:
    """cells[i] shrunk into a cell of size `cell` (None = a cell that says `empty`), read left to right and top to bottom, with a yellow tag `labels[i]` in its top-left corner."""
    w, h = cell
    sheet = Image.new("RGB", (w * columns, h * -(-len(cells) // columns)), BACKGROUND)
    draw, font = ImageDraw.Draw(sheet), ImageFont.load_default(size=28)
    for i, (pic, label) in enumerate(zip(cells, labels)):
        x, y = (i % columns) * w, (i // columns) * h
        if pic:
            pic = pic.copy()
            pic.thumbnail((w - 4, h - 4))
            sheet.paste(pic, (x + (w - pic.width) // 2, y + (h - pic.height) // 2))
        else:
            draw.text((x + 12, y + h // 2 - 14), empty, fill=(170, 170, 170), font=font)
        draw.rectangle((x, y, x + max(44, int(font.getlength(label)) + 20), y + 40), fill=TAG)
        draw.text((x + 10, y + 4), label, fill=(0, 0, 0), font=font)
    return sheet
