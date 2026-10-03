"""Simulation engine: pipeline builder, steady-state pass, and the main time-based loop."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .analysis import all_ok, lsi
from .stages import (CarbonFilter, Cartridge, Equalisation, MultimediaFilter, Pipeline,
                     UltrafiltrationStage, UVStage)
from .tanks import Tank
from .water import reject_flow_lph, reject_profile

SNAP_PARAMS = ("flow_lph", "turbidity_ntu", "tds_mgl", "toc_mgl", "chlorine_mgl", "bacteria_log")


def build_train(cfg) -> Pipeline:
    """Stage order: coarse -> fine -> membrane -> disinfection."""
    rw = reject_profile(cfg)
    daily_l = reject_flow_lph(cfg) * cfg("plant.ro_hours_per_day")
    return Pipeline([
        Equalisation(cfg),
        MultimediaFilter(cfg),
        CarbonFilter(cfg, rw.toc_mgl, daily_l),
        Cartridge(cfg, "cartridge_5um", "5 \u00b5m cartridge"),
        Cartridge(cfg, "candle_05um", "0.5 \u00b5m candle"),
        UltrafiltrationStage(cfg),
        UVStage(cfg),
    ])


def steady_state(cfg, flow_lph: float | None = None) -> pd.DataFrame:
    """Single pass through a fresh train: water quality after every stage."""
    cfg.validate()
    pl = build_train(cfg)
    q = flow_lph or cfg("plant.treatment_flow_lph")
    w = reject_profile(cfg).with_(flow_lph=q)
    ctx = {"t": 1.0, "hrt_h": 0.5 * cfg("plant.collection_tank_l") / q}
    _, _, snaps = pl.run(w, 1.0, ctx)
    rows = []
    for key, ws in snaps.items():
        r = ws.as_dict()
        r["stage"] = pl.labels[key]
        r["LSI"] = lsi(ws)
        rows.append(r)
    return pd.DataFrame(rows).set_index("stage")


@dataclass
class SimResult:
    df: pd.DataFrame
    events: pd.DataFrame
    summary: dict
    warnings: list
    cfg: object = field(repr=False, default=None)


def _in_window(hour_of_day: float, start: float, length: float) -> bool:
    return ((hour_of_day - start) % 24.0) < length


def run_time_based(cfg, days: float | None = None, dt_h: float | None = None) -> SimResult:
    warnings = list(cfg.validate())
    days = days if days is not None else cfg("simulation.days")
    dt = dt_h if dt_h is not None else cfg("simulation.dt_h")
    n_steps = int(round(days * 24.0 / dt))

    reject = reject_profile(cfg)
    q_reject = reject_flow_lph(cfg)
    pl = build_train(cfg)

    rg, rmax = cfg("tanks.regrowth_log_per_day"), cfg("tanks.regrowth_max_log")
    coll = Tank("collection", cfg("plant.collection_tank_l"))
    treated = Tank("treated", cfg("plant.treated_tank_l"), rg, rmax)
    reuse = Tank("reuse", cfg("plant.reuse_tank_l"), rg, rmax)

    q_pump = cfg("plant.treatment_flow_lph")
    start_lvl, stop_lvl = cfg("plant.pump_start_level"), cfg("plant.pump_stop_level")
    ro_start, ro_hours = cfg("plant.ro_start_hour"), cfg("plant.ro_hours_per_day")
    d_start = cfg("plant.demand_start_hour")
    d_len = cfg("plant.demand_end_hour") - d_start
    demand_rate = cfg("plant.demand_l_per_day") / d_len  # L/h inside the demand window

    pump_on, ratio_est = False, 0.9
    events, flags, rows = [], {}, []

    def edge(name, cond, t, msg):
        if cond and not flags.get(name):
            events.append((t, "Plant", msg))
        flags[name] = cond

    for i in range(n_steps):
        t0, t1 = i * dt, (i + 1) * dt
        hod = t0 % 24.0

        # 1. RO produces reject water into the collection tank
        inflow = q_reject * dt if _in_window(hod, ro_start, ro_hours) else 0.0
        avail = coll.volume + inflow  # inflow and pumping happen simultaneously within a step

        # 2. Treatment pump with start/stop levels
        if not pump_on and avail > start_lvl * coll.capacity:
            pump_on = True
        if pump_on and avail <= stop_lvl * coll.capacity:
            pump_on = False
        draw = produced = lost_treated = waste_l = 0.0
        snaps, total_lrv = None, np.nan
        if pump_on:
            draw = min(q_pump * dt, avail, treated.free / max(ratio_est, 0.05))
            if draw > 1e-9:
                vol_before = avail
                w_in = reject.with_(flow_lph=draw / dt)
                ctx = {"t": t1, "hrt_h": vol_before / w_in.flow_lph}
                out, wastes, snaps = pl.run(w_in, dt, ctx)
                out_vol = out.flow_lph * dt
                ratio_est = out_vol / draw
                produced = treated.add(out_vol, out)
                lost_treated = out_vol - produced
                waste_l = sum(w.flow_lph for _, w in wastes) * dt
                total_lrv = sum(s.last.get(f"{s.key}.lrv", 0.0) for s in pl.stages)
        new_vol = avail - draw
        overflow = max(0.0, new_vol - coll.capacity)
        coll.volume, coll.water = new_vol - overflow, reject.with_(flow_lph=0.0)
        edge("coll_overflow", overflow > 1e-6, t1, "Collection tank overflow to drain")
        edge("treated_full", lost_treated > 1e-6, t1, "Treated tank full - output lost")

        # 3. Transfer treated -> reuse tank
        if reuse.volume < cfg("plant.reuse_refill_level") * reuse.capacity and treated.volume > 0:
            x = min(cfg("plant.transfer_rate_lph") * dt, treated.volume, reuse.free)
            taken, w_t = treated.remove(x)
            if taken > 0:
                reuse.add(taken, w_t)

        # 4. Non-potable demand
        demand = demand_rate * dt if _in_window(hod, d_start, d_len) else 0.0
        got, w_del = reuse.remove(demand) if demand > 0 else (0.0, None)
        ok_l = got if (got > 0 and w_del is not None and all_ok(w_del, cfg)) else 0.0
        edge("unmet", demand - got > 1e-6, t1, "Demand not fully met (reuse tank empty)")

        # 5. Bacterial regrowth in storage
        treated.regrow(dt)
        reuse.regrow(dt)

        row = dict(
            t_h=t1, day=t1 / 24.0, hour=hod, ro_on=inflow > 0, inflow_l=inflow, overflow_l=overflow,
            collection_l=coll.volume, pump_on=draw > 1e-9, processed_l=draw, waste_l=waste_l,
            produced_l=produced, treated_lost_l=lost_treated, treated_l=treated.volume,
            reuse_l=reuse.volume, demand_l=demand, delivered_l=got, unmet_l=demand - got,
            delivered_ok_l=ok_l, total_lrv=total_lrv,
            **{"treated_tank.bacteria_log": treated.water.bacteria_log if treated.water else np.nan,
               "reuse_tank.bacteria_log": reuse.water.bacteria_log if reuse.water else np.nan,
               "reuse_tank.turbidity_ntu": reuse.water.turbidity_ntu if reuse.water else np.nan,
               "reuse_tank.tds_mgl": reuse.water.tds_mgl if reuse.water else np.nan},
        )
        if snaps:
            for key, ws in snaps.items():
                for prm in SNAP_PARAMS:
                    row[f"{key}.{prm}"] = getattr(ws, prm)
        for s in pl.stages:
            row.update(s.state_metrics())
            if snaps:
                row.update(s.last)
        rows.append(row)

    df = pd.DataFrame(rows)
    ev = events + pl.events()
    events_df = pd.DataFrame(ev, columns=["t_h", "stage", "event"]).sort_values("t_h").reset_index(drop=True)
    warnings += sorted(pl.warnings())

    run = df[df["pump_on"]]
    sm = lambda col: float(run[col].mean()) if len(run) and col in run else float("nan")  # noqa: E731
    delivered = float(df["delivered_l"].sum())
    summary = {
        "days": days,
        "reject_generated_l": float(df["inflow_l"].sum()),
        "collection_overflow_l": float(df["overflow_l"].sum()),
        "processed_l": float(df["processed_l"].sum()),
        "backwash_waste_l": float(df["waste_l"].sum()),
        "produced_l": float(df["produced_l"].sum()),
        "treated_lost_l": float(df["treated_lost_l"].sum()),
        "delivered_l": delivered,
        "unmet_demand_l": float(df["unmet_l"].sum()),
        "delivered_compliant_pct": 100.0 * float(df["delivered_ok_l"].sum()) / delivered if delivered > 0 else float("nan"),
        "train_water_recovery_pct": 100.0 * float(df["produced_l"].sum() + df["treated_lost_l"].sum()) / float(df["processed_l"].sum())
        if df["processed_l"].sum() > 0 else float("nan"),
        "overall_reuse_pct": 100.0 * delivered / float(df["inflow_l"].sum()) if df["inflow_l"].sum() > 0 else float("nan"),
        "mean_outlet_turbidity_ntu": sm("uv.turbidity_ntu"),
        "mean_outlet_tds_mgl": sm("uv.tds_mgl"),
        "reject_tds_mgl": reject.tds_mgl,
        "mean_total_lrv": sm("total_lrv"),
        "mean_reuse_bacteria_log": float(df["reuse_tank.bacteria_log"].mean()),
        "n_events": len(events_df),
    }
    return SimResult(df=df, events=events_df, summary=summary, warnings=warnings, cfg=cfg)
