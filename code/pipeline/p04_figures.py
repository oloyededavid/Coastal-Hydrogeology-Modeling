"""Stage 4: figures for the report and the website, drawn only from the outputs of stages 1-3.

Writes figures/audit-2026-11/*.png (paper and repository) and, for the website, docs/assets/figures/*.webp plus a
*_phone.webp version of each, drawn narrower so that its text stays readable on a phone.
    python3 code/pipeline/p04_figures.py
"""
import io
import json
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap, TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[2]
CACHE, OUT = ROOT / "data_cache", ROOT / "outputs"
DOCS, REPO_FIG = ROOT / "docs" / "assets" / "figures", ROOT / "figures" / "audit-2026-11"
DOCS.mkdir(parents=True, exist_ok=True)
REPO_FIG.mkdir(parents=True, exist_ok=True)
INK, INK2, RULE, WATER, LAND = "#141412", "#55544e", "#d9d9d5", "#dfe8ef", "#f3f2ee"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.titlesize": 10, "axes.titleweight": "normal",
                     "axes.spines.top": False, "axes.spines.right": False, "savefig.facecolor": "white"})


PHONE = {"on": False}
PHONE_W = 3.8  # inches: 7-point text then stays above about 9 CSS pixels on a 390 px phone screen


def sub(*args, figsize=(6, 4), **kw):
    """plt.subplots, narrowed for the phone version (text keeps its point size, so it grows relative to the plot)."""
    if PHONE["on"]:
        f = PHONE_W / figsize[0]
        figsize = (PHONE_W, figsize[1] * max(f, 0.75))
    return plt.subplots(*args, figsize=figsize, **kw)


def wrap_(text, width=24):
    return textwrap.fill(text, width) if PHONE["on"] else text


def save(fig, name):
    from PIL import Image
    stem = name.rsplit(".", 1)[0]
    if PHONE["on"]:
        buf = io.BytesIO(); fig.savefig(buf, dpi=220, bbox_inches="tight"); buf.seek(0)
        Image.open(buf).convert("RGB").save(DOCS / f"{stem}_phone.webp", quality=82, method=6)
    else:
        fig.savefig(REPO_FIG / name, dpi=200, bbox_inches="tight")
        Image.open(REPO_FIG / name).convert("RGB").save(DOCS / f"{stem}.webp", quality=82, method=6)
    plt.close(fig)


def load_stack():
    with rasterio.open(CACHE / "stack_utm31n_30m.tif") as src:
        a = {n: src.read(i + 1).astype("float64") for i, n in enumerate(src.descriptions)}
        b = src.bounds
    for v in a.values():
        v[v == -9999.0] = np.nan
    return a, [b.left, b.right, b.bottom, b.top]


def map_frame(ax, ext, scale_km=10):
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ax.set_aspect("equal")
    for s in ax.spines.values():
        s.set_visible(True); s.set_color(RULE)
    xt = np.arange(np.ceil(ext[0] / 10000) * 10000, ext[1], 10000)
    yt = np.arange(np.ceil(ext[2] / 10000) * 10000, ext[3], 10000)
    ax.set_xticks(xt); ax.set_yticks(yt)
    ax.set_xticklabels([f"{x / 1000:.0f}" for x in xt], fontsize=7); ax.set_yticklabels([f"{y / 1000:.0f}" for y in yt], fontsize=7)
    ax.tick_params(length=2)
    x0, y0 = ext[0] + 0.03 * (ext[1] - ext[0]), ext[2] + 0.07 * (ext[3] - ext[2])
    ax.plot([x0, x0 + scale_km * 1000], [y0, y0], color=INK, lw=2.2, solid_capstyle="butt")
    ax.annotate(f"{scale_km} km", (x0 + scale_km * 500, y0), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=7, color=INK,
                bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none", alpha=0.8))
    xn, yn = ext[1] - 0.03 * (ext[1] - ext[0]), ext[3] - 0.2 * (ext[3] - ext[2])
    ax.annotate("N", xy=(xn, yn + 0.12 * (ext[3] - ext[2])), xytext=(xn, yn), ha="center", fontsize=8, color=INK,
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1))


def fig_study(a, ext, m):
    fig, ax = sub(figsize=(9, 4.4))
    ax.set_facecolor(WATER)
    base = np.where(m["valid"] & ~m["water"], 1.0, np.nan)
    ax.imshow(np.where(m["land"], np.nan, base), extent=ext, cmap=ListedColormap(["#e7e6e1"]), interpolation="nearest")
    dem = np.where(m["land"], np.clip(a["dem"], 0, 30), np.nan)
    im = ax.imshow(dem, extent=ext, cmap="Greys", vmin=-10, vmax=40, interpolation="nearest")
    core = np.where(m["core"], 1.0, np.nan)
    ax.imshow(core, extent=ext, cmap=ListedColormap(["#c2410c"]), alpha=0.18, interpolation="nearest")
    map_frame(ax, ext)
    for (x, y, t) in [(0.17, 0.80, "Lagos Lagoon"), (0.80, 0.86, "Lekki Lagoon"), (0.50, 0.08, "Atlantic Ocean (Gulf of Guinea)")]:
        ax.text(ext[0] + x * (ext[1] - ext[0]), ext[2] + y * (ext[3] - ext[2]), t, fontsize=8, style="italic", color="#3b5b75", ha="center")
    ax.set_title(wrap_("Study domain: the Lekki–Epe barrier between the lagoons and the sea (UTM 31N, km)", 44), loc="left", color=INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01); cb.set_label("Copernicus DEM (surface model), m", fontsize=7); cb.ax.tick_params(labelsize=7)
    if not PHONE["on"]:  # on a phone the caption carries this note
        ax.text(ext[0] + 0.02 * (ext[1] - ext[0]), ext[3] - 0.08 * (ext[3] - ext[2]),
            wrap_("Shaded orange: the western barrier (the earlier study's 'urban core', western 45 % of columns)", 40), fontsize=7, color="#9a3412")
    save(fig, "study_area.png")


def fig_index(ext, m, R):
    d = np.where(m["land"], m["arpi_95"] - m["arpi_24"], np.nan)
    fig, axes = sub(3, 1, figsize=(9, 10.2), constrained_layout=True)
    for ax, arr, t in ((axes[0], np.where(m["land"], m["arpi_95"], np.nan), wrap_("Recharge-potential index from 1986–1996 imagery", 40)),
                       (axes[1], np.where(m["land"], m["arpi_24"], np.nan), wrap_("Recharge-potential index from 2023–2024 imagery", 40))):
        ax.set_facecolor(WATER)
        im = ax.imshow(arr, extent=ext, cmap="YlGnBu", vmin=0.2, vmax=0.85, interpolation="nearest")
        map_frame(ax, ext); ax.set_title(t, loc="left", color=INK)
        fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01).set_label("index, 0–1", fontsize=7)
    ax = axes[2]; ax.set_facecolor(WATER)
    im = ax.imshow(d, extent=ext, cmap="RdBu_r", norm=TwoSlopeNorm(0, -0.3, 0.3), interpolation="nearest")
    map_frame(ax, ext)
    x70 = ext[0] + 0.70 * (ext[1] - ext[0])
    ax.axvline(x70, color=INK, lw=0.8, ls="--")
    ax.text(x70 + 400, ext[3] - 0.12 * (ext[3] - ext[2]), "the earlier study's\nunchanged reference\n(eastern 30 %)", fontsize=7, color=INK)
    ax.set_title(wrap_("Change in the index (red: decline, blue: rise)", 40), loc="left", color=INK)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01).set_label("earlier minus later", fontsize=7)
    save(fig, "index_maps.png")


def fig_sensitivity(R):
    rows = [("Notebook, as reported (Earth Engine inputs)", R["reproduction"]["notebook"]["basin_change_pct"], R["reproduction"]["notebook"]["urban_core_change_pct"]),
            ("Notebook method, rebuilt inputs", R["reproduction"]["basin_change_pct"], R["reproduction"]["urban_core_change_pct"])]
    lab = {"rainfall_per_epoch": "Rainfall of each epoch (1986–1996 for the baseline)",
           "shift_from_ghsl_never_built": "Sensor shift from never-built ground (GHSL)",
           "no_sensor_shift": "No sensor shift",
           "per_epoch_rain_and_ghsl_shift": "Both corrections",
           "without_twi_term": "Without the curvature term"}
    rows += [(lab[k], v["basin_change_pct"], v["urban_core_change_pct"]) for k, v in R["variants"].items()]
    ws = R["weight_sensitivity"]
    fig, ax = sub(figsize=(6.4, 4.6) if not PHONE["on"] else (6.4, 7.4))
    y = np.arange(len(rows))[::-1] + 2.5
    for yy, (t, b, u) in zip(y, rows):
        ax.plot([b, u], [yy, yy], color=RULE, lw=1, zorder=1)
        ax.scatter([b], [yy], s=26, color="#1f5fae", zorder=2); ax.scatter([u], [yy], s=26, color="#c2410c", zorder=2)
        ax.text(-0.02, yy, wrap_(t, 22), va="center", ha="right", fontsize=8, color=INK, transform=ax.get_yaxis_transform())
    for base_y, tag, label in ((1.5, "notebook_setup", "Random weights, notebook set-up (5–95 %)"), (0.5, "corrected_setup", "Random weights, both corrections (5–95 %)")):
        for dy, key, col in ((0.18, "basin_change_pct_p5_p50_p95", "#1f5fae"), (-0.18, "urban_core_change_pct_p5_p50_p95", "#c2410c")):
            p5, p50, p95 = ws[tag][key]
            ax.plot([p5, p95], [base_y + dy] * 2, color=col, lw=3, alpha=0.35, solid_capstyle="butt"); ax.scatter([p50], [base_y + dy], color=col, s=22)
        ax.text(-0.02, base_y, wrap_(label, 22), va="center", ha="right", fontsize=8, color=INK, transform=ax.get_yaxis_transform())
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_xlim(-16, 32); ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel(wrap_("Decline in the mean index between the two epochs, % (negative: rise)", 36))
    ax.scatter([], [], s=26, color="#1f5fae", label="whole barrier"); ax.scatter([], [], s=26, color="#c2410c", label="western barrier")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16 if PHONE["on"] else -0.13), ncol=2, fontsize=8, frameon=False)
    ax.set_title(wrap_("How much the headline change depends on choices in the method", 36), loc="left", color=INK)
    save(fig, "index_sensitivity.png")


def fig_ghsl(m, a):
    k = 10
    def bm(x):
        h, w = (x.shape[0] // k) * k, (x.shape[1] // k) * k
        return np.nanmean(x[:h, :w].reshape(h // k, k, w // k, k), axis=(1, 3))
    d_arpi = bm(np.where(m["land"], m["arpi_24"] - m["arpi_95"], np.nan))
    d_built = bm(np.where(m["land"], a["built_2020"] - a["built_1990"], np.nan))
    fl = bm(m["land"].astype(float))
    ok = np.isfinite(d_arpi) & np.isfinite(d_built) & (fl > 0.8)
    x, y = d_built[ok], d_arpi[ok]
    bins = np.array([-0.01, 0.02, 0.1, 0.2, 0.4, 1.0])
    idx = np.digitize(x, bins) - 1
    fig, ax = sub(figsize=(6.2, 3.4))
    data = [y[idx == i] for i in range(len(bins) - 1)]
    ax.boxplot(data, widths=0.5, showfliers=False, medianprops=dict(color="#c2410c"), boxprops=dict(color=INK2), whiskerprops=dict(color=INK2), capprops=dict(color=INK2))
    ax.set_xticklabels(["< 0.02", "0.02–0.1", "0.1–0.2", "0.2–0.4", "> 0.4"], fontsize=7 if PHONE["on"] else 9)
    for i, d_ in enumerate(data, 1):
        ax.text(i, 1.01, f"n = {len(d_)}", ha="center", va="bottom", fontsize=7, color=INK2, transform=ax.get_xaxis_transform())
    ax.axhline(0, color=RULE, lw=0.8)
    ax.set_xlabel(wrap_("Gain in GHSL built-up fraction, 1990–2020 (300 m blocks)", 36))
    ax.set_ylabel(wrap_("Change in index, later minus earlier", 24))
    ax.set_title(wrap_("The index falls where GHSL records new buildings", 34), loc="left", color=INK, pad=16)
    save(fig, "ghsl_check.png")


def fig_heads(ext_c, H, Rm):
    key = "ghsl_k15_b30_c0.35"
    if key not in H.files:
        return
    from scipy.ndimage import binary_erosion
    h90, h20 = H[key]
    act = H["active"]
    fig, axes = sub(2, 1, figsize=(9, 7.4), constrained_layout=True)
    ax = axes[0]; ax.set_facecolor(WATER)
    hh = np.where(act, h20, np.nan)
    im = ax.imshow(hh, extent=ext_c, cmap="Blues", vmin=0, vmax=6, interpolation="nearest")
    ny, nx = hh.shape
    X = ext_c[0] + (np.arange(nx) + 0.5) * 150.0; Y = ext_c[3] - (np.arange(ny) + 0.5) * 150.0  # cell centres
    cs = ax.contour(X, Y, hh, levels=[1, 2, 3, 4, 5], colors=INK, linewidths=0.4)
    if not PHONE["on"]:
        ax.clabel(cs, fontsize=6, fmt="%g m")
    gy, gx = np.gradient(hh)
    inner = binary_erosion(act, iterations=3)
    s_ = 10
    yy, xx = np.mgrid[0:ny:s_, 0:nx:s_]
    ok = inner[yy, xx] & np.isfinite(gx[yy, xx])
    u, v = -gx[yy, xx][ok], gy[yy, xx][ok]
    mag = np.hypot(u, v) + 1e-9
    ax.quiver(X[xx[ok]], Y[yy[ok]], u / mag, v / mag, color="#c2410c", scale=45, width=0.0018, headwidth=4, pivot="middle")
    map_frame(ax, ext_c)
    ax.set_title(wrap_("Water table, reference scenario (K 15 m/day, base −30 m, c 0.35, 2020). Arrows: direction of groundwater flow", 46),
                 loc="left", color=INK, fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01).set_label("Head above sea level, m", fontsize=7)
    key2 = "spectral_k15_b30_c0.35"
    ax = axes[1]; ax.set_facecolor(WATER)
    dd = (H[key2][1] - H[key2][0]) if key2 in H.files else (h20 - h90)
    im = ax.imshow(np.where(act, dd, np.nan), extent=ext_c, cmap="RdBu", norm=TwoSlopeNorm(0, -1.0, 1.0), interpolation="nearest")
    map_frame(ax, ext_c)
    ax.set_title(wrap_("Change in water table 1990 → 2020, high sealing scenario (red: fall, blue: rise)", 46), loc="left", color=INK, fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01).set_label("m", fontsize=7)
    save(fig, "heads.png")


def fig_scenarios(Rm):
    rows = [s for s in Rm["scenarios"] if "head_change_2020_minus_1990" in s]
    combos = sorted({(s["k_m_day"], s["base_m"], s["c"]) for s in rows})
    fig, ax = sub(figsize=(7.2, 3.6) if not PHONE["on"] else (7.2, 6.0))
    for i, cmb in enumerate(combos):
        for sealing, col in (("ghsl", "#1f5fae"), ("spectral", "#c2410c")):
            r = [s for s in rows if s["sealing"] == sealing and (s["k_m_day"], s["base_m"], s["c"]) == cmb][0]
            ax.scatter(r["head_change_2020_minus_1990"]["mean_core_m"], i, color=col, s=20, zorder=2)
        ax.axhline(i, color=RULE, lw=0.5, zorder=1)
    ax.set_yticks(range(len(combos)))
    ax.set_yticklabels([(f"K {k:g} · base {b:g} · c {c}" if PHONE["on"] else f"K {k:g} m/day · base {b:g} m · c {c}") for k, b, c in combos], fontsize=7)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_xlabel(wrap_("Mean change in water table in the western barrier, 1990 → 2020, m", 36))
    ax.scatter([], [], s=20, color="#1f5fae", label="GHSL buildings (likely too low)")
    ax.scatter([], [], s=20, color="#c2410c", label="high scenario (from the index)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22 if not PHONE["on"] else -0.16), ncol=1 if PHONE["on"] else 2, fontsize=8, frameon=False,
              title="Sealing from", title_fontsize=8)
    ax.set_title(wrap_("All 24 scenario pairs (sealing and rainfall both change)", 36), loc="left", color=INK, fontsize=9)
    save(fig, "scenarios.png")


def main():
    for f in DOCS.glob("*.png"):
        f.unlink()  # the website uses WebP; the PNGs live in figures/audit-2026-11/
    for phone in (False, True):
        PHONE["on"] = phone
        draw()
    print("figures written to", DOCS, "and", REPO_FIG)


def draw():
    a, ext = load_stack()
    m = np.load(OUT / "index_arrays.npz")
    R = json.load(open(OUT / "index_results.json"))
    fig_study(a, ext, m)
    fig_index(ext, m, R)
    fig_sensitivity(R)
    fig_ghsl(m, a)
    if (OUT / "modflow_heads.npz").exists():
        H = np.load(OUT / "modflow_heads.npz")
        Rm = json.load(open(OUT / "modflow_results.json"))
        ny, nx = H["active"].shape
        ext_c = [ext[0], ext[0] + nx * 150.0, ext[3] - ny * 150.0, ext[3]]
        fig_heads(ext_c, H, Rm)
        fig_scenarios(Rm)


if __name__ == "__main__":
    main()
