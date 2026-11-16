"""Check that the MODFLOW 6 executable and the model settings used here give the right answer on a problem with a
known solution, before trusting any run on the real domain.

Problem: an unconfined aquifer strip of width L between two water bodies held at head h0 (a barrier island between a
lagoon and the sea), uniform recharge N, uniform hydraulic conductivity K, flat base at z = 0. The Dupuit-Forchheimer
solution is   h(x)^2 = h0^2 + (N / K) * x * (L - x),   with the water divide at x = L / 2.

    python3 code/pipeline/test_mf6_dupuit.py        (or: pytest code/pipeline/test_mf6_dupuit.py)
"""
import os
import tempfile

import flopy
import numpy as np

MF6 = os.environ.get("MF6_EXE", "/home/user/tools/mf6/pkg/bin/mf6")


def run_strip(L=4000.0, ncol=161, h0=30.0, K=10.0, N=1e-3, top=60.0):
    delr = L / (ncol - 1)  # cell centres from x = 0 to x = L; end cells are the constant-head boundaries
    ws = tempfile.mkdtemp()
    sim = flopy.mf6.MFSimulation(sim_name="strip", exe_name=MF6, sim_ws=ws)
    flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[(1.0, 1, 1.0)], time_units="DAYS")
    flopy.mf6.ModflowIms(sim, complexity="MODERATE", outer_dvclose=1e-8, inner_dvclose=1e-9, linear_acceleration="BICGSTAB")
    gwf = flopy.mf6.ModflowGwf(sim, modelname="strip", newtonoptions="NEWTON", save_flows=True)
    flopy.mf6.ModflowGwfdis(gwf, nlay=1, nrow=1, ncol=ncol, delr=delr, delc=1.0, top=top, botm=0.0, length_units="METERS")
    flopy.mf6.ModflowGwfic(gwf, strt=h0)
    flopy.mf6.ModflowGwfnpf(gwf, icelltype=1, k=K)
    flopy.mf6.ModflowGwfsto(gwf, steady_state={0: True}, iconvert=1)
    flopy.mf6.ModflowGwfchd(gwf, stress_period_data=[[(0, 0, 0), h0], [(0, 0, ncol - 1), h0]])
    rch = np.full((1, ncol), N)
    flopy.mf6.ModflowGwfrcha(gwf, recharge=rch)
    flopy.mf6.ModflowGwfoc(gwf, head_filerecord="strip.hds", budget_filerecord="strip.bud", saverecord=[("HEAD", "ALL"), ("BUDGET", "ALL")])
    sim.write_simulation(silent=True)
    ok, _ = sim.run_simulation(silent=True)
    assert ok, "MODFLOW 6 did not converge"
    h = gwf.output.head().get_data()[0, 0]
    x = np.arange(ncol) * delr
    exact = np.sqrt(h0 ** 2 + (N / K) * x * (L - x))
    bud = gwf.output.budget()
    chd = bud.get_data(text="CHD")[0]["q"].sum()
    rch_in = bud.get_data(text="RCH")[0]["q"].sum()
    return h, exact, rch_in, chd


def test_dupuit_strip():
    h, exact, rch_in, chd = run_strip()
    # cell-centred finite differences on a 25 m grid: the divide head should match to within a few centimetres
    assert np.max(np.abs(h - exact)) < 0.05, np.max(np.abs(h - exact))
    # budget: all recharge leaves through the two constant-head cells (the end cells receive half-cell recharge too)
    assert abs(rch_in + chd) / rch_in < 1e-6


if __name__ == "__main__":
    h, exact, rch_in, chd = run_strip()
    print(f"max |MODFLOW - Dupuit| = {np.max(np.abs(h - exact)):.4f} m; divide head {h.max():.3f} m vs {exact.max():.3f} m")
    print(f"budget: recharge in {rch_in:.4f} m3/d, constant-head out {chd:.4f} m3/d, imbalance {(rch_in + chd) / rch_in:.2e}")
