"""Stage 3: a steady-state MODFLOW 6 groundwater model of the Lekki-Epe barrier, run as a set of scenarios.

What this is: an UNCALIBRATED scenario model. No groundwater-level, abstraction, aquifer-test or salinity data are
available to this study, so the model cannot be calibrated or validated. It answers one bounded question: for a
plausible range of aquifer properties and recharge, how would the water table respond to the change in built-up
cover between 1990 and 2020, and which way does groundwater flow? Absolute heads are illustrative only.

What the notebook's model lacked and this one has (AUDIT-2026-11-11.md): it runs; recharge is in m/day for a model
in metres and days; the lagoons and the sea are fixed-head boundaries; cells off the barrier are inactive;
hydraulic conductivity is set (as scenarios); the top follows the land surface; seepage to the surface is allowed;
the water budget is reported. The solver settings were checked against an analytical solution
(code/pipeline/test_mf6_dupuit.py).

Grid: the 30 m study grid aggregated to 150 m (5 x 5 cells), one unconfined layer, Newton formulation.
Boundaries: water cells (MNDWI or elevation <= 0.5 m, as in the notebook) next to the active area are constant head
at 0 m (lagoon and sea level taken as mean sea level; tides and lagoon set-up are ignored).
Top: 10th percentile of the 30 m Copernicus DEM in each 150 m cell (the DEM is a surface model that includes
buildings and trees; the low percentile reduces, but does not remove, that bias).
Base: a flat aquifer base at -30 m or -60 m (scenarios; the thickness of the coastal plain sands here is not known
to this study).
Hydraulic conductivity: 5, 15 or 40 m/day (scenarios spanning clean fine-to-medium sand; not measured here).
Recharge: R = c x P x (1 - s), with P the CHIRPS mean annual rainfall of the epoch (1986-1996 or 2019-2023),
s the sealed fraction of the epoch and c the fraction of rainfall on unsealed ground that reaches the water table,
0.20 or 0.35 (scenarios; 0.35 is the notebook's coefficient). Sealed ground gives no recharge (leaking pipes and
soakaways are ignored). Two estimates of s bracket sealing:
  ghsl      GHSL built-up surface fraction, 1990 and 2020. Building footprints only, so roads and paving are
            missed: likely too low.
  spectral  1 minus the index's own permeability term (1 - normalised NDBI) for 1990 and 2024, the satellite
            signal the recharge-potential index is built on, taken at face value. NDBI also flags bare sand and the
            term is a relative 0-1 score, not a measured fraction: a high scenario, not a strict bound (in about a
            third of cells its 1990-2020 change is smaller than the GHSL change).
Seepage: a drain at the land surface in every active cell (conductance K x cell area / 10 m), so the water table
cannot rise far above the ground; drain outflow stands for discharge to swamps, channels and drainage.
Interface: an indicative fresh-salt interface depth from the Ghyben-Herzberg relation (40 x head above sea level),
which assumes a sharp interface and hydrostatic conditions.

Outputs: outputs/modflow_results.json, outputs/modflow_heads.npz (heads per scenario), and the model files of the
central scenario in outputs/mf6_central/ (not committed; rebuilt by this script).

    python3 code/pipeline/p03_modflow.py
"""
import itertools
import json
import os
import shutil
from pathlib import Path

import flopy
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
CACHE, OUT = ROOT / "data_cache", ROOT / "outputs"
MF6 = os.environ.get("MF6_EXE", "/home/user/tools/mf6/pkg/bin/mf6")
F = 5  # 30 m -> 150 m
KS = [5.0, 15.0, 40.0]
BASES = [-30.0, -60.0]
CS = [0.20, 0.35]
CENTRAL = dict(k=15.0, base=-30.0, c=0.35)


def coarse(a, func=np.nanmean):
    h, w = (a.shape[0] // F) * F, (a.shape[1] // F) * F
    b = a[:h, :w].reshape(h // F, F, w // F, F).transpose(0, 2, 1, 3).reshape(h // F, w // F, F * F)
    return func(b, axis=2)


def load():
    with rasterio.open(CACHE / "stack_utm31n_30m.tif") as src:
        a = {n: src.read(i + 1).astype("float64") for i, n in enumerate(src.descriptions)}
        res = abs(src.transform.a)
    for v in a.values():
        v[v == -9999.0] = np.nan
    m = np.load(OUT / "index_arrays.npz")
    return a, m, res


def build(a, m, top_pct=10):
    land, water, core = m["land"].astype(float), m["water"].astype(float), m["core"].astype(float)
    fl, fw, fc = coarse(land), coarse(water), coarse(core)
    active = fl >= 0.5
    # constant-head water cells: mostly water and touching the active area (8-neighbours)
    from scipy.ndimage import binary_dilation
    chd = (fw >= 0.5) & ~active & binary_dilation(active, structure=np.ones((3, 3)))
    idomain = np.where(active | chd, 1, 0).astype(int)
    dem = np.where(m["land"], a["dem"], np.nan)
    top = coarse(dem, lambda x, axis: np.nanpercentile(x, top_pct, axis=axis))
    top = np.where(np.isfinite(top), top, 0.5)
    top = np.where(chd, 0.0, np.maximum(top, 0.2))
    built = {1990: coarse(np.nan_to_num(a["built_1990"])), 2020: coarse(np.nan_to_num(a["built_2020"]))}
    perm = {1990: coarse(np.where(m["land"], m["perm_95"], np.nan)), 2020: coarse(np.where(m["land"], m["perm_24"], np.nan))}
    spectral = {e: np.clip(1.0 - np.nan_to_num(v, nan=1.0), 0, 1) for e, v in perm.items()}
    rain = {1990: coarse(a["rain_1986_1996"]), 2020: coarse(a["rain_2019_2023"])}
    return dict(active=active, chd=chd, idomain=idomain, top=top, rain=rain, core=(fc >= 0.5) & active,
                sealed={"ghsl": built, "spectral": spectral})


def run(g, k, base, c, epoch, ws, keep=False, sealing="ghsl", drain_len=10.0, drain_depth=0.0, rain_epoch=None, drains=True):
    """One steady-state run. rain_epoch: take rainfall from another epoch (to separate sealing from rainfall);
    drains=False removes the seepage drains (to test how much they hold the water table)."""
    nrow, ncol = g["idomain"].shape
    d = 30.0 * F
    sim = flopy.mf6.MFSimulation(sim_name="lekki", exe_name=MF6, sim_ws=str(ws))
    flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[(1.0, 1, 1.0)], time_units="DAYS")
    flopy.mf6.ModflowIms(sim, complexity="COMPLEX", outer_dvclose=1e-5, inner_dvclose=1e-6, outer_maximum=400,
                         inner_maximum=500, linear_acceleration="BICGSTAB", under_relaxation="DBD")
    gwf = flopy.mf6.ModflowGwf(sim, modelname="lekki", newtonoptions="NEWTON UNDER_RELAXATION", save_flows=True)
    flopy.mf6.ModflowGwfdis(gwf, nlay=1, nrow=nrow, ncol=ncol, delr=d, delc=d, top=g["top"], botm=base,
                            idomain=g["idomain"], length_units="METERS")
    flopy.mf6.ModflowGwfic(gwf, strt=np.where(g["chd"], 0.0, np.maximum(g["top"] - 0.5, 0.1)))
    flopy.mf6.ModflowGwfnpf(gwf, icelltype=1, k=k)
    flopy.mf6.ModflowGwfsto(gwf, steady_state={0: True}, iconvert=1)
    flopy.mf6.ModflowGwfchd(gwf, stress_period_data=[[(0, r, cc), 0.0] for r, cc in zip(*np.where(g["chd"]))])
    rch_mmyr = c * g["rain"][rain_epoch or epoch] * (1.0 - g["sealed"][sealing][epoch])
    rch = np.where(g["active"], rch_mmyr / 1000.0 / 365.25, 0.0)
    flopy.mf6.ModflowGwfrcha(gwf, recharge=rch[None, :, :][0])
    cond = k * d * d / drain_len  # surface leakance: K x cell area over a connection length (10 m by default)
    # a drain is never set below the 0 m lagoon and sea level, so lowering drains cannot create sinks below sea level
    if drains:
        flopy.mf6.ModflowGwfdrn(gwf, stress_period_data=[[(0, r, cc), max(g["top"][r, cc] - drain_depth, 0.0), cond] for r, cc in zip(*np.where(g["active"]))])
    flopy.mf6.ModflowGwfoc(gwf, head_filerecord="lekki.hds", budget_filerecord="lekki.bud",
                           saverecord=[("HEAD", "ALL"), ("BUDGET", "ALL")])
    sim.write_simulation(silent=True)
    ok, buff = sim.run_simulation(silent=True)
    lst = (Path(ws) / "lekki.lst").read_text()
    disc = None
    for line in lst.splitlines():
        if "PERCENT DISCREPANCY" in line:
            disc = float(line.split("=")[-1].split()[0])
    if not ok:
        return {"converged": False}, None
    h = gwf.output.head().get_data()[0]
    h = np.where(g["active"], h, np.nan)
    bud = gwf.output.budget()
    q = {t: float(bud.get_data(text=t)[0]["q"].sum()) for t in ("RCH", "CHD") + (("DRN",) if drains else ())}
    q.setdefault("DRN", 0.0)
    area_km2 = g["active"].sum() * d * d / 1e6
    out = {"converged": True, "percent_discrepancy": disc,
           "recharge_mean_mm_yr": round(float(rch_mmyr[g["active"]].mean()), 1),
           "budget_m3_day": {k_: round(v, 1) for k_, v in q.items()},
           "share_to_lagoon_and_sea": round(-q["CHD"] / q["RCH"], 3), "share_to_surface_seepage": round(-q["DRN"] / q["RCH"], 3),
           "head_mean_m": round(float(np.nanmean(h)), 3), "head_max_m": round(float(np.nanmax(h)), 3),
           "head_mean_core_m": round(float(np.nanmean(h[g["core"]])), 3),
           "depth_to_water_median_m": round(float(np.nanmedian(g["top"][g["active"]] - h[g["active"]])), 2),
           "share_cells_seeping": round(float(np.mean((g["top"] - h)[g["active"]] < 0.05)), 3),
           "share_core_cells_seeping": round(float(np.mean((g["top"] - h)[g["core"]] < 0.05)), 3),
           "interface_depth_median_m_ghyben_herzberg": round(float(np.nanmedian(40 * np.clip(h[g["active"]], 0, None))), 1),
           "active_km2": round(float(area_km2), 1)}
    if keep:
        shutil.copytree(ws, OUT / "mf6_central", dirs_exist_ok=True)
    return out, h


def main():
    a, m, res = load()
    g = build(a, m)
    results = {"grid": {"cell_m": 30 * F, "rows": int(g["idomain"].shape[0]), "cols": int(g["idomain"].shape[1]),
                        "active_cells": int(g["active"].sum()), "constant_head_cells": int(g["chd"].sum()),
                        "sealed_fraction_mean": {s_: {str(e): round(float(g["sealed"][s_][e][g["active"]].mean()), 4) for e in (1990, 2020)}
                                                 for s_ in ("ghsl", "spectral")},
                        "rain_mean_mm_yr": {"1986_1996": round(float(np.nanmean(g["rain"][1990][g["active"]])), 1),
                                            "2019_2023": round(float(np.nanmean(g["rain"][2020][g["active"]])), 1)}},
               "scenarios": []}
    heads = {}
    ws = Path("/tmp/lekki_mf6")
    for sealing, k, base, c in itertools.product(("ghsl", "spectral"), KS, BASES, CS):
        row = {"sealing": sealing, "k_m_day": k, "base_m": base, "c": c}
        hs = {}
        for epoch in (1990, 2020):
            if ws.exists():
                shutil.rmtree(ws)
            ws.mkdir()
            central = dict(k=k, base=base, c=c) == CENTRAL and epoch == 2020 and sealing == "ghsl"
            r, h = run(g, k, base, c, epoch, ws, keep=central, sealing=sealing)
            row[str(epoch)] = r
            hs[epoch] = h
            print(sealing, k, base, c, epoch, r.get("converged"), r.get("percent_discrepancy"), r.get("head_mean_m"), flush=True)
        if hs[1990] is not None and hs[2020] is not None:
            dh = hs[2020] - hs[1990]
            row["head_change_2020_minus_1990"] = {"mean_m": round(float(np.nanmean(dh)), 3), "mean_core_m": round(float(np.nanmean(dh[g["core"]])), 3),
                                                  "p5_m": round(float(np.nanpercentile(dh, 5)), 3)}
            heads[f"{sealing}_k{k:g}_b{-base:g}_c{c:g}"] = np.stack([hs[1990], hs[2020]]).astype("float32")
        results["scenarios"].append(row)
    np.savez_compressed(OUT / "modflow_heads.npz", top=g["top"].astype("float32"), active=g["active"], chd=g["chd"], core=g["core"],
                        sealed_ghsl_1990=g["sealed"]["ghsl"][1990].astype("float32"), sealed_ghsl_2020=g["sealed"]["ghsl"][2020].astype("float32"),
                        sealed_spectral_1990=g["sealed"]["spectral"][1990].astype("float32"), sealed_spectral_2020=g["sealed"]["spectral"][2020].astype("float32"), **heads)
    json.dump(results, open(OUT / "modflow_results.json", "w"), indent=1)
    print(json.dumps(results["grid"], indent=1))


if __name__ == "__main__":
    main()
