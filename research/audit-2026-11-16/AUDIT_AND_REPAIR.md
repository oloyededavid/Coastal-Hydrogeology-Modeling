# Coastal hydrogeology: audit, repair and research potential

16 November 2026 · working branch `research-audit` (local, not pushed) · progress log: [`PROGRESS.md`](PROGRESS.md)

Scope: the whole repository (README, `AUDIT-2026-11-11.md`, the notebook `code/Lekki_Hydro_Study.ipynb`, the report PDF, the six figures). Every number below comes from a file named next to it; nothing is estimated by hand.

## 1. Audit: problems, ranked

Severity: **Critical** (a headline result is wrong or cannot be checked), **High** (a result is fragile or mislabelled), **Medium** (weakens rigour), **Low** (presentation).

| # | Problem | Evidence | Severity | Scientific consequence |
| :-- | :--- | :--- | :-- | :--- |
| 1 | The analysis cannot be re-run: it reads an Earth Engine export (`lekki_multiband_utm31n.tif`) that was saved to Google Drive and never stored | Notebook cell 4; not in the repository | Critical | No result could be checked or reproduced |
| 2 | The report still states an 18.1 % basin-wide and >45 % urban-core loss of recharge | Text of `documents/Lekki_Coastal_Aquifer_Recharge_Report.pdf`; notebook output is 5.16 % and 18.14 % | Critical | Misreported headline; also a change in an index, not in recharge |
| 3 | The MODFLOW model was never run, and could not have run meaningfully | Cell 8 calls only `write_simulation()`; recharge in mm/yr in a metre-day model; no boundary conditions; conductivity never set; uniform top 45 m and base 0 m; no inactive cells | Critical | No groundwater result exists in the original work |
| 4 | Recharge is rainfall × 0.35 × index | Cell 5 | High | A weighted index is turned into a physical flux with no basis |
| 5 | The weights (0.30/0.25/0.20/0.15/0.10) and the 0.35 coefficient are untested | Cell 5 | High | Size of the change not shown to be robust |
| 6 | Sensor matching assumes the eastern 30 % of columns did not change | Cell 5 (`rural_cols`) | High | The zone did change: GHSL built-up fraction 0.6 % → 1.5 % (whole zone) and 0.7 % → 2.9 % (south-east corner); the largest index decline in the domain lies in it (`outputs/index_results.json`, Figure 2 of the preview) |
| 7 | Rainfall for 2019–2023 is used for both epochs | Cell 2 | High | Rainfall cannot contribute to change; with 1986–1996 rainfall the basin-wide decline disappears |
| 8 | "TWI" is a shifted, smoothed negative Laplacian, not upslope area over slope | Cell 5 | Medium | Misnamed term; 20 % of the weight |
| 9 | The DEM is a surface model (buildings and trees), used for slope, curvature and as the model top | Copernicus GLO-30 | Medium | Urban areas carry building heights; the terrain terms are the same in both epochs, so they only scale the percentages |
| 10 | Built-up index (NDBI) reads bare sand as built | 59 km² scores as built in 2024 where GHSL maps no buildings (`index_results.json`, `ghsl_check`) | Medium | Sealing over-estimated where land is cleared or sand-filled |
| 11 | Least-cost "percolation corridor" presented as subsurface connectivity | Cell 6 | High (terminology) | A path over a surface index is not groundwater flow; modelled flow runs across the barrier, not along it |
| 12 | "1995 baseline" and "30-year" | Landsat-5 median of 1986–1996 | Low | Interval overstated |
| 13 | Notebook run out of order | Execution counts 3, 4, 11, 15, 16, 17, 26, 31, 32 | Low | Reproducibility |
| 14 | Report cites MERIT Hydro; code uses Copernicus GLO-30 | Report text, cell 2 | Low | Inconsistent methods |

What is computed, illustrative or only described in the original: the index and its two percentage changes were **computed** (from inputs that were not stored); the 18.1 % and 45 % figures were **unsupported**; the recharge array was **computed but meaningless as recharge**; the MODFLOW model was **described** (files written, never run); the percolation corridor was **computed** but mislabelled.

## 2. Corrections implemented

| Problem | Files | What was done | Verified by |
| :-- | :--- | :--- | :--- |
| 1 | `code/pipeline/p01_inputs.py` | All inputs rebuilt on the same 30 m UTM 31N grid from Planetary Computer (Copernicus DEM, Sentinel-2 L2A with the post-2022 offset removed, Landsat-5 C2 L2), CHIRPS and GHSL; per-scene cache, resumable | Run completed: 14 Sentinel-2 and 29 Landsat-5 scenes (`data_cache/stack_meta.json`); land mask 768.8 km² vs 766.1 km² in the notebook |
| 1, 5, 6, 7, 8 | `code/pipeline/p02_index.py` | Notebook method reproduced line for line; then one change at a time; 2,000 random weight sets; GHSL check | Run completed; results in `outputs/index_results.json` |
| 3, 4 | `code/pipeline/p03_modflow.py` | Steady-state MODFLOW 6 model of the barrier at 150 m: lagoon and sea cells at 0 m, inactive cells off the barrier, top from the DEM's 10th percentile per cell, base −30/−60 m, K 5/15/40 m/day, surface seepage drains, recharge = c × rain × (1 − sealed) with c 0.20/0.35 and two sealing estimates | 48 runs, all converged, budget error 0.00 % (`outputs/modflow_results.json`) |
| 3 | `code/pipeline/test_mf6_dupuit.py` | Analytical check of the solver set-up | Max head error 0.0088 m against Dupuit-Forchheimer; budget imbalance 2.8e-11; pytest 1 passed |
| 2, 8, 11, 12 | `README.md`, `docs/index.html` | Results reported from output files; terms corrected; corridor withdrawn; superseded material labelled | Preview page: no unfilled numbers, no console errors, no overflow at 320–1440 px, axe clean |
| — | `code/pipeline/p04_figures.py`, `p05_site_data.py` | Figures and page numbers generated from outputs | Figures inspected; page numbers read from `docs/data/site.json` |

Not changed, on purpose: the notebook, the report PDF and the original figures (kept as the record of the first version; the README says they are superseded).

## 3. Test and execution results

| Step | Result |
| :--- | :--- |
| `test_mf6_dupuit.py` | Pass. MODFLOW vs Dupuit max error 0.0088 m; divide head 36.047 vs 36.056 m |
| `p01_inputs.py` | Pass. Stack 2214 × 926 at 30 m, 11 bands |
| `p02_index.py` | Pass. Reproduction 3.91 % (basin) and 12.18 % (core) vs notebook 5.16 % and 18.14 %; mean index 0.567 vs 0.427 |
| `p03_modflow.py` | 48 of 48 converged after the surface-drain conductance was reduced from K·A/1 m to K·A/10 m (with the first setting 5 of 12 scenarios failed to converge); a scenario that converged under both settings gave the same mean head (1.339 vs 1.343 m) |
| Preview | 0 axe violations at 390 and 1440 px; no overflow at 320, 390, 1440 px; all 40 numbers filled |

Why the reproduction does not match the notebook exactly: the inputs differ (Planetary Computer composites instead of the Earth Engine export; slope by finite differences instead of `ee.Terrain.slope`). The absolute index level differs (0.57 vs 0.43), and because the terrain terms are identical in both epochs they sit in the denominator of the percentage change; the percentage therefore partly reflects the index's arbitrary constant terms, not change.

## 4. Unresolved limitations

- **No groundwater observations.** No water levels, abstraction, aquifer tests or salinity were available to this study. The model cannot be calibrated or validated; heads are illustrative.
- **Sealing is bracketed, not measured.** GHSL counts building footprints (misses roads and paving); the NDBI-based term counts bare sand.
- **Surface model.** The DEM includes buildings and trees; the low-percentile top reduces but does not remove the bias.
- **Steady state, no abstraction, no tides, no drainage works, no sand-filling history.**
- **No variable-density flow.** The Ghyben-Herzberg depth computed in `p03` is indicative only and is not reported as a finding. Saltwater intrusion is outside what this model can address.
- **Two epochs.** 1986–1996 imagery vs 2023–2024; the path between is unknown.

## 5. Research potential

**What the evidence supports now.** A reproducible, open-data account of surface sealing on the barrier since the late 1980s, checked against an independent built-up record, and a transparent scenario model showing that, on a shallow seeping water table, sealing alone moves heads by centimetres to a few decimetres. That is a defensible, modest result.

**What can be improved with available data.**
- An impervious-surface map built from Sentinel-2 with a sand class and checked against high-resolution imagery (Google/Esri basemaps for visual accuracy assessment), replacing the two bounds.
- A time series (Landsat 5/7/8/9, 1986–2024) instead of two epochs, to date the sealing and the sand-filling.
- Transient monthly recharge from CHIRPS and the model run transiently, to test whether seasonal water-table swings dwarf the sealing signal.

**What needs field or external data.** Borehole water levels (Lagos State Water Corporation, published theses, a monitoring campaign); borehole logs and pumping tests for conductivity and thickness of the coastal plain sands; abstraction estimates (domestic boreholes are numerous in Lekki); groundwater electrical conductivity or chloride.

**What should stay a future direction.** A variable-density model of the fresh–salt interface (MODFLOW 6 with the buoyancy package, or SEAWAT) and any statement about saltwater intrusion; sea-level-rise scenarios.

**Strongest defensible direction.** "How much do urbanisation and groundwater abstraction each change the shallow water table of a barrier-lagoon aquifer?" Sealing (this work) is the smaller, satellite-observable half; abstraction is probably the larger and needs data. That question fits a hydrogeology MSc (it is calibratable with a modest monitoring campaign), connects to the portfolio's groundwater work (Ouémé–Ogun recharge, Lake Chad storage) and its coastal work (Ogun lagoon), and avoids claims the data cannot carry.

**Assessment against eight criteria** (1–5; evidence in the sections above):

| Criterion | Before | After | Why |
| :--- | :--: | :--: | :--- |
| Scientific rigour | 1 | 3 | Claims now match outputs and sensitivity is shown; no validation of groundwater results is possible |
| Methodological validity | 1 | 3 | Model is physically consistent and checked analytically; index remains a heuristic |
| Technical implementation | 2 | 4 | Scripts run end to end from open data; model converges in all scenarios |
| Data quality | 2 | 3 | Same open data plus GHSL and per-epoch rainfall; no ground data |
| Reproducibility | 1 | 4 | Inputs rebuildable, outputs and figures generated by script |
| Research value | 2 | 3 | Modest but honest result and a clear path to a real study |
| Academic relevance | 2 | 3 | Fits coastal hydrogeology; needs observations to be publishable |
| Visual communication | 3 | 4 | Cartographic figures with scale and orientation, one clean page |

## 6. Before and after

| | Before | After |
| :--- | :--- | :--- |
| Can it be re-run? | No (inputs never stored) | Yes, from open data, end to end |
| Headline | "18.1 % basin-wide, >45 % urban-core recharge loss" | Index decline 3.9 % (basin) and 12.2 % (core), direction robust, size depends on choices; water table falls 4–34 cm in the core across scenarios |
| Groundwater model | Files written, never run, wrong units | 48 converged scenario runs, analytically checked |
| Flow direction | "Percolation corridor" along the barrier | Flow across the barrier to the lagoons and sea |
| Independent check | None | GHSL built-up record (ρ −0.66) |
| Limits | Partly stated | Stated in README, page and this file |

The portfolio integration plan for this project and Observational Hydrology is kept in the Observational-Hydrology-Extremes repository: research/audit-2026-11-16/PORTFOLIO_INTEGRATION_PLAN.md (same date and branch).
