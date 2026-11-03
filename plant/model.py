"""Teaching water model (Layer 1). Educational simulation only.

One tick = one simulation step. Meanings are kept separate:
  requested feed  - what was asked for
  accepted feed   - what the controller accepted
  actual delivery - what the pump really delivered (0 if stopped or no flow)
  residual        - modeled water state the sensors sample

Contract v0.1: target = max(0, delivery / flow - demand) for positive flow.
The water responds after a fixed delay (response_delay_ticks), then moves a
fixed fraction of the remaining difference toward the target each tick.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from plant.config import Baseline


@dataclass(frozen=True)
class PlantState:
    sim_step: int
    flow_l_s: float
    requested_feed_mg_s: float
    accepted_feed_mg_s: float
    pump_running: bool
    actual_delivery_mg_s: float
    modeled_residual_mg_l: float


class PlantModel:
    def __init__(self, baseline: Baseline) -> None:
        self.baseline = baseline
        self.reset()

    def reset(self) -> None:
        b = self.baseline
        self.sim_step = 0
        self.flow_l_s = b.flow_l_s
        self.requested_feed_mg_s = b.requested_feed_mg_s
        self.accepted_feed_mg_s = b.accepted_feed_mg_s
        self.pump_running = b.pump_running
        self.delivery_factor = b.delivery_factor
        self.residual_mg_l = b.initial_residual_mg_l
        # Deliveries waiting to reach the water: starts filled with the baseline delivery.
        self._delayed = deque([self.actual_delivery_mg_s()] * b.response_delay_ticks)

    # --- equipment behaviour ---------------------------------------------------
    def actual_delivery_mg_s(self) -> float:
        if not self.pump_running or self.flow_l_s <= 0:
            return 0.0
        return self.accepted_feed_mg_s * self.delivery_factor

    def set_requested_feed(self, value_mg_s: float) -> None:
        self.requested_feed_mg_s = value_mg_s

    def set_accepted_feed(self, value_mg_s: float) -> None:
        self.accepted_feed_mg_s = value_mg_s

    def set_pump_running(self, running: bool) -> None:
        self.pump_running = running

    # --- one simulation step -----------------------------------------------------
    def step(self) -> PlantState:
        self.sim_step += 1
        self._delayed.append(self.actual_delivery_mg_s())
        effective_delivery = self._delayed.popleft()
        if self.flow_l_s > 0:  # no flow: residual is left unchanged (contract: do not invent)
            target = max(0.0, effective_delivery / self.flow_l_s - self.baseline.demand_mg_l)
            self.residual_mg_l += self.baseline.response_fraction_per_tick * (target - self.residual_mg_l)
        return self.state()

    def state(self) -> PlantState:
        return PlantState(
            sim_step=self.sim_step,
            flow_l_s=self.flow_l_s,
            requested_feed_mg_s=self.requested_feed_mg_s,
            accepted_feed_mg_s=self.accepted_feed_mg_s,
            pump_running=self.pump_running,
            actual_delivery_mg_s=self.actual_delivery_mg_s(),
            modeled_residual_mg_l=self.residual_mg_l,
        )
