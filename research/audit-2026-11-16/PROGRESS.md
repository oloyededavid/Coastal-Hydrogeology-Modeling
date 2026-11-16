# Progress log: research audit, 16 November 2026

Working branch: `research-audit` (local only; nothing is pushed). Original files are kept; changes are recorded here.

## Environment
- MODFLOW 6.6.3 (conda-forge build, /home/user/tools/mf6/pkg/bin/mf6), FloPy 3.12.0, scikit-image 0.26.
- Data access: Microsoft Planetary Computer STAC (reachable), JRC GHSL FTP (reachable), GitHub release downloads (blocked).
- Google Earth Engine: no credentials in this environment.

## Log
- Phase 1 started. Read README.md, AUDIT-2026-11-11.md and all ten notebook cells.
  The analysis reads `lekki_multiband_utm31n.tif`, an Earth Engine export saved to Google Drive; it is not in the
  repository, so the notebook cannot be re-run as it stands.
- MODFLOW 6.6.3 obtained from the conda-forge package (GitHub release downloads are blocked here) and FloPy 3.12.0
  installed. Verification: `code/pipeline/test_mf6_dupuit.py` runs an unconfined strip between two fixed heads with
  uniform recharge and compares with the Dupuit-Forchheimer solution. Max head error 0.0088 m (divide 36.047 vs
  36.056 m); budget imbalance 2.8e-11. pytest: 1 passed.
- `code/pipeline/p01_inputs.py` written: rebuilds the Earth Engine stack from Planetary Computer (Copernicus DEM
  GLO-30, Sentinel-2 L2A, Landsat-5 C2 L2), CHIRPS annual files (2019-2023 and, new, 1986-1996) and GHSL built-up
  surface 1990/2020 (new, independent check). Grid 2214 x 926 at 30 m, EPSG:32631. Sentinel-2 +1000 offset for
  processing baseline >= 04.00 removed explicitly. Run started.
- Report PDF (documents/) still states an 18.1% basin reduction and >45% in the urban core, and mentions specific
  yield; the notebook output is 5.16% and 18.14% and no specific yield is used. Confirmed by text extraction.
- p01 completed (14 S2, 29 L5 scenes). p02: reproduction 3.91 % / 12.18 % vs notebook 5.16 % / 18.14 %; per-epoch
  rainfall removes the basin decline; core decline 3.1-22.7 % over 2,000 weight sets; GHSL rho -0.66; 59 km2 NDBI
  "built" sand. The notebook's eastern "rural" reference zone gained buildings (GHSL 0.6 % -> 1.5 %).
- p03: first run 5 of 12 scenarios failed (drain conductance K*A/1 m too stiff); with K*A/10 m and starting heads
  0.5 m below ground all 48 runs (12 parameter sets x 2 sealing estimates x 2 epochs) converge, budget 0.00 %.
  Core water-table change 1990->2020: -4 to -5 cm (GHSL sealing), -27 to -34 cm (satellite upper bound).
- p04 figures, p05 page data, docs/index.html preview (axe clean, no overflow 320-1440, all numbers filled).
- Page rebuilt in the study-site pattern: paper/template.md, p06_build_paper.py (paper.md, paper.docx), p07_build_page.py (docs/index.html); p05 and docs/data/site.json removed.
- README rewritten; AUDIT_AND_REPAIR.md written (audit, corrections, tests, limits, research potential, before/after).
