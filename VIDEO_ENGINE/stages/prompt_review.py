"""python -m backend.prompt_review context <id> <n>        -> the approved scene context a regeneration of prompt n must follow (JSON)
   python -m backend.prompt_review set <id> <n> "<text>"    -> save the newly generated English prompt for n (history keeps the old text; other prompts and approvals stay)
Used by the /regen command (.claude/commands/regen.md); the app's own writer is promptgen.py."""
import json
import sys

from . import config, review


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")                   # the narration is Telugu; the Windows console default cannot print it
    if len(argv) < 3 or argv[0] not in ("context", "set"):
        print(__doc__)
        return 2
    pdir = config.project_dir(argv[1])
    try:
        if argv[0] == "context":
            print(json.dumps(review.scene_context(pdir, int(argv[2])), ensure_ascii=False, indent=1))
        else:
            if len(argv) < 4:
                print("missing the new prompt text")
                return 2
            p = review.set_generated(pdir, int(argv[2]), argv[3])
            print(f"prompt {p['n']} saved ({len(p['text'])} characters); prompts.txt rewritten")
    except review.ReviewError as e:
        print(f"error: {e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
