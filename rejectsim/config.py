"""Config loading, access and validation. All model numbers come from config/defaults.yaml."""
from __future__ import annotations

import copy
import pathlib

import yaml

DEFAULT_PATH = pathlib.Path(__file__).resolve().parent.parent / "config" / "defaults.yaml"


class ConfigError(ValueError):
    """Raised when parameter values are physically impossible or inconsistent."""


def _is_leaf(node) -> bool:
    return isinstance(node, dict) and "value" in node


class Config:
    def __init__(self, data: dict):
        self._d = data

    @classmethod
    def load(cls, path=None) -> "Config":
        with open(path or DEFAULT_PATH, encoding="utf-8") as f:
            return cls(yaml.safe_load(f))

    def copy(self) -> "Config":
        return Config(copy.deepcopy(self._d))

    def _node(self, path: str):
        node = self._d
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                raise KeyError(f"Unknown config path: {path}")
            node = node[part]
        return node

    def leaf(self, path: str) -> dict:
        node = self._node(path)
        if not _is_leaf(node):
            raise KeyError(f"{path} is a section, not a parameter")
        return node

    def get(self, path: str):
        return self.leaf(path)["value"]

    __call__ = get

    def set(self, path: str, value) -> None:
        self.leaf(path)["value"] = value

    def section(self, path: str) -> dict:
        node = self._node(path)
        return {k: v["value"] for k, v in node.items() if _is_leaf(v)}

    def leaves(self) -> dict:
        out: dict = {}

        def walk(node, prefix):
            for k, v in node.items():
                p = f"{prefix}.{k}" if prefix else k
                if _is_leaf(v):
                    out[p] = v
                elif isinstance(v, dict):
                    walk(v, p)

        walk(self._d, "")
        return out

    def validate(self) -> list[str]:
        """Raise ConfigError for impossible values; return a list of range warnings."""
        errors: list[str] = []
        warns: list[str] = []
        for path, leaf in self.leaves().items():
            v = leaf["value"]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            if leaf.get("unit") == "fraction" and not 0.0 <= v <= 1.0:
                errors.append(f"{path}={v} must be a fraction between 0 and 1")
            lo, hi = leaf.get("min"), leaf.get("max")
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                warns.append(f"{path}={v} is outside the sensible range [{lo}, {hi}]")

        g = self.get
        if g("plant.ro_recovery") >= 0.95:
            errors.append("plant.ro_recovery must be below 0.95 (reject flow -> 0, concentration -> infinity)")
        if g("plant.pump_stop_level") >= g("plant.pump_start_level"):
            errors.append("plant.pump_stop_level must be below plant.pump_start_level")
        if g("plant.demand_end_hour") <= g("plant.demand_start_hour"):
            errors.append("plant.demand_end_hour must be after plant.demand_start_hour")
        if g("plant.ro_hours_per_day") > 24:
            errors.append("plant.ro_hours_per_day cannot exceed 24")
        if g("stages.uf.recovery") <= 0:
            errors.append("stages.uf.recovery must be above 0")
        for key in ("plant.treatment_flow_lph", "plant.ro_feed_flow_lph", "stages.uv.design_flow_lph"):
            if g(key) <= 0:
                errors.append(f"{key} must be positive")
        table = g("stages.uv.dose_response")
        doses = [row[0] for row in table]
        logs = [row[1] for row in table]
        if doses != sorted(doses) or logs != sorted(logs):
            errors.append("stages.uv.dose_response must be increasing in both dose and log reduction")
        if errors:
            raise ConfigError("; ".join(errors))
        return warns
