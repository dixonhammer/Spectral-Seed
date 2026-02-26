#!/usr/bin/env python3
"""
src/delta2_from_module.py  (AUDIT-GRADE)

Compute module-native μ_on and Δ2 from canonical repo inputs:

Inputs (canonical):
- config/constants.json                (Lambda_GeV)
- artifacts/ult_DF_full.npy
- artifacts/ult_DF_index_map.json      (tags.H_doublet indices)

Definition (module-native):
- sigma_H = smallest nonzero singular value of D_F restricted to H_doublet
- mu_on   = sigma_H * Lambda
- Delta2_add_to_inv_alpha2 = -(b2H/(4*pi)) * ln(Lambda/mu_on),
  where b2H = 4/3 for one Dirac SU(2) doublet (Y=0).

Output (canonical):
- artifacts/ult_delta2_module.json

Hard rules:
- NO low-energy targets
- NO kYstar_muon* references
- Full provenance + hashes recorded
"""

import json
import math
import os
import hashlib
import numpy as np
from typing import Any, Dict

CONFIG_DIR = "config"
ART_DIR = "artifacts"

CONST_FILE = os.path.join(CONFIG_DIR, "constants.json")
DF_FILE = os.path.join(ART_DIR, "ult_DF_full.npy")
MAP_FILE = os.path.join(ART_DIR, "ult_DF_index_map.json")
OUT_FILE = os.path.join(ART_DIR, "ult_delta2_module.json")

B2H = 4.0 / 3.0  # Dirac SU(2) doublet


def _load_json(p: str) -> Dict[str, Any]:
    with open(p, "r") as f:
        return json.load(f)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _require_exists(path: str) -> None:
    if not os.path.exists(path):
        raise SystemExit(f"[Δ2 MODULE] Missing required file: {path}")


def main() -> None:
    for p in (CONST_FILE, DF_FILE, MAP_FILE):
        _require_exists(p)

    C = _load_json(CONST_FILE)

    # Accept either key name (some earlier artifacts used "Lambda")
    if "Lambda_GeV" in C:
        Lambda = float(C["Lambda_GeV"])
        lambda_key = "Lambda_GeV"
    elif "Lambda" in C:
        Lambda = float(C["Lambda"])
        lambda_key = "Lambda"
    else:
        raise SystemExit(f"[Δ2 MODULE] constants.json missing 'Lambda_GeV' (preferred) or 'Lambda'.")

    DF = np.load(DF_FILE)
    idx = _load_json(MAP_FILE)

    H = idx.get("tags", {}).get("H_doublet", {})
    all_idx = H.get("all", None)
    if not all_idx:
        raise SystemExit("[Δ2 MODULE] index_map missing tags.H_doublet.all indices")

    # Ensure indices are ints
    try:
        all_idx = [int(i) for i in all_idx]
    except Exception:
        raise SystemExit("[Δ2 MODULE] tags.H_doublet.all must be a list of integer indices")

    sub = DF[np.ix_(all_idx, all_idx)]

    # smallest nonzero singular value
    svals = np.linalg.svd(sub, compute_uv=False)
    eps = 1e-18
    nz = [float(s) for s in svals if s > eps]
    if not nz:
        raise SystemExit("[Δ2 MODULE] No nonzero singular values in forced doublet block.")
    sigma_H = min(nz)

    mu_on = sigma_H * Lambda
    if not (0.0 < mu_on < Lambda):
        raise SystemExit(f"[Δ2 MODULE] mu_on out of range: mu_on={mu_on}, Lambda={Lambda}")

    Delta2 = -(B2H / (4.0 * math.pi)) * math.log(Lambda / mu_on)

    out = {
        "sigma_H": sigma_H,
        "mu_on_GeV": mu_on,
        "Lambda_GeV": Lambda,
        "Delta2_add_to_inv_alpha2": Delta2,
        "assumptions": {
            "b2H": B2H,
            "definition": "sigma_H = smallest nonzero singular value of D_F restricted to H_doublet",
            "mu_on": "mu_on = sigma_H * Lambda",
            "Delta2": "Delta2 = -(b2H/(4*pi))*ln(Lambda/mu_on)",
        },
        "provenance": {
            "inputs": {
                "constants": CONST_FILE,
                "df_npy": DF_FILE,
                "index_map": MAP_FILE,
            },
            "inputs_sha256": {
                "constants": _sha256_file(CONST_FILE),
                "df_npy": _sha256_file(DF_FILE),
                "index_map": _sha256_file(MAP_FILE),
            },
            "constants_lambda_key_used": lambda_key,
            "meaning": (
                "Δ2 and μ_on are computed module-natively from the forced-doublet block singular value "
                "and the locked unification scale Λ. No low-energy targets are used."
            ),
        },
    }

    os.makedirs(ART_DIR, exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)

    print(f"[Δ2 MODULE] sigma_H = {sigma_H:.12e}")
    print(f"[Δ2 MODULE] mu_on   = {mu_on:.6e} GeV")
    print(f"[Δ2 MODULE] Delta2  = {Delta2:.12f}  (add to 1/alpha2 at mu_on)")
    print(f"[Δ2 MODULE] wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
