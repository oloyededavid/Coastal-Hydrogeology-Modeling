"""Stage 3c: what the head changes of p03 are made of, and what holds the water table.

p03 compares 1990 and 2020 with each epoch's own sealing AND rainfall. This script separates them and tests the
seepage drains:
  - sealing only: every p03 parameter set rerun for 1990 with 2019-2023 rainfall, compared with the p03 2020 heads
    (outputs/modflow_heads.npz), so only the sealed fraction differs
  - the share of model cells where each sealing estimate falls between 1990 and 2020
  - no drains: the central parameters (K 15 m/day, base -30 m, c 0.35) without seepage drains, both sealing estimates,
    both epochs, so the head change can be compared with and without a water table held at the surface
  - weak drains: drain connection lengths of 1,000 and 10,000 m, low enough to approach the cell transmissivity
    (p03b tests 1-100 m, all far above it)
Output: outputs/attribution.json   (run from code/pipeline/: python3 p03c_attribution.py)
"""
import itertools
import json
import shutil
from pathlib import Path

import numpy as np

from p03_modflow import BASES, CS, KS, OUT, build, load, run

WS = Path("/tmp/lekki_mf6_c")


def fresh():
    shutil.rmtree(WS, ignore_errors=True)
    WS.mkdir()
    return WS


def main():
    a, m, _ = load()
    g = build(a, m)
    H = np.load(OUT / "modflow_heads.npz")
    core, act = g["core"], g["active"]
    res = {"sealing_falls_share_of_cells": {s: round(float(np.mean((g["sealed"][s][2020] < g["sealed"][s][1990])[act])), 3)
                                            for s in ("ghsl", "spectral")},
           "sealed_fraction_mean": {s: {str(e): round(float(g["sealed"][s][e][act].mean()), 3) for e in (1990, 2020)}
                                    for s in ("ghsl", "spectral")},
           "sealing_only": []}
    for sealing, k, base, c in itertools.product(("ghsl", "spectral"), KS, BASES, CS):
        r, h90 = run(g, k, base, c, 1990, fresh(), sealing=sealing, rain_epoch=2020)
        row = {"sealing": sealing, "k_m_day": k, "base_m": base, "c": c, "converged": r["converged"]}
        if r["converged"]:
            h20 = H[f"{sealing}_k{k:g}_b{-base:g}_c{c:g}"][1]
            dh = h20 - h90
            row.update({"mean_core_m": round(float(np.nanmean(dh[core])), 3), "share_cells_rising": round(float(np.mean(dh[act] > 0.005)), 3),
                        "percent_discrepancy": r["percent_discrepancy"]})
        res["sealing_only"].append(row)
        print(json.dumps(row), flush=True)
    for name, kw in [("no drains", {"drains": False}), ("drain length 1000 m", {"drain_len": 1000.0}),
                     ("drain length 10000 m", {"drain_len": 10000.0})]:
        for sealing in ("ghsl", "spectral"):
            rr, hh = {}, {}
            for e in (1990, 2020):
                rr[e], hh[e] = run(g, 15.0, -30.0, 0.35, e, fresh(), sealing=sealing, **kw)
            row = {"case": name, "sealing": sealing, "converged": all(rr[e]["converged"] for e in rr)}
            if row["converged"]:
                dh = hh[2020] - hh[1990]
                row.update({"core_head_change_m": round(float(np.nanmean(dh[core])), 3),
                            "head_above_top_share_2020": round(float(np.mean((hh[2020] - g["top"])[act] > 0.05)), 3),
                            "depth_to_water_median_2020_m": rr[2020]["depth_to_water_median_m"],
                            "seepage_share_2020": rr[2020]["share_to_surface_seepage"],
                            "share_core_cells_seeping_2020": rr[2020]["share_core_cells_seeping"],
                            "percent_discrepancy": max(abs(rr[e]["percent_discrepancy"]) for e in rr)})
            res.setdefault("structure", []).append(row)
            print(json.dumps(row), flush=True)
    json.dump(res, open(OUT / "attribution.json", "w"), indent=1)


if __name__ == "__main__":
    main()
