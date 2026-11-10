# Spec 001: Service skeleton and contracts v0.1.0

| | |
|---|---|
| **Status** | Implemented (skeleton from the agent-platform service template; FR-008, FR-009 added here) |
| **Plan** | [plan.md](plan.md) · **Tasks** [tasks.md](tasks.md) |

## Summary
The hexagonal skeleton every agent service starts from: a health endpoint, the shared error
envelope, request telemetry, the layer rule, a versioned provided contract and a container
image. Service features build on it in later specs, with IDs continuing from the highest
used here.

## Out of scope
Any service behaviour beyond health. Serving search and ingest is spec 002; this spec
publishes the contracts so the orchestrator (search) and docling-pipeline (ingest) can pin
them and build against them now.

---

## Functional requirements

### FR-001: Health endpoint
- **Given** the service is running, **when** `GET /healthz` is called without credentials,
  **then** it returns `200` `{"status": "ok", "version": "<package version>", "uptime_s": <n>}`.

### FR-002: Error envelope
- **Given** a request fails, **when** the response is sent, **then** it is the conventions'
  envelope `{"error": {"type", "message"}, "trace_id"}` with the status for that `type`.
- Domain errors map by `type`; schema validation failures are `422 invalid_request` naming
  the fields but not echoing their values; unknown routes are `404 not_found`; unhandled
  exceptions are `500 internal` with no exception text; `429` and `503` carry `retry-after`.

## Observability

### FR-003: Request telemetry
- **Given** a request (other than `/healthz`), **when** it completes, **then** there is an
  HTTP server span named for the route template and an `http.server.request.duration`
  metric with bounded attributes, and logs emitted while handling it are JSON lines carrying
  its `trace_id` and `span_id` (and are exported through the OpenTelemetry logs pipeline).
- `/healthz` produces no spans.

### FR-004: Telemetry configuration and lifecycle
- Exporters `none` / `console` / `otlp` per signal from `OTEL_TRACES_EXPORTER`,
  `OTEL_LOGS_EXPORTER`, `OTEL_METRICS_EXPORTER` (default `none`); the OTLP endpoint from
  `OTEL_EXPORTER_OTLP_ENDPOINT`; `service.name` from `OTEL_SERVICE_NAME` (default
  `retrieval-service`); `deployment.environment.name` from `RETRIEVAL_SERVICE_ENVIRONMENT`.
  Invalid values fail startup.
- **Given** the service shuts down, **then** buffered telemetry is flushed and the
  providers are shut down.

## Architecture and contract

### FR-005: Layer rule
- `scripts/check_layers.py` passes: `domain` imports only the standard library,
  `application` adds only the OpenTelemetry API, inbound and outbound adapters don't import
  each other, and only `bootstrap.py` wires adapters (ADR 0002).

### FR-006: Provided contract
- `contracts/openapi.yaml` is valid OpenAPI 3.1 with a semver `info.version`, passes
  `scripts/contract_check.py` against `main`, and the HTTP adapter's responses for
  `/healthz` and errors validate against its schemas.

### FR-007: Container image
- Two-stage build from `uv.lock` with a uv-managed interpreter, non-root runtime, pinned
  base images, `HEALTHCHECK` on `/healthz`, listening on `$PORT` (default `8090`).

## Retrieval contracts (agent-platform ADR 0005)

### FR-008: Search contract
- `contracts/mcp/search.json` (MCP tool `search`, v0.1.0) and `POST /v1/search` in
  `contracts/openapi.yaml` take the same input: `query` (1–2000 characters), `k`
  (1–50, default 8) and an optional `collection`, and nothing else
  (`additionalProperties: false`). There is no user, tenant, group or filter argument.
- `POST /v1/search` requires `x-agent-identity`; authorization comes only from it.
- Results carry `chunk_id`, `document_id`, `collection`, `score`, `text` and `source`
  (title, URI) for citations, plus `truncated` and `tokens` for the token budget.

### FR-009: Ingest contract
- `PUT /v1/collections/{collection}/documents/{document_id}` replaces a document's chunks
  atomically for one `version`, with an `acl` (tenants, groups, users) and 1–5000 chunks
  of text (`chunk_id`, `order`, `text`, string `metadata`). Clients send text only; the
  service embeds it. Repeating a version returns `unchanged`; an older version is `409`.
- `GET` returns the stored version and chunk count; `DELETE` removes the document (`204`).
- Ingest uses the service-to-service bearer credential, not an end-user identity.

## Non-functional requirements

### NFR-001: Reproducible environment
- uv-managed interpreter, committed `uv.lock`, image built with `--locked`.

### NFR-002: Telemetry never breaks the service
- **Given** the OTLP collector is unreachable, **when** requests arrive, **then** they
  succeed and shutdown completes in bounded time.

### NFR-003: Every requirement is tested
- Each ID here is cited by a test, and no test cites an unknown ID.

### NFR-004: Offline default tests
- The default suite opens no non-loopback network connection. Tests needing real external
  services are marked `live` and opt-in.
