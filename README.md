# retrieval-service

Retrieval for the agent services: an MCP search tool and an ingest API over one index, with per-user access filtering and token-budgeted results.

Part of the agent services; cross-service conventions and decisions live in
[agent-platform](https://github.com/narendersurabhi/agent-platform). Created from its
service template (`.copier-answers.yml` records the version).

## Quick start

```bash
uv sync                      # uv-managed Python + locked dependencies in .venv
uv run pre-commit install    # git hooks: the only quality gate (no hosted CI)
uv run pytest                # offline suite
uv run retrieval-service    # http://localhost:8090/healthz
docker compose up --build    # with Grafana LGTM on http://localhost:3000
```

## Layout (ports and adapters)

| Path | Holds | May import |
|---|---|---|
| `src/retrieval_service/domain/` | entities, value objects, errors | standard library |
| `src/retrieval_service/application/` | use cases, ports | + domain, OpenTelemetry API |
| `src/retrieval_service/adapters/inbound/` | HTTP routes, queue consumers | anything but outbound adapters and bootstrap |
| `src/retrieval_service/adapters/outbound/` | port implementations | anything but inbound adapters and bootstrap |
| `src/retrieval_service/infrastructure/` | settings, telemetry setup | anything but adapters and bootstrap |
| `src/retrieval_service/bootstrap.py` | the composition root | anything |

## Contract

The provided contract is [contracts/openapi.yaml](contracts/openapi.yaml) (MCP tools, if
any, in `contracts/mcp/`). Change it only with a version bump; breaking changes bump MAJOR
and keep the old major served. Contracts this service consumes are pinned under
`contracts/consumed/<provider>/`.

## Configuration

| Variable | Default | |
|---|---|---|
| `RETRIEVAL_SERVICE_ENVIRONMENT` | `dev` | `deployment.environment.name` |
| `RETRIEVAL_SERVICE_LOG_LEVEL` | `INFO` | level exported through OTLP |
| `PORT` | `8090` | listen port |
| `OTEL_TRACES_EXPORTER` / `OTEL_LOGS_EXPORTER` / `OTEL_METRICS_EXPORTER` | `none` | `none`, `console` or `otlp` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | | OTLP/HTTP collector |
| `OTEL_SERVICE_NAME` | `retrieval-service` | `service.name` |

## Process

Spec-driven: see [specs/constitution.md](specs/constitution.md) and
[specs/README.md](specs/README.md). Pull template updates with `uvx copier update --trust`.
