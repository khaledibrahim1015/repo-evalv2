---
name: implement-task
description: Implement one task from the Wasla delivery plan (IDs like T0.2.1, T1.5.7) end to end - load only the relevant spec sections, plan, build inside the right module, test, review, and record progress. Use whenever writing code for a planned task.
---

# Implement a task

## 1. Load the task (small context)
```
python3 tools/progress/tasks.py show <ID>
python3 tools/progress/tasks.py start <ID>
```
- Dependencies not done? Stop and tell the user which ones; do not build on missing foundations.
- Read the task row and its epic in `integration/prd/04-delivery-plan.md` (`grep -n "<ID>"`, then read that epic only).
- For each service id (Sxx) on the task: read only that section of `integration/prd/03-services.md`.
- Read the parts of `integration/prd/05-tech-stack.md` that apply (deployable in §2, language libraries in §4, layout in §13).
- Read architecture flows only if the task implements one (`02-architecture.md` §5) and the ADRs it touches (§15).
- For larger lookups, ask the `spec-guardian` subagent instead of reading many sections yourself.

## 2. Plan
- Small task (< ~2 files, obvious): write a short plan in your reply.
- Otherwise: use the `task-planner` subagent with the task ID; review its plan; adjust.
- The plan must name: files to create/change, module and deployable, contracts/events, migrations, tests, what is out of scope.
- If the task is ambiguous or a doc contradicts another, ask the user rather than guessing. If a decision is made, use `record-decision`.

## 3. Build
- Stay inside the module(s) of the task. New module? Use `new-module`.
- Follow AGENTS.md §6 (definition of done) and §7 (engineering rules).
- Commit in small, working steps: `T<ID>: <summary>`.
- If the task is too big for one session, split it: finish a coherent slice, record what remains in a tracker note and the session log.

## 4. Verify
- Run the tests and linters for what you touched (after T0.2.1: `task test`, `task lint`; before that, the toolchain directly). Report real results; never claim tests pass without running them.
- Use `code-reviewer` on the diff. Use `security-reviewer` when the change touches auth, tenancy/RLS, KMS/secrets, PII, Edge Agent, sandbox or LLM inputs.
- Fix findings or record why not.

## 5. Record
```
python3 tools/progress/tasks.py done <ID> --note "<what was built, key files, follow-ups>"
```
- Partial work: `tasks.py note <ID> --note "..."` and keep it `in_progress`.
- Blocked: `tasks.py block <ID> --note "<reason, what is needed>"`.
- Then run `handoff` if the session is ending, or continue with the next task if context is still small.
