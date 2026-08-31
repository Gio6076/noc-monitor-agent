# NOC Monitor Agent

A lightweight FastAPI monitoring agent that exposes read-only host, network, and explicitly configured service telemetry for the NOC Monitoring Platform.

## Project links

- [NOC Dashboard repository](https://github.com/Gio6076/noc-dashboard)
- [Public dashboard demo](https://noc-dashboard-theta.vercel.app/)

The public dashboard demo is a hosted UI demonstration. It does not connect directly to this agent.

## Overview

The agent runs on a monitored host and provides current observations through a small HTTP API. It collects system and network metrics locally and can perform HTTP(S) and TCP checks against an explicit, environment-configured target list.

In the broader NOC Monitoring Platform, an independent collector retrieves these observations and persists monitoring data in PostgreSQL for the dashboard. This agent does not own historical storage, persistent alert lifecycle state, or reliability analytics; it exposes the current state needed by those downstream components.

## Architecture role

```text
Monitored Host → NOC Monitor Agent → Independent Collector → PostgreSQL
                → Read Models / Alerts / Reliability Analytics → NOC Dashboard
```

The agent is intentionally simple and read-only with respect to the monitored host. It does not discover hosts, scan networks or ports, or maintain a monitoring schedule.

## API endpoints

All endpoints are `GET` routes. FastAPI also exposes interactive documentation at `/docs` and an OpenAPI schema at `/openapi.json`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Returns agent name, version, running status, and documentation path. |
| `GET` | `/health` | Returns a lightweight API health response with hostname and timestamp. |
| `GET` | `/api/system` | Returns a current snapshot of host system telemetry. |
| `GET` | `/api/network` | Returns current host network counters and non-loopback interface telemetry. |
| `GET` | `/api/services` | Runs and returns the current state of explicitly configured HTTP(S) and TCP targets. |

## Telemetry

### System

`GET /api/system` reports:

- Host identity: `hostname`, `platform`, `platformRelease`, and `architecture`
- CPU: `cpuUsagePercent` and `cpuLogicalCount`
- Memory: total bytes, used bytes, and usage percentage
- Root filesystem disk: total bytes, used bytes, and usage percentage
- `uptimeSeconds`, `bootTime`, and `collectedAt`

### Network

`GET /api/network` reports host totals for bytes, packets, inbound/outbound errors, and inbound/outbound drops. It also reports sampled `inboundBytesPerSecond` and `outboundBytesPerSecond`; these rates are `null` until a previous sample is available.

Each returned non-loopback interface includes its name, administrative state, MTU, optional link speed, IPv4/IPv6 addresses, byte counters, and packet counters. Loopback-only interfaces are omitted.

## Service monitoring

Service targets come only from `NOC_SERVICE_TARGETS`, which must contain a JSON array. Supported target shapes are:

- TCP: `{"name":"Example TCP Service","type":"tcp","host":"127.0.0.1","port":5432}`
- HTTP(S): `{"name":"Example Health Endpoint","type":"http","url":"http://127.0.0.1:8000/health"}`

Checks use the following semantics:

- HTTP and HTTPS targets perform an HTTP `GET`; status codes `200`–`399` are `up`.
- TCP targets are `up` when an explicit connection can be established. They do not authenticate, send credentials, or run commands.
- Each target is checked independently, with no retries.
- Checks run concurrently with at most 10 workers.
- The target list accepts at most 100 entries. An unset or empty list returns zero services.
- `responseTimeMs`, status, timestamps, and an HTTP status code where applicable are returned for each target.
- Returned HTTP(S) URLs omit query strings and fragments. URLs containing user credentials are rejected during configuration parsing.

A `down` service result describes that target check; it does not mean the agent API is unavailable. Use `/health` for agent availability.

## Configuration

The agent reads these environment variables:

| Variable | Description | Default / valid range |
| --- | --- | --- |
| `NOC_SERVICE_TARGETS` | JSON array of explicit TCP and HTTP(S) targets. | `[]` |
| `NOC_SERVICE_CHECK_TIMEOUT_SECONDS` | Per-target connection/request timeout. | `2` seconds; `0.1`–`30` seconds |

Example configuration uses local placeholder services only:

```sh
export NOC_SERVICE_TARGETS='[
  {"name":"Example Health Endpoint","type":"http","url":"http://127.0.0.1:8000/health"},
  {"name":"Example TCP Service","type":"tcp","host":"127.0.0.1","port":5432}
]'
export NOC_SERVICE_CHECK_TIMEOUT_SECONDS=2
```

TCP ports must be integers from `1` through `65535`. HTTP(S) URLs must have a matching `http` or `https` scheme and a hostname. Keep machine-specific values in the process environment or an uncommitted `.env`; the checked-in [.env.example](.env.example) contains development-only examples.

## Running locally

This project requires Python `3.14+`, uses [uv](https://docs.astral.sh/uv/), and declares FastAPI and psutil as its runtime dependencies.

```sh
uv sync
uv run fastapi run app/main.py --host 127.0.0.1 --port 8000
```

With the agent running, browse to <http://127.0.0.1:8000/docs> or query an endpoint:

```sh
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/system
curl http://127.0.0.1:8000/api/network
curl http://127.0.0.1:8000/api/services
```

## Data contract and design

Pydantic models define the response contracts. Python fields use `snake_case`, while JSON responses use lower camel case aliases such as `platformRelease` and `collectedAt`. Timestamps are timezone-aware ISO 8601 values. Service results are sanitized for display where applicable, including removal of URL query strings and fragments.

The API returns current observations at request time. It does not persist samples, reconcile persistent alerts, or calculate historical reliability metrics.

## Security and deployment boundary

This agent is intended for controlled or private environments. It reads local telemetry and performs only the explicitly configured checks; it is not a vulnerability scanner or network discovery tool. The API currently has no built-in authentication or TLS layer. The public dashboard deployment does not directly access the agent, and agent endpoints should not be exposed publicly without a separate secured architecture.

## Testing

The repository includes `unittest` coverage for service-target parsing and validation, including:

- loading explicit HTTP and TCP targets
- rejecting HTTP URL credentials and invalid TCP ports
- sanitizing query strings and fragments from returned URLs
- enforcing timeout parsing and bounds

Run the test suite with:

```sh
uv run python -m unittest discover -s tests -v
```

No separate formatter, linter, or type-check command is configured in `pyproject.toml`.

## Project structure

```text
app/
├── main.py                         # FastAPI application and routes
├── models.py                       # Pydantic response models
└── services/
    ├── system_metrics.py           # Host telemetry collection
    ├── network_metrics.py          # Network counters and interfaces
    └── service_checks.py           # Explicit HTTP(S)/TCP checks
tests/
└── test_service_checks.py          # Service configuration tests
docs/
└── persistent-monitoring-architecture.md
```

## Relationship to NOC Dashboard

This agent is one layer of the full system.

The [NOC Dashboard repository](https://github.com/Gio6076/noc-dashboard) owns the independent collector, PostgreSQL persistence, current-state read models, historical monitoring, persistent alert lifecycle, reliability analytics, and UI. This repository owns host telemetry collection, network telemetry collection, configured service checks, and FastAPI exposure of current observations.

## Current status and roadmap

### Implemented

- FastAPI endpoints for agent information, health, system telemetry, network telemetry, and configured service checks
- Pydantic response contracts with camelCase JSON aliases
- Local system and network collection through psutil
- Explicit HTTP(S) `GET` and TCP connection checks with bounded concurrency and configurable timeouts
- Service-target validation and safe URL presentation

### Planned

- Deployment as an always-on Linux service when the Linux monitoring host is available
- `systemd` supervision as part of the broader lab deployment
- A future authenticated and secured remote-ingestion architecture

These deployment and security items are not implemented in this repository.

## Author

Giovani Paulo R. Ebarola
BS Information Technology student
