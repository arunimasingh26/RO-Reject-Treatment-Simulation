# Dialysis RO-reject water treatment: simulation

A time-based simulation of a treatment train for hospital dialysis RO reject water, aimed at
non-potable reuse. It comes with an interactive Streamlit dashboard and a **Live plant** view that
animates the whole train: water flowing through each unit, changing colour as it is cleaned, tanks
filling and emptying, and filters, cartridges, carbon and the UV lamp wearing out over time.

```
collection tank -> equalisation -> multimedia filter -> ACF/GAC carbon -> 5 um cartridge
-> 0.5 um candle -> UF membrane -> UV -> treated tank -> reuse tank
```

> All numbers are editable placeholders until replaced with measured or cited data. See
> [Replacing placeholders with real data](#replacing-placeholders-with-real-data).

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py        # interactive dashboard (includes the Live plant tab)
python run_demo.py          # prints results, saves plots and CSVs to ./output
pytest -q                   # tests: mass balance, volume conservation, edge cases
```

## The dashboard

`streamlit run app.py` opens a dashboard with the parameters in the sidebar and six tabs:

| Tab | What it shows |
|---|---|
| Overview | Headline results and reuse-target checks for the treated water |
| **Live plant** | Animated view of the whole train (see below) |
| Per-stage quality | Steady-state water quality after each stage |
| Time-based | Time series of tanks, flows and quality over the run |
| Sensitivity | Which parameters move the results most |
| Parameters | Every parameter with its unit, range and source/assumption note |

### Sidebar parameters

Changing any slider reruns the simulation and redraws every tab.

| Section | Parameters |
|---|---|
| Plant | RO feed flow, RO recovery, RO hours per day, treatment pump flow, demand, collection tank size |
| Source water | Feed TDS and hardness, RO salt rejection, feed turbidity, reject TOC, reject bacteria |
| Stages | Carbon TOC removal, UF bacteria log removal, UV design dose, UV sleeve fouling, storage regrowth |
| Maintenance and lifetimes | Backwash interval, carbon bed life, 5 um cartridge life, 0.5 um candle life, UV lamp life |
| Replacement limits | Pressure-drop limits (multimedia filter, 5 um cartridge, 0.5 um candle), UF clean-in-place TMP limit |
| Simulation | Number of days |

## Live plant

The **Live plant** tab plays back the time-based run as an animation of the treatment train.

**What you see**

- The train laid out as connected units, with pipes whose flow animation follows the flow rate.
  Idle hours (pump off) show stopped pipes and held colours.
- **Water colour** shifts from clear cyan to murky brown. Use the dropdown to colour by overall
  cleanliness, turbidity, organics (TOC) or bacteria. Grey specks in the pipes show turbidity and
  red specks show bacteria on a log scale, so you can watch them thin out through UF and UV.
- **Tank levels** follow the simulated volumes of the collection, treated and reuse tanks.
- **Wear gauges** under each stage show the percentage of its replacement limit (pressure drop,
  carbon saturation, UF TMP, UV lamp hours). The units themselves change appearance: filter sand
  darkens, the carbon bed lightens, cartridge elements go from white to brown, UF fibres take on a
  tint, sludge builds up in the equalisation tank and the UV lamp dims with age.
- **Events** (backwash, replacements, unmet demand, tank overflow) flash a halo around the
  relevant unit and appear in the event log. Click a log entry to jump to that moment.
- **Inspector:** click any unit (or tab to it and press Enter) to see its flow and its inlet and
  outlet turbidity, TOC and bacteria, plus its wear metric against the limit.
- **Controls:** play and pause, step back or forward one hour, speed (4 to 72 simulated hours per
  second), and a time scrubber with event ticks (amber for plant-level warnings).

**Reading the colours:** colours encode the model's numbers relative to the raw reject water and
are contrast-boosted so that small real changes stay visible. They are not a literal rendering
of what the water looks like. TDS is not coloured because no stage in the model changes it.

### How it works

```
sidebar sliders
      |
      v
rejectsim (the model, unchanged)  ->  run_time_based() and steady_state()
      |
      v
plantviz/payload.py     ->  compact JSON: layout data, per-hour frames, events, wear limits
      |
      v
plantviz/component.py   ->  one self-contained HTML page via st.components.v1.html
      |
      v
browser (vanilla JS + SVG, no external libraries)
  data -> animator (clock) -> scene (units, pipes, particles) -> HUD (log, inspector, controls)
```

The visual is a read-only consumer of the model results. Play, pause, speed and scrubbing run
entirely in the browser, so they do not rerun Streamlit.

**Notes and limitations**

- Changing a sidebar slider reruns the model and the animation restarts from the beginning.
- Runs longer than about 2,000 hours are sampled down to keep the page light. A 30-day run is
  roughly 220 KB.
- The model does not record the treated-tank to reuse-tank transfer, so that pipe flows whenever
  the pump is on, the treated tank holds water and the reuse tank is not full.
- Treated and reuse tank colours use the UV outlet water, because those tanks do not log full
  quality values.
- Backwash is amortised in the model, so the visual shows a steady drain trickle plus a flash at
  each backwash event, not a discrete shutdown.
- The equalisation tank has no sludge limit in the model, so its gauge is relative to the peak of
  the current run.

## Project layout

```
config/defaults.yaml     every number: value, unit, min/max, source/assumption note
rejectsim/               the simulation model
  config.py              loading + validation (errors for impossible values, warnings for out-of-range)
  water.py               WaterState, mixing, RO-reject source module (reject concentration is calculated)
  stages.py              all stages, one interface: process(water, dt, ctx) -> (water, waste)
  tanks.py               tanks with mixing + bacterial regrowth
  simulation.py          build_train(), steady_state(), run_time_based()
  analysis.py            reuse-target checks, LSI, mass balance, sensitivity
  viz.py                 flow diagram, per-stage bars, time series, tornado
plantviz/                the Live plant visual (Streamlit component)
  payload.py             simulation results -> JSON scene description
  component.py           assembles the HTML/CSS/JS bundle and embeds it in Streamlit
  web/index.html         page skeleton
  web/style.css          styling
  web/js/layout.js       the floor plan: unit positions and pipe routes
  web/js/colour.js       water quality -> colour and speck counts
  web/js/units.js        SVG drawing for each unit type
  web/js/data.js         frame lookup and interpolation between hourly rows
  web/js/scene.js        builds the SVG once, then updates colours, levels, flow and gauges
  web/js/playback.js     clock, controls, event flashes, event log, inspector
app.py                   Streamlit dashboard
run_demo.py              command-line demo
tests/test_sim.py        tests
```

## Changing parameters

There are two places, depending on what you want to change.

1. **A slider's default value, allowed range, unit or note:** edit that parameter's `value`,
   `min`, `max`, `unit` and `note` in `config/defaults.yaml`.
2. **Whether a parameter has a sidebar slider:** edit the `slider("path", "Label", step)` lines in
   `app.py`. The path is the parameter's location in the YAML, for example
   `stages.uv.lamp_life_h`. Use `integer=True` for whole-number parameters.

The Live plant needs no changes for these: it reads its limits from the same configuration the
sliders change.

**Adding a parameter that does not exist yet**

1. Add it to `config/defaults.yaml` with value, min, max, unit and note.
2. Make the model use it, usually in `rejectsim/stages.py`. A slider alone does not change results.
3. Add its `slider(...)` line to `app.py`.

**Adding a new wear gauge to the Live plant**

1. Add a row to the `HEALTH` table in `plantviz/payload.py` (column to read, label, unit and the
   config path of its limit).
2. To also change how the unit looks, add a branch for it in `healthFx` in
   `plantviz/web/js/scene.js` and tag the element to recolour with `class="hl"` in
   `plantviz/web/js/units.js`.

**Rearranging the plant**

All unit positions and pipe routes are in `plantviz/web/js/layout.js`. Rendering code does not
need to change.

## Replacing placeholders with real data

Edit `config/defaults.yaml`. Every note starting with ASSUMPTION is a placeholder. Derived values
(reject TDS, hardness, flows) are computed, not typed, so keep recovery, rejection and feed quality
consistent instead of overriding reject values. Out-of-range values give warnings; impossible ones
(recovery >= 0.95, fractions outside 0 to 1, inconsistent pump levels, non-monotonic UV curve)
raise an error.

## Known simplifications

- Backwash water is an amortised percentage loss, not a discrete shutdown.
- Removal percentages are fixed per stage (with floors, loading and flow effects where noted); they
  are not mechanistic filtration models.
- UV uses a placeholder bacteria dose-response curve; viruses are not modelled.
- No hydraulics (pipe friction, pump curves) and no cleaning-chemical effluent.
- Bacterial regrowth in storage is a pure assumption.
- The Live plant is a visual encoding of the model output. It adds no physics of its own, and its
  colours are exaggerated for visibility.

## Requirements

Python 3 with `numpy`, `pandas`, `matplotlib`, `pyyaml`, `streamlit` and `pytest` (see
`requirements.txt`). The Live plant uses no extra Python or JavaScript packages.

## Deploying on Streamlit Community Cloud

Commit the whole repository, including the `plantviz/` folder with its `web/` subfolder, because
the visual loads its HTML, CSS and JavaScript from those files at runtime. Point the app at
`app.py`.

## Screenshots

Overview
<img width="1916" height="917" alt="image" src="https://github.com/user-attachments/assets/c6001cdb-373f-4033-9874-77730cdf4d42" />

Live plant
<img width="1917" height="915" alt="image" src="https://github.com/user-attachments/assets/33d4d4c4-b48d-4c06-87a1-6d37a91824c2" />

Per-stage quality
<img width="1917" height="912" alt="image" src="https://github.com/user-attachments/assets/558a708e-9de9-4a2f-8b5d-8c70dff79be5" />

Time-based
<img width="1916" height="911" alt="image" src="https://github.com/user-attachments/assets/61f2df50-28f7-4d4b-86bd-4bce67a17022" />

Sensitivity
<img width="1917" height="912" alt="image" src="https://github.com/user-attachments/assets/5e4859f7-ce6b-4752-b13f-8ba0d1e3bf61" />

Parameters
<img width="1917" height="913" alt="image" src="https://github.com/user-attachments/assets/65ddcfa2-710a-40bf-81a4-6273c1fa97bc" />
