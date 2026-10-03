import math

import pytest

from rejectsim import (Config, ConfigError, build_train, lsi, mass_balance, reject_profile,
                       run_time_based, sensitivity, steady_state)
from rejectsim.water import WaterState, concentration_factor, mix


@pytest.fixture
def cfg():
    return Config.load()


def test_default_config_is_valid(cfg):
    assert cfg.validate() == []


def test_reject_concentration_formula(cfg):
    # 300 mg/L feed, 50% recovery, 97% rejection -> 591 mg/L (about 2x)
    assert reject_profile(cfg).tds_mgl == pytest.approx(591.0)
    assert concentration_factor(0.5, 0.97) == pytest.approx(1.97)


def test_reject_salt_mass_balance_across_ro(cfg):
    r, rej = cfg("plant.ro_recovery"), cfg("source.ro_salt_rejection")
    qf = cfg("plant.ro_feed_flow_lph")
    cf = cfg("source.feed_tds_mgl")
    rw = reject_profile(cfg)
    permeate_mass = qf * r * cf * (1 - rej)
    assert qf * cf == pytest.approx(rw.flow_lph * rw.tds_mgl + permeate_mass)


@pytest.mark.parametrize("recovery", [0.3, 0.5, 0.75])
def test_pipeline_mass_balance(cfg, recovery):
    cfg.set("plant.ro_recovery", recovery)
    pl = build_train(cfg)
    w = reject_profile(cfg).with_(flow_lph=800.0)
    out, wastes, _ = pl.run(w, 1.0, {"t": 1.0, "hrt_h": 2.0})
    for name, err in mass_balance(w, out, wastes).items():
        assert err < 1e-9, name


def test_uf_rejection_goes_to_waste_and_balances(cfg):
    cfg.set("stages.uf.tds_rejection", 0.02)
    pl = build_train(cfg)
    w = reject_profile(cfg).with_(flow_lph=800.0)
    out, wastes, _ = pl.run(w, 1.0, {"t": 1.0, "hrt_h": 2.0})
    assert out.tds_mgl < w.tds_mgl
    assert mass_balance(w, out, wastes)["tds_mgl"] < 1e-9


def test_no_stage_removes_salts_by_default(cfg):
    ss = steady_state(cfg)
    assert ss["tds_mgl"].nunique() == 1
    assert ss["hardness_mgl"].nunique() == 1


def test_uv_dose_falls_with_flow(cfg):
    from rejectsim.stages import UVStage
    w = reject_profile(cfg)
    lo, hi = UVStage(cfg), UVStage(cfg)
    lo.process(w.with_(flow_lph=500), 1.0, {"t": 1})
    hi.process(w.with_(flow_lph=1500), 1.0, {"t": 1})
    assert lo.last["uv.dose_mj_cm2"] > hi.last["uv.dose_mj_cm2"]
    assert lo.last["uv.lrv"] >= hi.last["uv.lrv"]


def test_turbidity_floor_respected(cfg):
    ss = steady_state(cfg)
    assert ss["turbidity_ntu"].iloc[-1] >= cfg("stages.uf.turbidity_floor_ntu") - 1e-12


def test_mix_conserves_volume_weighted_quantities():
    a = WaterState(0, 1, 100, 50, 30, 40, 7, 10, 5, 2, 0, 25, 2.0)
    b = a.with_(turbidity_ntu=3, tds_mgl=300, bacteria_log=0.0)
    m = mix(a, 100, b, 100)
    assert m.turbidity_ntu == pytest.approx(2) and m.tds_mgl == pytest.approx(200)
    assert m.bacteria_log == pytest.approx(math.log10((100 + 1) / 2))


def test_time_based_volume_conservation(cfg):
    res = run_time_based(cfg, days=20)
    s, df = res.summary, res.df
    # generated = overflow + processed + change in collection tank
    assert s["reject_generated_l"] == pytest.approx(s["collection_overflow_l"] + s["processed_l"] + df["collection_l"].iloc[-1])
    # processed = waste + produced + lost at treated tank
    assert s["processed_l"] == pytest.approx(s["backwash_waste_l"] + s["produced_l"] + s["treated_lost_l"])
    # produced = delivered + stored in treated/reuse tanks
    assert s["produced_l"] == pytest.approx(s["delivered_l"] + df["treated_l"].iloc[-1] + df["reuse_l"].iloc[-1])


def test_tanks_never_negative_or_over_capacity(cfg):
    df = run_time_based(cfg, days=15).df
    for col, cap in [("collection_l", "collection_tank_l"), ("treated_l", "treated_tank_l"), ("reuse_l", "reuse_tank_l")]:
        assert df[col].min() >= -1e-9
        assert df[col].max() <= cfg(f"plant.{cap}") + 1e-6


def test_small_tank_overflows_and_is_reported(cfg):
    cfg.set("plant.collection_tank_l", 500)
    res = run_time_based(cfg, days=3)
    assert res.summary["collection_overflow_l"] > 0
    assert res.events["event"].str.contains("overflow").any()


def test_replacement_events_triggered(cfg):
    cfg.set("stages.candle_05um.solids_capacity_g", 20)
    cfg.set("stages.carbon.bed_life_days", 20)
    res = run_time_based(cfg, days=60)
    ev = res.events["event"]
    assert ev.str.contains("Cartridge replaced").any()
    assert ev.str.contains("Carbon bed replaced").any()


def test_regrowth_raises_stored_water_bacteria(cfg):
    cfg.set("tanks.regrowth_log_per_day", 0.3)
    hi = run_time_based(cfg, days=10).summary["mean_reuse_bacteria_log"]
    cfg.set("tanks.regrowth_log_per_day", 0.0)
    lo = run_time_based(cfg, days=10).summary["mean_reuse_bacteria_log"]
    assert hi > lo


def test_invalid_values_raise(cfg):
    cfg.set("plant.ro_recovery", 0.99)
    with pytest.raises(ConfigError):
        cfg.validate()
    c2 = Config.load()
    c2.set("stages.uf.recovery", 1.4)
    with pytest.raises(ConfigError):
        run_time_based(c2, days=1)


def test_out_of_range_value_warns_not_fails(cfg):
    cfg.set("source.feed_tds_mgl", 1500)
    assert any("feed_tds_mgl" in w for w in cfg.validate())
    assert run_time_based(cfg, days=2).summary["reject_tds_mgl"] > 2500


def test_uv_dose_response_must_be_monotonic(cfg):
    cfg.set("stages.uv.dose_response", [[0, 0], [20, 3], [10, 1]])
    with pytest.raises(ConfigError):
        cfg.validate()


def test_zero_demand_and_zero_flow_edges(cfg):
    cfg.set("plant.demand_l_per_day", 0)
    res = run_time_based(cfg, days=5)
    assert res.summary["delivered_l"] == 0
    assert math.isnan(res.summary["delivered_compliant_pct"])


def test_lsi_sign_behaviour(cfg):
    w = reject_profile(cfg)
    assert lsi(w.with_(ph=9.0)) > lsi(w.with_(ph=6.5))


def test_sensitivity_runs_and_ranks(cfg):
    sdf = sensitivity(cfg, paths=["stages.uv.fouling_factor", "plant.treatment_flow_lph"], days=5)
    assert len(sdf) == 2 and (sdf["swing"].diff().dropna() <= 1e-12).all()


def test_regression_default_results(cfg):
    """Pin default-run behaviour so later edits do not change results silently."""
    s = run_time_based(cfg, days=30).summary
    assert s["reject_tds_mgl"] == pytest.approx(591.0)
    assert s["train_water_recovery_pct"] == pytest.approx(89.24, abs=0.05)
    assert s["delivered_compliant_pct"] == pytest.approx(100.0)
    assert s["mean_outlet_tds_mgl"] == pytest.approx(591.0)
