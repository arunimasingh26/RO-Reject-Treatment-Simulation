# Dialysis RO-reject water treatment: simulation

Time-based simulation of a treatment train for hospital dialysis RO reject water,
for non-potable reuse:

collection tank -> equalisation -> multimedia filter -> ACF/GAC carbon -> 5 um cartridge
-> 0.5 um candle -> UF membrane -> UV -> treated tank -> reuse tank

## Run

    pip install -r requirements.txt
    python run_demo.py          # prints results, saves plots + CSVs to ./output
    streamlit run app.py        # interactive dashboard
    pytest -q                   # tests (mass balance, volume conservation, edge cases)

## Layout

    config/defaults.yaml     every number: value, unit, min/max, source/assumption note
    rejectsim/config.py      loading + validation (errors for impossible values, warnings for out-of-range)
    rejectsim/water.py       WaterState, mixing, RO-reject source module (reject concentration is calculated)
    rejectsim/stages.py      all stages, one interface: process(water, dt, ctx) -> (water, waste)
    rejectsim/tanks.py       tanks with mixing + bacterial regrowth
    rejectsim/simulation.py  build_train(), steady_state(), run_time_based()
    rejectsim/analysis.py    reuse-target checks, LSI, mass balance, sensitivity
    rejectsim/viz.py         flow diagram, per-stage bars, time series, tornado
    app.py                   Streamlit dashboard
    tests/test_sim.py

## Replacing placeholders with real data

Edit `config/defaults.yaml`. Every note starting with ASSUMPTION is a placeholder.
Derived values (reject TDS, hardness, flows) are computed, not typed, so keep
recovery / rejection / feed quality consistent instead of overriding reject values.
Out-of-range values give warnings; impossible ones (recovery >= 0.95, fractions outside 0-1,
inconsistent pump levels, non-monotonic UV curve) raise an error.

## Known simplifications

- Backwash water is an amortised % loss, not a discrete shutdown.
- Removal percentages are fixed per stage (with floors, loading and flow effects where noted);
  they are not mechanistic filtration models.
- UV uses a placeholder bacteria dose-response curve; viruses are not modelled.
- No hydraulics (pipe friction, pump curves); no cleaning-chemical effluent.
- Bacterial regrowth in storage is a pure assumption.
