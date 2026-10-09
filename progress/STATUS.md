# Project status

*Updated: 2026-10-09 · Keep under ~60 lines. Detail goes in progress/sessions/.*

## Phase
**Phase 0 — Foundations** (not started in code). Planning and design pack are complete.

## In progress
- None.

## Next engineering tasks (see `python3 tools/progress/tasks.py next`)
1. T0.2.1 — Monorepo setup (modular-monolith layout, TS/Py/Go tooling, boundary lint, Taskfile)
2. T0.5.1 — Canonical model format (JSON Schema conventions)
3. T0.5.4 — Capability Model schema v0
4. T0.2.10 — Full ADR documents for ADR-001…014 (rows exist in 02-architecture.md §15)

## Human / business tasks the user owns (mark `external` when done)
- T0.1.1 fintech interviews · T0.1.2 merchant interviews + A–F survey · T0.1.4 design-partner agreements
- T0.1.6 legal review (consent text, ETA delegation, residency, LLM processing outside Egypt)
- T0.3.1 Egypt hosting provider (engineering + PM)

## Open questions for the user
- Can a third party read a merchant's ETA invoices with delegated credentials? (validates priority #1)
- May masked merchant data be processed by an LLM outside Egypt?
- Product name (working name: Wasla).

## Key references
- Instructions: AGENTS.md, CLAUDE.md · Human guide: HANDBOOK.md
- Docs: integration/prd/README.md
- Latest session log: progress/sessions/2026-10-09-planning.md
