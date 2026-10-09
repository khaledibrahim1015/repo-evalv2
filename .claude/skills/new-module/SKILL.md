---
name: new-module
description: Scaffold a new Wasla module (one per service id S01-S50) in TypeScript, Python or Go inside the modular monolith, or a new deployable entrypoint, following the tech stack and boundary rules. Use before writing the first code of any service.
---

# New module

Read first: `integration/prd/05-tech-stack.md` §2 (deployables and which module lives where), §4 (libraries), §13 (layout); the service section in `03-services.md`.

## Decide
- **Service id and name**, e.g. `S06 consent` → folder `modules/ts/consent/`.
- **Language and deployable** from tech stack §2 (do not choose differently without `record-decision`).
- **Postgres schema** name = module name (snake_case).
- **Events** it publishes/consumes (subjects from `02-architecture.md` §4.4).

## Create (TypeScript example; mirror the structure in Python/Go)
```
modules/ts/<name>/
  package.json            # name "@wasla/<name>", private
  src/index.ts            # the ONLY public interface (functions/types other modules may use)
  src/domain/             # entities, rules (no I/O)
  src/app/                # use cases; transactions; outbox writes
  src/infra/              # Kysely repositories, clients, NATS consumers, Temporal activities
  src/http/               # Fastify routes (if the module has an API) + OpenAPI via Zod
  migrations/             # Kysely migrations for schema "<name>" (RLS on tenant tables)
  test/                   # unit + integration (Testcontainers)
  README.md               # purpose, interface, events, tables, owner service id
```
Python: `modules/py/<name>/` with `pyproject.toml` (uv), package `wasla_<name>`, same subfolders, pytest.
Go: `modules/go/<name>/` package with `internal/` for non-public parts, `go test`.

## Wire
- Register routes/workers/consumers in the deployable entrypoint under `apps/<deployable>/` only.
- Add contracts to `packages/contracts` (OpenAPI paths, AsyncAPI channels, JSON Schemas) and regenerate clients.
- Add the module to the boundary-lint config (dependency-cruiser / import-linter / Go internal packages).
- Use the service kit for config, auth, tenancy (`set_config('app.tenant_id', ...)`), logging, tracing, outbox.

## Check
- Builds and tests pass for the new module.
- No imports from another module's internals; no cross-schema SQL.
- README lists interface, events, tables, and the service id.
