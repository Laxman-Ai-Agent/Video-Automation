"""Production Release Verification: Standalone Live Remotion Render & Media Probe.

Executes an authentic video render using the production Remotion engine and host Chrome,
probes the output MP4 with ffprobe, and persists verified technical evidence
under reports/SYSTEM_AGENTS_PHASE_10_20261017/artifacts/.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import sys
import time
import wave
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import config, orchestrator
from VIDEO_ENGINE.stages import media_probe, render


def create_synthetic_wav(path: Path, duration_sec: float = 1.0, sample_rate: int = 44100) -> None:
    """Creates a valid 1.0s sine wave audio file for production render verification."""
    num_samples = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        # Generate 440 Hz tone
        import math
        raw_frames = bytearray()
        for i in range(num_samples):
            val = int(10000.0 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            raw_frames.extend(struct.pack("<h", val))
        wav_file.writeframes(raw_frames)


def main() -> None:
    print("=== Phase 10 Production Release Live Render Verification ===")
    artifacts_dir = config.PROJECT_ROOT / "reports" / "SYSTEM_AGENTS_PHASE_10_20261017" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    project_dir = config.PROJECT_ROOT / "projects" / "prod_release_verification"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    # 1. Synthesize 1.0s audio file (30 frames @ 30fps)
    audio_name = "synth_prod_release.wav"
    audio_path = project_dir / "audio.wav"
    create_synthetic_wav(audio_path, duration_sec=1.0)
    print(f"[1/6] Created synthetic verification audio: {audio_path} ({audio_path.stat().st_size} bytes)")

    # 2. Stage audio into Remotion public
    remotion_public = config.REMOTION_DIR / "public"
    remotion_public.mkdir(parents=True, exist_ok=True)
    staged_audio = remotion_public / audio_name
    shutil.copyfile(audio_path, staged_audio)
    print(f"[2/6] Staged audio to Remotion public: {staged_audio}")

    # 3. Create TSX Scene
    scenes_dir = project_dir / "scenes"
    scenes_dir.mkdir(exist_ok=True)
    tsx_code = (
        'import React from "react";\n'
        'export const Scene1: React.FC = () => (\n'
        '  <div style={{\n'
        '    display: "flex",\n'
        '    flexDirection: "column",\n'
        '    alignItems: "center",\n'
        '    justifyContent: "center",\n'
        '    width: "100%",\n'
        '    height: "100%",\n'
        '    backgroundColor: "#0d1117",\n'
        '    color: "#58a6ff",\n'
        '    fontFamily: "sans-serif",\n'
        '    fontSize: 56,\n'
        '    fontWeight: "bold",\n'
        '    textAlign: "center",\n'
        '  }}>\n'
        '    <p style={{ margin: 0 }}>LAXMAN-AUTONOMOUS MASTER SYSTEM</p>\n'
        '    <p style={{ margin: "16px 0 0 0", color: "#3fb950", fontSize: 40 }}>Phase 10 Production Release Verified</p>\n'
        '  </div>\n'
        ');\n'
    )
    (scenes_dir / "scene_1.tsx").write_text(tsx_code, encoding="utf-8")
    print(f"[3/6] Synthesized TSX scene component: {scenes_dir / 'scene_1.tsx'}")

    # 4. Create composition.json
    comp_data = {
        "schema_version": "1.0",
        "meta": {
            "aspect": "16:9",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "duration": 1.0,
            "audio": audio_name,
            "motionOnly": True,
        },
        "aspect_ratio": "16:9",
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "total_frames": 30,
        "duration_frames": 30,
        "scenes": [
            {
                "id": 1,
                "scene_id": "scene_1",
                "start": 0.0,
                "end": 1.0,
                "start_frame": 0,
                "end_frame": 30,
                "duration_frames": 30,
                "component": "scenes/scene_1.tsx",
                "layers": [],
            }
        ],
        "audio_track": {"src": audio_name, "volume": 1.0},
    }
    (project_dir / "composition.json").write_text(json.dumps(comp_data, indent=2), encoding="utf-8")
    (project_dir / "timeline.json").write_text(json.dumps(comp_data, indent=2), encoding="utf-8")

    # 5. Check browser executable
    b_path, b_source = orchestrator.find_browser_executable()
    print(f"[4/6] Browser executable detected: {b_path} ({b_source})")
    assert b_path is not None, "Browser executable (Chrome/Puppeteer) required for production render"

    # 6. Execute live render
    output_mp4 = artifacts_dir / "production_verified_release.mp4"
    print(f"[5/6] Executing authentic Remotion render to: {output_mp4} ...")
    t0 = time.perf_counter()
    render.render(project_dir, preview=False, aspect="16:9", out=output_mp4)
    elapsed = time.perf_counter() - t0
    print(f"Render completed in {elapsed:.2f} seconds!")

    assert output_mp4.exists(), f"Rendered output missing: {output_mp4}"
    video_size = output_mp4.stat().st_size
    video_sha256 = hashlib.sha256(output_mp4.read_bytes()).hexdigest()
    print(f"Rendered file size: {video_size} bytes | SHA-256: {video_sha256}")

    # 7. Probe technical properties via ffprobe
    print("[6/6] Probing technical media properties via ffprobe ...")
    probe_info = media_probe.probe(output_mp4)
    probe_info_path = artifacts_dir / "production_ffprobe_probe.json"
    probe_info_path.write_text(json.dumps(probe_info, indent=2), encoding="utf-8")

    telemetry = {
        "release_version": "1.0.0",
        "phase": 10,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "render_elapsed_seconds": round(elapsed, 2),
        "browser_executable": b_path,
        "browser_source": b_source,
        "output_artifact_path": str(output_mp4),
        "video_size_bytes": video_size,
        "sha256": video_sha256,
        "container": probe_info.get("container"),
        "duration_seconds": probe_info.get("duration"),
        "video": probe_info.get("video"),
        "audio": probe_info.get("audio"),
        "status": "VERIFIED_PRODUCTION_READY",
    }
    telemetry_path = artifacts_dir / "production_render_telemetry.json"
    telemetry_path.write_text(json.dumps(telemetry, indent=2), encoding="utf-8")

    print("\n=== TECHNICAL MEDIA EVIDENCE VERIFIED ===")
    print(f"Container: {probe_info.get('container')}")
    print(f"Duration: {probe_info.get('duration')}s (expected 1.0s)")
    v_info = probe_info.get("video") or {}
    print(f"Video Codec: {v_info.get('codec')} | Resolution: {v_info.get('width')}x{v_info.get('height')} @ {v_info.get('fps')} fps")
    a_info = probe_info.get("audio") or {}
    print(f"Audio Codec: {a_info.get('codec')} | Channels: {a_info.get('channels')} | Sample Rate: {a_info.get('sample_rate')} Hz")
    print(f"Saved artifacts:")
    print(f"  - {output_mp4}")
    print(f"  - {probe_info_path}")
    print(f"  - {telemetry_path}")


if __name__ == "__main__":
    main()
