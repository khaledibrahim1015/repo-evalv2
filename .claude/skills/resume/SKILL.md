---
name: resume
description: Rebuild working state at the start of a session, after /clear or compaction, or whenever unsure what to do next in the Wasla project. Reads progress files and the task tracker, verifies them against git, and picks the next task.
---

# Resume

Goal: know exactly where the project stands in a few minutes, using files — not memory.

## Steps

1. **Read the injected context.** The SessionStart hook already printed branch, recent commits, `shared/progress/STATUS.md`, the tracker brief and the last session's "Next" section. Do not re-read those files in full unless something is unclear.

2. **Check consistency with git.**
   - `git status --short` — uncommitted work from a previous session? If yes, inspect it (`git diff --stat`) and decide with the user whether to finish, commit or discard. Never discard without asking.
   - If a task is `in_progress` in the tracker, read its last note and the last session log section for it.

3. **Sync the tracker if the plan changed.** If `integration/prd/04-delivery-plan.md` changed in recent commits (`git log -3 --stat -- integration/prd/04-delivery-plan.md`), run `python3 shared/tools/progress/tasks.py sync`.

4. **Pick the task.**
   - An `in_progress` task comes first.
   - Otherwise the first entry of `python3 shared/tools/progress/tasks.py next`.
   - If the user named a task or goal, use that; if it conflicts with dependencies, say so before starting.
   - Human/business tasks (kind `human`) are not coded. Ask the user whether they are done (`tasks.py external <ID> --note ...`) or skip past them.

5. **State the plan in two or three lines** to the user: task ID, what will be built, which docs/sections you will read. Then continue with the `implement-task` skill.

## Rules
- Do not read whole PRD documents during resume. Load task-specific sections later.
- If STATUS.md and the tracker disagree, the tracker wins for task status; fix STATUS.md at handoff.
- If anything in shared/progress/ looks wrong or missing, say so and repair it (STATUS.md, session log) before coding.
