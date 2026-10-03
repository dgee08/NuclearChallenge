"""
ALL NUMBERS USED BY THE SAFETY EXTENSION LIVE IN THIS FILE.

Every value has:
    - a source key (see SOURCES at the bottom), and
    - a status:  "sourced"     = taken from the cited reference
                 "derived"     = calculated from sourced numbers (formula in the comment)
                 "assumption"  = engineering estimate - RESEARCH AND REPLACE if you can

To change a number: edit it here, save, and refresh the Streamlit page. Nothing else
needs to change. The app's "Assumptions & sources" table is generated from this file.
"""

# ============================================================================ plant
PLANT = {
    "core_power_MWt":       (870.0,  "GEV_BWRX", "sourced",    "BWRX-300 rated thermal power"),
    "net_efficiency":       (0.345,  "GEV_BWRX", "derived",    "~300 MWe / 870 MWt"),
    "n_bundles":            (240,    "GEV_BWRX", "sourced",    "GNF2 bundles in core"),
    "active_length_m":      (3.81,   "CNSC_GNF2", "sourced",   "full-length rod active fuel length"),
    "coolant_pressure_MPa": (7.2,    "GEV_BWRX", "assumption", "typical BWR dome pressure ~7 MPa"),
    "T_sat_C":              (287.0,  "GEV_BWRX", "derived",    "saturation temperature at ~7.2 MPa"),
    "capacity_factor":      (0.95,   "GEV_BWRX", "assumption", "design target; edit in the app"),
}

# ============================================================================ bundle layouts
# effective_rods = full-length-equivalent rods (part-length rods counted by length)
LAYOUTS = {
    "10x10 (GNF2)": {
        "rods": 92, "effective_rods": 85.6, "pitch_mm": 12.95,
        "ref_pellet_mm": 8.76, "ref_gap_mm": 0.09, "ref_wall_mm": 0.66,
        "notes": "GNF2: 92 rods (78 full + 8 long + 6 short part-length), pitch 1.295 cm, "
                 "185 kgU/bundle (CNSC_GNF2). Rod dimensions are proprietary; pellet/gap/wall "
                 "are public GE14-class estimates (assumption).",
    },
    "11x11 (ATRIUM 11-style)": {
        "rods": 112, "effective_rods": 104.2, "pitch_mm": 11.77,
        "ref_pellet_mm": 7.96, "ref_gap_mm": 0.08, "ref_wall_mm": 0.60,
        "notes": "ASSUMPTION: 112 rods, same channel size so pitch = 12.95 x 10/11; rod "
                 "dimensions scaled by 10/11 from the 10x10 values; same part-length fraction "
                 "as GNF2 (85.6/92). Replace with real ATRIUM 11 data if you find it.",
    },
}
REFERENCE_LAYOUT = "10x10 (GNF2)"

# ============================================================================ fuel
FUEL = {
    "UO2_density_TD_g_cc":   (10.96, "IAEA_UO2", "sourced",    "theoretical density of UO2"),
    "pellet_density_frac":   (0.95,  "IAEA_UO2", "assumption", "typical 95% TD"),
    "U_mass_fraction":       (0.8815, "IAEA_UO2", "derived",   "238/270 for UO2"),
    "k_UO2_W_mK":            (3.0,   "IAEA_UO2", "assumption", "average UO2 conductivity at operating temperature"),
    "h_gap_W_m2K":           (5700., "TEAM",     "assumption", "pellet-clad gap conductance"),
    "h_film_W_m2K":          (30000., "TEAM",    "assumption", "boiling heat transfer coefficient"),
    "radial_x_axial_peaking": (2.4,  "TEAM",     "assumption", "hot-spot / core-average linear power"),
    "overpower_factor":      (1.2,   "TEAM",     "assumption", "transient margin applied to the hot spot"),
    "max_centerline_C":      (1800., "TEAM",     "assumption", "design limit on fuel centre temperature"),
    "peak_to_avg_burnup":    (1.15,  "TEAM",     "assumption", "peak-rod / batch-average burnup"),
}

# ============================================================================ economics
ECON = {
    "U3O8_usd_per_lb":     (96.50, "CAMECO",  "sourced",    "long-term price, 30 Sep 2026"),
    "conversion_usd_kgU":  (55.50, "MKT_AUG26", "sourced",  "N. American long-term conversion, Aug 2026"),
    "SWU_usd":             (183.0, "MKT_AUG26", "sourced",  "long-term enrichment price, Aug 2026"),
    "tails_assay_pct":     (0.25,  "TEAM",    "assumption", "enrichment plant tails"),
    "fab_usd_per_kgU":     (491.0, "WIT",     "sourced",    "INL WIT fabrication, mean (from model.py)"),
    "hardware_share_fab":  (0.30,  "WIT",     "sourced",    "share of fab toll that is hardware (from model.py)"),
    "backend_usd_per_kgHM": (927.0, "WIT",    "sourced",    "186 + 32 + 709 storage/transport/disposal (model.py)"),
}

# ============================================================================ neutronics
NEUTRONICS = {
    # Linear reactivity model: discharge burnup B = slope * (e - e0)
    # calibrated so a 7-batch BWR (12-month cycle) reaches ~50 GWd/t at ~4.2 wt%.
    "e0_wt":              (0.70,   "DRISCOLL", "sourced",    "enrichment intercept of the linear reactivity model"),
    "burnup_slope":       (14.175, "DRISCOLL", "derived",    "2n/(n+1) x 8.1 with n = 7 batches; GWd/t per wt%"),
    # epithermal weighting of resonance integrals: sigma_eff = sigma_th + w * RI
    "resonance_weight":   (0.10,   "TEAM",     "assumption", "rough LWR epithermal weighting - replace with lattice code"),
    # calibration: C26M FeCrAl 0.385 mm wall needs +0.6 wt% vs 0.64 mm Zr-2 (ORNL 0.4-0.8)
    "calib_fecral_wall_mm": (0.385, "ORNL_EE", "sourced",   "FeCrAl wall used in ORNL analysis"),
    "calib_fecral_dE_wt":   (0.60,  "ORNL_EE", "sourced",   "mid-point of the 0.4-0.8 wt% penalty"),
    "calib_zr_wall_mm":     (0.64,  "ORNL_EE", "sourced",   "nominal Zr-2 wall in ORNL analysis"),
    "max_enrichment_wt":    (5.0,   "CNSC_GNF2", "sourced", "current fuel facility / transport limit"),
    "max_peak_rod_burnup":  (62.0,  "NRC_BU",  "sourced",   "peak-rod average burnup licensing limit, GWd/tU"),
}

# thermal (2200 m/s) absorption cross sections and resonance integrals, barns
ELEMENTS = {
    #       A        sigma_th   RI
    "Zr": (91.224,   0.185,     1.0),
    "Sn": (118.71,   0.626,     7.8),
    "Fe": (55.845,   2.56,      1.4),
    "Cr": (51.996,   3.05,      1.6),
    "Ni": (58.693,   4.49,      2.2),
    "Al": (26.982,   0.231,     0.17),
    "Mo": (95.95,    2.48,      24.0),
}
ELEMENT_SOURCES = ("NIST_XS", "sourced", "sigma_th from NIST table; RI from Mughabghab Atlas (check values)")

# ============================================================================ materials
# rho kg/m3, cp J/kgK, k W/mK, E GPa (at ~300 C), nu, cost $/kg fabricated tube/layer
# rate_mult: steam-oxidation rate vs Zircaloy (Cathcart-Pawel) while this layer faces steam
# q_per_mol_O: heat released per mol O picked up from steam (J)
# lost_C: temperature above which this layer stops protecting (melts / eutectic)
MATERIALS = {
    "Zircaloy-2": {
        "rho": 6550, "cp": 330, "k": 17.0, "E_GPa": 80, "nu": 0.37,
        "comp_wt": {"Zr": 0.983, "Sn": 0.015, "Fe": 0.0015, "Cr": 0.001, "Ni": 0.0005},
        "cost_usd_kg": 420.0,
        "rate_mult": 1.0, "q_per_mol_O": 308e3, "metal_per_O": 2.85,
        "lost_C": 1850, "melt_C": 1850, "eol_corrosion_mm": 0.04,
        "color": "#2a78d6",
        "src": {"rho": ("DTIC_ZR", "sourced"), "cp": ("DTIC_ZR", "sourced"),
                "k": ("DTIC_ZR", "sourced"), "E_GPa": ("DTIC_ZR", "assumption"),
                "cost_usd_kg": ("STARTER", "sourced"), "rate_mult": ("CP", "sourced"),
                "q_per_mol_O": ("NIST_THERMO", "derived"), "melt_C": ("NPWR_ZR", "sourced")},
    },
    "FeCrAl (C26M)": {
        "rho": 7150, "cp": 550, "k": 12.0, "E_GPa": 190, "nu": 0.28,
        "comp_wt": {"Fe": 0.80, "Cr": 0.12, "Al": 0.06, "Mo": 0.02},
        "cost_usd_kg": 500.0,
        "rate_mult": 0.002, "q_per_mol_O": 317e3, "metal_per_O": 2.3,
        "lost_C": 1500, "melt_C": 1500, "eol_corrosion_mm": 0.004,
        "color": "#1baf7a",
        "src": {"rho": ("ORNL_HB", "assumption"), "cp": ("ORNL_HB", "sourced"),
                "k": ("ORNL_HB", "sourced"), "E_GPa": ("ORNL_HB", "sourced"),
                "comp_wt": ("ORNL_EE", "sourced"), "cost_usd_kg": ("TEAM", "assumption"),
                "rate_mult": ("PNNL_FE", "assumption"), "q_per_mol_O": ("NIST_THERMO", "derived"),
                "melt_C": ("PNNL_FE", "sourced")},
    },
    "Molybdenum": {
        "rho": 10220, "cp": 251, "k": 138.0, "E_GPa": 329, "nu": 0.31,
        "comp_wt": {"Mo": 1.0},
        "cost_usd_kg": 1500.0,
        "rate_mult": 0.01, "q_per_mol_O": 52e3, "metal_per_O": 3.0,
        "lost_C": 2623, "melt_C": 2623, "eol_corrosion_mm": 0.0,
        "color": "#8a6d3b",
        "src": {"rho": ("IMOA", "sourced"), "cp": ("WIKI_MO", "sourced"), "k": ("IMOA", "sourced"),
                "E_GPa": ("WIKI_MO", "sourced"), "cost_usd_kg": ("TEAM", "assumption"),
                "rate_mult": ("EPRI_MO", "derived"), "q_per_mol_O": ("NIST_THERMO", "derived"),
                "melt_C": ("IMOA", "sourced")},
    },
    "Chromium coating": {
        "rho": 7190, "cp": 450, "k": 94.0, "E_GPa": 279, "nu": 0.21,
        "comp_wt": {"Cr": 1.0},
        "cost_usd_kg": 2000.0,
        "rate_mult": 0.10, "q_per_mol_O": 138e3, "metal_per_O": 2.17,
        "lost_C": 1332, "melt_C": 1907, "eol_corrosion_mm": 0.002,
        "color": "#eb6834",
        "src": {"rate_mult": ("NATURE_CR", "assumption"), "lost_C": ("NATURE_CR", "sourced"),
                "cost_usd_kg": ("TEAM", "assumption"), "q_per_mol_O": ("NIST_THERMO", "derived")},
    },
}

# temperature at which the whole cladding loses its shape (first liquid in the structure)
INTERFACE_LIMITS_C = {
    ("FeCrAl (C26M)", "Molybdenum"): (1453, "CT_FEMO", "sourced", "lowest liquid in Fe-Mo system"),
    ("Zircaloy-2", "Molybdenum"):    (1551, "ZRMO",    "sourced", "Zr-Mo eutectic"),
    ("Chromium coating", "Zircaloy-2"): (1332, "NATURE_CR", "sourced", "Cr-Zr eutectic"),
}

# ============================================================================ LOCA scenario
LOCA = {
    "t_uncover_h":      (1.0,   "TEAM",  "assumption", "core uncovers 1 h after shutdown (beyond design basis)"),
    "h_steam_W_m2K":    (5.0,   "TEAM",  "assumption", "steam cooling of uncovered rods - BIGGEST UNCERTAINTY"),
    "operation_s":      (3.15e7, "TEAM", "assumption", "1 year at power before shutdown (decay heat)"),
    "duration_min":     (90.0,  "TEAM",  "assumption", "simulated time without cooling"),
    "pct_limit":        (1204., "NRC50", "sourced",    "peak cladding temperature limit"),
    "h2_limit_frac":    (0.01,  "NRC50", "sourced",    "1% of the H2 from reacting all reference cladding"),
    "response_min":     (30.0,  "TEAM",  "assumption", "time to restore cooling; H2 is counted up to this time"),
    "W0_g_cm2":         (1e-3,  "TEAM",  "assumption", "pre-existing oxide (~7 um)"),
}

# end-of-life wall loss of the OUTER layer to normal-operation corrosion (mm):
# Zircaloy ~0.04 mm (TEAM assumption from typical BWR oxide); FeCrAl oxide ~10x thinner (PNNL_FE).

# how the layered cladding is judged to lose its shape:
#   "Zr-Mo eutectic" -> 1551 C (inner Zr liner liquefies against Mo; conservative)
#   "Mo melting"     -> 2623 C (assumes the thin Zr liner does not matter)
LAYERED_FAIL_MODE = "Zr-Mo eutectic"

MECH = {
    "collapse_sf_min": (2.0, "TEAM", "assumption", "elastic collapse safety factor, no credit for internal gas"),
    "moderation_band": (0.10, "TEAM", "assumption", "water-to-fuel ratio within +/-10% of reference (void coefficient proxy)"),
    "flow_area_min":   (0.95, "TEAM", "assumption", "flow area >= 95% of reference (natural circulation / CHF)"),
    "min_layer_mm":    (0.01, "EPRI_MO", "derived", "thinnest practical layer (Cr coatings ~0.01-0.02 mm; EPRI used ~0.05 mm)"),
}

# ============================================================================ sources
SOURCES = {
    "GEV_BWRX": ("BWRX-300 General Description, GE Vernova",
                 "https://www.gevernova.com/content/dam/gevernova-nuclear/global/en_us/documents/carbon-free-power/005N9751-BWRX-300-General-Description.pdf"),
    "CNSC_GNF2": ("BWRX-300 DNNP GNF2 Fuel Design Qualification (CNSC CMD24-H3)",
                  "https://api.cnsc-ccsn.gc.ca/dms/digital-medias/CMD24-H3-Ref-BWRX-300-DNNP-GNF2-Fuel-Design-Qualification-and-BWR-Fuel-Licensing-Non-Proprietary-Information.PDF/object"),
    "CAMECO": ("Cameco uranium price (month-end, UxC/TradeTech average)",
               "https://www.cameco.com/invest/markets/uranium-price"),
    "MKT_AUG26": ("August 2026 month-end TradeTech/UxC prices (conversion $55.50, SWU $183), as reported",
                  "https://x.com/quakes99/status/2094695542769012832"),
    "WIT": ("INL Advanced Fuel Cycle Cost Basis (WIT values used in starter model.py)",
            "https://github.com/IdeasClinicUWaterloo/F26-NuclearIC/blob/main/Reactor%20Design%20Optimization/smr-reactor-design-optimizer/model.py"),
    "STARTER": ("Challenge starter tool model.py hardware cost table",
                "https://github.com/IdeasClinicUWaterloo/F26-NuclearIC/blob/main/Reactor%20Design%20Optimization/smr-reactor-design-optimizer/model.py"),
    "DRISCOLL": ("Driscoll, Downar & Pilat, The Linear Reactivity Model for Nuclear Fuel Management (ANS, 1990)", ""),
    "ORNL_EE": ("ORNL/TM-2021/1961 Extended-Enrichment Accident-Tolerant LWR fuel (FeCrAl penalty 0.4-0.8 wt%)",
                "https://www.nrc.gov/docs/ML2108/ML21088A254.pdf"),
    "NRC_BU": ("NRC: 62 GWd/MTU peak-rod average burnup limit (RG 1.183 / current LWR fuel licensing)", ""),
    "NIST_XS": ("NIST neutron scattering lengths and cross sections (Sears 1992)",
                "https://www.ncnr.nist.gov/resources/n-lengths/list.html"),
    "DTIC_ZR": ("Properties of Zircaloy-2 (DTIC)", "https://apps.dtic.mil/sti/tr/pdf/ADA316065.pdf"),
    "NPWR_ZR": ("High-temperature steam oxidation of zirconium alloys (nuclear-power.com)",
                "https://www.nuclear-power.com/nuclear-power-plant/nuclear-fuel/fuel-assembly/fuel-cladding-cladding-tube/high-temperature-steam-oxidation-of-zirconium-alloys/"),
    "CP": ("Cathcart-Pawel Zr steam oxidation correlation (ORNL Zircaloy-2 steam study)",
           "https://www.osti.gov/servlets/purl/1855637"),
    "ORNL_HB": ("ORNL/TM-2017/186 Handbook on the Material Properties of FeCrAl Alloys",
                "https://info.ornl.gov/sites/publications/Files/Pub74128.pdf"),
    "PNNL_FE": ("PNNL-30445 Degradation and Failure Phenomena of ATF: FeCrAl",
                "https://www.nrc.gov/docs/ML2027/ML20272A218.pdf"),
    "IMOA": ("International Molybdenum Association: molybdenum properties",
             "https://www.imoa.info/molybdenum/molybdenum-properties.php"),
    "WIKI_MO": ("Molybdenum (Wikipedia data box)", "https://en.wikipedia.org/wiki/Molybdenum"),
    "EPRI_MO": ("Cheng et al., Evaluations of Mo-alloy for LWR fuel cladding (EPJ-N 2016): Mo 0.2-0.25 mm, "
                "~0.05 mm Zr/FeCrAl coatings, Mo steam loss ~20-25 um/day at 1000 C (~100x below Zr)",
                "https://www.epj-n.org/articles/epjn/full_html/2016/01/epjn150060/epjn150060.html"),
    "NATURE_CR": ("Oxidation of Cr-coated Zr above 1200 C (npj Mater. Degrad.): Cr-Zr eutectic 1332 C",
                  "https://www.nature.com/articles/s41529-021-00155-8"),
    "CT_FEMO": ("CompuTherm Fe-Mo invariant reactions (liquid at 1453 C)", "https://computherm.com/fe-mo"),
    "ZRMO": ("High temperature phase diagrams for Zr-Mo (Metall. Trans.): eutectic 1551 C",
             "https://link.springer.com/article/10.1007/BF02661635"),
    "NIST_THERMO": ("NIST-JANAF heats of formation: H2O(g) -241.8, ZrO2 -1100.6, MoO2 -588.9, "
                    "Al2O3 -1675.7, Cr2O3 -1139.7 kJ/mol", "https://janaf.nist.gov/"),
    "NRC50": ("10 CFR 50.46 ECCS acceptance criteria", "https://www.nrc.gov/reading-rm/doc-collections/cfr/part050/part050-0046.html"),
    "IAEA_UO2": ("IAEA Thermophysical properties database of UO2", ""),
    "TEAM": ("Team engineering assumption - needs research", ""),
}


def v(table, key):
    """Return just the value of a (value, source, status, note) entry."""
    return table[key][0]
