"""Sensor A and Sensor B adapters (Layer 1).

Each sensor is a separate software adapter with its own source ID and its own
seeded random generator. Both sample the MODELED WATER residual, never the
controller setting or the FUXA display. They share one model and one laptop,
so their independence is limited (documented limitation).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from plant.config import SensorSettings


@dataclass(frozen=True)
class SensorSample:
    source_id: str
    sim_step: int
    value_mg_l: float
    quality: str  # good / uncertain / bad


# Same freshness policy as the evidence API (monitor/api_app.py): stale at 3, unavailable at 10.
STALE_AFTER_STEPS = 3
UNAVAILABLE_AFTER_STEPS = 10


class SensorAdapter:
    def __init__(self, settings: SensorSettings) -> None:
        self.settings = settings
        self.reset()

    def reset(self) -> None:
        self._rng = random.Random(self.settings.seed)
        self.last_sample: SensorSample | None = None
        self.last_sample_step: int | None = None

    @property
    def source_id(self) -> str:
        return self.settings.source_id

    def sample(self, modeled_residual_mg_l: float, sim_step: int) -> SensorSample:
        bound = self.settings.noise_bound_mg_l
        value = max(0.0, modeled_residual_mg_l + self._rng.uniform(-bound, bound))
        sample = SensorSample(self.source_id, sim_step, value, "good")
        self.last_sample = sample
        self.last_sample_step = sim_step
        return sample

    def age_steps(self, current_step: int) -> int:
        """Steps since the last valid sample (65535 if never sampled)."""
        if self.last_sample_step is None:
            return 65535
        return min(65535, current_step - self.last_sample_step)

    def quality(self, current_step: int) -> str:
        """Observer quality of the retained sample: good, uncertain (stale), unavailable.
        A missing sample is never replaced by zero; the last real value is kept."""
        age = self.age_steps(current_step)
        if self.last_sample is None or age >= UNAVAILABLE_AFTER_STEPS:
            return "unavailable"
        if age >= STALE_AFTER_STEPS:
            return "uncertain"
        return "good"
