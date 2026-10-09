---
name: handoff
description: Record progress so the next session (or a fresh context after /clear) can continue without this conversation. Use at the end of every session, before /clear, when context is getting large, or when the Stop hook says progress is not recorded.
---

# Handoff

The next session knows only what is in the repository. Write it down.

## Steps

1. **Tracker** — every task touched this session has the right status:
   `python3 tools/progress/tasks.py done|note|block <ID> --note "..."`.

2. **Session log** — create or update `progress/sessions/YYYY-MM-DD-<short-topic>.md` (date in UTC) using this template:
   ```markdown
   # <date> — <topic>

   ## Done
   - T<ID>: <what was built> (<key files>)

   ## Decisions
   - <decision> → <where recorded: ADR-0xx / doc section>

   ## Problems / open questions
   - <issue, what was tried, what is needed>

   ## Next
   1. <the very next concrete step, with task ID and the file to open first>
   2. ...
   ```
   Keep it short and factual. The "Next" section is printed automatically at the next session start.

3. **STATUS.md** — update `progress/STATUS.md` (keep under ~60 lines): current phase, task in progress, last completed tasks, open blockers, open questions for the user, pointer to the latest session log. Remove stale lines instead of appending forever.

4. **Docs** — if behavior or decisions changed and docs are not yet updated, do it now (or run `record-decision`).

5. **Commit** — `git add progress/ <other changed files>` and commit: `progress: <summary>` (or include it in the last task commit). Push only if the user or environment asks for it.

6. **Tell the user** in two or three lines: what was done, what is next, anything they must decide or do (e.g., human tasks).

## Rules
- Never record something as done that was not verified.
- Never put secrets, customer data or credentials in progress files.
- If nothing changed in this turn, add one line to the latest session log saying so and commit; this satisfies the Stop hook.
