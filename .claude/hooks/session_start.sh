#!/usr/bin/env bash
# SessionStart hook: injects a compact project status into Claude's context
# on startup, resume, /clear and after compaction. Keep the output short.
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT" || exit 0

echo "=== Wasla project context (auto-loaded by SessionStart hook) ==="
echo "Branch: $(git branch --show-current 2>/dev/null)  |  Uncommitted files: $(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
echo
echo "--- Recent commits ---"
git log --oneline -5 2>/dev/null
echo
if [ -f progress/STATUS.md ]; then
  echo "--- progress/STATUS.md ---"
  head -n 60 progress/STATUS.md
  echo
fi
echo "--- Task tracker ---"
python3 tools/progress/tasks.py brief 2>/dev/null || echo "(tracker unavailable: run python3 tools/progress/tasks.py sync)"
echo
LAST_LOG=$(ls -1 progress/sessions/*.md 2>/dev/null | grep -v README | sort | tail -n 1)
if [ -n "${LAST_LOG:-}" ]; then
  echo "--- Last session log: $LAST_LOG (section 'Next') ---"
  awk '/^## Next/{f=1;next} /^## /{f=0} f' "$LAST_LOG" | head -n 20
  echo
fi
echo "Start with the 'resume' skill. Source of truth: AGENTS.md -> integration/prd/*.md -> progress/."
exit 0
