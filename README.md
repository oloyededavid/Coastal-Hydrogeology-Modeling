# Urban sealing and groundwater on the Lekki–Epe barrier, Lagos

**Author:** David Oloyede · **Status:** re-analysis, November 2026 (working branch `research-audit`, not yet published) · **Licence:** MIT

How much has the land surface of the Lekki–Epe barrier sealed over since the late 1980s, how reliable is the satellite evidence, and what could that sealing do to the shallow water table beneath it?

The barrier lies between the Lagos and Lekki lagoons and the Atlantic Ocean. This repository holds two versions of the work:

- **The re-analysis (current).** Scripts in [`code/pipeline/`](code/pipeline/) rebuild all inputs from open data, reproduce the original recharge-potential index, test how much its result depends on each choice, check it against an independent built-up map, and run a MODFLOW 6 groundwater model as a set of scenarios. A preview page is in [`docs/`](docs/).
- **The original study (superseded, kept for the record).** The Earth Engine notebook [`code/Lekki_Hydro_Study.ipynb`](code/Lekki_Hydro_Study.ipynb), its figures in [`figures/`](figures/) and the report in [`documents/`](documents/). Their errors are listed in [`AUDIT-2026-11-11.md`](AUDIT-2026-11-11.md) and [`research/audit-2026-11-16/`](research/audit-2026-11-16/). The report still gives an 18.1 % basin-wide and over 45 % urban-core loss of recharge; neither figure is supported by any output.

## Main results (re-analysis)

Numbers below are from [`outputs/index_results.json`](outputs/index_results.json) and [`outputs/modflow_results.json`](outputs/modflow_results.json).

1. **The western barrier has sealed over.** Rebuilt with the original method, the recharge-potential index falls by 3.9 % over the whole barrier and 12.2 % in the western "urban core" (the notebook reported 5.2 % and 18.1 % from its Earth Engine inputs). The index falls where the GHSL built-up map records new buildings (Spearman ρ −0.66 over 8,278 blocks of 300 m). GHSL uses a different algorithm but partly the same Landsat archive, so this is a cross-check, not independent validation.
2. **The size of the decline is not robust, and the basin-wide direction is not either.** Using the rainfall of each epoch removes the basin-wide decline (a 0.4 % rise) and leaves 9.3 % in the core. With both corrections and 2,000 random weight sets the core declines in 91 % of sets and the whole barrier in 75 %; the core change runs from -4.2 to 30.5 % (5th–95th percentile, negative values are rises). About 59 km² scores as built-up in 2024 where GHSL maps no buildings (bare sand, cleared land, roads or paving). The "rural" zone the original study used to match the two sensors changed too.
3. **In the model, sealing moves the water table only a little, because the water table sits near the ground.** In a steady-state model of the barrier (48 runs, all converged, budget error under 0.01 %), groundwater flows from the middle of the barrier to the lagoons and the sea, the water table lies 1.2–4.4 m below ground (medians across scenarios) and 16–80 % of recharge seeps out at the surface. From 1990 to 2020 the mean water table in the western core falls by 4–5 cm with sealing from GHSL buildings (footprints only, likely too low) and 27–34 cm in a high scenario taken from the index's satellite term (not a measured fraction and not a strict bound). Varying the model structure (drain elevation and conductance, how the surface model sets the top) gives 4–6 cm and 26–38 cm (`outputs/structure_sensitivity.json`). The result says more about a water table held near the surface than about the aquifer: if abstraction has already lowered the real water table, the response to sealing could be larger. Both epochs use today's terrain and land and water masks, and the head changes include the small rainfall difference between epochs.

The model is **not calibrated**: no water-level, abstraction, aquifer-test or salinity data were available. Its absolute heads are illustrative; its results are differences between scenarios.

## What was corrected

| Problem in the original | Correction |
| :--- | :--- |
| The Earth Engine export the notebook reads was never stored, so nothing could be re-run | `p01_inputs.py` rebuilds every input from Planetary Computer, CHIRPS and GHSL |
| README and report misreported the notebook (18.1 % and >45 % instead of 5.16 % and 18.14 %, in an index, not in recharge) | Results reported from output files only; the report is marked superseded |
| MODFLOW input written but never run; recharge in mm/yr in a metre-day model; no boundaries, conductivity or inactive cells; uniform top and base | `p03_modflow.py`: model runs; units consistent; lagoon and sea boundaries, surface seepage, conductivity and base as scenarios; solver set-up checked against the Dupuit solution without seepage (`test_mf6_dupuit.py`, error 9 mm); drain and top settings varied (`p03b_structure_sensitivity.py`) |
| Recharge = rainfall × 0.35 × index, with no physical basis | The index is kept as a relative score; the model takes recharge from rainfall on unsealed ground, with the coefficient as a scenario |
| "TWI" computed from a smoothed Laplacian, not upslope area | Described as a surface-curvature term; the result without it is reported |
| Sensor matching on the eastern 30 % of columns, assumed unchanged but changed | Matching on GHSL never-built ground tested; both reported |
| The same 2019–2023 rainfall used for both epochs | CHIRPS 1986–1996 for the earlier epoch |
| Least-cost "percolation corridor" presented as subsurface flow | Withdrawn; modelled groundwater flows across the barrier, not along it |
| No validation | Satellite sealing cross-checked against GHSL (not independent of Landsat); the model's limits stated; no groundwater validation is possible without observations |

## Run

Requires Python 3.10+, `numpy scipy rasterio pystac-client planetary-computer flopy matplotlib`, and a MODFLOW 6 executable (`MF6_EXE`, default `/home/user/tools/mf6/pkg/bin/mf6`; MODFLOW 6.6.3 was used).

```bash
python3 code/pipeline/test_mf6_dupuit.py    # check MODFLOW 6 against an analytical solution
python3 code/pipeline/p01_inputs.py         # inputs (about 10 minutes; GHSL tile R9_C19 for 1990 and 2020 must be in data_cache/ghsl/)
python3 code/pipeline/p02_index.py          # index reproduction and sensitivity
python3 code/pipeline/p03_modflow.py        # 48 groundwater model runs (about 30 minutes)
python3 code/pipeline/p03b_structure_sensitivity.py  # drain and model-top sensitivity (run from code/pipeline/)
python3 code/pipeline/p04_figures.py        # figures
python3 code/pipeline/p05_site_data.py      # numbers for the preview page
python3 -m http.server -d docs 8811         # preview at http://localhost:8811/
```

## Limits

No groundwater observations; sealing not measured (building footprints are too low, the satellite index is a relative score that also reads bare ground as built); a water table held near the surface by seepage, which controls the result; the DEM is a surface model; steady state only, with no abstraction, tides or drainage works; no variable-density flow, so nothing reliable can be said about saltwater intrusion. See [`research/audit-2026-11-16/`](research/audit-2026-11-16/) for the full audit and what further data would make this a calibrated hydrogeological study.
