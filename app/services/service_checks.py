"""TCP and HTTP checks for explicitly configured monitoring targets."""

import json
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from app.models import HttpServiceCheck, ServiceMetrics, TcpServiceCheck
from app.services.system_metrics import utc_now

TARGETS_ENV = "NOC_SERVICE_TARGETS"
TIMEOUT_ENV = "NOC_SERVICE_CHECK_TIMEOUT_SECONDS"
DEFAULT_TIMEOUT_SECONDS = 2.0
MAX_TIMEOUT_SECONDS = 30.0
MAX_TARGETS = 100


@dataclass(frozen=True)
class TcpTarget:
    name: str
    host: str
    port: int
    type: Literal["tcp"] = "tcp"


@dataclass(frozen=True)
class HttpTarget:
    name: str
    url: str
    type: Literal["http", "https"]


ServiceTarget = TcpTarget | HttpTarget


def _required_string(item: dict[str, object], field: str, index: int) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Target {index} must have a non-empty {field}")
    return value.strip()


def load_targets(value: str | None = None) -> list[ServiceTarget]:
    """Load and validate the allowlist of targets from a JSON environment value."""
    raw_value = os.getenv(TARGETS_ENV, "[]") if value is None else value
    try:
        raw_targets = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{TARGETS_ENV} must contain valid JSON") from exc

    if not isinstance(raw_targets, list):
        raise ValueError(f"{TARGETS_ENV} must contain a JSON array")
    if len(raw_targets) > MAX_TARGETS:
        raise ValueError(f"{TARGETS_ENV} supports at most {MAX_TARGETS} targets")

    targets: list[ServiceTarget] = []
    for index, raw_target in enumerate(raw_targets):
        if not isinstance(raw_target, dict):
            raise ValueError(f"Target {index} must be a JSON object")
        name = _required_string(raw_target, "name", index)
        target_type = _required_string(raw_target, "type", index).lower()

        if target_type == "tcp":
            host = _required_string(raw_target, "host", index)
            port = raw_target.get("port")
            if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
                raise ValueError(f"TCP target {index} must have a port from 1 to 65535")
            targets.append(TcpTarget(name=name, host=host, port=port))
            continue

        if target_type in {"http", "https"}:
            url = _required_string(raw_target, "url", index)
            parsed = urlsplit(url)
            if parsed.scheme.lower() != target_type or not parsed.hostname:
                raise ValueError(f"HTTP target {index} must have a valid {target_type} URL")
            if parsed.username is not None or parsed.password is not None:
                raise ValueError(f"HTTP target {index} must not contain credentials")
            try:
                parsed.port
            except ValueError as exc:
                raise ValueError(f"HTTP target {index} has an invalid port") from exc
            targets.append(HttpTarget(name=name, url=url, type=target_type))
            continue

        raise ValueError(f"Target {index} has unsupported type {target_type!r}")

    return targets


def get_timeout_seconds(value: str | None = None) -> float:
    """Return the configured per-target timeout within safe bounds."""
    raw_value = os.getenv(TIMEOUT_ENV, str(DEFAULT_TIMEOUT_SECONDS)) if value is None else value
    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{TIMEOUT_ENV} must be a number") from exc
    if not 0.1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"{TIMEOUT_ENV} must be between 0.1 and {MAX_TIMEOUT_SECONDS} seconds")
    return timeout


def _safe_url(url: str) -> str:
    """Remove user info, query parameters, and fragments from a displayed URL."""
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    display_host = f"[{hostname}]" if ":" in hostname else hostname
    netloc = f"{display_host}:{parsed.port}" if parsed.port is not None else display_host
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def check_tcp(target: TcpTarget, timeout: float) -> TcpServiceCheck:
    """Consider a TCP target up when a connection can be established."""
    started_at = time.monotonic()
    status: Literal["up", "down"] = "down"
    try:
        with socket.create_connection((target.host, target.port), timeout=timeout):
            status = "up"
    except Exception:
        # A target-level DNS, address, socket, or timeout failure is a down
        # result and must not abort checks for the remaining allowlisted targets.
        pass

    return TcpServiceCheck(
        name=target.name,
        host=target.host,
        port=target.port,
        type="tcp",
        status=status,
        response_time_ms=round((time.monotonic() - started_at) * 1000, 2),
        checked_at=utc_now(),
    )


def check_http(target: HttpTarget, timeout: float) -> HttpServiceCheck:
    """Perform a verified HTTP GET without reading or returning its response body."""
    started_at = time.monotonic()
    status: Literal["up", "down"] = "down"
    status_code: int | None = None
    request = Request(target.url, headers={"User-Agent": "noc-monitor-agent/0.1"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = response.status
            if 200 <= status_code < 400:
                status = "up"
    except HTTPError as exc:
        status_code = exc.code
        exc.close()
    except (URLError, OSError, TimeoutError):
        pass
    except Exception:
        # Keep malformed remote responses and other target-specific client
        # failures isolated from the aggregate endpoint.
        pass

    return HttpServiceCheck(
        name=target.name,
        url=_safe_url(target.url),
        type=target.type,
        status=status,
        http_status_code=status_code,
        response_time_ms=round((time.monotonic() - started_at) * 1000, 2),
        checked_at=utc_now(),
    )


def _check_target(target: ServiceTarget, timeout: float) -> TcpServiceCheck | HttpServiceCheck:
    if isinstance(target, TcpTarget):
        return check_tcp(target, timeout)
    return check_http(target, timeout)


def collect_service_metrics() -> ServiceMetrics:
    """Run each configured check independently and summarize the current state."""
    collected_at = utc_now()
    targets = load_targets()
    if not targets:
        return ServiceMetrics(
            collected_at=collected_at,
            total_services=0,
            services_up=0,
            services_down=0,
            services=[],
        )

    timeout = get_timeout_seconds()
    with ThreadPoolExecutor(max_workers=min(10, len(targets))) as executor:
        services = list(executor.map(lambda target: _check_target(target, timeout), targets))
    services_up = sum(service.status == "up" for service in services)
    return ServiceMetrics(
        collected_at=collected_at,
        total_services=len(services),
        services_up=services_up,
        services_down=len(services) - services_up,
        services=services,
    )
