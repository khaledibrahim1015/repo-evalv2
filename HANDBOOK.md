# Wasla — Working Handbook (Claude Code)

This handbook explains how the repository is set up for working with Claude Code, and how to use it day to day.

The goal of the setup: **every session knows everything that happened before, works on one planned task at a time, and leaves the project in a state the next session can continue from — without relying on chat history.** Memory lives in files, not in conversations.

---

## 1. The idea in one picture

```
            ┌──────────────── repository = the project's memory ────────────────┐
            │                                                                    │
            │  integration/prd/   what to build (PRD, architecture, services,    │
            │                     delivery plan, tech stack)                     │
            │  shared/progress/          where we are (STATUS, tasks.json, sessions/)   │
            │  AGENTS.md          how to work (rules, decisions, definition of   │
            │                     done)                                          │
            └────────────────────────────────────────────────────────────────────┘
                         ▲ read at start                  │ written at end
                         │                                ▼
   new session ──► resume ──► implement one task ──► review ──► handoff ──► /clear ──► next session
```

---

## 2. What is in the repository

| Path | What it is | Who changes it |
|---|---|---|
| `AGENTS.md` | Main instructions for any coding agent: sources of truth, decisions already made, working loop, definition of done, engineering rules, git conventions, context hygiene | You or Claude (via `record-decision`) |
| `CLAUDE.md` | Imports `AGENTS.md` and adds Claude Code specifics (hooks, skills, subagents) | Rarely |
| `HANDBOOK.md` | This guide, for humans | Rarely |
| `integration/prd/` | Product & engineering pack: `01-prd.md`, `02-architecture.md`, `03-services.md`, `04-delivery-plan.md`, `05-tech-stack.md` | Claude, when decisions change |
| `shared/progress/STATUS.md` | Short current state: phase, task in progress, next tasks, blockers, open questions | Claude at every handoff |
| `shared/progress/tasks.json` | Status of every task in the delivery plan | **Only** through `shared/tools/progress/tasks.py` |
| `shared/progress/sessions/` | One log per session: Done · Decisions · Problems · Next | Claude at every handoff |
| `shared/tools/progress/tasks.py` | Task tracker (plain Python, no dependencies) | Rarely |
| `.claude/settings.json` | Hooks and a few pre-approved commands | Rarely |
| `.claude/hooks/` | Hook scripts | Rarely |
| `.claude/skills/` | Step-by-step workflows Claude follows | When the process changes |
| `.claude/agents/` | Specialised subagents (planner, doc expert, reviewers) | When the process changes |

Files in `integration/` outside `prd/` are background from early planning and are **superseded** by `prd/`.

---

## 3. Daily usage

### 3.1 Starting a session
Open Claude Code in the repository and type:

```
resume
```

What happens:
1. The **SessionStart hook** has already loaded the branch, the last 5 commits, `shared/progress/STATUS.md`, the tracker summary and the "Next" list from the last session log.
2. The `resume` skill checks git for leftover uncommitted work, syncs the tracker if the plan changed, and picks the task: the one in progress, otherwise the first ready task.
3. Claude tells you in two or three lines what it will do next.

### 3.2 Working on a task
Claude follows the `implement-task` skill:

1. `tasks.py show <ID>` and `tasks.py start <ID>`.
2. Reads **only** the sections the task needs (its row in the delivery plan, its service sections, the relevant tech-stack parts).
3. Plans. For non-trivial tasks it asks the `task-planner` subagent.
4. Builds inside the right module, with small commits named `T<ID>: ...`.
5. Runs tests and linters, then asks `code-reviewer`, and `security-reviewer` when security-sensitive code changed.
6. Marks the task done with a note: `tasks.py done <ID> --note "..."`.

You can also point it at a specific task:

```
implement T0.5.1
```

### 3.3 Ending a session
Say:

```
handoff
```

Claude updates the tracker, writes the session log, refreshes `STATUS.md`, commits, and tells you what is next.
If you forget, the **Stop hook** blocks the stop once and asks Claude to do the handoff.

Then type `/clear` (or close the session). The next session starts from the files.

### 3.4 Recommended rhythm

```
resume → one task → review → handoff → /clear → resume → next task …
```

One task per session keeps the context small and focused. Small related tasks can be grouped.

---

## 4. Typical prompts

| You want to… | Say |
|---|---|
| Continue where things stopped | `resume` |
| Work on a specific task | `implement T1.3.16` |
| See what is next | `what's next?` (Claude runs `tasks.py next`) |
| Know what the docs say about something | `ask spec-guardian what the docs say about consent revocation` |
| Change a decision | `we decided X instead of Y — record it` (triggers `record-decision`) |
| Check if a phase is finished | `phase gate for phase 0` |
| Stop for today | `handoff` |
| Mark a business task as done | `T0.1.6 is done: legal approved the consent text` (Claude runs `tasks.py external`) |

---

## 5. The task tracker

The delivery plan (`integration/prd/04-delivery-plan.md`) contains every task as a table row. The tracker reads those rows and keeps a status for each in `shared/progress/tasks.json`.

### Commands

```bash
python3 shared/tools/progress/tasks.py brief                 # summary used at session start
python3 shared/tools/progress/tasks.py next                  # ready engineering tasks in the current phase
python3 shared/tools/progress/tasks.py next --all            # include human/business tasks
python3 shared/tools/progress/tasks.py next --any-phase      # look ahead into later phases
python3 shared/tools/progress/tasks.py show T1.5.7           # details, dependency status, what to read
python3 shared/tools/progress/tasks.py list --phase 1        # all tasks of a phase
python3 shared/tools/progress/tasks.py list --status blocked
python3 shared/tools/progress/tasks.py start T1.5.7
python3 shared/tools/progress/tasks.py done T1.5.7 --note "what changed, key files"
python3 shared/tools/progress/tasks.py block T1.5.7 --note "reason, what is needed"
python3 shared/tools/progress/tasks.py note T1.5.7 --note "partial progress"
python3 shared/tools/progress/tasks.py external T0.1.6 --note "done outside the codebase"
python3 shared/tools/progress/tasks.py reopen T1.5.7
python3 shared/tools/progress/tasks.py sync                  # after the delivery plan changes
```

### Statuses
`todo` · `in_progress` · `done` · `blocked` · `external` (done outside the code) · `skipped` (removed from the plan)

### How "ready" is decided
- A task is ready when all its dependencies are `done`, `external` or `skipped`.
- Dependencies come from the plan's "Dep" column: explicit IDs (`T0.4.4`), wildcards (`T1.6.*`), `all`/`many` (every earlier engineering task in the same phase) and `above` (every earlier task in the same epic).
- `next` shows only the **current phase** (the lowest phase with open tasks), unless you pass `--any-phase`.

### Human vs. engineering tasks
Tasks whose roles are only PM, UX or DOM (interviews, legal review, partner agreements) are marked `human`. They don't appear in `next` by default and are never "implemented" in code. When you finish one, tell Claude and it marks it `external`.

### When the plan changes
Edit the plan through `record-decision`, then run `tasks.py sync`. Statuses and notes are kept. Tasks removed from the plan become `skipped`.

---

## 6. Hooks (automatic)

Configured in `.claude/settings.json`. They run without being asked.

| Hook | When | What it does |
|---|---|---|
| **SessionStart** | Startup, resume, `/clear`, after compaction | Prints branch, recent commits, `STATUS.md`, tracker brief, and the last session's "Next" list into Claude's context |
| **Stop** | When Claude is about to stop | If code changed after the last `shared/progress/` update, it blocks the stop **once** and asks for a handoff. It never blocks twice in a row |
| **PreToolUse** (Edit/Write) | Before any file edit | Blocks edits to `.env*` (except `.env.example`/`.sample`/`.template`), `*.pem`/`*.key`/`*.p12`/`*.pfx`/`*.jks`, `secrets/`, and hand edits to `shared/progress/tasks.json` |

Notes:
- Hooks load when a session starts. After changing `.claude/settings.json`, open `/hooks` once or restart the session.
- To review or disable hooks: `/hooks`.
- If nothing worth recording happened but the Stop hook still asks, Claude adds one line to the latest session log and commits. That satisfies it.

---

## 7. Skills

Skills are written workflows in `.claude/skills/<name>/SKILL.md`. Claude picks them automatically when the situation matches, or you can name them.

| Skill | Use when | What it does |
|---|---|---|
| `resume` | Start of a session, after `/clear` or compaction, when unsure what's next | Checks git and the tracker, picks the next task, states the plan |
| `implement-task` | Building a planned task | Loads only relevant spec sections → plan → build → test → review → record |
| `handoff` | End of session, before `/clear`, when context is large, when the Stop hook asks | Tracker statuses, session log, `STATUS.md`, commit, short summary to you |
| `new-module` | First code of a service (S01–S50) or a new deployable | Scaffolds the module in TS/Python/Go with the agreed structure, schema, contracts and boundary lint |
| `record-decision` | You make or change a decision | Updates every affected doc, the ADR log, `AGENTS.md` §3 and the tracker, then checks nothing still describes the old option |
| `phase-gate` | A phase looks finished | Checks exit criteria with evidence and writes `shared/progress/gates/phase-N.md`. **You** decide go/no-go |

---

## 8. Subagents

Subagents run in their own context and return only conclusions. This keeps the main session small. They start with no knowledge of the conversation, so Claude passes them the task ID and what it needs.

| Agent | Purpose | Edits files? |
|---|---|---|
| `task-planner` | Turns a task ID into a file-level plan: files, contracts, migrations, steps, tests, out-of-scope items, open questions | No |
| `spec-guardian` | Answers "what do the docs say about X" with `file:line` references; checks a change against PRD, ADRs, tech stack and priorities | No |
| `code-reviewer` | Reviews the diff against the definition of done; runs tests/linters; ranks findings blocker / should-fix / nit | No |
| `security-reviewer` | Reviews auth, tenancy/RLS, secrets, PII, Edge Agent, sandbox, webhooks, LLM inputs; ranks findings critical → low | No |

---

## 9. How context rot is avoided

| Problem | How the setup handles it |
|---|---|
| New session forgets everything | SessionStart hook + `resume` reload state from files |
| Long sessions drift and get slow | One task per session; `handoff` + `/clear` between tasks |
| Compaction loses details | Hook re-injects state after compaction; decisions live in docs and logs, not chat |
| Reading whole documents fills context | Skills read only task-specific sections; `spec-guardian` does broad reads in its own context |
| Docs contradict each other after changes | `record-decision` updates all docs + ADR + tracker and greps for leftovers |
| Work done but not recorded | Stop hook blocks once until progress is recorded |
| Tracker edited by hand and broken | `tasks.json` is protected; only the script changes it |

---

## 10. Source-of-truth order

When two places disagree, Claude follows this order:

1. `AGENTS.md` §3 (decisions already made) and ADRs in `integration/prd/02-architecture.md` §15
2. `integration/prd/05-tech-stack.md` (technology)
3. `integration/prd/01-prd.md` (requirements, priority order §2.2)
4. `integration/prd/03-services.md` and `04-delivery-plan.md`
5. `shared/progress/` (current state). For task status, the tracker wins over `STATUS.md`

Anything not in these files or in git history counts as **not decided**.

---

## 11. Conventions

- **Commits:** `T<ID>: <summary>` for tasks, `docs: ...` for documentation, `progress: ...` for progress-only updates.
- **Branches:** use the branch the environment or you specify; Claude never pushes elsewhere without permission.
- **Session log name:** `shared/progress/sessions/YYYY-MM-DD-<topic>.md` (UTC date).
- **Definition of done:** see `AGENTS.md` §6. In short: right module, tests pass, contracts updated, tenancy and outbox rules respected, PII masked, observability added, docs updated, tracker updated, committed.

---

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| Session starts without the status block | Hooks not loaded: open `/hooks` or restart; check `.claude/settings.json` is valid JSON (`jq . .claude/settings.json`) |
| "Tracker unavailable" at start | Run `python3 shared/tools/progress/tasks.py sync` |
| `next` shows nothing | Current-phase tasks are blocked or waiting on human tasks: run `tasks.py list --phase <N> --status todo` and `next --all` |
| Stop hook keeps asking | Commit the `shared/progress/` update (session log + STATUS). It only checks whether `shared/progress/` was updated after the latest code change |
| Claude wants to edit `tasks.json` and gets blocked | Expected. Use `tasks.py` commands |
| Docs and code disagree | Ask `spec-guardian` to check; then either fix the code or run `record-decision` |
| A task is too big for one session | Finish a coherent slice, `tasks.py note` what remains, `handoff`, continue next session |

---

## 13. First steps from here

1. Open a new Claude Code session in the repository and type `resume`.
2. The first engineering task is **T0.2.1, monorepo setup**. It creates the code layout and the `task dev/build/test/lint` commands.
3. In parallel, the business tasks in `shared/progress/STATUS.md` are yours (interviews, legal review, hosting choice). Tell Claude when each is done.
