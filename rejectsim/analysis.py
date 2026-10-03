"""Pass/fail checks, scaling index, mass balance and sensitivity analysis."""
from __future__ import annotations

import math

import pandas as pd

from .water import DISSOLVED, WaterState


def check_targets(w: WaterState, cfg) -> pd.DataFrame:
    """Compare water against the (placeholder) non-potable reuse targets in config."""
    t = cfg.section("targets")
    rows = [
        ("Turbidity (NTU)", w.turbidity_ntu, f"<= {t['turbidity_max_ntu']}", w.turbidity_ntu <= t["turbidity_max_ntu"]),
        ("pH", w.ph, f"{t['ph_min']} - {t['ph_max']}", t["ph_min"] <= w.ph <= t["ph_max"]),
        ("TDS (mg/L)", w.tds_mgl, f"<= {t['tds_max_mgl']}", w.tds_mgl <= t["tds_max_mgl"]),
        ("Bacteria (log10 CFU/mL)", w.bacteria_log, f"<= {t['bacteria_max_log']}", w.bacteria_log <= t["bacteria_max_log"]),
    ]
    return pd.DataFrame(rows, columns=["parameter", "value", "limit", "pass"])


def all_ok(w: WaterState, cfg) -> bool:
    return bool(check_targets(w, cfg)["pass"].all())


def lsi(w: WaterState) -> float:
    """Langelier Saturation Index. Positive = scale-forming, negative = corrosive."""
    a = (math.log10(max(w.tds_mgl, 1.0)) - 1.0) / 10.0
    b = -13.12 * math.log10(w.temp_c + 273.0) + 34.55
    c = math.log10(max(w.ca_hardness_mgl, 1e-3)) - 0.4
    d = math.log10(max(w.alkalinity_mgl, 1e-3))
    return w.ph - ((9.3 + a + b) - (c + d))


def mass_balance(w_in: WaterState, w_out: WaterState, wastes: list) -> dict:
    """Relative errors of the water and dissolved-salt balances across a pipeline pass."""
    q_in = w_in.flow_lph
    q_w = sum(wst.flow_lph for _, wst in wastes)
    flow_err = abs(q_in - w_out.flow_lph - q_w) / q_in
    errs = {}
    for k in DISSOLVED:
        m_in = q_in * getattr(w_in, k)
        m_out = w_out.flow_lph * getattr(w_out, k) + sum(wst.flow_lph * wst.conc.get(k, 0.0) for _, wst in wastes)
        errs[k] = abs(m_in - m_out) / m_in
    return {"flow": flow_err, **errs}


SENSITIVITY_PARAMS = [
    "plant.treatment_flow_lph", "plant.ro_recovery", "plant.demand_l_per_day",
    "source.feed_turbidity_ntu", "source.reject_toc_mgl", "source.reject_bacteria_log",
    "stages.uv.fouling_factor", "stages.uv.design_dose_mj_cm2", "stages.uf.bacteria_lrv",
    "stages.carbon.fresh_toc_removal", "stages.candle_05um.turbidity_removal", "tanks.regrowth_log_per_day",
]

SENSITIVITY_METRICS = {
    "mean_total_lrv": "Mean total bacteria log removal capacity",
    "mean_outlet_turbidity_ntu": "Mean outlet turbidity (NTU)",
    "mean_reuse_bacteria_log": "Mean reuse-tank bacteria (log10 CFU/mL)",
    "delivered_l": "Water delivered to demand (L)",
    "collection_overflow_l": "Collection tank overflow (L)",
}


def sensitivity(cfg, paths=None, rel_delta=0.25, days=14, metric="mean_total_lrv") -> pd.DataFrame:
    """One-at-a-time +/- rel_delta variation; values are clipped to each parameter's sensible range."""
    from .simulation import run_time_based  # lazy import avoids a circular import

    paths = paths or SENSITIVITY_PARAMS
    base = run_time_based(cfg, days=days).summary[metric]
    rows = []
    for path in paths:
        leaf = cfg.leaf(path)
        v0 = leaf["value"]
        vals = []
        for sign in (-1, +1):
            v = v0 * (1 + sign * rel_delta)
            lo, hi = leaf.get("min"), leaf.get("max")
            if lo is not None:
                v = max(v, lo)
            if hi is not None:
                v = min(v, hi)
            vals.append(v)
        res = []
        for v in vals:
            c = cfg.copy()
            c.set(path, v)
            try:
                res.append(run_time_based(c, days=days).summary[metric])
            except Exception:
                res.append(float("nan"))
        rows.append({"parameter": path, "low_value": vals[0], "high_value": vals[1],
                     "metric_low": res[0], "metric_base": base, "metric_high": res[1],
                     "swing": abs(res[1] - res[0])})
    return pd.DataFrame(rows).sort_values("swing", ascending=False).reset_index(drop=True)
