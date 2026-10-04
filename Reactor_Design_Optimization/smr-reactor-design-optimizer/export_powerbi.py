"""
Export Power BI-ready CSVs from the LOCA safety / layered cladding app.

HOW TO RUN (from the folder that contains the `safety/` package, same place you run Streamlit):
    python export_powerbi.py
    python export_powerbi.py --burnup 50 --min-coping 0 --response-min 30 --h-steam 5

Output: ./powerbi_csv/*.csv  (UTF-8, one header row, no index, tidy "long" tables)
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from safety import data as D                                   # noqa: E402
from safety.data import v                                      # noqa: E402
from safety.rod import Design, make_layers, FAMILIES           # noqa: E402
from safety.loca import simulate_batch                         # noqa: E402
from safety.explore import (evaluate, build_grid, rank, best_per_family,   # noqa: E402
                            pellet_sweep, tornado)

ap = argparse.ArgumentParser()
ap.add_argument("--burnup", type=float, default=50.0)
ap.add_argument("--min-coping", type=float, default=0.0)
ap.add_argument("--response-min", type=float, default=float(v(D.LOCA, "response_min")))
ap.add_argument("--h-steam", type=float, default=float(v(D.LOCA, "h_steam_W_m2K")))
ap.add_argument("--objective", default="cost", choices=["cost", "safety", "balanced"])
ap.add_argument("--out", default="powerbi_csv")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)


def save(df, name):
    path = os.path.join(a.out, name)
    df.to_csv(path, index=False)
    print(f"wrote {path}  ({len(df)} rows)")


# ======================================================================================
# PART A - INPUT DATA (straight from safety/data.py)
# ======================================================================================
rows = []
for group, table in (("Plant", D.PLANT), ("Fuel", D.FUEL), ("Economics", D.ECON), ("Neutronics", D.NEUTRONICS),
                     ("LOCA", D.LOCA), ("Mechanical", D.MECH)):
    for k, (val, src, status, note) in table.items():
        rows.append(dict(group=group, parameter=k, value=val, status=status, note=note,
                         source=D.SOURCES.get(src, ("", ""))[0], link=D.SOURCES.get(src, ("", ""))[1]))
save(pd.DataFrame(rows), "01_parameters.csv")

mat_rows, comp_rows, src_rows = [], [], []
for name, m in D.MATERIALS.items():
    mat_rows.append(dict(material=name, **{k: m[k] for k in (
        "rho", "cp", "k", "E_GPa", "nu", "cost_usd_kg", "rate_mult", "q_per_mol_O", "lost_C", "melt_C",
        "eol_corrosion_mm")}))
    for el, frac in m["comp_wt"].items():
        comp_rows.append(dict(material=name, element=el, weight_fraction=frac))
    for prop, (src, status) in m.get("src", {}).items():
        src_rows.append(dict(material=name, property=prop, status=status, source=D.SOURCES[src][0]))
save(pd.DataFrame(mat_rows).rename(columns={
    "rho": "density_kg_m3", "cp": "specific_heat_J_kgK", "k": "conductivity_W_mK", "E_GPa": "youngs_modulus_GPa",
    "nu": "poisson_ratio", "rate_mult": "oxidation_rate_vs_zircaloy", "q_per_mol_O": "heat_per_mol_O_J",
    "lost_C": "protection_lost_C", "melt_C": "melt_C", "eol_corrosion_mm": "end_of_life_corrosion_mm"}),
    "02_materials.csv")
save(pd.DataFrame(comp_rows), "03_material_composition.csv")
save(pd.DataFrame(src_rows), "04_material_property_sources.csv")

save(pd.DataFrame([dict(layout=n, rods=L["rods"], effective_rods=L["effective_rods"], pitch_mm=L["pitch_mm"],
                        ref_pellet_mm=L["ref_pellet_mm"], ref_gap_mm=L["ref_gap_mm"], ref_wall_mm=L["ref_wall_mm"],
                        notes=L["notes"]) for n, L in D.LAYOUTS.items()]), "05_bundle_layouts.csv")
save(pd.DataFrame([dict(element=e, atomic_mass=A, thermal_xs_barns=s, resonance_integral_barns=ri)
                   for e, (A, s, ri) in D.ELEMENTS.items()]), "06_element_cross_sections.csv")
save(pd.DataFrame([dict(layer_a=a_, layer_b=b_, failure_temp_C=val, status=st, note=note)
                   for (a_, b_), (val, src, st, note) in D.INTERFACE_LIMITS_C.items()]), "07_interface_limits.csv")

# ======================================================================================
# PART B - MODEL RESULTS (uses the same functions the Streamlit page calls)
# ======================================================================================
L0 = D.LAYOUTS[D.REFERENCE_LAYOUT]
ref = Design("Zircaloy-2", make_layers("Zircaloy-2", L0["ref_wall_mm"]), L0["ref_pellet_mm"], L0["ref_gap_mm"],
             D.REFERENCE_LAYOUT, a.burnup, "Today's GNF2-class rod")

grid = build_grid(burnup=a.burnup)
space = evaluate(grid, min_coping=a.min_coping, response_min=a.response_min, h_steam=a.h_steam,
                 run_loca_on="fast")
dur = space.attrs.get("duration_min", 90)
h2_limit = space.attrs.get("h2_limit_kg", np.nan)


def flatten(df):
    """Keep only scalar columns and turn the pass/fail dictionaries into 0/1 columns."""
    out = df.drop(columns=[c for c in ("design", "cost", "checks", "safety_checks") if c in df.columns]).copy()
    for col in ("checks", "safety_checks"):
        if col in df.columns:
            exp = pd.DataFrame(list(df[col])).astype(int).add_prefix("pass_")
            exp.index = out.index
            out = pd.concat([out, exp], axis=1)
    return out


flat = flatten(space).drop(columns=["design_id"], errors="ignore")
flat.insert(0, "design_id", range(1, len(flat) + 1))
flat["duration_min_simulated"] = dur
flat["h2_limit_kg"] = h2_limit
save(flat, "10_design_space.csv")                       # every design tested

ranked = rank(space, a.objective)
rk = flatten(ranked).drop(columns=["rank"], errors="ignore")
rk.insert(0, "rank", range(1, len(rk) + 1))
save(rk.head(100), "11_top_100_ranked_designs.csv")

bpf = best_per_family(space, a.objective)
save(flatten(bpf), "12_best_design_per_cladding.csv")

fails = space.loc[~space["feasible"], "failed_checks"].str.split(", ").explode().value_counts()
save(fails.rename_axis("failed_limit").reset_index(name="designs_failing"), "13_why_designs_failed.csv")

# ---- cost breakdown ($/MWh) for today's rod + best of each cladding
ev_ref = evaluate([ref], min_coping=a.min_coping, response_min=a.response_min, h_steam=a.h_steam)
picks = [("Today's rod", ev_ref.iloc[0], ref)] + [(r["family"], r, r["design"]) for _, r in bpf.iterrows()]
cb = []
for label, row, d in picks:
    mwh = d.burnup * 24 * v(D.PLANT, "net_efficiency")          # MWh(e) per kgU
    for item, usd in row["cost"]["breakdown_usd_per_kgU"].items():
        cb.append(dict(design=label, cost_item=item, usd_per_kgU=usd, usd_per_MWh_e=usd / mwh))
save(pd.DataFrame(cb), "14_cost_breakdown.csv")

# ---- LOCA time curves (temperature + hydrogen vs time) for today's rod + best of each cladding
designs = [d for _, _, d in picks]
curves = simulate_batch(designs, response_min=a.response_min, h_steam=a.h_steam)
cv = []
for i, (label, _, _) in enumerate(picks):
    cv.append(pd.DataFrame(dict(design=label, minutes=curves["t_min"], hottest_clad_temp_C=curves["T_hot"][i],
                                core_hydrogen_kg=curves["h2_kg"][i])))
cv = pd.concat(cv, ignore_index=True)
cv["temp_limit_C"] = float(v(D.LOCA, "pct_limit"))
cv["h2_limit_kg"] = h2_limit
cv["cooling_restored_min"] = a.response_min
save(cv, "15_loca_curves.csv")

# ---- pellet-size sweep and layer-thickness map for the best layered design
lay_rank = rank(space[space.family == "Layered Zr/Mo/FeCrAl"], a.objective)
if len(lay_rank):
    dl = lay_rank.iloc[0]["design"]
    pel = np.round(np.arange(dl.pellet_mm - 0.8, dl.pellet_mm + 0.81, 0.05), 3)
    sw = pellet_sweep(dl, pel, min_coping=a.min_coping, response_min=a.response_min, h_steam=a.h_steam)
    save(flatten(sw), "16_pellet_sweep_layered.csv")

    zr_t = dict(dl.layers)["Zircaloy-2"]
    mos = np.round(np.arange(0.10, 0.46, 0.05), 3)
    fes = np.round(np.arange(0.02, 0.17, 0.02), 3)
    combos = [(m_, f_) for m_ in mos for f_ in fes]
    gd = [Design(dl.family, make_layers(dl.family, zr_mm=zr_t, mo_mm=m_, fe_mm=f_), dl.pellet_mm, dl.gap_mm,
                 dl.layout, dl.burnup) for m_, f_ in combos]
    hm = flatten(evaluate(gd, a.min_coping, a.response_min, a.h_steam)).drop(
        columns=["mo_mm", "fecral_mm", "inner_zr_mm"], errors="ignore")
    hm.insert(0, "fecral_mm", [f_ for _, f_ in combos])
    hm.insert(0, "mo_mm", [m_ for m_, _ in combos])
    hm.insert(2, "inner_zr_mm", zr_t)
    save(hm, "17_layer_thickness_map.csv")

# ---- tornado (sensitivity) for each cladding's best design
tor_all = []
for _, r in bpf.iterrows():
    tor, base = tornado(r["design"], min_coping=a.min_coping)
    t = tor.copy().drop(columns=["design"], errors="ignore")
    t.insert(0, "design", r["family"])
    t["base_cost_usd_MWh_e"] = base.usd_per_MWh_e
    t["base_coping_min"] = base.coping_plot_min
    tor_all.append(t)
if tor_all:
    save(pd.concat(tor_all, ignore_index=True), "18_sensitivity_tornado.csv")

# ---- the settings used for this export (handy as a Power BI "slicer" note)
save(pd.DataFrame([dict(burnup_GWd_t=a.burnup, min_coping_min=a.min_coping, response_min=a.response_min,
                        h_steam_W_m2K=a.h_steam, ranking_objective=a.objective, sim_duration_min=dur)]),
     "00_scenario_settings.csv")
print("\nDone. In Power BI: Get Data > Text/CSV, select the files in", a.out)