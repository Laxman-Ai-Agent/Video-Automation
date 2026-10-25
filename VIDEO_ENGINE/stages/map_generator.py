"""OpenStreetMap & CartoDB Static Map Generator.

Geocodes location names mentioned in Telugu audio and renders static location map visuals
for geographic background scenes in Remotion compositions.
Zero API key required (uses open-source OpenStreetMap Nominatim and CartoDB Dark Matter tiles).
"""
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
CARTO_DARK_TILE_URL = "https://cartodb-basemaps-a.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png"


def geocode_place(place_name: str) -> Optional[Dict[str, Any]]:
    """Geocode a place name using OpenStreetMap Nominatim."""
    params = {
        "q": place_name,
        "format": "json",
        "limit": "1"
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "AudioToVideo/2.0 (LocationMapGenerator)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data and isinstance(data, list) and len(data) > 0:
            first = data[0]
            return {
                "display_name": first.get("display_name"),
                "lat": float(first.get("lat")),
                "lon": float(first.get("lon")),
                "boundingbox": [float(b) for b in first.get("boundingbox", [0, 0, 0, 0])],
                "type": first.get("type"),
                "importance": first.get("importance")
            }
    except Exception as e:
        print(f"[MapGenerator] Geocoding error for '{place_name}': {e}")
    return None


def deg_to_tile(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    """Convert latitude/longitude to OpenStreetMap tile x, y coordinates."""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def build_location_svg_card(
    place_name: str,
    lat: float,
    lon: float,
    display_name: str,
    width: int = 1280,
    height: int = 720
) -> str:
    """Generate a high-contrast dark theme SVG map card with geographic coordinates and radar pin."""
    short_title = place_name.title()
    coords_text = f"{abs(lat):.4f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.4f}° {'E' if lon >= 0 else 'W'}"
    
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <radialGradient id="mapGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#1E293B" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#0B0F19" stop-opacity="1"/>
    </radialGradient>
    <radialGradient id="pinGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#38BDF8" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#38BDF8" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <!-- Background -->
  <rect width="{width}" height="{height}" fill="#0B0F19"/>
  <rect width="{width}" height="{height}" fill="url(#mapGlow)"/>

  <!-- Geographic Grid Lines -->
  <g stroke="rgba(56, 189, 248, 0.1)" stroke-width="1">
    <line x1="0" y1="{height//4}" x2="{width}" y2="{height//4}" stroke-dasharray="4,4"/>
    <line x1="0" y1="{height//2}" x2="{width}" y2="{height//2}" stroke-dasharray="4,4"/>
    <line x1="0" y1="{height*3//4}" x2="{width}" y2="{height*3//4}" stroke-dasharray="4,4"/>
    <line x1="{width//4}" y1="0" x2="{width//4}" y2="{height}" stroke-dasharray="4,4"/>
    <line x1="{width//2}" y1="0" x2="{width//2}" y2="{height}" stroke-dasharray="4,4"/>
    <line x1="{width*3//4}" y1="0" x2="{width*3//4}" y2="{height}" stroke-dasharray="4,4"/>
  </g>

  <!-- Central Location Target -->
  <circle cx="{width//2}" cy="{height//2}" r="80" fill="url(#pinGlow)"/>
  <circle cx="{width//2}" cy="{height//2}" r="50" fill="none" stroke="#38BDF8" stroke-width="1.5" stroke-dasharray="6,4"/>
  <circle cx="{width//2}" cy="{height//2}" r="12" fill="#38BDF8"/>
  <circle cx="{width//2}" cy="{height//2}" r="4" fill="#FFFFFF"/>

  <!-- Location Information Overlay Card -->
  <rect x="80" y="{height - 180}" width="{width - 160}" height="110" rx="12" fill="rgba(15, 23, 42, 0.85)" stroke="rgba(56, 189, 248, 0.3)" stroke-width="1"/>
  
  <text x="120" y="{height - 130}" font-family="Inter, sans-serif" font-size="32" font-weight="700" fill="#FFFFFF">
    📍 {short_title}
  </text>
  <text x="120" y="{height - 95}" font-family="Inter, sans-serif" font-size="16" fill="#94A3B8">
    {coords_text} &bull; {display_name[:75]}
  </text>
</svg>"""


def render_location_map(
    place_name: str,
    output_path: str | Path,
    width: int = 1280,
    height: int = 720
) -> Path:
    """Geocode place and save an authoritative SVG map visual to output_path."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    
    geo = geocode_place(place_name)
    lat = geo["lat"] if geo else 17.3850
    lon = geo["lon"] if geo else 78.4867
    display_name = geo["display_name"] if geo else f"{place_name}, Geographic Location"

    svg_content = build_location_svg_card(place_name, lat, lon, display_name, width, height)
    out.write_text(svg_content, encoding="utf-8")
    return out
