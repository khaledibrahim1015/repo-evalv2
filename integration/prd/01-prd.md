# 01 — Product Requirements Document (PRD)

*Version 2.0 · October 8, 2026 · Status: Draft for review*
*Supersedes the build plan v1.1 and design revisions R1–R5 as the source of truth. Those documents remain as background.*

**Working name:** **Wasla** (وصلة, "connection"). Replace when branding is decided.

---

## 1. Summary

Wasla is a **generic B2B integration network**. It connects any company to any other company, whatever the state of their systems: a modern API, an on-prem database, a web app without an API, Excel and email, or no system at all.

It is sold to **hubs**, companies that must integrate with many counterparties (first: fintechs and embedded-finance providers in Egypt). The hub embeds Wasla's **Connect** experience; its **spokes** (merchants, suppliers, customers) connect once at whatever level they can. Wasla then:

1. **Discovers** what each spoke's systems can do and describes it in one **Capability Model**.
2. **Maps** each spoke's data once to a **Canonical Data Model** per vertical, so every hub reads the same entities whatever the spoke's system.
3. **Runs** integrations durably (retries, queues, idempotency, monitoring) on behalf of companies whose own infrastructure is weak.
4. **Proves** that both parties agree, by tracking every shared object in a **State Ledger** and **reconciling** both sides continuously.

**Build policy:** every product component is built in-house. Commodity infrastructure (database engine, message broker, container orchestration, durable-workflow engine) is used as infrastructure, not as product. Licensing is out of scope for this document.

---

## 2. Problem

| # | Problem | Who feels it |
|---|---|---|
| P1 | Most B2B counterparties have no usable API: on-prem ERPs, local accounting software, Excel, paper | Fintechs, large buyers, logistics companies |
| P2 | Each integration is a custom project; integration #50 costs as much as #1 | Hubs' engineering teams |
| P3 | SMBs cannot run reliable infrastructure; webhooks get lost, jobs fail silently | Both sides |
| P4 | Nobody can prove both sides agree; drift is found weeks later by accountants or customers | Finance, ops, risk teams |
| P5 | Existing iPaaS products assume both sides are software companies with engineers | Underserved MENA SMB market |
| P6 | Fintech onboarding stalls on "send us your data" for days or weeks | Fintech growth and risk teams |
| P7 | Data must also flow back (payment status, settlements, decisions), which is hardest where merchants have no system | Fintechs, merchants |

### 2.1 Reference scenario: an Egyptian fintech with 1,000 merchants

A payments/lending fintech must exchange data with 1,000 merchants. Each merchant is in a different situation:

```
A  ERP with API                 Merchant ERP ──REST API──────────────▶ Fintech
B  ERP, no API, DB reachable    Merchant ERP ── Database ── ? ───────▶ Fintech
B2 Cloud ERP, no API, no DB     Web screens only ── ? ───────────────▶ Fintech
C  Legacy on-prem system        Legacy app ── local SQL Server (behind firewall, no internet API)
D  Excel                        Excel ── Email ──────────────────────▶ Fintech
E  No system                    Paper / WhatsApp ── Employee ────────▶ Fintech
F  Data held by third parties   ETA e-invoices · bank statements · POS/marketplaces · the fintech itself
```

**Two axes describe every merchant better than one list:**

| Axis | Values |
|---|---|
| **Interface** | API · database · screens only (web UI) · files · nothing |
| **Location** | Cloud and reachable · on-prem behind a firewall |

**Case → method → ladder tier**

| Case | Method | Tier |
|---|---|---|
| A — ERP with API | Call the API directly | T1 (T2 if only docs exist) |
| B — ERP without API, DB reachable | Read the DB; generate an API from the DB or code | T3 / T4 |
| B2 — Cloud ERP, no API, no DB access | Automate/analyze the web screens | T5 |
| C — Legacy on-prem | Edge Agent inside the network + DB | T3 via Edge Agent |
| D — Excel and email | Extract from files and inbox | T7 |
| E — No system | WhatsApp/form tasks, or a micro-app | T8 |
| F — Data held elsewhere | ETA, bank statements, POS/marketplaces, the fintech's own records | T6 |

**What the scenario shows**
1. **Mixed merchants.** One merchant can be several cases at once (sales in an ERP with API, stock in Excel, collections reported on WhatsApp). The method is chosen **per data type**, not per merchant.
2. **Both directions.** Reading from merchants is half the problem. Writing back (payment status, settlements, financing decisions) is harder: C needs writes to a local DB, D has nowhere to write, E needs a human reply.
3. **Connectivity is only one of four problems.**

   | Problem | Meaning |
   |---|---|
   | Reach | Get to the data whatever the case (A–F) |
   | Shape | Every system names things differently → map once to a canonical model |
   | Trust | A is precise and real-time; D and E are late and error-prone → confidence scores and reconciliation |
   | Cost per merchant | One week of work × 1,000 merchants = 1,000 weeks. The real problem is doing it 1,000 times at near-zero marginal cost |
4. **The easy case is likely the minority.** Among Egyptian SMB merchants, A is probably rare and D/E common. This is an assumption to verify with a survey of design-partner merchants (see delivery plan T0.1.2); if confirmed, D, E and F matter more than A in the MVP.

**Problem in one sentence:** a fintech must exchange data in both directions with thousands of merchants, each with a different system or none at all, reliably and at near-zero cost per merchant.

---

## 3. Vision and goals

**Vision:** any company can be connected to any other company in under a day, and both can trust the data they exchange.

### 3.1 Goals (end of project, Month 24)
| ID | Goal | Metric |
|---|---|---|
| G1 | Connect any spoke regardless of system | ≥95% of invited spokes connected at some ladder tier |
| G2 | Fast onboarding | Median spoke time-to-connected < 1 day; median new hub integration live < 1 week |
| G3 | Reliability | ≥99.9% platform availability; ≥99.5% integration run success after retries |
| G4 | Agreement | ≥99% agreement score on reconciled entities |
| G5 | Low marginal cost | ≥80% of fields auto-mapped above threshold; human effort per new spoke < 30 min |
| G6 | Network effect | ≥30% of new hub–spoke connections reuse an existing spoke connection |
| G7 | Commercial | 10+ paying hubs, 2 countries (Egypt, KSA), 2 verticals |

### 3.2 Non-goals
- A general-purpose workflow automation tool for end users (not Zapier/n8n).
- A full ERP. Micro-apps (§7.13) cover narrow flows only.
- Holding or moving money. Wasla records and reconciles value; licensed partners move funds.
- Consumer (B2C) integrations.
- Data warehouse or BI product.

---

## 4. Users and personas

| Persona | Organization | Needs |
|---|---|---|
| **Hub Product/Ops Manager** ("Mona") | Fintech | Get merchants connected fast; see who is connected, at which tier, and whether data is trustworthy |
| **Hub Developer** ("Karim") | Fintech | One API and webhooks; embed Connect; read merchant data as canonical entities; no per-merchant code |
| **Hub Risk/Finance Analyst** ("Heba") | Fintech | Reliable data with source information; reconciliation reports; proof of agreement for audit |
| **Spoke Owner / Accountant** ("Ahmed") | SMB merchant / supplier | Connect in minutes without IT; understand and control what is shared; few manual tasks |
| **Spoke IT person** ("Sara") | Mid-size company | Install the Edge Agent safely; read-only access; clear security story |
| **Integration Engineer** ("Omar") | Wasla | Review agent output, fix low-confidence items, onboard difficult spokes |
| **Platform Operator / SRE** ("Youssef") | Wasla | Keep the runtime healthy; tenant-level visibility; incident tooling |
| **Wasla Admin** | Wasla | Manage tenants, plans, regions, country packs, canonical models |

---

## 5. Core concepts (glossary)

| Term | Definition |
|---|---|
| **Hub** | Tenant that pays and integrates with many counterparties |
| **Spoke** | Counterparty organization connected to one or more hubs |
| **Party** | Any organization in an integration (hub or spoke) |
| **Connection** | Credential-bearing link from Wasla to one party's system or channel |
| **Connectivity Ladder** | Ordered methods to reach a system: T1 API → T2 docs → T3 DB → T4 code → T5 UI traffic → T6 shared external source → T7 documents → T8 human/micro-app |
| **Capability Model (CM)** | Normalized description of what a party's systems can do: entities, fields, operations, events, auth, limits, tier, provenance, confidence |
| **Canonical Data Model (CDM)** | Per-vertical set of entities (e.g. MerchantProfile, Customer, Invoice, Payment) with fields, validation rules and state machines, defined in JSON Schema |
| **Mapping** | Per connection and entity: which source operation supplies the entity and how source fields convert to canonical fields; produced by the mapping agent with confidence |
| **Canonical Data Service (CDS)** | Service that reads and writes canonical entities for a party, using the mapped source operation of the selected connection |
| **Integration Spec (IS)** | Declarative definition of one integration: trigger, steps, reliability, SLA, reconciliation |
| **Run** | One execution of an Integration Spec |
| **State Ledger** | Append-only record of every cross-party object, its state machine and each party's observed view |
| **Money Ledger** | Double-entry ledger for value-bearing objects |
| **Break** | Detected disagreement between parties (missing, state, value, orphan money, stale) |
| **Agreement Score** | % of tracked objects where all parties agree |
| **Consent** | Spoke's revocable grant allowing a hub to access given scopes |
| **Country Pack** | Region config: residency, tax schema, e-invoicing connector, currency, language, holidays |
| **Edge Agent** | Wasla-built agent installed in a party's network, outbound-only tunnel |
| **Human Task** | Request to a person (form, email, WhatsApp) used as an API at tier T8a |
| **Micro-app** | Generated small app over canonical entities for parties with no system (T8b) |

---

## 6. Key user journeys

### J1 — Hub onboarding
1. Wasla admin creates the hub tenant, picks country pack (Egypt) and vertical canonical model (embedded finance).
2. Hub admin signs in, invites team, sets roles.
3. Hub developer gets API keys, configures webhook endpoints, embeds `connect.js` or uses hosted connect links.
4. Hub selects which **data products** it needs (e.g. *Merchant Profile*, *Sales History*, *Issued E-Invoices*, *Bank Lines*, *Payment Status write-back*).
5. Wasla generates default Integration Specs for those data products; hub reviews and approves.

### J2 — Spoke connects (each tier)
1. Spoke receives an invite inside the hub app or by link (email/WhatsApp/SMS).
2. Spoke sees the hub name, requested scopes and purpose; grants consent.
3. Spoke picks "How do you manage your business?" → list of known systems, "Our own system", "Excel/paper", "Nothing".
4. Depending on choice:
   - **Known cloud system (T1):** OAuth or API key → done.
   - **Own system with docs (T2):** upload docs/Postman, or give the portal URL.
   - **On-prem system (T3):** download Edge Agent installer; IT runs one command; select read-only DB user.
   - **Own code (T4):** connect repository (read-only) or install Edge Agent near the code.
   - **Web app only (T5):** record a guided session in the browser helper; consent recorded.
   - **E-invoicing (T6):** authorize Wasla on the tax portal (ETA client credentials).
   - **Excel/email (T7):** get a dedicated inbox address and upload page.
   - **Nothing (T8):** choose WhatsApp/email tasks or activate a micro-app.
5. Discovery runs; spoke sees progress and a summary of what was found.
6. Low-confidence items go to Wasla's review queue; spoke is asked only plain-language questions.
7. Connection becomes **ready**; hub gets `connection.ready` webhook.

### J3 — Hub reads canonical data
1. Hub developer calls `GET /v1/spokes/{id}/data/invoices?issued_from=2026-04-01`.
2. CDS uses the connection mapped for `Invoice` (e.g. ETA for this spoke), calls it through the Connector Runtime, applies the mapping and returns canonical records with source metadata (connection, tier, fetched at).
3. If no connection supplies the entity yet, the response says so; Discovery may ask the spoke for more (e.g. upload an export).

### J4 — Integration runs and is reconciled
1. Trigger fires (webhook, schedule, CDC, human task reply).
2. Run executes steps durably; every transition is written to the State Ledger.
3. Reconciler compares both sides on schedule; agreement score updates.
4. Breaks appear in the shared Breaks Inbox with suggested resolution.

### J5 — Schema drift
1. Re-discovery detects a CM change (new/removed field, changed type).
2. Affected integrations auto-pause if the change is breaking.
3. Ops Agent proposes mapping or spec changes; engineer approves; runs resume and replay from the pause point.

### J6 — Human-as-API
1. Spec needs data a spoke can only provide manually (e.g. confirm delivery date).
2. Human Task Service sends WhatsApp message with a short form link.
3. Reply is parsed to typed values with confidence; low confidence → clarification message or engineer review.
4. Run continues.

### J7 — Write-back
1. Hub posts a payment status (`POST /v1/spokes/{id}/data/payments`).
2. CDS uses the write mapping for `Payment` and picks the target operation on the spoke system (API, DB via Edge Agent, generated API, or human task).
3. Dry-run preview → approval policy → idempotent write → reconciled.

### J8 — Spoke reuses connection for a second hub
1. Second hub invites a spoke already on Wasla.
2. Spoke sees "You're already connected"; grants consent for new scopes only.
3. Connection is live in minutes; no rediscovery needed.

---

## 7. Functional requirements

Priority: **P0** = MVP (Phase 1), **P1** = Phase 2–3, **P2** = Phase 4–5.

### 7.1 Tenancy, identity, access
| ID | Requirement | P |
|---|---|---|
| FR-ID-01 | Multi-tenant model: organizations (hub/spoke/both), workspaces, environments (sandbox, production) | P0 |
| FR-ID-02 | Users, invitations, email+password, magic link, TOTP MFA | P0 |
| FR-ID-03 | SSO via OIDC/SAML for hubs | P1 |
| FR-ID-04 | Roles: Owner, Admin, Developer, Analyst, Viewer, Spoke Owner, Spoke Contributor; custom roles | P0 (fixed) / P1 (custom) |
| FR-ID-05 | API keys per environment with scopes, rotation, last-used | P0 |
| FR-ID-06 | Service-to-service identity (mTLS + short-lived tokens) | P0 |
| FR-ID-07 | Wasla staff access to tenant data only via just-in-time, audited break-glass | P0 |

### 7.2 Consent
| ID | Requirement | P |
|---|---|---|
| FR-CO-01 | Consent request with hub identity, purpose, scopes (data products / canonical entities), duration | P0 |
| FR-CO-02 | Spoke can view, narrow, and revoke consent; revocation takes effect < 1 min | P0 |
| FR-CO-03 | Every data access checks consent; denied access logged | P0 |
| FR-CO-04 | Consent receipts (signed PDF/JSON) downloadable by both parties | P1 |
| FR-CO-05 | Reuse of an existing spoke connection by a new hub requires new consent only | P1 |

### 7.3 Connect experience
| ID | Requirement | P |
|---|---|---|
| FR-CN-01 | Embeddable `connect.js` widget (web) with theming, Arabic/English, RTL | P0 |
| FR-CN-02 | Hosted connect link (shareable via email/WhatsApp/SMS) | P0 |
| FR-CN-03 | System picker with search over known systems and "own system / Excel / nothing" paths | P0 |
| FR-CN-04 | Guided flows per tier (OAuth, API key, docs upload, Edge Agent install, inbox, human tasks) | P0 (T1, T3, T6, T7) / P1 (T2, T4, T5, T8) |
| FR-CN-05 | Progress and status page for spokes; resumable flows | P0 |
| FR-CN-06 | Mobile-friendly flows (spokes often on phones) | P0 |
| FR-CN-07 | Hub can pre-fill spoke details and choose allowed tiers | P1 |

### 7.4 Connections and Edge Agent
| ID | Requirement | P |
|---|---|---|
| FR-CX-01 | Connection lifecycle: draft → authorizing → discovering → review → ready → degraded → paused → revoked | P0 |
| FR-CX-02 | Credential storage encrypted with per-tenant keys; never shown after entry | P0 |
| FR-CX-03 | OAuth 2.0 flows with token refresh; API key, basic, mTLS, custom header auth | P0 |
| FR-CX-04 | Health checks per connection; degraded/paused states with reason | P0 |
| FR-CX-05 | Edge Agent: single binary for Linux/Windows, one-command install, outbound-only TLS tunnel, auto-update, local buffer | P0 |
| FR-CX-06 | Edge Agent DB connectors: SQL Server, MySQL/MariaDB, PostgreSQL, Oracle; read-only by default | P0 (SQL Server, MySQL, PostgreSQL) / P1 (Oracle) |
| FR-CX-07 | Edge Agent CDC (log-based where available, polling with watermark otherwise) | P1 |
| FR-CX-08 | Edge Agent hosts generated APIs (S2) | P1 |
| FR-CX-09 | Rate limiting and circuit breaker per connection | P0 |

### 7.5 Discovery (Connectivity Ladder)
| ID | Requirement | P |
|---|---|---|
| FR-DI-01 | Discovery Orchestrator runs tiers per entity and records chosen tier and reason | P0 (T1, T3, T6, T7) / P1 (all) |
| FR-DI-02 | T1: OpenAPI 2/3, Postman, GraphQL introspection, SOAP/WSDL ingestion | P0 (OpenAPI, Postman) / P1 (GraphQL, WSDL) |
| FR-DI-03 | T2: Doc reader agent from PDF/HTML/portal URL → draft OpenAPI with confidence | P1 |
| FR-DI-04 | T3: DB introspection (tables, keys, enums, samples), entity inference, PII detection | P0 |
| FR-DI-05 | T4: Code analyzer for named stacks (PHP/Laravel, .NET, Node) → operations | P1 |
| FR-DI-06 | T5: Traffic analyzer from recorded browser sessions → internal API client | P1 |
| FR-DI-07 | T6: Country-pack connectors (Egypt ETA e-invoice/e-receipt; KSA ZATCA later) | P0 (ETA) / P1 (ZATCA) |
| FR-DI-08 | T7: Inbox + upload ingestion of Excel/CSV/PDF/images → typed records with confidence | P0 (Excel/CSV) / P1 (PDF, images) |
| FR-DI-09 | T8: Human tasks and micro-apps exposed as capabilities | P1 (T8a) / P2 (T8b) |
| FR-DI-10 | Scheduled re-discovery, CM diff, breaking-change classification | P0 |
| FR-DI-11 | Automatic tier upgrade when a better path appears, with reconciliation check | P1 |

### 7.6 Capability Model, canonical model and mapping
| ID | Requirement | P |
|---|---|---|
| FR-CM-01 | CM stored as versioned documents (OpenAPI 3.1 + Wasla extensions) per connection | P0 |
| FR-CM-02 | CM diff between versions with change classification | P0 |
| FR-CM-03 | Canonical Data Model per vertical in JSON Schema: entities, fields, validation, state machines; versioned | P0 |
| FR-CM-04 | Embedded-finance CDM v1 (~20 entities) | P0 (v0 ~8 entities) / P1 (v1) |
| FR-CM-05 | Mapping agent maps each connection's entities/fields to canonical entities with confidence; threshold configurable | P0 |
| FR-CM-06 | Review UI for low-confidence mappings; bulk accept; learn from corrections | P0 |
| FR-CM-07 | Mapping templates per known system (reused across all spokes on that system) | P0 |
| FR-CM-08 | Second vertical CDM (retail/distribution or logistics) | P2 |

### 7.7 Canonical Data Service (read and write canonical entities)
| ID | Requirement | P |
|---|---|---|
| FR-DS-01 | Read canonical entities per spoke: list with filters, pagination, get by id | P0 |
| FR-DS-02 | Per entity, use the connection selected by Discovery; ordered fallback connections when the primary is down | P0 |
| FR-DS-03 | Consent check on every read/write | P0 |
| FR-DS-04 | Source metadata on every record (connection, tier, fetched at, confidence for T7/T8) | P0 |
| FR-DS-05 | Clear error when no connection supplies an entity | P0 |
| FR-DS-06 | Write canonical entities: reverse mapping, target operation, dry-run, idempotency | P0 (dry-run, T1/T3) / P1 (all tiers) |
| FR-DS-07 | Caching per (connection, entity, filters) with TTL per tier | P0 |
| FR-DS-08 | Change feed: push changed canonical records to hubs | P2 |

### 7.8 Integration Specs and runtime
| ID | Requirement | P |
|---|---|---|
| FR-IS-01 | Integration Spec YAML: trigger, steps (`fetch`, `write`, `map`, `call`, `human`, `code`), reliability, SLA, reconciliation | P0 |
| FR-IS-02 | Data-product templates generate specs for common hub needs | P0 |
| FR-IS-03 | Integration designer agent: intent → spec draft | P1 |
| FR-IS-04 | Spec validation against CMs, mappings and the canonical model; compile to workflow definitions | P0 |
| FR-IS-05 | Two-party approval before production; versioning; rollback | P0 |
| FR-IS-06 | Triggers: webhook, schedule, CDC, poll, human task reply, hub API call | P0 (webhook, schedule, poll, API) / P1 (CDC, human) |
| FR-IS-07 | Reliability: retries with backoff, timeouts, DLQ, per-key ordering, idempotency, circuit breaker | P0 |
| FR-IS-08 | Run history with step-level inputs/outputs (PII-masked), replay single/bulk | P0 |
| FR-IS-09 | Sandbox mode with mocks of both sides and recorded payload replay | P0 |
| FR-IS-10 | `code` step escape hatch (TypeScript) in sandbox | P1 |

### 7.9 Verification
| ID | Requirement | P |
|---|---|---|
| FR-VE-01 | Mock servers generated from CMs | P0 |
| FR-VE-02 | Contract tests between spec steps and CMs | P0 |
| FR-VE-03 | Property-based/fuzz tests on generated APIs | P1 |
| FR-VE-04 | Golden tests for mappings from sample data | P0 |
| FR-VE-05 | Go-live gate: tests green + both approvals + all low-confidence items confirmed | P0 |

### 7.10 State Ledger and reconciliation
| ID | Requirement | P |
|---|---|---|
| FR-SL-01 | Record each cross-party object: canonical key, state machine, per-party observed view, transitions | P0 |
| FR-SL-02 | Reconciler per integration on schedule; break types: missing_at_target, missing_at_source, state_mismatch, value_mismatch, orphan_money, stale | P0 (missing, state, stale) / P1 (value, orphan) |
| FR-SL-03 | Auto-heal policy (only missing_at_target, state_mismatch by default) | P0 |
| FR-SL-04 | Shared Breaks Inbox for both parties with assignment, comments, resolution | P0 |
| FR-SL-05 | Agreement score per integration, party, hub | P0 |
| FR-SL-06 | Proof-of-agreement export (signed) | P1 |
| FR-SL-07 | Money Ledger: double-entry accounts, postings, balances, multi-currency, immutable | P1 |
| FR-SL-08 | Payment matching (rules + agent suggestions) for orphan money | P1 |

### 7.11 Human tasks (T8a)
| ID | Requirement | P |
|---|---|---|
| FR-HT-01 | Task types: confirm, provide values, upload file, choose option | P1 |
| FR-HT-02 | Channels: WhatsApp Business, email, SMS link, web form | P1 |
| FR-HT-03 | Reply parsing to typed values with confidence; clarification loop | P1 |
| FR-HT-04 | Reminders, escalation, SLA per task | P1 |
| FR-HT-05 | Arabic (Egyptian and Gulf dialects) and English | P1 |

### 7.12 API generation (S2)
| ID | Requirement | P |
|---|---|---|
| FR-AG-01 | Generate REST API from DB (curated reads + specific writes) deployed in Edge Agent | P1 |
| FR-AG-02 | Generate API layer from codebase for named stacks, delivered as PR or Edge service | P1 |
| FR-AG-03 | Generated APIs have OpenAPI, tests, and feed back into CM as T1 | P1 |

### 7.13 Micro-apps (T8b)
| ID | Requirement | P |
|---|---|---|
| FR-MA-01 | Generate app (tables, forms, status board, import/export) from selected models | P2 |
| FR-MA-02 | Arabic/English, mobile-first, roles for the spoke's staff | P2 |
| FR-MA-03 | Micro-app data exposed as T1 capability automatically | P2 |

### 7.14 Agents platform
| ID | Requirement | P |
|---|---|---|
| FR-AI-01 | LLM gateway with model routing, quotas, caching, cost tracking per tenant | P0 |
| FR-AI-02 | PII detection/masking before any customer data reaches a model | P0 |
| FR-AI-03 | Prompt/version registry; evaluation harness with golden datasets; regression gates | P0 |
| FR-AI-04 | Sandboxed execution of generated code | P1 |
| FR-AI-05 | Option to use self-hosted models for sensitive tenants | P2 |
| FR-AI-06 | Every agent decision logged (inputs, outputs, reasoning summary) | P0 |

### 7.15 Operations (Ops Agent, drift)
| ID | Requirement | P |
|---|---|---|
| FR-OP-01 | Detect failure patterns and drift; auto-pause on breaking changes | P0 |
| FR-OP-02 | Ops Agent diagnoses and proposes fixes as spec/mapping change requests | P1 |
| FR-OP-03 | Incident timeline per integration | P1 |

### 7.16 Hub developer surface
| ID | Requirement | P |
|---|---|---|
| FR-DX-01 | REST API v1: spokes, connections, consent, canonical data (read/write), integrations, runs, breaks | P0 |
| FR-DX-02 | Signed webhooks with retries and replay; event catalog | P0 |
| FR-DX-03 | SDKs: TypeScript, Python; later Java, .NET, PHP | P0 (TS, Python) / P2 (others) |
| FR-DX-04 | Developer docs portal with guides, API reference, sandbox | P0 |
| FR-DX-05 | CLI for specs and canonical models (`wasla spec push`, `wasla cdm publish`) | P1 |

### 7.17 Consoles
| ID | Requirement | P |
|---|---|---|
| FR-UI-01 | **Hub Console**: spokes list with tier/status/agreement, integrations, runs, breaks, consent, API keys, webhooks, team, billing | P0 |
| FR-UI-02 | **Spoke Portal**: my connections, hubs with access, consent management, tasks, breaks visible to me | P0 |
| FR-UI-03 | **Wasla Studio** (internal): review queues (mappings, discovery, docs), tenants, canonical models, country packs, agent evals, support tools | P0 |
| FR-UI-04 | Arabic/English with RTL across all consoles | P0 |

### 7.18 Notifications, audit, billing
| ID | Requirement | P |
|---|---|---|
| FR-NO-01 | Notifications: in-app, email, WhatsApp, webhook; user preferences | P0 |
| FR-AU-01 | Immutable audit log of every admin, consent, approval, data-access action; export | P0 |
| FR-BI-01 | Metering: connected spokes, runs, resolved queries, reconciled objects, human tasks | P0 |
| FR-BI-02 | Plans, invoices, usage dashboards; payment collection via local payment providers | P1 |

### 7.19 Regions and country packs
| ID | Requirement | P |
|---|---|---|
| FR-RG-01 | Tenant pinned to a region; data stored and processed in region | P0 |
| FR-RG-02 | Country pack: tax schema, e-invoicing connector, currency, calendar, language defaults, ID formats | P0 (EG) / P1 (SA) |
| FR-RG-03 | Region deployment in KSA (in-kingdom) | P1 |

---

## 8. Non-functional requirements

| Area | Requirement |
|---|---|
| **Availability** | Control plane 99.9%; runtime 99.9%; Edge tunnel gateway 99.95%; RPO ≤ 5 min, RTO ≤ 1 h |
| **Performance** | Query p95 < 2 s for T1/T3 sources (excluding upstream latency > 1 s); webhook ingress p99 < 200 ms ack; run start latency p95 < 1 s |
| **Scale (Month 24)** | 50 hubs, 20,000 spokes, 60,000 connections, 50M runs/month, 500M ledger entries, 5,000 concurrent Edge Agents |
| **Durability** | No acknowledged event lost; at-least-once delivery + idempotency = effectively-once effects |
| **Security** | Encryption in transit (TLS 1.2+) and at rest (per-tenant envelope keys); least privilege; secrets never logged; OWASP ASVS L2; annual pen test |
| **Privacy** | PII classification on every CM field; masking in logs, UI previews and LLM prompts; data minimization by consent scope; deletion on request |
| **Residency** | Tenant data stays in its region (Egypt first; KSA in-kingdom) including backups and LLM processing where required |
| **Compliance targets** | Egypt PDPL and CBE/FRA guidance as applicable to service providers of fintechs; SOC 2 Type I by Month 15, Type II by Month 24; ISO 27001 readiness |
| **Auditability** | Every data access, consent change, approval and agent decision traceable for 7 years |
| **Localization** | Arabic and English, RTL, Arabic numerals optional, Hijri/Gregorian dates where needed |
| **Accessibility** | WCAG 2.1 AA for consoles and Connect |
| **Operability** | All services emit traces, metrics, structured logs with tenant id; SLOs with alerting; runbooks |
| **Edge Agent footprint** | < 100 MB disk, < 200 MB RAM idle; works on Windows Server 2012 R2+ and common Linux |

---

## 9. Packaging and pricing (initial hypothesis)

| Plan | For | Includes | Price driver |
|---|---|---|---|
| **Starter** | Small hubs | Up to 100 connected spokes, T1/T6/T7, reconciliation daily | Per connected spoke / month |
| **Growth** | Most fintechs | All tiers, Edge Agent, human tasks, hourly reconciliation, SLA 99.5% | Per spoke + per 1k runs |
| **Enterprise** | Banks, large buyers | Dedicated region/cluster, SSO, custom SLA 99.9%, self-hosted models | Annual contract |
| **Spoke** | Spokes | Free: portal, consent, own connection status | Micro-apps paid add-on (P2) |

---

## 10. Success metrics (tracked from Phase 1)

| Category | Metric |
|---|---|
| Adoption | Hubs live; spokes invited → connected conversion; connections by tier |
| Speed | Time-to-connected per tier; time-to-first-data-read; time-to-go-live per integration |
| Quality | Mapping precision/recall; % auto-mapped; discovery accuracy; canonical data correctness |
| Reliability | Run success rate; MTTD/MTTR; DLQ age; Edge Agent uptime |
| Trust | Agreement score; open breaks; break age; auto-heal rate |
| Efficiency | Engineer minutes per spoke; LLM cost per spoke; infra cost per run |
| Network | % connections reusing an existing spoke; spokes connected to ≥2 hubs |
| Revenue | ARR, net revenue retention, gross margin |

---

## 11. Release plan (summary)

Detailed plan in [04-delivery-plan.md](04-delivery-plan.md).

| Phase | Months | Theme | Exit |
|---|---|---|---|
| 0 | 0–1.5 | Foundations | Platform skeleton, canonical model v0, mapping prototype, design partners signed |
| 1 | 1.5–5 | MVP: Egypt fintech hub | 1 hub, ≥20 spokes, ≥3 tiers, reconciliation live |
| 2 | 5–9 | All ladder tiers | API generation, human tasks, Money Ledger, Ops Agent; 3 hubs |
| 3 | 9–13 | Network & KSA | Connection reuse, proof of agreement, KSA region, SOC 2 Type I; 6 hubs |
| 4 | 13–18 | Micro-apps & 2nd vertical | Micro-apps GA, second vertical live; 8 hubs |
| 5 | 18–24 | Scale & GA hardening | Self-serve, marketplace, SOC 2 Type II, scale targets; 10+ hubs |

---

## 12. Assumptions
- Team grows from 8 (Phase 0) to ~18 (Phase 4–5); see delivery plan.
- 1–2 Egyptian fintech design partners commit to Phase 1 with 20+ spokes each.
- Spokes can obtain ETA API credentials (or delegate access) for T6.
- WhatsApp Business API access via an approved provider is available for T8a.
- Cloud region options exist that satisfy Egyptian residency needs; otherwise a local data center/colocation provider is used.

## 13. Risks
| Risk | Impact | Mitigation |
|---|---|---|
| Spokes distrust installing an agent | Low T3 adoption | Read-only, outbound-only, open audit log, signed binaries, IT-friendly docs, hub endorsement |
| Agent mistakes corrupt data | Severe | Read-only discovery, verification gate, dry-run, two-party approval, reconciliation |
| Building everything in-house slows delivery | Schedule | Strict phase scope; commodity infra only where it is not product; reuse internal libraries |
| Becoming a services company | Margin | Track engineer minutes per spoke; every manual fix must become a mapping template or rule |
| Regulatory changes (fintech data rules) | Market | Legal counsel per country; consent and residency built in from day one |
| UI-traffic (T5) breaks often | Reliability | Lowest preference among automated tiers; monitored; auto-fallback to T7/T8 |
| LLM cost | Margin | Caching, small models for classification, batch processing |
| Currency risk (EGP) | Revenue | USD-linked enterprise contracts; KSA expansion |

## 14. Open questions
1. Brand name and domain.
2. Hosting provider for Egypt region.
3. WhatsApp provider selection.
4. Pricing validation with design partners.
5. Second vertical choice (decide by Month 12): retail/distribution buyer vs. logistics/3PL.
