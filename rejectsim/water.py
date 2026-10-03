"""Water state, mixing, and the RO-reject source module.

Units: flow L/h, concentrations mg/L, turbidity NTU, temperature degC,
bacteria as log10 CFU/mL. Derived values (reject concentrations) are
computed here from feed quality, recovery and rejection - never typed in.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace

DISSOLVED = ("tds_mgl", "hardness_mgl", "ca_hardness_mgl", "alkalinity_mgl", "chloride_mgl", "silica_mgl")
LINEAR = ("turbidity_ntu", "toc_mgl", "chlorine_mgl", "ph", "temp_c") + DISSOLVED


@dataclass(frozen=True)
class WaterState:
    flow_lph: float
    turbidity_ntu: float
    tds_mgl: float
    hardness_mgl: float
    ca_hardness_mgl: float
    alkalinity_mgl: float
    ph: float
    chloride_mgl: float
    silica_mgl: float
    toc_mgl: float
    chlorine_mgl: float
    temp_c: float
    bacteria_log: float

    def with_(self, **kw) -> "WaterState":
        return replace(self, **kw)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Waste:
    """Waste stream leaving a stage (backwash, UF concentrate). Solids are in grams for the step."""
    flow_lph: float = 0.0
    conc: dict = field(default_factory=dict)
    solids_g: float = 0.0


def mix(a: WaterState | None, va: float, b: WaterState, vb: float) -> WaterState:
    """Volume-weighted mix of two waters (volumes in L). Bacteria are mixed in CFU space."""
    if a is None or va <= 0:
        return b.with_(flow_lph=0.0)
    if vb <= 0:
        return a
    f = vb / (va + vb)
    kw = {k: getattr(a, k) * (1 - f) + getattr(b, k) * f for k in LINEAR}
    bl = math.log10((1 - f) * 10 ** a.bacteria_log + f * 10 ** b.bacteria_log)
    return a.with_(bacteria_log=bl, flow_lph=0.0, **kw)


def concentration_factor(recovery: float, rejection: float) -> float:
    """Reject/feed concentration ratio for a RO with given recovery and rejection.
    C_reject = C_feed * (1 - r*(1 - R)) / (1 - r)   (from a mass balance)."""
    return (1.0 - recovery * (1.0 - rejection)) / (1.0 - recovery)


def reject_flow_lph(cfg) -> float:
    return cfg("plant.ro_feed_flow_lph") * (1.0 - cfg("plant.ro_recovery"))


def reject_profile(cfg) -> WaterState:
    """Build the RO reject water from feed quality + recovery + rejection."""
    s = cfg.section("source")
    r = cfg("plant.ro_recovery")
    ks = concentration_factor(r, s["ro_salt_rejection"])
    kp = concentration_factor(r, s["ro_particle_rejection"])
    return WaterState(
        flow_lph=reject_flow_lph(cfg),
        turbidity_ntu=s["feed_turbidity_ntu"] * kp,
        tds_mgl=s["feed_tds_mgl"] * ks,
        hardness_mgl=s["feed_hardness_mgl"] * ks,
        ca_hardness_mgl=s["feed_ca_hardness_mgl"] * ks,
        alkalinity_mgl=s["feed_alkalinity_mgl"] * ks,
        ph=s["feed_ph"] + s["reject_ph_shift"],
        chloride_mgl=s["feed_chloride_mgl"] * ks,
        silica_mgl=s["feed_silica_mgl"] * ks,
        toc_mgl=s["reject_toc_mgl"],
        chlorine_mgl=s["reject_chlorine_mgl"],
        temp_c=s["temp_c"],
        bacteria_log=s["reject_bacteria_log"],
    )
