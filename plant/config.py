"""Plant configuration: teaching baseline + local service settings.

Values come from contracts/baseline.json (shared contract v0.1) and environment
variables (see .env.example). Nothing here is a real treatment operating limit.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_FILE = ROOT / "contracts" / "baseline.json"


@dataclass(frozen=True)
class SensorSettings:
    source_id: str
    seed: int
    noise_bound_mg_l: float


@dataclass(frozen=True)
class Baseline:
    tick_seconds: float
    flow_l_s: float
    requested_feed_mg_s: float
    accepted_feed_mg_s: float
    demand_mg_l: float
    initial_residual_mg_l: float
    response_delay_ticks: int
    response_fraction_per_tick: float
    pump_running: bool
    delivery_factor: float
    sensor_a: SensorSettings
    sensor_b: SensorSettings


def load_baseline(path: Path = BASELINE_FILE) -> Baseline:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Baseline(
        tick_seconds=float(data["tick_seconds"]),
        flow_l_s=float(data["flow_l_s"]),
        requested_feed_mg_s=float(data["requested_feed_mg_s"]),
        accepted_feed_mg_s=float(data["accepted_feed_mg_s"]),
        demand_mg_l=float(data["demand_mg_l"]),
        initial_residual_mg_l=float(data["initial_residual_mg_l"]),
        response_delay_ticks=int(data["response_delay_ticks"]),
        response_fraction_per_tick=float(data["response_fraction_per_tick"]),
        pump_running=bool(data["pump_running"]),
        delivery_factor=float(data["delivery_factor"]),
        sensor_a=SensorSettings(**data["sensor_a"]),
        sensor_b=SensorSettings(**data["sensor_b"]),
    )


@dataclass(frozen=True)
class ServiceSettings:
    bind_host: str
    observer_port: int
    controller_port: int
    desk_port: int
    collector_url: str
    evidence_dir: Path


def load_service_settings() -> ServiceSettings:
    host = os.environ.get("MVP_BIND_HOST", "127.0.0.1")
    collector_port = int(os.environ.get("MVP_COLLECTOR_PORT", "5001"))
    return ServiceSettings(
        bind_host=host,
        observer_port=int(os.environ.get("MVP_OBSERVER_PORT", "1502")),
        controller_port=int(os.environ.get("MVP_CONTROLLER_PORT", "1503")),
        desk_port=int(os.environ.get("MVP_DESK_PORT", "5000")),
        collector_url=f"http://{host}:{collector_port}/intake/events",
        evidence_dir=ROOT / "evidence",
    )
