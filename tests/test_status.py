"""STATUS.json bookkeeping: a milestone is done/doing/todo exactly according to its tasks.
(This cannot detect a task that was finished but never ticked; it catches inconsistent files and typos.)"""
import json
from pathlib import Path

STATUS = json.loads((Path(__file__).resolve().parent.parent / "STATUS.json").read_text(encoding="utf-8"))


def test_milestone_status_matches_its_tasks():
    for m in STATUS["milestones"]:
        done = sum(t["done"] for t in m["tasks"])
        expected = "done" if done == len(m["tasks"]) else "doing" if done else "todo"
        assert m["status"] == expected, f'{m["id"]}: status {m["status"]} but {done}/{len(m["tasks"])} tasks done'


def test_milestones_are_finished_in_order():
    """No milestone may be started while an earlier one has not even begun (M0..M9 are built in order)."""
    states = [m["status"] for m in STATUS["milestones"]]
    first_todo = states.index("todo") if "todo" in states else len(states)
    assert all(s == "todo" for s in states[first_todo:]), states


def test_task_names_are_unique_within_a_milestone():
    for m in STATUS["milestones"]:
        names = [t["name"].lower() for t in m["tasks"]]
        assert len(names) == len(set(names)), m["id"]
