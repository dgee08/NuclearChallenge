# LOCA Safety & New Layered Cladding: extension to the SMR design tool

The starter tool measures **cost and fuel lifetime only**. This extension adds **loss-of-coolant
(LOCA) safety limits** and a **new layered cladding** (Zircaloy inside → molybdenum → FeCrAl
outside). It answers:

> Which fuel-rod design change, a protective coating/new cladding or a change in rod geometry,
> gives the most safety time and the least hydrogen for the lowest cost, while still meeting all
> temperature, cost and fuel-lifetime limits?

## What was added (nothing in the original `app.py` / `model.py` was changed)

| File | What it does |
|---|---|
| `pages/1_LOCA_Safety_and_New_Cladding.py` | New Streamlit page (appears in the left sidebar) |
| `safety/data.py` | **Every number used, with source and status.** Edit here |
| `safety/rod.py` | Geometry, neutron penalty → enrichment, fuel-cycle cost, collapse strength, fuel temperature, moderation and flow checks |
| `safety/loca.py` | Loss-of-coolant transient (rods in steam) for many designs at once: temperature, oxidation heat, hydrogen, melting |
| `safety/explore.py` | Design-space search, ranking, best design per cladding, pellet sweep, tornado |
| `requirements.txt` | Adds `plotly` (the starter app needed it but did not list it) |

## Run it (Codespace / Linux)

```bash
cd "/workspaces/F26-NuclearIC/Reactor Design Optimization/smr-reactor-design-optimizer"
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```
Then pick **"LOCA Safety and New Cladding"** in the left sidebar.

## The page

1. **Your design: cost vs safety.** Choose a cladding (Zircaloy-2, Cr-coated Zr, FeCrAl, layered
   Zr/Mo/FeCrAl), layer thicknesses, pellet diameter and bundle layout. Cost and LOCA safety
   appear side by side against today's rod, with a pass/fail table for every limit and the
   temperature and hydrogen curves.
2. **Design-space exploration.** About 3,000 designs (pellet diameter × wall/layer thickness ×
   cladding × 10x10 or 11x11 layout) are tested. Designs breaking a limit are discarded, the rest
   are ranked. Includes a cost vs coping-time chart with one colour per cladding.
3. **Optimized Zircaloy vs new layered.** The best Zircaloy rod and the best layered rod side by
   side: dimensions, to-scale cross-sections, cost breakdown, a pellet-diameter sweep and a
   Mo × FeCrAl thickness map.
4. **Sensitivity (tornado).** Each input is changed ±10% to show what moves cost and coping time
   the most.
5. **Assumptions & sources.** Every number, its status (sourced / derived / assumption) and a link.

## Limits applied to every design

| Limit | Value | Where |
|---|---|---|
| Enrichment | ≤ 5 wt% U-235 | `NEUTRONICS.max_enrichment_wt` |
| Peak-rod burnup | ≤ 62 GWd/t | `NEUTRONICS.max_peak_rod_burnup` |
| Fuel centre temperature (hot spot, 120% power) | < 1800 °C | `FUEL.max_centerline_C` |
| Elastic collapse safety factor (end of life) | ≥ 2 | `MECH.collapse_sf_min` |
| Water-to-fuel ratio (void coefficient proxy) | within ±10% of today | `MECH.moderation_band` |
| Coolant flow area (natural circulation) | ≥ 95% of today | `MECH.flow_area_min` |
| Hydrogen produced before cooling returns | ≤ 1% of all reference Zr reacting (~4.5 kg) | `LOCA.h2_limit_frac` |
| No melting before cooling returns | time set in the sidebar (default 30 min) | `LOCA.response_min` |
| Minimum coping time | sidebar slider | n/a |

## How the models work

- **Enrichment.** Linear reactivity model, `e = 0.70 + B / 14.175`, plus a cladding absorption
  penalty proportional to (absorption cross section × cladding area) per unit fuel area. It is
  calibrated so that 0.385 mm FeCrAl needs +0.6 wt% (the ORNL range is 0.4–0.8).
- **Fuel cost ($/MWh e).** Uranium (U3O8 price × feed), conversion, SWU (standard value
  function, 0.25% tails), fabrication and back-end (INL WIT values from the starter tool), and
  cladding hardware (layer mass × $/kg), divided by burnup × 24 MWh/kg × efficiency.
- **LOCA.** 5 power groups × 8 axial slices. Heat balance: decay heat + oxidation heat − steam
  cooling. Oxidation uses the Cathcart–Pawel parabolic law, multiplied by the rate factor of
  whichever layer faces the steam. The outer layer protects until it melts or forms a eutectic
  with the layer below, then the next layer is exposed. The rod loses its shape at its failure
  temperature. Hydrogen is 1 mol H₂ per mol of oxygen picked up.
- **Layered cladding rules.** FeCrAl protects until **1453 °C** (first liquid in the Fe–Mo
  system), then molybdenum faces steam (~100× slower than Zr, little heat). The rod is judged to
  fail at **1551 °C** (Zr–Mo eutectic at the inner liner, conservative). Switch to Mo melting
  (2623 °C) with `LAYERED_FAIL_MODE` in `data.py`.
- **Collapse.** Ring buckling `p = 3·D/r³`, where D is the bending stiffness of the layered wall
  (each layer with its own Young's modulus) after end-of-life corrosion of the outer layer.

## Results with the current numbers (default settings)

| Best design per cladding (lowest cost, all limits met) | $/MWh(e) | Coping to 1204 °C | Melts | H₂ by 30 min |
|---|---|---|---|---|
| Zircaloy-2: 11x11, pellet 8.27 mm, wall 0.45 mm | 12.35 | 25.8 min | 32.6 min | 2.5 kg |
| Cr-coated Zr: 10x10, pellet 9.20, Zr 0.40 + Cr 0.015 | 12.40 | 29.9 min | 42.4 min | 0.37 kg |
| FeCrAl: 11x11, pellet 8.45, wall 0.30 | 13.64 | 37.9 min | not in 90 min | 0.01 kg |
| **Layered: 10x10, pellet 9.10, Zr 0.10 / Mo 0.15 / FeCrAl 0.10** | **13.93** | **29.9 min** | **not in 90 min** | **0.01 kg** |
| Today's rod: 10x10, pellet 8.76, Zr 0.66 | 12.48 | 23.7 min | 30.3 min | 4.0 kg |

What this says, honestly:

- **The layered cladding is much safer than Zircaloy.** It makes almost no hydrogen and does not
  melt within 90 minutes, compared with Zircaloy melting at ~30 minutes and making ~36 kg of
  hydrogen.
- **It is not the cheapest.** It costs about **+$1.6/MWh (~$4M per year per reactor)** more than
  the best Zircaloy rod. Most of that is extra enrichment, because molybdenum absorbs neutrons
  (especially in its resonances).
- **Geometry alone (best Zircaloy) is cheap but barely safer**: +2 minutes of coping, and it
  still melts and makes hydrogen.
- **What-if results:**
  - If cooling takes 60 minutes, **every Zircaloy design fails** and only coated or new
    claddings remain.
  - If molybdenum's resonance absorption is lower than assumed (resonance weight 0), the layered
    design becomes **cheaper than FeCrAl** (13.42 vs 13.65 $/MWh). That's the key number to
    research.
  - The layered design's peak temperature (~1430 °C) sits just below the 1453 °C Fe–Mo limit,
    so its margin depends on that interface.

## Numbers to research first (status "assumption")

1. Molybdenum neutron penalty (resonance weighting): has the biggest effect on the layered cost.
2. Molybdenum and FeCrAl fabricated tube cost per kg ($1,500 and $500 assumed).
3. Steam cooling coefficient of uncovered rods (5 W/m²K): has the biggest effect on coping time.
4. Real GNF2 and ATRIUM 11 rod dimensions (proprietary; public estimates used).
5. FeCrAl and Mo steam-oxidation rate factors (0.002 and 0.01 × Zircaloy).
6. Whether the Zr–Mo eutectic (1551 °C) or Mo melting should define layered failure.

## Sources

See the **Assumptions & sources** tab, or `SOURCES` in `safety/data.py`. Main references:

- GE Vernova, BWRX-300 General Description
- CNSC CMD24-H3 GNF2 fuel qualification for the BWRX-300
- ORNL/TM-2021/1961 (FeCrAl enrichment penalty)
- ORNL/TM-2017/186 (FeCrAl handbook)
- PNNL-30445 (FeCrAl failure phenomena)
- Cheng et al., EPJ-N 2016 (Mo-alloy cladding)
- CompuTherm Fe–Mo and Metall. Trans. Zr–Mo phase diagrams
- npj Materials Degradation (Cr-coated Zr)
- Cathcart–Pawel (ORNL Zircaloy-2 steam study)
- 10 CFR 50.46
- Cameco and TradeTech/UxC fuel prices (Aug–Sep 2026)
- NIST neutron cross sections
- INL WIT cost basis (from the starter tool)

Educational model only, not for real design or licensing.
