"""FastAPI application for the NOC Monitor Agent."""

from fastapi import FastAPI, HTTPException

from app.models import AgentInfo, HealthStatus, NetworkMetrics, SystemMetrics
from app.services.network_metrics import collect_network_metrics
from app.services.system_metrics import collect_system_metrics, get_hostname, utc_now

SERVICE_NAME = "NOC Monitor Agent"
VERSION = "0.1.0"

app = FastAPI(
    title=SERVICE_NAME,
    description="A lightweight API providing real telemetry from the local system.",
    version=VERSION,
)


@app.get("/", response_model=AgentInfo)
def get_agent_info() -> AgentInfo:
    """Return basic service information and its documentation location."""
    return AgentInfo(
        service_name=SERVICE_NAME,
        version=VERSION,
        status="running",
        documentation_path=app.docs_url or "/docs",
    )


@app.get("/health", response_model=HealthStatus)
def get_health() -> HealthStatus:
    """Return a lightweight indication that the API is responsive."""
    return HealthStatus(status="healthy", hostname=get_hostname(), timestamp=utc_now())


@app.get("/api/system", response_model=SystemMetrics)
def get_system_metrics() -> SystemMetrics:
    """Return a current snapshot of telemetry from this host."""
    try:
        return collect_system_metrics()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to collect system telemetry",
        ) from exc


@app.get("/api/network", response_model=NetworkMetrics)
def get_network_metrics() -> NetworkMetrics:
    """Return current host and interface network telemetry."""
    try:
        return collect_network_metrics()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to collect network telemetry",
        ) from exc
