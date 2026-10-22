"""python -m backend.cli <command> <project> [options]   (argument parsing + dispatch only; logic is in pipeline.py)
  new <id> --audio <file>   create projects/<id>
  transcribe <id>           Whisper transcript + cut points
  plan-input <id>           translate_input.txt (and plan_input.txt once /plan wrote translation.json)
  prompts <id>              write prompts.txt and show where to put the images
  build <id> [--preview] [--no-render] [--aspect 9:16]   Motion Planning, Motion Generation, render
                            (--aspect 9:16 also makes the vertical video out_9x16.mp4; 16:9 stays the default)
  check <id> [--aspect 9:16]  pre-render validation: empty slots, crops, duplicates, timeline, safe areas (prerender_report.json)
  status <id>               files, job step, timings"""
import argparse
import sys
from pathlib import Path

from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter as pipeline
from VIDEO_ENGINE.pipeline.legacy_pipeline_adapter import CHAINS, Ctx, StepError

from . import config


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="backend.cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new")
    p.add_argument("id")
    p.add_argument("--audio", required=True)
    for c in ("transcribe", "plan-input", "prompts", "status"):
        sub.add_parser(c).add_argument("id")
    b = sub.add_parser("build")
    b.add_argument("id")
    b.add_argument("--preview", action="store_true", help="quick preview: half size (960x540), full frame rate")
    b.add_argument("--no-render", action="store_true")
    b.add_argument("--aspect", choices=("16:9", "9:16"), default="16:9", help="9:16 = vertical 1080x1920 video (out_9x16.mp4)")
    k = sub.add_parser("check")
    k.add_argument("id")
    k.add_argument("--aspect", choices=("16:9", "9:16"), default="16:9")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    try:
        if a.cmd == "new":
            print(f"created {pipeline.new_project(a.id, Path(a.audio))}")
            return 0
        pdir = config.PROJECTS_DIR / a.id
        if not pdir.exists():
            raise StepError(f"project {a.id} does not exist - run: python -m backend.cli new {a.id} --audio <file>")
        if a.cmd == "status":
            print(pipeline.status(pdir))
        elif a.cmd == "check":
            from VIDEO_ENGINE.stages import prerender_checks as pc
            if not pc.comp_file(pdir, a.aspect).exists():
                raise StepError(f"{pc.comp_file(pdir, a.aspect).name} does not exist yet - run /plan and the build first")
            rep = pc.check(pdir, a.aspect)
            pc.write_report(pdir, rep)
            print(pc.format_text(rep))
            return 2 if rep.errors else 0
        elif a.cmd == "build":
            label = ("build-preview" if a.preview else "build") + ("-9x16" if a.aspect == "9:16" else "")
            names = pipeline.chain_for(pdir, label)
            pipeline.run_chain(pdir, names[:-1] if a.no_render else names, label,
                               Ctx(preview=a.preview))
        else:
            pipeline.run_chain(pdir, CHAINS[a.cmd], a.cmd)
        return 0
    except StepError as e:
        print(f"\n{e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrupted - finished steps are kept; re-run the same command to resume", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
