"""Stage 6: build paper/paper.md from paper/template.md. Every number comes from the outputs of stages 1-3; the
script stops if a statement in the template is no longer true or a step has not been run. Then the Word version:

    python3 code/pipeline/p06_build_paper.py && pandoc paper/paper.md -o paper/paper.docx --resource-path=.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
sys.path.insert(0, str(Path(__file__).resolve().parent))


def need(cond, msg):
    if not cond:
        raise SystemExit("template statement no longer true: " + msg)


def f1(x):
    return f"{x:.1f}".replace("-", "−")


def cm(v):
    return f"{abs(v) * 100:.0f}"


def build():
    for f in ("index_results.json", "modflow_results.json", "structure_sensitivity.json", "attribution.json", "modflow_heads.npz"):
        if not (OUT / f).exists():
            raise SystemExit(f"outputs/{f} missing: run the pipeline (p02, p03, p03b, p03c) first")
    R = json.loads((OUT / "index_results.json").read_text())
    M = json.loads((OUT / "modflow_results.json").read_text())
    S = json.loads((OUT / "structure_sensitivity.json").read_text())
    H = np.load(OUT / "modflow_heads.npz")
    A = json.loads((OUT / "attribution.json").read_text())
    meta = json.loads((ROOT / "data_cache" / "stack_meta.json").read_text())
    rp, var, gh = R["reproduction"], R["variants"], R["ghsl_check"]
    wc = R["weight_sensitivity"]["corrected_setup"]

    # statements in the text
    need(rp["basin_change_pct"] > 0 and rp["urban_core_change_pct"] > 0, "the rebuilt index falls (positive = decline)")
    need(var["per_epoch_rain_and_ghsl_shift"]["basin_change_pct"] > 0 and var["per_epoch_rain_and_ghsl_shift"]["urban_core_change_pct"] > 0,
         "with both corrections the index still falls")
    need(gh["spearman_rho_dindex_ci95_block_bootstrap"][1] < 0, "the block-bootstrap interval of rho excludes zero")
    need(rp["urban_core_change_pct"] > 0 and all(v["urban_core_change_pct"] > 0 for v in var.values()), "the western decline appears in every single change")
    need(var["rainfall_per_epoch"]["basin_change_pct"] < 0, "per-epoch rainfall turns the barrier-wide decline into a rise")
    need(M["grid"]["rain_mean_mm_yr"]["2019_2023"] > M["grid"]["rain_mean_mm_yr"]["1986_1996"], "2019-2023 was wetter than 1986-1996")
    need(gh["spearman_rho_dperm_vs_dbuilt"] < 0, "the index falls where GHSL maps new buildings")
    sc = [s for s in M["scenarios"]]
    need(all(s[e]["converged"] for s in sc for e in ("1990", "2020")), "all scenario runs converged")
    act = H["active"]
    heads_ok = all(np.nanmin(H[k][:, act]) > 0 for k in H.files if k.startswith(("ghsl_", "spectral_")))
    need(heads_ok, "heads everywhere above sea level, so flow is outwards to the 0 m lagoon and sea cells")
    seeps = [s[e]["share_to_surface_seepage"] for s in sc for e in ("1990", "2020")]
    need(min(seeps) < 0.5 < max(seeps), "the seepage share spans both sides of one half (the text gives a range, not 'most')")
    pairs = {}
    for s in sc:
        pairs.setdefault((s["k_m_day"], s["base_m"], s["c"]), {})[s["sealing"]] = s["head_change_2020_minus_1990"]["mean_core_m"]
    need(all(p["spectral"] < p["ghsl"] < 0 for p in pairs.values()), "both estimates lower the western water table, the spectral one more")
    ghsl_core = [p["ghsl"] for p in pairs.values()]
    spec_core = [p["spectral"] for p in pairs.values()]
    need(max(ghsl_core) - min(ghsl_core) < 0.02, "conductivity, thickness and recharge share move the GHSL answer by under 2 cm")
    need(wc["urban_core_share_of_draws_with_decline"] > wc["basin_share_of_draws_with_decline"], "the west declines in more weight sets than the barrier")
    st = {k: [c["core_head_change_m"] for c in S["cases"] if c["sealing"] == k and c["converged"]] for k in ("ghsl", "spectral")}
    need(all(c["converged"] for c in S["cases"]), "all structure runs converged")
    need(all(x < 0 for x in st["ghsl"] + st["spectral"]), "every structure run gives a fall")
    so = A["sealing_only"]
    need(all(r["converged"] for r in so) and all(r["mean_core_m"] < 0 for r in so), "sealing alone lowers the western water table in every run")
    so_pair = {(r["sealing"], r["k_m_day"], r["base_m"], r["c"]): r["mean_core_m"] for r in so}
    need(all(so_pair[(s["sealing"], s["k_m_day"], s["base_m"], s["c"])] < s["head_change_2020_minus_1990"]["mean_core_m"] for s in sc),
         "sealing alone lowers the water table more than sealing and rainfall together (rainfall rose)")
    need(A["sealing_falls_share_of_cells"]["spectral"] > 0.2 and A["sealing_falls_share_of_cells"]["ghsl"] == 0,
         "the index-based sealing falls in a fifth or more of cells; GHSL sealing never falls")
    stc = {(c["case"], c["sealing"]): c for c in A["structure"]}
    need(all(c["converged"] for c in A["structure"]), "all drain test runs converged")
    nod_g, nod_s = stc[("no drains", "ghsl")]["core_head_change_m"], stc[("no drains", "spectral")]["core_head_change_m"]
    cen_g = pairs[(15.0, -30.0, 0.35)]["ghsl"]; cen_s = pairs[(15.0, -30.0, 0.35)]["spectral"]
    need(nod_g < 5 * cen_g and nod_s < 5 * cen_s, "without drains the fall is more than five times larger")
    weak = [stc[(n, s)]["core_head_change_m"] for n in ("drain length 1000 m", "drain length 10000 m") for s in ("ghsl", "spectral")]
    need(all(w < 0 for w in weak), "weak drains also give falls")
    nod_r = [nod_g / cen_g, nod_s / cen_s]
    weak_r = max(weak[0] / cen_g, weak[2] / cen_g, weak[1] / cen_s, weak[3] / cen_s)
    rise_so = [r["share_cells_rising"] for r in so if r["sealing"] == "spectral"]

    # eastern 'rural' reference zone: GHSL built-up fraction in 1990 and 2020
    m = np.load(OUT / "index_arrays.npz")
    with rasterio.open(ROOT / "data_cache" / "stack_utm31n_30m.tif") as src:
        names = list(src.descriptions)
        b90, b20 = src.read(names.index("built_1990") + 1), src.read(names.index("built_2020") + 1)
    east = m["land"].copy()
    east[:, : int(east.shape[1] * 0.70)] = False
    e90, e20 = float(np.nanmean(b90[east])), float(np.nanmean(b20[east]))
    need(e20 > e90, "the eastern reference zone gained built-up area")

    spec = [k for k in H.files if k.startswith("spectral_")]
    falls = [float(np.nanmin((H[k][1] - H[k][0])[act])) for k in spec]
    need(all(f < 0 for f in falls), "the largest change in each high-scenario run is a fall")
    rise = [float(np.mean((H[k][1] - H[k][0])[act] > 0.005)) for k in spec]
    dsp = H["sealed_spectral_2020"] - H["sealed_spectral_1990"]
    dgh = H["sealed_ghsl_2020"] - H["sealed_ghsl_1990"]
    allr = [s[e] for s in sc for e in ("1990", "2020")]

    from test_mf6_dupuit import run_strip
    hd, exact, _, _ = run_strip()
    dup = float(np.max(np.abs(hd - exact)))
    need(dup < 0.05, "the solver matches the Dupuit solution")

    v = {
        "date": date.today().strftime("%B %Y"),
        "land_km2": f"{R['grid']['land_km2']:.0f}", "core_km2": f"{R['grid']['core_km2']:.0f}",
        "l5_scenes": str(len(meta["sources"]["landsat5_scenes"])), "s2_scenes": str(len(meta["sources"]["sentinel2_scenes"])),
        "rain90": f"{M['grid']['rain_mean_mm_yr']['1986_1996']:,.0f}", "rain20": f"{M['grid']['rain_mean_mm_yr']['2019_2023']:,.0f}",
        "nb_basin": f1(rp["notebook"]["basin_change_pct"]), "nb_core": f1(rp["notebook"]["urban_core_change_pct"]), "nb_mean95": f"{rp['notebook']['mean_1995']:.2f}",
        "rp_basin": f1(rp["basin_change_pct"]), "rp_core": f1(rp["urban_core_change_pct"]),
        "rp_mean95": f"{rp['mean_1995']:.2f}", "rp_mean24": f"{rp['mean_2024']:.2f}",
        "perm_share": f"{R['decomposition']['share_of_mean_change_from_permeability'] * 100:.0f}",
        "rain_basin": f1(-var["rainfall_per_epoch"]["basin_change_pct"]), "rain_core": f1(var["rainfall_per_epoch"]["urban_core_change_pct"]),
        "shift_basin": f1(var["shift_from_ghsl_never_built"]["basin_change_pct"]), "shift_core": f1(var["shift_from_ghsl_never_built"]["urban_core_change_pct"]),
        "noshift_basin": f1(var["no_sensor_shift"]["basin_change_pct"]), "noshift_core": f1(var["no_sensor_shift"]["urban_core_change_pct"]),
        "notwi_basin": f1(var["without_twi_term"]["basin_change_pct"]), "notwi_core": f1(var["without_twi_term"]["urban_core_change_pct"]),
        "both_basin": f1(var["per_epoch_rain_and_ghsl_shift"]["basin_change_pct"]), "both_core": f1(var["per_epoch_rain_and_ghsl_shift"]["urban_core_change_pct"]),
        "w_core_share": f"{wc['urban_core_share_of_draws_with_decline'] * 100:.0f}", "w_basin_share": f"{wc['basin_share_of_draws_with_decline'] * 100:.0f}",
        "w_core_p5": f1(wc["urban_core_change_pct_p5_p50_p95"][0]), "w_core_p95": f1(wc["urban_core_change_pct_p5_p50_p95"][2]),
        "ghsl_blocks": f"{gh['blocks_dindex']:,}",
        "b90": f"{gh['ghsl_built_fraction_core_mean']['1990'] * 100:.0f}", "b20": f"{gh['ghsl_built_fraction_core_mean']['2020'] * 100:.0f}",
        "east_b90": f"{e90 * 100:.1f}", "east_b20": f"{e20 * 100:.1f}",
        "sand_km2": f"{gh['ndbi_high_but_not_built_km2_2024']:.0f}",
        "runs": str(2 * len(sc)), "max_disc": "0.01" if max(abs(r["percent_discrepancy"]) for r in allr) < 0.01 else "?",
        "spec_below": f"{float(np.mean((dsp < dgh)[act])) * 100:.0f}",
        "depth_lo": f"{min(r['depth_to_water_median_m'] for r in allr):.1f}", "depth_hi": f"{max(r['depth_to_water_median_m'] for r in allr):.1f}",
        "seep_lo": f"{min(r['share_to_surface_seepage'] for r in allr) * 100:.0f}", "seep_hi": f"{max(r['share_to_surface_seepage'] for r in allr) * 100:.0f}",
        "c_ghsl_lo": cm(max(ghsl_core)), "c_ghsl_hi": cm(min(ghsl_core)),
        "c_spec_lo": cm(max(p["spectral"] for p in pairs.values())), "c_spec_hi": cm(min(p["spectral"] for p in pairs.values())),
        "fall_lo": f"{abs(max(falls)):.1f}", "fall_hi": f"{abs(min(falls)):.1f}",
        "rise_lo": f"{min(rise) * 100:.0f}", "rise_hi": f"{max(rise) * 100:.0f}",
        "st_ghsl_lo": cm(max(st["ghsl"])), "st_ghsl_hi": cm(min(st["ghsl"])), "st_spec_lo": cm(max(st["spectral"])), "st_spec_hi": cm(min(st["spectral"])),
        "st_seep_lo": f"{min(c['seepage_share_2020'] for c in S['cases']) * 100:.0f}", "st_seep_hi": f"{max(c['seepage_share_2020'] for c in S['cases']) * 100:.0f}",
        "dupuit_err": f"{dup:.3f}",
        "rho_lo": f"{gh['spearman_rho_dindex_ci95_block_bootstrap'][0]:.2f}".replace("-", "−"),
        "rho_hi": f"{gh['spearman_rho_dindex_ci95_block_bootstrap'][1]:.2f}".replace("-", "−"),
        "ghsl_rho": f"{gh['spearman_rho_dindex_corrected_variant']:.2f}".replace("-", "−"),
        "rho_groups": str(gh["bootstrap_groups_3km"]),
        "rain_rise": f"{(M['grid']['rain_mean_mm_yr']['2019_2023'] / M['grid']['rain_mean_mm_yr']['1986_1996'] - 1) * 100:.0f}",
        "sg90": f"{A['sealed_fraction_mean']['ghsl']['1990'] * 100:.0f}", "sg20": f"{A['sealed_fraction_mean']['ghsl']['2020'] * 100:.0f}",
        "ss90": f"{A['sealed_fraction_mean']['spectral']['1990'] * 100:.0f}", "ss20": f"{A['sealed_fraction_mean']['spectral']['2020'] * 100:.0f}",
        "spec_falls": f"{A['sealing_falls_share_of_cells']['spectral'] * 100:.0f}",
        "so_ghsl_lo": cm(max(r["mean_core_m"] for r in so if r["sealing"] == "ghsl")), "so_ghsl_hi": cm(min(r["mean_core_m"] for r in so if r["sealing"] == "ghsl")),
        "so_spec_lo": cm(max(r["mean_core_m"] for r in so if r["sealing"] == "spectral")), "so_spec_hi": cm(min(r["mean_core_m"] for r in so if r["sealing"] == "spectral")),
        "so_rise_lo": f"{min(r['share_cells_rising'] for r in so if r['sealing'] == 'spectral') * 100:.0f}",
        "so_rise_hi": f"{max(r['share_cells_rising'] for r in so if r['sealing'] == 'spectral') * 100:.0f}",
        "spread_g": cm(max(ghsl_core) - min(ghsl_core)), "spread_s": cm(max(spec_core) - min(spec_core)),
        "seepcell_lo": f"{min(s[e]['share_cells_seeping'] for s in sc for e in ('1990', '2020')) * 100:.1f}",
        "seepcell_hi": f"{max(s[e]['share_cells_seeping'] for s in sc for e in ('1990', '2020')) * 100:.0f}",
        "cen_g": cm(cen_g), "cen_s": cm(cen_s), "nod_g": f"{abs(nod_g):.2f}", "nod_s": f"{abs(nod_s):.1f}",
        "nod_above": f"{stc[('no drains', 'ghsl')]['head_above_top_share_2020'] * 100:.0f}",
        "nod_ratio_lo": f"{min(nod_r):.0f}", "nod_ratio_hi": f"{max(nod_r):.0f}", "weak_ratio": f"{weak_r:.0f}",
        "weak_g_lo": cm(max(weak[0], weak[2])), "weak_g_hi": cm(min(weak[0], weak[2])),
        "weak_s_lo": cm(max(weak[1], weak[3])), "weak_s_hi": cm(min(weak[1], weak[3])),
    }
    need(min(rise_so) > 0.5 * min(rise) and max(rise_so) > 0.5 * max(rise), "most high-scenario rises remain with rainfall held fixed")
    need("?" not in v.values(), "budget discrepancy below 0.01 %")
    t = (ROOT / "paper" / "template.md").read_text(encoding="utf-8")
    out = re.sub(r"\{\{(\w+)\}\}", lambda mm: v[mm.group(1)], t)
    if "{{" in out:
        raise SystemExit("unfilled placeholder")
    return out


def main():
    (ROOT / "paper" / "paper.md").write_text(build(), encoding="utf-8")
    print("wrote paper/paper.md")


if __name__ == "__main__":
    main()
