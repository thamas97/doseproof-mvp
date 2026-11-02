"""DoseProof plant entrypoint (Layer 1). Educational simulation only.

One process runs the operator side of the simulation:
  * teaching model + Sensor A/B adapters, one tick per second
  * read-only observer for FUXA/DoseProof        127.0.0.1:1502
  * private controller (operator desk only)        127.0.0.1:1503
  * named operator desk (request/approve/execute)  http://127.0.0.1:5000
Source copies go to evidence/<run_id>/plant-source-records.jsonl and the collector.

Start:  .\\.venv\\Scripts\\python.exe plant\\app.py   (or scripts\\start-mvp.ps1 -Service plant)
Stop:   Ctrl+C
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymodbus.client import ModbusTcpClient
from werkzeug.serving import make_server

from plant.config import load_baseline, load_service_settings
from plant.controller import CommandRegistry, ControllerServer, PendingCommand
from plant.desk import Desk
from plant.desk_web import create_desk_app
from plant.events import EventFactory, Publisher, plant_feedback, sensor_observation
from plant.model import PlantModel
from plant.observer import ObserverServer, build_snapshot
from plant.sensors import SensorAdapter

log = logging.getLogger("plant")


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:6]


class Plant:
    def __init__(self, run_id: str | None = None, settings=None) -> None:
        self.baseline = load_baseline()
        self.settings = settings or load_service_settings()
        self._lock = threading.RLock()  # plant tick, controller acceptance and reset
        self.paused = False
        self.observer = ObserverServer(self.settings.bind_host, self.settings.observer_port)
        self.registry = CommandRegistry()
        self.controller = ControllerServer(
            self.settings.bind_host, self.settings.controller_port, self.registry, self._controller_accept)
        self._start_run(run_id)
        self.desk = Desk(self._desk_emit, self._send_command, self._run_dir / "desk-audit.jsonl",
                         lab_mode=self.settings.lab_mode)

    def _start_run(self, run_id: str | None) -> None:
        """Fresh baseline: new run ID, model, seeds, queues and record file."""
        self.run_id = run_id or new_run_id()
        self.model = PlantModel(self.baseline)
        self.sensor_a = SensorAdapter(self.baseline.sensor_a)
        self.sensor_b = SensorAdapter(self.baseline.sensor_b)
        self.ack_counter = 0
        self.registry.clear()
        self._run_dir = self.settings.evidence_dir / self.run_id
        self.events = EventFactory(self.run_id)
        self.publisher = Publisher(self.settings.collector_url, self._run_dir / "plant-source-records.jsonl")
        self._refresh_observer()

    # --- lab controls (operator only, via the desk) ----------------------------------------
    def reset(self, paused: bool = True) -> str:
        """New run at step 0. Earlier evidence folders are kept. Starts paused by default
        so an approved command can be applied before step 1."""
        with self._lock:
            self.paused = paused
            self._start_run(None)
        self.desk.reset(self._run_dir / "desk-audit.jsonl")
        log.info("RESET: new run %s at step 0 (%s)", self.run_id, "paused" if paused else "running")
        return self.run_id

    def pause(self) -> None:
        self.paused = True
        log.info("PAUSED at step %d", self.model.sim_step)

    def resume(self) -> None:
        self.paused = False
        log.info("RESUMED at step %d", self.model.sim_step)

    # --- plant tick ------------------------------------------------------------------------
    def _refresh_observer(self) -> list[int]:
        state = self.model.state()
        a, b = self.sensor_a.last_sample, self.sensor_b.last_sample
        snapshot = build_snapshot(
            state, a, b, "good" if a else "unavailable", "good" if b else "unavailable",
            self.sensor_a.age_steps(state.sim_step), self.sensor_b.age_steps(state.sim_step),
            self.ack_counter,
        )
        self.observer.update(snapshot)
        return snapshot

    def tick(self) -> list[int]:
        with self._lock:
            state = self.model.step()
            a = self.sensor_a.sample(state.modeled_residual_mg_l, state.sim_step)
            b = self.sensor_b.sample(state.modeled_residual_mg_l, state.sim_step)
            snapshot = self._refresh_observer()
            for event in (plant_feedback(self.events, state), sensor_observation(self.events, a),
                          sensor_observation(self.events, b)):
                self.publisher.publish(event)
        log.info(
            "step %d  flow %.2f L/s  accepted %.2f mg/s  delivery %.2f mg/s  residual %.4f  A %.3f  B %.3f",
            state.sim_step, state.flow_l_s, state.accepted_feed_mg_s, state.actual_delivery_mg_s,
            state.modeled_residual_mg_l, a.value_mg_l, b.value_mg_l,
        )
        return snapshot

    # --- operator side ---------------------------------------------------------------------
    def _desk_emit(self, event_type: str, payload: dict, change_id: str) -> dict:
        event = self.events.make("operator-desk", event_type, self.model.sim_step, payload, change_id=change_id)
        self.publisher.publish(event)
        return event

    def _send_command(self, command_id: str, change_id: str, feed_mg_s: float) -> None:
        """Desk -> private controller over Modbus (FC16: [sequence, feed x100])."""
        cmd = self.registry.register(command_id, change_id, feed_mg_s)
        client = ModbusTcpClient(self.settings.bind_host, port=self.settings.controller_port, timeout=3)
        try:
            if not client.connect():
                raise ConnectionError("private controller not reachable")
            result = client.write_registers(0, [cmd.seq, round(feed_mg_s * 100)], device_id=1)
            if result.isError():
                raise RuntimeError(f"controller refused: {result}")
        finally:
            client.close()

    def _controller_accept(self, cmd: PendingCommand) -> None:
        """Runs in the plant loop when the controller accepts an authorised write."""
        with self._lock:
            self.model.set_requested_feed(cmd.requested_feed_mg_s)
            self.model.set_accepted_feed(cmd.requested_feed_mg_s)
            self.ack_counter += 1
            self._refresh_observer()  # setting and ack visible now; delivery effect follows the model
        ack = {
            "command_id": cmd.command_id,
            "accepted": True,
            "accepted_feed_mg_s": cmd.requested_feed_mg_s,
            "reason": "Setting accepted by controller. Delivery and water response are reported separately.",
        }
        event = self.events.make("controller", "acknowledgement", self.model.sim_step, ack, change_id=cmd.change_id)
        self.publisher.publish(event)
        self.desk.record_acknowledgement(cmd.command_id, ack)
        log.info("controller accepted %s: accepted feed now %.2f mg/s", cmd.command_id, cmd.requested_feed_mg_s)

    # --- run -------------------------------------------------------------------------------
    def start_desk(self):
        app = create_desk_app(self.desk, lambda: self.model.state(), controls=self)
        server = make_server(self.settings.bind_host, self.settings.desk_port, app, threaded=True)
        threading.Thread(target=server.serve_forever, name="operator-desk", daemon=True).start()
        log.info("Operator desk on http://%s:%d", self.settings.bind_host, self.settings.desk_port)
        return server

    async def run(self) -> None:
        async def loop() -> None:
            while True:
                try:
                    if not self.paused:
                        self.tick()
                except Exception:  # keep the plant alive; record the error
                    log.exception("tick failed")
                await asyncio.sleep(self.baseline.tick_seconds)

        log.info("Plant run %s starting (records: %s)", self.run_id, self.publisher.jsonl_path)
        if self.settings.lab_mode:
            log.warning("LAB MODE ENABLED: the labelled lab-unapproved path is available to the operator")
        self.start_desk()
        await asyncio.gather(self.observer.serve(), self.controller.serve(), loop())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    try:
        asyncio.run(Plant().run())
    except KeyboardInterrupt:
        log.info("Plant stopped")


if __name__ == "__main__":
    main()
