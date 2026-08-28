"""Collection of real telemetry from the machine running the agent."""

import platform
import socket
from datetime import UTC, datetime

import psutil

from app.models import SystemMetrics


# Prime psutil's process-wide CPU measurement. Later calls remain non-blocking and
# report CPU activity since this call (or since the preceding API request).
psutil.cpu_percent(interval=None)


def get_hostname() -> str:
    """Return the local hostname without resolving network addresses."""
    return socket.gethostname()


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def collect_system_metrics() -> SystemMetrics:
    """Collect a point-in-time snapshot of host system metrics."""
    collected_at = utc_now()
    boot_timestamp = psutil.boot_time()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    logical_cpu_count = psutil.cpu_count(logical=True)

    if logical_cpu_count is None:
        raise RuntimeError("Logical CPU count is unavailable")

    return SystemMetrics(
        hostname=get_hostname(),
        platform=platform.system(),
        platform_release=platform.release(),
        architecture=platform.machine(),
        cpu_usage_percent=psutil.cpu_percent(interval=None),
        cpu_logical_count=logical_cpu_count,
        memory_total_bytes=memory.total,
        memory_used_bytes=memory.used,
        memory_usage_percent=memory.percent,
        disk_total_bytes=disk.total,
        disk_used_bytes=disk.used,
        disk_usage_percent=disk.percent,
        uptime_seconds=max(0.0, collected_at.timestamp() - boot_timestamp),
        boot_time=datetime.fromtimestamp(boot_timestamp, tz=UTC),
        collected_at=collected_at,
    )
