"""Tick a task: python scripts/update_status.py "<task name>" [done|todo]"""
import difflib, json, sys
from datetime import datetime
from pathlib import Path

F = Path(__file__).resolve().parent.parent / "STATUS.json"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    name, val = sys.argv[1].lower(), (sys.argv[2] if len(sys.argv) > 2 else "done") == "done"
    d = json.loads(F.read_text(encoding="utf-8"))
    hits = [t for m in d["milestones"] for t in m["tasks"] if t["name"].lower() == name]
    if not hits:
        names = [t["name"] for m in d["milestones"] for t in m["tasks"]]
        sys.exit(f"Unknown task. Closest: {difflib.get_close_matches(sys.argv[1], names, 5, 0.3)}")
    for t in hits:  # same name may exist in several milestones; tick the first not-yet-set one
        if t["done"] != val:
            t["done"] = val
            break
    for m in d["milestones"]:
        n = sum(t["done"] for t in m["tasks"])
        m["status"] = "done" if n == len(m["tasks"]) else "doing" if n else "todo"
    d["updated"] = datetime.now().strftime("%Y-%m-%dT%H:%M")
    F.write_text(json.dumps(d, indent=1), encoding="utf-8")
    print("ok")


main()
