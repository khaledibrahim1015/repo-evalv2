#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write|MultiEdit|NotebookEdit): block edits to secrets and to the
generated task state, which must change only through shared/tools/progress/tasks.py."""
import json
import os
import re
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)
path = (payload.get("tool_input") or {}).get("file_path") or (payload.get("tool_input") or {}).get("notebook_path") or ""
rel = os.path.relpath(path, os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()) if path else ""
name = os.path.basename(path)

rules = [
    (re.compile(r"^\.env(\..+)?$"), lambda n: not n.endswith((".example", ".sample", ".template")),
     "secret env file; edit the matching .env.example instead and keep real secrets out of git"),
    (re.compile(r".*\.(pem|key|p12|pfx|jks)$"), lambda n: True, "key/certificate material must never be written by the agent"),
]
for pattern, cond, why in rules:
    if pattern.match(name) and cond(name):
        print(f"Blocked edit to {rel}: {why}.", file=sys.stderr)
        sys.exit(2)
if rel.replace(os.sep, "/") in ("shared/progress/tasks.json",):
    print("Blocked: shared/progress/tasks.json is managed by shared/tools/progress/tasks.py "
          "(use sync/start/done/block/external/note).", file=sys.stderr)
    sys.exit(2)
if rel.replace(os.sep, "/").startswith("secrets/"):
    print(f"Blocked edit to {rel}: secrets/ is off-limits.", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
