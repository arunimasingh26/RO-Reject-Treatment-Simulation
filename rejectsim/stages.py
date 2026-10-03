"""Treatment stages. Every stage has the same interface:

    process(water_in, dt_h, ctx) -> (water_out, Waste)

ctx is a dict with "t" (hours at end of step) and "hrt_h" (collection tank retention time).
Stages keep internal state (clogging, carbon loading, lamp hours) that evolves over time.
No stage removes dissolved salts except UF's (default zero) rejection - by design.
"""
from __future__ import annotations

import numpy as np

from .water import DISSOLVED, Waste, WaterState


def turb_out(t_in: float, removal: float, floor: float) -> float:
    """Output turbidity with a physical floor (a filter cannot reach 0 NTU)."""
    if t_in <= floor:
        return t_in
    return max(floor, t_in * (1.0 - removal))


def reduce_log(bl: float, lrv: float, floor: float) -> float:
    if bl <= floor:
        return bl
    return max(floor, bl - lrv)


class Clogging:
    """Pressure drop that rises with accumulated solids and scales with flow."""

    def __init__(self, dp_clean, dp_limit, capacity_g, q_ref, life_days=None):
        self.dp_clean, self.dp_limit = dp_clean, dp_limit
        self.cap, self.q_ref, self.life_days = capacity_g, q_ref, life_days
        self.solids = 0.0
        self.installed_t = 0.0

    def add(self, grams: float) -> None:
        self.solids += grams

    def dp_ref(self) -> float:
        return self.dp_clean + (self.dp_limit - self.dp_clean) * min(self.solids / self.cap, 1.5)

    def dp(self, flow_lph: float) -> float:
        return self.dp_ref() * flow_lph / self.q_ref

    def due(self, t: float):
        if self.dp_ref() >= self.dp_limit:
            return "pressure-drop limit reached"
        if self.life_days and (t - self.installed_t) >= self.life_days * 24.0:
            return "service life reached"
        return None

    def reset(self, t: float) -> None:
        self.solids = 0.0
        self.installed_t = t


class Stage:
    key = "stage"
    label = "Stage"

    def __init__(self, cfg, key=None, label=None):
        if key:
            self.key = key
        if label:
            self.label = label
        self.cfg = cfg
        self.p = cfg.section(f"stages.{self.key}")
        self.ntu2tss = cfg("general.ntu_to_tss_mgl")
        self.floor = cfg("general.bacteria_floor_log")
        self.events: list[tuple] = []
        self.warnings: set[str] = set()
        self.last: dict = {}  # metrics of the latest processed step (flow dependent)

    def process(self, w: WaterState, dt: float, ctx: dict):
        raise NotImplementedError

    def state_metrics(self) -> dict:
        return {}

    def _event(self, t, msg):
        self.events.append((t, self.label, msg))

    @staticmethod
    def _inlet_conc(w: WaterState) -> dict:
        return {k: getattr(w, k) for k in DISSOLVED}

    def _solids(self, w: WaterState, t_out: float, dt: float) -> float:
        return max(0.0, w.turbidity_ntu - t_out) * self.ntu2tss * w.flow_lph * dt / 1000.0


class Equalisation(Stage):
    key, label = "equalisation", "Equalisation tank"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.sludge_g = 0.0

    def process(self, w, dt, ctx):
        p = self.p
        hrt = ctx.get("hrt_h", p["reference_hrt_h"])
        removal = p["max_turbidity_removal"] * min(1.0, hrt / p["reference_hrt_h"])
        t_out = turb_out(w.turbidity_ntu, removal, p["turbidity_floor_ntu"])
        solids = self._solids(w, t_out, dt)
        self.sludge_g += solids
        self.last = {"equalisation.hrt_h": hrt, "equalisation.removal": removal}
        return w.with_(turbidity_ntu=t_out), Waste(0.0, {}, solids)

    def state_metrics(self):
        return {"equalisation.sludge_g": self.sludge_g}


class MultimediaFilter(Stage):
    key, label = "mmf", "Multimedia filter"

    def __init__(self, cfg):
        super().__init__(cfg)
        p = self.p
        self.clog = Clogging(p["dp_clean_bar"], p["dp_limit_bar"], p["solids_capacity_g"], cfg("plant.treatment_flow_lph"))
        self.run_h = 0.0

    def process(self, w, dt, ctx):
        p = self.p
        if w.turbidity_ntu > p["max_inlet_turbidity_ntu"]:
            self.warnings.add("Multimedia filter inlet turbidity above model validity limit")
        t_out = turb_out(w.turbidity_ntu, p["turbidity_removal"], p["turbidity_floor_ntu"])
        q_waste = w.flow_lph * p["backwash_loss_frac"]  # backwash water, amortised over the cycle
        solids = self._solids(w, t_out, dt)
        self.clog.add(solids)
        self.run_h += dt
        self.last = {"mmf.dp_bar": self.clog.dp(w.flow_lph)}
        if self.run_h >= p["backwash_interval_h"] or self.clog.due(ctx["t"]):
            self._event(ctx["t"], "Backwash performed")
            self.clog.reset(ctx["t"])
            self.run_h = 0.0
        out = w.with_(turbidity_ntu=t_out, flow_lph=w.flow_lph - q_waste)
        return out, Waste(q_waste, self._inlet_conc(w), solids)


class CarbonFilter(Stage):
    """ACF + GAC. Removal falls with short contact time and as the bed saturates (breakthrough)."""
    key, label = "carbon", "ACF + GAC carbon"

    def __init__(self, cfg, design_toc_mgl: float, design_daily_l: float):
        super().__init__(cfg)
        p = self.p
        self.capacity_g = p["bed_life_days"] * p["fresh_toc_removal"] * design_toc_mgl * design_daily_l / 1000.0
        self.loaded_g = 0.0
        self.beds_used = 1

    @property
    def saturation(self) -> float:
        return self.loaded_g / self.capacity_g

    def process(self, w, dt, ctx):
        p = self.p
        ebct = p["bed_volume_l"] / max(w.flow_lph, 1e-9) * 60.0
        f_ebct = min(1.0, ebct / p["ebct_ref_min"])
        f_life = max(0.0, 1.0 - self.saturation ** 3)  # smooth breakthrough curve
        eff_toc = p["fresh_toc_removal"] * f_ebct * f_life
        eff_cl = p["chlorine_removal"] * f_ebct * f_life
        toc_out = w.toc_mgl * (1 - eff_toc)
        self.loaded_g += (w.toc_mgl - toc_out) * w.flow_lph * dt / 1000.0
        self.last = {"carbon.ebct_min": ebct, "carbon.toc_removal": eff_toc}
        if self.saturation >= p["replace_at_saturation"]:
            self._event(ctx["t"], "Carbon bed replaced (breakthrough)")
            self.loaded_g = 0.0
            self.beds_used += 1
        out = w.with_(toc_mgl=toc_out, chlorine_mgl=w.chlorine_mgl * (1 - eff_cl))
        return out, Waste(0.0, {}, 0.0)  # adsorbed on carbon, no waste stream; dissolved salts untouched

    def state_metrics(self):
        return {"carbon.saturation": self.saturation}


class Cartridge(Stage):
    """Cartridge / candle filter, parameterised by config section (5 um or 0.5 um)."""

    def __init__(self, cfg, key, label):
        super().__init__(cfg, key=key, label=label)
        p = self.p
        self.clog = Clogging(p["dp_clean_bar"], p["dp_limit_bar"], p["solids_capacity_g"],
                             cfg("plant.treatment_flow_lph"), p["life_days"])
        self.replacements = 0

    def process(self, w, dt, ctx):
        p = self.p
        t_out = turb_out(w.turbidity_ntu, p["turbidity_removal"], p["turbidity_floor_ntu"])
        solids = self._solids(w, t_out, dt)
        self.clog.add(solids)
        self.last = {f"{self.key}.dp_bar": self.clog.dp(w.flow_lph), f"{self.key}.lrv": p["bacteria_lrv"]}
        reason = self.clog.due(ctx["t"])
        if reason:
            self._event(ctx["t"], f"Cartridge replaced ({reason})")
            self.clog.reset(ctx["t"])
            self.replacements += 1
        out = w.with_(turbidity_ntu=t_out, bacteria_log=reduce_log(w.bacteria_log, p["bacteria_lrv"], self.floor))
        return out, Waste(0.0, {}, 0.0)

    def state_metrics(self):
        return {f"{self.key}.loading": self.clog.solids / self.clog.cap}


class UltrafiltrationStage(Stage):
    """UF membrane: particles and bacteria out, dissolved salts pass (rejection ~0)."""
    key, label = "uf", "UF membrane"

    def __init__(self, cfg):
        super().__init__(cfg)
        p = self.p
        self.clog = Clogging(p["tmp_clean_bar"], p["tmp_limit_bar"], p["solids_capacity_g"], cfg("plant.treatment_flow_lph"))
        self.cleans = 0

    def process(self, w, dt, ctx):
        p = self.p
        q_out = w.flow_lph * p["recovery"]
        q_waste = w.flow_lph - q_out
        t_out = turb_out(w.turbidity_ntu, p["turbidity_removal"], p["turbidity_floor_ntu"])
        rej = p["tds_rejection"]
        diss = {k: getattr(w, k) * (1 - rej) for k in DISSOLVED}
        # waste carries inlet concentration plus whatever salt the membrane rejected
        waste_conc = {k: (q_waste * getattr(w, k) + q_out * (getattr(w, k) - diss[k])) / q_waste for k in DISSOLVED}
        solids = self._solids(w, t_out, dt)
        self.clog.add(solids)
        flux = q_out / p["membrane_area_m2"]
        if flux > p["max_flux_lmh"]:
            self.warnings.add("UF flux above recommended maximum")
        self.last = {"uf.tmp_bar": self.clog.dp(w.flow_lph), "uf.flux_lmh": flux, "uf.lrv": p["bacteria_lrv"]}
        reason = self.clog.due(ctx["t"])
        if reason:
            self._event(ctx["t"], f"UF chemical clean ({reason})")
            self.clog.reset(ctx["t"])
            self.cleans += 1
        out = w.with_(flow_lph=q_out, turbidity_ntu=t_out,
                      bacteria_log=reduce_log(w.bacteria_log, p["bacteria_lrv"], self.floor), **diss)
        return out, Waste(q_waste, waste_conc, solids)


class UVStage(Stage):
    """Dose-based UV disinfection. Dose scales with 1/flow, UV transmittance, lamp age and fouling."""
    key, label = "uv", "UV disinfection"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.lamp_h = 0.0
        self.lamps_used = 1
        tbl = np.array(self.p["dose_response"], dtype=float)
        self._dose, self._log = tbl[:, 0], tbl[:, 1]

    def process(self, w, dt, ctx):
        p = self.p
        uvt = float(np.clip(p["uvt_clean_pct"] - p["uv_abs_per_toc"] * w.toc_mgl
                            - p["uv_abs_per_ntu"] * w.turbidity_ntu, 50.0, 99.0))
        age = 1.0 - (1.0 - p["lamp_end_factor"]) * min(1.0, self.lamp_h / p["lamp_life_h"])
        dose = (p["design_dose_mj_cm2"] * p["design_flow_lph"] / max(w.flow_lph, 1e-9)
                * uvt / p["uvt_design_pct"] * age * p["fouling_factor"])
        lrv = float(np.interp(dose, self._dose, self._log))
        if dose < 20.0:
            self.warnings.add("UV dose below 20 mJ/cm2 (weak bacteria disinfection)")
        self.last = {"uv.dose_mj_cm2": dose, "uv.lrv": lrv, "uv.uvt_pct": uvt, "uv.age_factor": age}
        self.lamp_h += dt
        if self.lamp_h >= p["lamp_life_h"]:
            self._event(ctx["t"], "UV lamp replaced")
            self.lamp_h = 0.0
            self.lamps_used += 1
        return w.with_(bacteria_log=reduce_log(w.bacteria_log, lrv, self.floor)), Waste(0.0, {}, 0.0)

    def state_metrics(self):
        return {"uv.lamp_h": self.lamp_h}


class Pipeline:
    def __init__(self, stages):
        self.stages = stages
        self.labels = {s.key: s.label for s in stages}
        self.labels["reject"] = "Reject (input)"

    def run(self, w: WaterState, dt: float, ctx: dict):
        snaps = {"reject": w}
        wastes = []
        for s in self.stages:
            w, waste = s.process(w, dt, ctx)
            snaps[s.key] = w
            wastes.append((s.key, waste))
        return w, wastes, snaps

    def warnings(self) -> set:
        return set().union(*(s.warnings for s in self.stages))

    def events(self) -> list:
        return [e for s in self.stages for e in s.events]
