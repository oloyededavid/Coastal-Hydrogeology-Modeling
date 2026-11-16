"""Stage 1: rebuild the notebook's input stack without Earth Engine.

The original notebook (code/Lekki_Hydro_Study.ipynb, cell 2) exported an 8-band GeoTIFF from Google Earth Engine to
Google Drive. That file is not in the repository, so the analysis could not be re-run. This script rebuilds the
same layers from the same source products, read from Microsoft Planetary Computer and the data providers, on the
same grid: bounding box 3.45-4.05 E, 6.40-6.65 N, WGS 84 / UTM zone 31N (EPSG:32631), 30 m.

Layers (same definitions as the notebook unless stated):
  dem        Copernicus DEM GLO-30 (a digital SURFACE model: buildings and trees are included)
  slope      degrees, from the 30 m DEM by finite differences (the notebook used ee.Terrain.slope)
  ndvi_24, ndbi_24, mndwi_24
             Sentinel-2 L2A, 1 Nov 2023 - 31 Mar 2024, scene cloud < 25 %, SCL classes 4-7 kept, per-band median
  ndvi_95, ndbi_95
             Landsat-5 TM Collection 2 Level 2, 1986-1996, November-March, QA cloud and shadow masked,
             per-band median, gaps filled with an 8-pixel focal mean (as in the notebook)
  rain_2019_2023  CHIRPS v2.0 mean annual total 2019-2023 (mm/yr), bilinear to 30 m (as in the notebook)
  rain_1986_1996  CHIRPS v2.0 mean annual total 1986-1996 (mm/yr) - NEW: rainfall for the baseline epoch
  built_1990, built_2020
             GHSL GHS-BUILT-S R2023A (3 arc-second), built-up surface fraction of each cell - NEW: an independent
             record of built-up area, used only to check the satellite sealing signal

Output: data_cache/stack_utm31n_30m.tif (float32, nodata -9999) and data_cache/stack_meta.json.
data_cache/ is not committed (see .gitignore); re-running this script rebuilds it.

    python3 code/pipeline/p01_inputs.py
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data_cache"
CACHE.mkdir(exist_ok=True)
BBOX = (3.45, 6.40, 4.05, 6.65)
CRS = "EPSG:32631"
RES = 30.0

left, bottom, right, top = transform_bounds("EPSG:4326", CRS, *BBOX, densify_pts=21)
left, bottom = np.floor(left / RES) * RES, np.floor(bottom / RES) * RES
right, top = np.ceil(right / RES) * RES, np.ceil(top / RES) * RES
W, H = int(round((right - left) / RES)), int(round((top - bottom) / RES))
TRANSFORM = from_origin(left, top, RES, RES)
GRID = dict(crs=CRS, transform=TRANSFORM, width=W, height=H)

os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.TIF,.tiff")


def read_to_grid(href, resampling=Resampling.bilinear, src_nodata=None, band=1, retries=4):
    """Read one band of a remote raster, warped onto the target grid. Returns float32 with NaN for no data."""
    for k in range(retries):
        try:
            with rasterio.open(href) as src:
                nd = src_nodata if src_nodata is not None else src.nodata
                with WarpedVRT(src, **GRID, resampling=resampling, src_nodata=nd, nodata=np.nan,
                               dtype="float32") as vrt:
                    return vrt.read(band).astype("float32")
        except Exception as e:  # network hiccups on large remote reads
            if k == retries - 1:
                raise
            print(f"  retry {k + 1} after {type(e).__name__}: {str(e)[:120]}", flush=True)
            time.sleep(3 * (k + 1))


def catalog():
    return pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)


def dem_layers(cat):
    items = list(cat.search(collections=["cop-dem-glo-30"], bbox=BBOX).items())
    dem = np.full((H, W), np.nan, "float32")
    for it in items:
        a = read_to_grid(it.assets["data"].href)
        dem = np.where(np.isnan(dem), a, dem)
    gy, gx = np.gradient(np.where(np.isnan(dem), 0.0, dem), RES)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")
    slope[np.isnan(dem)] = np.nan
    return dem, slope, [it.id for it in items]


def median_composite(items, bands, mask_fn, scale_fn, label):
    """Per-band median over the scenes, using a per-scene mask. Bands are read onto the 30 m grid."""
    stacks = {b: [] for b in bands}
    used = []
    scene_dir = CACHE / "scenes"
    scene_dir.mkdir(exist_ok=True)
    for i, it in enumerate(items):
        f = scene_dir / f"{it.id}.npz"  # per-scene cache, so an interrupted run resumes where it stopped
        if f.exists():
            z = np.load(f)
            if "empty" in z.files:
                continue
            m, vals = z["mask"], {b: z[b] for b in bands}
        else:
            try:
                m = mask_fn(it)
                if m is None or not np.any(m):
                    np.savez(f, empty=np.array([1]))
                    continue
                vals = {b: scale_fn(read_to_grid(it.assets[b].href, Resampling.average)) for b in bands}
            except Exception as e:
                print(f"  {label}: skipped {it.id}: {str(e)[:100]}", flush=True)
                continue
            np.savez_compressed(f, mask=m, **vals)
        for b in bands:
            v = vals[b]
            v[~m] = np.nan
            stacks[b].append(v)
        used.append(it.id)
        print(f"  {label}: {i + 1}/{len(items)} {it.id} clear {np.mean(m):.2f}", flush=True)
    out = {b: np.nanmedian(np.stack(stacks[b]), axis=0).astype("float32") for b in bands}
    return out, used


def s2_layers(cat):
    items = list(cat.search(collections=["sentinel-2-l2a"], bbox=BBOX, datetime="2023-11-01/2024-03-31",
                            query={"eo:cloud_cover": {"lt": 25}}).items())
    # Processing baseline 04.00 and later (all scenes from 2022) store L2A reflectance with a +1000 offset
    # (BOA_ADD_OFFSET = -1000). Earth Engine's S2_SR_HARMONIZED removes it; here it is removed explicitly.
    baselines = sorted({it.properties.get("s2:processing_baseline") for it in items})
    if any(b is None or float(b) < 4.0 for b in baselines):
        sys.exit(f"unexpected Sentinel-2 processing baselines {baselines}: the offset rule would not hold for all scenes")

    def mask(it):
        scl = read_to_grid(it.assets["SCL"].href, Resampling.nearest)
        return (scl >= 4) & (scl <= 7)

    def scale(a):
        return np.clip((a - 1000.0) / 10000.0, 0.0001, 1.0)

    out, used = median_composite(items, ["B03", "B04", "B08", "B11"], mask, scale, "S2")
    return out, used, baselines


def l5_layers(cat):
    items = [it for it in cat.search(collections=["landsat-c2-l2"], bbox=BBOX, datetime="1986-01-01/1996-12-31",
                                     query={"platform": {"eq": "landsat-5"}}).items()
             if it.datetime.month in (11, 12, 1, 2, 3)]

    def mask(it):
        qa = read_to_grid(it.assets["qa_pixel"].href, Resampling.nearest)
        q = np.nan_to_num(qa, nan=1).astype("uint16")
        return ((q & (1 << 3)) == 0) & ((q & (1 << 4)) == 0) & (q != 1) & ~np.isnan(qa)

    def scale(a):
        return np.clip(a * 0.0000275 - 0.2, 0.0001, 1.0)

    out, used = median_composite(items, ["green", "red", "nir08", "swir16"], mask, scale, "L5")
    return out, used


def focal_fill(a, radius=8):
    """Fill NaN with the mean of valid pixels within a circular radius (the notebook's focalMean(8, 'circle'))."""
    from scipy.ndimage import convolve
    yy, xx = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    k = ((xx ** 2 + yy ** 2) <= radius ** 2).astype("float32")
    v = np.isfinite(a)
    s = convolve(np.where(v, a, 0.0), k, mode="nearest")
    n = convolve(v.astype("float32"), k, mode="nearest")
    fill = np.where(n > 0, s / np.maximum(n, 1e-9), np.nan)
    return np.where(v, a, fill).astype("float32")


def nd(a, b):
    with np.errstate(invalid="ignore", divide="ignore"):
        return ((a - b) / (a + b)).astype("float32")


def chirps_mean(years):
    acc = []
    for y in years:
        href = f"/vsicurl/https://data.chc.ucsb.edu/products/CHIRPS/v2.0/global_annual/tifs/chirps-v2.0.{y}.tif"
        acc.append(read_to_grid(href, Resampling.bilinear, src_nodata=-9999))
        print(f"  CHIRPS {y}", flush=True)
    return np.mean(np.stack(acc), axis=0).astype("float32")


def ghsl_fraction(epoch):
    f = CACHE / "ghsl" / f"GHS_BUILT_S_E{epoch}_GLOBE_R2023A_4326_3ss_V1_0_R9_C19.tif"
    if not f.exists():
        sys.exit(f"missing {f}: download the GHSL R9_C19 tile for {epoch} (see research/audit-2026-11-16/PROGRESS.md)")
    with rasterio.open(f) as src:
        with WarpedVRT(src, **GRID, resampling=Resampling.average, src_nodata=65535, nodata=np.nan,
                       dtype="float32") as vrt:
            m2 = vrt.read(1)
    # GHS-BUILT-S is square metres of built-up surface per 3-arc-second cell (about 92 x 92 m here);
    # averaged onto 30 m cells it stays m2 per source cell, so divide by the source cell area.
    lat = np.radians(6.525)
    cell_m2 = (3 / 3600 * 111320.0) * (3 / 3600 * 111320.0 * np.cos(lat))
    return np.clip(m2 / cell_m2, 0, 1).astype("float32")


def main():
    t0 = time.time()
    print(f"grid {W} x {H} at {RES} m, {CRS}", flush=True)
    cat = catalog()
    dem, slope, dem_ids = dem_layers(cat)
    print("DEM done", flush=True)
    s2, s2_ids, s2_baselines = s2_layers(cat)
    ndvi_24, ndbi_24, mndwi_24 = nd(s2["B08"], s2["B04"]), nd(s2["B11"], s2["B08"]), nd(s2["B03"], s2["B11"])
    print("S2 done", flush=True)
    l5, l5_ids = l5_layers(cat)
    l5f = {b: focal_fill(v) for b, v in l5.items()}
    ndvi_95, ndbi_95 = nd(l5f["nir08"], l5f["red"]), nd(l5f["swir16"], l5f["nir08"])
    print("L5 done", flush=True)
    cat = catalog()  # fresh signatures
    rain_now = chirps_mean(range(2019, 2024))
    rain_then = chirps_mean(range(1986, 1997))
    b90, b20 = ghsl_fraction(1990), ghsl_fraction(2020)
    names = ["dem", "slope", "ndvi_24", "ndbi_24", "mndwi_24", "ndvi_95", "ndbi_95", "rain_2019_2023",
             "rain_1986_1996", "built_1990", "built_2020"]
    layers = [dem, slope, ndvi_24, ndbi_24, mndwi_24, ndvi_95, ndbi_95, rain_now, rain_then, b90, b20]
    prof = dict(driver="GTiff", dtype="float32", count=len(layers), nodata=-9999.0, compress="deflate",
                predictor=3, tiled=True, **GRID)
    with rasterio.open(CACHE / "stack_utm31n_30m.tif", "w", **prof) as dst:
        for i, (n, a) in enumerate(zip(names, layers), 1):
            dst.write(np.where(np.isfinite(a), a, -9999.0).astype("float32"), i)
            dst.set_band_description(i, n)
    meta = {"bands": names, "grid": {"crs": CRS, "res_m": RES, "width": W, "height": H,
                                     "bounds": [left, bottom, right, top]},
            "sources": {"dem": dem_ids, "sentinel2_scenes": s2_ids, "sentinel2_processing_baselines": s2_baselines, "landsat5_scenes": l5_ids,
                        "chirps": "CHIRPS v2.0 global_annual tifs, 1986-1996 and 2019-2023",
                        "ghsl": "GHS-BUILT-S R2023A 4326 3ss, tile R9_C19, epochs 1990 and 2020"},
            "seconds": round(time.time() - t0)}
    json.dump(meta, open(CACHE / "stack_meta.json", "w"), indent=1)
    print(f"wrote {CACHE / 'stack_utm31n_30m.tif'} in {meta['seconds']} s; S2 scenes {len(s2_ids)}, L5 scenes {len(l5_ids)}")


if __name__ == "__main__":
    main()
