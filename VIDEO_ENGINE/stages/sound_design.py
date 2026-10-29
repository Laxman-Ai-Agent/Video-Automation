"""Sound design (Phase 4): the ONE audio track the render plays. Today a video carries only the narration, quiet (about -21 LUFS); this builds `audio_mix.wav` from
  - the narration (never edited, its length is the video's length),
  - a soft whoosh at every scene transition (synthesised here with ffmpeg, so there is no licence to track),
  - an OPTIONAL licensed music bed (`assets/music/bed.<ext>` + `bed.json` with its source, licence and credit; without that provenance the music is NOT used), ducked under the narration
    with a sidechain compressor, looped / trimmed to the video and faded in and out,
and normalises the result to -14 LUFS (true peak at most -1.5 dBTP) with a two-pass loudnorm. No LLM is involved: every step is ffmpeg and is measured afterwards (`sound_design.json`).
`render.stage_audio` plays the mix instead of the bare narration; the render fingerprint carries `inputs()`, so a change of the mix renders again."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from VIDEO_ENGINE.ffmpeg import media_probe

from . import config

VERSION = 1                       # bump when the mix changes (part of the render fingerprint)
FPS = 30
SAMPLE_RATE = 48000
TARGET_LUFS, TRUE_PEAK_DB, TARGET_LRA = -14.0, -1.5, 11.0
LOUDNESS_TOLERANCE = 1.0          # LU: the measured result must be this close to the target, else the build fails with the numbers
WHOOSH_S = 0.7
WHOOSH_LEAD_S = 0.3               # the whoosh starts this long before the cut, so its swell peaks at the cut
WHOOSH_DB = -12.0
MUSIC_DB = -22.0
MUSIC_FADE_IN_S, MUSIC_FADE_OUT_S = 2.0, 3.0
DUCK = "sidechaincompress=threshold=0.02:ratio=10:attack=15:release=500"
FFMPEG_TIMEOUT_S = 300
MUSIC_EXTS = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac")
REPORT = "sound_design.json"
MIX = "audio_mix.wav"


class SoundDesignError(Exception):
    """The mix could not be built or did not measure as intended (the message says why)."""


def _ffmpeg(args: list[str]) -> str:
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=FFMPEG_TIMEOUT_S, creationflags=config.LOW_PRIORITY)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise SoundDesignError(f"ffmpeg did not finish: {e}") from e
    if r.returncode != 0:
        raise SoundDesignError(f"ffmpeg failed: {(r.stderr or '').strip()[-400:]}")
    return r.stderr or ""


def _loudness(path: Path, extra: str = "") -> dict:
    """Measure a file with loudnorm (print_format json): input_i (LUFS), input_tp (dBTP), input_lra, input_thresh, target_offset."""
    out = _ffmpeg(["-i", str(path), "-af", f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK_DB}:LRA={TARGET_LRA}:print_format=json{extra}", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", out, re.S)
    if not m:
        raise SoundDesignError("ffmpeg gave no loudness measurement")
    d = json.loads(m.group(0))
    return {k: float(v) for k, v in d.items() if k in ("input_i", "input_tp", "input_lra", "input_thresh", "output_i", "output_tp", "target_offset")}


def music_bed(pdir: Path) -> tuple[Path | None, dict | None, str]:
    """(file, provenance, why not): the licensed music bed of the project, only when its provenance is complete and its rights are known to allow commercial use."""
    folder = pdir / "assets" / "music"
    f = next((p for p in sorted(folder.glob("bed.*")) if p.suffix.lower() in MUSIC_EXTS), None) if folder.is_dir() else None
    if f is None:
        return None, None, "no music bed (assets/music/bed.<ext>)"
    try:
        prov = json.loads((folder / "bed.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None, "the music bed has no readable bed.json (source, licence, credit): not used"
    if not (prov.get("source_url") and prov.get("license_name") and prov.get("attribution_text")) or prov.get("commercial_use_known") is not True:
        return None, None, "the music bed's provenance is incomplete or its licence is not known to allow commercial use: not used"
    return f, prov, ""


def transition_times(pdir: Path, aspect: str = "16:9") -> list[float]:
    """Seconds of every supported scene cut of the approved timeline (a transition's boundary frame / fps)."""
    f = pdir / f"timeline{'_9x16' if aspect == '9:16' else ''}.json"
    try:
        tl = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return sorted({round(t["boundary_frame"] / FPS, 3) for t in tl.get("transitions", []) if t.get("supported", True) and t.get("boundary_frame") is not None})


def _settings(pdir: Path, aspect: str) -> str:
    """The version and constants of the mix, the transition times and the music bed's provenance, as one string."""
    _, prov, _ = music_bed(pdir)
    return json.dumps([VERSION, TARGET_LUFS, TRUE_PEAK_DB, WHOOSH_DB, MUSIC_DB, DUCK, transition_times(pdir, aspect), prov], sort_keys=True, default=str)


def inputs(pdir: Path, narration: Path, aspect: str = "16:9") -> list:
    """What the mix is made from, for the render fingerprint: its settings, the music bed file and the narration."""
    bed, _, _ = music_bed(pdir)
    return [_settings(pdir, aspect), *([bed] if bed else []), narration]


def fingerprint(pdir: Path, aspect: str = "16:9") -> str:
    """A cheap fingerprint of the sound design for the render STAGE's freshness (no audio is hashed): the settings plus the music file's size and time."""
    bed, _, _ = music_bed(pdir)
    st = bed.stat() if bed else None
    return hashlib.sha256(json.dumps([_settings(pdir, aspect), st and [st.st_size, st.st_mtime_ns]]).encode()).hexdigest()[:16]


def _digest(parts: list) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(media_probe.sha256_file(p).encode() if isinstance(p, Path) else str(p).encode())
        h.update(b"|")
    return h.hexdigest()


def _filter_graph(n_cuts: int, cut_times: list[float], music: bool, duration: float) -> str:
    g = ["[0:a]aresample=%d,aformat=channel_layouts=stereo%s" % (SAMPLE_RATE, ",asplit=2[nar][side]" if music else "[nar]")]
    labels = ["[nar]"]
    nxt = 1
    if n_cuts:
        g.append(f"[{nxt}:a]aformat=channel_layouts=stereo,volume={WHOOSH_DB}dB" + (f",asplit={n_cuts}" + "".join(f"[w{i}]" for i in range(n_cuts)) if n_cuts > 1 else "[w0]"))
        for i, t in enumerate(cut_times):
            ms = max(0, round((t - WHOOSH_LEAD_S) * 1000))
            g.append(f"[w{i}]adelay={ms}|{ms}[d{i}]")
        g.append("".join(f"[d{i}]" for i in range(n_cuts)) + (f"amix=inputs={n_cuts}:normalize=0[sfx]" if n_cuts > 1 else "anull[sfx]"))
        labels.append("[sfx]")
        nxt += 1
    if music:
        fade_out = max(0.0, duration - MUSIC_FADE_OUT_S)
        g.append(f"[{nxt}:a]aloop=loop=-1:size=2147483647,atrim=0:duration={duration:.3f},asetpts=PTS-STARTPTS,aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,volume={MUSIC_DB}dB[m]")
        g.append(f"[m][side]{DUCK}[md]")
        g.append(f"[md]afade=t=in:d={MUSIC_FADE_IN_S},afade=t=out:st={fade_out:.3f}:d={MUSIC_FADE_OUT_S}[mf]")
        labels.append("[mf]")
    g.append("".join(labels) + (f"amix=inputs={len(labels)}:normalize=0:duration=longest" if len(labels) > 1 else "anull") + f",atrim=0:duration={duration:.3f},asetpts=N/SR/TB")
    return ";".join(g)


def build(pdir: Path, narration: Path, aspect: str = "16:9") -> dict:
    """Build `audio_mix.wav` for this project (reused while its inputs are unchanged) and record `sound_design.json`. Raises SoundDesignError with the cause."""
    digest = _digest(inputs(pdir, narration, aspect))
    out, report_file = pdir / MIX, pdir / REPORT
    try:
        old = json.loads(report_file.read_text(encoding="utf-8"))
        if old.get("input_digest") == digest and out.exists():
            return {**old, "reused": True}
    except (OSError, ValueError):
        pass
    t0 = time.time()
    info = media_probe.probe(narration)
    duration = float(info["duration"])
    cuts = [t for t in transition_times(pdir, aspect) if t < duration]
    bed, prov, why_no_music = music_bed(pdir)
    with tempfile.TemporaryDirectory(prefix="sound_design_") as tmp:
        tmp_dir = Path(tmp)
        cmd = ["-i", str(narration)]
        if cuts:
            whoosh = tmp_dir / "whoosh.wav"
            _ffmpeg(["-f", "lavfi", "-i", f"anoisesrc=color=pink:duration={WHOOSH_S}:sample_rate={SAMPLE_RATE}:amplitude=0.6", "-af",
                     f"highpass=f=350,lowpass=f=7000,afade=t=in:d={WHOOSH_S * 0.55:.2f},afade=t=out:st={WHOOSH_S * 0.55:.2f}:d={WHOOSH_S * 0.45:.2f}", "-ac", "2", str(whoosh)])
            cmd += ["-i", str(whoosh)]
        if bed:
            cmd += ["-i", str(bed)]
        raw = tmp_dir / "raw.wav"
        _ffmpeg([*cmd, "-filter_complex", _filter_graph(len(cuts), cuts, bool(bed), duration), "-c:a", "pcm_f32le", "-ar", str(SAMPLE_RATE), str(raw)])
        before = _loudness(raw)
        norm = (f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK_DB}:LRA={TARGET_LRA}:measured_I={before['input_i']}:measured_TP={before['input_tp']}:measured_LRA={before['input_lra']}"
                f":measured_thresh={before['input_thresh']}:offset={before['target_offset']}:linear=true")
        tmp_out = tmp_dir / MIX
        _ffmpeg(["-i", str(raw), "-af", norm, "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", str(tmp_out)])
        after = _loudness(tmp_out)
        mix_len = float(media_probe.probe(tmp_out)["duration"])
        if abs(mix_len - duration) > 1 / FPS:
            raise SoundDesignError(f"the mix is {mix_len:.3f}s long but the narration is {duration:.3f}s: the video would lose sync")
        if abs(after["input_i"] - TARGET_LUFS) > LOUDNESS_TOLERANCE or after["input_tp"] > TRUE_PEAK_DB + 0.5:
            raise SoundDesignError(f"the mix measures {after['input_i']:.1f} LUFS / {after['input_tp']:.1f} dBTP, not {TARGET_LUFS} LUFS / {TRUE_PEAK_DB} dBTP")
        out.write_bytes(tmp_out.read_bytes())
    report = {"version": VERSION, "input_digest": digest, "file": MIX, "narration": narration.name, "duration_s": round(duration, 3), "cuts_s": cuts, "whoosh_db": WHOOSH_DB if cuts else None,
              "music": {"file": bed.name, "provenance": prov, "db": MUSIC_DB, "ducked": True} if bed else None, "music_not_used": None if bed else why_no_music,
              "loudness_before_normalisation": before, "loudness": {"integrated_lufs": after["input_i"], "true_peak_dbtp": after["input_tp"], "lra": after["input_lra"], "target_lufs": TARGET_LUFS},
              "seconds": round(time.time() - t0, 1), "reused": False}
    report_file.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return report


def audio_for_render(pdir: Path, narration: Path) -> Path:
    """The file the render plays: the mix when it exists, else the bare narration (a project whose mix was never built keeps working)."""
    mix = pdir / MIX
    return mix if mix.exists() else narration
