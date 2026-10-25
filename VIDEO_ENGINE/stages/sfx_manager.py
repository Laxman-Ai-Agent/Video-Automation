"""Motion Sound Effects (SFX) & Audio Asset Manager.

Manages motion transition sound effects (Whoosh, Pop, Ding, Swoosh, Riser)
for Remotion compositions, with Freesound API search integration.
"""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

FREESOUND_API_URL = "https://freesound.org/apiv2/search/text/"

BUILTIN_SFX_PRESETS: Dict[str, Dict[str, Any]] = {
    "whoosh": {
        "name": "Transition Whoosh",
        "category": "transition",
        "description": "Smooth airy whoosh for scene cuts and slide transitions",
        "duration_ms": 450,
        "filename": "whoosh.wav"
    },
    "pop": {
        "name": "Element Pop",
        "category": "kinetic",
        "description": "Clean wooden/bubble pop for icon and text reveals",
        "duration_ms": 180,
        "filename": "pop.wav"
    },
    "ding": {
        "name": "Metric Ding",
        "category": "highlight",
        "description": "Bright crystal chime for statistical and number highlights",
        "duration_ms": 600,
        "filename": "ding.wav"
    },
    "swoosh": {
        "name": "Fast Swoosh",
        "category": "motion",
        "description": "Fast kinetic whip for rapid text cards and chart wipes",
        "duration_ms": 320,
        "filename": "swoosh.wav"
    },
    "riser": {
        "name": "Cinematic Riser",
        "category": "build",
        "description": "Subtle pitch riser leading into climax or topic conclusion",
        "duration_ms": 1200,
        "filename": "riser.wav"
    }
}


def list_builtin_sfx() -> List[Dict[str, Any]]:
    """Return catalog of available built-in SFX motion cues."""
    return [
        {"id": k, **v} for k, v in BUILTIN_SFX_PRESETS.items()
    ]


def search_freesound(query: str, page_size: int = 5) -> List[Dict[str, Any]]:
    """Search Freesound.org API for royalty-free sound effects (requires FREESOUND_API_KEY)."""
    api_key = os.getenv("FREESOUND_API_KEY")
    if not api_key:
        return []

    params = {
        "query": query,
        "token": api_key,
        "page_size": str(page_size),
        "fields": "id,name,duration,previews,license,username",
        "filter": "license:\"Creative Commons 0\" OR license:\"Attribution\""
    }
    url = f"{FREESOUND_API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "AudioToVideo/2.0 (SFXManager)"})

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = []
        for item in data.get("results", []):
            previews = item.get("previews") or {}
            results.append({
                "id": str(item.get("id")),
                "name": item.get("name"),
                "duration_s": item.get("duration"),
                "download_url": previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3"),
                "license": item.get("license"),
                "author": item.get("username")
            })
        return results
    except Exception as e:
        print(f"[SFXManager] Freesound search error: {e}")
        return []


def ensure_sfx_asset(sfx_id: str, target_dir: str | Path) -> Optional[Path]:
    """Ensure a specified SFX preset exists in target directory."""
    preset = BUILTIN_SFX_PRESETS.get(sfx_id.lower())
    if not preset:
        return None

    dest = Path(target_dir) / preset["filename"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    if not dest.exists():
        # Write clean synthesized silent fallback WAV header if not present on disk
        dest.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    
    return dest
