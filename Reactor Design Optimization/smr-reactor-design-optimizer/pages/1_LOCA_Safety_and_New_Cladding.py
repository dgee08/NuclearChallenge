"""
LOCA safety + new layered cladding page.

Adds what the starter tool is missing: safety limits. Cost and loss-of-coolant safety
are shown side by side, and a design-space search ranks claddings and geometries.
All inputs and their sources are in safety/data.py.
"""
import os
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from safety import data as D                                          # noqa: E402
from safety.data import v                                             # noqa: E402
from safety.rod import Design, make_layers, FAMILIES, FAMILY_COLORS   # noqa: E402
from safety.loca import simulate_batch                                # noqa: E402
from safety.explore import (evaluate, build_grid, rank, best_per_family,   # noqa: E402
                            pellet_sweep, tornado)

st.set_page_config(page_title="Claddr: LOCA Safety & New Cladding", layout="wide")
st.session_state["_chart_n"] = 0

GRID_COLOR = "rgba(128,128,128,0.25)"
LIMIT_COLOR = "#8a8984"


def show(fig, height=None, h_legend=True):
    fig.update_layout(margin=dict(l=10, r=10, t=60, b=10), height=height)
    if h_legend:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    fig.update_xaxes(gridcolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR)
    st.session_state["_chart_n"] = st.session_state.get("_chart_n", 0) + 1
    key = f"chart_{st.session_state['_chart_n']}"
    try:
        st.plotly_chart(fig, width="stretch", key=key)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=key)


def money(x):
    return f"${x / 1e6:,.2f}M" if abs(x) >= 1e6 else f"${x:,.0f}"


def fmt_min(x, dur):
    return f">{dur:.0f} min" if (x is None or np.isnan(x)) else f"{x:.1f} min"


# ------------------------------------------------------------------ cached runners
@st.cache_data(show_spinner=False)
def run_eval(designs, min_coping, response_min, h_steam):
    return evaluate(list(designs), min_coping=min_coping, response_min=response_min, h_steam=h_steam)


@st.cache_data(show_spinner=False)
def run_curves(designs, response_min, h_steam):
    return simulate_batch(list(designs), response_min=response_min, h_steam=h_steam)


@st.cache_data(show_spinner=False)
def run_space(burnup, min_coping, response_min, h_steam):
    g = build_grid(burnup=burnup)
    return evaluate(g, min_coping=min_coping, response_min=response_min, h_steam=h_steam,
                    run_loca_on="fast"), len(g)


@st.cache_data(show_spinner=False)
def run_tornado(design, min_coping):
    return tornado(design, min_coping=min_coping)


def reference_design(burnup):
    L = D.LAYOUTS[D.REFERENCE_LAYOUT]
    return Design("Zircaloy-2", make_layers("Zircaloy-2", L["ref_wall_mm"]), L["ref_pellet_mm"],
                  L["ref_gap_mm"], D.REFERENCE_LAYOUT, burnup, "Today's GNF2-class rod")


# ------------------------------------------------------------------ drawing
def rod_figure(d, title=""):
    L = D.LAYOUTS[d.layout]
    p = L["pitch_mm"]
    fig = go.Figure()
    fig.add_shape(type="rect", x0=-p / 2, y0=-p / 2, x1=p / 2, y1=p / 2,
                  fillcolor="rgba(91,155,213,0.18)", line=dict(color="rgba(91,155,213,0.6)"))
    rings = [(m, r1 * 1000, r2 * 1000) for m, r1, r2 in d.radii_m()]
    for m, a, b in reversed(rings):
        fig.add_shape(type="circle", x0=-b, y0=-b, x1=b, y1=b,
                      fillcolor=D.MATERIALS[m]["color"], line=dict(width=0))
    r_gap = rings[0][1]
    fig.add_shape(type="circle", x0=-r_gap, y0=-r_gap, x1=r_gap, y1=r_gap,
                  fillcolor="#f2f2f2", line=dict(width=0))
    rp = d.pellet_mm / 2
    fig.add_shape(type="circle", x0=-rp, y0=-rp, x1=rp, y1=rp, fillcolor="#3a3a3a", line=dict(width=0))
    # legend entries
    for name, col in [("UO2 pellet", "#3a3a3a"), ("Gap", "#cccccc")] + \
                     [(m, D.MATERIALS[m]["color"]) for m, _, _ in rings] + [("Water", "rgba(91,155,213,0.5)")]:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=name,
                                 marker=dict(size=10, color=col, symbol="square")))
    ext = max(L2["pitch_mm"] for L2 in D.LAYOUTS.values()) / 2 + 0.3
    fig.update_xaxes(range=[-ext, ext], showgrid=False, zeroline=False, title="mm")
    fig.update_yaxes(range=[-ext, ext], showgrid=False, zeroline=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(title=title or "Rod cross-section (to scale)", height=360,
                      margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="v", x=1.02, y=0.5, yanchor="middle"))
    return fig


def wall_figure(d):
    """Wall layers magnified (the rings are too thin to see at full scale)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(y=["wall"], x=[d.gap_mm], orientation="h", name="Gap", marker_color="#cccccc",
                         hovertemplate="Gap %{x:.3f} mm<extra></extra>"))
    for m, t in d.layers:
        fig.add_trace(go.Bar(y=["wall"], x=[t], orientation="h", name=m,
                             marker_color=D.MATERIALS[m]["color"], text=[f"{m.split(' ')[0]} {t:.2f}"],
                             textposition="inside", insidetextanchor="middle",
                             hovertemplate=f"{m} %{{x:.3f}} mm<extra></extra>"))
    fig.update_layout(barmode="stack", height=150, title="Wall layers, inner → outer (magnified, mm)",
                      xaxis_title="mm from pellet surface", yaxis=dict(showticklabels=False),
                      margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
    return fig


def layer_editor(prefix, default_family="Layered Zr/Mo/FeCrAl"):
    fam = st.selectbox("Cladding", FAMILIES, index=FAMILIES.index(default_family), key=prefix + "fam")
    if fam in ("Zircaloy-2", "FeCrAl"):
        w = st.number_input("Wall thickness (mm)", 0.10, 1.20, 0.66 if fam == "Zircaloy-2" else 0.35,
                            0.01, key=prefix + "w")
        layers = make_layers(fam, wall_mm=w)
    elif fam == "Cr-coated Zr":
        w = st.number_input("Zircaloy wall (mm)", 0.10, 1.20, 0.66, 0.01, key=prefix + "w")
        cr = st.number_input("Chromium coating (mm)", 0.005, 0.10, 0.015, 0.005, format="%.3f", key=prefix + "cr")
        layers = make_layers(fam, wall_mm=w, cr_mm=cr)
    else:
        c1, c2, c3 = st.columns(3)
        zr = c1.number_input("Inner Zircaloy (mm)", 0.01, 0.50, 0.10, 0.01, key=prefix + "zr")
        mo = c2.number_input("Middle Mo (mm)", 0.05, 0.80, 0.15, 0.01, key=prefix + "mo")
        fe = c3.number_input("Outer FeCrAl (mm)", 0.01, 0.50, 0.10, 0.01, key=prefix + "fe")
        layers = make_layers(fam, zr_mm=zr, mo_mm=mo, fe_mm=fe)
    return fam, layers


# ------------------------------------------------------------------ sidebar: scenario
st.sidebar.header("LOCA scenario")
h_steam = st.sidebar.slider("Steam cooling of uncovered rods (W/m²K)", 2.0, 10.0,
                            float(v(D.LOCA, "h_steam_W_m2K")), 0.5,
                            help="Biggest uncertainty in the safety model. See Assumptions tab.")
response_min = st.sidebar.slider("Time to restore cooling (min)", 10, 60, int(v(D.LOCA, "response_min")), 5,
                                 help="Hydrogen is counted up to this time; melting before it fails the design.")
min_coping = st.sidebar.slider("Minimum coping time required (min)", 0, 45, 0, 1)
burnup = st.sidebar.slider("Target discharge burnup (GWd/t)", 40.0, 60.0, 50.0, 1.0)
objective = st.sidebar.radio("Rank designs by", ["cost", "safety", "balanced"],
                             format_func={"cost": "Lowest cost (safe designs only)",
                                          "safety": "Longest coping time",
                                          "balanced": "Balanced cost + safety"}.get)
st.sidebar.caption(f"Layered cladding judged to fail at: **{D.LAYERED_FAIL_MODE}** (edit in safety/data.py)")

# ------------------------------------------------------------------ header
st.title("Claddr: LOCA Safety & Layered Cladding")
st.markdown(
    "**Problem:** When fuel rods lose cooling, zirconium cladding reacts with steam, heats itself up, "
    "melts and releases explosive hydrogen. The provided starter tool only measures **cost and fuel lifetime**. "
    "Our app **Claddr** adds safety limits and compares today's Zircaloy rod with a **new layered cladding**: "
    "Zircaloy inside, molybdenum in the middle, FeCrAl outside."
)
st.caption("Educational model for the Nuclear Innovation Challenge. Every number and its source is in the "
           "**Assumptions & sources** tab and in `safety/data.py`.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["1 · Your design: cost vs safety", "2 · Design-space exploration",
                                        "3 · Optimized Zircaloy vs new layered", "4 · Sensitivity (tornado)",
                                        "5 · Assumptions & sources"])

ref = reference_design(burnup)

# ================================================================== TAB 1
with tab1:
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Design inputs")
        fam, layers = layer_editor("t1")
        lay = st.selectbox("Bundle layout", list(D.LAYOUTS), key="t1lay")
        Lr = D.LAYOUTS[lay]
        default_pellet = round(Lr["ref_pellet_mm"] * (9.10 / 8.76), 2) if fam == "Layered Zr/Mo/FeCrAl" \
            else float(Lr["ref_pellet_mm"])
        pellet = st.number_input("Pellet diameter (mm)", 6.5, 10.5, default_pellet, 0.05,
                                 key=f"t1pel_{fam}_{lay}")
        gap = st.number_input("Pellet-cladding gap (mm)", 0.03, 0.20, float(Lr["ref_gap_mm"]), 0.01)
        design = Design(fam, layers, pellet, gap, lay, burnup, "Your design")
    with right:
        show(rod_figure(design), 360, h_legend=False)
        show(wall_figure(design), 160, h_legend=False)

    res = run_eval((ref, design), min_coping, response_min, h_steam)
    r0, r1 = res.iloc[0], res.iloc[1]
    dur = res.attrs.get("duration_min", 90)
    lim = res.attrs.get("h2_limit_kg", 4.5)

    st.subheader("Cost and safety, side by side")
    st.caption(f"Compared with today's rod: {ref.describe()}")
    cc, cs = st.columns(2)
    with cc:
        st.markdown("#### 💲 Cost")
        a, b = st.columns(2)
        a.metric("Fuel-cycle cost", f"${r1.usd_per_MWh_e:.2f}/MWh",
                 f"{r1.usd_per_MWh_e - r0.usd_per_MWh_e:+.2f}", delta_color="inverse")
        b.metric("Annual fuel cost (1 unit)", money(r1.annual_fuel_cost_usd),
                 money(r1.annual_fuel_cost_usd - r0.annual_fuel_cost_usd), delta_color="inverse")
        a.metric("Enrichment needed", f"{r1.enrichment_wt:.2f} wt%",
                 f"{r1.enrichment_wt - r0.enrichment_wt:+.2f} (neutron penalty)", delta_color="inverse")
        b.metric("Rod outer diameter", f"{r1.od_mm:.2f} mm", f"{r1.od_mm - r0.od_mm:+.2f}", delta_color="off")
    with cs:
        st.markdown("#### 🛡️ LOCA safety")
        a, b = st.columns(2)
        cop1 = r1.coping_plot_min
        a.metric("Coping time (to 1204 °C)", fmt_min(r1.coping_min, dur),
                 f"{cop1 - r0.coping_plot_min:+.1f} min")
        b.metric("Time to melt / lose shape", fmt_min(r1.melt_min, dur),
                 f"{r1.melt_plot_min - r0.melt_plot_min:+.1f} min")
        a.metric(f"Hydrogen by {response_min} min", f"{r1.h2_at_response_kg:.2f} kg",
                 f"{r1.h2_at_response_kg - r0.h2_at_response_kg:+.2f} kg (limit {lim:.1f})", delta_color="inverse")
        b.metric(f"Hydrogen after {dur:.0f} min", f"{r1.h2_end_kg:.1f} kg",
                 f"{r1.h2_end_kg - r0.h2_end_kg:+.1f} kg", delta_color="inverse")

    st.markdown("#### Limits check")
    checks = {**r1["checks"], **r1["safety_checks"]}
    chk = pd.DataFrame({"Limit": list(checks), "Your design": ["✅ pass" if x else "❌ fail" for x in checks.values()],
                        "Today's rod": ["✅ pass" if x else "❌ fail"
                                        for x in {**r0["checks"], **r0["safety_checks"]}.values()]})
    vals = pd.DataFrame({
        "Value": [f"{r1.enrichment_wt:.2f} wt%", f"{r1.peak_rod_burnup:.1f} GWd/t", f"{r1.centerline_C:.0f} °C",
                  f"{r1.collapse_sf:.2f}", f"{(r1.moderation_ratio - 1) * 100:+.1f}%", f"{r1.flow_ratio * 100:.0f}%",
                  "min " + f"{min(t for _, t in design.layers):.3f} mm",
                  f"{r1.h2_at_response_kg:.2f} / {lim:.1f} kg", fmt_min(r1.melt_min, dur), fmt_min(r1.coping_min, dur)]})
    st.dataframe(pd.concat([chk, vals], axis=1), hide_index=True)

    curves = run_curves((ref, design), response_min, h_steam)
    f1, f2 = st.columns(2)
    with f1:
        fig = go.Figure()
        for i, (nm, col) in enumerate([("Today's Zircaloy rod", FAMILY_COLORS["Zircaloy-2"]),
                                       ("Your design", FAMILY_COLORS[fam])]):
            fig.add_trace(go.Scatter(x=curves["t_min"], y=curves["T_hot"][i], name=nm,
                                     line=dict(color=col, width=2, dash="dot" if i == 0 else "solid")))
        fig.add_hline(y=1204, line=dict(color=LIMIT_COLOR, dash="dash", width=1),
                      annotation_text="1204 °C limit", annotation_position="top left")
        fig.add_vline(x=response_min, line=dict(color=LIMIT_COLOR, dash="dot", width=1),
                      annotation_text="cooling restored", annotation_position="bottom right")
        fig.update_layout(title="Hottest cladding temperature, no cooling", xaxis_title="Minutes after rods uncover",
                          yaxis_title="°C")
        show(fig, 380)
    with f2:
        fig = go.Figure()
        for i, (nm, col) in enumerate([("Today's Zircaloy rod", FAMILY_COLORS["Zircaloy-2"]),
                                       ("Your design", FAMILY_COLORS[fam])]):
            fig.add_trace(go.Scatter(x=curves["t_min"], y=curves["h2_kg"][i], name=nm,
                                     line=dict(color=col, width=2, dash="dot" if i == 0 else "solid")))
        fig.add_hline(y=lim, line=dict(color=LIMIT_COLOR, dash="dash", width=1),
                      annotation_text=f"{lim:.1f} kg limit", annotation_position="top left")
        fig.update_layout(title="Hydrogen produced in the whole core", xaxis_title="Minutes after rods uncover",
                          yaxis_title="kg H₂")
        show(fig, 380)

# ================================================================== TAB 2
with tab2:
    st.subheader("Automatically test and rank thousands of designs")
    st.markdown("Every combination of **pellet diameter × wall/layer thickness × cladding × bundle layout** is "
                "checked against all limits. Designs that pass the quick checks get the full LOCA transient.")
    with st.spinner("Testing designs..."):
        space, n_total = run_space(burnup, min_coping, response_min, h_steam)
    feas = space[space["feasible"]]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Designs tested", f"{n_total:,}")
    m2.metric("Pass quick checks", f"{int(space['fast_ok'].sum()):,}")
    m3.metric("Pass ALL limits", f"{len(feas):,}")
    m4.metric("Cheapest safe design", f"${feas.usd_per_MWh_e.min():.2f}/MWh" if len(feas) else "none")

    show_bad = st.checkbox("Also show designs that pass quick checks but fail a safety limit", value=True)
    fig = go.Figure()
    for famx in FAMILIES:
        sub = space[(space.family == famx) & space.feasible]
        fig.add_trace(go.Scatter(
            x=sub.coping_plot_min, y=sub.usd_per_MWh_e, mode="markers", name=famx,
            marker=dict(color=FAMILY_COLORS[famx], size=8, line=dict(color="white", width=1)),
            customdata=np.stack([sub.layers, sub.pellet_mm, sub.layout, sub.h2_at_response_kg], axis=-1)
            if len(sub) else None,
            hovertemplate="%{customdata[0]}<br>pellet %{customdata[1]} mm, %{customdata[2]}<br>"
                          "coping %{x:.1f} min, H2 %{customdata[3]:.2f} kg<br>$%{y:.2f}/MWh<extra></extra>"))
        if show_bad:
            bad = space[(space.family == famx) & space.fast_ok & ~space.safe_ok]
            if len(bad):
                fig.add_trace(go.Scatter(x=bad.coping_plot_min, y=bad.usd_per_MWh_e, mode="markers",
                                         name=f"{famx} (fails safety)", showlegend=False,
                                         marker=dict(color=FAMILY_COLORS[famx], size=7, symbol="x", opacity=0.35),
                                         hovertemplate="fails: %{text}<extra></extra>", text=bad.failed_checks))
    fig.add_trace(go.Scatter(x=[res.iloc[0].coping_plot_min], y=[res.iloc[0].usd_per_MWh_e], mode="markers",
                             name="Today's rod", marker=dict(symbol="star", size=16, color="#222")))
    fig.update_layout(title="Cost vs coping time (each dot = one safe design; x = fails a safety limit)",
                      xaxis_title="Coping time: minutes until 1204 °C (right = safer)",
                      yaxis_title="Fuel-cycle cost $/MWh(e) (down = cheaper)")
    show(fig, 520)

    st.markdown("#### Ranked safe designs")
    ranked = rank(space, objective)
    cols = ["rank", "family", "layout", "pellet_mm", "layers", "od_mm", "enrichment_wt", "usd_per_MWh_e",
            "coping_plot_min", "melt_plot_min", "h2_at_response_kg", "collapse_sf"]
    nice = {"pellet_mm": "Pellet (mm)", "layers": "Wall layers (mm)", "od_mm": "Rod OD (mm)",
            "enrichment_wt": "Enrich. (wt%)", "usd_per_MWh_e": "$/MWh(e)", "coping_plot_min": "Coping (min)",
            "melt_plot_min": "Melt (min)", "h2_at_response_kg": "H₂ (kg)", "collapse_sf": "Collapse SF"}
    st.dataframe(ranked[cols].head(20).rename(columns=nice).round(3), hide_index=True)
    st.markdown("#### Best design of each cladding type")
    bpf = best_per_family(space, objective)
    st.dataframe(bpf[cols[1:]].rename(columns=nice).round(3), hide_index=True)
    with st.expander("Why designs were thrown out"):
        fails = space.loc[~space.feasible, "failed_checks"].str.split(", ").explode().value_counts()
        st.dataframe(fails.rename("designs failing").to_frame())

# ================================================================== TAB 3
with tab3:
    st.subheader("Most optimized Zircaloy rod vs the new layered cladding")
    space, _ = run_space(burnup, min_coping, response_min, h_steam)
    bz = rank(space[space.family == "Zircaloy-2"], objective)
    bl = rank(space[space.family == "Layered Zr/Mo/FeCrAl"], objective)
    if not len(bz) or not len(bl):
        st.warning("No safe design found for one of the claddings with the current settings.")
    else:
        z, l = bz.iloc[0], bl.iloc[0]
        dz, dl = z["design"], l["design"]
        c1, c2 = st.columns(2)
        for col, row, d, name in ((c1, z, dz, "Optimized Zircaloy-2"), (c2, l, dl, "Optimized layered Zr/Mo/FeCrAl")):
            with col:
                st.markdown(f"#### {name}")
                st.markdown(f"**Pellet** {d.pellet_mm:.2f} mm · **rod OD** {d.od_mm:.2f} mm · **{d.layout}**  \n"
                            + "  \n".join(f"**{m}**: {t:.3f} mm" for m, t in d.layers)
                            + f"  \n**Total wall** {d.wall_mm:.3f} mm (cylindrical tube)")
                show(rod_figure(d, name), 340, h_legend=False)
                show(wall_figure(d), 160, h_legend=False)
        comp = pd.DataFrame({
            "Metric": ["Fuel-cycle cost ($/MWh e)", "Annual fuel cost (1 unit)", "Enrichment (wt%)",
                       "Coping time to 1204 °C (min)", "Time to melt (min)", f"H₂ by {response_min} min (kg)",
                       f"H₂ after {res.attrs.get('duration_min', 90):.0f} min (kg)", "Collapse safety factor",
                       "Fuel centre temperature (°C)"],
            "Optimized Zircaloy-2": [f"{z.usd_per_MWh_e:.2f}", money(z.annual_fuel_cost_usd), f"{z.enrichment_wt:.2f}",
                                     f"{z.coping_plot_min:.1f}", fmt_min(z.melt_min, 90), f"{z.h2_at_response_kg:.2f}",
                                     f"{z.h2_end_kg:.1f}", f"{z.collapse_sf:.2f}", f"{z.centerline_C:.0f}"],
            "Optimized layered": [f"{l.usd_per_MWh_e:.2f}", money(l.annual_fuel_cost_usd), f"{l.enrichment_wt:.2f}",
                                  f"{l.coping_plot_min:.1f}", fmt_min(l.melt_min, 90), f"{l.h2_at_response_kg:.2f}",
                                  f"{l.h2_end_kg:.1f}", f"{l.collapse_sf:.2f}", f"{l.centerline_C:.0f}"],
        })
        st.dataframe(comp, hide_index=True)
        dc = l.usd_per_MWh_e - z.usd_per_MWh_e
        dh = z.h2_end_kg - l.h2_end_kg
        msg = (f"The layered design costs **{dc:+.2f} $/MWh** ({money(l.annual_fuel_cost_usd - z.annual_fuel_cost_usd)}"
               f" per year per unit) versus the best Zircaloy rod, and makes **{dh:.1f} kg less hydrogen** if cooling "
               f"is never restored. That's about **{money((l.annual_fuel_cost_usd - z.annual_fuel_cost_usd) / max(dh, 0.01))}"
               f" per year per kg of hydrogen avoided**.")
        st.info(msg.replace("$", "\\$"))

        st.markdown("#### Where does the extra cost come from?")
        bz_cost, bl_cost = z["cost"]["breakdown_usd_per_kgU"], l["cost"]["breakdown_usd_per_kgU"]
        mwh_z = dz.burnup * 24 * v(D.PLANT, "net_efficiency")
        mwh_l = dl.burnup * 24 * v(D.PLANT, "net_efficiency")
        fig = go.Figure()
        for (nm, row, mwh, col) in (("Optimized Zircaloy-2", bz_cost, mwh_z, FAMILY_COLORS["Zircaloy-2"]),
                                    ("Optimized layered", bl_cost, mwh_l, FAMILY_COLORS["Layered Zr/Mo/FeCrAl"])):
            fig.add_trace(go.Bar(name=nm, x=list(row), y=[x / mwh for x in row.values()], marker_color=col))
        fig.update_layout(barmode="group", title="Fuel-cycle cost breakdown", yaxis_title="$/MWh(e)")
        show(fig, 360)

        st.markdown("#### Changing the diameter: finding the best pellet size for the layered cladding")
        pel = np.round(np.arange(dl.pellet_mm - 0.8, dl.pellet_mm + 0.81, 0.05), 3)
        sw = pellet_sweep(dl, pel, min_coping=min_coping, response_min=response_min, h_steam=h_steam)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sw.pellet_mm, y=sw.usd_per_MWh_e, mode="lines", name="cost",
                                 line=dict(color=FAMILY_COLORS["Layered Zr/Mo/FeCrAl"], width=2)))
        ok = sw[sw.feasible]
        fig.add_trace(go.Scatter(x=ok.pellet_mm, y=ok.usd_per_MWh_e, mode="markers", name="passes all limits",
                                 marker=dict(color=FAMILY_COLORS["Layered Zr/Mo/FeCrAl"], size=9)))
        bad = sw[~sw.feasible]
        fig.add_trace(go.Scatter(x=bad.pellet_mm, y=bad.usd_per_MWh_e, mode="markers", name="fails a limit",
                                 marker=dict(color="#999", size=7, symbol="x"), text=bad.failed_checks,
                                 hovertemplate="%{x} mm: %{text}<extra></extra>"))
        fig.add_vline(x=dl.pellet_mm, line=dict(color=LIMIT_COLOR, dash="dash"), annotation_text="optimum")
        fig.update_layout(title="Bigger pellet = cheaper, until moderation / strength / flow limits stop it",
                          xaxis_title="Pellet diameter (mm), same layers", yaxis_title="$/MWh(e)")
        show(fig, 380)

        st.markdown("#### Layer thickness map (Mo × FeCrAl) for the optimized pellet and inner Zr")
        zr_t = dict(dl.layers)["Zircaloy-2"]
        mos = np.round(np.arange(0.10, 0.46, 0.05), 3)
        fes = np.round(np.arange(0.02, 0.17, 0.02), 3)
        grid = [Design(dl.family, make_layers(dl.family, zr_mm=zr_t, mo_mm=a, fe_mm=b), dl.pellet_mm, dl.gap_mm,
                       dl.layout, dl.burnup) for a in mos for b in fes]
        hm = run_eval(tuple(grid), min_coping, response_min, h_steam)
        Z = hm.usd_per_MWh_e.values.reshape(len(mos), len(fes))
        F = hm.feasible.values.reshape(len(mos), len(fes))
        txt = np.where(F, np.round(Z, 2).astype(str), "✗")
        fig = go.Figure(go.Heatmap(z=Z, x=fes, y=mos, text=txt, texttemplate="%{text}", colorscale="Purples",
                                   colorbar=dict(title="$/MWh")))
        fig.update_layout(title="Cost for each Mo / FeCrAl thickness (✗ = breaks a limit)",
                          xaxis_title="Outer FeCrAl (mm)", yaxis_title="Middle Mo (mm)")
        show(fig, 420)

# ================================================================== TAB 4
with tab4:
    st.subheader("Which inputs move cost and safety the most? (each input ±10%)")
    space, _ = run_space(burnup, min_coping, response_min, h_steam)
    bpf = best_per_family(space, objective)
    choice = st.selectbox("Design to test", list(bpf.family) if len(bpf) else ["Zircaloy-2"],
                          index=(list(bpf.family).index("Layered Zr/Mo/FeCrAl")
                                 if "Layered Zr/Mo/FeCrAl" in list(bpf.family) else 0))
    dsel = bpf[bpf.family == choice].iloc[0]["design"] if len(bpf) else ref
    st.caption(dsel.describe())
    with st.spinner("Running ±10% cases..."):
        tor, base = run_tornado(dsel, min_coping)
    c1, c2 = st.columns(2)
    for col, key, unit, title in ((c1, "cost", "$/MWh", "Cost ($/MWh e)"), (c2, "coping", "min", "Coping time (min)")):
        t = tor.sort_values(f"{key}_swing")
        fig = go.Figure()
        fig.add_trace(go.Bar(y=t.input, x=t[f"{key}_low"], orientation="h", name="input −10%", marker_color="#2a78d6"))
        fig.add_trace(go.Bar(y=t.input, x=t[f"{key}_high"], orientation="h", name="input +10%", marker_color="#eb6834"))
        fig.update_layout(barmode="overlay", title=f"{title}: change from base",
                          xaxis_title=f"change in {unit}")
        with col:
            show(fig, 460)
    st.caption(f"Base: ${base.usd_per_MWh_e:.2f}/MWh(e), coping {base.coping_plot_min:.1f} min. "
               "Coping time is capped at the simulated duration, so very safe designs can show zero change.")

# ================================================================== TAB 5
with tab5:
    st.subheader("Every number used, where it came from, and whether it still needs research")
    st.markdown("Edit values in **`safety/data.py`** and refresh. Status: **sourced** = from the reference, "
                "**derived** = calculated from sourced values, **assumption** = needs research.")
    rows = []
    for tname, table in (("Plant", D.PLANT), ("Fuel", D.FUEL), ("Economics", D.ECON), ("Neutronics", D.NEUTRONICS),
                         ("LOCA", D.LOCA), ("Mechanical / lattice", D.MECH)):
        for k, (val, src, status, note) in table.items():
            rows.append({"Group": tname, "Parameter": k, "Value": val, "Status": status, "Note": note,
                         "Source": D.SOURCES.get(src, ("", ""))[0], "Link": D.SOURCES.get(src, ("", ""))[1]})
    for mname, m in D.MATERIALS.items():
        for k in ("rho", "cp", "k", "E_GPa", "cost_usd_kg", "rate_mult", "q_per_mol_O", "lost_C", "melt_C"):
            src, status = m.get("src", {}).get(k, ("TEAM", "assumption"))
            rows.append({"Group": f"Material: {mname}", "Parameter": k, "Value": m[k], "Status": status, "Note": "",
                         "Source": D.SOURCES[src][0], "Link": D.SOURCES[src][1]})
    for (a, b), (val, src, status, note) in D.INTERFACE_LIMITS_C.items():
        rows.append({"Group": "Interface limit", "Parameter": f"{a} / {b}", "Value": val, "Status": status,
                     "Note": note, "Source": D.SOURCES[src][0], "Link": D.SOURCES[src][1]})
    src, status, note = D.ELEMENT_SOURCES
    for el, (A, s, ri) in D.ELEMENTS.items():
        rows.append({"Group": "Cross sections", "Parameter": el, "Value": f"σ={s} b, RI={ri} b", "Status": status,
                     "Note": note, "Source": D.SOURCES[src][0], "Link": D.SOURCES[src][1]})
    for lname, L in D.LAYOUTS.items():
        rows.append({"Group": "Layout", "Parameter": lname,
                     "Value": f"{L['rods']} rods, pitch {L['pitch_mm']} mm, pellet {L['ref_pellet_mm']} mm",
                     "Status": "sourced/assumption", "Note": L["notes"], "Source": "", "Link": ""})
    table = pd.DataFrame(rows)
    status_filter = st.multiselect("Show status", ["sourced", "derived", "assumption", "sourced/assumption"],
                                   default=["sourced", "derived", "assumption", "sourced/assumption"])
    table["Value"] = table["Value"].astype(str)
    try:
        st.dataframe(table[table.Status.isin(status_filter)], hide_index=True,
                     column_config={"Link": st.column_config.LinkColumn("Link")})
    except Exception:
        st.dataframe(table[table.Status.isin(status_filter)], hide_index=True)
    st.markdown("**Model limits:** lumped rod slices, no axial steam heat transport or steam starvation, "
                "no ballooning/burst, no lattice-physics code (the neutron penalty is calibrated to one ORNL FeCrAl "
                "result and uses rough resonance weighting, which matters a lot for molybdenum), fuel cost is "
                "undiscounted like the starter tool. Beyond-design-basis scenario: the BWRX-300 is designed so "
                "its design-basis accidents never uncover the core.")
