#!/usr/bin/env python3
"""
src/rg_2loop_pipeline.py  (AUDIT-GRADE)

2-loop SM RG with deterministic thresholds + high-scale finite matching shifts Δ_i.
Δ_i are additive to 1/alpha_i at Λ (standard GUT threshold correction).

IMPORTANT (audit-grade):
- d2 (the SU(2) inverse-alpha shift) is sourced from artifacts/ult_delta2_module.json if present AND valid.
- Otherwise d2 falls back to config/highscale_shifts.json.
- kY is sourced ONLY from artifacts/ult_kY_pure.json if present; else SU(5) 5/3.
  (No references to kYstar_muon solver or ult_kYstar_muon.json.)

This file does NOT derive mu_on/Delta2 from MZ targets. It only consumes artifacts.

Inputs (canonical):
- config/constants.json
- config/thresholds.json
- config/highscale_shifts.json
- artifacts/ult_delta2_module.json (optional override for d2, preferred)
- artifacts/ult_kY_pure.json (preferred)

Outputs (canonical):
- artifacts/ult_MZ_observables.json
"""

import json
import math
import time
import os
import hashlib
from typing import Any, Dict

MZ = 91.1876

CONFIG_DIR = "config"
ART_DIR = "artifacts"

CONSTANTS = os.path.join(CONFIG_DIR, "constants.json")
THRESHOLDS = os.path.join(CONFIG_DIR, "thresholds.json")
HIGHSCALE = os.path.join(CONFIG_DIR, "highscale_shifts.json")

DELTA2_ART = os.path.join(ART_DIR, "ult_delta2_module.json")
KY_PURE_ART = os.path.join(ART_DIR, "ult_kY_pure.json")
OUT_MZ = os.path.join(ART_DIR, "ult_MZ_observables.json")


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _isfinite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


# ---------------- Load constants ----------------
if not os.path.exists(CONSTANTS):
    raise SystemExit(f"[RG] Missing {CONSTANTS}")
C = _load_json(CONSTANTS)

# Support either key naming in constants
if "Lambda_GeV" in C:
    MU = float(C["Lambda_GeV"])
    _lambda_key = "Lambda_GeV"
elif "Lambda" in C:
    MU = float(C["Lambda"])
    _lambda_key = "Lambda"
else:
    raise SystemExit("[RG] constants.json missing Lambda_GeV (preferred) or Lambda")

if "gU" not in C:
    raise SystemExit("[RG] constants.json missing gU")
gU = float(C["gU"])

alpha0 = gU * gU / (4.0 * math.pi)

# ---------------- Load high-scale shifts (defaults=0) ----------------
d1 = d2 = d3 = 0.0
deltas_source = {"d1": "none", "d2": "none", "d3": "none"}
deltas_sha256 = {"d1": None, "d2": None, "d3": None}

if os.path.exists(HIGHSCALE):
    SH = _load_json(HIGHSCALE)
    d1 = float(SH.get("delta_inv_a1_GUT", 0.0))
    d2 = float(SH.get("delta_inv_a2", 0.0))
    d3 = float(SH.get("delta_inv_a3", 0.0))
    deltas_source["d1"] = HIGHSCALE
    deltas_source["d2"] = HIGHSCALE
    deltas_source["d3"] = HIGHSCALE
    sh_hash = _sha256_file(HIGHSCALE)
    deltas_sha256["d1"] = sh_hash
    deltas_sha256["d2"] = sh_hash
    deltas_sha256["d3"] = sh_hash

# ---------------- Override d2 from module-derived Δ2 if available + valid ----------------
module_delta2 = None
module_mu_on = None
module_delta2_sha256 = None

if os.path.exists(DELTA2_ART):
    MOD = _load_json(DELTA2_ART)

    # Strict key presence
    has_keys = (
        ("Delta2_add_to_inv_alpha2" in MOD)
        and ("mu_on_GeV" in MOD)
        and ("sigma_H" in MOD)
        and ("Lambda_GeV" in MOD)
    )

    if has_keys:
        cand_d2 = MOD.get("Delta2_add_to_inv_alpha2")
        cand_mu = MOD.get("mu_on_GeV")
        cand_sig = MOD.get("sigma_H")
        cand_L = MOD.get("Lambda_GeV")

        # Basic sanity: finite numbers and physically sensible ranges
        sane = (
            _isfinite(cand_d2)
            and _isfinite(cand_mu)
            and _isfinite(cand_sig)
            and _isfinite(cand_L)
            and (0.0 < float(cand_sig) < 1.0)
            and (1.0e3 < float(cand_mu) < float(cand_L))
        )

        if sane:
            module_delta2 = float(cand_d2)
            module_mu_on = float(cand_mu)
            d2 = module_delta2
            deltas_source["d2"] = DELTA2_ART
            module_delta2_sha256 = _sha256_file(DELTA2_ART)
            deltas_sha256["d2"] = module_delta2_sha256
        else:
            deltas_source["d2"] = f"{HIGHSCALE} (module Δ2 present but failed sanity)"
    else:
        deltas_source["d2"] = f"{HIGHSCALE} (module Δ2 present but missing keys)"

# ---------------- Load kY (prefer pure; else SU(5) 5/3) ----------------
kY = 5.0 / 3.0
kY_source = "default_SU5_5over3"
kY_sha256 = None

if os.path.exists(KY_PURE_ART):
    KY = _load_json(KY_PURE_ART)
    if "kY_star" in KY and _isfinite(KY["kY_star"]):
        kY = float(KY["kY_star"])
        kY_source = KY_PURE_ART
        kY_sha256 = _sha256_file(KY_PURE_ART)

# ---------------- Threshold masses ----------------
if not os.path.exists(THRESHOLDS):
    raise SystemExit(f"[RG] Missing {THRESHOLDS}")
TH = _load_json(THRESHOLDS)["masses_GeV"]
m_e, m_mu, m_tau = TH["e"], TH["mu"], TH["tau"]
m_c, m_b, m_t = TH["c"], TH["b"], TH["t"]
m_W, m_Z, m_H = TH["W"], TH["Z"], TH["H"]

# 1-loop SM coefficients (GUT norm) when all light fields are active
b1_SM, b2_SM, b3_SM = 41.0 / 10.0, -19.0 / 6.0, -7.0

# 2-loop fixed SM matrix (GUT norm)
B11, B12, B13 = 199.0 / 50.0, 27.0 / 10.0, 44.0 / 5.0
B21, B22, B23 = 9.0 / 10.0, 35.0 / 6.0, 12.0
B31, B32, B33 = 11.0 / 10.0, 9.0 / 2.0, -26.0

# Yukawa feedback (top only)
c1, c2, c3 = 17.0 / 10.0, 3.0 / 2.0, 2.0
vEW = 246.22

# clamps
A_MIN, A_MAX = 0.01, 5.0e4
YT_MAX = 5.0


def clamp(x: float, lo: float, hi: float) -> float:
    if not math.isfinite(x):
        return 0.5 * (lo + hi)
    return lo if x < lo else (hi if x > hi else x)


def inv_from_a(a: float) -> float:
    a = clamp(a, A_MIN, A_MAX)
    return 1.0 / a


def yt_from_mt(mt: float) -> float:
    return math.sqrt(2.0) * mt / vEW


def active_fields(mu: float) -> Dict[str, bool]:
    return {
        "e": mu >= m_e,
        "mu": mu >= m_mu,
        "tau": mu >= m_tau,
        "u": True,
        "d": True,
        "s": True,
        "c": mu >= m_c,
        "b": mu >= m_b,
        "t": mu >= m_t,
        "H": mu >= m_H,
    }


def b_i_with_thresholds(mu: float):
    act = active_fields(mu)
    b1, b2, b3 = b1_SM, b2_SM, b3_SM

    # Higgs off
    if not act["H"]:
        b1 += -1.0 / 10.0
        b2 += -1.0 / 6.0

    # charged leptons off (approx model)
    for L in ("e", "mu", "tau"):
        if not act[L]:
            b1 += -4.0 / 10.0
            b2 += +1.0 / 6.0

    # heavy quarks off (approx model)
    for Q in ("c", "b", "t"):
        if not act[Q]:
            b1 += -4.0 / 30.0
            b3 += +4.0 / 3.0

    return b1, b2, b3


def betas_da(a1: float, a2: float, a3: float, yt: float, b1: float, b2: float, b3: float):
    tp = 2.0 * math.pi
    ep2 = 8.0 * math.pi * math.pi
    a1i, a2i, a3i = inv_from_a(a1), inv_from_a(a2), inv_from_a(a3)
    da1 = -b1 / tp - ((B11 * a1i + B12 * a2i + B13 * a3i) / ep2) + (c1 * yt * yt) / ep2
    da2 = -b2 / tp - ((B21 * a1i + B22 * a2i + B23 * a3i) / ep2) + (c2 * yt * yt) / ep2
    da3 = -b3 / tp - ((B31 * a1i + B32 * a2i + B33 * a3i) / ep2) + (c3 * yt * yt) / ep2
    return da1, da2, da3


def beta_yt(yt: float, a1: float, a2: float, a3: float) -> float:
    a1i, a2i, a3i = inv_from_a(a1), inv_from_a(a2), inv_from_a(a3)
    gY2 = (3.0 / 5.0) * 4.0 * math.pi * a1i
    g22 = 4.0 * math.pi * a2i
    g32 = 4.0 * math.pi * a3i
    gauge = (17.0 / 20.0) * gY2 + (9.0 / 4.0) * g22 + 8.0 * g32
    return yt * (4.5 * yt * yt - gauge) / (16.0 * math.pi * math.pi)


def run_to_MZ():
    # initial inverse alphas at Λ with finite shifts Δ_i (a1,a2,a3 are inverse couplings here)
    a1 = 1.0 / alpha0 + d1
    a2 = 1.0 / alpha0 + d2
    a3 = 1.0 / alpha0 + d3
    yt = yt_from_mt(m_t)

    t_hi, t_lo = math.log(MU), math.log(MZ)
    N = 180_000
    h = (t_lo - t_hi) / N

    for k in range(N):
        mu = math.exp(t_hi + k * h)
        b1, b2, b3 = b_i_with_thresholds(mu)
        top_on = mu >= m_t

        da1a, da2a, da3a = betas_da(a1, a2, a3, yt if top_on else 0.0, b1, b2, b3)
        dya = beta_yt(yt, a1, a2, a3) if top_on else 0.0

        a1b = a1 + 0.5 * h * da1a
        a2b = a2 + 0.5 * h * da2a
        a3b = a3 + 0.5 * h * da3a
        ytb = yt + 0.5 * h * dya
        da1b, da2b, da3b = betas_da(a1b, a2b, a3b, ytb if top_on else 0.0, b1, b2, b3)
        dyb = beta_yt(ytb, a1b, a2b, a3b) if top_on else 0.0

        a1c = a1 + 0.5 * h * da1b
        a2c = a2 + 0.5 * h * da2b
        a3c = a3 + 0.5 * h * da3b
        ytc = yt + 0.5 * h * dyb
        da1c, da2c, da3c = betas_da(a1c, a2c, a3c, ytc if top_on else 0.0, b1, b2, b3)
        dyc = beta_yt(ytc, a1c, a2c, a3c) if top_on else 0.0

        a1d = a1 + h * da1c
        a2d = a2 + h * da2c
        a3d = a3 + h * da3c
        ytd = yt + h * dyc
        da1d, da2d, da3d = betas_da(a1d, a2d, a3d, ytd if top_on else 0.0, b1, b2, b3)
        dyd = beta_yt(ytd, a1d, a2d, a3d) if top_on else 0.0

        a1 += (h / 6.0) * (da1a + 2 * da1b + 2 * da1c + da1d)
        a2 += (h / 6.0) * (da2a + 2 * da2b + 2 * da2c + da2d)
        a3 += (h / 6.0) * (da3a + 2 * da3b + 2 * da3c + da3d)
        if top_on:
            yt += (h / 6.0) * (dya + 2 * dyb + 2 * dyc + dyd)

        a1 = clamp(a1, A_MIN, A_MAX)
        a2 = clamp(a2, A_MIN, A_MAX)
        a3 = clamp(a3, A_MIN, A_MAX)
        yt = clamp(yt, 0.0, YT_MAX)

    # Convert back: alpha_i = 1/(inv_alpha_i)
    a1_GUT = inv_from_a(a1)
    a2_fin = inv_from_a(a2)
    a3_fin = inv_from_a(a3)

    aY = a1_GUT / kY
    inv_alpha_em = kY / a1_GUT + 1.0 / a2_fin
    alpha_em = 1.0 / inv_alpha_em
    sin2W = aY / (aY + a2_fin)

    return {
        "alpha_em_inv": 1.0 / alpha_em,
        "sin2_thetaW": sin2W,
        "alpha_s": a3_fin,
        "g_MZ": {
            "g1": math.sqrt(4.0 * math.pi * a1_GUT),
            "g2": math.sqrt(4.0 * math.pi * a2_fin),
            "g3": math.sqrt(4.0 * math.pi * a3_fin),
        },
    }


def main() -> None:
    os.makedirs(ART_DIR, exist_ok=True)

    extra = ""
    if module_delta2 is not None:
        extra = f",  μ_on(module)={module_mu_on:.3e} GeV"

    print(
        f"[RG] gU={gU:.6f}, Λ={MU:.3e} GeV,  "
        f"Δ(1/a)=(d1={d1:.3f}, d2={d2:.3f}, d3={d3:.3f}) "
        f"[src d1={deltas_source['d1']}, d2={deltas_source['d2']}, d3={deltas_source['d3']}],  "
        f"kY={kY:.6f} [src {kY_source}]"
        f"{extra}"
    )

    out = run_to_MZ()

    payload = {
        "alpha_em_inv": float(out["alpha_em_inv"]),
        "sin2_thetaW": float(out["sin2_thetaW"]),
        "alpha_s": float(out["alpha_s"]),
        "g_MZ": {k: float(v) for k, v in out["g_MZ"].items()},
        "note": {
            "gU_used": gU,
            "Lambda_key_used": _lambda_key,
            "MU_used_GeV": MU,
            "kY_used": kY,
            "kY_source": kY_source,
            "kY_sha256": kY_sha256,
            "deltas": {"d1": d1, "d2": d2, "d3": d3},
            "deltas_source": deltas_source,
            "deltas_sha256": deltas_sha256,
            "module_mu_on_GeV": (module_mu_on if module_mu_on is not None else None),
            "module_delta2_sha256": module_delta2_sha256,
            "inputs_sha256": {
                "constants": _sha256_file(CONSTANTS),
                "thresholds": _sha256_file(THRESHOLDS),
                "highscale_shifts": (_sha256_file(HIGHSCALE) if os.path.exists(HIGHSCALE) else None),
                "delta2_module": (_sha256_file(DELTA2_ART) if os.path.exists(DELTA2_ART) else None),
                "kY_pure": (_sha256_file(KY_PURE_ART) if os.path.exists(KY_PURE_ART) else None),
            },
            "ts": time.time(),
        },
    }

    with open(OUT_MZ, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)

    print(f"Wrote {OUT_MZ}")


if __name__ == "__main__":
    main()
