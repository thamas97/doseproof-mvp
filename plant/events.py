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
import os
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
    """Durable JSONL outbox with an atomic byte cursor and bounded retry delay.

    A collector receipt is evidence of retention, not an assurance PASS. Invalid
    or conflicting events are acknowledged only after the collector returns its
    retained receipt; their rejection is recorded in the delivery log.
    """

    def __init__(self, collector_url: str, jsonl_path: Path, timeout_s: float = 2.0) -> None:
        self.collector_url = collector_url
        self.jsonl_path = jsonl_path
        self.timeout_s = timeout_s
        self.sent = 0
        self.failed = 0
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self.cursor_path = jsonl_path.with_suffix('.cursor.json')
        self.delivery_path = jsonl_path.with_suffix('.delivery.jsonl')
        self._file_lock = threading.Lock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self._offset = 0
        if self.cursor_path.exists():
            self._offset = json.loads(self.cursor_path.read_text(encoding='utf-8'))['offset']
            if type(self._offset) is not int or self._offset < 0 or not jsonl_path.exists() or self._offset > jsonl_path.stat().st_size:
                raise ValueError('Invalid outbox cursor; original spool must be restored, not silently discarded')
            if self._offset:
                with jsonl_path.open('rb') as f:
                    f.seek(self._offset - 1)
                    if f.read(1) != b'\n':
                        raise ValueError('Outbox cursor is not at a complete record boundary')
        self._thread = threading.Thread(target=self._send_loop, name="collector-sender", daemon=True)
        self._thread.start()

    def publish(self, event: dict) -> None:
        line = json.dumps(event, separators=(",", ":"), allow_nan=False).encode('utf-8')
        with self._file_lock, self.jsonl_path.open('ab') as f:
            f.write(line + b'\n'); f.flush(); os.fsync(f.fileno())
        self._wake.set()

    def _send_loop(self) -> None:
        delay = 0.25
        while not self._stop.is_set():
            with self._file_lock:
                if self.jsonl_path.exists():
                    with self.jsonl_path.open('rb') as f:
                        f.seek(self._offset); line = f.readline(); next_offset = f.tell()
                else:
                    line = b''
            if not line or not line.endswith(b'\n'):
                self._wake.wait(0.25); self._wake.clear(); continue
            request = urllib.request.Request(
                self.collector_url, data=line[:-1],
                headers={"Content-Type": "application/json"}, method="POST",
            )
            try:
                try:
                    with self._opener.open(request, timeout=self.timeout_s) as response:
                        status, reply = response.status, json.loads(response.read(65536))
                except urllib.error.HTTPError as exc:
                    try:
                        if exc.code not in (409, 422):
                            raise
                        status, reply = exc.code, json.loads(exc.read(65536))
                    finally:
                        exc.close()
                if not isinstance(reply.get('receipt_id'), str) or reply.get('processing') not in ('created', 'duplicate', 'rejected', 'conflict'):
                    raise ValueError('Collector did not confirm a durable receipt')
                if status not in (200, 201, 409, 422):
                    raise ValueError('Unexpected collector response')
                with self._file_lock:
                    with self.delivery_path.open('a', encoding='utf-8') as f:
                        f.write(json.dumps({'end_offset':next_offset, 'http_status':status, **reply})+'\n')
                        f.flush(); os.fsync(f.fileno())
                    temp = self.cursor_path.with_suffix('.tmp')
                    with temp.open('w', encoding='utf-8') as f:
                        json.dump({'offset':next_offset}, f); f.flush(); os.fsync(f.fileno())
                    os.replace(temp, self.cursor_path)
                    self._offset = next_offset
                self.sent += 1
                delay = 0.25
            except (urllib.error.URLError, OSError, ValueError, TypeError) as exc:
                self._record_failure(exc)
                self._stop.wait(delay)
                delay = min(delay * 2, 5)

    def close(self):
        self._stop.set(); self._wake.set()
        self._thread.join(timeout=self.timeout_s + 2)

    def _record_failure(self, reason) -> None:
        self.failed += 1
        if self.failed in (1, 10, 100) or self.failed % 1000 == 0:
            log.warning("Collector copy not sent (%d so far; local JSONL kept): %s", self.failed, reason)
