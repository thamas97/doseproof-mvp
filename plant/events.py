"""Source event records (contract v0.1 envelope) and a simple publisher.

Each record keeps the producer's identity and times. The publisher always
writes a local JSONL copy, then tries to POST a copy to the collector.
A missing collector never stops the plant (DoseProof is passive).
Emmanuel's Layer 2 owns retry/outbox behaviour; failures here are counted
and logged, not hidden.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "0.1"
log = logging.getLogger("plant.events")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EventFactory:
    """Creates envelopes with per-source sequence numbers for one run."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._seq: dict[str, int] = {}
        self._lock = threading.Lock()  # desk (web thread) and plant tick both create events

    def make(self, source_id, event_type, sim_step, payload, source_time=None, change_id=None) -> dict:
        with self._lock:
            seq = self._seq.get(source_id, 0)
            self._seq[source_id] = seq + 1
        source_time = source_time or utc_now()
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "event_id": str(uuid.uuid4()),
            "source_id": source_id,
            "source_seq": seq,
            "event_type": event_type,
            "source_timestamp_utc": source_time,
            "emitted_at_utc": utc_now(),
            "sim_step": sim_step,
            "change_id": change_id,
            "payload": payload,
        }


def plant_feedback(factory: EventFactory, state, equipment_id="dosing-pump-1") -> dict:
    return factory.make(
        "plant-model",
        "plant_feedback",
        state.sim_step,
        {
            "equipment_id": equipment_id,
            "flow_l_s": state.flow_l_s,
            "pump_running": state.pump_running,
            "actual_delivery_mg_s": state.actual_delivery_mg_s,
            "modeled_residual_mg_l": state.modeled_residual_mg_l,
        },
    )


def sensor_observation(factory: EventFactory, sample, equipment_id="contact-tank") -> dict:
    return factory.make(
        sample.source_id,
        "sensor_observation",
        sample.sim_step,
        {"equipment_id": equipment_id, "value": sample.value_mg_l, "unit": "mg/L", "quality": sample.quality},
    )


class Publisher:
    """Writes every record locally first, then sends copies from a background
    thread so a slow or missing collector never delays the plant tick."""

    def __init__(self, collector_url: str, jsonl_path: Path, timeout_s: float = 2.0) -> None:
        self.collector_url = collector_url
        self.jsonl_path = jsonl_path
        self.timeout_s = timeout_s
        self.sent = 0
        self.failed = 0
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self._queue: queue.Queue[str] = queue.Queue(maxsize=10000)
        self._file_lock = threading.Lock()
        threading.Thread(target=self._send_loop, name="collector-sender", daemon=True).start()

    def publish(self, event: dict) -> None:
        line = json.dumps(event, separators=(",", ":"))
        with self._file_lock, self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        try:
            self._queue.put_nowait(line)
        except queue.Full:
            self._record_failure("send queue full")

    def _send_loop(self) -> None:
        while True:
            line = self._queue.get()
            request = urllib.request.Request(
                self.collector_url, data=line.encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_s):
                    self.sent += 1
            except (urllib.error.URLError, OSError) as exc:
                self._record_failure(exc)

    def _record_failure(self, reason) -> None:
        self.failed += 1
        if self.failed in (1, 10, 100) or self.failed % 1000 == 0:
            log.warning("Collector copy not sent (%d so far; local JSONL kept): %s", self.failed, reason)
