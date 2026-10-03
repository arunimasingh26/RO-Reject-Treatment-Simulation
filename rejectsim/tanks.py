"""Fully mixed storage tank with optional bacterial regrowth (UV leaves no residual)."""
from __future__ import annotations

from .water import WaterState, mix


class Tank:
    def __init__(self, name: str, capacity_l: float, regrowth_log_per_day: float = 0.0, regrowth_max_log: float = 3.0):
        self.name, self.capacity = name, capacity_l
        self.regrowth, self.regrowth_max = regrowth_log_per_day, regrowth_max_log
        self.volume = 0.0
        self.water: WaterState | None = None

    @property
    def free(self) -> float:
        return max(0.0, self.capacity - self.volume)

    def add(self, v: float, w: WaterState) -> float:
        """Add up to v litres; returns the volume actually accepted (the rest is lost/overflow)."""
        v_acc = max(0.0, min(v, self.free))
        if v_acc > 0:
            self.water = mix(self.water, self.volume, w, v_acc)
            self.volume += v_acc
        return v_acc

    def remove(self, v: float):
        """Remove up to v litres; returns (volume taken, water quality)."""
        taken = max(0.0, min(v, self.volume))
        w = self.water
        self.volume -= taken
        if self.volume < 1e-9:
            self.volume, self.water = 0.0, None
        return taken, w

    def regrow(self, dt_h: float) -> None:
        if self.water is not None and self.water.bacteria_log < self.regrowth_max:
            bl = min(self.regrowth_max, self.water.bacteria_log + self.regrowth * dt_h / 24.0)
            self.water = self.water.with_(bacteria_log=bl)
