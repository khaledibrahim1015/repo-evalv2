# Agentic B2B Integration Engine — Market Scan

*Prepared: October 6, 2026*

## The idea

A generic, agent-driven engine that integrates two B2B companies regardless of their starting point:

1. **Both sides have APIs** — ingest Swagger/OpenAPI, Postman collections, written docs, or fetch the online API docs, then build the integration.
2. **One or both sides have no API** — generate the API from their codebase (or database / UI).
3. **One or both sides have no system at all** — build the missing system, then integrate (phase 2).

Across all three, provide **durable infrastructure** (retries, queues, monitoring, security), because most B2B companies' infrastructure is not solid enough.

## Short answer

**No single product does all three scenarios end to end.** The pieces exist, mostly separately. The gap between them is the opportunity.

---

## What exists for each scenario

### Scenario 1 — Both sides have APIs

Well covered.

**Nango (open source, self-hostable)** — closest match.
- Open-source agentic API integrations platform, 800+ APIs.
- Developers pair a coding agent (Claude Code, Cursor, Codex) with Nango's AI builder skill to build and deploy integrations.
- Handles auth, execution, scaling, observability.
- **Gap:** built for one SaaS product connecting to many APIs, not as a neutral broker between two companies.
- https://github.com/NangoHQ/nango

**Enterprise iPaaS (closed source)** — Boomi, MuleSoft, Workato all went agentic in 2026.
- **Boomi Companion:** design, build, test and deploy Boomi integrations from Claude Code, Codex or GitHub Copilot. Strong for EDI / B2B and governance.
- **MuleSoft Vibes / Anypoint Code Builder:** generate integrations from natural language.
- **Gap:** expensive, sales-led pricing, integrations are locked to the vendor platform.

### Scenario 2 — One side has no API (generate it)

Partially covered; tools are older and mostly not agentic.

| Source | Tool | Notes |
|---|---|---|
| Database | PostgREST, Hasura, sandman2 (open source) | Instant REST/GraphQL over a DB. CRUD only, no business logic. |
| Legacy code / mainframe | OpenLegacy (commercial) | Analyzes legacy source, terminal screens or DB; generates REST/SOAP as a deployable Java project. |
| Web UI with no API | Integuru (open source, AGPL-3.0) | Takes browser network traffic (HAR) + cookies + a prompt; outputs Python that calls the platform's internal endpoints. |

**Cautions on Integuru:** reverse-engineered APIs can violate terms of service and break without warning when internal endpoints change. In a B2B deal where both parties consent, the ToS concern largely disappears. AGPL-3.0 has disclosure obligations if you run it as a hosted service.

**Missing in the market:** an agent that reads a company's **codebase** and produces a proper business-level API layer. This would be built in-house (coding agent + guardrails + tests).

### Scenario 3 — One side has no system (build it)

Not offered by any integration product. This is custom software delivery, accelerated with coding agents and industry templates.

### Durability layer

No need to invent this — standard open-source building blocks:

- **Temporal** — durable, retryable workflows
- **Kafka / RabbitMQ** — queues, buffering, replay
- **Kong** (or similar API gateway) — auth, rate limiting
- **OpenTelemetry** — tracing, metrics, alerting

**Value add:** package these as a managed, multi-tenant "integration backbone" so smaller B2B companies don't have to operate them.

---

## Where the product fits

| Layer | Use existing | Build yourselves |
|---|---|---|
| Ingest specs (Swagger, Postman, docs, online) | OpenAPI parsers, Nango | Agent that fetches and normalizes docs |
| Map Company A ↔ Company B data | — | **Agentic schema mapping + tests (core IP)** |
| Generate API when missing | PostgREST / Hasura (DB), Integuru (UI) | **Codebase → API agent** |
| Build missing system | Coding agents | Templates per industry |
| Durable runtime | Temporal, Kafka, Kong, OpenTelemetry | Packaged multi-tenant hosting |

## Differentiator

A **neutral two-sided broker**: onboard both companies, accept any starting point (API, codebase, nothing), and own reliability end to end. Existing tools assume at least one side is a software company with its own engineers.

## Suggested path

1. **MVP (Scenario 1):** Nango + Temporal + an agent for spec ingestion and A↔B data mapping.
2. **Phase 2 (Scenario 2):** codebase → API agent; DB → API via PostgREST/Hasura; UI → API via Integuru-style approach (with consent).
3. **Phase 3 (Scenario 3):** build-the-missing-system offering, using templates per industry.
4. **Throughout:** managed durability layer as the recurring-revenue core.

---

## Sources

- [Nango – Five ways to build product integrations in 2026](https://nango.dev/blog/four-ways-to-build-in-app-integrations)
- [Nango docs – Intro](https://nango.dev/docs/getting-started/intro-to-nango)
- [Nango on GitHub](https://github.com/NangoHQ/nango)
- [Integuru on GitHub](https://github.com/Integuru-AI/Integuru)
- [DEV.co – Integuru overview](https://dev.co/ai/frameworks/integuru)
- [ISG – Boomi analyst perspective](https://research.isg-one.com/analyst-perspectives/boomi-enables-enterprise-data-and-agent-activation)
- [Boomi – Innovations May 2026](https://boomi.com/blog/boomi-innovations-may-2026/)
- [Salesforce – MuleSoft TDX 2026](https://www.salesforce.com/events/webinars/top-developer-productivity-insights-tdx-2026-mulesoft/?bc=OTH)
- [Gumloop – Boomi alternatives](https://www.gumloop.com/blog/boomi-alternatives)
- [OpenLegacy – Concept & Architecture](https://openlegacy.atlassian.net/wiki/x/AYAmJw)
- [sandman2 on gittrend](https://gittrend.io/repo/jeffknupp/sandman2)
