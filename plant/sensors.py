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


STALE_AFTER_STEPS = 3        # runbook MVP threshold (team review required)
UNAVAILABLE_AFTER_STEPS = 10  # unavailable by the end of a ten-step missing window


class SensorAdapter:
    def __init__(self, settings: SensorSettings) -> None:
        self.settings = settings
        self.reset()

    def reset(self) -> None:
        self._rng = random.Random(self.settings.seed)
        self.last_sample: SensorSample | None = None
        self.last_sample_step: int | None = None
        self.suppressed = False  # DPM-18 lab fault: no new samples while True

    @property
    def source_id(self) -> str:
        return self.settings.source_id

    def sample(self, modeled_residual_mg_l: float, sim_step: int) -> SensorSample | None:
        """Return a new sample, or None while suppressed. A missing sample is never
        replaced by a zero or synthetic value; the last real sample is retained."""
        if self.suppressed:
            return None
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
        """good -> uncertain (stale, age >= 3) -> unavailable (age >= 10 or never sampled)."""
        age = self.age_steps(current_step)
        if self.last_sample is None or age >= UNAVAILABLE_AFTER_STEPS:
            return "unavailable"
        if age >= STALE_AFTER_STEPS:
            return "uncertain"
        return "good"
