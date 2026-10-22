"""store.read_info / write_info under concurrent threads (the API status polling and the job threads of one server process).
On Windows os.replace makes a concurrent read of project.json raise PermissionError; the per-project lock in backend/store.py must prevent that."""
import json
import os
import sys
import threading
import time

import pytest

from backend import store


def hammer(pdir, seconds, read=store.read_info, write=store.write_info):
    errors, reads, stop = [], [0], time.monotonic() + seconds

    def reader():
        while time.monotonic() < stop:
            try:
                assert read(pdir)["id"] == "p"
                reads[0] += 1
            except Exception as e:                               # PermissionError, JSONDecodeError, ...
                errors.append(repr(e))

    def writer(n):
        i = 0
        while time.monotonic() < stop:
            i += 1
            try:
                write(pdir, {"id": "p", "state": f"w{n}-{i}", "pad": "x" * 2000})
            except Exception as e:
                errors.append(repr(e))

    ts = [threading.Thread(target=reader) for _ in range(6)] + [threading.Thread(target=writer, args=(n,)) for n in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return errors, reads[0]


def unlocked_read(pdir):
    return json.loads((pdir / "project.json").read_text(encoding="utf-8"))


def unlocked_write(pdir, info):
    tmp = pdir / "project.json.tmp"
    tmp.write_text(json.dumps(info, indent=1), encoding="utf-8")
    os.replace(tmp, pdir / "project.json")


def test_concurrent_reads_and_writes_never_fail_and_never_see_a_half_written_file(tmp_path):
    store.write_info(tmp_path, {"id": "p", "state": "start"})
    errors, reads = hammer(tmp_path, 2.0)
    assert errors == [] and reads > 100
    assert store.read_info(tmp_path)["id"] == "p" and not (tmp_path / "project.json.tmp").exists()


def test_set_state_calls_do_not_lose_the_other_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(store.config, "PROJECTS_DIR", tmp_path.parent)
    store.write_info(tmp_path, {"id": "p", "name": "keep", "state": "created"})
    ts = [threading.Thread(target=lambda n=n: [store.set_state(tmp_path.name, f"s{n}") for _ in range(50)]) for n in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    info = store.read_info(tmp_path)
    assert info["name"] == "keep" and info["state"].startswith("s")


@pytest.mark.skipif(sys.platform != "win32", reason="the PermissionError on replace is a Windows file-lock behaviour")
def test_the_same_load_without_the_lock_does_fail_on_windows(tmp_path):
    """Proves the test above can fail: the old, unlocked pattern raises PermissionError under the same load."""
    unlocked_write(tmp_path, {"id": "p", "state": "start"})
    errors, _ = hammer(tmp_path, 2.0, read=unlocked_read, write=unlocked_write)
    assert any("PermissionError" in e for e in errors)
