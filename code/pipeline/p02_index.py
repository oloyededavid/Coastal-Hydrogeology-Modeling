"""Stage 2: reproduce the recharge-potential index (ARPI) and test how much its headline change depends on choices.

Part 1 reproduces the notebook (code/Lekki_Hydro_Study.ipynb, cells 4-5) line for line on the rebuilt inputs:
same masks, same normalisation, same weights (0.30 permeability, 0.25 slope, 0.20 "TWI", 0.15 rainfall,
0.10 vegetation), same column-cut "rural" reference for the Landsat-to-Sentinel shift, same urban-core column cut.

Part 2 changes one thing at a time and reports the effect on the basin and urban-core change:
  - rainfall per epoch (CHIRPS 1986-1996 for the baseline) instead of 2019-2023 for both epochs
  - the cross-sensor shift taken from GHSL never-built cells instead of the eastern 30 % of columns
  - no cross-sensor shift
  - the "TWI" term (a smoothed negative Laplacian, not upslope area) dropped
  - 2,000 random weight sets (flat Dirichlet) instead of the fixed weights

Part 3 checks the sealing signal against an independent record: the change in the permeability term
(1 - normalised NDBI) against the change in GHSL built-up fraction 1990-2020, on 300 m blocks.

Outputs: outputs/index_results.json, outputs/arpi_1990.tif, outputs/arpi_2024.tif (variant: per-epoch rainfall,
GHSL reference), and the arrays the figures and the model need (outputs/index_arrays.npz).

    python3 code/pipeline/p02_index.py
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import binary_closing, binary_fill_holes, gaussian_filter, label, laplace
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
CACHE, OUT = ROOT / "data_cache", ROOT / "outputs"
OUT.mkdir(exist_ok=True)
W_FIXED = np.array([0.30, 0.25, 0.20, 0.15, 0.10])  # permeability, slope, "TWI", rainfall, vegetation


def load():
    with rasterio.open(CACHE / "stack_utm31n_30m.tif") as src:
        names = list(src.descriptions)
        arr = {n: src.read(i + 1).astype("float64") for i, n in enumerate(names)}
        prof, res = src.profile, abs(src.transform.a)
    for a in arr.values():
        a[a == -9999.0] = np.nan
    return arr, prof, res


def masks(a):
    """The notebook's masks (cell 4): valid data, water, and the focus land patch around a fixed seed point."""
    dem, ndvi_24, mndwi_24 = a["dem"], a["ndvi_24"], a["mndwi_24"]
    valid = (dem > -50.0) & np.isfinite(dem) & (np.nan_to_num(ndvi_24, nan=-9) > -2.0)
    water = (np.nan_to_num(mndwi_24, nan=-9) > 0.04) | (np.nan_to_num(dem, nan=-99) <= 0.5)
    all_land = valid & ~water
    bridged = binary_closing(all_land, structure=np.ones((5, 5)))
    lab, _ = label(bridged, structure=np.ones((3, 3), int))
    r, c = int(dem.shape[0] * 0.62), int(dem.shape[1] * 0.52)
    tid = lab[r, c]
    if tid == 0:
        v, n = np.unique(lab[lab > 0], return_counts=True)
        tid = v[np.argmax(n)]
    land = binary_fill_holes(lab == tid) & all_land
    return valid, water, land


def norm(arr, mask, ref=None):
    target = ref[mask] if ref is not None else arr[mask]
    target = target[np.isfinite(target)]
    lo, hi = np.percentile(target, [2, 98])
    return np.where(mask, np.clip((arr - lo) / (hi - lo + 1e-8), 0.0, 1.0), 0.0)


def terrain_terms(a, valid, land, res):
    dem = a["dem"]
    dem_filled = np.where(valid, dem, np.nanmedian(dem[land]))
    dem_blur = gaussian_filter(dem_filled, sigma=1.2)
    gy, gx = np.gradient(dem_blur, res)
    tan_b = np.tan(np.clip(np.arctan(np.hypot(gx, gy)), np.radians(0.1), np.radians(85.0)))
    conv = gaussian_filter(-laplace(dem_blur), sigma=1.5)
    catch = np.clip(conv - np.percentile(conv[land], 5) + 1.0, 1.0, None)
    twi = np.log((catch * res) / tan_b)  # named "TWI" in the notebook; catch is a shifted Laplacian, not upslope area
    w_slope = norm(np.exp(np.clip(-np.nan_to_num(a["slope"]) / 5.0, -20, 20)), land)
    return w_slope, norm(twi, land)


def epoch_terms(a, land, ref_zone, shift=True, rain_then=False):
    """Permeability, vegetation and rainfall terms for both epochs. ref_zone: cells used for the sensor shift."""
    ndbi_24, ndvi_24, ndbi_95, ndvi_95 = a["ndbi_24"], a["ndvi_24"], a["ndbi_95"], a["ndvi_95"]
    valid_95 = np.isfinite(ndbi_95) & np.isfinite(ndvi_95) & (np.abs(ndbi_95) < 1) & (np.abs(ndvi_95) < 1) & land
    z = ref_zone & valid_95 & np.isfinite(ndbi_24) & np.isfinite(ndvi_24)
    s_ndbi = float(np.median(ndbi_24[z]) - np.median(ndbi_95[z])) if shift else 0.0
    s_ndvi = float(np.median(ndvi_24[z]) - np.median(ndvi_95[z])) if shift else 0.0
    ndbi_95c = np.where(valid_95, ndbi_95 + s_ndbi, np.median(ndbi_95[valid_95]) + s_ndbi)
    ndvi_95c = np.where(valid_95, ndvi_95 + s_ndvi, np.median(ndvi_95[valid_95]) + s_ndvi)
    t24 = dict(perm=1.0 - norm(np.nan_to_num(ndbi_24), land), veg=norm(np.nan_to_num(ndvi_24), land),
               rain=norm(a["rain_2019_2023"], land))
    t95 = dict(perm=1.0 - norm(ndbi_95c, land, ref=np.nan_to_num(ndbi_24)),
               veg=norm(ndvi_95c, land, ref=np.nan_to_num(ndvi_24)),
               rain=norm(a["rain_1986_1996"], land, ref=a["rain_2019_2023"]) if rain_then else t24["rain"])
    return t95, t24, {"ndbi_shift": round(s_ndbi, 4), "ndvi_shift": round(s_ndvi, 4), "ref_cells": int(z.sum())}


def index(t, w_slope, w_twi, w=W_FIXED):
    return w[0] * t["perm"] + w[1] * w_slope + w[2] * w_twi + w[3] * t["rain"] + w[4] * t["veg"]


def changes(i95, i24, land, core):
    basin = (i95[land].mean() - i24[land].mean()) / i95[land].mean() * 100
    urban = (i95[core].mean() - i24[core].mean()) / i95[core].mean() * 100
    return round(float(basin), 2), round(float(urban), 2)


def block_mean(a, k):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    return np.nanmean(a[:h, :w].reshape(h // k, k, w // k, k), axis=(1, 3))


def main():
    a, prof, res = load()
    valid, water, land = masks(a)
    core = land.copy()
    core[:, int(land.shape[1] * 0.45):] = False  # the notebook's "Lekki urban core": the western 45 % of columns
    cols = np.zeros_like(land)
    cols[:, int(land.shape[1] * 0.70):] = True  # the notebook's "rural reference": the eastern 30 % of columns
    w_slope, w_twi = terrain_terms(a, valid, land, res)
    R = {"grid": {"land_km2": round(float(land.sum() * res * res / 1e6), 1), "core_km2": round(float(core.sum() * res * res / 1e6), 1)}}

    # Part 1: the notebook as written
    t95, t24, sh = epoch_terms(a, land, cols)
    i95, i24 = index(t95, w_slope, w_twi), index(t24, w_slope, w_twi)
    b, u = changes(i95, i24, land, core)
    R["reproduction"] = {"basin_change_pct": b, "urban_core_change_pct": u, "mean_1995": round(float(i95[land].mean()), 4),
                         "mean_2024": round(float(i24[land].mean()), 4), "shift": sh,
                         "notebook": {"basin_change_pct": 5.16, "urban_core_change_pct": 18.14, "mean_1995": 0.4274, "mean_2024": 0.4054,
                                      "land_km2": 766.1}}
    # what drives the change: the terrain and (in the notebook) rainfall terms are identical in both epochs
    d = i95 - i24
    R["decomposition"] = {"share_of_mean_change_from_permeability": round(float((0.30 * (t95["perm"] - t24["perm"]))[land].mean() / d[land].mean()), 3),
                          "share_from_vegetation": round(float((0.10 * (t95["veg"] - t24["veg"]))[land].mean() / d[land].mean()), 3),
                          "terrain_terms_identical_in_both_epochs": True}

    # Part 2: one change at a time
    never_built = (np.nan_to_num(a["built_1990"]) < 0.01) & (np.nan_to_num(a["built_2020"]) < 0.01)
    variants = {}
    for name, kw, ref in [("rainfall_per_epoch", dict(rain_then=True), cols),
                          ("shift_from_ghsl_never_built", {}, never_built),
                          ("no_sensor_shift", dict(shift=False), cols),
                          ("per_epoch_rain_and_ghsl_shift", dict(rain_then=True), never_built)]:
        p95, p24, s = epoch_terms(a, land, ref, **kw)
        variants[name] = dict(zip(("basin_change_pct", "urban_core_change_pct"), changes(index(p95, w_slope, w_twi), index(p24, w_slope, w_twi), land, core)), shift=s)
    w_nt = W_FIXED.copy(); w_nt[2] = 0; w_nt /= w_nt.sum()
    variants["without_twi_term"] = dict(zip(("basin_change_pct", "urban_core_change_pct"), changes(index(t95, w_slope, w_twi, w_nt), index(t24, w_slope, w_twi, w_nt), land, core)))
    R["variants"] = variants

    rng = np.random.default_rng(42)
    sb, su = [], []
    lm, cm = land, core
    T95 = np.stack([t95["perm"][lm], w_slope[lm], w_twi[lm], t95["rain"][lm], t95["veg"][lm]])
    T24 = np.stack([t24["perm"][lm], w_slope[lm], w_twi[lm], t24["rain"][lm], t24["veg"][lm]])
    C95 = np.stack([t95["perm"][cm], w_slope[cm], w_twi[cm], t95["rain"][cm], t95["veg"][cm]])
    C24 = np.stack([t24["perm"][cm], w_slope[cm], w_twi[cm], t24["rain"][cm], t24["veg"][cm]])
    m95, m24, n95, n24 = T95.mean(1), T24.mean(1), C95.mean(1), C24.mean(1)
    for w in rng.dirichlet(np.ones(5), 2000):
        sb.append((w @ m95 - w @ m24) / (w @ m95) * 100)
        su.append((w @ n95 - w @ n24) / (w @ n95) * 100)
    q = lambda v: [round(float(x), 2) for x in np.percentile(v, [5, 50, 95])]
    R["weight_sensitivity"] = {"draws": 2000, "basin_change_pct_p5_p50_p95": q(sb), "urban_core_change_pct_p5_p50_p95": q(su),
                               "share_of_draws_with_basin_decline": round(float(np.mean(np.array(sb) > 0)), 3)}

    # Part 3: sealing signal against GHSL on 300 m blocks inside the land mask
    k = 10
    dperm = block_mean(np.where(land, t24["perm"] - t95["perm"], np.nan), k)
    dbuilt = block_mean(np.where(land, a["built_2020"] - a["built_1990"], np.nan), k)
    frac_land = block_mean(land.astype(float), k)
    ok = np.isfinite(dperm) & np.isfinite(dbuilt) & (frac_land > 0.8)
    rho = spearmanr(dperm[ok], dbuilt[ok])
    newly = dbuilt[ok] > 0.2
    R["ghsl_check"] = {"blocks": int(ok.sum()), "spearman_rho_dperm_vs_dbuilt": round(float(rho.statistic), 3),
                       "p": float(f"{rho.pvalue:.2e}"),
                       "mean_dperm_newly_built_blocks": round(float(dperm[ok][newly].mean()), 3),
                       "mean_dperm_other_blocks": round(float(dperm[ok][~newly].mean()), 3),
                       "ghsl_built_fraction_land_mean": {"1990": round(float(np.nanmean(a["built_1990"][land])), 4),
                                                         "2020": round(float(np.nanmean(a["built_2020"][land])), 4)},
                       "ghsl_built_fraction_core_mean": {"1990": round(float(np.nanmean(a["built_1990"][core])), 4),
                                                         "2020": round(float(np.nanmean(a["built_2020"][core])), 4)}}
    # NDBI confuses bright bare sand with built surfaces: high NDBI that GHSL does not call built
    sandlike = land & (np.nan_to_num(a["ndbi_24"], nan=-9) > 0.05) & (np.nan_to_num(a["built_2020"]) < 0.05)
    R["ghsl_check"]["ndbi_high_but_not_built_km2_2024"] = round(float(sandlike.sum() * res * res / 1e6), 1)

    # outputs for figures and the groundwater model (variant: per-epoch rainfall, GHSL shift)
    p95, p24, _ = epoch_terms(a, land, never_built, rain_then=True)
    j95, j24 = index(p95, w_slope, w_twi), index(p24, w_slope, w_twi)
    np.savez_compressed(OUT / "index_arrays.npz", land=land, water=water, core=core, valid=valid,
                        arpi_nb_95=i95.astype("float32"), arpi_nb_24=i24.astype("float32"),
                        arpi_95=j95.astype("float32"), arpi_24=j24.astype("float32"),
                        perm_95=p95["perm"].astype("float32"), perm_24=p24["perm"].astype("float32"))
    pr = dict(prof, count=1, nodata=-9999.0)
    for nm, arr in (("arpi_1990.tif", j95), ("arpi_2024.tif", j24)):
        with rasterio.open(OUT / nm, "w", **pr) as dst:
            dst.write(np.where(land, arr, -9999.0).astype("float32"), 1)
    json.dump(R, open(OUT / "index_results.json", "w"), indent=1)
    print(json.dumps(R, indent=1))


if __name__ == "__main__":
    main()
