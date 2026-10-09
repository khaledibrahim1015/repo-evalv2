# 05 — Technology Stack (detailed)

*Version 1.0 · October 9, 2026 · Companion to [02-architecture.md](02-architecture.md). This document is the source of truth for technology choices; the architecture document summarizes it.*

---

## 1. Decisions this stack is built on

| # | Decision | ADR |
|---|---|---|
| 1 | **Modular monolith**: code is split into the same module boundaries as the services in [03-services.md](03-services.md), but shipped as a small number of deployables. Any module can be extracted later without rewriting | ADR-012 |
| 2 | **Three languages from day one**: TypeScript (core product), Python (AI, extraction, data), Go (edge, security, ledgers) | ADR-013 |
| 3 | **NATS JetStream** is the event backbone from day one; Postgres outbox + relay for atomic publishing | ADR-011 |
| 4 | **Temporal** for all durable, multi-step processing | ADR-004 |
| 5 | **PostgreSQL** as the only system of record | ADR-002 |
| 6 | **No agent frameworks** (no LangChain/LangGraph): Anthropic SDK + our own Agent Runtime + Temporal | ADR-014 |
| 7 | **Product components built in-house**; commodity infrastructure and libraries used as building blocks | — |
| 8 | **Region cells**: everything below runs per region (Egypt first) | ADR-001 |

Versions: use the **current stable/LTS release at project start** for every item; the versions below are the minimum baseline. Pin exact versions in the repo and update through Renovate.

---

## 2. Deployables

Seven backend deployables at the start (plus front-end apps). Each runs as one or more Kubernetes Deployments with separate entrypoints (API, workers).

| # | Deployable | Language | Modules inside (service ids) | Entrypoints | Phase |
|---|---|---|---|---|---|
| D1 | **edge** | Go | API Gateway (S01), Webhook Ingress (S02); Tunnel Gateway (S03) from Phase 2 | `gateway`, `ingress`, `tunnel` | 0 |
| D2 | **core** | TypeScript | IAM (S04), Tenant (S05), Consent (S06), Region (S08), Notification (S10), Billing (S11), Connection (S12), Discovery (S13), Spec Ingestor (S14), Connector Runtime (S20), Shared-source Connectors (S21), CM Registry (S24), Canonical Model Registry (S25), Canonical Data Service (S27), Spec Service (S28), Spec Compiler (S30), Orchestration (S31), Run History (S32), Verification (S33), Reconciler (S36), Breaks (S37), Human Tasks (S38), Micro-app Platform (S39), Hub API (S45), Console BFF (S46), Connect Service (S47), Search (S49) | `api` (HTTP), `worker` (Temporal workers + NATS consumers), `relay` (outbox → NATS), `cron` | 0 |
| D3 | **kms** | Go | Secrets & Keys (S07) | `kms` | 0 |
| D4 | **ledger** | Go | Audit (S09), State Ledger (S34), Money Ledger (S35, Phase 2) | `api`, `consumer` | 0 |
| D5 | **ai** | Python | LLM Gateway + PII Guard (S40), Agent Runtime (S41), Evaluation (S42), Mapping (S26), Document Extractor (S19); Phase 2: DB Introspector (S16), Website-to-API (S18), Ops Agent (S44) | `api`, `worker` (Temporal activities + NATS consumers), `embeddings` | 0 |
| D6 | **sandbox** | Go | Code Sandbox (S43) + isolated browser runner for S18 | `sandbox` (isolated node pool) | 2 |
| D7 | **edge-agent** | Go | Edge Agent (S22), installed at customer sites | single binary | 2 |

**Why these boundaries:** KMS is isolated for security; ledger and audit are isolated because they are append-only, high-write and must never be affected by product deploys; edge is isolated because it faces the internet; ai is isolated because its dependencies, scaling and cost profile differ; sandbox is isolated because it runs untrusted code.

### 2.1 Module rules (inside a deployable)
- Each module has its own folder, its own Postgres schema, its own public interface (`index.ts` / `__init__.py` / Go package API) and its own events.
- A module **never** reads another module's tables. It calls the other module's interface (in-process) or consumes its events.
- Cross-deployable calls use internal HTTP/JSON with OpenAPI contracts, or NATS events.
- Lint rules (dependency-cruiser for TS, import-linter for Python, Go internal packages) fail the build on boundary violations.
- Extraction path: a module becomes its own deployable by moving its entrypoint; its interface becomes an HTTP client with the same signature.

---

## 3. Languages and runtimes

| Language | Baseline | Used for | Toolchain |
|---|---|---|---|
| **TypeScript** | Node.js 24 LTS, TypeScript 5.x (strict) | core (D2), front-ends, SDK | pnpm workspaces, Turborepo, tsx/tsup, ESLint + Prettier, Vitest |
| **Python** | Python 3.13 | ai (D5) | uv (env + lock), Ruff (lint + format), Pyright (types), pytest |
| **Go** | Go 1.25+ | edge (D1), kms (D3), ledger (D4), sandbox (D6), edge-agent (D7) | Go workspaces, golangci-lint, `go test` |
| **SQL** | PostgreSQL dialect | migrations, reports | migration tool per language (below), sqlfluff |

Top-level task runner: **Taskfile (go-task)** wraps pnpm/uv/go commands so one command builds, tests and lints everything (`task build`, `task test`, `task lint`, `task dev`).

---

## 4. Backend libraries per language

### 4.1 TypeScript (core)
| Concern | Choice |
|---|---|
| HTTP framework | **Fastify** (+ `@fastify/swagger` for OpenAPI output) |
| Validation & types | **Zod** (request/response schemas, event payloads, structured outputs) |
| Database access | **Kysely** (type-safe SQL builder) on **node-postgres (pg)**; no ORM |
| Migrations | Kysely migrations, one folder per module schema |
| Tenancy | Every transaction sets `app.tenant_id` / `app.region` via `set_config`, enforced by Postgres RLS |
| Workflows | **Temporal TypeScript SDK** (workers, workflows, activities), wrapped by `packages/durable` |
| Events | **NATS JetStream** JS client (`@nats-io/jetstream`), wrapped by `packages/events` (outbox, relay, consumers, dedup) |
| Auth (own IAM) | `jose` (JWT/JWKS), `@node-rs/argon2` (password hashing), `otplib` (TOTP); WebAuthn later |
| Expression language | Own `packages/expr` (JSONata-compatible syntax), interpreter in TS |
| JSON Schema | Ajv (2020-12) for canonical model validation |
| Excel export/import in core | ExcelJS (micro-app import/export) |
| HTTP client (connectors) | undici with per-connection agent pools |
| Scheduling | Temporal schedules (no separate cron library) |
| Observability | OpenTelemetry JS SDK (traces, metrics), pino (structured logs) |
| Testing | Vitest, Testcontainers (Postgres, NATS, Temporal), Pact-style contract tests from OpenAPI |

### 4.2 Python (ai)
| Concern | Choice |
|---|---|
| HTTP framework | **FastAPI** (internal APIs only) |
| Models & validation | **Pydantic v2** (structured outputs, tool schemas, event payloads) |
| LLM | **Anthropic Python SDK** (`anthropic`), called only through the LLM Gateway module |
| Agent loop | SDK Tool Runner / manual loop inside our Agent Runtime module; **no LangChain/LangGraph** |
| Workflows | **Temporal Python SDK** (activities for extraction, mapping, agents) |
| Events | `nats-py` (JetStream), wrapped by `service-kit-py` |
| Database | psycopg 3 (+ pgvector adapter); SQL written by hand |
| Excel / CSV | python-calamine (fast read), openpyxl (formats, merged cells), Polars (tabular processing) |
| PDF / images | Claude document and image input (Phase 2); pypdf for splitting |
| Arabic text | Own normalization module (alef/yaa/taa-marbuta, digits, diacritics) |
| PII detection | Own rules + regex (Egyptian national ID, phones, tax IDs, IBAN, emails) + optional NER |
| Embeddings | Self-hosted multilingual embedding model with Arabic support (e.g. BGE-M3) served by the `embeddings` entrypoint |
| Browser automation (Phase 2) | Playwright, run inside the sandbox (D6) |
| Testing | pytest, Testcontainers, golden-file tests, eval harness (S42) |

### 4.3 Go (edge, kms, ledger, sandbox, edge-agent)
| Concern | Choice |
|---|---|
| HTTP | net/http + **chi** router |
| Database | **pgx v5** |
| Events | **nats.go** (JetStream) |
| Crypto | Go standard library crypto (AES-GCM envelope encryption, Ed25519 signing, X.509 for internal CA) |
| Root key | Provider HSM/KMS if available in region; otherwise HSM appliance or sealed key file with strict ops (decided in T0.3.7) |
| Rate limiting (gateway) | Token bucket in Valkey |
| Edge Agent DB drivers (Phase 2) | go-mssqldb, go-sql-driver/mysql, pgx, godror (Oracle) |
| Edge Agent local storage | SQLite (pure-Go driver), encrypted |
| Sandbox (Phase 2) | gVisor (runsc) as RuntimeClass on an isolated node pool; Firecracker evaluated if stronger isolation is needed |
| Observability | OpenTelemetry Go, slog |
| Testing | `go test`, Testcontainers-go |

---

## 5. Data and messaging

| Component | Choice | Configuration |
|---|---|---|
| **System of record** | **PostgreSQL 17+** (18 if supported by the provider) | HA (primary + 2 replicas), PITR, one schema per module, RLS on all tenant tables, partitioning for runs/ledger/audit (pg_partman), **pgvector** for embeddings, **PgBouncer** in transaction mode |
| **Events** | **NATS JetStream** (2.11+) | 3-node cluster per region, TLS, accounts per environment, one stream per domain, replicas = 3, durable pull consumers, DLQ subjects, dedup via `Nats-Msg-Id` |
| **Durable workflows** | **Temporal** (self-hosted) | Postgres persistence (separate database), namespaces per environment, task queues per deployable |
| **Cache / rate limits** | **Valkey** (Redis-compatible) | Rate-limit counters, CDS cache, sessions; no data that cannot be lost |
| **Object storage** | S3-compatible (provider service; MinIO if none) | Buckets per purpose (raw uploads, run payloads, exports, evals), encryption with tenant data keys, lifecycle rules |
| **Search** | PostgreSQL full-text (Arabic/English configurations) + pgvector | No separate search engine at the start |

---

## 6. AI stack

| Concern | Choice |
|---|---|
| Model provider | Anthropic API |
| Default model | `claude-opus-5-5`, effort set per route: `low` (extraction, classification, reply parsing), `medium` (mapping), `high` (website-to-API, Ops Agent) |
| Cheaper models | Only after measuring on golden datasets; decision by product owner |
| Output control | Structured outputs (`output_config.format`) and strict tools (`strict: true`); `tool_choice: auto` (forced tool choice is not supported on the default model) |
| Cost controls | Prompt caching (stable prefixes: instructions + canonical model), Batch API for backfills and large evals, per-tenant budgets in the LLM Gateway |
| Safety | PII Guard before every call; external content (Excel, HAR, WhatsApp) treated as data, never instructions; refusal handling with server-side fallbacks |
| Agent Runtime | Own module: tool registry, step/token budgets, approval gates for write tools, decision logs, Temporal activities |
| Evaluation | Own harness (S42): golden datasets per agent, regression gate in CI |
| Embeddings | Self-hosted multilingual model (see 4.2) |
| Open legal question | Whether masked data may be processed outside Egypt (to be answered by counsel before Phase 1) |

---

## 7. Front-end

| App | Users | Stack |
|---|---|---|
| **console** | Hub Console + Spoke Portal + Wasla Studio (role-based areas) | React 19, TypeScript, Vite, TanStack Router, TanStack Query, React Hook Form + Zod |
| **connect** | Connect flows + micro-app PWA (merchant-facing, mobile-first) | Same stack + PWA (Workbox), small bundle budget |
| **dev-portal** | Hub developers | Static site generated from OpenAPI/AsyncAPI + guides |

Shared: `packages/design-system` (headless Radix UI primitives + Tailwind CSS, own components and tokens), `packages/i18n` (i18next, Arabic/English, RTL, Arabic/Latin digits, date formats), generated API clients from OpenAPI.

---

## 8. Contracts and code generation

| Contract | Standard | Generated |
|---|---|---|
| Public & internal REST | OpenAPI 3.1 | TS clients (front-ends, SDK), Python/Go clients for cross-deployable calls, docs |
| Events | AsyncAPI 3.0 + JSON Schema 2020-12 | Zod / Pydantic / Go types for payloads |
| Canonical model | JSON Schema 2020-12 + state machine YAML | Validators, TS/Python types, micro-app screens |
| Integration Spec | JSON Schema for YAML | Editor validation, compiler input types |

All contracts live in `packages/contracts`; CI fails on breaking changes without a version bump.

---

## 9. Infrastructure

| Concern | Choice |
|---|---|
| Hosting | Provider in Egypt meeting residency (decided in T0.3.1); KSA in-kingdom in Phase 3 |
| Orchestration | Kubernetes (managed if the provider offers it; otherwise RKE2/k3s on VMs) |
| Packaging | Helm charts per deployable |
| GitOps | Argo CD (one repo per environment) |
| IaC | OpenTofu |
| Ingress | Envoy Gateway (L7) in front of the Go API Gateway |
| TLS | cert-manager |
| Infra secrets | SOPS + age in GitOps repos; application secrets in our KMS |
| Container registry | Harbor (or provider registry), image signing with Cosign |
| Networking | Network policies per namespace, mTLS between deployables |
| Environments | `dev` (ephemeral PR envs), `staging`, `sandbox` (customer-facing), `production` |

---

## 10. Observability

| Concern | Choice |
|---|---|
| Instrumentation | OpenTelemetry in all three languages; trace context propagated over HTTP, NATS headers and Temporal |
| Collection | OpenTelemetry Collector |
| Metrics | Prometheus-compatible store (VictoriaMetrics) |
| Logs | Loki |
| Traces | Tempo |
| Dashboards & alerts | Grafana + Alertmanager; SLO burn-rate alerts |
| Errors | Errors as traces/logs with `trace_id`; no separate error service at the start |
| LLM observability | LLM Gateway logs (masked) + Grafana dashboards for cost, latency, quality |
| Status page | Static status page fed by synthetic checks |

---

## 11. CI/CD and quality

| Concern | Choice |
|---|---|
| CI | GitHub Actions |
| Build orchestration | Taskfile + Turborepo (TS) + uv + Go build cache; affected-only builds |
| Static analysis | ESLint, Ruff, Pyright, golangci-lint, Semgrep |
| Dependencies | Renovate; vulnerability scanning with Trivy |
| SBOM & signing | Syft (SBOM), Cosign (images, Edge Agent binaries) |
| Tests | Unit, integration (Testcontainers), contract (OpenAPI/AsyncAPI), golden-file (mappings, extraction), evals (agents), end-to-end (Playwright for front-ends) |
| Delivery | Build once → staging → sandbox → production via Argo CD; canary with automatic rollback from Phase 3 |
| Database changes | Expand/contract migrations, backward compatible for one release |

---

## 12. Local development

`task dev` starts, via Docker Compose:
- PostgreSQL (with pgvector), NATS JetStream, Temporal (+ UI), Valkey, MinIO, OpenTelemetry Collector + Grafana (optional profile)
- core (`api`, `worker`, `relay`), ai (`api`, `worker`), edge, kms, ledger in watch mode
- console and connect front-ends with Vite dev servers
- Seed script: sample hub, spokes, canonical model v0, Odoo/SQL/ETA fixtures

---

## 13. Repository layout (modular monolith)

```
wasla/
├─ apps/                         # deployables (thin: wiring + entrypoints)
│  ├─ edge/            (Go)      # gateway, ingress, tunnel
│  ├─ core/            (TS)      # api, worker, relay, cron entrypoints
│  ├─ kms/             (Go)
│  ├─ ledger/          (Go)
│  ├─ ai/              (Py)      # api, worker, embeddings
│  ├─ sandbox/         (Go)      # Phase 2
│  ├─ edge-agent/      (Go)      # Phase 2
│  ├─ console/         (React)
│  ├─ connect/         (React, PWA)
│  └─ dev-portal/      (static)
├─ modules/                      # domain modules, one folder per service id
│  ├─ ts/   iam/ tenant/ consent/ region/ notification/ billing/ connection/ discovery/
│  │        spec-ingestor/ connector-runtime/ shared-sources/ cm-registry/ cdm-registry/
│  │        canonical-data/ spec-service/ spec-compiler/ orchestration/ run-history/
│  │        verification/ reconciler/ breaks/ human-tasks/ microapps/ hub-api/
│  │        console-bff/ connect-service/ search/
│  ├─ py/   llm-gateway/ agent-runtime/ evaluation/ mapping/ document-extractor/
│  │        db-introspector/ website-to-api/ ops-agent/
│  └─ go/   gateway/ ingress/ tunnel/ kms/ audit/ state-ledger/ money-ledger/ sandbox/
├─ packages/                     # shared libraries
│  ├─ service-kit-ts/ service-kit-py/ service-kit-go/   # config, auth, tenancy, logging, tracing
│  ├─ events-ts/ events-py/ events-go/                  # outbox, relay, JetStream consumers, dedup
│  ├─ durable/                   # Temporal wrappers (TS + Py)
│  ├─ contracts/                 # OpenAPI, AsyncAPI, JSON Schemas + generated code
│  ├─ expr/                      # expression language
│  ├─ policy/                    # authorization
│  ├─ design-system/ i18n/
│  └─ sdk-ts/ sdk-py/            # public SDKs
├─ canonical-models/             # embedded-finance/ (JSON Schema + state machines)
├─ country-packs/                # eg/, sa/
├─ evals/                        # golden datasets and eval configs
├─ infra/                        # OpenTofu, Helm charts, Argo CD apps, compose for local dev
├─ docs/                         # ADRs, runbooks
└─ Taskfile.yml
```

---

## 14. What is intentionally not in the stack

| Not used | Why |
|---|---|
| Kafka | NATS JetStream covers our volume with far less operations work |
| LangChain / LangGraph | Few, bounded agents; Temporal covers state, retries and human-in-the-loop; prompts must stay visible for caching and debugging |
| A separate search engine | Postgres full-text + pgvector is enough at the start |
| An ORM | Typed SQL builders keep RLS, partitioning and query plans explicit |
| GraphQL | REST + webhooks fit hub developers and the canonical data API |
| Microservice-per-module deployment | Ops cost too high for the team size; module boundaries keep the option open |
