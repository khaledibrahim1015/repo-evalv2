# Agentic B2B Integration Engine — Design Revisions (v1.1)

*Prepared: October 8, 2026 · Amends [build plan v1.0](agentic-integration-engine-build-plan.md)*

## Why this revision

A second pass over adjacent products — **Integuru** (UI → internal API), **Nango vs. Tray Embedded** (embedded integrations), the open-source **integration platforms** and **Retool alternatives** catalogs, and **Formance** (ledger, reconciliation, money flows) — exposed five gaps in v1.0. None of them changes the core (Capability Model, Integration Spec, durable runtime). They change **how we reach customers**, **what guarantee we sell**, and **how we cover companies with weak or no systems**. A later review of **Orbital / Taxi** added R6, which does change the core: how fields are matched across parties.

| # | Revision | Gap in v1.0 | Borrowed from |
|---|---|---|---|
| R1 | Hub-and-spoke go-to-market with an embeddable **Connect SDK** | Two-sided cold start: we must sell to A *and* B | Tray Embedded, Nango |
| R2 | **Cross-party State Ledger & Reconciler** as a first-class feature | We move data but never prove both sides agree | Formance Ledger + Reconciliation, generalized |
| R3 | **Connectivity Ladder** with an automatic **Discovery Orchestrator** | Ingestion paths exist, nothing chooses or upgrades between them | Integuru, Nango, Airbyte-style agents |
| R4 | Scenario 3 re-scoped to **human-as-API** and **generated micro-apps** | "Build the missing system" drifts into services work | Appsmith / ToolJet / NocoBase pattern |
| R5 | **First hub = fintech / embedded finance** (Egypt first) | Vertical choice left open | Fintech pain in the brief |
| R6 | **Semantic types** instead of field-to-field mappings | Mappings are per pair, brittle, and limit the network effect | Orbital / Taxi (Apache-2.0 parts only) |

**What stays the same:** the engine is generic. It integrates any business objects (orders, inventory, shipments, customers, invoices, payments, HR, anything a Capability Model can describe). The fintech choice in R5 is only the first hub, not the product's scope.

---

## R1 — Hub-and-spoke go-to-market + Connect SDK

### Problem
v1.0 positions us as a neutral broker between two companies. Every deal needs two buyers, two approvals and two onboarding projects. That is the slowest possible sales motion.

### Change
Sell to one **hub**: a company that needs to integrate with *many* counterparties (a fintech with hundreds of merchants, a buyer with hundreds of suppliers, a 3PL with hundreds of shippers). The hub embeds our **Connect SDK** in its own onboarding. Each **spoke** connects its system once, at whatever level it can (API, DB, UI, documents, nothing).

```
                 ┌──────────── Hub (pays) ────────────┐
                 │  product + embedded Connect widget │
                 └───────┬───────────┬────────────┬───┘
                         │           │            │
                     Spoke 1     Spoke 2      Spoke N
                  (Odoo API)  (on-prem SQL)  (Excel + email)
```

- **The hub pays** (per connected spoke + volume). Spokes join for free.
- **The network effect is real:** a spoke already connected for Hub 1 can be connected to Hub 2 in minutes because its Capability Model and canonical mapping already exist (with the spoke's consent).
- The **two-sided control plane stays**: every integration still has two owners, two views and two-party approval. Only the commercial motion changes.

### Connect SDK (new component, 🔴 build)
| Part | Description |
|---|---|
| `connect.js` widget | Drop-in UI in the hub's app: pick your system, authorize, or choose "no API / no system" paths |
| Hosted connect pages | Same flow as a link the hub can email or WhatsApp to a spoke |
| Hub API + webhooks | `POST /connections`, `GET /spokes/{id}/capabilities`, events such as `connection.ready`, `reconciliation.break` |
| White-label | Hub branding, custom domain, language (Arabic / English first) |
| Consent records | Who granted what scope to which hub, revocable, auditable |

---

## R2 — Cross-party State Ledger & Reconciler

### Problem
Every iPaaS (Boomi, Workato, n8n, Tray) moves data and retries on failure. None of them answers the question a business owner actually asks: **"do my partner and I agree on what happened?"** Lost webhooks, manual edits, partial failures and upstream bugs create silent drift that is found weeks later by accountants or angry customers.

### Change
Track every object that crosses between parties in a **State Ledger**, and continuously **reconcile** each side's view against it. Formance does this for money; we do it for any canonical entity.

**Value proposition shifts from "we connect you" to "we guarantee you and your partner stay in agreement".**

### Model

```
Business object (e.g. Order #8812)
  ├─ canonical key: { party_a_id, party_b_id, external_ids... }
  ├─ state machine: created → confirmed → shipped → delivered → settled
  ├─ observed view at A   (last sync, hash of tracked fields)
  ├─ observed view at B   (last sync, hash of tracked fields)
  └─ ledger entries       (append-only; every transition with source + run id)
```

- **State Ledger**: append-only, per tenant, in Postgres. Every transition records source party, integration run, payload hash and timestamp.
- **Money flows**: when an object carries value (payments, invoices, refunds, settlements), postings go into a double-entry ledger. Use **Formance Ledger** (open source; verify license at adoption) instead of building one.
- **Reconciler**: a scheduled Temporal workflow per integration that pulls both sides' current state (via the same connections), compares it with the ledger, and emits **breaks**.

### Break types
| Break | Example | Default action |
|---|---|---|
| `missing_at_target` | Order exists at A, never arrived at B | Auto-replay the integration run |
| `missing_at_source` | Object at B with no origin at A | Alert both parties |
| `state_mismatch` | A says *shipped*, B says *confirmed* | Re-sync if within SLA; otherwise alert |
| `value_mismatch` | Quantity 10 vs. 12; amount 1,000 vs. 1,050 | Alert; never auto-fix value fields |
| `orphan_money` | Payment received with no matching object | Route to matching queue (rules + agent suggestion) |
| `stale` | Object stuck in a state beyond SLA | Escalate per `sla` block |

The **Ops Agent** (v1.0 §4.1) gets a new input: breaks. It diagnoses root cause (mapping bug, upstream change, manual edit) and proposes a fix as a PR to the spec or mapping, never as a direct write.

### Integration Spec extension
```yaml
reconciliation:
  entity: canonical.Order
  match_on: [external_ids.party_a, external_ids.party_b]
  track_fields: [status, total_amount, currency, line_items[*].quantity]
  tolerance:
    total_amount: { abs: 0.01 }
  schedule: "*/30 * * * *"      # every 30 minutes
  lookback: 30d
  auto_heal: [missing_at_target, state_mismatch]
  on_break:
    notify: [party_a.ops, party_b.ops]
ledger:
  money: true                    # post value movements to the double-entry ledger
  accounts:
    receivable: "parties:{{party_b}}:receivable"
    settled:    "parties:{{party_a}}:settled"
```

### Product surface
- **Agreement score** per integration and per counterparty (% of objects in agreement)
- **Breaks inbox** shared by both parties, with suggested resolution
- **Proof of agreement export**: signed report for audits, disputes, or the hub's risk team

---

## R3 — Connectivity Ladder + Discovery Orchestrator

### Problem
v1.0 lists six ingestion paths but leaves picking one to a human, per company, once. Real companies are mixed: orders through an API, stock only in the database, prices only in Excel.

### Change
A **Discovery Orchestrator** walks a ladder of connection methods **per entity**, picks the highest tier that works, and records the choice in the Capability Model.

| Tier | Method | Reliability | Typical latency | Built on |
|---|---|---|---|---|
| T1 | Official API / webhooks | Highest | Real-time | Spec parsers, OAuth (Nango as design reference) |
| T2 | Docs / Postman → generated client | High | Real-time | Doc Reader agent |
| T3 | Database via Edge Agent (+ CDC) | High | Seconds | PostgREST, Debezium |
| T4 | Codebase → generated API | High after review | Real-time | Code Analyzer + API Builder agents |
| T5 | UI traffic → internal API (consented) | Medium; breaks on UI changes | Real-time | Playwright, mitmproxy, own Traffic Analyzer |
| T6 | Shared external sources | Medium–high | Hours | Connectors to tax e-invoicing portals (ETA Egypt, ZATCA KSA), marketplaces, open-banking statements, customs portals |
| T7 | Documents (email inbox, Excel, PDF) | Medium; needs confidence scoring | Minutes–hours | Docling + extraction agent |
| T8 | Human-as-API | Depends on people | Hours | See R4 |

Rules:
1. **Per entity, not per company.** `Order` may be T1 while `Inventory` is T3 and `PriceList` is T7.
2. **Every tier emits the same Capability Model**, so the Integration Spec is identical whatever tier serves an entity.
3. **Automatic upgrade.** When a company gains a better path (installs an ERP, exposes an API), the orchestrator re-runs discovery and upgrades the connection behind the same spec, then the Reconciler verifies nothing changed.
4. **Tier is visible to the hub.** Reliability and latency of each spoke's tier show up in the hub's dashboard and in SLAs.
5. **T6 sources are a network asset.** One ETA/ZATCA connector covers every compliant company in that country, with or without an ERP.

---

## R4 — Scenario 3 re-scoped: human-as-API and micro-apps

### Problem
v1.0 Phase 4 builds "a minimal system from templates". That is custom software delivery with a different name, and it conflicts with the risk "becoming a services agency" (v1.0 §10).

### Change
Treat "no system" as two more connector tiers, generated from the Canonical Model, not as a project.

**T8a — Human-as-API (default, ships in Phase 2)**
- The engine sends the counterparty a task when the spec needs input: a form link, an email, or a WhatsApp message ("Confirm order #8812: quantity and delivery date").
- Replies (form submit, email reply, uploaded file, chat message) are parsed by an agent into canonical events with confidence scores.
- From the integration's point of view, it is a slow API with the same Integration Spec.

**T8b — Generated micro-app (Phase 4, optional upsell)**
- For counterparties with recurring volume, generate a small app over the canonical entities they handle: tables, forms, status board, export.
- Data lives in our platform; the app *is* their system of record for that flow, and its API is T1 by construction.
- Use the low-code pattern of Appsmith / ToolJet / NocoBase. Prefer an Apache-2.0/MIT base or our own React-Admin/Refine generator (license notes in v1.0 Appendix B still apply).

Result: Scenario 3 stops being bespoke work and becomes the bottom of the ladder.

---

## R5 — First hub: fintech / embedded finance

### Recommendation
Start with fintechs (lenders, B2B BNPL, payment and collections platforms, invoice financing) in **Egypt first, then KSA** as the first hubs (see *Launch market* below).

### Why
| Factor | Why fintech wins |
|---|---|
| Pain | They must connect to hundreds of SMB merchants with no IT staff and every possible system (cloud ERP, on-prem, Excel, nothing). This is exactly the ladder. |
| Budget | Integration directly drives revenue (underwriting, collections). They pay per connected merchant. |
| Value of R2 | Money makes reconciliation essential, so the State Ledger is valued from day one. |
| Universal fallback | Mandatory e-invoicing (ETA, ZATCA) gives a T6 source that covers merchants with no system. |
| Network | A merchant connected for one lender can be offered to the next with consent. |

### Why it does not narrow the product
A fintech hub needs many entity types: company profile (KYB), sales orders, customers, inventory, invoices, bank statements, payments, and payment status written back to the merchant's system. The same engine later serves a retail buyer (orders, ASN, stock) or a 3PL (shipments, PODs) with a new canonical model and nothing else rebuilt.

### Watch-outs
- Central-bank and data-protection rules: consent records, data residency, audit trails (R1 consent + v1.0 security work cover most of it).
- Money write-back is high risk: two-party approval + dry-run + Reconciler before any production write.

### Launch market: Egypt first, KSA next (decided)
Technically the choice is small: it changes the T6 connector (ETA vs. ZATCA Fatoora), tax/registration fields in the canonical model, currency and language. Commercially it matters more.

| | Egypt | KSA |
|---|---|---|
| Spokes | Very large SMB base | Fewer, larger companies |
| Systems | Mostly Excel, local software or none → the lower ladder tiers matter most | More cloud ERP → more T1 |
| Hub budget | Lower; EGP currency risk | Higher; SAR pegged to USD |
| Sales cycle | Faster | Slower; local entity/presence often expected |
| Data residency | Lighter | Financial data likely must be hosted in-kingdom |
| Team cost | Lower | Higher |

*Regulatory points are indicative and must be confirmed with local counsel.*

**Why Egypt first:** it has the hardest cases (no API, no system). If the ladder works there, it works anywhere, and that builds the moat. Design partners and the team are cheaper and faster to get. KSA follows once one Egyptian hub is live with real numbers (agreement score, onboarding time), which shortens KSA sales cycles.

**Requirement from day one:** country is configuration, not code. Tenants carry a region; data residency, e-invoicing connector, tax fields, currency and language are resolved per region, so KSA (in-kingdom hosting included) is a deployment, not a rewrite.

## R6 — Semantic types instead of field-to-field mappings

### Problem
In v1.0 the mapping agent writes a JSONata mapping for every pair (A→B) or every company→canonical entity. Mappings are the most brittle artifact in the system: they break when either side changes, they are hard to review, and each new hub–spoke pair still needs mapping work. That weakens the network effect.

### Change
Borrow the core idea of **Orbital** and its **Taxi** language: describe *what each field means* with **semantic types**, and let a query/resolution engine compose sources automatically.

1. A **semantic type library** per vertical replaces most of the rigid canonical entities:
   ```taxi
   type TaxRegistrationNumber inherits String
   type CommercialRegistryNumber inherits String
   type InvoiceTotal inherits Decimal
   type CurrencyCode inherits String
   type MerchantId inherits String
   ```
2. Every Capability Model field gets a tag, whatever ladder tier it came from (API, DB, document, human form):
   ```yaml
   # inside the CM (OpenAPI 3.1 + our extensions)
   properties:
     tax_no:
       type: string
       x-taxi-type: { name: TaxRegistrationNumber }
       x-confidence: 0.94
       x-provenance: from_db
   ```
3. The **mapping agent becomes a tagging agent**: per field it predicts a semantic type with a confidence score (classification, not code generation). Low-confidence tags go to human review, exactly as before.
4. The **Integration Spec asks for data by meaning**, not by path:
   ```yaml
   steps:
     - id: merchant_profile
       find: MerchantProfile          # resolved across all of the spoke's sources
       where: { MerchantId: "{{ trigger.payload.merchant_id }}" }
       as: [CommercialRegistryNumber, TaxRegistrationNumber, MonthlySalesTotal]
   ```
   The resolver works out which connections and calls supply each field and joins them.
5. **JSONata stays** for real transformations only: currency, units, dates, enum translation, splitting/joining.

### Why it is better
| | v1.0 mappings | v1.1 semantic types |
|---|---|---|
| Work per new hub–spoke pair | New mapping | Usually none: both sides already tagged |
| Upstream change | Mapping breaks | Re-tag the changed field; queries keep working |
| Agent task | Generate transform code | Classify a field (easier to evaluate, higher accuracy) |
| Network effect | Linear | Each tagged spoke is reusable by every hub |
| Fits the ladder | Per tier | Same tags whatever tier serves the field |

### What we take from Orbital, and what we don't
The Orbital monorepo is multi-licensed; anything without its own license defaults to **BSL 1.1** (converts to Apache 2.0 four years after each release). Its `LICENSE_FAQ.md` explicitly says a license is required to *"provide configurable integration capabilities to end users"*, *"allow customers to create data pipelines"*, or *"provide services which compete with Orbital"*, which is exactly our product.

| Part | License | Decision |
|---|---|---|
| **Taxi** language and tooling (taxilang repo) | Apache 2.0 | **Use**: semantic type definitions, parser, OpenAPI `x-taxi-type` convention |
| **TaxiQL query engine** and its modules (`taxiql-query-engine`, `vyne-core-types`, `vyne-query-api`, `schema-management/*`, `datatype-converters`, …) | Apache 2.0 (per-module LICENSE files) | **Spike** as the read resolver; verify every transitive dependency |
| **Orbital platform** (UI, connectors, pipelines, auth, …) | BSL 1.1 | **Reference only**: UX, schema publishing, architecture |

### Limits to keep in mind
- **Stack:** Orbital/TaxiQL is Kotlin on the JVM; our plan is TypeScript + Python. If adopted, the resolver runs as a separate service behind an internal API.
- **Reads vs. writes:** Orbital shines at read-time federation (find, join, enrich). Writes, durable flows and reconciliation stay on Temporal + State Ledger. Semantic tags still help there: write targets are addressed by type too.
- **Vendor continuity:** small company; we only depend on the Apache-licensed parts, so we can fork if needed.

### Spike (Phase 0, 1–2 weeks)
1. Define ~40 semantic types for embedded finance (merchant profile, sales, invoices, payments, bank lines).
2. Tag two real spoke sources (one Odoo API, one SQL DB) and the ETA e-invoice schema.
3. Run TaxiQL queries that join them; measure correctness and latency.
4. Measure tagging-agent accuracy on the same fields.
5. **Decide:** embed TaxiQL engine, or keep Taxi as the type language and build a lighter resolver ourselves.

---

## Impact on the roadmap

| Phase | v1.0 | v1.1 |
|---|---|---|
| 0 | Pick vertical, CM + IS schemas, infra | Fintech hub in **Egypt** chosen; region-aware tenancy; 1–2 hub design partners with 10–20 spokes each; semantic type library v0 for embedded finance; State Ledger schema; **TaxiQL spike** (R6) |
| 1 (MVP) | S1 integrations, mapping agent, runtime, control plane | mapping agent → **semantic tagging agent**; `find`-by-type steps in the spec; + **Connect SDK v1**, + **Reconciler v1** (missing/state breaks, no auto-heal on values), + T6 connector for **ETA (Egypt)** |
| 2 | S2: Edge Agent, DB, code, traffic | + **Discovery Orchestrator**, + **T7 documents**, + **T8a human-as-API**, + Formance ledger for money flows |
| 3 | Network effect & scale | + **KSA launch** (ZATCA connector, in-kingdom deployment), + reuse spoke connections across hubs with consent, agreement score, proof-of-agreement export |
| 4 | S3 system builder, second vertical | **T8b micro-apps** (optional), second vertical (retail buyer or 3PL hub) |

**Revised MVP exit criteria:** 1 hub live with ≥20 spokes across ≥3 ladder tiers; ≥99.5% run success; ≥99% agreement score on reconciled entities; median spoke onboarding < 1 day.

## Remaining open decisions
1. ~~Egypt first or KSA first~~ → **Egypt first**, KSA in Phase 3
2. Self-hosted ledger (Formance) vs. our own Postgres ledger for non-money state only
3. Pricing per connected spoke vs. per reconciled object
4. Whether spokes get a free self-serve view of their own connections (helps the network, costs support)
5. Embed the TaxiQL engine (JVM service) or build our own resolver on Taxi types (decided by the R6 spike)

## Sources
- [Integuru — fintech](https://www.integuru.com/industries/fintech)
- [Nango — Tray.io Embedded alternatives](https://nango.dev/blog/tray-io-embedded-alternatives#how-does-nango-compare-to-tray-embedded)
- [OpenAlternative — integration platforms](https://openalternative.co/categories/developer-tools/integration-platforms)
- [OpenAlternative — Retool alternatives](https://openalternative.co/alternatives/retool)
- [Formance — Flows](https://www.formance.com/platform/flows)
- [Orbital docs](https://orbitalhq.com/docs)
- [Orbital on GitHub — license](https://github.com/orbitalapi/orbital?tab=License-1-ov-file) (README, LICENSE and LICENSE_FAQ.md reviewed from a clone; last commit March 2026)
- [Taxi language](https://taxilang.org)
