"""DoseProof plant entrypoint (Layer 1, DPM-9 baseline).

Runs the teaching model once per tick, samples Sensor A and B, updates the
read-only Modbus observer for FUXA and publishes source copies.

Start:  .\\.venv\\Scripts\\python.exe plant\\app.py   (or scripts\\start-mvp.ps1 -Service plant)
Stop:   Ctrl+C
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plant.config import load_baseline, load_service_settings
from plant.events import EventFactory, Publisher, plant_feedback, sensor_observation
from plant.model import PlantModel
from plant.observer import ObserverServer, build_snapshot
from plant.sensors import SensorAdapter

log = logging.getLogger("plant")


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:6]


class Plant:
    def __init__(self, run_id: str | None = None) -> None:
        self.baseline = load_baseline()
        self.settings = load_service_settings()
        self.run_id = run_id or new_run_id()
        self.model = PlantModel(self.baseline)
        self.sensor_a = SensorAdapter(self.baseline.sensor_a)
        self.sensor_b = SensorAdapter(self.baseline.sensor_b)
        self.ack_counter = 0
        self.events = EventFactory(self.run_id)
        self.publisher = Publisher(
            self.settings.collector_url,
            self.settings.evidence_dir / self.run_id / "plant-source-records.jsonl",
        )
        self.observer = ObserverServer(self.settings.bind_host, self.settings.observer_port)

    def tick(self) -> list[int]:
        state = self.model.step()
        a = self.sensor_a.sample(state.modeled_residual_mg_l, state.sim_step)
        b = self.sensor_b.sample(state.modeled_residual_mg_l, state.sim_step)
        snapshot = build_snapshot(
            state, a, b, a.quality, b.quality,
            self.sensor_a.age_steps(state.sim_step), self.sensor_b.age_steps(state.sim_step),
            self.ack_counter,
        )
        self.observer.update(snapshot)
        for event in (plant_feedback(self.events, state), sensor_observation(self.events, a),
                      sensor_observation(self.events, b)):
            self.publisher.publish(event)
        log.info(
            "step %d  flow %.2f L/s  accepted %.2f mg/s  delivery %.2f mg/s  residual %.4f  A %.3f  B %.3f",
            state.sim_step, state.flow_l_s, state.accepted_feed_mg_s, state.actual_delivery_mg_s,
            state.modeled_residual_mg_l, a.value_mg_l, b.value_mg_l,
        )
        return snapshot

    async def run(self) -> None:
        async def loop() -> None:
            while True:
                try:
                    await asyncio.to_thread(self.tick)
                except Exception:  # keep the plant alive; record the error
                    log.exception("tick failed")
                await asyncio.sleep(self.baseline.tick_seconds)

        log.info("Plant run %s starting (records: %s)", self.run_id, self.publisher.jsonl_path)
        await asyncio.gather(self.observer.serve(), loop())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S")
    try:
        asyncio.run(Plant().run())
    except KeyboardInterrupt:
        log.info("Plant stopped")


if __name__ == "__main__":
    main()
