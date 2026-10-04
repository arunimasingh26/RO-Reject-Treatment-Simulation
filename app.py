"""Streamlit dashboard:  streamlit run app.py"""
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from rejectsim import Config, ConfigError, build_train, check_targets, run_time_based, steady_state
from rejectsim.analysis import SENSITIVITY_METRICS, sensitivity
from rejectsim.viz import fig_flow_diagram, fig_sensitivity, fig_stage_profile, fig_timeseries
from rejectsim.water import WaterState
from plantviz import build_payload, render_plant

st.set_page_config(page_title="Dialysis RO-reject treatment simulation", layout="wide")
st.title("Dialysis RO-reject water treatment: simulation")
st.caption("All values are editable placeholders (see the Parameters tab for each one's note). "
           "Replace them with measured or cited data before drawing conclusions.")

cfg = Config.load()


def slider(path, label, step=None, integer=False):
    leaf = cfg.leaf(path)
    lo, hi, v = leaf["min"], leaf["max"], leaf["value"]
    if integer:
        val = st.sidebar.slider(label, int(lo), int(hi), int(v), 1, help=leaf["note"])
    else:
        val = st.sidebar.slider(label, float(lo), float(hi), float(v), step, help=leaf["note"])
    cfg.set(path, val)


sb = st.sidebar
sb.header("Plant")
slider("plant.ro_feed_flow_lph", "RO feed flow (L/h)", 50.0)
slider("plant.ro_recovery", "RO recovery", 0.01)
slider("plant.ro_hours_per_day", "RO hours per day", integer=True)
slider("plant.treatment_flow_lph", "Treatment pump flow (L/h)", 25.0)
slider("plant.demand_l_per_day", "Non-potable demand (L/day)", 100.0)
slider("plant.collection_tank_l", "Collection tank (L)", 100.0)
sb.header("Source water")
slider("source.feed_tds_mgl", "Feed TDS (mg/L)", 10.0)
slider("source.feed_hardness_mgl", "Feed hardness (mg/L CaCO3)", 5.0)
slider("source.ro_salt_rejection", "RO salt rejection", 0.005)
slider("source.feed_turbidity_ntu", "Feed turbidity (NTU)", 0.05)
slider("source.reject_toc_mgl", "Reject TOC (mg/L)", 0.5)
slider("source.reject_bacteria_log", "Reject bacteria (log10 CFU/mL)", 0.1)
sb.header("Stages")
slider("stages.carbon.fresh_toc_removal", "Carbon TOC removal (fresh)", 0.01)
slider("stages.uf.bacteria_lrv", "UF bacteria log removal", 0.1)
slider("stages.uv.design_dose_mj_cm2", "UV design dose (mJ/cm2)", 1.0)
slider("stages.uv.fouling_factor", "UV sleeve fouling factor", 0.01)
slider("tanks.regrowth_log_per_day", "Storage regrowth (log/day)", 0.01)
sb.header("Simulation")
slider("simulation.days", "Days", integer=True)

try:
    warn = cfg.validate()
    ss = steady_state(cfg)
    res = run_time_based(cfg)
except ConfigError as e:
    st.error(f"Invalid parameters: {e}")
    st.stop()

for w in res.warnings:
    st.warning(w)

tab_over, tab_live, tab_stage, tab_time, tab_sens, tab_params = st.tabs(
    ["Overview", "Live plant", "Per-stage quality", "Time-based", "Sensitivity", "Parameters"])

s = res.summary
with tab_over:
    st.pyplot(fig_flow_diagram(build_train(cfg), ss.reset_index(drop=True)))
    c = st.columns(4)
    c[0].metric("Reject generated", f"{s['reject_generated_l'] / 1000:,.0f} m\u00b3")
    c[1].metric("Delivered for reuse", f"{s['delivered_l'] / 1000:,.0f} m\u00b3")
    c[2].metric("Overall reuse", f"{s['overall_reuse_pct']:.1f} %")
    c[3].metric("Overflow to drain", f"{s['collection_overflow_l'] / 1000:,.1f} m\u00b3")
    c = st.columns(4)
    c[0].metric("Train water recovery", f"{s['train_water_recovery_pct']:.1f} %")
    c[1].metric("Unmet demand", f"{s['unmet_demand_l'] / 1000:,.1f} m\u00b3")
    c[2].metric("Delivered water meeting targets", f"{s['delivered_compliant_pct']:.0f} %")
    c[3].metric("TDS: reject \u2192 treated", f"{s['reject_tds_mgl']:.0f} \u2192 {s['mean_outlet_tds_mgl']:.0f} mg/L")
    st.info("Key limitation: no stage in this train removes dissolved salts, so TDS and hardness are unchanged. "
            "Turbidity, organics and microbes are what the train improves.")
    last = ss.iloc[-1]
    st.subheader("Treated water vs (placeholder) reuse targets")
    st.dataframe(check_targets(WaterState(**{k: last[k] for k in ss.columns if k != "LSI"}), cfg), hide_index=True)
    st.caption(f"Scaling index (LSI): reject {ss['LSI'].iloc[0]:.2f}. Positive values indicate scale-forming water.")

with tab_live:
    render_plant(build_payload(cfg, build_train(cfg), ss))

with tab_stage:
    st.dataframe(ss.round(3))
    st.pyplot(fig_stage_profile(ss))

with tab_time:
    st.pyplot(fig_timeseries(res.df))
    st.subheader("Events")
    st.dataframe(res.events, hide_index=True)
    st.download_button("Download time series (CSV)", res.df.to_csv(index=False), "timeseries.csv")

with tab_sens:
    metric = st.selectbox("Metric", list(SENSITIVITY_METRICS), format_func=SENSITIVITY_METRICS.get)
    if st.button("Run sensitivity analysis (about 25 short runs)"):
        sdf = sensitivity(cfg, metric=metric, days=14)
        st.pyplot(fig_sensitivity(sdf, SENSITIVITY_METRICS[metric]))
        st.dataframe(sdf.round(4), hide_index=True)

with tab_params:
    rows = [{"parameter": p, "value": str(l["value"]), "unit": l.get("unit", ""),
             "min": l.get("min"), "max": l.get("max"), "note": l.get("note", "")}
            for p, l in cfg.leaves().items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, height=600)
    st.caption("Edit defaults in config/defaults.yaml. Sidebar sliders change only the current session.")

plt.close("all")
