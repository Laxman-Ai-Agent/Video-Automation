"""python -m backend.validate projects/demo  -> validates every JSON that exists; short errors."""
import sys
from pathlib import Path

from pydantic import ValidationError

from . import config
from .models import Composition, Cuts, PromptsMap, ScenePlan
from .transcribe import Transcript

FILES = {
    "transcript.json": Transcript, "cuts.json": Cuts, "scene_plan.json": ScenePlan,
    "prompts_map.json": PromptsMap, "composition.json": Composition,
}


def validate_project(pdir: Path) -> list[str]:
    errs: list[str] = []
    for name, model in FILES.items():
        f = pdir / name
        if not f.exists():
            continue
        try:
            model.model_validate_json(f.read_text(encoding="utf-8"))
        except ValidationError as e:
            for x in e.errors()[:8]:
                errs.append(f"{name}: {'.'.join(str(p) for p in x['loc'])}: {x['msg']}")
        except ValueError as e:
            errs.append(f"{name}: {e}")
    return errs


if __name__ == "__main__":
    pdir = config.project_dir(sys.argv[1])
    errs = validate_project(pdir)
    print("\n".join(errs) if errs else "validate: OK")
    sys.exit(1 if errs else 0)
