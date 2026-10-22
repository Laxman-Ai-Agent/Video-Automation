Run milestone $ARGUMENTS in autopilot. Do not ask for permission or confirmation.

1. Read CLAUDE.md (already loaded) and docs/$ARGUMENTS.md only.
2. For each task in STATUS.json for this milestone, in order:
   a. Implement it (small, focused changes).
   b. Verify: run its test/command (tsc, pytest, render, script). Read only errors and the last 10 lines.
   c. If it passes: `python scripts/update_status.py "<task>" done` (before M0 creates it, edit that one task's flag),
      then `git add -A` and `git commit -m "$ARGUMENTS: <task>"`. Continue immediately to the next task.
   d. If it fails: fix and retry, max 3 attempts. Then STOP and report the error (last 10 lines) and your diagnosis.
3. Stop only when: the milestone is finished, a task fails 3 times, a required input is missing
   (audio, images, user decision), a visual review is needed, or a package is not installed.
4. At the end reply in Telugu in under 10 lines: tasks done, anything pending, test results,
   which model to switch to for the next milestone, and "run /clear then /go <next>".
Never: delete files, read .env, push to git, install packages without asking, view images.
