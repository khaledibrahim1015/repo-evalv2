---
name: phase-gate
description: Check whether a Wasla delivery phase (0-5) can close - task completion, exit criteria with evidence, and the phase gate checklist - and produce a gate report. Use when most tasks of a phase are done or the user asks if a phase is finished.
---

# Phase gate

## Steps
1. `python3 shared/tools/progress/tasks.py list --phase <N>` — count by status. List every task not `done`/`external`/`skipped` with its reason.
2. Read the phase's **exit criteria** in `integration/prd/04-delivery-plan.md` (the phase section) and, for each criterion, find evidence: test reports, metrics, dashboards, customer confirmations recorded in session logs. Mark each: met / not met / no evidence.
3. Walk the **phase gate checklist** (`04-delivery-plan.md`, last section).
4. Use `code-reviewer` and `security-reviewer` for a final pass on the phase's main modules if not done recently.
5. Write `shared/progress/gates/phase-<N>.md`: criteria table with evidence links, open items, risks, recommendation (go / no-go / go with conditions).
6. Do not mark the phase closed yourself. Present the report; the user decides. Record the decision in STATUS.md and the session log.
