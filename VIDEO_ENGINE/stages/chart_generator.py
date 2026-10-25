"""QuickChart Infographics & Data Visualization Generator.

Generates high-resolution chart graphics (Bar, Line, Pie, Doughnut) for numerical
and statistical callouts in Telugu video compositions using QuickChart API.
Zero API key required (public, free open API).
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

QUICKCHART_ENDPOINT = "https://quickchart.io/chart"
DEFAULT_PALETTE = [
    "#38BDF8",  # Sky blue
    "#34D399",  # Emerald green
    "#F472B6",  # Pink
    "#FBBF24",  # Amber
    "#A78BFA",  # Purple
    "#FB7185",  # Rose
]


def build_chart_config(
    chart_type: str,
    labels: List[str],
    data: List[float],
    title: str = "",
    label: str = "Metric",
    dark_mode: bool = True,
    colors: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Build a Chart.js v2/v3 compatible configuration dictionary."""
    palette = colors or DEFAULT_PALETTE
    chart_type = chart_type.lower()
    if chart_type in ("bar", "horizontalbar", "line"):
        bg_colors = palette[0] if chart_type == "line" else palette[:len(data)]
    else:  # pie, doughnut
        bg_colors = [palette[i % len(palette)] for i in range(len(data))]

    text_color = "#F8FAFC" if dark_mode else "#0F172A"
    grid_color = "rgba(255, 255, 255, 0.1)" if dark_mode else "rgba(0, 0, 0, 0.1)"

    dataset: Dict[str, Any] = {
        "label": label,
        "data": data,
        "backgroundColor": bg_colors,
        "borderColor": palette[0] if chart_type == "line" else "transparent",
        "borderWidth": 3 if chart_type == "line" else 1,
        "fill": False if chart_type == "line" else True,
    }

    config: Dict[str, Any] = {
        "type": chart_type,
        "data": {
            "labels": labels,
            "datasets": [dataset]
        },
        "options": {
            "responsive": True,
            "plugins": {
                "legend": {
                    "display": chart_type in ("pie", "doughnut"),
                    "labels": {"color": text_color, "font": {"size": 16, "family": "Inter, sans-serif"}}
                },
                "title": {
                    "display": bool(title),
                    "text": title,
                    "color": text_color,
                    "font": {"size": 22, "weight": "bold", "family": "Inter, sans-serif"},
                    "padding": {"top": 10, "bottom": 20}
                }
            }
        }
    }

    if chart_type in ("bar", "line"):
        config["options"]["scales"] = {
            "x": {
                "ticks": {"color": text_color, "font": {"size": 14}},
                "grid": {"color": grid_color}
            },
            "y": {
                "ticks": {"color": text_color, "font": {"size": 14}},
                "grid": {"color": grid_color}
            }
        }

    return config


def generate_chart_url(
    config: Dict[str, Any],
    width: int = 1280,
    height: int = 720,
    bg_color: str = "#0B0F19",
    device_pixel_ratio: int = 2
) -> str:
    """Return an authoritative URL rendering the chart via QuickChart."""
    params = {
        "c": json.dumps(config),
        "w": str(width),
        "h": str(height),
        "bkg": bg_color,
        "devicePixelRatio": str(device_pixel_ratio)
    }
    return f"{QUICKCHART_ENDPOINT}?{urllib.parse.urlencode(params)}"


def render_and_save_chart(
    config: Dict[str, Any],
    output_path: str | Path,
    width: int = 1280,
    height: int = 720,
    bg_color: str = "#0B0F19"
) -> Path:
    """Send chart specification to QuickChart and write image file to disk."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    
    url = generate_chart_url(config, width=width, height=height, bg_color=bg_color)
    req = urllib.request.Request(url, headers={"User-Agent": "AudioToVideo/2.0 (ChartGenerator)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    
    out.write_bytes(data)
    return out
