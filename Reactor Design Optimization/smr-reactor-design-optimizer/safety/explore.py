"""
Design-space exploration, ranking, per-family optimum and tornado sensitivity.
"""
import itertools
import numpy as np
import pandas as pd

from . import data as D
from .data import v
from .rod import Design, make_layers, fast_metrics, FAMILIES
from .loca import simulate_batch

SAFETY_CHECKS = ["H2 by response time <= limit", "No melting before response time",
                 "Coping time >= minimum"]


def evaluate(designs, min_coping=0.0, response_min=None, h_steam=None, decay_mult=1.0,
             rate_scale=1.0, econ_override=None, run_loca_on="all"):
    """Fast checks for every design; LOCA transient for those passing (or all)."""
    rows = [fast_metrics(d, econ_override) for d in designs]
    df = pd.DataFrame(rows)
    df["fast_ok"] = [all(r["checks"].values()) for r in rows]
    idx = list(range(len(designs))) if run_loca_on == "all" else list(np.where(df["fast_ok"])[0])
    for c in ("coping_min", "melt_min", "protection_lost_min", "h2_at_response_kg", "h2_end_kg", "peak_T"):
        df[c] = np.nan
    if idx:
        res = simulate_batch([designs[i] for i in idx], h_steam=h_steam, decay_mult=decay_mult,
                             rate_scale=rate_scale, response_min=response_min)
        for c in ("coping_min", "melt_min", "protection_lost_min", "h2_at_response_kg", "h2_end_kg", "peak_T"):
            df.loc[idx, c] = res[c]
        df.attrs["h2_limit_kg"] = res["h2_limit_kg"]
        df.attrs["duration_min"] = res["duration_min"]
        df.attrs["response_min"] = res["response_min"]
    resp = df.attrs.get("response_min", v(D.LOCA, "response_min"))
    dur = df.attrs.get("duration_min", v(D.LOCA, "duration_min"))
    lim = df.attrs.get("h2_limit_kg", 4.5)
    # coping: never reaching 1204 C within the simulated time counts as the full duration
    df["coping_plot_min"] = df["coping_min"].fillna(dur)
    df["melt_plot_min"] = df["melt_min"].fillna(dur)
    safety = []
    for _, r in df.iterrows():
        safety.append({
            "H2 by response time <= limit": bool(r["h2_at_response_kg"] <= lim),
            "No melting before response time": bool(np.isnan(r["melt_min"]) or r["melt_min"] > resp),
            "Coping time >= minimum": bool(r["coping_plot_min"] >= min_coping),
        })
    df["safety_checks"] = safety
    df["safe_ok"] = [all(s.values()) for s in safety]
    df["feasible"] = df["fast_ok"] & df["safe_ok"]
    df["failed_checks"] = [
        ", ".join([k for k, ok in {**r["checks"], **s}.items() if not ok]) or "-"
        for r, s in zip(rows, safety)
    ]
    return df


def build_grid(burnup=50.0, families=None, coarse=False):
    """Candidate designs for each cladding family (a few hundred to ~2000)."""
    families = families or FAMILIES
    layouts = list(D.LAYOUTS)
    designs = []
    for lay in layouts:
        L = D.LAYOUTS[lay]
        scale = L["ref_pellet_mm"] / D.LAYOUTS[D.REFERENCE_LAYOUT]["ref_pellet_mm"]
        pellets = np.round(np.arange(7.9, 9.71, 0.15 if coarse else 0.1) * scale, 3)
        gap = L["ref_gap_mm"]
        for fam in families:
            if fam == "Zircaloy-2":
                opts = [dict(wall_mm=w) for w in np.round(np.arange(0.40, 0.81, 0.05), 3)]
            elif fam == "Cr-coated Zr":
                opts = [dict(wall_mm=w, cr_mm=0.015) for w in np.round(np.arange(0.40, 0.81, 0.05), 3)]
            elif fam == "FeCrAl":
                opts = [dict(wall_mm=w) for w in np.round(np.arange(0.25, 0.61, 0.05), 3)]
            else:
                zr = [0.03, 0.06, 0.10]
                mo = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
                fe = [0.03, 0.06, 0.10]
                opts = [dict(zr_mm=a, mo_mm=b, fe_mm=c) for a, b, c in itertools.product(zr, mo, fe)]
            for o in opts:
                layers = make_layers(fam, **o)
                for p in pellets:
                    designs.append(Design(fam, layers, float(p), gap, lay, burnup))
    return designs


def rank(df, objective="cost"):
    ok = df[df["feasible"]].copy()
    if objective == "cost":
        ok = ok.sort_values(["usd_per_MWh_e", "coping_plot_min"], ascending=[True, False])
    elif objective == "safety":
        ok = ok.sort_values(["coping_plot_min", "h2_at_response_kg", "usd_per_MWh_e"],
                            ascending=[False, True, True])
    else:   # balanced: cost per minute of coping relative to baseline
        base_cost = df["usd_per_MWh_e"].min()
        ok["score"] = (ok["usd_per_MWh_e"] / base_cost) - 0.5 * (ok["coping_plot_min"] / ok["coping_plot_min"].max())
        ok = ok.sort_values("score")
    ok.insert(0, "rank", range(1, len(ok) + 1))
    return ok


def best_per_family(df, objective="cost"):
    out = []
    for fam in FAMILIES:
        sub = rank(df[df["family"] == fam], objective)
        if len(sub):
            out.append(sub.iloc[0])
    return pd.DataFrame(out)


def pellet_sweep(design, pellets, **kw):
    """Same layers/layout, different pellet diameters (for the 'change the diameter' chart)."""
    ds = [Design(design.family, design.layers, float(p), design.gap_mm, design.layout, design.burnup)
          for p in pellets]
    return evaluate(ds, **kw)


# ------------------------------------------------------------------ tornado
def tornado(design, pct=0.10, min_coping=0.0):
    """Change each input +/-pct; report change in $/MWh(e) and coping time."""
    base = evaluate([design], min_coping=min_coping).iloc[0]
    items = []

    def scaled_layers(i, f):
        lay = list(design.layers)
        m, t = lay[i]
        lay[i] = (m, t * f)
        return tuple(lay)

    def mk(**chg):
        p = dict(family=design.family, layers=design.layers, pellet_mm=design.pellet_mm,
                 gap_mm=design.gap_mm, layout=design.layout, burnup=design.burnup)
        p.update(chg)
        return Design(**p)

    cases = [("Pellet diameter", lambda f: (mk(pellet_mm=design.pellet_mm * f), {}))]
    for i, (m, t) in enumerate(design.layers):
        cases.append((f"{m.split(' ')[0]} layer thickness", lambda f, i=i: (mk(layers=scaled_layers(i, f)), {})))
    cases += [
        ("Discharge burnup", lambda f: (mk(burnup=design.burnup * f), {})),
        ("Uranium price", lambda f: (design, {"econ": {"U3O8_usd_per_lb": v(D.ECON, "U3O8_usd_per_lb") * f}})),
        ("Enrichment (SWU) price", lambda f: (design, {"econ": {"SWU_usd": v(D.ECON, "SWU_usd") * f}})),
        ("Fabrication cost", lambda f: (design, {"econ": {"fab_usd_per_kgU": v(D.ECON, "fab_usd_per_kgU") * f}})),
        ("Steam cooling coefficient", lambda f: (design, {"h_steam": v(D.LOCA, "h_steam_W_m2K") * f})),
        ("Decay heat level", lambda f: (design, {"decay_mult": f})),
        ("Outer-layer oxidation rate", lambda f: (design, {"rate_scale": f})),
    ]
    for name, fn in cases:
        vals = {}
        for f in (1 - pct, 1 + pct):
            d, extra = fn(f)
            r = evaluate([d], min_coping=min_coping, h_steam=extra.get("h_steam"),
                         decay_mult=extra.get("decay_mult", 1.0),
                         rate_scale=extra.get("rate_scale", 1.0),
                         econ_override=extra.get("econ")).iloc[0]
            vals[f] = r
        lo, hi = vals[1 - pct], vals[1 + pct]
        items.append({
            "input": name,
            "cost_low": lo["usd_per_MWh_e"] - base["usd_per_MWh_e"],
            "cost_high": hi["usd_per_MWh_e"] - base["usd_per_MWh_e"],
            "coping_low": lo["coping_plot_min"] - base["coping_plot_min"],
            "coping_high": hi["coping_plot_min"] - base["coping_plot_min"],
        })
    t = pd.DataFrame(items)
    t["cost_swing"] = (t["cost_high"] - t["cost_low"]).abs()
    t["coping_swing"] = (t["coping_high"] - t["coping_low"]).abs()
    return t, base
