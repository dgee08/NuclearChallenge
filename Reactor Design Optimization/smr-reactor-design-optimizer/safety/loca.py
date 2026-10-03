"""
Loss-of-coolant (rods uncovered in steam) transient for MANY designs at once.

Physics per rod slice (same as the team's steam_oxidation.py, generalised to layers):
    m*c dT/dt = decay heat + oxidation heat - steam cooling
    oxidation: parabolic Cathcart-Pawel law  w^2 = Kp t,  Kp = 0.1811 exp(-39940/(1.987 T))
               multiplied by the rate factor of whichever layer currently faces the steam
    hydrogen:  1 mol H2 per mol O picked up  ->  H2 = w / 16  (mol/cm2)
Layer logic:
    outer layer protects until it is lost (melts / eutectic with the layer below);
    then the next layer faces the steam; the rod loses its shape at fail_C.
Core: 5 radial power groups x 8 axial slices.
"""
import math
import numpy as np

from . import data as D
from .data import v
from .rod import Design, layout, kgU_per_m, mass_per_m

R_CAL = 1.987
RADIAL_PEAK = np.array([0.70, 0.90, 1.00, 1.15, 1.40])
RADIAL_FRAC = np.array([0.20, 0.25, 0.25, 0.20, 0.10])
RADIAL_PEAK = RADIAL_PEAK / np.sum(RADIAL_PEAK * RADIAL_FRAC)
N_AX = 8
_z = (np.arange(N_AX) + 0.5) / N_AX
AXIAL_PEAK = np.cos(np.pi * (_z - 0.5) * 0.9)
AXIAL_PEAK = AXIAL_PEAK / AXIAL_PEAK.mean()
SHAPE = np.outer(RADIAL_PEAK, AXIAL_PEAK)          # (5, 8)


def decay_fraction(t_s, operation_s):
    t = np.maximum(t_s, 1.0)
    return 0.0622 * (t ** -0.2 - (t + operation_s) ** -0.2)


def layer_logic(d: Design):
    """Return protected/exposed oxidation parameters, protection-loss and failure temps."""
    mats = [m for m, _ in d.layers]
    M = D.MATERIALS
    outer = mats[-1]
    if d.family == "Zircaloy-2":
        p = e = M["Zircaloy-2"]
        lost, fail = 1e9, M["Zircaloy-2"]["melt_C"]
    elif d.family == "FeCrAl":
        p = e = M["FeCrAl (C26M)"]
        lost, fail = 1e9, M["FeCrAl (C26M)"]["melt_C"]
    elif d.family == "Cr-coated Zr":
        p, e = M["Chromium coating"], M["Zircaloy-2"]
        lost = D.INTERFACE_LIMITS_C[("Chromium coating", "Zircaloy-2")][0]
        fail = M["Zircaloy-2"]["melt_C"]
    elif d.family == "Layered Zr/Mo/FeCrAl":
        p, e = M["FeCrAl (C26M)"], M["Molybdenum"]
        lost = min(M["FeCrAl (C26M)"]["lost_C"],
                   D.INTERFACE_LIMITS_C[("FeCrAl (C26M)", "Molybdenum")][0])
        if D.LAYERED_FAIL_MODE == "Zr-Mo eutectic":
            fail = D.INTERFACE_LIMITS_C[("Zircaloy-2", "Molybdenum")][0]
        else:
            fail = M["Molybdenum"]["melt_C"]
    else:
        raise ValueError(d.family)
    return {"rate_p": p["rate_mult"], "q_p": p["q_per_mol_O"],
            "rate_e": e["rate_mult"], "q_e": e["q_per_mol_O"],
            "lost_C": lost, "fail_C": fail}


def simulate_batch(designs, h_steam=None, decay_mult=1.0, rate_scale=1.0,
                   duration_min=None, dt=2.0, response_min=None, record_s=30.0):
    """Run the uncovered-core transient for a list of designs. Returns a dict of arrays."""
    n = len(designs)
    h_steam = v(D.LOCA, "h_steam_W_m2K") if h_steam is None else h_steam
    duration_min = v(D.LOCA, "duration_min") if duration_min is None else duration_min
    response_min = v(D.LOCA, "response_min") if response_min is None else response_min
    t0 = v(D.LOCA, "t_uncover_h") * 3600
    op = v(D.LOCA, "operation_s")
    W0 = v(D.LOCA, "W0_g_cm2")
    Tsat = v(D.PLANT, "T_sat_C")
    L_act = v(D.PLANT, "active_length_m")
    dz = L_act / N_AX
    nb = v(D.PLANT, "n_bundles")

    def col(vals):
        return np.asarray(vals, float)[:, None, None]

    mc, area, perim, q_avg, rods, rate_p, q_p, rate_e, q_e, lost, fail = ([] for _ in range(11))
    for d in designs:
        rad = d.radii_m()
        r_o = rad[-1][2]
        c = kgU_per_m(d) / v(D.FUEL, "U_mass_fraction") * 320.0          # UO2 cp ~320 J/kgK
        c += sum(mass_per_m(m, a, b) * D.MATERIALS[m]["cp"] for m, a, b in rad)
        mc.append(c)
        perim.append(2 * math.pi * r_o)                                     # m
        area.append(2 * math.pi * r_o * 100 * 100)                          # cm2 per m
        L = layout(d)
        q_avg.append(v(D.PLANT, "core_power_MWt") * 1e6 / (nb * L["effective_rods"] * L_act) * decay_mult)
        rods.append(nb * L["effective_rods"])
        lg = layer_logic(d)
        rate_p.append(lg["rate_p"] * rate_scale); q_p.append(lg["q_p"])
        rate_e.append(lg["rate_e"]); q_e.append(lg["q_e"])
        lost.append(lg["lost_C"]); fail.append(lg["fail_C"])
    mc, area, perim, q_avg = col(mc), col(area), col(perim), col(q_avg)
    rate_p, q_p, rate_e, q_e, lost, fail = map(col, (rate_p, q_p, rate_e, q_e, lost, fail))
    rods_node = np.asarray(rods)[:, None, None] * RADIAL_FRAC[None, :, None] * np.ones((1, 1, N_AX))
    shape = SHAPE[None, :, :]

    T = np.full((n, 5, N_AX), Tsat)
    w = np.full((n, 5, N_AX), W0)
    protected = np.ones_like(T, bool)
    failed = np.zeros_like(T, bool)
    steps = int(duration_min * 60 / dt) + 1
    every = max(1, int(record_s / dt))
    t1204 = np.full(n, np.nan)
    tfail = np.full(n, np.nan)
    tlost = np.full(n, np.nan)
    h2_resp = np.full(n, np.nan)
    pct = v(D.LOCA, "pct_limit")
    rec_t, rec_T, rec_h2 = [], [], []

    def h2_kg():
        mol = np.sum((w - W0) / 16.0 * area * dz * rods_node, axis=(1, 2))
        return mol * 2.016e-3

    for i in range(steps):
        t = i * dt
        q_dec = q_avg * decay_fraction(t0 + t, op) * shape
        protected &= T < lost
        rate = np.where(protected, rate_p, rate_e)
        qmol = np.where(protected, q_p, q_e)
        kp = 0.1811 * np.exp(-39940.0 / (R_CAL * (T + 273.15))) * rate
        dwdt = np.where(failed, 0.0, kp / (2 * w))
        q_ox = dwdt * area * qmol / 16.0                     # W/m  (g O/s/m -> mol O -> J)
        q_out = h_steam * perim * (T - Tsat)
        T = np.where(failed, T, T + (q_dec + q_ox - q_out) / mc * dt)
        w = w + dwdt * dt
        failed |= T >= fail
        T = np.where(failed, np.minimum(T, fail), T)
        Tmax = T.max(axis=(1, 2))
        newly = np.isnan(t1204) & (Tmax >= pct)
        t1204[newly] = t / 60
        f_any = failed.any(axis=(1, 2))
        tfail[np.isnan(tfail) & f_any] = t / 60
        l_any = (~protected).any(axis=(1, 2))
        tlost[np.isnan(tlost) & l_any] = t / 60
        if np.isnan(h2_resp[0]) and t >= response_min * 60:
            h2_resp = h2_kg()
        if i % every == 0:
            rec_t.append(t / 60)
            rec_T.append(Tmax.copy())
            rec_h2.append(h2_kg())
    if np.isnan(h2_resp[0]):
        h2_resp = h2_kg()

    # 1% of H2 from reacting all REFERENCE Zircaloy cladding (fixed yardstick, ~4.8 kg)
    Lref = D.LAYOUTS[D.REFERENCE_LAYOUT]
    r_i = (Lref["ref_pellet_mm"] / 2 + Lref["ref_gap_mm"]) / 1000
    m_zr = mass_per_m("Zircaloy-2", r_i, r_i + Lref["ref_wall_mm"] / 1000) * 1000   # g/m
    h2_all = m_zr * L_act * nb * Lref["effective_rods"] / D.MATERIALS["Zircaloy-2"]["metal_per_O"] / 16 * 2.016e-3
    return {
        "coping_min": t1204, "melt_min": tfail, "protection_lost_min": tlost,
        "h2_at_response_kg": h2_resp, "h2_end_kg": rec_h2[-1],
        "h2_limit_kg": v(D.LOCA, "h2_limit_frac") * h2_all,
        "peak_T": np.max(np.array(rec_T), axis=0),
        "t_min": np.array(rec_t), "T_hot": np.array(rec_T).T, "h2_kg": np.array(rec_h2).T,
        "duration_min": duration_min, "response_min": response_min,
    }
