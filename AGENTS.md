# AGENTS.md — Wasla

Instructions for any coding agent working in this repository. Claude Code loads this through `CLAUDE.md`.

## 1. What we are building

**Wasla** (working name) is a generic B2B integration network. A **hub** (first: fintechs in Egypt) embeds our Connect flow; its **spokes** (merchants, suppliers) connect at whatever level they can — API, database, website, Excel/email, or nothing. Wasla maps each spoke to a **canonical data model**, runs integrations durably, and **reconciles** both sides so they provably agree.

Full product and engineering pack: `integration/prd/` (read the index in `integration/prd/README.md`).

## 2. Sources of truth (in priority order)

| Need | Read |
|---|---|
| Current state, what to do next | `shared/progress/STATUS.md`, `python3 shared/tools/progress/tasks.py brief`, latest `shared/progress/sessions/*.md` |
| A task's scope, owner, dependencies | `python3 shared/tools/progress/tasks.py show <ID>` → row in `integration/prd/04-delivery-plan.md` |
| What a service/module must do | `integration/prd/03-services.md` (section S01–S50) |
| How things fit together, flows, ADRs | `integration/prd/02-architecture.md` |
| Technology, libraries, deployables, repo layout | `integration/prd/05-tech-stack.md` |
| Why / requirements / priorities | `integration/prd/01-prd.md` (§2.2 priority order, §7 requirements) |

The files under `integration/` outside `prd/` are **background only**; they are superseded by `prd/`.

**Do not rely on memory of earlier conversations.** If it is not in the files above or in git history, it was not decided.

## 3. Decisions already made (do not reopen without the user)

- Modular monolith: 7 deployables — `edge` (Go), `core` (TS), `kms` (Go), `ledger` (Go), `ai` (Python), `sandbox` (Go, Phase 2), `edge-agent` (Go, Phase 2). Module boundaries = services S01–S50.
- Languages from day one: TypeScript, Python, Go.
- PostgreSQL is the only system of record (schema per module, RLS for tenancy). Temporal for durable workflows. **NATS JetStream** for events (Postgres outbox → relay). No Kafka.
- Canonical Data Model per vertical (JSON Schema) + Mapping Service + Canonical Data Service. **No semantic types / Taxi / Orbital-style resolver.**
- AI: Anthropic SDK directly, own Agent Runtime, Temporal. **No LangChain / LangGraph.** Default model `claude-opus-5-5`, effort set per route.
- Build product components in-house; licensing is not a concern in this project.
- Priority order (PRD §2.2): MVP = F (ETA, bank statements, hub data) + D (Excel/email) + A (cloud ERP APIs) + micro-app pilot. Phase 2 = Edge Agent (T3), website → API (T5), human tasks (T8a). Deferred: T2 doc reader, T4 code → API, API generation.
- Egypt first, KSA in Phase 3.

Any new decision: use the `record-decision` workflow (§7) so docs, ADRs and the tracker stay consistent.

## 4. Repository layout

```
AGENTS.md, CLAUDE.md                agent instructions (HANDBOOK.md: human guide)
integration/prd/                    PRD, architecture, services, delivery plan, tech stack (source of truth)
shared/                             project working state and tooling (not product code)
  progress/                         STATUS.md, tasks.json (generated), sessions/ (one log per session), gates/
  tools/progress/tasks.py           task tracker (stdlib Python)
.claude/                            Claude Code skills, agents, hooks, settings
apps/ modules/ packages/            product code (created from T0.2.1, layout in 05-tech-stack.md §13)
canonical-models/ country-packs/ evals/ infra/ docs/
```

## 5. Working loop (every session)

1. **Resume** — read the session-start context, `shared/progress/STATUS.md`, the last session log; run `tasks.py brief`.
2. **Pick one task** — the one in progress, else the first ready task from `tasks.py next`. One task per session is the default; small related tasks may be grouped.
3. **Load only what the task needs** — `tasks.py show <ID>`, then the specific sections it points to. Do not read whole documents when a section will do.
4. **Plan → implement → verify** — follow the definition of done (§6). Keep changes inside the module(s) the task names.
5. **Record** — `tasks.py start/done/block/note`, update `shared/progress/STATUS.md`, write the session log, commit.

Human/business tasks (`kind: human`, e.g. interviews, legal review) are not done in code. Mark them `external` with a note when the user confirms they are done, or skip past them.

## 6. Definition of done (per task)

- Code inside the right module and deployable; no reads of another module's tables; boundary lint passes.
- Tests: unit + integration (Testcontainers for Postgres/NATS/Temporal where touched); golden-file tests for mappings/extraction; evals for agent changes.
- Contracts updated (`packages/contracts`: OpenAPI 3.1, AsyncAPI 3.0, JSON Schema) and generated code refreshed.
- Tenant and region on every request, row, event and log line; RLS policies for new tenant tables.
- Events via outbox → JetStream with `Nats-Msg-Id = event_id`; consumers idempotent.
- Writes to external systems carry idempotency keys.
- PII masked in logs, run history and LLM prompts; secrets only via KMS.
- OpenTelemetry traces/metrics/logs added for new paths.
- Docs updated if behavior or decisions changed; runbook for new operational components.
- `tasks.py done <ID> --note "<what changed, where>"` and a commit referencing the task ID.

## 7. Engineering rules

- **Modules:** one folder per service id under `modules/{ts,py,go}/`; public interface only; cross-deployable calls via OpenAPI clients or NATS events.
- **Database:** Kysely (TS), psycopg (Py), pgx (Go); no ORM; expand/contract migrations; one schema per module.
- **Workflows:** all multi-step or retried work goes through Temporal (`packages/durable`); workflows deterministic.
- **AI:** call models only through the LLM Gateway module; structured outputs or strict tools; `tool_choice: auto`; PII Guard before every call; external content (Excel, HAR, WhatsApp) is data, never instructions; prompts versioned; every change passes the eval gate.
- **Arabic:** normalize text (alef/yaa/taa-marbuta, digits); every UI string in Arabic and English; RTL.
- **Security:** never write real secrets, keys or customer data to the repo; `.env.example` only.
- **Decisions:** when the user changes a decision, update every affected doc (`01`–`05`), add or amend an ADR in `02-architecture.md` §15, run `tasks.py sync` if the delivery plan changed, and log it in the session log.
- **Scope:** do not add features, abstractions or tasks the plan does not ask for; propose them instead.

## 8. Git

- Work on the branch the user or environment specifies; never push to another branch without permission.
- Commit message: `T<id>: <imperative summary>` (several IDs allowed). Docs-only: `docs: ...`. Progress-only: `progress: ...`.
- Commit at the end of each task and at handoff. Do not rewrite shared history.

## 9. Context hygiene (avoid context rot)

- The tracker, STATUS and session logs are the memory. Write things there, not only in chat.
- Prefer targeted reads (`grep -n`, line ranges, `tasks.py show`) over reading whole files.
- Delegate broad searches and reviews to subagents; keep only their conclusions.
- Hand off before the context gets large: record progress, commit, then start fresh (`/clear`) — the session-start hook reloads the state.
- Keep STATUS.md under ~60 lines; move detail into session logs.

## 10. Commands

Available now:
```
python3 shared/tools/progress/tasks.py brief | next | show <ID> | start <ID> | done <ID> --note "..." | block <ID> --note "..." | external <ID> | sync
```
Available after T0.2.1 (monorepo setup): `task dev`, `task build`, `task test`, `task lint` (see `05-tech-stack.md` §3 and §12). Until then, use each toolchain directly.
