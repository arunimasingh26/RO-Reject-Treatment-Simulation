"""Turn simulation results into a small JSON scene description for the browser.

Phase 1: static scene from the steady-state table (one value set per stage).
Phase 2 will add time-series frames and events to the same payload.
"""
from __future__ import annotations

import math

import numpy as np

QUALITY = ("flow_lph", "turbidity_ntu", "toc_mgl", "chlorine_mgl", "tds_mgl", "bacteria_log")


def _num(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 4)


def build_payload(cfg, pipeline, steady, res=None, max_frames: int = 2000) -> dict:
    """cfg: Config, pipeline: from build_train(), steady: steady_state() DataFrame,
    res: optional SimResult from run_time_based() to enable playback."""
    keys = ["reject"] + [s.key for s in pipeline.stages]
    rows = steady.reset_index(drop=True)
    if len(rows) != len(keys):
        raise ValueError("steady-state table does not match the pipeline stages")
    quality = {k: {c: _num(rows.iloc[i][c]) for c in QUALITY} for i, k in enumerate(keys)}
    flows = [quality[k]["flow_lph"] for k in keys]
    waste = {k: _num(max(0.0, flows[i - 1] - flows[i])) for i, k in enumerate(keys) if i > 0}
    out = {
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
    if res is not None:
        out.update(_timeseries(res, keys, quality, max_frames, cfg))
    return out


def _arr(series, nd=3):
    return [round(float(v), nd) for v in series]


# stage key -> (df column, label, unit, config path of its limit or None)
HEALTH = {
    "equalisation": ("equalisation.sludge_g", "Sludge held", "g", None),
    "mmf": ("mmf.dp_bar", "Pressure drop", "bar", "stages.mmf.dp_limit_bar"),
    "carbon": ("carbon.saturation", "Carbon used", "fraction", "stages.carbon.replace_at_saturation"),
    "cartridge_5um": ("cartridge_5um.dp_bar", "Pressure drop", "bar", "stages.cartridge_5um.dp_limit_bar"),
    "candle_05um": ("candle_05um.dp_bar", "Pressure drop", "bar", "stages.candle_05um.dp_limit_bar"),
    "uf": ("uf.tmp_bar", "Transmembrane pressure", "bar", "stages.uf.tmp_limit_bar"),
    "uv": ("uv.lamp_h", "Lamp hours", "h", "stages.uv.lamp_life_h"),
}


def _health(df, cfg):
    out = {}
    for k, (col, label, unit, lim) in HEALTH.items():
        if col not in df:
            continue
        v = df[col].ffill().fillna(0)
        peak = float(v.max())
        limit = float(cfg(lim)) if lim else (peak if peak > 0 else 1.0)
        out[k] = {"label": label, "unit": unit, "limit": round(limit, 4), "relative": lim is None, "values": _arr(v, 4)}
    return out


def _timeseries(res, keys, steady_q, max_frames, cfg):
    df = res.df
    stride = max(1, math.ceil(len(df) / max_frames))
    df = df.iloc[::stride].reset_index(drop=True)
    t = df["t_h"].to_numpy(dtype=float)
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 1.0
    cols = ("inflow_l", "collection_l", "treated_l", "reuse_l", "delivered_l", "unmet_l")
    frames = {"t_h": _arr(t), "ro_on": [int(bool(v)) for v in df["ro_on"]],
              "pump_on": [int(bool(v)) for v in df["pump_on"]]}
    for c in cols:
        frames[c] = _arr(df[c].fillna(0)) if c in df else [0.0] * len(df)
    series = {}
    for k in keys:
        d = {}
        for c in ("flow_lph", "turbidity_ntu", "toc_mgl", "bacteria_log"):
            col = f"{k}.{c}"
            v = df[col] if col in df else None
            if c == "flow_lph":
                d[c] = _arr(v.fillna(0) if v is not None else np.zeros(len(df)), 1)
            else:  # hold the last known quality while the pump is idle
                v = v.ffill() if v is not None else None
                d[c] = _arr(v.fillna(steady_q[k][c]) if v is not None else np.full(len(df), steady_q[k][c]), 4)
        series[k] = d
    ev = res.events
    events = [[round(float(r.t_h), 2), str(r.stage), str(r.event)] for r in ev.itertuples()]
    return {"mode": "timeseries", "dt_h": dt, "frames": frames, "series": series, "events": events, "health": _health(df, cfg)}
