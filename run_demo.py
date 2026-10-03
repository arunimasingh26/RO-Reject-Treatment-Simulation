"""Command-line demo: runs the default scenario, prints results, saves plots + CSVs to ./output."""
import pathlib

import matplotlib.pyplot as plt
import pandas as pd

from rejectsim import Config, build_train, check_targets, run_time_based, steady_state
from rejectsim.viz import fig_flow_diagram, fig_stage_profile, fig_timeseries

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)
out = pathlib.Path("output")
out.mkdir(exist_ok=True)

cfg = Config.load()
ss = steady_state(cfg)
print("\n== Steady-state: quality after each stage ==")
print(ss[["flow_lph", "turbidity_ntu", "tds_mgl", "toc_mgl", "chlorine_mgl", "bacteria_log", "LSI"]].round(3))
print("\n== Checks on treated water vs reuse targets ==")
print(check_targets(ss.iloc[-1].pipe(lambda r: __import__("rejectsim").water.WaterState(**{k: r[k] for k in ss.columns if k != "LSI"})), cfg))

res = run_time_based(cfg)
print("\n== Time-based summary ==")
for k, v in res.summary.items():
    print(f"{k:28s} {v:,.2f}" if isinstance(v, float) else f"{k:28s} {v}")
print("\nWarnings:", res.warnings or "none")

res.df.to_csv(out / "timeseries.csv", index=False)
res.events.to_csv(out / "events.csv", index=False)
ss.to_csv(out / "steady_state.csv")
fig_flow_diagram(build_train(cfg), ss.reset_index(drop=True)).savefig(out / "flow_diagram.png", dpi=150)
fig_stage_profile(ss).savefig(out / "stage_profile.png", dpi=130)
fig_timeseries(res.df).savefig(out / "timeseries.png", dpi=110)
plt.close("all")
print(f"\nSaved plots and CSVs to {out.resolve()}")
