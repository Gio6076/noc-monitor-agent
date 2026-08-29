# NOC Monitor Agent

A lightweight FastAPI agent that reports local system, network, and explicitly configured service telemetry.

## Service checks

Service checks are configured with `NOC_SERVICE_TARGETS`, a JSON array. The agent checks only these explicit targets; it does not discover hosts or scan ports. An empty or unset array produces zero services.

Supported entries:

- TCP: `{"name":"Local SSH","type":"tcp","host":"127.0.0.1","port":22}` tests whether a TCP connection can be established. It does not authenticate, send credentials, or run commands.
- HTTP: `{"name":"NOC Agent Health","type":"http","url":"http://127.0.0.1:8000/health"}` performs a GET. HTTPS uses the same shape with `"type":"https"` and an `https://` URL.

For the current macOS development checks, start the agent from the project directory with:

```sh
export NOC_SERVICE_TARGETS='[{"name":"NOC Agent Health","type":"http","url":"http://127.0.0.1:8000/health"},{"name":"Local SSH","type":"tcp","host":"127.0.0.1","port":22}]'
export NOC_SERVICE_CHECK_TIMEOUT_SECONDS=2
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`NOC_SERVICE_CHECK_TIMEOUT_SECONDS` is the per-target timeout and accepts values from `0.1` through `30` seconds; it defaults to `2`. Checks run concurrently with at most 10 workers. HTTP URLs in telemetry omit credentials, query strings, and fragments. Configuration rejects malformed JSON, unknown types, invalid ports, URL/type mismatches, and URLs containing credentials.

A service reported as `down` means that target could not be reached or did not return a successful HTTP status (200–399). It does not mean the monitoring agent itself is down; use `/health` to determine agent availability. A local SSH result may legitimately be `down` when macOS Remote Login is disabled.

See [.env.example](.env.example) for the same development configuration. Keep machine-specific values in the process environment or an uncommitted `.env`; `.env` is ignored by Git.

## API

With the agent running, inspect the configured checks and core telemetry:

```sh
curl http://127.0.0.1:8000/api/services
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/system
curl http://127.0.0.1:8000/api/network
```

