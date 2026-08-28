"""Typed API response models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    """Convert a snake_case field name to lower camel case."""
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    """Base model that exposes idiomatic Python fields as camelCase JSON."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AgentInfo(ApiModel):
    service_name: str
    version: str
    status: str
    documentation_path: str


class HealthStatus(ApiModel):
    status: str
    hostname: str
    timestamp: datetime


class SystemMetrics(ApiModel):
    hostname: str
    platform: str
    platform_release: str
    architecture: str
    cpu_usage_percent: float
    cpu_logical_count: int
    memory_total_bytes: int
    memory_used_bytes: int
    memory_usage_percent: float
    disk_total_bytes: int
    disk_used_bytes: int
    disk_usage_percent: float
    uptime_seconds: float
    boot_time: datetime
    collected_at: datetime


class NetworkInterfaceMetrics(ApiModel):
    name: str
    is_up: bool
    mtu: int
    speed_mbps: int | None
    ipv4_addresses: list[str]
    ipv6_addresses: list[str]
    bytes_sent: int
    bytes_received: int
    packets_sent: int
    packets_received: int


class NetworkMetrics(ApiModel):
    hostname: str
    collected_at: datetime
    total_bytes_sent: int
    total_bytes_received: int
    total_packets_sent: int
    total_packets_received: int
    total_errors_in: int
    total_errors_out: int
    total_drops_in: int
    total_drops_out: int
    inbound_bytes_per_second: float | None
    outbound_bytes_per_second: float | None
    interfaces: list[NetworkInterfaceMetrics]
