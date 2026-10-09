#!/usr/bin/env python3
"""Stop hook: if code changed since progress/ was last updated, block the stop once
and ask Claude to run the `handoff` skill. Never blocks twice in a row."""
import json
import os
import subprocess
import sys

root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


try:
    payload = json.load(sys.stdin)
except Exception:
    payload = {}
if payload.get("stop_hook_active"):
    sys.exit(0)

IGNORED = ("progress/",)
dirty = [line[3:] for line in git("status", "--porcelain").splitlines() if len(line) > 3]
dirty_code = [p for p in dirty if not p.startswith(IGNORED)]
dirty_progress = [p for p in dirty if p.startswith("progress/")]

last_progress = int(git("log", "-1", "--format=%ct", "--", "progress") or 0)
last_code = int(git("log", "-1", "--format=%ct", "--", ".", ":(exclude)progress") or 0)
committed_unrecorded = last_code > last_progress

if dirty_progress:
    sys.exit(0)
if dirty_code or committed_unrecorded:
    reason = []
    if dirty_code:
        reason.append(f"{len(dirty_code)} uncommitted file(s) outside progress/")
    if committed_unrecorded:
        reason.append("commits after the last progress/ update")
    print(
        "Progress is not recorded (" + "; ".join(reason) + "). Before stopping, run the `handoff` skill: "
        "update task statuses with tools/progress/tasks.py, update progress/STATUS.md, write a session log in "
        "progress/sessions/, and commit. If this turn changed nothing worth recording, add one line to the "
        "latest session log saying so and commit it.",
        file=sys.stderr,
    )
    sys.exit(2)
sys.exit(0)
