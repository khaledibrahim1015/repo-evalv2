# 03 — Service Specifications

*Version 2.0 · October 8, 2026 · Companion to [02-architecture.md](02-architecture.md)*

Every service follows the same contract:
- Built on the language **service kit** (auth, tenancy, region, logging, tracing, metrics, outbox/inbox, health, config, feature flags).
- Exposes `/healthz`, `/readyz`, `/metrics`; OpenAPI (sync) and AsyncAPI (events) contracts in `packages/contracts`.
- Owns its Postgres schema; publishes events via outbox; consumes events idempotently.
- Tenant id and region on every request, row, event, log line.

Format per service: **Purpose · Responsibilities · API · Events (pub / sub) · Data · Depends on · Scale & SLO · Phase**.

---

## Edge layer

### S01 — API Gateway
- **Purpose:** single entry for public API, consoles, Connect.
- **Responsibilities:** TLS termination; routing by path/host; JWT and API key validation (via IAM introspection cache); rate limiting per key/tenant/IP; request size limits; CORS; WAF rules; tenant → region cell routing via tenant directory; request id + trace injection.
- **API:** configuration only (routes declared in GitOps).
- **Events:** pub `usage.recorded` (API calls).
- **Data:** Redis (rate-limit counters, key cache).
- **Depends on:** IAM, Tenant directory.
- **Scale & SLO:** stateless, HPA on RPS; p99 overhead < 10 ms; 99.95%.
- **Phase:** 0.

### S02 — Webhook Ingress
- **Purpose:** receive webhooks from spoke systems and external providers durably.
- **Responsibilities:** unique endpoint per connection (`/in/{connection_token}`); signature verification per provider; persist raw payload to object store + publish to JetStream (ack from JetStream) before 2xx; dedup by provider event id; payload size and rate limits.
- **API:** `POST /in/{token}`; internal `GET /internal/webhooks/{id}`.
- **Events:** pub `webhook.received`.
- **Data:** object store (raw payloads, encrypted); small Postgres table for endpoint registry.
- **Depends on:** Connection, KMS.
- **Scale & SLO:** stateless; ack p99 < 200 ms; zero loss after ack.
- **Phase:** 1.

### S03 — Tunnel Gateway
- **Purpose:** terminate Edge Agent tunnels and route commands to them.
- **Responsibilities:** mTLS authentication of agents; HTTP/2 multiplexed streams; agent registry (which pod holds which agent); command routing with request/response correlation; heartbeats; back-pressure; version reporting; staged update orchestration.
- **API:** agent-facing tunnel endpoint; internal `POST /internal/agents/{id}/commands`, `GET /internal/agents/{id}`.
- **Events:** pub `edge.agent_connected/disconnected/updated`.
- **Data:** Redis (agent → pod routing), Postgres (agent registry, versions).
- **Depends on:** KMS (CA), Connection.
- **Scale & SLO:** sticky connections, horizontal by agent count (target 2,000 agents/pod); 99.95%.
- **Phase:** 2.

---

## Platform services

### S04 — Identity & Access (IAM)
- **Purpose:** users, authentication, tokens, API keys, roles.
- **Responsibilities:** sign-up/invite; password (argon2id), magic link, TOTP MFA; sessions; OIDC provider for consoles; SSO federation (OIDC/SAML, P1); JWT issuance and JWKS; API keys (hashed, scoped, per environment); roles and permissions; service identities; break-glass staff access with approval.
- **API:** `/v1/auth/*` (login, refresh, logout, mfa), `/v1/users`, `/v1/invitations`, `/v1/api-keys`, `/v1/roles`, `/.well-known/jwks.json`, internal `/internal/introspect`.
- **Events:** pub `iam.user.*`, `iam.apikey.*`, `audit.recorded`; sub `tenant.org.created`.
- **Data:** users, credentials, memberships, roles, api_keys, sessions, sso_configs.
- **Depends on:** Tenant, Notification (emails), KMS.
- **Scale & SLO:** login p95 < 300 ms; introspection cached; 99.95%.
- **Phase:** 0 (core), 1 (MFA, API keys), 3 (SSO, custom roles).

### S05 — Tenant & Party
- **Purpose:** organizations, workspaces, environments, hub–spoke relationships, tenant directory.
- **Responsibilities:** org CRUD (kind hub/spoke/both, legal identity, tax ids, region); workspaces and environments (sandbox/production); hub–spoke links with lifecycle (invited → active → suspended → ended); spoke identity resolution (avoid duplicates: same tax id → same spoke org); tenant directory (tenant → region/cell).
- **API:** `/v1/organizations`, `/v1/workspaces`, `/v1/spokes` (hub view), `/v1/hubs` (spoke view), internal `/internal/directory/{tenant}`.
- **Events:** pub `tenant.org.created/updated`, `tenant.hubspoke.linked/unlinked`.
- **Data:** organizations, workspaces, environments, hub_spoke_links, directory.
- **Depends on:** Region.
- **Scale & SLO:** p95 < 100 ms reads.
- **Phase:** 0.

### S06 — Consent
- **Purpose:** spokes' grants to hubs.
- **Responsibilities:** consent requests (hub, purpose, scopes = data products/canonical entities, duration); grant/narrow/revoke; evaluation API (is access to entity X for (hub, spoke) allowed?); consent receipts (signed); expiry jobs; history.
- **API:** `/v1/consents`, `/v1/consents/{id}/grant|revoke|narrow`, `/v1/consents/{id}/receipt`, internal `POST /internal/consent/evaluate` (batch).
- **Events:** pub `consent.requested/granted/narrowed/revoked/expired`.
- **Data:** consent_requests, consents, consent_scopes, consent_events.
- **Depends on:** Tenant, Canonical Model Registry (scope validation), KMS (signing).
- **Scale & SLO:** evaluate p99 < 20 ms (local cache invalidated by events); revocation effective < 60 s.
- **Phase:** 1.

### S07 — Secrets & Keys (KMS)
- **Purpose:** key hierarchy and credential vault.
- **Responsibilities:** regional root key (HSM/cloud KMS) → tenant keys → data keys; encrypt/decrypt APIs; credential storage with versioning and rotation; Wasla internal CA for mTLS (services, Edge Agents); signing keys (webhooks, receipts, proof exports, Edge commands); access policy per caller service; audit of every decrypt.
- **API:** internal only: `/internal/keys/*`, `/internal/secrets/{ref}` (put/get/rotate), `/internal/sign`, `/internal/ca/sign-csr`.
- **Events:** pub `audit.recorded`.
- **Data:** encrypted secrets, key metadata, certificate registry.
- **Depends on:** root key provider.
- **Scale & SLO:** p99 < 15 ms; 99.99%; strict network isolation.
- **Phase:** 0.

### S08 — Region & Country Pack
- **Purpose:** region configuration and country-specific behavior as data.
- **Responsibilities:** regions and cells registry; country packs (tax id formats/validators, currencies, calendars/holidays, language defaults, e-invoicing connector binding, residency rules, LLM processing rules); feature flags per region.
- **API:** `/internal/regions`, `/internal/country-packs/{code}`.
- **Events:** pub `region.pack_published`.
- **Data:** regions, cells, packs (versioned).
- **Phase:** 1 (EG), 3 (SA).

### S09 — Audit
- **Purpose:** immutable audit trail.
- **Responsibilities:** ingest `audit.recorded` from all services; append-only storage with hash chaining per tenant/day; query and export for tenants (their own records) and staff; retention 7 years with tiering to object store.
- **API:** `/v1/audit-events` (tenant-scoped query), `/v1/audit-exports`.
- **Events:** sub `audit.recorded`.
- **Data:** audit_events (partitioned by month), chain anchors.
- **Scale & SLO:** ingest 5k events/s; query p95 < 1 s for 30-day windows.
- **Phase:** 0.

### S10 — Notification
- **Purpose:** deliver messages to people.
- **Responsibilities:** templates (Arabic/English) with versioning; channels: email, WhatsApp Business (template messages), SMS, in-app; user preferences and quiet hours; delivery tracking; provider failover.
- **API:** internal `POST /internal/notifications`; `/v1/notifications` (in-app inbox), `/v1/notification-preferences`.
- **Events:** sub many (`connection.*`, `recon.break_detected`, `run.dead_lettered`, `task.*`); pub `notification.delivered/failed`.
- **Data:** templates, messages, deliveries, preferences.
- **Phase:** 1.

### S11 — Billing & Metering
- **Purpose:** usage metering, plans, invoicing.
- **Responsibilities:** consume `usage.recorded`; aggregate per tenant/meter/day (connected spokes, runs, queries, reconciled objects, human tasks, LLM cost); plans and entitlements (limits enforced via feature flags); invoice generation; local payment provider integration; usage dashboards.
- **API:** `/v1/usage`, `/v1/plans`, `/v1/subscriptions`, `/v1/invoices`; internal `/internal/entitlements/{tenant}`.
- **Events:** sub `usage.recorded`, `tenant.*`; pub `billing.invoice_issued`, `billing.entitlement_changed`.
- **Phase:** 1 (metering), 3 (billing).

### S49 — Search
- **Purpose:** search across tenant objects and canonical entities.
- **Responsibilities:** index spokes, connections, specs, runs (metadata), breaks, canonical entities, fields; full-text (Arabic/English analyzers) + vector similarity; tenant-scoped.
- **API:** `/v1/search?q=`; internal indexing via events.
- **Phase:** 2.

---

## Connectivity

### S12 — Connection Service
- **Purpose:** lifecycle of connections to party systems and channels.
- **Responsibilities:** create connection (system kind, tier path); credential capture → KMS; OAuth flows (authorize URL, callback, refresh scheduler); auth methods (API key, basic, OAuth2, mTLS, custom); health checks; status machine (draft → authorizing → discovering → review → ready → degraded → paused → revoked); known-systems catalog (Odoo, Zoho, QuickBooks, Dynamics, SAP B1, local ERPs) with auth templates; webhook endpoint provisioning (S02).
- **API:** `/v1/connections`, `/v1/connections/{id}` (get/patch/delete), `/v1/connections/{id}/authorize`, `/oauth/callback`, `/v1/connections/{id}/health`, `/v1/systems` (catalog).
- **Events:** pub `connection.created/status_changed/health_changed/credentials_rotated`; sub `edge.agent_*`, `discovery.completed`, `consent.revoked`.
- **Data:** connections, auth_configs, oauth_states, health_checks, systems_catalog.
- **Depends on:** KMS, Tenant, Consent, Tunnel Gateway.
- **Phase:** 1.

### S13 — Discovery Orchestrator
- **Purpose:** run the Connectivity Ladder and produce CMs.
- **Responsibilities:** per connection, durable discovery workflow; decide which tier workers to run per target entity (from data products requested); collect worker outputs; merge into CM draft with provenance/confidence; select best tier per entity (rules + scores); schedule re-discovery; detect better paths and propose upgrades; escalate to Studio review.
- **API:** `/v1/connections/{id}/discovery` (start, status), internal `/internal/discovery/runs/{id}`.
- **Events:** pub `discovery.started/tier_selected/completed/failed/upgrade_available`; sub `connection.created`, `cm.diff_detected`, connector error signals.
- **Data:** discovery_runs, tier_decisions, worker_results (refs).
- **Depends on:** ingestion workers S14–S19, S21, CM Registry, Mapping.
- **Phase:** 1 (T1, T6, T7, T8b), 2 (T3, T5, T8a, upgrades).

### S14 — Spec Ingestor (T1)
- **Purpose:** ingest machine-readable API descriptions.
- **Responsibilities:** OpenAPI 2/3.x parse, validate, dereference, normalize; Postman v2.x → OpenAPI; GraphQL introspection → operations (P1); WSDL → operations (P1); infer pagination, auth, error shapes, rate-limit headers; examples → schemas; produce CM fragment.
- **API:** internal `POST /internal/ingest/spec` (artifact ref) → CM fragment.
- **Data:** object store artifacts.
- **Phase:** 1.

### S15 — Doc Reader (T2)
- **Purpose:** turn human API documentation into a draft spec.
- **Responsibilities:** crawl portal URLs (headless browser), parse PDF/HTML; extract endpoints, params, schemas, auth; generate draft OpenAPI with confidence per item; probe endpoints with test credentials (read-only, safe methods) to confirm.
- **API:** internal `POST /internal/ingest/docs`.
- **Depends on:** Agent Runtime, LLM Gateway, Connector Runtime (probes).
- **Phase:** Deferred (delivery plan §8).

### S16 — DB Introspector (T3)
- **Purpose:** describe databases reachable through the Edge Agent.
- **Responsibilities:** schema introspection (tables, columns, types, PK/FK, indexes, enums, views); row samples (limited, masked); entity inference (which tables are customers, invoices, …) using names, keys, samples; PII detection; change-tracking options (CDC availability, timestamp columns); generate read operations (queries) as CM operations.
- **API:** internal `POST /internal/ingest/db`.
- **Depends on:** Tunnel Gateway, Agent Runtime.
- **Phase:** 2.

### S17 — Code Analyzer (T4)
- **Purpose:** find business operations in a codebase.
- **Responsibilities:** clone read-only (or receive archive from Edge Agent); parse with language parsers (PHP/Laravel, C#/.NET, JS/TS-Node first); extract routes, controllers, services, ORM models, DB writes; agent identifies business operations and side effects; output CM operations (internal) and input to API Generator.
- **API:** internal `POST /internal/ingest/code`.
- **Depends on:** Code Sandbox, Agent Runtime.
- **Phase:** Deferred (delivery plan §8).

### S18 — Website-to-API (T5)
- **Purpose:** turn any website a merchant uses (cloud ERP, portal) into an API, with the merchant's consent.
- **Responsibilities:** browser helper records a guided session (HAR + cookies) with PII redaction; analysis of request chains, auth/session handling and CSRF, preferring internal network calls over screen clicks; **site profiles**: one reusable profile per website/platform shared by all merchants on it; isolated headless browser runner for flows that need screen automation; **session vault** (credentials in KMS, session refresh, OTP/captcha requested from the merchant via WhatsApp); **self-healing**: synthetic checks per profile, change detection, agent re-derives the profile, review before rollout; read-only first; per-site legal/ToS checklist before enabling.
- **API:** internal `POST /internal/web/profiles`, `POST /internal/web/sessions`, `POST /internal/web/execute`; Studio `/v1/studio/site-profiles`.
- **Events:** pub `web.profile_broken`, `web.profile_healed`, `web.otp_requested`.
- **Data:** site profiles (versioned), sessions (encrypted refs), check results.
- **Depends on:** KMS, Human Task Service (OTP via WhatsApp), Code Sandbox (runner isolation), Agent Runtime, Connector Runtime.
- **Phase:** 2.

### S19 — Document Extractor (T7)
- **Purpose:** typed records from Excel/CSV/PDF/images/emails.
- **Responsibilities:** dedicated inbox per connection; upload endpoint; Excel/CSV structure detection (header row, merged cells, multiple tables, Arabic headers); PDF/image OCR (Arabic + English); template learning per spoke (same layout next time = no LLM); extraction to records with confidence; dedup; produce CM (from first files) and data (from each file).
- **API:** `POST /v1/connections/{id}/uploads`; inbound email handler; internal `/internal/extract`.
- **Events:** pub `documents.extracted`, `documents.needs_review`.
- **Phase:** 1 (Excel/CSV), 2 (PDF/images/email).

### S20 — Connector Runtime
- **Purpose:** execute operations against party systems.
- **Responsibilities:** generic adapters: HTTP/REST, GraphQL, SOAP, SQL (via Edge), file (via Edge), document-backed (T7 datasets), human-backed (T8 via Human Tasks), micro-app (T8b); auth injection from KMS; pagination strategies; retries, timeouts, circuit breakers, rate limits per connection; response normalization to CM schemas; request/response capture (masked) for debugging.
- **API:** internal `POST /internal/execute` `{connection_id, operation_id, inputs, idempotency_key}`.
- **Events:** pub `usage.recorded`, `connector.error_pattern`.
- **Data:** Redis (limits, breaker state).
- **Scale & SLO:** stateless; overhead p95 < 30 ms.
- **Phase:** 1.

### S21 — Shared-source Connectors (T6)
- **Purpose:** data about merchants held outside the merchant: tax portals, banks, the hub itself.
- **Responsibilities:** **Egypt ETA**: e-invoice and e-receipt APIs (authentication with taxpayer client credentials, document search, document details, submission status), mapping templates to the embedded-finance canonical model; **KSA ZATCA** (Phase 3); bank statement ingestion (MT940/CAMT/CSV/Excel) and open-banking providers when available; **hub-data connector** for the fintech's own records per merchant (transactions, collections); marketplace connectors (P2).
- **API:** registered as connectors in Connector Runtime + CM templates.
- **Phase:** 1 (ETA, bank statements, hub data), 3 (ZATCA), 5 (marketplaces).

### S22 — Edge Agent
- **Purpose:** secure presence inside customer networks.
- **Responsibilities:** see architecture §6: enrollment, tunnel, signed commands, local policy, DB drivers, CDC, file watcher, generated-API host, buffer/outbox, local audit, auto-update, local status UI (`localhost` page), diagnostics bundle.
- **Platforms:** Windows Server 2012 R2+ (service), Linux x64/arm64 (systemd), Docker image.
- **Phase:** 2 (tunnel, SQL Server/MySQL/PostgreSQL read, buffer, update, then CDC, Oracle, files). Hosted APIs deferred.

### S23 — API Generator (S2)
- **Purpose:** create an API where none exists.
- **Responsibilities:** from DB CM: generate curated read endpoints + specific write endpoints (stored procedure or table writes with validation) as an Edge-hosted plugin; from code CM: generate a thin API layer in the customer's stack calling their functions, delivered as PR or Edge plugin; generate OpenAPI + tests; run tests in Sandbox against a cloned/staging DB; publish result back as T1 capability.
- **API:** internal `POST /internal/apigen/jobs`, `GET /internal/apigen/jobs/{id}`.
- **Depends on:** Code Sandbox, Agent Runtime, Verification, Tunnel Gateway.
- **Phase:** Deferred (delivery plan §8).

---

## Canonical data

### S24 — Capability Model Registry
- **Purpose:** source of truth for CMs.
- **Responsibilities:** store CM versions per connection (OpenAPI 3.1 + `x-wasla-*` extensions: entity, provenance, confidence, tier, pii, rate limits, events); validation; diff between versions and change classification (additive / breaking / mapping-affecting); query APIs for Mapping and CDS (operations by entity); PII classification storage.
- **API:** `/internal/cms/{connection}/versions`, `/internal/cms/{connection}/diff?from&to`, `/internal/cms/operations?entity=`; Studio read APIs.
- **Events:** pub `cm.version_published`, `cm.diff_detected`.
- **Data:** cm_versions (JSONB), operations index, field index.
- **Phase:** 1.

### S25 — Canonical Model Registry
- **Purpose:** source of truth for each vertical's Canonical Data Model.
- **Responsibilities:** JSON Schema entity definitions in Git per vertical; state machines and reconciliation-tracked fields per entity; validation and compatibility checks (additive within a major version); publish/version; lookup APIs; embeddings per entity/field (names, docs, examples) for the mapping agent.
- **API:** `/internal/cdm?vertical=&version=`, `/internal/cdm/entities/{name}`, Studio `/v1/studio/canonical-models/*`; CLI `wasla cdm validate|publish`.
- **Events:** pub `cdm.version_published`.
- **Phase:** 0.

### S26 — Mapping Service
- **Purpose:** map each connection's CM to canonical entities.
- **Responsibilities:** per (connection, entity): choose source operations (list/get/write); candidate field matches (names/descriptions, embeddings, data types, value patterns, samples); mapping agent proposes field expressions, enum maps, conversions and filter translation; confidence per field; review queue; **mapping templates per known system** reused across spokes; learning from confirmations; re-mapping proposals on CM diff or CDM version change.
- **API:** internal `POST /internal/mapping/jobs`, `GET /internal/mapping/{connection}/{entity}`; Studio `/v1/studio/mapping-reviews` (list, accept, correct, bulk), `/v1/studio/mapping-templates`.
- **Events:** pub `mapping.proposed/confirmed`; sub `cm.version_published`, `cm.diff_detected`, `cdm.version_published`.
- **Data:** mappings (versioned), mapping_reviews, templates, embeddings.
- **Phase:** 1.

### S27 — Canonical Data Service (CDS)
- **Purpose:** read and write canonical entities for a party.
- **Responsibilities:** see architecture §7.3: source selection with ordered fallbacks, consent check, filter translation, execution through Connector Runtime, mapping and CDM validation, source metadata per record, cache, writes with reverse mapping, dry-run and idempotency; change feed (P2).
- **API:** `GET /internal/cds/{party}/{entity}` (list with filters/cursor), `GET /internal/cds/{party}/{entity}/{id}`, `POST /internal/cds/{party}/{entity}` (write, `dry_run`); exposed publicly through Hub API as `/v1/spokes/{id}/data/{entity}`.
- **Events:** pub `usage.recorded`, `cds.entity_unavailable`; sub `mapping.confirmed`, `cm.version_published`, `consent.*`, CDC topics (cache invalidation).
- **Scale & SLO:** stateless with shared cache; overhead p95 < 50 ms; end-to-end p95 < 2 s (T1/T3).
- **Phase:** 1.

---

## Integration

### S28 — Integration Spec Service
- **Purpose:** author, version, approve and activate specs.
- **Responsibilities:** CRUD of specs (YAML) per hub–spoke link or per hub template; data-product templates (hub-level templates applied to each spoke automatically); validation (schema + CM + mappings + canonical model + consent); versioning in Git; approval workflow (both parties; policies for auto-approval of template instances); activation/pause/rollback; diff views.
- **API:** `/v1/integrations`, `/v1/integrations/{id}/versions`, `/v1/integrations/{id}/approve|activate|pause|rollback`, `/v1/data-products`.
- **Events:** pub `spec.submitted/approved/activated/paused/rolled_back`; sub `cm.diff_detected` (pause on breaking), `consent.revoked`.
- **Phase:** 1.

### S29 — Designer Agent
- **Purpose:** turn intent into a spec.
- **Responsibilities:** input business intent + parties' CMs + canonical model; produce spec draft, test fixtures and explanation; iterate on validation errors; never activates.
- **API:** internal `POST /internal/designer/drafts`.
- **Phase:** 2.

### S30 — Spec Compiler
- **Purpose:** compile specs into executable workflow definitions.
- **Responsibilities:** parse YAML → IR; resolve step references; static checks (entities mapped for the parties, idempotency keys present for writes, reconciliation config valid); generate workflow plan for Orchestration (interpreted IR, not code generation); generate reconciliation job config; generate mocks/test plans for Verification.
- **API:** internal `POST /internal/compile`.
- **Phase:** 1.

### S31 — Orchestration Runtime
- **Purpose:** execute runs durably.
- **Responsibilities:** generic interpreter workflow executing compiled IR; trigger adapters (webhook events, schedules, polls, CDC events, API calls, human task replies); activities: CDS fetch/write, convert, human task, code (sandbox), ledger transition/post, notify; retry policies, timeouts, DLQ, per-key ordering (workflow id = key), concurrency limits per tenant/connection; pause/resume; replay.
- **API:** internal `/internal/runs` (start, signal, cancel), triggers via events.
- **Events:** pub `run.*`, `usage.recorded`; sub `webhook.received`, `spec.activated/paused`, `task.answered`, CDC topics.
- **Data:** Temporal + Postgres (trigger registry, schedules).
- **Scale & SLO:** worker pools per namespace; 50M runs/month at Month 24; start p95 < 1 s.
- **Phase:** 1.

### S32 — Run History & Replay
- **Purpose:** visibility and recovery.
- **Responsibilities:** store run and step records (status, timings, masked inputs/outputs refs); search/filter; replay single/bulk from a step with new spec version; DLQ management; retention policies.
- **API:** `/v1/runs`, `/v1/runs/{id}`, `/v1/runs/{id}/replay`, `/v1/dead-letters`, `/v1/dead-letters/replay`.
- **Events:** sub `run.*`; pub `run.replay_requested`.
- **Data:** runs, steps (partitioned by day); payloads in object store.
- **Phase:** 1.

### S33 — Verification Service
- **Purpose:** prove an integration before go-live.
- **Responsibilities:** generate mocks from CMs; contract tests (spec steps vs CMs); golden tests for mappings from samples; recorded payload replay in sandbox; fuzz/property tests for generated APIs (P2); test reports attached to spec versions; go-live gate evaluation.
- **API:** internal `POST /internal/verify/{spec_version}`; `/v1/integrations/{id}/versions/{v}/test-report`.
- **Phase:** 1.

---

## Agreement

### S34 — State Ledger
- **Purpose:** record every cross-party object and its history.
- **Responsibilities:** tracked objects (model, canonical key, parties' external ids, current state); state machines per entity (defined in the canonical model/spec); append-only transitions (from, to, source party, run id, payload hash, time); per-party observed views (last seen hash, time); hash-chained entries per object; queries by key/state/time; export.
- **API:** internal `POST /internal/ledger/transition`, `POST /internal/ledger/observe`, `GET /internal/ledger/objects`; public read via Hub API `/v1/objects`.
- **Events:** pub `ledger.object_transitioned`.
- **Data:** objects, transitions (partitioned), observations.
- **Scale & SLO:** 5k writes/s per cell; p99 write < 20 ms.
- **Phase:** 1.

### S35 — Money Ledger
- **Purpose:** double-entry ledger for value.
- **Responsibilities:** accounts (per tenant, hierarchical names e.g. `parties:{spoke}:receivable`), multi-currency; transactions with balanced postings; immutability (reversal entries only); balances (current and as-of); idempotent posting; metadata linking to tracked objects; posting templates from specs.
- **API:** internal `POST /internal/money/transactions`, `GET /internal/money/accounts/{a}/balance?asOf=`, `GET /internal/money/transactions`; public read via Hub API.
- **Events:** pub `money.posted`.
- **Data:** accounts, transactions, postings (partitioned), balance snapshots.
- **Phase:** 2.

### S36 — Reconciler
- **Purpose:** detect disagreement.
- **Responsibilities:** schedule recon jobs per integration (cron from spec); cursor through ledger objects within lookback; fetch parties' current views via CDS in batches; compare tracked fields with tolerance; classify breaks; auto-heal per policy (request replay/resync); compute agreement scores; payment matching rules + agent suggestions for orphan money (P1).
- **API:** internal `/internal/recon/jobs`; `/v1/integrations/{id}/agreement`, `/v1/agreement-score`.
- **Events:** pub `recon.completed`, `recon.break_detected`; sub `ledger.object_transitioned` (for near-real-time checks), `spec.activated`.
- **Phase:** 1 (missing/state/stale), 2 (value, orphan money, matching).

### S37 — Breaks & Cases
- **Purpose:** manage disagreements to resolution.
- **Responsibilities:** break records with type, objects, evidence (both views, source metadata); shared inbox visible to both parties according to roles; assignment, comments, attachments, SLA timers; suggested resolution (from Ops Agent); resolution actions (accept A / accept B / replay / manual note); proof-of-agreement export (signed report) (P1).
- **API:** `/v1/breaks`, `/v1/breaks/{id}` (assign, comment, resolve), `/v1/agreement-reports`.
- **Events:** pub `recon.break_resolved`, sub `recon.break_detected`.
- **Phase:** 1.

---

## Human channels

### S38 — Human Task Service (T8a)
- **Purpose:** use people as an API.
- **Responsibilities:** task definitions with typed schema (from spec `human` steps); channel selection (WhatsApp, email, SMS link, web form); message composition (Arabic/English, templates approved by WhatsApp); short forms (mobile web); free-text reply parsing (LLM + rules) to typed values with confidence; clarification loop; reminders/escalation; signals result to Orchestration.
- **API:** `/v1/tasks` (spoke view), `/t/{token}` (public form), internal `/internal/tasks`.
- **Events:** pub `task.created/sent/answered/expired`; sub channel inbound messages.
- **Phase:** 2.

### S39 — Micro-app Platform (T8b)
- **Purpose:** minimal systems for parties without one.
- **Responsibilities:** narrow app generator for the hub's flow from selected canonical entities (lists, forms, detail views, status boards, simple roles); starts from the merchant's uploaded Excel; WhatsApp links and notifications; receives hub write-back (payment status, settlements); per-app schema storage; mobile-first PWA; Arabic/English; app data automatically exposed as T1 capabilities (CM generated); upgrades when the canonical model changes.
- **API:** `/v1/microapps`, `/v1/microapps/{id}/data/*`, app runtime at `{spoke}.apps.wasla...`.
- **Phase:** 1 (pilot: one narrow app), 2 (expansion if ≥ 40% of pilot merchants active after 60 days).

---

## AI platform

### S40 — LLM Gateway + PII Guard
- **Purpose:** controlled access to models.
- **Responsibilities:** provider/model routing (by task, region rules, tenant policy); PII detection and masking/tokenization on every prompt, unmasking on outputs where allowed; quotas and budgets per tenant/agent; response caching; retries/fallbacks; full logging (masked) with cost; self-hosted model support (P2).
- **API:** internal `POST /internal/llm/complete`, `/internal/llm/embed`.
- **Phase:** 0.

### S41 — Agent Runtime + Prompt Registry
- **Purpose:** common runtime for all agents.
- **Responsibilities:** agent definitions (tools, prompts, policies) versioned; tool interface to internal APIs with scoped service tokens; step limits, timeouts; decision logs (inputs, outputs, reasoning summary); human-in-the-loop hooks; prompt/version registry with rollout flags.
- **API:** internal library + `/internal/agents/{name}/runs`.
- **Phase:** 0.

### S42 — Evaluation Service
- **Purpose:** measure agents.
- **Responsibilities:** golden datasets (mappings, discovery, extraction, designer, reply parsing) built from confirmed production data (masked); eval runs per prompt/model change; metrics (precision/recall, accuracy, cost, latency); regression gates in CI; dashboards in Studio.
- **API:** `/internal/evals/*`; Studio views.
- **Phase:** 1.

### S43 — Code Sandbox
- **Purpose:** run untrusted/generated code safely.
- **Responsibilities:** microVM/strong-isolation containers; no network by default, allow-list per job; CPU/mem/time limits; artifact in/out via object store; used by Code Analyzer, API Generator, `code` steps, Verification.
- **API:** internal `POST /internal/sandbox/jobs`.
- **Phase:** 2.

### S44 — Ops Agent
- **Purpose:** automated diagnosis and fix proposals.
- **Responsibilities:** consume failures, DLQ, drift, breaks; cluster incidents; diagnose root cause using run history, CMs, mappings; propose changes (re-map, spec patch, conversion fix, connection re-auth) as change requests for approval; incident timeline per integration.
- **API:** `/v1/studio/ops/proposals`, `/v1/integrations/{id}/incidents`.
- **Events:** sub `run.dead_lettered`, `cm.diff_detected`, `recon.break_detected`, `connector.error_pattern`; pub `ops.proposal_created`.
- **Phase:** 2.

---

## Experiences

### S45 — Hub Public API
- **Purpose:** public developer surface for hubs.
- **Responsibilities:** `/v1` resources: spokes, invitations, connections (status), consents, canonical data (read/write, dry-run), integrations, runs, objects, money, breaks, agreement, webhooks (endpoints, deliveries, replay), events catalog; outbound webhook delivery with signing/retries; SDK generation (TS, Python).
- **Events:** sub public-facing events; pub `webhook.delivery_*`.
- **Phase:** 1.

### S46 — Console BFF
- **Purpose:** backend-for-frontend for Hub Console, Spoke Portal and Studio.
- **Responsibilities:** session auth; aggregation of service APIs per screen; permission-aware responses; server-sent events for live updates.
- **Phase:** 1.

### S47 — Connect Service (widget + hosted)
- **Purpose:** spoke onboarding flows.
- **Responsibilities:** `connect.js` loader and iframe app; hosted connect pages; invite links (signed, expiring); flow state machine per tier path; resumable sessions; theming per hub; Arabic/English RTL; Edge Agent download/enrollment UX; analytics funnel.
- **API:** `/connect/*` public; `/v1/connect/sessions` (hub creates session token).
- **Phase:** 1.

### S48 — Developer Portal
- **Purpose:** docs and self-serve developer onboarding.
- **Responsibilities:** guides, API reference (from OpenAPI), event catalog (from AsyncAPI), canonical model browser, sandbox keys, changelog.
- **Phase:** 1.

### Front-end applications
| App | Main screens | Phase |
|---|---|---|
| **Hub Console** | Overview (spokes by tier/status, agreement), Spokes (list, detail, connections, consent), Data products, Integrations (specs, versions, approvals, tests), Runs & DLQ, Objects & ledger, Breaks inbox, Webhooks, API keys, Team, Usage & billing, Settings | 1 |
| **Spoke Portal** | My connections & health, Hubs with access & consent, Tasks, Breaks involving me, Edge Agent status, Micro-apps (P4), Team | 1 |
| **Wasla Studio** | Review queues (mappings, discovery, documents), Tenants & directory, Canonical model editor, Mapping templates, Country packs, Known-systems catalog, Agent evals, Ops proposals, Support tools (JIT access) | 1 |
| **Connect** | Invite landing, consent, system picker, tier flows, progress | 1 |

### S50 — Observability Platform
- **Purpose:** platform telemetry.
- **Responsibilities:** collectors, metrics store, log store, trace store, dashboards, alerting, SLO definitions, on-call routing, status page.
- **Phase:** 0.
