"""Collection of real network telemetry from the local machine."""

import ipaddress
import socket
import threading
import time

import psutil

from app.models import NetworkInterfaceMetrics, NetworkMetrics
from app.services.system_metrics import get_hostname, utc_now


class ThroughputSampler:
    """Calculate throughput between calls from cumulative host counters."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._previous: tuple[float, int, int] | None = None

    def sample(self, bytes_received: int, bytes_sent: int) -> tuple[float | None, float | None]:
        now = time.monotonic()
        with self._lock:
            previous = self._previous
            self._previous = (now, bytes_received, bytes_sent)

        if previous is None:
            return None, None

        previous_time, previous_received, previous_sent = previous
        elapsed = now - previous_time
        received_delta = bytes_received - previous_received
        sent_delta = bytes_sent - previous_sent
        if elapsed <= 0:
            return None, None

        inbound_rate = received_delta / elapsed if received_delta >= 0 else None
        outbound_rate = sent_delta / elapsed if sent_delta >= 0 else None
        return inbound_rate, outbound_rate


_throughput_sampler = ThroughputSampler()


def _is_non_loopback(address: str) -> bool:
    """Return whether an IPv4/IPv6 address is not a loopback address."""
    address_without_scope = address.split("%", maxsplit=1)[0]
    try:
        return not ipaddress.ip_address(address_without_scope).is_loopback
    except ValueError:
        return False


def _collect_interfaces() -> list[NetworkInterfaceMetrics]:
    addresses_by_name = psutil.net_if_addrs()
    stats_by_name = psutil.net_if_stats()
    counters_by_name = psutil.net_io_counters(pernic=True)
    interfaces: list[NetworkInterfaceMetrics] = []

    for name, addresses in addresses_by_name.items():
        stats = stats_by_name.get(name)
        counters = counters_by_name.get(name)
        if stats is None or counters is None:
            continue

        ipv4_addresses = [item.address for item in addresses if item.family == socket.AF_INET]
        ipv6_addresses = [item.address for item in addresses if item.family == socket.AF_INET6]

        flags = {flag.strip().lower() for flag in stats.flags.split(",")}
        # Prefer the OS-provided interface flag, with address inspection ensuring
        # unnamed/flagless loopback-only interfaces are also omitted.
        if "loopback" in flags or not any(
            _is_non_loopback(address) for address in ipv4_addresses + ipv6_addresses
        ):
            continue

        interfaces.append(
            NetworkInterfaceMetrics(
                name=name,
                is_up=stats.isup,
                mtu=stats.mtu,
                speed_mbps=stats.speed if stats.speed > 0 else None,
                ipv4_addresses=ipv4_addresses,
                ipv6_addresses=ipv6_addresses,
                bytes_sent=counters.bytes_sent,
                bytes_received=counters.bytes_recv,
                packets_sent=counters.packets_sent,
                packets_received=counters.packets_recv,
            )
        )

    return interfaces


def collect_network_metrics() -> NetworkMetrics:
    """Collect host and per-interface network counters without blocking."""
    counters = psutil.net_io_counters()
    if counters is None:
        raise RuntimeError("Host network counters are unavailable")

    inbound_rate, outbound_rate = _throughput_sampler.sample(
        bytes_received=counters.bytes_recv,
        bytes_sent=counters.bytes_sent,
    )

    return NetworkMetrics(
        hostname=get_hostname(),
        collected_at=utc_now(),
        total_bytes_sent=counters.bytes_sent,
        total_bytes_received=counters.bytes_recv,
        total_packets_sent=counters.packets_sent,
        total_packets_received=counters.packets_recv,
        total_errors_in=counters.errin,
        total_errors_out=counters.errout,
        total_drops_in=counters.dropin,
        total_drops_out=counters.dropout,
        inbound_bytes_per_second=inbound_rate,
        outbound_bytes_per_second=outbound_rate,
        interfaces=_collect_interfaces(),
    )
