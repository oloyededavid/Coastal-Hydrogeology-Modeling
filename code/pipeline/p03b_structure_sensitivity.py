"""Stage 3b: how much the model's structure, not its aquifer properties, controls the result.

The 48 runs of p03 vary conductivity, aquifer base and recharge fraction, and the head change in the western core
barely moves. That points to a water table held near the land surface by the seepage drains. This script varies
what p03 kept fixed, for the central parameters (K 15 m/day, base -30 m, c 0.35) and both sealing estimates:
  - drain connection length 1, 10 (p03 default) and 100 m (conductance K x cell area / length)
  - drain elevation at the model top (default), 0.5 m and 1.0 m below it
  - model top from the 2nd, 10th (default) or 50th percentile of the 30 m surface model in each 150 m cell
Each run uses present-day topography and the present-day land and water masks for both epochs, as p03 does: the
comparison is "today's terrain with 1990 sealing" against "today's terrain with 2020 sealing".
Output: outputs/structure_sensitivity.json
    python3 code/pipeline/p03b_structure_sensitivity.py
"""
import json
import shutil
from pathlib import Path

import numpy as np

from p03_modflow import OUT, build, load, run

CASES = [("default", {}, 10), ("drain length 1 m", {"drain_len": 1.0}, 10), ("drain length 100 m", {"drain_len": 100.0}, 10),
         ("drain 0.5 m below top", {"drain_depth": 0.5}, 10), ("drain 1.0 m below top", {"drain_depth": 1.0}, 10),
         ("top = 2nd percentile", {}, 2), ("top = 50th percentile", {}, 50)]


def main():
    a, m, _ = load()
    rows, grids = [], {}
    ws = Path("/tmp/lekki_mf6_s")
    for name, kw, pct in CASES:
        if pct not in grids:
            grids[pct] = build(a, m, top_pct=pct)
        g = grids[pct]
        for sealing in ("ghsl", "spectral"):
            hs, res = {}, {}
            for epoch in (1990, 2020):
                shutil.rmtree(ws, ignore_errors=True); ws.mkdir()
                r, h = run(g, 15.0, -30.0, 0.35, epoch, ws, sealing=sealing, **kw)
                hs[epoch], res[epoch] = h, r
            row = {"case": name, "sealing": sealing, "converged": all(res[e]["converged"] for e in res)}
            if row["converged"]:
                dh = hs[2020] - hs[1990]
                row.update({"core_head_change_m": round(float(np.nanmean(dh[g["core"]])), 3),
                            "head_mean_2020_m": res[2020]["head_mean_m"], "seepage_share_2020": res[2020]["share_to_surface_seepage"],
                            "percent_discrepancy": max(abs(res[e]["percent_discrepancy"]) for e in res)})
            rows.append(row)
            print(json.dumps(row), flush=True)
    # the specific check quoted in the audit: K 40, base -60, c 0.2, GHSL, 2020, drain length 1 m vs 10 m
    g = grids[10]
    chk = {}
    for L in (1.0, 10.0):
        shutil.rmtree(ws, ignore_errors=True); ws.mkdir()
        r, _ = run(g, 40.0, -60.0, 0.2, 2020, ws, sealing="ghsl", drain_len=L)
        chk[f"drain_length_{L:g}m_head_mean_m"] = r["head_mean_m"]
    json.dump({"central": {"k_m_day": 15.0, "base_m": -30.0, "c": 0.35}, "cases": rows, "k40_b60_c0.2_ghsl_2020": chk},
              open(OUT / "structure_sensitivity.json", "w"), indent=1)


if __name__ == "__main__":
    main()
