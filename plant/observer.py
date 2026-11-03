"""Read-only Modbus observer (127.0.0.1:1502, device 1, holding registers 0-12).

Contract v0.1 register order (UInt16):
  0 sensor A x100   1 sensor B x100   2 flow x100   3 requested feed x100
  4 accepted feed x100   5 actual delivery x100   6 pump 0/1   7 ack counter
  8 A quality   9 B quality   10 A age (s)   11 B age (s)   12 tick counter

Network writes (FC 6, 16, 23 ...) are refused with ILLEGAL_FUNCTION. The plant
updates the snapshot internally; each read returns the latest snapshot.
This local prototype does not protect against a malicious process running
under the same Windows account.
"""

from __future__ import annotations

import asyncio
import logging

from pymodbus.constants import ExcCodes
from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

DEVICE_ID = 1
REGISTER_COUNT = 13
QUALITY_CODES = {"good": 0, "uncertain": 1, "bad": 2, "unavailable": 3}

log = logging.getLogger("plant.observer")


def scaled(value: float) -> int:
    """Scale by 100 once and clamp to UInt16."""
    return max(0, min(65535, round(value * 100)))


def build_snapshot(state, sample_a, sample_b, quality_a, quality_b, age_a, age_b, ack_counter) -> list[int]:
    return [
        scaled(sample_a.value_mg_l) if sample_a else 0,
        scaled(sample_b.value_mg_l) if sample_b else 0,
        scaled(state.flow_l_s),
        scaled(state.requested_feed_mg_s),
        scaled(state.accepted_feed_mg_s),
        scaled(state.actual_delivery_mg_s),
        1 if state.pump_running else 0,
        ack_counter % 65536,
        QUALITY_CODES[quality_a],
        QUALITY_CODES[quality_b],
        min(65535, age_a),
        min(65535, age_b),
        state.sim_step % 65536,
    ]


class ObserverServer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.clear()
        self.refused_writes = 0
        self.server: ModbusTcpServer | None = None  # created in serve(): pymodbus needs a running loop

    def clear(self) -> None:
        self.snapshot = [0] * 8 + [QUALITY_CODES['unavailable']] * 2 + [65535, 65535, 0]

    async def _on_request(self, func_code, start, address, count, current, set_values):
        if set_values is not None:  # any write request from the network
            self.refused_writes += 1
            log.warning("Refused Modbus write (function %s, address %s)", func_code, address)
            return ExcCodes.ILLEGAL_FUNCTION
        for i in range(count):
            current[address - start + i] = self.snapshot[address + i]
        return None

    def update(self, snapshot: list[int]) -> None:
        if len(snapshot) != REGISTER_COUNT:
            raise ValueError("snapshot must have 13 registers")
        self.snapshot = list(snapshot)

    async def serve(self) -> None:
        device = SimDevice(
            DEVICE_ID,
            simdata=SimData(0, count=REGISTER_COUNT, values=0, datatype=DataType.REGISTERS),
            action=self._on_request,
        )
        self.server = ModbusTcpServer(context=device, address=(self.host, self.port))
        log.info("Observer listening on %s:%d (device %d, read-only)", self.host, self.port, DEVICE_ID)
        await self.server.serve_forever()

    async def shutdown(self) -> None:
        if self.server is not None:
            await self.server.shutdown()
