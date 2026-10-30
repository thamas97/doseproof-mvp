"""Private operator-side controller (DPM-12).

A separate Modbus endpoint (default 127.0.0.1:1503, device 1) used ONLY by the
operator desk. It is not part of the DoseProof observer configuration.

Command write: one FC16 write of 2 registers at address 0:
  register 0 = command sequence number (assigned by the desk)
  register 1 = requested feed x100 (mg/s)
The controller accepts a write only when it matches a command the desk has
registered (same sequence and value) and the value is within the teaching
limits. Anything else is refused with a Modbus exception and no change.

On acceptance the controller sets the accepted feed and emits an
acknowledgement. The acknowledgement says the controller accepted the
setting; it does NOT claim delivery or any sensor change. Actual delivery
and the water response come later from the plant model and sensors.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable

from pymodbus.constants import ExcCodes
from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

DEVICE_ID = 1
MAX_FEED_MG_S = 40.0  # teaching limit only, not a real operating limit
log = logging.getLogger("plant.controller")


@dataclass(frozen=True)
class PendingCommand:
    seq: int
    command_id: str
    change_id: str
    requested_feed_mg_s: float


class CommandRegistry:
    """Commands the desk has authorised and is about to write."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[int, PendingCommand] = {}
        self._next_seq = 1

    def register(self, command_id: str, change_id: str, feed_mg_s: float) -> PendingCommand:
        with self._lock:
            seq = self._next_seq
            self._next_seq = self._next_seq % 65535 + 1
            cmd = PendingCommand(seq, command_id, change_id, feed_mg_s)
            self._pending[seq] = cmd
            return cmd

    def take(self, seq: int, raw_feed: int) -> PendingCommand | None:
        """Remove and return the pending command only if seq and value match."""
        with self._lock:
            cmd = self._pending.get(seq)
            if cmd is None or round(cmd.requested_feed_mg_s * 100) != raw_feed:
                return None
            return self._pending.pop(seq)


class ControllerServer:
    def __init__(self, host: str, port: int, registry: CommandRegistry,
                 on_accept: Callable[[PendingCommand], None]) -> None:
        self.host = host
        self.port = port
        self.registry = registry
        self.on_accept = on_accept
        self.refused = 0
        self.server: ModbusTcpServer | None = None

    async def _on_request(self, func_code, start, address, count, current, set_values):
        if set_values is None:  # reads are allowed (desk can confirm)
            return None
        if func_code != 16 or address != 0 or len(set_values) != 2:
            return self._refuse(f"unsupported write fc={func_code} addr={address}")
        seq, raw_feed = int(set_values[0]), int(set_values[1])
        if raw_feed > round(MAX_FEED_MG_S * 100):
            return self._refuse(f"value {raw_feed / 100} mg/s above teaching limit")
        cmd = self.registry.take(seq, raw_feed)
        if cmd is None:
            return self._refuse(f"no authorised command for seq={seq} value={raw_feed / 100}")
        self.on_accept(cmd)
        return None  # let the write land in the controller's own registers

    def _refuse(self, reason: str):
        self.refused += 1
        log.warning("Controller refused write: %s", reason)
        return ExcCodes.ILLEGAL_DATA_VALUE

    async def serve(self) -> None:
        device = SimDevice(
            DEVICE_ID,
            simdata=SimData(0, count=2, values=0, datatype=DataType.REGISTERS),
            action=self._on_request,
        )
        self.server = ModbusTcpServer(context=device, address=(self.host, self.port))
        log.info("Private controller listening on %s:%d (operator desk only)", self.host, self.port)
        await self.server.serve_forever()

    async def shutdown(self) -> None:
        if self.server is not None:
            await self.server.shutdown()
