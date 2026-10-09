# 02 — Detailed Architecture

*Version 2.0 · October 8, 2026 · Companion to [01-prd.md](01-prd.md)*

---

## 1. Architecture principles

1. **One model in the middle.** Every ladder tier produces the same Capability Model; everything downstream reads only the CM and the canonical model.
2. **Map once to canonical.** Each connection is mapped once to the vertical's Canonical Data Model. Hubs only ever see canonical entities, so a new hub needs no new mapping for an existing spoke.
3. **Durable by default.** Every side-effect runs inside a durable workflow with idempotency keys. Nothing important lives only in memory.
4. **Prove, don't assume.** Every cross-party object is tracked in the State Ledger and reconciled.
5. **Agents propose, gates decide.** Agents produce artifacts (CMs, mappings, specs, fixes); verification and humans approve. Agents never write to customer production directly.
6. **Tenant and region isolation first.** Tenant id and region are on every request, row, event, log line, and key.
7. **Outbound-only into customer networks.** The Edge Agent dials out; Wasla never needs inbound firewall rules.
8. **Events as the backbone.** Services communicate through commands (sync API) and domain events (async). Each service owns its data.
9. **Built in-house, infrastructure as commodity.** Product logic is ours. We rely on commodity infrastructure only: PostgreSQL, NATS JetStream (events), Redis-compatible cache, object storage, Kubernetes, and a durable-workflow engine (Temporal) (ADR-011). Each is wrapped behind an internal interface so it can be replaced.

---

## 2. System context

```mermaid
flowchart LR
  subgraph HubSide["Hub (fintech)"]
    HA[Hub app + embedded Connect]
    HB[Hub backend]
    HU[Hub ops / risk users]
  end
  subgraph SpokeSide["Spoke (merchant / supplier)"]
    SP[Spoke owner / accountant]
    SS1[Cloud ERP / SaaS]
    SS2[On-prem DB / ERP]
    SS3[Own web app / code]
    SS4[Excel, email, paper]
  end
  subgraph External["External shared sources"]
    ETA[ETA e-invoicing / e-receipt]
    ZATCA[ZATCA Fatoora - later]
    BANK[Bank statements / open banking]
    WA[WhatsApp / SMS / email providers]
  end
  W[(Wasla platform)]
  EA[Edge Agent]

  HA -- connect.js --> W
  HB -- REST API / webhooks --> W
  HU -- Hub Console --> W
  SP -- Spoke Portal / tasks --> W
  W -- API calls --> SS1
  EA -- outbound tunnel --> W
  EA -- local --> SS2
  EA -- local --> SS3
  SS4 -- inbox / upload --> W
  W --> ETA
  W --> ZATCA
  W --> BANK
  W <--> WA
```

---

## 3. Logical architecture

```mermaid
flowchart TB
  subgraph Edge["Edge layer"]
    GW[API Gateway]
    WH[Webhook Ingress]
    TG[Tunnel Gateway]
    CDN[Static/CDN: consoles, connect.js]
  end

  subgraph Platform["Platform services"]
    IAM[Identity & Access]
    TEN[Tenant & Party]
    CON[Consent]
    SEC[Secrets & Keys]
    REG[Region & Country Pack]
    AUD[Audit]
    NOT[Notification]
    BIL[Billing & Metering]
  end

  subgraph Connectivity["Connectivity"]
    CXN[Connection Service]
    DIS[Discovery Orchestrator]
    ING[Ingestion Workers: spec, docs, DB, code, traffic, documents]
    CNR[Connector Runtime]
    C6[Country connectors: ETA, ZATCA]
    APG[API Generator]
    EAG[Edge Agent - customer site]
  end

  subgraph Canonical["Canonical data"]
    CMR[Capability Model Registry]
    CDMR[Canonical Model Registry]
    MAPS[Mapping Service]
    CDS[Canonical Data Service]
  end

  subgraph Integration["Integration"]
    ISS[Integration Spec Service]
    DES[Designer Agent]
    CMP[Spec Compiler]
    ORC[Orchestration Runtime]
    RUN[Run History & Replay]
    VER[Verification Service]
  end

  subgraph Agreement["Agreement"]
    SLS[State Ledger]
    MLS[Money Ledger]
    REC[Reconciler]
    BRK[Breaks & Cases]
  end

  subgraph Human["Human channels"]
    HTS[Human Task Service]
    MAP[Micro-app Platform]
  end

  subgraph AI["AI platform"]
    LLM[LLM Gateway + PII Guard]
    AGR[Agent Runtime + Prompt Registry]
    EVL[Evaluation Service]
    SBX[Code Sandbox]
    OPS[Ops Agent]
  end

  subgraph UX["Experiences"]
    HC[Hub Console]
    SPP[Spoke Portal]
    STU[Wasla Studio]
    CNK[Connect widget + hosted connect]
    DEV[Developer portal]
  end

  BUS[(NATS JetStream)]

  UX --> GW --> Platform & Connectivity & Canonical & Integration & Agreement & Human
  WH --> BUS
  TG <--> EAG
  CNR --> TG
  Connectivity & Canonical & Integration & Agreement & Human & AI --> BUS
  ING --> CMR
  CMR --> MAPS --> CDMR
  CDS --> CNR
  CDS --> CMR & CDMR
  ORC --> CDS
  ORC --> SLS
  REC --> SLS & CDS
  REC --> BRK
  OPS --> RUN & BRK & CMR
```

### 3.1 Service catalog (summary)

Full specification of each service in [03-services.md](03-services.md).

| # | Service | Domain | Lang | Store | Phase |
|---|---|---|---|---|---|
| S01 | API Gateway | Edge | Go | Redis | 0 |
| S02 | Webhook Ingress | Edge | Go | NATS JetStream, object store | 1 |
| S03 | Tunnel Gateway | Edge | Go | Redis | 2 |
| S04 | Identity & Access (IAM) | Platform | TS | Postgres | 0 |
| S05 | Tenant & Party | Platform | TS | Postgres | 0 |
| S06 | Consent | Platform | TS | Postgres | 1 |
| S07 | Secrets & Keys (KMS) | Platform | Go | Postgres + HSM/KMS root | 0 |
| S08 | Region & Country Pack | Platform | TS | Postgres | 1 |
| S09 | Audit | Platform | Go | Postgres (append-only) + object store | 0 |
| S10 | Notification | Platform | TS | Postgres | 1 |
| S11 | Billing & Metering | Platform | TS | Postgres | 1 (metering) / 3 (billing) |
| S12 | Connection Service | Connectivity | TS | Postgres | 1 |
| S13 | Discovery Orchestrator | Connectivity | TS | Postgres + workflows | 1 |
| S14 | Spec Ingestor (T1) | Connectivity | TS | Object store | 1 |
| S15 | Doc Reader (T2) | Connectivity | Python | Object store | Deferred |
| S16 | DB Introspector (T3) | Connectivity | Python | Object store | 2 |
| S17 | Code Analyzer (T4) | Connectivity | Python | Object store | Deferred |
| S18 | Website-to-API (T5) | Connectivity | Python + Go | Object store, Postgres | 2 |
| S19 | Document Extractor (T7) | Connectivity | Python | Object store | 1 |
| S20 | Connector Runtime | Connectivity | TS | Redis | 1 |
| S21 | Shared-source Connectors (T6) | Connectivity | TS | Postgres | 1 (ETA, bank, hub data) / 3 (ZATCA) |
| S22 | Edge Agent | Connectivity | Go | Local SQLite buffer | 2 |
| S23 | API Generator (S2) | Connectivity | Python + TS | Object store, Git | Deferred |
| S24 | Capability Model Registry | Canonical data | TS | Postgres (JSONB) | 1 |
| S25 | Canonical Model Registry | Canonical data | TS | Postgres + Git | 0 |
| S26 | Mapping Service | Canonical data | Python | Postgres + vectors | 1 |
| S27 | Canonical Data Service (CDS) | Canonical data | TS | Redis cache | 1 |
| S28 | Integration Spec Service | Integration | TS | Postgres + Git | 1 |
| S29 | Designer Agent | Integration | Python | — | 2 |
| S30 | Spec Compiler | Integration | TS | — | 1 |
| S31 | Orchestration Runtime | Integration | TS | Temporal + Postgres | 1 |
| S32 | Run History & Replay | Integration | TS | Postgres (partitioned) + object store | 1 |
| S33 | Verification Service | Integration | TS | Object store | 1 |
| S34 | State Ledger | Agreement | Go | Postgres (partitioned, append-only) | 1 |
| S35 | Money Ledger | Agreement | Go | Postgres (append-only) | 2 |
| S36 | Reconciler | Agreement | TS | Postgres | 1 |
| S37 | Breaks & Cases | Agreement | TS | Postgres | 1 |
| S38 | Human Task Service | Human | TS | Postgres | 2 |
| S39 | Micro-app Platform | Human | TS | Postgres (per-app schema) | 1 (pilot) / 2 (expansion) |
| S40 | LLM Gateway + PII Guard | AI | Python | Redis, Postgres | 0 |
| S41 | Agent Runtime + Prompt Registry | AI | Python | Postgres | 0 |
| S42 | Evaluation Service | AI | Python | Postgres + object store | 1 |
| S43 | Code Sandbox | AI | Go | — | 2 |
| S44 | Ops Agent | AI | Python | Postgres | 2 |
| S45 | Hub Public API (BFF) | UX | TS | — | 1 |
| S46 | Console BFF (Hub Console, Spoke Portal, Studio) | UX | TS | — | 1 |
| S47 | Connect Service (widget + hosted) | UX | TS | Postgres | 1 |
| S48 | Developer Portal | UX | TS (static) | — | 1 |
| S49 | Search Service | Platform | TS | Postgres FTS + vectors | 2 |
| S50 | Observability Platform | Ops | — | Metrics/logs/traces stores | 0 |

---

## 4. Data architecture

### 4.1 Ownership
Each service owns its tables in its own Postgres schema (logical database per service). No cross-service joins; data needed elsewhere is obtained by API or by consuming events into a local read model.

### 4.2 Core entities (owner → key fields)

```mermaid
erDiagram
  ORGANIZATION ||--o{ WORKSPACE : has
  ORGANIZATION { uuid id string kind "hub|spoke|both" string region string legal_name string tax_id }
  WORKSPACE ||--o{ ENVIRONMENT : has
  ORGANIZATION ||--o{ USER_MEMBERSHIP : has
  HUB_SPOKE_LINK }o--|| ORGANIZATION : hub
  HUB_SPOKE_LINK }o--|| ORGANIZATION : spoke
  HUB_SPOKE_LINK { uuid id string status }
  CONSENT }o--|| HUB_SPOKE_LINK : for
  CONSENT { uuid id string[] scopes date expires_at string status }
  CONNECTION }o--|| ORGANIZATION : owned_by
  CONNECTION { uuid id string tier string system_kind string status uuid secret_ref }
  CAPABILITY_MODEL }o--|| CONNECTION : describes
  CAPABILITY_MODEL { uuid id int version jsonb document string hash }
  ENTITY_MAPPING }o--|| CAPABILITY_MODEL : on
  ENTITY_MAPPING { string canonical_entity string source_operation text field_mapping float confidence string status }
  INTEGRATION_SPEC }o--|| HUB_SPOKE_LINK : for
  INTEGRATION_SPEC { uuid id int version text yaml string status }
  RUN }o--|| INTEGRATION_SPEC : executes
  RUN { uuid id string status timestamptz started_at }
  TRACKED_OBJECT }o--|| HUB_SPOKE_LINK : between
  TRACKED_OBJECT { uuid id string model string canonical_key string state }
  LEDGER_ENTRY }o--|| TRACKED_OBJECT : records
  BREAK }o--|| TRACKED_OBJECT : about
  BREAK { uuid id string type string status }
```

### 4.3 Stores
| Store | Use |
|---|---|
| PostgreSQL (per region, HA, PITR) | All transactional data; JSONB for CMs/specs; partitioned tables for runs and ledger |
| Vector index (pgvector-style column in Postgres) | Field/entity embeddings for mapping and search |
| Object storage (S3-compatible, per region) | Raw ingested artifacts (specs, docs, HAR, uploads), run payloads (encrypted), exports |
| NATS JetStream (per region, 3-node cluster, file storage) | Domain events, CDC events, webhook ingress buffer. One stream per domain (`TENANT`, `CONSENT`, `CONNECTION`, `DISCOVERY`, `CM`, `MAPPING`, `SPEC`, `RUN`, `LEDGER`, `RECON`, `TASK`, `WEBHOOK`, `USAGE`, `AUDIT`), replicas = 3, retention by limits/age per stream; durable pull consumers per consuming module; dedup window via `Nats-Msg-Id` = `event_id`. Services write events to a Postgres outbox in the same transaction as their data; an outbox relay publishes to JetStream |
| Redis-compatible cache | Rate limits, CDS cache, sessions, tunnel routing |
| Temporal | Durable workflow state for discovery, runs, reconciliation, human tasks |
| Git (internal) | Canonical models, spec history, generated code |

### 4.4 Event catalog (NATS subjects)
Subject naming: `<region>.<domain>.<entity>.<event>.v<N>.<tenant_id>`; ordering key = `tenant_id:<entity_id>`; envelope includes `event_id`, `tenant_id`, `region`, `occurred_at`, `actor`, `trace_id`, `schema_version`.

| Subject (without region/tenant tokens) | Producer | Main consumers |
|---|---|---|
| `tenant.org.created/updated` | Tenant | IAM, Billing, Audit |
| `tenant.hubspoke.linked/unlinked` | Tenant | Consent, Connect, Billing |
| `consent.granted/narrowed/revoked` | Consent | CDS, Connection, Orchestration, Audit |
| `connection.created/status_changed/health_changed` | Connection | Discovery, Hub API (webhooks), Notification |
| `discovery.started/tier_selected/completed/failed` | Discovery | CM Registry, Studio, Notification |
| `cm.version_published` / `cm.diff_detected` | CM Registry | Mapping, Spec Service, Ops Agent |
| `mapping.proposed/confirmed` | Mapping | CDS cache, Evaluation |
| `cdm.version_published` | Canonical Model Registry | Mapping, CDS, Spec Service |
| `spec.submitted/approved/activated/paused` | Spec Service | Compiler, Orchestration, Notification |
| `run.started/step_completed/succeeded/failed/dead_lettered` | Orchestration | Run History, State Ledger, Metering, Ops Agent |
| `ledger.object_transitioned` | State Ledger | Reconciler, Hub API |
| `money.posted` | Money Ledger | Reconciler, Billing (none), Hub API |
| `recon.completed` / `recon.break_detected/resolved` | Reconciler / Breaks | Breaks, Notification, Ops Agent, Hub API |
| `task.created/sent/answered/expired` | Human Task | Orchestration, Notification |
| `edge.agent_connected/disconnected/updated` | Tunnel Gateway | Connection, Notification |
| `webhook.received` | Webhook Ingress | Orchestration triggers |
| `usage.recorded` | All metered services | Billing |
| `audit.recorded` | All | Audit |

---

## 5. Key flows

### 5.1 Spoke onboarding and discovery
```mermaid
sequenceDiagram
  participant S as Spoke (Connect)
  participant CS as Connect Service
  participant CO as Consent
  participant CX as Connection
  participant D as Discovery Orchestrator
  participant I as Ingestion worker
  participant CM as CM Registry
  participant T as Mapping
  participant ST as Studio (review)
  S->>CS: open invite link
  CS->>CO: create consent request (hub, scopes)
  S->>CO: grant consent
  S->>CS: choose system / tier path
  CS->>CX: create connection (+credentials to KMS)
  CX-->>D: connection.created
  D->>I: run tier workers per entity (parallel)
  I->>CM: draft CM (provenance, confidence)
  CM-->>T: cm.version_published
  T->>T: mappings to canonical entities (confidence)
  alt low confidence items
    T-->>ST: review queue
    ST->>T: confirm/correct
  end
  D->>CX: status = ready
  CX-->>CS: connection.ready (webhook to hub)
```

### 5.2 Reading canonical data
```mermaid
sequenceDiagram
  participant H as Hub backend
  participant API as Hub Public API
  participant DS as Canonical Data Service
  participant CO as Consent
  participant MP as Mapping Service
  participant CR as Connector Runtime
  participant TG as Tunnel Gateway / Edge Agent
  H->>API: GET /v1/spokes/{id}/data/invoices?issued_from=...
  API->>DS: read(tenant, spoke, Invoice, filters)
  DS->>CO: allowed? (hub, spoke, Invoice)
  DS->>MP: active mapping for (spoke, Invoice) (cached)
  DS->>CR: call mapped source operation (filters translated)
  CR->>TG: tunnel request (if T3)
  CR-->>DS: source records
  DS->>DS: apply mapping, validate against CDM, add source metadata
  DS-->>API: canonical records + next cursor
  API-->>H: 200
```

### 5.3 Integration run with ledger
1. Trigger (webhook/schedule/CDC/API) → Orchestration starts workflow `run(spec_version, trigger_payload)`.
2. Each step is an activity: `fetch`/`write` via CDS, `map` via conversion engine, `human` via Human Task Service, `code` via Sandbox.
3. After each state-changing step, Orchestration calls State Ledger `transition(object_key, from, to, run_id, payload_hash)`; money effects call Money Ledger `post(entries)`.
4. Failures → retry policy → DLQ → `run.dead_lettered` → Ops Agent + notification.
5. Run History stores step records (masked) for UI and replay.

### 5.4 Reconciliation
1. Scheduled workflow per integration (`recon(spec_id)`), cursor-based over State Ledger objects within lookback.
2. For each batch: CDS fetches current views from each party (cached, rate-limited); compares tracked fields with tolerance.
3. Emits breaks; applies auto-heal policy (replay run / re-sync state) for allowed break types.
4. Updates agreement score; publishes `recon.completed`.

### 5.5 Drift
1. Discovery re-runs on schedule or on connector errors (e.g. 4xx schema errors).
2. CM Registry diffs versions → classifies changes (additive, breaking, mapping-affecting).
3. Breaking → Spec Service pauses affected specs; Ops Agent proposes fix; on approval, specs resume, paused runs replay.

### 5.6 Human task (T8a)
1. Step `human` → Human Task Service creates task with typed schema and channel preference.
2. Sends WhatsApp template / email with link to short form (or accepts free-text reply).
3. Reply → parser (LLM + rules) → typed values + confidence → validation → signal back to workflow.
4. Expiry → reminders → escalation → step fails per policy.

---

## 6. Edge Agent architecture

```
┌──────────────────────── Customer network ────────────────────────┐
│  Edge Agent (single Go binary, Windows service / systemd)         │
│  ├─ Tunnel client  ── outbound TLS 1.3 / mTLS, HTTP/2 multiplex ──┼──▶ Tunnel Gateway (Wasla)
│  ├─ Command router (signed commands only)                         │
│  ├─ DB drivers: SQL Server, MySQL, PostgreSQL, Oracle (P1)        │
│  ├─ CDC readers (log-based or watermark polling)                  │
│  ├─ File watcher (shared folders, exports)                        │
│  ├─ Generated API host (S2 services as sandboxed plugins)         │
│  ├─ Local buffer (SQLite, encrypted) + outbox                     │
│  ├─ Policy engine (allow-listed tables/ops, read-only default)    │
│  ├─ Local audit log (viewable by customer IT)                     │
│  └─ Auto-updater (signed releases, staged rollout, rollback)      │
└───────────────────────────────────────────────────────────────────┘
```

- Enrollment: one-time token from Connect → agent generates key pair → CSR signed by Wasla CA → mTLS identity bound to (tenant, connection).
- Every command from Wasla is signed and checked against the local policy (allowed tables, operations, row limits).
- Buffering: if the tunnel drops, CDC/events are kept locally (configurable size) and flushed in order.
- Customer can view the local audit log and pause the agent at any time.

---

## 7. Canonical model, mapping and Canonical Data Service

### 7.1 Canonical Data Model
- One CDM per vertical, stored as versioned JSON Schema documents in Git and published to the Canonical Model Registry.
- Each entity defines: fields (type, format, required, enum), identity keys, validation rules, a state machine (for tracked entities such as Invoice, Payment) and which fields are tracked for reconciliation.
- Embedded-finance CDM v0: `MerchantProfile`, `Customer`, `SalesSummary`, `Invoice`, `InvoiceLine`, `Payment`, `BankLine`, `PaymentStatus`.
- Compatibility rules: additive changes only within a major version; breaking changes create a new major version with migration of mappings.

### 7.2 Mapping
- Unit of mapping = **(connection, canonical entity)**.
- A mapping contains: the source operation(s) that supply the entity (list/get/write), filter translation (canonical filters → source parameters/SQL), field mapping expressions (expression language, JSONata-compatible syntax), enum maps, unit/currency/date conversions, and confidence per field.
- **Mapping templates per known system:** Odoo, Zoho, ETA, etc. are mapped once; every spoke on that system reuses the template, and only custom fields need new work.
- The Mapping Service proposes mappings with the mapping agent; low-confidence fields go to Studio review; confirmed mappings become templates and evaluation data.

### 7.3 Canonical Data Service (CDS)
| Component | Responsibility |
|---|---|
| **Source selector** | Picks the connection mapped for the entity (primary from Discovery) and the ordered fallbacks |
| **Consent check** | Rejects reads/writes outside the hub's consent scopes |
| **Filter translator** | Converts canonical filters and pagination to the source operation |
| **Executor** | Calls the Connector Runtime; streams pages; timeouts and retries for direct API calls; runs as workflow activity inside integration runs |
| **Mapper** | Applies the field mapping and conversions; validates output against the CDM |
| **Source metadata** | Adds connection, tier, fetched-at and (for T7/T8) confidence to every record |
| **Cache** | Key `(connection, entity, normalized filters)`; TTL by tier; invalidated by CDC events |
| **Writer** | Applies reverse mapping, selects target operation, dry-run, idempotency key |

---

## 8. Security architecture

| Layer | Controls |
|---|---|
| Identity | IAM issues short-lived JWT access tokens (5–15 min) + refresh; API keys hashed (argon2id); MFA; SSO (P1) |
| Authorization | Policy engine in each service via shared library: RBAC + tenant + consent scopes + environment; deny by default |
| Service mesh | mTLS between services; workload identities; network policies per namespace |
| Secrets | KMS service with envelope encryption: root key in HSM/cloud KMS per region → tenant key → data keys; credentials never leave KMS unencrypted except to the Connector Runtime process in memory |
| Data at rest | Disk encryption + application-level encryption for credentials, run payloads, PII columns |
| PII | Classifier tags PII fields in CMs; masking in logs, run history, UI previews, LLM prompts; reversible tokenization for LLM context where needed |
| Tenant isolation | Tenant id on every row with row-level security in Postgres; per-tenant encryption keys; per-tenant rate limits; optional dedicated cells for enterprise |
| Edge | Outbound-only; signed commands; local policy; signed updates; customer-visible audit |
| Supply chain | Signed builds, SBOM, dependency scanning, reproducible Edge Agent builds |
| Monitoring | Security events to SIEM; anomaly detection on data access per tenant |
| Staff access | Just-in-time elevation, approval, session recording, audit |

---

## 9. Deployment architecture

### 9.1 Topology
- **Region cell** = one Kubernetes cluster (3 AZs or 3 failure domains) + regional Postgres HA + NATS JetStream cluster + object store + Temporal cluster + KMS. Egypt cell first; KSA cell in Phase 3.
- **Global control plane (minimal):** tenant directory (tenant → region routing), billing aggregation, Studio access, docs. Holds no customer business data.
- **Cells for scale/enterprise:** a region can run multiple cells; tenants are assigned to a cell; dedicated cells for enterprise.

```
            ┌─────────── Global ───────────┐
            │ Tenant directory · Billing   │
            │ Docs · Status page · Studio  │
            └───────┬──────────────┬───────┘
                    │              │
        ┌───────────▼───┐   ┌──────▼────────┐
        │ Egypt cell(s) │   │ KSA cell(s)   │  (Phase 3)
        │ K8s · PG · EL │   │ K8s · PG · EL │
        │ Temporal · OS │   │ Temporal · OS │
        └───────────────┘   └───────────────┘
```

### 9.2 Environments
`dev` (shared, ephemeral PR environments) → `staging` (prod-like, synthetic tenants) → `sandbox` (customer-facing sandbox, per region) → `production`.

### 9.3 Kubernetes layout
| Namespace | Contents |
|---|---|
| `edge` | API Gateway, Webhook Ingress, Tunnel Gateway |
| `platform` | IAM, Tenant, Consent, KMS, Region, Audit, Notification, Billing, Search |
| `connectivity` | Connection, Discovery, ingestion workers, Connector Runtime, Country Connectors, API Generator |
| `canonical` | CM Registry, Canonical Model Registry, Mapping, CDS |
| `integration` | Spec Service, Compiler, Orchestration workers, Run History, Verification |
| `agreement` | State Ledger, Money Ledger, Reconciler, Breaks |
| `human` | Human Tasks, Micro-app Platform |
| `ai` | LLM Gateway, Agent Runtime, Evaluation, Sandbox (isolated node pool), Ops Agent |
| `ux` | Hub API, Console BFF, Connect Service, Developer Portal |
| `infra` | Temporal, NATS JetStream, cache, observability |

### 9.4 Delivery
Monorepo → CI (lint, test, build, scan, SBOM) → images signed → GitOps (desired state repo per environment) → progressive delivery (canary 5% → 25% → 100% with SLO-based automatic rollback). Database migrations: expand/contract, backward compatible for one release.

---

## 10. Reliability patterns

| Pattern | Where |
|---|---|
| Idempotency keys | All writes to parties; all API POSTs; ledger postings |
| Transactional outbox | Every service publishing events from DB changes; outbox relay publishes to JetStream with `Nats-Msg-Id` for dedup |
| Inbox / dedup | Every JetStream consumer (processed-event table); explicit ack, max deliver, backoff, DLQ subject per consumer |
| Retries with exponential backoff + jitter | Connector Runtime, webhooks out, workflow activities |
| Dead-letter + replay | Runs, webhook deliveries, event consumers |
| Circuit breaker | Per connection and per upstream host |
| Bulkheads | Per-tenant worker quotas; separate pools for agent workloads |
| Back-pressure | Rate limits per connection; queue depth-based throttling |
| Per-key ordering | JetStream preserves order per subject; consumers process per key with `max_ack_pending` tuned; one Temporal workflow per key where strict ordering is required |
| Timeouts everywhere | Default budgets per call type |
| Graceful degradation | CDS falls back to the next mapped connection; clear error when none is available |
| Chaos testing | Monthly game days in staging (tunnel loss, DB failover, NATS node loss, Temporal loss) |

---

## 11. Observability

- **Tracing:** every request/run carries `trace_id`, `tenant_id`, `connection_id`, `run_id`; spans across CDS → Connector → Edge.
- **Metrics:** RED per service; business metrics (connections by tier/status, runs, breaks, agreement score); SLO burn-rate alerts.
- **Logs:** structured JSON, PII-masked, tenant-tagged; retention per region policy.
- **Customer-facing:** run history, connection health, Edge Agent status, breaks, agreement score inside consoles (never raw internal dashboards).
- **Agent observability:** every LLM call logged with prompt version, model, tokens, latency, cost, masked inputs/outputs, evaluation links.

---

## 12. Technology stack

| Concern | Choice |
|---|---|
| Core services | TypeScript (Node.js LTS), framework: Fastify + internal service kit |
| Agent & analysis services | Python 3.12, FastAPI + internal agent kit |
| Performance/edge services | Go (Gateway, Tunnel, KMS, Ledgers, Edge Agent, Sandbox, Audit) |
| Frontend | React + TypeScript, internal design system, i18n with RTL |
| Workflows | Temporal (TS and Python SDKs), wrapped by internal `durable` library |
| Database | PostgreSQL 16+ with partitioning, RLS, vector column type |
| Events | NATS JetStream (Postgres outbox → relay → JetStream; durable pull consumers) (ADR-011) |
| Cache | Redis-compatible |
| Object store | S3-compatible |
| Infra | Kubernetes, Helm charts, GitOps controller, IaC |
| Canonical model | JSON Schema per entity + state machine definitions |
| Mapping/conversion | Internal expression language (JSONata-compatible syntax) |
| API contracts | OpenAPI 3.1 for REST, AsyncAPI for events, JSON Schema for payloads |

---

## 13. Repository and code organization

```
wasla/
├─ apps/                      # deployable services and UIs
│  ├─ gateway/  tunnel-gateway/  webhook-ingress/            (Go)
│  ├─ iam/  tenant/  consent/  region/  notification/  billing/  search/   (TS)
│  ├─ kms/  audit/  state-ledger/  money-ledger/  sandbox/   (Go)
│  ├─ connection/  discovery/  connector-runtime/  country-connectors/     (TS)
│  ├─ ingest-spec/ (TS)  ingest-db/ website-to-api/ ingest-documents/ (Py)  · deferred: ingest-docs/ ingest-code/
│  ├─ api-generator/  (Py+TS)
│  ├─ cm-registry/  cdm-registry/  canonical-data/          (TS)
│  ├─ mapping/  designer-agent/  ops-agent/  llm-gateway/  agent-runtime/  evaluation/ (Py)
│  ├─ spec-service/  spec-compiler/  orchestration/  run-history/  verification/ (TS)
│  ├─ reconciler/  breaks/  human-tasks/  microapps/        (TS)
│  ├─ hub-api/  console-bff/  connect-service/              (TS)
│  ├─ web-hub-console/  web-spoke-portal/  web-studio/  web-connect/  web-dev-portal/ (React)
│  └─ edge-agent/                                           (Go)
├─ packages/                  # shared libraries
│  ├─ service-kit-ts/  service-kit-py/  service-kit-go/     # auth, tenancy, logging, tracing, outbox/inbox
│  ├─ contracts/              # OpenAPI, AsyncAPI, JSON Schemas, generated clients
│  ├─ durable/                # workflow wrappers, activity helpers
│  ├─ expr/                   # conversion expression language
│  ├─ policy/                 # authz library
│  ├─ design-system/  i18n/
│  └─ sdk-ts/  sdk-py/
├─ canonical-models/          # embedded-finance/, retail/ ... (JSON Schema)
├─ country-packs/             # eg/, sa/
├─ infra/                     # IaC, Helm charts, GitOps env repos
├─ evals/                     # golden datasets, eval configs
└─ docs/                      # ADRs, runbooks, API docs
```

---

## 14. API conventions

- REST, JSON, `/v1/...`, resource-oriented; cursor pagination (`?cursor=&limit=`); filtering via query params; `Idempotency-Key` header required on POST that creates or writes.
- Errors: RFC 9457 problem details with `code`, `detail`, `trace_id`.
- Webhooks: signed with HMAC-SHA256 (`Wasla-Signature: t=..., v1=...`), at-least-once, retries for 72 h with backoff, replay from console/API.
- Versioning: additive changes in place; breaking changes → new major version with 12-month overlap.
- Rate limits: per API key and per tenant; headers `RateLimit-*`.
- Internal APIs: same conventions, plus service identity and `X-Tenant-Id`, `X-Region` propagated.

---

## 15. Architecture decision log (initial)

| ADR | Decision |
|---|---|
| ADR-001 | Region cells with a minimal global directory |
| ADR-002 | Postgres per service schema; no cross-service joins |
| ADR-003 | Events via transactional outbox; consumers idempotent |
| ADR-004 | Durable workflows on Temporal, wrapped by internal `durable` library |
| ADR-005 | Canonical Data Model per vertical; each connection mapped once to it |
| ADR-006 | Canonical Data Service reads/writes one mapped source per entity with ordered fallbacks |
| ADR-007 | In-house State Ledger and Money Ledger (Go, append-only Postgres) |
| ADR-008 | Edge Agent in Go, outbound-only, signed commands |
| ADR-009 | All agents behind LLM Gateway with mandatory PII Guard |
| ADR-010 | Monorepo with shared service kits per language |
| ADR-011 | NATS JetStream is the event backbone from day one (not Kafka): light to operate, request/reply, accounts for tenant isolation, replay, and leaf nodes for edge connectivity. Postgres outbox + relay keeps publishing atomic with data changes; consumers are idempotent. Durable multi-step processing stays in Temporal. All producers/consumers use the `events` interface in the service kits |
