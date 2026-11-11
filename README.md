# Coastal Hydrogeology & Subsurface Connectivity Modeling

![Python](https://img.shields.io/badge/Python-3.10%2B-1B365D?style=flat-square&logo=python&logoColor=white)
![Google Earth Engine](https://img.shields.io/badge/Google%20Earth%20Engine-Cloud%20API-2C5E3B?style=flat-square&logo=googleearth&logoColor=white)
![Spatial Stack](https://img.shields.io/badge/Spatial%20Stack-Rasterio%20%7C%20SciPy%20%7C%20GeoPandas-334155?style=flat-square)
![MODFLOW 6](https://img.shields.io/badge/Numerical%20Coupling-MODFLOW%206%20%7C%20FloPy-8B2635?style=flat-square)

**Author:** David Oloyede  
**Research Focus:** Coastal Zone Dynamics, Physical Hydrogeology & Global Change  

---

> **Status, 11 November 2026: the recharge results and the numerical model in this repository are not verified.** An audit of the notebook found the following. The whole-basin and urban-core changes in earlier versions of this file (18.1% and over 45%) did not match the notebook output (5.16% and 18.14% for the index); they are corrected below. The index weights (0.30, 0.25, 0.20, 0.15, 0.10) and the recharge coefficient (0.35) are fixed assumptions with no calibration and no sensitivity test. The MODFLOW 6 input files are written but the model is never run, recharge in mm/yr is passed to a model set in metres and days, and no boundary conditions or hydraulic conductivity are set. The "1995" baseline is a 1986 to 1996 Landsat-5 median. The sensor harmonization forces the eastern 30% of the raster columns to show no change. Nothing is validated against piezometric, recharge or impervious-surface data. See `AUDIT-2026-11-11.md`.

## Overview
This repository contains a computational pipeline that estimates the change in a recharge-potential index between a 1986–1996 Landsat-5 median and 2024, and a surface-resistance path, across the Lekki-Epe coastal aquifer corridor in Lagos, Nigeria. Rapid demographic and infrastructural expansion along the Gulf of Guinea margin has driven widespread replacement of permeable coastal sands and wetland vegetation with impervious concrete. This land-surface sealing disrupts natural infiltration pathways, accelerates surface runoff, starves shallow unconfined groundwater reserves, and heightens vulnerability to saltwater intrusion from the Atlantic Ocean and the Lagos-Lekki lagoon system.

To overcome the chronic scarcity of long-term piezometric gauge networks in the basin, this study engineers an end-to-end cloud-to-numerical workflow. Using Google Earth Engine (GEE) and scientific Python libraries, the pipeline harmonizes multi-decadal optical satellite records (Landsat-5 TM and Sentinel-2 MSI), conditions 30m digital elevation data via a 2D Laplacian operator to model surface convergence, synthesizes an Aquifer Recharge Potential Index (ARPI) from fixed weights, executes graph-theoretical Dijkstra routing to isolate subsurface flow bottlenecks, and converts the index to recharge arrays (mm/yr) with a fixed coefficient and writes MODFLOW 6 input files via FloPy; the model was never run.

## Complete Portfolio Documentation
* **Full Written Mini-Study & Spatial Analysis:** [View Complete PDF](documents/Lekki_Coastal_Aquifer_Recharge_Report.pdf)

## Module-by-Module Code Execution
* **Cloud Harmonization, ARPI Synthesis, Dijkstra Percolation Routing & MODFLOW 6 / FloPy Export:** [Open Colab Notebook](https://colab.research.google.com/drive/11YyjwtvWrfmiFU0lYvBRQe6YMzfSbmId) | [View Source Notebook](code/Lekki_Hydro_Study.ipynb)

---

## Visual Synthesis

| Study Domain & Physiographic Baseline |
| :---: |
| ![Study Area](figures/fig0_study_area.png) |
| **Physiographic Setting:** Delineation of the unconfined coastal aquifer study domain across the Lekki-Epe peninsula (UTM Zone 31N), bounded by the Lagos Lagoon to the north, the Lekki Lagoon to the east, and the Atlantic Ocean to the south, illustrating the structural transition from the densely urbanized western core to the pervious Epe hinterland. |

| Historical Baseline ARPI (1995) | Modern Post-Urbanization ARPI (2024) |
| :---: | :---: |
| ![1995 Baseline](figures/1995_Baseline_ARPI.png) | ![2024 Modern](figures/2024_Modern_ARPI.png) |
| **1995 Pre-Expansion Baseline:** Widespread high-to-moderate recharge capacity sustained across natural coastal sandy ridges, barrier islands, and undisturbed swamp forest corridors prior to intensive metropolitan expansion. | **2024 Modern State:** Severe contraction of active infiltration zones across the western Lekki-Ikoyi urban core, showing a 5.16% whole-basin reduction of the ARPI index and an 18.14% reduction in the Lekki urban core (the notebook output). |

| 30-Year Recharge Capacity Difference (1995–2024) | Hydraulic Friction Manifold & Percolation Routing |
| :---: | :---: |
| ![Temporal Delta](figures/ARPI_Temporal_Delta_Map.png) | ![Percolation Routing](figures/Percolation_Routing_Map.png) |
| **Differential Infiltration Loss:** Pixel-wise 30-year temporal delta (1995 - 2024) isolating contiguous zones of acute anthropogenic recharge loss ($> +0.20$, red) along primary highway and real-estate development axes, contrasted against stable rural recharge zones in blue. | **Least-Cost Subsurface Connectivity:** Graph-theoretical 8-connected Dijkstra path routed across the log-transformed hydraulic resistance manifold ($\log_{10} R$), tracing the primary percolation corridor from the Epe inflow source to the Lekki coastal outlet and flagging critical urban choke points ($\text{ARPI} < 0.35$). |

| Longitudinal Hydro-Spatial Transect Profile |
| :---: |
| ![Longitudinal Transect](figures/Longitudinal_Transect_Profile.png) |
| **Cross-Sectional Attenuation:** Longitudinal profile extracted along the routed percolation corridor from the Epe hinterland to the Lekki coastal margin, contrasting the 1995 baseline against the 2024 post-urbanization profile and highlighting the 30-year cumulative recharge deficit and active sealed bottleneck zones below the critical $\text{ARPI} = 0.35$ threshold. |

---

## Methodological Architecture & Technical Stack

| Stage | Analytical Module | Mathematical & Spatial Operations | Technical Stack |
| :--- | :--- | :--- | :--- |
| **01** | **Cloud Ingestion & Cross-Sensor Harmonization** | Multi-temporal surface reflectance ingestion from Landsat-5 TM (1995 baseline) and Sentinel-2 MSI (2024 modern state); empirical radiometric shift calibration anchored across undisturbed rural reference polygons in the eastern Epe sector to remove sensor bandpass bias; derivation of Normalized Difference Built-up Index ($\text{NDBI}$) and Vegetation Index ($\text{NDVI}$). | `Google Earth Engine API`, `Python` |
| **02** | **Topographic Conditioning & ARPI Synthesis** | Gaussian kernel smoothing ($\sigma = 1.5$) on a 30m Digital Elevation Model (DEM); omnidirectional 2D Laplacian operator ($-\nabla^2 z$) to quantify local topographic convergence and depression storage; adjusted Topographic Wetness Index ($\text{TWI}$) derivation; multi-criteria weighted linear combination integrating surface permeability ($1 - \text{NDBI}$), terrain slope, $\text{TWI}$, CHIRPS precipitation, and $\text{NDVI}$. | `NumPy`, `SciPy (ndimage)`, `Rasterio` |
| **03** | **Graph-Theoretical Percolation Routing** | Non-linear exponential transformation of the modern recharge surface into an isotropic hydraulic resistance manifold; construction of an 8-connected pixel adjacency graph; execution of Dijkstra's minimum-cost path algorithm from the Epe recharge hinterland to the Lekki discharge margin; automated extraction of longitudinal profiles and urban sealing choke nodes ($\text{ARPI} < 0.35$). | `scikit-image (graph)`, `GeoPandas`, `Shapely` |
| **04** | **Numerical Coupling & Cartographic Synthesis** | Conversion of unitless 30m ARPI arrays into physical Effective Areal Recharge grids ($\text{mm/yr}$) computed as the 2019–2023 CHIRPS rainfall total times a fixed coefficient (0.35) times the index (specific yield is not used); programmatic generation of MODFLOW 6 Simulation (`MFSimulation`), Spatial Discretization (`ModflowGwfdis`), and Recharge (`ModflowGwfrch`) input files, with no boundary conditions or conductivity and no model run; 300 DPI cartographic output generation. | `FloPy (MODFLOW 6)`, `Matplotlib` |

---

## Key Empirical Findings
* **Basin-wide index change:** Across the Lekki-Epe corridor the mean ARPI index fell by **5.16%** between the 1986–1996 baseline and 2024 (the notebook output). ARPI is a weighted index, not measured recharge.
* **Urban core index change:** Within the Lekki urban core the mean ARPI index fell by **18.14%** (the notebook output). Earlier versions of this file gave over 45%, which no output supports.
* **Surface-resistance bottlenecks:** A least-cost path over a surface index (not a groundwater flow model, with start and end points fixed as raster positions) suggests that while the eastern Epe hinterland remains an active recharge source, lateral and vertical percolation toward the western coastal margin is increasingly pinched by contiguous urban choke zones falling below the $\text{ARPI} = 0.35$ threshold.
* **Direct Numerical Model Readiness:** Scaling the 2024 ARPI surface against CHIRPS precipitation yields a spatially explicit 30m recharge boundary array ingested directly into `ModflowGwfrch`, eliminating the need for uniform recharge assumptions in coastal groundwater head and saltwater-intrusion simulations.

---

## Research Reflection
In rapidly urbanizing West African coastal megacities, groundwater depletion and saline intrusion along the land-ocean boundary are frequently approached purely from the perspective of over-abstraction, overlooking how aggressive surface sealing starves shallow unconfined aquifers from above. Because continuous in-situ piezometric monitoring across the Lagos coastal basin remains sparse, open-source satellite Earth Observation provides a vital observational bridge. By coupling multi-decadal spectral harmonization and terrain physics with graph-theoretical routing and MODFLOW 6 package compilation, this work demonstrates how reproducible geospatial workflows can convert raw orbital telemetry into physical boundary constraints for coastal water resource management.

