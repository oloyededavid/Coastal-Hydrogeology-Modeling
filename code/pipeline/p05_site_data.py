"""Stage 5: collect every number the website shows into docs/data/site.json, from the stage 2 and 3 outputs.
The page (docs/index.html) fills its numbers from this file; none is typed into the page.
    python3 code/pipeline/p05_site_data.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"


def pct(x):
    return f"{x:.1f}"


def main():
    R = json.load(open(OUT / "index_results.json"))
    M = json.load(open(OUT / "modflow_results.json"))
    meta = json.load(open(ROOT / "data_cache" / "stack_meta.json"))
    rp, var, ws, gh = R["reproduction"], R["variants"], R["weight_sensitivity"], R["ghsl_check"]
    sc = [s for s in M["scenarios"] if "head_change_2020_minus_1990" in s]
    by = {s_: [s for s in sc if s["sealing"] == s_] for s_ in ("ghsl", "spectral")}
    core = {s_: [s["head_change_2020_minus_1990"]["mean_core_m"] for s in v] for s_, v in by.items()}
    p5 = {s_: [s["head_change_2020_minus_1990"]["p5_m"] for s in v] for s_, v in by.items()}
    allr = [s[e] for s in sc for e in ("1990", "2020")]
    central = [s for s in by["ghsl"] if (s["k_m_day"], s["base_m"], s["c"]) == (15.0, -30.0, 0.35)][0]["2020"]
    cm = lambda v: f"{abs(v) * 100:.0f}"
    import numpy as np
    H = np.load(OUT / "modflow_heads.npz")
    act = H["active"]
    spec = [k for k in H.files if k.startswith("spectral_")]
    falls = [float(np.nanmin((H[k][1] - H[k][0])[act])) for k in spec]
    rise = [float(np.mean((H[k][1] - H[k][0])[act] > 0.005)) for k in spec]
    dsp = H["sealed_spectral_2020"] - H["sealed_spectral_1990"]
    dgh = H["sealed_ghsl_2020"] - H["sealed_ghsl_1990"]
    below = float(np.mean((dsp < dgh)[act]))
    S = json.load(open(OUT / "structure_sensitivity.json"))
    st = {s_: [c["core_head_change_m"] for c in S["cases"] if c["sealing"] == s_ and c["converged"]] for s_ in ("ghsl", "spectral")}
    wc = ws["corrected_setup"]
    v = {
        "landKm2": f"{R['grid']['land_km2']:.0f}", "coreKm2": f"{R['grid']['core_km2']:.0f}",
        "s2Scenes": str(len(meta["sources"]["sentinel2_scenes"])), "l5Scenes": str(len(meta["sources"]["landsat5_scenes"])),
        "nbBasin": pct(rp["notebook"]["basin_change_pct"]), "nbCore": pct(rp["notebook"]["urban_core_change_pct"]),
        "rpBasin": pct(rp["basin_change_pct"]), "rpCore": pct(rp["urban_core_change_pct"]),
        "rpMean95": f"{rp['mean_1995']:.2f}", "rpMean24": f"{rp['mean_2024']:.2f}", "nbMean95": f"{rp['notebook']['mean_1995']:.2f}",
        "rainBasin": pct(-var["rainfall_per_epoch"]["basin_change_pct"]), "rainCore": pct(var["rainfall_per_epoch"]["urban_core_change_pct"]),
        "noTwiCore": f"{var['without_twi_term']['urban_core_change_pct']:.0f}",
        "bothBasin": pct(var["per_epoch_rain_and_ghsl_shift"]["basin_change_pct"]), "bothCore": pct(var["per_epoch_rain_and_ghsl_shift"]["urban_core_change_pct"]),
        "wCoreShare": f"{wc['urban_core_share_of_draws_with_decline'] * 100:.0f}", "wBasinShare": f"{wc['basin_share_of_draws_with_decline'] * 100:.0f}",
        "wCoreP5": pct(wc["urban_core_change_pct_p5_p50_p95"][0]), "wCoreP95": pct(wc["urban_core_change_pct_p5_p50_p95"][2]),
        "wCoreP50": pct(wc["urban_core_change_pct_p5_p50_p95"][1]),
        "permShare": f"{R['decomposition']['share_of_mean_change_from_permeability'] * 100:.0f}",
        "ghslRho": f"{gh['spearman_rho_dperm_vs_dbuilt']:.2f}".replace("-", "−"), "ghslBlocks": f"{gh['blocks']:,}",
        "built90": f"{gh['ghsl_built_fraction_core_mean']['1990'] * 100:.0f}", "built20": f"{gh['ghsl_built_fraction_core_mean']['2020'] * 100:.0f}",
        "sandKm2": f"{gh['ndbi_high_but_not_built_km2_2024']:.0f}",
        "rain90": f"{M['grid']['rain_mean_mm_yr']['1986_1996']:,.0f}", "rain20": f"{M['grid']['rain_mean_mm_yr']['2019_2023']:,.0f}",
        "runs": str(2 * len(sc)), "maxDisc": f"{max(abs(r['percent_discrepancy']) for r in allr):.2f}",
        "activeKm2": f"{allr[0]['active_km2']:.0f}",
        "coreGhslMin": cm(max(core["ghsl"])), "coreGhslMax": cm(min(core["ghsl"])),
        "coreSpecMin": cm(max(core["spectral"])), "coreSpecMax": cm(min(core["spectral"])),
        "specBelowGhsl": f"{below * 100:.0f}",
        "fallSpecMin": f"{abs(max(falls)):.1f}", "fallSpecMax": f"{abs(min(falls)):.1f}",
        "riseSpecMin": f"{min(rise) * 100:.0f}", "riseSpecMax": f"{max(rise) * 100:.0f}",
        "stGhslMin": cm(max(st["ghsl"])), "stGhslMax": cm(min(st["ghsl"])), "stSpecMin": cm(max(st["spectral"])), "stSpecMax": cm(min(st["spectral"])),
        "stSeepMin": f"{min(c['seepage_share_2020'] for c in S['cases'] if c['converged']) * 100:.0f}",
        "stSeepMax": f"{max(c['seepage_share_2020'] for c in S['cases'] if c['converged']) * 100:.0f}",
        "depthMin": f"{min(r['depth_to_water_median_m'] for r in allr):.1f}", "depthMax": f"{max(r['depth_to_water_median_m'] for r in allr):.1f}",
        "seepMin": f"{min(r['share_to_surface_seepage'] for r in allr) * 100:.0f}", "seepMax": f"{max(r['share_to_surface_seepage'] for r in allr) * 100:.0f}",
        "cHeadMean": f"{central['head_mean_m']:.1f}", "cHeadMax": f"{central['head_max_m']:.1f}",
    }
    (ROOT / "docs" / "data").mkdir(parents=True, exist_ok=True)
    json.dump({"values": v, "sources": ["outputs/index_results.json", "outputs/modflow_results.json", "outputs/modflow_heads.npz", "outputs/structure_sensitivity.json", "data_cache/stack_meta.json"]},
              open(ROOT / "docs" / "data" / "site.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(v, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
