@AGENTS.md

# Claude Code specifics

## Automatic behavior (hooks in `.claude/settings.json`)
- **SessionStart** (startup, resume, /clear, compaction): prints branch, recent commits, `shared/progress/STATUS.md`, tracker brief and the "Next" section of the last session log. Treat it as the starting state.
- **Stop**: if code changed after the last `shared/progress/` update, the stop is blocked once with a request to run `handoff`. Do it; don't argue with it.
- **PreToolUse (Edit/Write)**: blocks edits to `.env*` (except examples), key/cert files, `secrets/`, and `shared/progress/tasks.json` (use `shared/tools/progress/tasks.py`).

## Skills (`.claude/skills/`)
| Skill | Use when |
|---|---|
| `resume` | Start of every session, after /clear or compaction, or when unsure what to do next |
| `implement-task` | Implementing a task ID from the delivery plan |
| `handoff` | End of a session, before /clear, when context is getting large, or when the Stop hook asks |
| `new-module` | Creating a module (TS/Python/Go) or a deployable |
| `record-decision` | The user changes or makes a product/architecture decision |
| `phase-gate` | Checking whether a phase can close |

## Subagents (`.claude/agents/`)
| Agent | Use for |
|---|---|
| `task-planner` | Turning a task into a concrete file-level plan before coding (non-trivial tasks) |
| `spec-guardian` | Looking up what the docs say, and checking a change against PRD/architecture/ADRs |
| `code-reviewer` | Reviewing the diff against the definition of done and engineering rules before marking a task done |
| `security-reviewer` | Changes touching auth, tenancy/RLS, KMS/secrets, PII, Edge Agent, sandbox, LLM inputs |

Subagents start without this conversation: give them the task ID, the files involved and what you need back.

## Session rhythm
`resume` → one task with `implement-task` → reviewers → `handoff` → `/clear` → next task.
