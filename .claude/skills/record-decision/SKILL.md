---
name: record-decision
description: Apply a product or architecture decision consistently across the Wasla docs, ADR log and task tracker. Use whenever the user makes, changes or reverses a decision (stack, scope, priority, phase, service design), so no document contradicts another.
---

# Record a decision

Decisions in this project change often. A decision is only real when every affected document agrees.

## Steps

1. **Restate the decision** in one sentence and confirm it with the user if there is any doubt about scope (which phase, which services).

2. **Find every affected place** (use `spec-guardian` for a wide search, or grep):
   ```
   grep -n -i "<keyword>" integration/prd/*.md AGENTS.md .claude/skills/*/SKILL.md
   ```
   Typical places: PRD (§2.2 priorities, §7 requirements with P0/P1/P2, §11 release plan), architecture (principles, diagrams, stores, flows, §15 ADRs), services (responsibilities, phase lines), delivery plan (tasks, exit criteria, deferred backlog), tech stack (tables, §14 "not in the stack"), AGENTS.md §3.

3. **Edit them all.** Keep wording consistent; remove the old option rather than leaving both.

4. **ADR** — add or amend a row in `integration/prd/02-architecture.md` §15 (`ADR-0NN | decision and why`). Keep ADR numbers in order.

5. **Tracker** — if `04-delivery-plan.md` changed: `python3 shared/tools/progress/tasks.py sync` and check `tasks.py brief`. Tasks removed from the plan become `skipped` automatically.

6. **AGENTS.md §3** — update the "decisions already made" list if the decision belongs there.

7. **Log and commit** — add the decision under "Decisions" in the current session log; commit with `docs: <decision>`.

8. **Verify** — grep again for the old option; nothing should still describe it as current.
