"""Where would a build resume, and why? Read-only: uses the same fingerprint rule as pipeline.execute (inputs + settings + stage-logic version),
the recorded fingerprints (.build_state.json) and the last outcome of every step (timings.json). Nothing is run, written or deleted.
  python -m backend.resume projects/demo [build|build-preview|timeline|match|transcribe ...]
States: fresh (output kept), stale (will run again, with the reason), blocked (an input it needs does not exist), always (cheap check that runs every time)."""
import json
import shutil
import sys
from pathlib import Path

try:
    from backend import config
except ImportError:
    import config

from . import legacy_pipeline_adapter as pipeline

try:
    from VIDEO_ENGINE.stages.fingerprint import versioned
except ImportError:
    from backend.fingerprint import versioned


def _read(pdir: Path, name: str, default):
    f = pdir / name
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default
    except ValueError:
        return default                       # a damaged state file means "nothing is known": every step then shows as stale, never as fresh


def state(pdir: Path, names, ctx: pipeline.Ctx | None = None) -> list[dict]:
    ctx = ctx or pipeline.Ctx()
    known = _read(pdir, ".build_state.json", {}).get("fingerprints", {})
    last = _read(pdir, "timings.json", {}).get("steps", {})
    rows = []
    for n in names:
        st = pipeline.STEPS[n]
        row = {"step": n, "state": "fresh", "reason": "inputs unchanged, output kept", "last": last.get(n, {}).get("status") or None}
        missing_tools = [t for t in st.tools if shutil.which(t) is None]
        missing = [r for r in st.requires if not list(pdir.glob(r))]
        if missing_tools or missing:
            row.update(state="blocked", reason=("missing tools on PATH: " + ", ".join(missing_tools)) if missing_tools else f"missing {', '.join(missing)} - {st.hint}")
        else:
            try:
                fp = versioned(n, st.fingerprint(pdir, ctx) if st.fingerprint else None)
            except Exception as e:           # the inputs cannot even be read: that is a reason to run (and see the real error), not to skip
                row.update(state="stale", reason=f"its inputs could not be read ({type(e).__name__})")
                rows.append(row)
                continue
            outs = st.outputs(pdir)
            if not outs or fp is None:
                row.update(state="always", reason="a quick check that runs every time")
            elif not all(o.exists() for o in outs):
                row.update(state="stale", reason="its output is missing")
            elif n not in known:
                row.update(state="stale", reason="it was never recorded as finished")
            elif known[n] != fp:
                row.update(state="stale", reason="its inputs or settings changed since the last successful run")
            if row["state"] == "fresh" and row["last"] in ("failed", "stopped"):
                row.update(state="stale", reason=f"its last run {row['last']}")
        rows.append(row)
    first = resume_point(rows)
    if first:                                # what comes after the first step that must run is only fresh relative to OLD data: it is checked again once that step has run
        after = rows.index(first) + 1
        for r in rows[after:]:
            if r["state"] == "fresh":
                r.update(state="recheck", reason=f"'{first['step']}' runs first and may change what this step reads")
    return rows


def resume_point(rows: list[dict]) -> dict | None:
    """The first step that is not fresh and not a quick always-run check: where a build starts doing real work again."""
    return next((r for r in rows if r["state"] in ("stale", "blocked")), None)


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    names = pipeline.CHAINS.get(sys.argv[2] if len(sys.argv) > 2 else "build", None) or sys.argv[2:]
    rows = state(pdir, names)
    for r in rows:
        print(f"{r['step']:<20} {r['state']:<8} {r['reason']}" + (f"  (last run: {r['last']})" if r["last"] else ""))
    p = resume_point(rows)
    print("resume at:", p["step"] if p else "nothing to do (everything is fresh)")
