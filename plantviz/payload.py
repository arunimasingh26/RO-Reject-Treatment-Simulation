"""Turn simulation results into a small JSON scene description for the browser.

Phase 1: static scene from the steady-state table (one value set per stage).
Phase 2 will add time-series frames and events to the same payload.
"""
from __future__ import annotations

import math

QUALITY = ("flow_lph", "turbidity_ntu", "toc_mgl", "chlorine_mgl", "tds_mgl", "bacteria_log")


def _num(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 4)


def build_payload(cfg, pipeline, steady) -> dict:
    """cfg: Config, pipeline: Pipeline from build_train(), steady: steady_state() DataFrame."""
    keys = ["reject"] + [s.key for s in pipeline.stages]
    rows = steady.reset_index(drop=True)
    if len(rows) != len(keys):
        raise ValueError("steady-state table does not match the pipeline stages")
    quality = {k: {c: _num(rows.iloc[i][c]) for c in QUALITY} for i, k in enumerate(keys)}
    flows = [quality[k]["flow_lph"] for k in keys]
    waste = {k: _num(max(0.0, flows[i - 1] - flows[i])) for i, k in enumerate(keys) if i > 0}
    return {
        "mode": "steady",
        "labels": pipeline.labels,
        "quality": quality,
        "waste_lph": waste,
        "scales": {
            "inlet": quality["reject"],
            "bacteria_floor": cfg("general.bacteria_floor_log"),
            "targets": cfg.section("targets"),
        },
        "plant": {
            "collection_l": cfg("plant.collection_tank_l"),
            "treated_l": cfg("plant.treated_tank_l"),
            "reuse_l": cfg("plant.reuse_tank_l"),
            "ro_feed_flow_lph": cfg("plant.ro_feed_flow_lph"),
            "ro_recovery": cfg("plant.ro_recovery"),
            "treatment_flow_lph": cfg("plant.treatment_flow_lph"),
        },
    }
