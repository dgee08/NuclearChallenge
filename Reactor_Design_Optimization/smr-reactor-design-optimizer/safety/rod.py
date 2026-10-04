"""
Fuel-rod design definition plus the fast (non-transient) calculations:
geometry, neutron penalty -> required enrichment, fuel-cycle cost,
collapse strength, fuel temperature, moderation and flow-area checks.

All numbers come from data.py.
"""
from dataclasses import dataclass, field
from functools import lru_cache
import math

from . import data as D
from .data import v

N_A = 6.02214e23
BARN = 1e-24

# ------------------------------------------------------------------ cladding families
FAMILIES = ["Zircaloy-2", "Cr-coated Zr", "FeCrAl", "Layered Zr/Mo/FeCrAl"]
FAMILY_COLORS = {"Zircaloy-2": "#2a78d6", "Cr-coated Zr": "#eb6834",
                 "FeCrAl": "#1baf7a", "Layered Zr/Mo/FeCrAl": "#7b4fd6"}


def make_layers(family, wall_mm=None, zr_mm=None, mo_mm=None, fe_mm=None, cr_mm=0.015):
    """Return layers inner -> outer as ((material, thickness_mm), ...)."""
    if family == "Zircaloy-2":
        return (("Zircaloy-2", wall_mm),)
    if family == "FeCrAl":
        return (("FeCrAl (C26M)", wall_mm),)
    if family == "Cr-coated Zr":
        return (("Zircaloy-2", wall_mm), ("Chromium coating", cr_mm))
    if family == "Layered Zr/Mo/FeCrAl":
        return (("Zircaloy-2", zr_mm), ("Molybdenum", mo_mm), ("FeCrAl (C26M)", fe_mm))
    raise ValueError(family)


@dataclass(frozen=True)
class Design:
    family: str
    layers: tuple                      # ((material, t_mm), ...) inner -> outer
    pellet_mm: float
    gap_mm: float = 0.09
    layout: str = D.REFERENCE_LAYOUT
    burnup: float = 50.0               # batch-average discharge burnup, GWd/tU
    label: str = ""

    # ---------------- geometry
    @property
    def wall_mm(self):
        return sum(t for _, t in self.layers)

    @property
    def od_mm(self):
        return self.pellet_mm + 2 * self.gap_mm + 2 * self.wall_mm

    def radii_m(self):
        """[(material, r_in, r_out)] in metres, inner -> outer."""
        r = (self.pellet_mm / 2 + self.gap_mm) / 1000
        out = []
        for m, t in self.layers:
            out.append((m, r, r + t / 1000))
            r += t / 1000
        return out

    def describe(self):
        lay = " / ".join(f"{m.split(' ')[0]} {t:.3f}" for m, t in self.layers)
        return f"{self.family}: pellet {self.pellet_mm:.2f} mm, wall [{lay}] mm, {self.layout}"


# ------------------------------------------------------------------ material helpers
@lru_cache(maxsize=None)
def sigma_eff(material):
    """Effective macroscopic absorption cross section, 1/cm (thermal + weighted resonance)."""
    m = D.MATERIALS[material]
    rho_gcc = m["rho"] / 1000
    w_res = v(D.NEUTRONICS, "resonance_weight")
    total = 0.0
    for el, wt in m["comp_wt"].items():
        A, s_th, ri = D.ELEMENTS[el]
        n = rho_gcc * wt / A * N_A
        total += n * (s_th + w_res * ri) * BARN
    return total


def layout(d):
    return D.LAYOUTS[d.layout]


def _ref_design():
    L = D.LAYOUTS[D.REFERENCE_LAYOUT]
    return Design("Zircaloy-2", make_layers("Zircaloy-2", L["ref_wall_mm"]), L["ref_pellet_mm"],
                  L["ref_gap_mm"], D.REFERENCE_LAYOUT, 50.0, "Reference GNF2-class")


def clad_absorption_per_fuel(d):
    """Cladding absorption per unit fuel area (dimensionless index)."""
    a_fuel = math.pi * (d.pellet_mm / 20) ** 2                 # cm2
    tot = 0.0
    for m, r1, r2 in d.radii_m():
        area = math.pi * ((r2 * 100) ** 2 - (r1 * 100) ** 2)   # cm2
        tot += sigma_eff(m) * area
    return tot / a_fuel


@lru_cache(maxsize=1)
def _penalty_calibration():
    """wt% per unit of absorption index, from the ORNL FeCrAl result."""
    L = D.LAYOUTS[D.REFERENCE_LAYOUT]
    od = L["ref_pellet_mm"] + 2 * L["ref_gap_mm"] + 2 * L["ref_wall_mm"]
    zr_wall = v(D.NEUTRONICS, "calib_zr_wall_mm")
    fe_wall = v(D.NEUTRONICS, "calib_fecral_wall_mm")
    gap = L["ref_gap_mm"]
    zr = Design("Zircaloy-2", make_layers("Zircaloy-2", zr_wall), od - 2 * gap - 2 * zr_wall, gap)
    fe = Design("FeCrAl", make_layers("FeCrAl", fe_wall), od - 2 * gap - 2 * fe_wall, gap)
    d_index = clad_absorption_per_fuel(fe) - clad_absorption_per_fuel(zr)
    return v(D.NEUTRONICS, "calib_fecral_dE_wt") / d_index


def enrichment_required(d):
    """Linear reactivity model + cladding absorption penalty (wt% U-235)."""
    base = v(D.NEUTRONICS, "e0_wt") + d.burnup / v(D.NEUTRONICS, "burnup_slope")
    ref = _ref_design()
    penalty = _penalty_calibration() * (clad_absorption_per_fuel(d) - clad_absorption_per_fuel(ref))
    return base + penalty, penalty


# ------------------------------------------------------------------ economics
def _V(x):
    return (2 * x - 1) * math.log(x / (1 - x))


def fuel_cost(d, econ_override=None):
    """Fuel-cycle cost per MWh(e) and its breakdown (undiscounted, like the starter tool)."""
    E = {k: val[0] for k, val in D.ECON.items()}
    if econ_override:
        E.update(econ_override)
    e, _ = enrichment_required(d)
    xp, xt, xf = e / 100, E["tails_assay_pct"] / 100, 0.00711
    feed = (xp - xt) / (xf - xt)
    swu = _V(xp) + (feed - 1) * _V(xt) - feed * _V(xf)
    uranium = feed * E["U3O8_usd_per_lb"] * 2.5998          # 2.6 lb U3O8 per kgU
    conversion = feed * E["conversion_usd_kgU"]
    enrich = swu * E["SWU_usd"]
    fab = E["fab_usd_per_kgU"] * (1 - E["hardware_share_fab"])
    u_per_m = kgU_per_m(d)
    clad_cost_per_m = sum(mass_per_m(m, r1, r2) * D.MATERIALS[m]["cost_usd_kg"]
                          for m, r1, r2 in d.radii_m())
    hardware = clad_cost_per_m / u_per_m
    backend = E["backend_usd_per_kgHM"]
    per_kgU = uranium + conversion + enrich + fab + hardware + backend
    mwh_e_per_kgU = d.burnup * 24.0 * v(D.PLANT, "net_efficiency")
    usd_mwh = per_kgU / mwh_e_per_kgU
    p_e = v(D.PLANT, "core_power_MWt") * v(D.PLANT, "net_efficiency")
    annual = usd_mwh * p_e * v(D.PLANT, "capacity_factor") * 8760
    return {
        "enrichment_wt": e, "feed_per_kgU": feed, "swu_per_kgU": swu,
        "usd_per_MWh_e": usd_mwh, "annual_fuel_cost_usd": annual,
        "breakdown_usd_per_kgU": {"Uranium": uranium, "Conversion": conversion,
                                  "Enrichment": enrich, "Fabrication": fab,
                                  "Cladding hardware": hardware, "Back-end": backend},
        "kgU_core": u_per_m * v(D.PLANT, "active_length_m") * layout(d)["effective_rods"] * v(D.PLANT, "n_bundles"),
    }


def kgU_per_m(d):
    area_m2 = math.pi * (d.pellet_mm / 2000) ** 2
    rho = v(D.FUEL, "UO2_density_TD_g_cc") * 1000 * v(D.FUEL, "pellet_density_frac")
    return area_m2 * rho * v(D.FUEL, "U_mass_fraction")


def mass_per_m(material, r1, r2):
    return math.pi * (r2 ** 2 - r1 ** 2) * D.MATERIALS[material]["rho"]


# ------------------------------------------------------------------ mechanics
def collapse_safety_factor(d):
    """Elastic ring-collapse pressure of the layered wall at end of life / coolant pressure."""
    rad = list(d.radii_m())
    m_out, r1, r2 = rad[-1]
    rad[-1] = (m_out, r1, max(r1, r2 - D.MATERIALS[m_out]["eol_corrosion_mm"] / 1000))
    r_in, r_out = rad[0][1], rad[-1][2]
    r_m = 0.5 * (r_in + r_out)
    Ep = [D.MATERIALS[m]["E_GPa"] * 1e9 / (1 - D.MATERIALS[m]["nu"] ** 2) for m, _, _ in rad]
    num = sum(E * (b - a) * 0.5 * (a + b) for E, (_, a, b) in zip(Ep, rad))
    den = sum(E * (b - a) for E, (_, a, b) in zip(Ep, rad))
    zn = num / den
    Dflex = sum(E * ((b - zn) ** 3 - (a - zn) ** 3) / 3 for E, (_, a, b) in zip(Ep, rad))
    p_cr = 3 * Dflex / r_m ** 3
    return p_cr / (v(D.PLANT, "coolant_pressure_MPa") * 1e6)


# ------------------------------------------------------------------ thermal
def avg_linear_power_W_m(d):
    L = layout(d)
    return v(D.PLANT, "core_power_MWt") * 1e6 / (v(D.PLANT, "n_bundles") * L["effective_rods"]
                                                  * v(D.PLANT, "active_length_m"))


def centerline_temperature(d):
    q = avg_linear_power_W_m(d) * v(D.FUEL, "radial_x_axial_peaking") * v(D.FUEL, "overpower_factor")
    rad = d.radii_m()
    r_o = rad[-1][2]
    T = v(D.PLANT, "T_sat_C") + q / (2 * math.pi * r_o * v(D.FUEL, "h_film_W_m2K"))
    for m, a, b in rad:
        T += q * math.log(b / a) / (2 * math.pi * D.MATERIALS[m]["k"])
    T += q / (2 * math.pi * rad[0][1] * v(D.FUEL, "h_gap_W_m2K"))
    T += q / (4 * math.pi * v(D.FUEL, "k_UO2_W_mK"))
    return T


# ------------------------------------------------------------------ lattice checks
def _water_and_flow(d):
    L = layout(d)
    p = L["pitch_mm"]
    water = p ** 2 - math.pi * d.od_mm ** 2 / 4
    fuel = math.pi * d.pellet_mm ** 2 / 4
    return water / fuel, water * L["rods"]


@lru_cache(maxsize=1)
def _ref_lattice():
    return _water_and_flow(_ref_design())


def moderation_ratio(d):
    return _water_and_flow(d)[0] / _ref_lattice()[0]


def flow_area_ratio(d):
    return _water_and_flow(d)[1] / _ref_lattice()[1]


# ------------------------------------------------------------------ all fast checks
def fast_metrics(d, econ_override=None):
    c = fuel_cost(d, econ_override)
    e = c["enrichment_wt"]
    m = {
        "design": d, "family": d.family, "layout": d.layout,
        "pellet_mm": d.pellet_mm, "wall_mm": d.wall_mm, "od_mm": d.od_mm,
        "layers": " / ".join(f"{mat.split(' ')[0]} {t:.3f}" for mat, t in d.layers),
        "enrichment_wt": e, "enrich_penalty_wt": enrichment_required(d)[1],
        "usd_per_MWh_e": c["usd_per_MWh_e"], "annual_fuel_cost_usd": c["annual_fuel_cost_usd"],
        "collapse_sf": collapse_safety_factor(d),
        "centerline_C": centerline_temperature(d),
        "moderation_ratio": moderation_ratio(d),
        "flow_ratio": flow_area_ratio(d),
        "peak_rod_burnup": d.burnup * v(D.FUEL, "peak_to_avg_burnup"),
        "cost": c,
    }
    band = v(D.MECH, "moderation_band")
    m["checks"] = {
        "Enrichment <= 5 wt%": e <= v(D.NEUTRONICS, "max_enrichment_wt"),
        "Peak-rod burnup <= 62 GWd/t": m["peak_rod_burnup"] <= v(D.NEUTRONICS, "max_peak_rod_burnup"),
        "Fuel centre < 1800 C": m["centerline_C"] < v(D.FUEL, "max_centerline_C"),
        "Collapse safety factor >= 2": m["collapse_sf"] >= v(D.MECH, "collapse_sf_min"),
        "Moderation within +/-10%": abs(m["moderation_ratio"] - 1) <= band,
        "Flow area >= 95%": m["flow_ratio"] >= v(D.MECH, "flow_area_min"),
        "Layers >= 0.01 mm": all(t >= v(D.MECH, "min_layer_mm") - 1e-9 for _, t in d.layers),
    }
    return m
